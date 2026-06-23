"""Views for the metadata section of the TWF application."""

import json
import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import FormView

from twf.forms.metadata.metadata_forms import ExtractMetadataValuesForm
from twf.models import Page, Document, PageTag, Variation, Workflow
from twf.views.views_base import TWFView, ProjectPermissionMixin

logger = logging.getLogger(__name__)


class TWFMetadataView(LoginRequiredMixin, TWFView):
    """Base view for all project views."""

    template_name = "twf/metadata/overview.html"
    page_title = None

    def get_context_data(self, **kwargs):
        """Get the context data."""
        context = super().get_context_data(**kwargs)
        return context

    def get_sub_navigation(self):
        """Get the sub navigation."""
        sub_nav = [
            {
                "name": "Metadata",
                "options": [
                    {"url": reverse("twf:metadata_overview"), "value": "Overview"},
                    {
                        "url": reverse("twf:metadata_manage"),
                        "value": "Manage Metadata",
                        "permission": "metadata.manage",
                    },
                ],
            },
            {
                "name": "Workflows",
                "options": [
                    {
                        "url": reverse("twf:metadata_review_documents"),
                        "value": "Review Document Metadata",
                        "permission": "metadata.edit",
                    },
                    {
                        "url": reverse("twf:metadata_review_pages"),
                        "value": "Review Page Metadata",
                        "permission": "metadata.edit",
                    },
                ],
            },
            {
                "name": "Manage",
                "options": [
                    {
                        "url": reverse("twf:metadata_load_metadata"),
                        "value": "Load JSON Metadata",
                        "permission": "metadata.manage",
                    },
                    {
                        "url": reverse("twf:metadata_load_sheets_metadata"),
                        "value": "Load Google Sheets Metadata",
                        "permission": "metadata.manage",
                    },
                ],
            },
            {
                "name": "Settings",
                "options": [
                    {
                        "url": reverse("twf:metadata_settings"),
                        "value": "Metadata Settings",
                        "permission": "metadata.manage",
                    },
                    {
                        "url": reverse("twf:google_sheets_settings"),
                        "value": "Google Sheets Connection",
                        "permission": "metadata.manage",
                    },
                ],
            },
        ]
        return sub_nav

    def get_navigation_index(self):
        """Get the navigation index."""
        return 4


class TWFMetadataOverviewView(TWFMetadataView):
    """View for the metadata overview."""

    template_name = "twf/metadata/overview.html"
    page_title = "Metadata"
    show_context_help = False

    def get_context_data(self, **kwargs):
        """Get the context data."""
        context = super().get_context_data(**kwargs)
        project = self.get_project()

        documents = Document.objects.filter(project=project)
        documents_with_metadata_count = documents.exclude(metadata={}).count()

        pages = Page.objects.filter(document__project=project)
        pages_with_metadata_count = pages.exclude(metadata={}).count()

        context["doc_count"] = documents_with_metadata_count
        context["doc_total_count"] = documents.count()

        context["page_count"] = pages_with_metadata_count
        context["page_total_count"] = pages.count()

        try:
            context["doc_coverage"] = (
                documents_with_metadata_count / documents.count() * 100
            )
        except ZeroDivisionError:
            context["doc_coverage"] = 0

        # Get metadata block statistics
        doc_keys = Document.get_distinct_metadata_keys()
        page_keys = Page.get_distinct_metadata_keys()

        # Count documents/pages for each key
        doc_key_counts = {}
        for key in doc_keys:
            count = Document.objects.filter(
                project=project, metadata__has_key=key
            ).count()
            doc_key_counts[key] = count

        page_key_counts = {}
        for key in page_keys:
            count = Page.objects.filter(
                document__project=project, metadata__has_key=key
            ).count()
            page_key_counts[key] = count

        context["doc_keys"] = doc_keys
        context["page_keys"] = page_keys
        context["doc_key_counts"] = doc_key_counts
        context["page_key_counts"] = page_key_counts

        return context


class TWFMetadataExtractTagsView(ProjectPermissionMixin, FormView, TWFMetadataView):
    """View for extracting metadata values."""
    required_permission = "metadata.manage"

    template_name = "twf/metadata/extract.html"
    page_title = "Extract Metadata Values"
    form_class = ExtractMetadataValuesForm
    success_url = reverse_lazy("twf:metadata_extract")

    def form_valid(self, form):
        # Save the metadata
        form.is_valid()

        # Get the project
        project = self.get_project()

        # Get the json data key and the dictionary
        extract_from = "documents"  # form.cleaned_data['extract_from']
        json_data_key = form.cleaned_data["json_data_key"]
        dictionary = form.cleaned_data["dictionary"]
        extracted_values = 0

        if extract_from == "documents":
            data = Document.objects.filter(project=project)
            for doc in data:
                if "json_import" in doc.metadata:
                    metadata = doc.metadata["json_import"]
                    if json_data_key in metadata:
                        page = doc.pages.order_by("tk_page_number").first()

                        if page.tags.filter(variation=metadata[json_data_key]).exists():
                            page.tags.filter(variation=metadata[json_data_key]).delete()

                        tag = PageTag(
                            page=page,
                            variation=metadata[json_data_key],
                            variation_type=dictionary.type,
                            dictionary_entry=None,
                        )
                        # Try to assign the tag to its dictionary entry
                        variations = Variation.objects.filter(
                            entry__dictionary=dictionary,
                            variation=metadata[json_data_key],
                        )
                        if variations.exists():
                            tag.dictionary_entry = variations.first().entry

                        tag.save(current_user=self.request.user)
                        extracted_values += 1
                else:
                    logger.warning("Document %s has no json metadata", doc)

        elif extract_from == "pages":
            data = Page.objects.filter(document__project=project)
            for page in data:
                if "json_import" in page.metadata:
                    metadata = page.metadata["json_import"]
                    if json_data_key in metadata:
                        tag = PageTag(
                            page=page,
                            variation=metadata[json_data_key],
                            variation_type=dictionary.type,
                            dictionary_entry=None,
                        )

                        # Try to assign the tag to its dictionary entry
                        variations = Variation.objects.filter(
                            entry__dictionary=dictionary,
                            variation=metadata[json_data_key],
                        )
                        if variations.exists():
                            tag.dictionary_entry = variations.first().entry

                        tag.save(current_user=self.request.user)
                        extracted_values += 1
                else:
                    logger.warning("Page %s has no json metadata", page)

        else:
            pass

        messages.success(
            self.request, f"Extracted {extracted_values} values from the metadata."
        )
        return super().form_valid(form)

    def get_example_keys(self):
        """Get example keys for the metadata."""
        return [
            "dbid",
            "docid",
            "title",
            "author",
            "date",
            "language",
            "genre",
            "keywords",
            "notes",
        ]

    def get_context_data(self, **kwargs):
        """Get the context data."""
        context = super().get_context_data(**kwargs)
        context["found_key"] = self.get_example_keys()
        return context

    def get_form_kwargs(self):
        """Get the form kwargs."""
        kwargs = super().get_form_kwargs()
        kwargs["project"] = self.get_project()
        return kwargs


class TWFMetadataReviewPagesView(ProjectPermissionMixin, TWFMetadataView):
    """View for reviewing page metadata with workflow support."""
    required_permission = "metadata.edit"

    template_name = "twf/metadata/review_page.html"
    page_title = "Review Page Metadata"

    def get_context_data(self, **kwargs):
        """Get the context data."""
        context = super().get_context_data(**kwargs)

        # Fetch the current workflow
        workflow = (
            Workflow.objects.filter(
                project=self.get_project(),
                workflow_type="review_metadata_pages",
                user=self.request.user,
                status="started",
            )
            .order_by("created_at")
            .first()
        )

        if not workflow:
            context["has_active_workflow"] = False
            # Count pages with metadata that need review
            pages_with_metadata = Page.objects.filter(
                document__project=self.get_project()
            ).exclude(metadata={}).count()
            context["available_items_count"] = pages_with_metadata
            return context

        context["has_active_workflow"] = True

        # Fetch the next page
        next_page = workflow.get_next_item()
        context["workflow"] = workflow
        context["workflow_definition"] = workflow.get_workflow_definition()
        context["page"] = next_page

        # Get field configuration
        conf_tasks = self.get_project().conf_tasks or {}
        metadata_config = conf_tasks.get("metadata_review", {})

        # Try to get new config first, fallback to legacy
        field_config_str = metadata_config.get("page_field_config", "")
        if field_config_str:
            try:
                field_config = json.loads(field_config_str)
            except (json.JSONDecodeError, TypeError):
                field_config = {}
        else:
            # Fallback to legacy config
            page_config = metadata_config.get("page_metadata_review", {})
            if isinstance(page_config, str):
                try:
                    field_config = json.loads(page_config)
                except json.JSONDecodeError:
                    field_config = {}
            else:
                field_config = page_config if isinstance(page_config, dict) else {}

        context["field_config"] = field_config

        if next_page:
            context["metadata"] = next_page.metadata
            context["document"] = next_page.document

            # Prepare field values for easy access in template
            field_values = {}
            for field_key in field_config.keys():
                keys = field_key.split(".")
                value = next_page.metadata
                try:
                    for key in keys:
                        value = value.get(key, "")
                    field_values[field_key] = value if value else ""
                except (AttributeError, TypeError):
                    field_values[field_key] = ""
            context["field_values"] = field_values
        else:
            context["metadata"] = {}
            context["document"] = None
            context["field_values"] = {}

        return context

    def post(self, request, *args, **kwargs):
        """Handle page metadata review workflow actions."""
        action = request.POST.get("action")

        # Handle workflow start
        if action == "start_workflow":
            batch_size = int(request.POST.get("batch_size", 10))

            # Get pages with metadata that aren't already in a workflow
            available_pages = (
                Page.objects.filter(document__project=self.get_project())
                .exclude(metadata={})
                .exclude(workflows__workflow_type="review_metadata_pages", workflows__status="started")
                .order_by("modified_at")[:batch_size]
            )

            if not available_pages.exists():
                messages.warning(request, "No pages with metadata available for review.")
                return redirect("twf:metadata_review_pages")

            # Create task for workflow tracking
            from twf.tasks.instant_tasks import start_related_task
            task = start_related_task(
                self.get_project(),
                request.user,
                "Review Page Metadata",
                "Review metadata for pages in the project.",
                f"The user has started a workflow to review metadata for {available_pages.count()} page(s).",
            )

            # Create workflow
            workflow = Workflow.objects.create(
                project=self.get_project(),
                user=request.user,
                workflow_type="review_metadata_pages",
                item_count=available_pages.count(),
                status="started",
                related_task=task,
            )

            # Initialize workflow_steps in the related task
            if task:
                task.workflow_steps = {
                    "current_step": 0,
                    "total_steps": available_pages.count(),
                    "steps": [],
                    "workflow_type": "review_metadata_pages",
                    "started_at": task.start_time.isoformat() if task.start_time else None
                }
                task.save(update_fields=["workflow_steps"])

            # Assign pages to workflow
            workflow.assigned_page_items.set(available_pages)

            messages.success(
                request,
                f"Started metadata review workflow with {available_pages.count()} pages.",
            )
            return redirect("twf:metadata_review_pages")

        # Handle workflow actions
        workflow = (
            Workflow.objects.filter(
                project=self.get_project(),
                workflow_type="review_metadata_pages",
                user=request.user,
                status="started",
            )
            .order_by("created_at")
            .first()
        )

        if not workflow:
            messages.error(request, "No active workflow found.")
            return redirect("twf:metadata_review_pages")

        page_id = request.POST.get("page_id")
        if page_id:
            page = Page.objects.filter(id=page_id).first()

            if page:
                # Get field config to know which fields to save
                conf_tasks = self.get_project().conf_tasks or {}
                metadata_config = conf_tasks.get("metadata_review", {})
                field_config_str = metadata_config.get("page_field_config", "")

                if field_config_str:
                    try:
                        field_config = json.loads(field_config_str)
                    except (json.JSONDecodeError, TypeError):
                        field_config = {}
                else:
                    field_config = {}

                # Update metadata for configured fields
                if field_config:
                    metadata = page.metadata.copy()
                    for field_key, config in field_config.items():
                        if config.get("include"):
                            field_value = request.POST.get(f"field_{field_key.replace('.', '_')}")
                            if field_value is not None:
                                keys = field_key.split(".")
                                set_nested_value(metadata, keys, field_value)
                    page.metadata = metadata

                # Handle different actions
                if action == "save_and_next":
                    page.save(current_user=request.user)
                    messages.success(request, f"Saved metadata for page {page}")

                    # Build item description for task logging
                    page_desc = f"Page {page.tk_page_number} of document {page.document.document_id}"

                    if workflow.has_more_items():
                        workflow.advance(item_description=page_desc)
                    else:
                        workflow.finish()
                        messages.success(request, "Workflow completed!")

                elif action == "skip":
                    messages.info(request, "Skipped page")

                    # Build item description for task logging
                    page_desc = f"Page {page.tk_page_number} of document {page.document.document_id} (skipped)"

                    if workflow.has_more_items():
                        workflow.advance(item_description=page_desc)
                    else:
                        workflow.finish()
                        messages.success(request, "Workflow completed!")

        return redirect("twf:metadata_review_pages")


import logging


def set_nested_value(d, keys, value):
    """Helper function to set a value in a nested dictionary or list using a list of keys."""
    for key in keys[:-1]:
        logging.info(f"Current d: {d}, current key: {key}")
        if key.isdigit():
            key = int(key)
            if isinstance(d, list):
                while len(d) <= key:
                    d.append({})
            else:
                raise ValueError(
                    f"Expected a list at {key}, but found {type(d).__name__}"
                )
            d = d[key]
        else:
            if isinstance(d, dict):
                d = d.setdefault(key, {})
            else:
                raise ValueError(
                    f"Expected a dict at {key}, but found {type(d).__name__}"
                )

    last_key = keys[-1]
    logging.info(f"Final d before setting value: {d}, final key: {last_key}")
    if last_key.isdigit():
        last_key = int(last_key)
        if isinstance(d, list):
            while len(d) <= last_key:
                d.append({})
            d[last_key] = value
        else:
            raise ValueError(
                f"Expected a list at {last_key}, but found {type(d).__name__}"
            )
    else:
        if isinstance(d, dict):
            d[last_key] = value
        elif isinstance(d, list):
            raise ValueError(
                f"Expected a dict at {last_key}, but found a list. Possibly incorrect key sequence: {keys}"
            )
        else:
            raise ValueError(f"Unexpected type {type(d).__name__} at {last_key}.")


class TWFMetadataReviewDocumentsView(ProjectPermissionMixin, TWFMetadataView):
    """View for reviewing document metadata with workflow support."""
    required_permission = "metadata.edit"

    template_name = "twf/metadata/review_document.html"
    page_title = "Review Document Metadata"

    def get_context_data(self, **kwargs):
        """Get the context data."""
        context = super().get_context_data(**kwargs)

        # Fetch the current workflow
        workflow = (
            Workflow.objects.filter(
                project=self.get_project(),
                workflow_type="review_metadata_documents",
                user=self.request.user,
                status="started",
            )
            .order_by("created_at")
            .first()
        )

        if not workflow:
            context["has_active_workflow"] = False
            # Count documents with metadata that need review
            docs_with_metadata = Document.objects.filter(
                project=self.get_project()
            ).exclude(metadata={}).count()
            context["available_items_count"] = docs_with_metadata
            return context

        context["has_active_workflow"] = True

        # Fetch the next document
        next_document = workflow.get_next_item()
        context["workflow"] = workflow
        context["workflow_definition"] = workflow.get_workflow_definition()
        context["document"] = next_document

        # Get field configuration
        conf_tasks = self.get_project().conf_tasks or {}
        metadata_config = conf_tasks.get("metadata_review", {})

        # Try to get new config first, fallback to legacy
        field_config_str = metadata_config.get("document_field_config", "")
        if field_config_str:
            try:
                field_config = json.loads(field_config_str)
            except (json.JSONDecodeError, TypeError):
                field_config = {}
        else:
            # Fallback to legacy config
            doc_config = metadata_config.get("document_metadata_review", {})
            if isinstance(doc_config, str):
                try:
                    field_config = json.loads(doc_config)
                except json.JSONDecodeError:
                    field_config = {}
            else:
                field_config = doc_config if isinstance(doc_config, dict) else {}

        context["field_config"] = field_config

        if next_document:
            context["metadata"] = next_document.metadata
            context["workflow_remarks"] = next_document.workflow_remarks

            # Prepare field values for easy access in template
            field_values = {}
            for field_key in field_config.keys():
                keys = field_key.split(".")
                value = next_document.metadata
                try:
                    for key in keys:
                        value = value.get(key, "")
                    field_values[field_key] = value if value else ""
                except (AttributeError, TypeError):
                    field_values[field_key] = ""
            context["field_values"] = field_values
        else:
            context["metadata"] = {}
            context["workflow_remarks"] = ""
            context["field_values"] = {}

        return context

    def post(self, request, *args, **kwargs):
        """Handle document metadata review workflow actions."""
        action = request.POST.get("action")

        # Handle workflow start
        if action == "start_workflow":
            batch_size = int(request.POST.get("batch_size", 10))

            # Get documents with metadata that aren't already in a workflow
            available_documents = (
                Document.objects.filter(project=self.get_project())
                .exclude(metadata={})
                .exclude(workflows__workflow_type="review_metadata_documents", workflows__status="started")
                .order_by("modified_at")[:batch_size]
            )

            if not available_documents.exists():
                messages.warning(request, "No documents with metadata available for review.")
                return redirect("twf:metadata_review_documents")

            # Create task for workflow tracking
            from twf.tasks.instant_tasks import start_related_task
            task = start_related_task(
                self.get_project(),
                request.user,
                "Review Document Metadata",
                "Review metadata for documents in the project.",
                f"The user has started a workflow to review metadata for {available_documents.count()} document(s).",
            )

            # Create workflow
            workflow = Workflow.objects.create(
                project=self.get_project(),
                user=request.user,
                workflow_type="review_metadata_documents",
                item_count=available_documents.count(),
                status="started",
                related_task=task,
            )

            # Initialize workflow_steps in the related task
            if task:
                task.workflow_steps = {
                    "current_step": 0,
                    "total_steps": available_documents.count(),
                    "steps": [],
                    "workflow_type": "review_metadata_documents",
                    "started_at": task.start_time.isoformat() if task.start_time else None
                }
                task.save(update_fields=["workflow_steps"])

            # Assign documents to workflow
            workflow.assigned_document_items.set(available_documents)

            messages.success(
                request,
                f"Started metadata review workflow with {available_documents.count()} documents.",
            )
            return redirect("twf:metadata_review_documents")

        # Handle workflow actions
        workflow = (
            Workflow.objects.filter(
                project=self.get_project(),
                workflow_type="review_metadata_documents",
                user=request.user,
                status="started",
            )
            .order_by("created_at")
            .first()
        )

        if not workflow:
            messages.error(request, "No active workflow found.")
            return redirect("twf:metadata_review_documents")

        document_id = request.POST.get("document_id")
        if document_id:
            document = Document.objects.filter(id=document_id).first()

            if document:
                # Get field config to know which fields to save
                conf_tasks = self.get_project().conf_tasks or {}
                metadata_config = conf_tasks.get("metadata_review", {})
                field_config_str = metadata_config.get("document_field_config", "")

                if field_config_str:
                    try:
                        field_config = json.loads(field_config_str)
                    except (json.JSONDecodeError, TypeError):
                        field_config = {}
                else:
                    field_config = {}

                # Update metadata for configured fields
                if field_config:
                    metadata = document.metadata.copy()
                    for field_key, config in field_config.items():
                        if config.get("include"):
                            field_value = request.POST.get(f"field_{field_key.replace('.', '_')}")
                            if field_value is not None:
                                keys = field_key.split(".")
                                set_nested_value(metadata, keys, field_value)
                    document.metadata = metadata

                # Save workflow remarks
                workflow_remarks = request.POST.get("workflow_remarks", "").strip()
                if workflow_remarks:
                    document.workflow_remarks = workflow_remarks

                # Build item description for task logging
                doc_desc = f"Document {document.document_id}"
                if document.title:
                    doc_desc += f" ({document.title})"

                # Handle different actions
                if action == "save_and_next":
                    document.save()
                    messages.success(request, f"Saved metadata for document {document}")
                    if workflow.has_more_items():
                        workflow.advance(item_description=doc_desc)
                    else:
                        workflow.finish()
                        messages.success(request, "Workflow completed!")

                elif action == "park":
                    document.is_parked = True
                    document.save()
                    messages.success(request, f"Parked document {document}")
                    if workflow.has_more_items():
                        workflow.advance(item_description=doc_desc + " (parked)")
                    else:
                        workflow.finish()
                        messages.success(request, "Workflow completed!")

                elif action == "skip":
                    messages.info(request, "Skipped document")
                    if workflow.has_more_items():
                        workflow.advance(item_description=doc_desc + " (skipped)")
                    else:
                        workflow.finish()
                        messages.success(request, "Workflow completed!")

        return redirect("twf:metadata_review_documents")


class TWFMetadataSettingsView(ProjectPermissionMixin, FormView, TWFMetadataView):
    """View for metadata review settings."""
    required_permission = "metadata.manage"

    template_name = "twf/metadata/settings.html"
    page_title = "Metadata Review Settings"
    success_url = reverse_lazy("twf:metadata_settings")

    def get_form_class(self):
        """Return the form class."""
        from twf.forms.metadata.metadata_review_settings_forms import (
            MetadataReviewSettingsForm,
        )

        return MetadataReviewSettingsForm

    def get_form_kwargs(self):
        """Add project to form kwargs."""
        kwargs = super().get_form_kwargs()
        kwargs["project"] = self.get_project()
        return kwargs

    def form_valid(self, form):
        """Handle successful form submission."""
        if form.save():
            messages.success(self.request, "Metadata review settings saved successfully.")
        else:
            messages.error(self.request, "Failed to save metadata review settings.")
        return super().form_valid(form)


class TWFGoogleSheetsSettingsView(ProjectPermissionMixin, FormView, TWFMetadataView):
    """View for Google Sheets settings."""
    required_permission = "metadata.manage"

    template_name = "twf/metadata/google_sheets_settings.html"
    page_title = "Google Sheets Settings"
    success_url = reverse_lazy("twf:google_sheets_settings")

    def get_form_class(self):
        """Return the form class."""
        from twf.forms.metadata.google_sheets_forms import GoogleSheetsSettingsForm

        return GoogleSheetsSettingsForm

    def get_form_kwargs(self):
        """Add project to form kwargs."""
        kwargs = super().get_form_kwargs()
        kwargs["project"] = self.get_project()
        return kwargs

    def form_valid(self, form):
        """Handle successful form submission."""
        if form.save():
            messages.success(self.request, "Google Sheets settings saved successfully.")
        else:
            messages.error(self.request, "Failed to save Google Sheets settings.")
        return super().form_valid(form)


class TWFMetadataManagementView(ProjectPermissionMixin, FormView, TWFMetadataView):
    """View for managing (deleting) metadata blocks."""
    required_permission = "metadata.manage"

    template_name = "twf/metadata/manage.html"
    page_title = "Manage Metadata"
    success_url = reverse_lazy("twf:metadata_manage")

    def get_form_class(self):
        """Return the form class."""
        from twf.forms.metadata.metadata_management_forms import MetadataManagementForm

        return MetadataManagementForm

    def get_form_kwargs(self):
        """Add project to form kwargs."""
        kwargs = super().get_form_kwargs()
        kwargs["project"] = self.get_project()
        return kwargs

    def get_context_data(self, **kwargs):
        """Get the context data."""
        context = super().get_context_data(**kwargs)
        project = self.get_project()

        # Get metadata statistics
        doc_keys = Document.get_distinct_metadata_keys()
        page_keys = Page.get_distinct_metadata_keys()

        # Count documents/pages for each key
        doc_key_counts = {}
        for key in doc_keys:
            count = Document.objects.filter(
                project=project, metadata__has_key=key
            ).count()
            doc_key_counts[key] = count

        page_key_counts = {}
        for key in page_keys:
            count = Page.objects.filter(
                document__project=project, metadata__has_key=key
            ).count()
            page_key_counts[key] = count

        context["doc_keys"] = doc_keys
        context["page_keys"] = page_keys
        context["doc_key_counts"] = doc_key_counts
        context["page_key_counts"] = page_key_counts

        return context

    def form_valid(self, form):
        """Handle successful form submission."""
        deleted_count = form.save(user=self.request.user)
        target_type = form.cleaned_data["target_type"]
        metadata_key = form.cleaned_data["metadata_key"]

        messages.success(
            self.request,
            f"Successfully deleted metadata block '{metadata_key}' from {deleted_count} {target_type}(s).",
        )
        return super().form_valid(form)
