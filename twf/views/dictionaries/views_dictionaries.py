"""Views for the dictionary overview and the dictionary entries."""

import logging
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import FormView
from django_filters.views import FilterView
from django_tables2 import SingleTableView

from twf.forms.filters.filters import DictionaryEntryFilter, DictionaryFilter
from twf.forms.dictionaries.dictionaries_forms import (
    DictionaryForm,
    DictionaryEntryForm,
    MergeEntriesForm,
)
from twf.forms.dictionaries.dictionary_settings_forms import DictionarySettingsForm
from twf.forms.enrich_forms import EnrichEntryManualForm, EnrichEntryForm
from twf.forms.tags.enrichment_forms import get_enrichment_form_class
from twf.models import Dictionary, DictionaryEntry, Variation, PageTag, Workflow
from twf.utils.project_statistics import get_dictionary_statistics, get_dictionary_state_statistics
from twf.workflows.dictionary_workflows import (
    create_dictionary_enrichment_workflow,
    create_dictionary_review_workflow,
)
from twf.tasks.instant_tasks import save_instant_task_merge_entries
from twf.tables.tables_dictionary import (
    DictionaryTable,
    DictionaryEntryTable,
    DictionaryEntryVariationTable,
    DictionaryAddTable,
)
from twf.views.views_base import TWFView, ProjectPermissionMixin

logger = logging.getLogger(__name__)

class TWFDictionaryView(LoginRequiredMixin, TWFView):
    """Base view for all dictionary views."""

    template_name = None

    def get_sub_navigation(self):
        """Get the sub navigation."""
        sub_nav = [
            {
                "name": "Dictionaries",
                "options": [
                    {"url": reverse("twf:dictionaries_overview"), "value": "Overview"},
                    {
                        "url": reverse("twf:dictionaries"),
                        "value": "Dictionaries",
                        "permission": "dictionary.view",
                    },

                ],
            },
            {
                "name": "Workflows",
                "options": [
                    {
                        "url": reverse("twf:dictionaries_enrichment"),
                        "value": "Manual Enrichment",
                        "permission": "dictionary.edit",
                    },
                    {
                        "url": reverse("twf:dictionaries_review_entries"),
                        "value": "Review Entries",
                        "permission": "dictionary.edit",
                    },
                    {
                        "url": reverse("twf:dictionaries_merge_entries"),
                        "value": "Merge Entries",
                        "permission": "dictionary.manage",
                    },
                    {
                        "url": reverse("twf:dictionaries_batch_gnd"),
                        "value": "GND Batch",
                        "permission": "dictionary.manage",
                    },
                    {
                        "url": reverse("twf:dictionaries_batch_wikidata"),
                        "value": "Wikidata Batch",
                        "permission": "dictionary.manage",
                    },
                    {
                        "url": reverse("twf:dictionaries_batch_geonames"),
                        "value": "GeoNames Batch",
                        "permission": "dictionary.manage",
                    },
                ],
            },
            {
                "name": "Settings",
                "options": [
                    {
                        "url": reverse("twf:dictionaries_settings"),
                        "value": "Enrichment Settings",
                        "permission": "dictionary.manage",
                    },
                    {
                        "url": reverse("twf:dictionaries_add"),
                        "value": "Add Dictionaries",
                        "permission": "dictionary.manage",
                    },
                    {
                        "url": reverse("twf:dictionary_create"),
                        "value": "Create New Dictionary",
                        "permission": "dictionary.manage",
                    },
                ],
            },
        ]
        return sub_nav

    def get_navigation_index(self):
        """Get the navigation index."""
        return 5

    def get_ai_batch_options(self):
        """
        Get the AI batch options.
        Returns simplified navigation with unified AI Batch processing.
        """
        options = [
            {
                "url": reverse("twf:dictionaries_batch_ai_unified"),
                "value": "AI Batch Processing",
                "permission": "dictionary.manage",
            }
        ]
        return options

    def get_ai_request_options(self):
        """
        Get the AI request options.
        Returns simplified navigation with unified AI Request processing.
        """
        options = [
            {
                "url": reverse("twf:dictionaries_request_ai_unified"),
                "value": "AI Request",
                "permission": "dictionary.edit",
            }
        ]
        return options

    def get_dictionaries(self):
        """Get the dictionaries."""
        project = self.get_project()
        return project.selected_dictionaries.all()

    def get_context_data(self, **kwargs):
        """Get the context data."""
        context = super().get_context_data(**kwargs)
        return context

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.page_title is None:
            self.page_title = kwargs.get("page_title", "Dictionary View")


class TWFDictionaryOverviewView(TWFDictionaryView):
    """View for the dictionary overview."""

    template_name = "twf/dictionaries/overview.html"
    page_title = "Dictionaries"
    show_context_help = False

    def get_context_data(self, **kwargs):
        """Get the context data."""
        context = super().get_context_data(**kwargs)
        project = self.get_project()
        context["dict_stats"] = get_dictionary_statistics(project)
        context["dict_state_stats"] = get_dictionary_state_statistics(project)
        return context


class TWFDictionaryDictionariesView(ProjectPermissionMixin, SingleTableView, FilterView, TWFDictionaryView):
    """View for the dictionaries. Provides a table of all dictionaries.
    The table is filterable and sortable."""
    required_permission = "dictionary.view"

    template_name = "twf/dictionaries/dictionaries.html"
    page_title = "Dictionaries Overview"
    table_class = DictionaryTable
    filterset_class = DictionaryFilter
    paginate_by = 10
    model = Dictionary
    strict = False  # Don't enforce form validation for filters

    def get_queryset(self):
        """Get the queryset."""
        project = self.get_project()
        queryset = project.selected_dictionaries.all()
        self.filterset = self.filterset_class(
            self.request.GET or None, queryset=queryset
        )

        # If filter is applied, return filtered queryset
        if self.request.GET and self.filterset.is_bound:
            return self.filterset.qs
        return queryset

    def get(self, request, *args, **kwargs):
        """Handle the GET request with proper filter handling."""
        # Set up initial queryset
        project = self.get_project()
        queryset = project.selected_dictionaries.all()

        # Initialize the filter
        self.filterset = self.filterset_class(request.GET or None, queryset=queryset)

        # Set object_list either to all items or filtered items
        if request.GET and self.filterset.is_bound:
            self.object_list = self.filterset.qs
        else:
            self.object_list = queryset

        # Get context and render response
        context = self.get_context_data()
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        """Get the context data."""
        context = super().get_context_data(**kwargs)
        context["filter"] = self.filterset
        return context


class TWFDictionaryAddView(ProjectPermissionMixin, SingleTableView, FilterView, TWFDictionaryView):
    """View for adding dictionaries to the project."""
    required_permission = "dictionary.manage"

    template_name = "twf/dictionaries/dictionaries_add.html"
    page_title = "Add Dictionaries"
    table_class = DictionaryAddTable
    filterset_class = DictionaryFilter
    paginate_by = 10
    model = Dictionary
    strict = False  # Don't enforce form validation for filters

    def get_queryset(self):
        """Get the queryset of dictionaries not already in the project."""
        project = self.get_project()

        # Get the IDs of dictionaries already in the project more efficiently
        selected_dictionary_ids = project.selected_dictionaries.values_list(
            "id", flat=True
        )

        # Get all dictionaries except those already in the project
        queryset = Dictionary.objects.exclude(id__in=selected_dictionary_ids)

        # Initialize the filter
        self.filterset = self.filterset_class(
            self.request.GET or None, queryset=queryset
        )

        # If filter is applied, return filtered queryset
        if self.request.GET and self.filterset.is_bound:
            return self.filterset.qs
        return queryset

    def get(self, request, *args, **kwargs):
        """Handle the GET request with proper filter handling."""
        # Get the queryset using the existing method to avoid code duplication
        queryset = self.get_queryset()

        # Set object_list to the queryset
        self.object_list = queryset

        # Log the count for debugging
        logger.debug(f"Available dictionaries count: {queryset.count()}")

        # Get context and render response
        context = self.get_context_data()
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        """Get the context data."""
        context = super().get_context_data(**kwargs)
        context["filter"] = self.filterset
        return context


class TWFDictionaryCreateView(ProjectPermissionMixin, FormView, TWFDictionaryView):
    """Create a new dictionary."""
    required_permission = "dictionary.manage"

    template_name = "twf/dictionaries/create.html"
    form_class = DictionaryForm
    success_url = reverse_lazy("twf:dictionaries")

    def form_valid(self, form):
        """Handle the form submission."""
        # Save the form
        form.instance.save(current_user=self.request.user)
        project = self.get_project()
        project.selected_dictionaries.add(form.instance)
        project.save()

        # Add a success message
        messages.success(
            self.request,
            "Dictionary has been created successfully and has been added to your project.",
        )

        # Redirect to the success URL
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        """Get the context data."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Create New Dictionary"
        return context


class TWFDictionaryDictionaryView(ProjectPermissionMixin, SingleTableView, FilterView, TWFDictionaryView):
    """View for the dictionary entries. Provides a table of dictionary entries of a single dictionary.
    The table is filterable and sortable."""
    required_permission = "dictionary.view"

    template_name = "twf/dictionaries/dictionary.html"
    page_title = "View Dictionary"
    navigation_anchor = reverse_lazy("twf:dictionaries")

    table_class = DictionaryEntryTable
    filterset_class = DictionaryEntryFilter
    paginate_by = 10
    model = DictionaryEntry
    strict = False  # Don't enforce form validation for filters

    def get_queryset(self):
        """Get the queryset."""
        queryset = DictionaryEntry.objects.filter(dictionary_id=self.kwargs.get("pk"))
        self.filterset = self.filterset_class(
            self.request.GET or None, queryset=queryset
        )

        # If filter is applied, return filtered queryset
        if self.request.GET and self.filterset.is_bound:
            return self.filterset.qs
        return queryset

    def get(self, request, *args, **kwargs):
        """Handle the GET request with proper filter handling."""
        # Set up initial queryset
        queryset = DictionaryEntry.objects.filter(dictionary_id=self.kwargs.get("pk"))

        # Initialize the filter
        self.filterset = self.filterset_class(request.GET or None, queryset=queryset)

        # Set object_list either to all items or filtered items
        if request.GET and self.filterset.is_bound:
            self.object_list = self.filterset.qs
        else:
            self.object_list = queryset

        # Get context and render response
        context = self.get_context_data()
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        """Get the context data."""
        context = super().get_context_data(**kwargs)
        context["dictionary"] = Dictionary.objects.get(pk=self.kwargs.get("pk"))
        context["filter"] = self.filterset
        return context

    def get_breadcrumbs(self):
        """Get the breadcrumbs for dictionary entry view."""
        # Start with home and dictionaries section
        breadcrumbs = [
            {"url": reverse("twf:home"), "value": '<i class="fas fa-home"></i>'},
            {"url": reverse("twf:dictionaries"), "value": "Dictionaries"},
        ]

        # Get the entry and its dictionary
        dictionary = Dictionary.objects.get(pk=self.kwargs.get("pk"))
        breadcrumbs.append(
            {
                "url": reverse("twf:dictionaries_view", args=[dictionary.pk]),
                "value": dictionary.label,
            }
        )
        return breadcrumbs


class TWFDictionaryDictionaryEntryView(ProjectPermissionMixin, SingleTableView, TWFDictionaryView):
    """View for a single dictionary entry."""
    required_permission = "dictionary.view"

    template_name = "twf/dictionaries/dictionary_entry.html"
    page_title = "View Dictionary Entry"
    table_class = DictionaryEntryVariationTable
    navigation_anchor = reverse_lazy("twf:dictionaries")

    def get_queryset(self):
        """Get the queryset."""
        return Variation.objects.filter(entry_id=self.kwargs.get("pk"))

    def get(self, request, *args, **kwargs):
        """Handle the GET request."""
        self.object_list = self.get_queryset()
        context = self.get_context_data()
        return self.render_to_response(context)

    def get_breadcrumbs(self):
        """Get the breadcrumbs for dictionary entry view."""
        # Start with home and dictionaries section
        breadcrumbs = [
            {"url": reverse("twf:home"), "value": '<i class="fas fa-home"></i>'},
            {"url": reverse("twf:dictionaries_overview"), "value": "Dictionaries"},
            {"url": reverse("twf:dictionaries"), "value": "Dictionary List"},
        ]

        # Get the entry and its dictionary
        entry = self.get_entry()
        if entry:
            # Add the dictionary to the breadcrumbs
            breadcrumbs.append(
                {
                    "url": reverse("twf:dictionaries_view", args=[entry.dictionary.pk]),
                    "value": entry.dictionary.label,
                }
            )

            # Add the entry itself
            breadcrumbs.append(
                {"url": self.request.path, "value": f"Entry: {entry.label}"}
            )

        return breadcrumbs

    def get_entry(self):
        """Get the dictionary entry."""
        try:
            return DictionaryEntry.objects.get(pk=self.kwargs.get("pk"))
        except DictionaryEntry.DoesNotExist:
            return None

    def get_context_data(self, **kwargs):
        """Get the context data."""
        context = super().get_context_data(**kwargs)
        table = self.table_class(self.object_list, project=self.get_project())
        context["table"] = table

        entry = self.get_entry()
        context["entry"] = entry

        # Check if entry has enrichment data
        if entry and entry.metadata:
            # Filter enrichment data (keys that have normalized_value and enrichment_data structure)
            enrichment_data = {}
            for key, value in entry.metadata.items():
                if isinstance(value, dict) and "normalized_value" in value and "enrichment_data" in value:
                    enrichment_data[key] = value

            context["has_enrichment"] = bool(enrichment_data)
            context["enrichment_data"] = enrichment_data
        else:
            context["has_enrichment"] = False
            context["enrichment_data"] = {}

        return context


class TWFDictionaryDictionaryEditView(ProjectPermissionMixin, FormView, TWFDictionaryView):
    """Edit a dictionary."""
    required_permission = "dictionary.manage"

    template_name = "twf/dictionaries/dictionary_edit.html"
    page_title = "Edit Dictionary"
    form_class = DictionaryForm
    success_url = reverse_lazy("twf:dictionaries")
    navigation_anchor = reverse_lazy("twf:dictionaries")

    def get_context_data(self, **kwargs):
        """Get the context data."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.page_title
        context["dictionary"] = (
            Dictionary.objects.get(pk=self.kwargs.get("pk"))
            if self.kwargs.get("pk")
            else None
        )
        return context

    def get_form_kwargs(self):
        """Get the form kwargs."""
        kwargs = super().get_form_kwargs()
        if self.kwargs.get("pk"):
            kwargs["instance"] = Dictionary.objects.get(pk=self.kwargs.get("pk"))
        return kwargs

    def form_valid(self, form):
        """Handle the form submission."""
        # Save the form
        form.instance.save(current_user=self.request.user)
        # Add a success message
        messages.success(
            self.request, "Dictionary settings have been updated successfully."
        )
        # Redirect to the success URL
        return super().form_valid(form)


class TWFDictionaryNormDataView(ProjectPermissionMixin, TWFDictionaryView):
    """Normalization Data Wizard."""
    required_permission = "dictionary.manage"

    template_name = "twf/dictionaries/normalization_wizard.html"
    page_title = "Normalization Data Wizard"
    navigation_anchor = reverse_lazy("twf:dictionaries_normalization")

    def post(self, request, *args, **kwargs):
        """Handle the POST request."""
        if "submit_geonames" in request.POST:
            logger.debug("Dictionary normalization - submit_geonames selected")
        elif "submit_gnd" in request.POST:
            logger.debug("Dictionary normalization - submit_gnd selected")
        elif "submit_wikidata" in request.POST:
            logger.debug("Dictionary normalization - submit_wikidata selected")
        elif "submit_openai" in request.POST:
            logger.debug("Dictionary normalization - submit_openai selected")

        return redirect("twf:dictionaries_normalization")

    def get_context_data(self, **kwargs):
        """Get the context data."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.page_title
        dictionaries = self.get_dictionaries()
        context["selected_dict"] = self.request.GET.get(
            "selected_dict", dictionaries[0].type
        )
        context["next_unenriched_entry"] = self.get_next_unenriched_entry(
            context["selected_dict"]
        )

        label = (
            context["next_unenriched_entry"].label
            if context["next_unenriched_entry"]
            else None
        )
        context["form_manual"] = EnrichEntryManualForm(
            instance=context["next_unenriched_entry"]
        )
        context["form_geonames"] = EnrichEntryForm(
            search_term=label, form_name="geonames"
        )
        context["form_gnd"] = EnrichEntryForm(search_term=label, form_name="gnd")
        context["form_wikidata"] = EnrichEntryForm(
            search_term=label, form_name="wikidata"
        )
        # context['form_openai'] = GeonamesBatchForm()

        return context

    def get_next_unenriched_entry(self, selected_dict):
        """Get the next unenriched entry."""
        dictionary = self.get_project().selected_dictionaries.get(type=selected_dict)
        entry = dictionary.entries.filter(metadata={}).order_by("modified_at").first()
        return entry


class TWFDictionaryMergeEntriesView(ProjectPermissionMixin, TWFDictionaryView):
    """Normalization Data Wizard."""
    required_permission = "dictionary.manage"

    template_name = "twf/dictionaries/merge_entries.html"
    page_title = "Merge Dictionary Entries"

    def post(self, request, *args, **kwargs):
        """Handle the POST request to merge entries."""
        project = self.get_project()
        form = MergeEntriesForm(request.POST, project=project)

        if not form.is_valid():
            messages.error(request, "Please select both entries to merge.")
            return redirect(self.request.path)

        remaining_entry_id = form.cleaned_data["remaining_entry"]
        merge_entry_id = form.cleaned_data["merge_entry"]

        if remaining_entry_id == merge_entry_id:
            messages.error(request, "You cannot merge an entry into itself.")
            return redirect(self.request.path)

        try:
            remaining_entry = DictionaryEntry.objects.get(pk=remaining_entry_id)
            merge_entry = DictionaryEntry.objects.get(pk=merge_entry_id)
        except DictionaryEntry.DoesNotExist:
            messages.error(request, "One of the selected entries does not exist.")
            return redirect(self.request.path)

        # Step 1: Transfer PageTags
        PageTag.objects.filter(dictionary_entry=merge_entry).update(
            dictionary_entry=remaining_entry
        )

        # Step 2: Transfer Variations
        merge_variations = merge_entry.variations.all()
        for variation in merge_variations:
            # Reassign the variation to the remaining entry
            variation.entry = remaining_entry
            variation.save()

        # Step 3: Merge notes and authorization data
        remaining_entry.notes += f"\nMerged Notes:\n{merge_entry.notes}"
        for key, value in merge_entry.metadata.items():
            if key not in remaining_entry.metadata:
                remaining_entry.metadata[key] = value

        remaining_entry.save()

        # Store labels before deletion
        merge_entry_label = merge_entry.label
        remaining_entry_label = remaining_entry.label

        # Step 4: Delete the merged entry
        merge_entry.delete()

        # Create instant task
        save_instant_task_merge_entries(
            project, request.user, remaining_entry_label, merge_entry_label
        )

        messages.success(
            request,
            f"Successfully merged entry '{merge_entry_label}' into '{remaining_entry_label}'.",
        )
        return redirect(self.request.path)

    def get_context_data(self, **kwargs):
        """Get the context data."""
        context = super().get_context_data(**kwargs)
        project = self.get_project()

        # Create form with project
        form = MergeEntriesForm(project=project)
        context["form"] = form

        return context


class TWFDictionaryDictionaryEntryEditView(ProjectPermissionMixin, FormView, TWFDictionaryView):
    """Edit a dictionary entry."""
    required_permission = "dictionary.edit"

    template_name = "twf/dictionaries/dictionary_entry_edit.html"
    page_title = "Edit Dictionary Entry"
    form_class = DictionaryEntryForm
    success_url = reverse_lazy("twf:dictionaries")
    navigation_anchor = reverse_lazy("twf:dictionaries")

    def get_form_kwargs(self):
        """Get the form kwargs."""
        kwargs = super().get_form_kwargs()
        if self.kwargs.get("pk"):
            kwargs["instance"] = self.get_entry()
        return kwargs

    def get_entry(self):
        """Get the dictionary entry."""
        try:
            return DictionaryEntry.objects.get(pk=self.kwargs.get("pk"))
        except DictionaryEntry.DoesNotExist:
            return None

    def get_breadcrumbs(self):
        """Get the breadcrumbs for dictionary entry edit view."""
        # Start with home and dictionaries section
        breadcrumbs = [
            {"url": reverse("twf:home"), "value": '<i class="fas fa-home"></i>'},
            {"url": reverse("twf:dictionaries_overview"), "value": "Dictionaries"},
            {"url": reverse("twf:dictionaries"), "value": "Dictionary List"},
        ]

        # Get the entry and its dictionary
        entry = self.get_entry()
        if entry:
            # Add the dictionary to the breadcrumbs
            breadcrumbs.append(
                {
                    "url": reverse("twf:dictionaries_view", args=[entry.dictionary.pk]),
                    "value": entry.dictionary.label,
                }
            )

            # Add the entry view as another level
            breadcrumbs.append(
                {
                    "url": reverse("twf:dictionaries_entry_view", args=[entry.pk]),
                    "value": entry.label,
                }
            )

            # Add the edit page
            breadcrumbs.append({"url": self.request.path, "value": "Edit"})

        return breadcrumbs

    def get_context_data(self, **kwargs):
        """Get the context data."""
        context = super().get_context_data(**kwargs)
        context["entry"] = self.get_entry()
        return context

    def form_valid(self, form):
        """Handle the form submission."""
        # Check if the delete button was pressed
        if "delete_entry" in self.request.POST:
            # Delete the entry
            entry = form.instance
            entry.delete()

            # Add a success message
            messages.success(
                self.request, "Dictionary Entry has been deleted successfully."
            )

            # Redirect to the success URL
            return redirect(self.success_url)

        # If the save button was pressed, save the form
        if "save_entry" in self.request.POST:
            form.instance.save(current_user=self.request.user)

            # Add a success message
            messages.success(
                self.request,
                "Dictionary Entry settings have been updated successfully.",
            )

            # Redirect to the dictionary view page instead of the dictionaries list
            if form.instance.pk:
                return redirect("twf:dictionaries_entry_view", pk=form.instance.pk)

            # Fallback to the success URL if something went wrong
            return super().form_valid(form)

        # If neither button matches, fallback to the default behavior
        return super().form_invalid(form)

class TWFDictionaryEnrichmentView(ProjectPermissionMixin, FormView, TWFDictionaryView):
    """Generic view for dictionary entry enrichment workflows."""
    required_permission = "dictionary.edit"

    template_name = "twf/dictionaries/enrichment_workflow.html"
    page_title = "Dictionary Enrichment"

    def get_enrichment_type(self):
        """Get enrichment type from workflow metadata."""
        workflow = self.get_active_workflow()
        if workflow and workflow.metadata:
            return workflow.metadata.get("enrichment_type")
        return None

    def get_form_class(self):
        """Return appropriate form class based on enrichment type."""
        workflow = self.get_active_workflow()
        if workflow and workflow.get_next_item():
            enrichment_type = self.get_enrichment_type()
            if enrichment_type:
                return get_enrichment_form_class(enrichment_type)
        return None

    def get_form(self, form_class=None):
        """Return form instance or None if no active workflow."""
        if form_class is None:
            form_class = self.get_form_class()
        if form_class is None:
            return None
        return super().get_form(form_class)

    def get_form_kwargs(self):
        """Add project and item to form kwargs."""
        kwargs = super().get_form_kwargs()
        workflow = self.get_active_workflow()
        if workflow:
            next_entry = workflow.get_next_item()
            if next_entry:
                kwargs["project"] = self.get_project()
                kwargs["item"] = next_entry
        return kwargs

    def get_active_workflow(self):
        """Get active dictionary enrichment workflow for current user."""
        return Workflow.objects.filter(
            project=self.get_project(),
            user=self.request.user,
            workflow_type="review_dictionary_enrichment",
            status="started",
        ).first()

    def post(self, request, *args, **kwargs):
        """Handle the post request."""
        logger.debug(f"POST request received. Buttons: start_workflow={'start_workflow' in request.POST}, search={'search' in request.POST}, save_and_next={'save_and_next' in request.POST}, park_and_next={'park_and_next' in request.POST}")

        # Handle park_and_next action
        if "park_and_next" in request.POST:
            from twf.tasks.instant_tasks import save_instant_task_park_dictionary_entry

            workflow = self.get_active_workflow()
            if not workflow:
                messages.error(request, "No active workflow found.")
                return redirect("twf:dictionaries_enrichment")

            current_entry = workflow.get_next_item()
            if not current_entry:
                messages.error(request, "No entry to park.")
                return redirect("twf:dictionaries_enrichment")

            # Park the entry
            current_entry.is_parked = True
            current_entry.save()

            # Log the action
            save_instant_task_park_dictionary_entry(
                self.get_project(),
                request.user,
                current_entry.label,
                current_entry.id
            )

            # Advance workflow (don't save enrichment, just skip this entry)
            workflow.advance(item_description=f"Parked '{current_entry.label}'")
            messages.info(request, f"Dictionary entry '{current_entry.label}' parked.")

            # Check workflow completion
            if not workflow.get_next_item():
                workflow.finish()
                messages.success(request, "Workflow completed!")

            return redirect("twf:dictionaries_enrichment")

        # Handle workflow start
        if "start_workflow" in request.POST:
            dictionary_id = request.POST.get("dictionary_id")
            enrichment_type = request.POST.get("enrichment_type")
            batch_size = int(request.POST.get("batch_size", 20))

            if dictionary_id and enrichment_type:
                # Validate that enrichment type is configured for this dictionary
                try:
                    dictionary = Dictionary.objects.get(
                        id=int(dictionary_id),
                        selected_projects=self.get_project()
                    )
                    dict_config = self.get_project().get_dictionary_enrichment_config(dictionary.type)
                    configured_types = dict_config.get("enrichment_types", [])

                    # If no configuration exists, allow all types (backward compatibility)
                    if configured_types and enrichment_type not in configured_types:
                        messages.error(
                            request,
                            f"Enrichment type '{enrichment_type}' is not configured for dictionary type '{dictionary.type}'. "
                            f"Please configure it in Dictionary Settings."
                        )
                        return redirect("twf:dictionaries_enrichment")
                except Dictionary.DoesNotExist:
                    messages.error(request, "Dictionary not found.")
                    return redirect("twf:dictionaries_enrichment")

                workflow = create_dictionary_enrichment_workflow(
                    self.get_project(), request.user,
                    int(dictionary_id), enrichment_type, batch_size
                )
                if workflow:
                    messages.success(
                        request, f"Workflow started with {workflow.item_count} entries."
                    )
                else:
                    messages.error(
                        request, "No unenriched entries available for this dictionary and enrichment type."
                    )
            else:
                messages.error(request, "Invalid form data.")
            return redirect("twf:dictionaries_enrichment")

        # Handle search action for query-assisted forms
        if "search" in request.POST:
            import json
            from twf.clients.gnd_client import search_gnd
            from twf.clients.wikidata_client import search_wikidata_entities
            from twf.clients.geonames_client import search_location
            from twf.forms.tags.enrichment_forms import (
                GNDQueryEnrichmentForm,
                WikidataQueryEnrichmentForm,
                GeoNamesQueryEnrichmentForm,
            )

            workflow = self.get_active_workflow()
            if not workflow:
                messages.error(request, "No active workflow found.")
                return redirect("twf:dictionaries_enrichment")

            next_item = workflow.get_next_item()
            if not next_item:
                messages.error(request, "No items to enrich.")
                return redirect("twf:dictionaries_enrichment")

            form_class = self.get_form_class()
            search_query = request.POST.get("search_query", "")
            results = []

            # Call appropriate API based on form type
            if form_class == GNDQueryEnrichmentForm:
                try:
                    results = search_gnd(search_query)
                    if not results:
                        messages.warning(request, f"No GND results found for '{search_query}'.")
                except Exception as e:
                    messages.error(request, f"Error searching GND: {e}")
                    results = []

            elif form_class == WikidataQueryEnrichmentForm:
                try:
                    # Get entity_type from workflow metadata
                    workflow_metadata = workflow.metadata or {}
                    entity_type = workflow_metadata.get("wikidata_entity_type", "person")

                    results = search_wikidata_entities(
                        query=search_query,
                        entity_type=entity_type,
                        limit=10
                    )
                    if not results:
                        messages.warning(request, f"No Wikidata results found for '{search_query}'.")
                except Exception as e:
                    messages.error(request, f"Error searching Wikidata: {e}")
                    results = []

            elif form_class == GeoNamesQueryEnrichmentForm:
                try:
                    geonames_username = self.get_project().get_credentials("geonames").get("username")
                    if not geonames_username:
                        messages.error(request, "GeoNames username not configured.")
                        results = []
                    else:
                        location_results = search_location(search_query, geonames_username, False)
                        # search_location returns list of (data, similarity) tuples
                        results = [data for data, similarity in location_results] if location_results else []
                        if not results:
                            messages.warning(request, f"No GeoNames results found for '{search_query}'.")
                except Exception as e:
                    messages.error(request, f"Error searching GeoNames: {e}")
                    results = []

            # Re-render form with results
            form = form_class(
                {
                    "search_query": search_query,
                    "search_results_json": json.dumps(results),
                    "item_id": next_item.id,
                },
                project=self.get_project(),
                item=next_item,
            )

            context = self.get_context_data(form=form)
            return self.render_to_response(context)

        # Handle enrichment form submission (when workflow is active)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        """Handle the form submission."""
        logger.debug("Dictionary enrichment form is valid")
        workflow = self.get_active_workflow()
        if not workflow:
            messages.error(self.request, "No active workflow found.")
            return redirect("twf:dictionaries_enrichment")

        # Get current item info for logging
        current_item = workflow.get_next_item()
        item_description = current_item.label if current_item else "Unknown"

        # Save enrichment using form's save method
        form.save(user=self.request.user)
        logger.debug(f"Saved enrichment for item: {item_description}")

        # Advance workflow to next item
        workflow.advance(item_description=f"Enriched '{item_description}'")
        logger.debug(f"Advanced workflow. Current index: {workflow.current_item_index}/{workflow.item_count}")

        messages.success(self.request, f"Dictionary entry '{item_description}' enriched successfully.")

        # Check workflow completion
        if not workflow.get_next_item():
            workflow.finish()
            messages.success(self.request, "Workflow completed!")
            logger.debug("Workflow finished - no more items")

        return redirect("twf:dictionaries_enrichment")

    def form_invalid(self, form):
        """Handle invalid form submission with better error reporting."""
        logger.error(f"Dictionary enrichment form is INVALID. Errors: {form.errors}")
        logger.error(f"Non-field errors: {form.non_field_errors()}")
        logger.error(f"POST data keys: {list(self.request.POST.keys())}")

        # Add a user-friendly error message
        if form.errors:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(self.request, f"{field}: {error}")
        else:
            messages.error(self.request, "Form validation failed. Please check your input.")

        return super().form_invalid(form)

    def get(self, request, *args, **kwargs):
        """Override the get method to handle workflow state."""
        workflow = self.get_active_workflow()

        # No active workflow - show workflow start options
        if not workflow:
            context = self.get_context_data()
            context["has_active_workflow"] = False
            return self.render_to_response(context)

        # Active workflow exists
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """Get the context data."""
        project = self.get_project()
        workflow = self.get_active_workflow()

        # No active workflow - show start form
        if not workflow:
            context = super(FormView, self).get_context_data(**kwargs)
            # Get available dictionaries and enrichment types
            dictionaries = Dictionary.objects.filter(selected_projects=project)

            # All possible enrichment types
            all_enrichment_types = [
                ("date", "Date Normalization"),
                ("verse", "Bible Verse"),
                ("authority_id", "Authority ID (Generic)"),
                ("gnd", "GND (German National Library)"),
                ("wikidata", "Wikidata"),
                ("geonames", "GeoNames"),
            ]

            # Build dictionary configurations for JavaScript filtering
            import json
            dictionary_configs = {}
            for dictionary in dictionaries:
                dict_config = project.get_dictionary_enrichment_config(dictionary.type)
                configured_types = dict_config.get("enrichment_types", [])
                # If no configuration, allow all types
                if not configured_types:
                    configured_types = [et[0] for et in all_enrichment_types]
                dictionary_configs[str(dictionary.id)] = configured_types

            context["dictionaries"] = dictionaries
            context["enrichment_types"] = all_enrichment_types
            context["dictionary_configs_json"] = json.dumps(dictionary_configs)
            context["has_active_workflow"] = False
            return context

        # Active workflow exists
        context = super().get_context_data(**kwargs)
        context["has_active_workflow"] = True
        context["workflow"] = workflow
        context["workflow_definition"] = workflow.get_workflow_definition()
        context["workflow_progress"] = workflow.get_progress()

        next_entry = workflow.get_next_item()
        context["has_next_entry"] = next_entry is not None
        context["entry"] = next_entry
        context["workflow_title"] = (
            workflow.metadata.get("dictionary_title", "Dictionary") + " Enrichment"
        )
        context["enrichment_type"] = workflow.metadata.get("enrichment_type", "")

        return context


class TWFDictionarySettingsView(ProjectPermissionMixin, FormView, TWFDictionaryView):
    """View for configuring dictionary enrichment settings."""
    required_permission = "dictionary.manage"

    template_name = "twf/dictionaries/settings.html"
    form_class = DictionarySettingsForm

    def get_form_kwargs(self):
        """Pass project to form."""
        kwargs = super().get_form_kwargs()
        kwargs["project"] = self.get_project()
        return kwargs

    def form_valid(self, form):
        """Save form data."""
        form.save()
        messages.success(self.request, "Dictionary settings saved successfully.")
        return redirect("twf:dictionaries_settings")

    def get_context_data(self, **kwargs):
        """Add context data."""
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Dictionary Settings"
        return context


class TWFDictionaryEntriesReviewView(ProjectPermissionMixin, TWFDictionaryView):
    """Supervised workflow for reviewing dictionary entries after batch enrichment."""
    required_permission = "dictionary.edit"

    template_name = "twf/dictionaries/entries_review.html"
    page_title = "Review Dictionary Entries"

    def get_active_workflow(self):
        """Get active dictionary entries review workflow for current user."""
        return Workflow.objects.filter(
            project=self.get_project(),
            user=self.request.user,
            workflow_type="review_dictionary_entries",
            status="started",
        ).first()

    def _advance_or_finish(self, workflow, item_description):
        """Advance workflow; finish it if no more items remain."""
        workflow.advance(item_description=item_description)
        if not workflow.get_next_item():
            workflow.finish()
            messages.success(self.request, "Workflow completed — all entries reviewed!")

    def post(self, request, *args, **kwargs):
        """Handle workflow actions."""
        workflow = self.get_active_workflow()

        if "start_workflow" in request.POST:
            dictionary_id = request.POST.get("dictionary_id")
            batch_size = int(request.POST.get("batch_size", 20))
            if dictionary_id:
                created = create_dictionary_review_workflow(
                    self.get_project(), request.user, int(dictionary_id), batch_size
                )
                if created:
                    messages.success(request, f"Review workflow started with {created.item_count} entries.")
                else:
                    messages.error(request, "No pending entries available in this dictionary.")
            else:
                messages.error(request, "Please select a dictionary.")
            return redirect("twf:dictionaries_review_entries")

        if not workflow:
            messages.error(request, "No active workflow found.")
            return redirect("twf:dictionaries_review_entries")

        entry = workflow.get_next_item()
        if not entry:
            messages.error(request, "No entry to process.")
            return redirect("twf:dictionaries_review_entries")

        if "update_label" in request.POST:
            new_label = request.POST.get("new_label", "").strip()
            if new_label:
                entry.label = new_label
                entry.save(current_user=request.user)
                messages.success(request, f"Label updated to '{new_label}'.")
            else:
                messages.error(request, "Label cannot be empty.")

        elif "remove_normalization" in request.POST:
            entry.metadata = {}
            entry.save(current_user=request.user)
            messages.success(request, f"Normalization data removed for '{entry.label}'.")

        elif "mark_reviewed" in request.POST:
            entry.review_status = "reviewed"
            entry.is_reserved = False
            entry.save(current_user=request.user)
            self._advance_or_finish(workflow, f"Reviewed '{entry.label}'")
            messages.success(request, f"Entry '{entry.label}' marked as reviewed.")

        elif "park" in request.POST:
            entry.is_parked = True
            entry.is_reserved = False
            entry.save(current_user=request.user)
            self._advance_or_finish(workflow, f"Parked '{entry.label}'")
            messages.info(request, f"Entry '{entry.label}' parked.")

        return redirect("twf:dictionaries_review_entries")

    def get_context_data(self, **kwargs):
        """Build context for the review view."""
        context = super().get_context_data(**kwargs)
        workflow = self.get_active_workflow()

        if workflow:
            context["has_active_workflow"] = True
            context["workflow"] = workflow
            context["workflow_definition"] = workflow.get_workflow_definition()
            context["workflow_progress"] = workflow.get_progress()
            entry = workflow.get_next_item()
            context["entry"] = entry
            context["has_next_entry"] = entry is not None
        else:
            context["has_active_workflow"] = False
            context["dictionaries"] = Dictionary.objects.filter(
                selected_projects=self.get_project()
            )

        return context
