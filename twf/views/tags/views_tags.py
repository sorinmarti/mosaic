""" Views for the tags section of the TWF app. """

import logging
from collections import defaultdict
from io import StringIO

import pandas as pd
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import redirect

logger = logging.getLogger(__name__)
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import FormView
from django_filters.views import FilterView
from django_tables2 import SingleTableMixin

from twf.forms.filters.filters import TagFilter, IgnoredTagFilter
from twf.forms.tags.workflow_forms import (
    StartTagGroupingWorkflowForm,
    StartEnrichmentWorkflowForm,
)
from twf.forms.tags.enrichment_forms import get_enrichment_form_class
from twf.forms.tags.tag_settings_forms import TagSettingsForm

from twf.models import (
    PageTag,
    Dictionary,
    DictionaryEntry,
    Variation,
    Workflow,
)
from twf.tables.tables_tags import TagTable, IgnoredTagTable, TagsWithCommentsTable
from twf.utils.tags_utils import (
    get_date_types,
    get_translated_tag_type,
    get_excluded_types,
    get_closest_variations,
    get_enrichment_types,
)
from twf.views.views_base import TWFView, ProjectPermissionMixin
from twf.workflows.tag_workflows import (
    create_tag_grouping_workflow,
    create_enrichment_workflow,
)


class TWFTagsView(LoginRequiredMixin, TWFView):
    """Base class for all tag views."""

    template_name = None

    def get_sub_navigation(self):
        """Get the sub navigation."""
        sub_nav = [
            {
                "name": "Tags",
                "options": [
                    {
                        "url": reverse("twf:tags_overview"),
                        "value": "Overview",
                        "permission": "tag.view",
                    },
                    {
                        "url": reverse("twf:tags_all"),
                        "value": "Browse Tags",
                        "permission": "tag.view",
                    },
                    {
                        "url": reverse("twf:tags_view_ignored"),
                        "value": "Ignored Tags",
                        "permission": "tag.view",
                    },
                    {
                        "url": reverse("twf:tags_with_comments"),
                        "value": "Tags with Comments",
                        "permission": "tag.view",
                    },
                ],
            },
            {
                "name": "Workflows",
                "options": [
                    {
                        "url": reverse("twf:tags_group"),
                        "value": "Grouping Tags",
                        "permission": "tag.edit",
                    },
                    {
                        "url": reverse("twf:tags_enrichment"),
                        "value": "Enrich Tags",
                        "permission": "tag.edit",
                    },
                ],
            },
            {
                "name": "Settings",
                "options": [
                    {
                        "url": reverse("twf:tags_settings"),
                        "value": "Tag Settings",
                        "permission": "tag.manage",
                    },
                    {
                        "url": reverse("twf:tags_manage"),
                        "value": "Manage Tags",
                        "permission": "tag.manage",
                    },
                ],
            },
        ]
        return sub_nav

    def get_navigation_index(self):
        """Get the navigation index."""
        return 3

    def get_context_data(self, **kwargs):
        """Get the context data."""
        context = super().get_context_data(**kwargs)
        return context

    @method_decorator(never_cache)
    def dispatch(self, *args, **kwargs):
        """Check if a project is selected."""
        project = self.get_project()
        if not project:
            messages.warning(self.request, "Please select a project first.")
            return redirect("twf:home")  # Replace with your redirect URL
        return super().dispatch(*args, **kwargs)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.page_title is None:
            self.page_title = kwargs.get("page_title", "Tags View")


class TWFTagsOverviewView(ProjectPermissionMixin, TWFTagsView):
    """View for the tags overview."""
    required_permission = "tag.view"

    template_name = "twf/tags/overview.html"
    page_title = "Tags"
    show_context_help = False

    def get_context_data(self, **kwargs):
        """Get the context data."""
        context = super().get_context_data(**kwargs)

        project = self.get_project()
        total_pagetags = PageTag.objects.filter(page__document__project=project).count()
        excluded_types = get_excluded_types(project)
        enrichment_types = get_enrichment_types(project)

        # Organize by dictionary type to find the most used entry per type
        entry_counts = (
            PageTag.objects.filter(page__document__project=project)
            .values(
                "dictionary_entry__id",
                "dictionary_entry__label",
                "dictionary_entry__dictionary__type",
            )
            .annotate(count=Count("id"))
            .order_by("dictionary_entry__dictionary__type", "-count")
        )

        # Prepare a dictionary to hold top 10 entries for each dictionary type
        top_entries_per_type = defaultdict(list)

        for entry in entry_counts:
            dtype = entry["dictionary_entry__dictionary__type"]
            if len(top_entries_per_type[dtype]) < 20:
                top_entries_per_type[dtype].append(entry)

        # Counting each variation_type in PageTags within a specific project
        # Split into main (non-ignored) and ignored
        variation_type_edit_counts_all = (
            PageTag.objects.filter(page__document__project=project)
            .values("variation_type")
            .annotate(count=Count("variation_type"))
            .order_by("-count")
        )

        # Separate main and ignored tags
        main_variation_types = []
        ignored_variation_types = []

        for variation in variation_type_edit_counts_all:
            # Add tag type translation
            tag_type = variation["variation_type"]
            translated_type = get_translated_tag_type(project, tag_type)
            variation["dict_type"] = (
                translated_type if translated_type != tag_type else None
            )

            # Determine workflow type
            if tag_type in excluded_types:
                variation["workflow_type"] = "ignore"
            elif tag_type in enrichment_types:
                variation["workflow_type"] = "enrich"
            else:
                variation["workflow_type"] = "group"

            variation["percentage"] = (
                (variation["count"] / total_pagetags * 100) if total_pagetags > 0 else 0
            )

            # Count grouped/unresolved based on workflow type
            if variation["workflow_type"] == "enrich":
                # For enrichment workflow: count tags with enrichment entries (old or new format)
                from django.db.models import Q
                variation["grouped"] = PageTag.objects.filter(
                    page__document__project=project,
                    variation_type=variation["variation_type"],
                ).filter(
                    Q(tag_enrichment_entry__isnull=False)
                    | (Q(enrichment__isnull=False) & ~Q(enrichment={}))
                ).count()

                variation["unresolved"] = PageTag.objects.filter(
                    page__document__project=project,
                    variation_type=variation["variation_type"],
                    tag_enrichment_entry__isnull=True,
                    is_parked=False,
                ).filter(Q(enrichment__isnull=True) | Q(enrichment={})).count()
            elif variation["workflow_type"] == "group":
                # For grouping workflow: count tags with dictionary entries
                variation["grouped"] = PageTag.objects.filter(
                    page__document__project=project,
                    variation_type=variation["variation_type"],
                    dictionary_entry__isnull=False,
                ).count()

                variation["unresolved"] = PageTag.objects.filter(
                    page__document__project=project,
                    variation_type=variation["variation_type"],
                    dictionary_entry__isnull=True,
                    is_parked=False,
                ).count()
            else:
                # For ignored tags: no grouped/unresolved counting
                variation["grouped"] = 0
                variation["unresolved"] = 0

            variation["grouped_percentage"] = (
                (variation["grouped"] / variation["count"] * 100)
                if variation["count"] > 0
                else 0
            )
            variation["parked"] = PageTag.objects.filter(
                page__document__project=project,
                variation_type=variation["variation_type"],
                is_parked=True,
            ).count()
            variation["parked_percentage"] = (
                (variation["parked"] / variation["count"] * 100)
                if variation["count"] > 0
                else 0
            )
            variation["unresolved_percentage"] = (
                (variation["unresolved"] / variation["count"] * 100)
                if variation["count"] > 0
                else 0
            )

            # Categorize as main or ignored
            if tag_type in excluded_types:
                ignored_variation_types.append(variation)
            else:
                main_variation_types.append(variation)

        # Calculate average grouped percentage for main tags
        grouped_percentages = [v["grouped_percentage"] for v in main_variation_types]
        average_grouped_percentage = (
            sum(grouped_percentages) / len(grouped_percentages)
            if grouped_percentages
            else 0
        )

        total_tag_types = len(main_variation_types)

        context["stats"] = {
            "most_used_entries_per_type": dict(top_entries_per_type),
            "variation_type_edit_counts": main_variation_types,
            "ignored_variation_type_counts": ignored_variation_types,
            "total_tag_types": total_tag_types,
            "total_tags": total_pagetags,
            "average_grouped_percentage": average_grouped_percentage,
            "has_ignored_tags": len(ignored_variation_types) > 0,
        }

        return context


class TWFTagsGroupView(ProjectPermissionMixin, TWFTagsView):
    """View for the tag grouping wizard with workflow support."""
    required_permission = "tag.edit"

    template_name = "twf/tags/grouping.html"
    page_title = "Tag Grouping Wizard"

    def get_active_workflow(self):
        """Get active tag grouping workflow for current user."""
        return Workflow.objects.filter(
            project=self.get_project(),
            user=self.request.user,
            workflow_type="review_tags_grouping",
            status="started",
        ).first()

    def post(self, request, *args, **kwargs):
        """Handle the post request."""

        # Handle workflow start
        if "start_workflow" in request.POST:
            form = StartTagGroupingWorkflowForm(
                request.POST, project=self.get_project()
            )
            if form.is_valid():
                tag_type = form.cleaned_data["tag_type"]
                batch_size = form.cleaned_data["batch_size"]
                workflow = create_tag_grouping_workflow(
                    self.get_project(), request.user, tag_type, batch_size
                )
                if workflow:
                    messages.success(
                        request,
                        f"Workflow started with {workflow.item_count} unique tags.",
                    )
                else:
                    messages.error(request, "No tags available for the selected type.")
            else:
                messages.error(request, "Invalid form data.")
            return redirect("twf:tags_group")

        # Handle tag assignment (when workflow is active)
        workflow = self.get_active_workflow()
        if not workflow:
            messages.error(request, "No active workflow found.")
            return redirect("twf:tags_group")

        # Create a new dictionary entry
        if "create_new" in request.POST:
            new_entry_label = request.POST.get("new_entry_label", None)
            if new_entry_label:
                tag_to_assign = PageTag.objects.get(pk=request.POST.get("tag_id", None))
                dictionary = Dictionary.objects.get(
                    pk=request.POST.get("dictionary_id", None)
                )
                new_entry = DictionaryEntry(
                    dictionary=dictionary,
                    label=new_entry_label,
                    notes=self.request.POST.get("notes_on_entry", ""),
                )
                new_entry.save(current_user=self.request.user)

                variation = Variation(
                    entry=new_entry, variation=tag_to_assign.variation
                )
                variation.save(current_user=self.request.user)
                tag_to_assign.dictionary_entry = new_entry
                tag_to_assign.save(current_user=self.request.user)

                number_of_tags = self.save_other_tags(
                    tag_to_assign, new_entry, self.request, workflow
                )
                messages.success(
                    request,
                    f'Created "{new_entry_label}" and assigned '
                    f"{number_of_tags+1} tags to it.",
                )
            else:
                messages.error(request, "Please provide a label for the new entry.")

        # Add to existing dictionary entry
        elif "add_to_existing" in request.POST:
            selected_entry = request.POST.get("selected_entry", None)
            if selected_entry:
                self.add_variation_to_entry(
                    selected_entry,
                    request.POST.get("tag_id", ""),
                    self.request,
                    workflow,
                )
            else:
                messages.error(request, "Please select an entry to add the tag to.")
        # Add to selected existing dictionary entry
        else:
            for key in request.POST.keys():
                if key.startswith("add_to_"):
                    selected_entry = key.replace("add_to_", "")
                    if selected_entry:
                        self.add_variation_to_entry(
                            selected_entry,
                            request.POST.get("tag_id", ""),
                            self.request,
                            workflow,
                        )
                    else:
                        messages.error(
                            request, "Please select an entry to add the tag to."
                        )

        # Check if workflow is complete
        if not workflow.get_next_item():
            workflow.finish()
            messages.success(request, "Workflow completed successfully!")
            return redirect("twf:tags_group")

        return super().get(request, *args, **kwargs)

    def add_variation_to_entry(self, entry_id, tag_id, request, workflow):
        """Add a variation to an existing dictionary entry."""
        try:
            entry = DictionaryEntry.objects.get(pk=entry_id)
            tag = PageTag.objects.get(pk=tag_id)
            variation = Variation(entry=entry, variation=tag.variation)
            variation.save(current_user=request.user)
            tag.dictionary_entry = entry
            tag.save(current_user=request.user)

            number_of_tags = self.save_other_tags(tag, entry, request, workflow)

            messages.success(
                self.request,
                f"Variation added to entry {entry.label} "
                f"(and {number_of_tags} other tags).",
            )
        except DictionaryEntry.DoesNotExist:
            messages.error(self.request, "Entry does not exist: " + entry_id)

    @staticmethod
    def save_other_tags(tag, entry, request, workflow):
        """Save all other tags of the same variation to the same dictionary entry."""
        # Check if any identical tags are reserved by others and warn
        reserved_by_others = (
            PageTag.objects.filter(variation=tag.variation, is_reserved=True)
            .exclude(id__in=workflow.assigned_tag_items.values_list("id", flat=True))
            .count()
        )

        if reserved_by_others > 0:
            messages.warning(
                request,
                f"Warning: {reserved_by_others} identical tags are currently reserved in another workflow.",
            )

        # Assign all other unassigned tags with same variation
        other_tags = PageTag.objects.filter(
            variation=tag.variation, page__is_ignored=False, dictionary_entry=None
        )
        for other_tag in other_tags:
            other_tag.dictionary_entry = entry
            other_tag.save(current_user=request.user)
        return other_tags.count()

    def get_next_unassigned_tag(self, workflow, tag_type):
        """Get the next unassigned tag from workflow."""
        return (
            workflow.assigned_tag_items.filter(
                dictionary_entry__isnull=True, is_parked=False, variation_type=tag_type
            )
            .order_by("pk")
            .first()
        )

    def get_context_data(self, **kwargs):
        """Get the context data."""
        context = super().get_context_data(**kwargs)
        project = self.get_project()
        workflow = self.get_active_workflow()

        # If no active workflow, show workflow start form
        if not workflow:
            form = StartTagGroupingWorkflowForm(project=project)
            context["workflow_start_form"] = form
            context["has_active_workflow"] = False
            return context

        # Active workflow exists - show workflow interface
        context["has_active_workflow"] = True
        context["workflow"] = workflow
        context["workflow_definition"] = workflow.get_workflow_definition()
        context["workflow_progress"] = workflow.get_progress()
        context["workflow_instructions"] = workflow.get_instructions()

        # Get tag type from workflow metadata
        tag_type = (workflow.metadata or {}).get("tag_type")

        if not tag_type:
            messages.error(self.request, "Workflow metadata is missing tag type.")
            context["tag"] = None
            return context

        dict_type = get_translated_tag_type(project, tag_type)
        unassigned_tag = self.get_next_unassigned_tag(workflow, tag_type)

        context["selected_type"] = tag_type
        context["selected_dict_type"] = dict_type
        context["tag"] = unassigned_tag

        if unassigned_tag:
            context["closest"] = get_closest_variations(unassigned_tag)
            # Count identical unparked tags with same variation within workflow
            identical_count = workflow.assigned_tag_items.filter(
                variation=unassigned_tag.variation, is_parked=False
            ).count()
            context["identical_tag_count"] = identical_count

        try:
            dictionary = project.selected_dictionaries.get(type=dict_type)
            context["dictionary"] = dictionary
            context["dict_entries"] = DictionaryEntry.objects.filter(
                dictionary=dictionary
            ).order_by("label")
        except Dictionary.DoesNotExist:
            context["dictionary"] = None
            context["dict_entries"] = []

        return context


class TWFTagsAssignTagView(ProjectPermissionMixin, TWFTagsView):
    """View for the tag grouping wizard."""
    required_permission = "tag.edit"

    template_name = "twf/tags/assign.html"
    page_title = "Assign Tag"


class TWFProjectTagsView(ProjectPermissionMixin, SingleTableMixin, FilterView, TWFTagsView):
    """Base class for all tag views."""
    required_permission = "tag.view"

    template_name = "twf/tags/all_tags.html"
    page_title = "All Tags"
    filterset_class = TagFilter
    table_class = TagTable
    paginate_by = 20
    model = PageTag
    strict = False

    def post(self, request, *args, **kwargs):
        """Handle the post request."""
        if "export_tags" in request.POST:
            result = []
            queryset = self.get_filterset(self.filterset_class).qs
            for item in queryset:
                result.append(
                    {
                        "Document ID": item.page.document.id,
                        "Transkribus ID": item.page.document.document_id,
                        "Transkribus Doc URL": item.page.document.get_transkribus_url(),
                        "Document Title": item.page.document.title,
                        "Page ID": item.page.id,
                        "Transkribus Page ID": item.page.tk_page_id,
                        "Transkribus Page URL": item.get_transkribus_url(),
                        "Page Number": item.page.tk_page_number,
                        "Tag ID": item.id,
                        "Tag Type": item.variation_type,
                        "Tag Variation": item.variation,
                        "Tag Additional Information": item.additional_information,
                        "Tag Dictionary Entry": (
                            item.dictionary_entry.label if item.dictionary_entry else ""
                        ),
                        "Tag Date Variation": (
                            item.date_variation_entry.edtf_of_normalized_variation
                            if item.date_variation_entry
                            else ""
                        ),
                        "Tag Is Parked": item.is_parked,
                        "Tag Is Resolved": item.is_resolved(),
                    }
                )

            df = pd.DataFrame(result)
            csv_buffer = StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_data = csv_buffer.getvalue()
            response = HttpResponse(csv_data, content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="tags_export.csv"'
            return response

        return redirect("twf:tags_all")

    def get_filterset(self, filterset_class):
        """Get the filterset."""
        project = self.get_project()
        excluded = get_excluded_types(project)
        return filterset_class(
            self.request.GET or None,
            queryset=self.get_queryset(),
            project=project,
            excluded=excluded,
        )

    def get_queryset(self):
        """Get the queryset."""
        project = self.get_project()
        excluded_types = get_excluded_types(project)

        return PageTag.objects.filter(page__document__project=project).exclude(
            variation_type__in=excluded_types
        )

    def get(self, request, *args, **kwargs):
        """Handle GET requests."""
        # Set up initial queryset
        queryset = self.get_queryset()

        # Initialize the filter
        project = self.get_project()
        excluded = get_excluded_types(project)
        self.filterset = self.filterset_class(
            request.GET or None, queryset=queryset, project=project, excluded=excluded
        )

        # Set object_list either to all items or filtered items
        if request.GET and self.filterset.is_bound:
            self.object_list = self.filterset.qs
        else:
            self.object_list = queryset

        # Log filter results for debugging
        logger.debug(f"Initial tags queryset count: {queryset.count()}")
        if hasattr(self, "filterset") and self.filterset:
            logger.debug(f"Filtered tags queryset count: {self.filterset.qs.count()}")

        # Get context and render response
        context = self.get_context_data()
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        """Get the context data."""
        context = super().get_context_data(**kwargs)

        # Basic context
        context["page_title"] = self.page_title
        context["filter"] = self.filterset

        # Tag statistics
        project = self.get_project()
        all_tags = PageTag.objects.filter(page__document__project=project)
        excluded_types = get_excluded_types(project)

        # Tag statistics for the header
        # Note: Using Q objects for database-level filtering (more efficient than
        # loading all objects and calling is_resolved() method)
        stats = {
            "total": all_tags.exclude(variation_type__in=excluded_types).count(),
            "resolved": all_tags.exclude(variation_type__in=excluded_types)
            .filter(
                Q(dictionary_entry__isnull=False)
                | Q(date_variation_entry__isnull=False)
            )
            .count(),
            "open": all_tags.exclude(variation_type__in=excluded_types)
            .filter(
                dictionary_entry__isnull=True,
                date_variation_entry__isnull=True,
                is_parked=False,
            )
            .count(),
            "parked": all_tags.exclude(variation_type__in=excluded_types)
            .filter(is_parked=True)
            .count(),
            "ignored": all_tags.filter(variation_type__in=excluded_types).count(),
        }
        context["tag_stats"] = stats

        return context


class TWFProjectTagsOpenView(TWFProjectTagsView):
    """View for the open tags."""

    required_permission = "tag.view"
    template_name = "twf/tags/open.html"
    page_title = "Open Tags"
    filterset = None

    def get_queryset(self):
        project = self.get_project()
        excluded = get_excluded_types(project)
        queryset = self.model.objects.filter(
            page__document__project=project,
            dictionary_entry=None,
            date_variation_entry=None,
            is_parked=False,
        ).exclude(variation_type__in=excluded)
        self.filterset = self.filterset_class(
            self.request.GET, queryset=queryset, project=project, excluded=excluded
        )
        return self.filterset.qs


class TWFProjectTagsParkedView(TWFProjectTagsView):
    """View for the parked tags."""
    required_permission = "tag.view"

    template_name = "twf/tags/parked.html"
    page_title = "Parked Tags"
    filterset = None

    def get_queryset(self):
        project = self.get_project()
        excluded = get_excluded_types(project)
        queryset = self.model.objects.filter(
            page__document__project=project, dictionary_entry=None, is_parked=True
        ).exclude(variation_type__in=excluded)
        self.filterset = self.filterset_class(
            self.request.GET, queryset=queryset, project=project, excluded=excluded
        )
        return self.filterset.qs


class TWFProjectTagsResolvedView(TWFProjectTagsView):
    """View for the resolved tags."""
    required_permission = "tag.view"

    template_name = "twf/tags/resolved.html"
    page_title = "Resolved Tags"
    filterset = None

    def get_queryset(self):
        project = self.get_project()
        excluded = get_excluded_types(project)
        queryset1 = self.model.objects.filter(
            page__document__project=project,
            dictionary_entry__isnull=False,
            is_parked=False,
        ).exclude(variation_type__in=excluded)
        queryset2 = self.model.objects.filter(
            page__document__project=project,
            date_variation_entry__isnull=False,
            variation_type__in=get_date_types(project),
            is_parked=False,
        ).exclude(variation_type__in=excluded)
        queryset = queryset1 | queryset2
        self.filterset = self.filterset_class(
            self.request.GET, queryset=queryset, project=project, excluded=excluded
        )
        return self.filterset.qs


class TWFProjectTagsWithCommentsView(TWFProjectTagsView):
    """View for tags with comments (dictionary entry notes)."""
    required_permission = "tag.view"

    template_name = "twf/tags/with_comments.html"
    page_title = "Tags with Comments"
    table_class = TagsWithCommentsTable
    filterset = None

    def get_queryset(self):
        """Get tags where the dictionary entry has notes."""
        project = self.get_project()
        excluded = get_excluded_types(project)
        queryset = self.model.objects.filter(
            page__document__project=project,
            dictionary_entry__isnull=False,
        ).exclude(
            dictionary_entry__notes=""
        ).exclude(variation_type__in=excluded)
        self.filterset = self.filterset_class(
            self.request.GET, queryset=queryset, project=project, excluded=excluded
        )
        return self.filterset.qs


class TWFProjectTagsIgnoredView(TWFProjectTagsView):
    """View for the ignored tags."""
    required_permission = "tag.view"

    template_name = "twf/tags/ignored.html"
    page_title = "Ignored Tags"
    filterset_class = IgnoredTagFilter
    table_class = IgnoredTagTable
    filterset = None

    def get_queryset(self):
        """Get the queryset."""
        project = self.get_project()
        excluded = get_excluded_types(project)
        queryset = self.model.objects.filter(
            page__document__project=project, variation_type__in=excluded
        )
        self.filterset = self.filterset_class(
            self.request.GET, queryset=queryset, project=project, excluded=excluded
        )
        return self.filterset.qs


class TWFTagsEnrichmentView(ProjectPermissionMixin, FormView, TWFTagsView):
    """Generic view for tag enrichment workflows."""
    required_permission = "tag.edit"

    template_name = "twf/tags/enrichment.html"
    page_title = "Tag Enrichment"

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
        """Add project and tag to form kwargs."""
        kwargs = super().get_form_kwargs()
        workflow = self.get_active_workflow()
        if workflow:
            next_tag = workflow.get_next_item()
            if next_tag:
                kwargs["project"] = self.get_project()
                kwargs["tag"] = next_tag
        return kwargs

    def get_active_workflow(self):
        """Get active enrichment workflow for current user."""
        return Workflow.objects.filter(
            project=self.get_project(),
            user=self.request.user,
            workflow_type="review_tags_enrichment",
            status="started",
        ).first()

    def post(self, request, *args, **kwargs):
        """Handle the post request."""
        # Handle workflow start
        if "start_workflow" in request.POST:
            form = StartEnrichmentWorkflowForm(request.POST, project=self.get_project())
            if form.is_valid():
                tag_type = form.cleaned_data["tag_type"]
                batch_size = form.cleaned_data["batch_size"]
                workflow = create_enrichment_workflow(
                    self.get_project(), request.user, tag_type, batch_size
                )
                if workflow:
                    messages.success(
                        request, f"Workflow started with {workflow.item_count} tags."
                    )
                else:
                    messages.error(
                        request, f"No {tag_type} tags available for enrichment."
                    )
            else:
                messages.error(request, "Invalid form data.")
            return redirect("twf:tags_enrichment")

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
                return redirect("twf:tags_enrichment")

            next_item = workflow.get_next_item()
            if not next_item:
                messages.error(request, "No items to enrich.")
                return redirect("twf:tags_enrichment")

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
                    # Get entity_type from workflow metadata or tag type settings
                    workflow_metadata = workflow.metadata or {}
                    entity_type = workflow_metadata.get("wikidata_entity_type")

                    # If not in workflow metadata, try to get from tag type settings
                    if not entity_type:
                        tag_type = workflow_metadata.get("tag_type")
                        if tag_type:
                            enrichment_config = self.get_project().get_tag_enrichment_config(tag_type)
                            entity_type = enrichment_config.get("wikidata_entity_type", "person")
                        else:
                            entity_type = "person"  # Default fallback

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
        logger.debug("Enrichment form is valid")
        workflow = self.get_active_workflow()
        if not workflow:
            messages.error(self.request, "No active workflow found.")
            return redirect("twf:tags_enrichment")

        # Save enrichment using form's save method
        form.save(user=self.request.user)
        messages.success(self.request, "Tag enriched successfully.")

        # Check workflow completion
        if not workflow.get_next_item():
            workflow.finish()
            messages.success(self.request, "Workflow completed!")

        return redirect("twf:tags_enrichment")

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
            form = StartEnrichmentWorkflowForm(project=project)
            context["workflow_start_form"] = form
            context["has_active_workflow"] = False
            return context

        # Active workflow exists
        context = super().get_context_data(**kwargs)
        context["has_active_workflow"] = True
        context["workflow"] = workflow
        context["workflow_definition"] = workflow.get_workflow_definition()
        context["workflow_progress"] = workflow.get_progress()
        context["workflow_instructions"] = workflow.get_instructions()

        next_tag = workflow.get_next_item()
        context["has_next_tag"] = next_tag is not None
        context["tag"] = next_tag
        context["workflow_title"] = (
            workflow.metadata.get("tag_type", "Tag") + " Enrichment"
        )

        return context


class TWFTagsSettingsView(ProjectPermissionMixin, FormView, TWFTagsView):
    """View for tag-specific settings."""
    required_permission = "tag.manage"

    template_name = "twf/tags/settings.html"
    form_class = TagSettingsForm
    page_title = "Tag Settings"
    show_context_help = True

    def get_form_kwargs(self):
        """Add project to form kwargs."""
        kwargs = super().get_form_kwargs()
        kwargs["project"] = self.get_project()
        return kwargs

    def form_valid(self, form):
        """Handle successful form submission."""
        if form.save():
            messages.success(self.request, "Tag settings saved successfully.")
        else:
            messages.error(self.request, "Failed to save tag settings.")
        return redirect("twf:tags_settings")

    def form_invalid(self, form):
        """Handle invalid form submission."""
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


class TWFManageTagsView(ProjectPermissionMixin, TWFTagsView):
    """View for bulk tag management operations."""
    required_permission = "tag.manage"

    template_name = "twf/tags/manage.html"
    page_title = "Manage Tags"
    show_context_help = False

    def get_context_data(self, **kwargs):
        """Get the context data."""
        context = super().get_context_data(**kwargs)
        project = self.get_project()

        # Get statistics for all tag types (excluding ignored types)
        excluded_types = get_excluded_types(project)
        enrichment_types = get_enrichment_types(project)
        tag_stats = []
        total_tags = 0
        total_parked = 0
        total_grouped = 0
        total_enriched = 0

        tag_types = (
            PageTag.objects.filter(page__document__project=project)
            .exclude(variation_type__in=excluded_types)
            .values("variation_type")
            .distinct()
            .order_by("variation_type")
        )

        for tag_type_dict in tag_types:
            tag_type = tag_type_dict["variation_type"]

            # Determine workflow type
            if tag_type in enrichment_types:
                workflow_type = "enrich"
            else:
                workflow_type = "group"

            stats = {
                "type": tag_type,
                "workflow_type": workflow_type,
                "total": PageTag.objects.filter(
                    page__document__project=project, variation_type=tag_type
                ).count(),
                "parked": PageTag.objects.filter(
                    page__document__project=project,
                    variation_type=tag_type,
                    is_parked=True,
                ).count(),
                "with_dict": PageTag.objects.filter(
                    page__document__project=project,
                    variation_type=tag_type,
                    dictionary_entry__isnull=False,
                ).count(),
                "with_enrichment": PageTag.objects.filter(
                    page__document__project=project,
                    variation_type=tag_type,
                ).filter(
                    Q(tag_enrichment_entry__isnull=False)
                    | (Q(enrichment__isnull=False) & ~Q(enrichment={}))
                ).count(),
                "unassigned": PageTag.objects.filter(
                    page__document__project=project,
                    variation_type=tag_type,
                    dictionary_entry__isnull=True,
                ).count(),
            }
            tag_stats.append(stats)

            # Accumulate totals
            total_tags += stats["total"]
            total_parked += stats["parked"]
            total_grouped += stats["with_dict"]
            total_enriched += stats["with_enrichment"]

        context["tag_stats"] = tag_stats
        context["total_tags"] = total_tags
        context["total_parked"] = total_parked
        context["total_grouped"] = total_grouped
        context["total_enriched"] = total_enriched
        return context


class TWFTagDetailView(ProjectPermissionMixin, TWFTagsView):
    """Detailed view of a single tag showing all associated data."""
    required_permission = "tag.view"

    template_name = "twf/tags/detail.html"
    page_title = "Tag Detail"

    def get(self, request, *args, **kwargs):
        """Handle GET request."""
        tag_id = kwargs.get("pk")
        try:
            tag = PageTag.objects.select_related(
                "page__document",
                "dictionary_entry__dictionary",
                "date_variation_entry",
                "tag_enrichment_entry",
            ).get(pk=tag_id)

            # Check project access
            if tag.page.document.project.id != self.get_project().id:
                messages.error(request, "Tag not found in current project.")
                return redirect("twf:tags_all")

        except PageTag.DoesNotExist:
            messages.error(request, "Tag not found.")
            return redirect("twf:tags_all")

        context = self.get_context_data(**kwargs)
        context["tag"] = tag
        context["page"] = tag.page
        context["document"] = tag.page.document

        # Get workflow configuration for this tag type
        project = self.get_project()
        enrichment_types = get_enrichment_types(project)
        excluded_types = get_excluded_types(project)

        if tag.variation_type in excluded_types:
            context["workflow_type"] = "ignore"
        elif tag.variation_type in enrichment_types:
            context["workflow_type"] = "enrich"
            context["enrichment_config"] = enrichment_types.get(tag.variation_type, {})

            # Add manual enrichment form if tag is not enriched and not reserved
            if not tag.tag_enrichment_entry and not tag.is_reserved:
                enrichment_type = context["enrichment_config"].get("form_type")
                # Only show manual enrichment for supported types
                supported_types = ["date", "verse", "authority_id"]
                if enrichment_type and enrichment_type in supported_types:
                    from crispy_forms.layout import Submit, ButtonHolder, HTML

                    form_class = get_enrichment_form_class(enrichment_type)
                    form = form_class(project=project, tag=tag)

                    # Find and replace the ButtonHolder in the layout
                    # The layout structure is: tag_id, fields, ButtonHolder, [JavaScript HTML]
                    new_layout_fields = []
                    for field in form.helper.layout.fields:
                        # Keep everything except ButtonHolder (which has the old buttons)
                        if not isinstance(field, ButtonHolder):
                            new_layout_fields.append(field)
                        else:
                            # Replace with our custom button
                            new_layout_fields.append(
                                ButtonHolder(
                                    Submit(
                                        "save_enrichment",
                                        "Save Enrichment",
                                        css_class="btn btn-success",
                                    ),
                                    css_class="mt-3",
                                )
                            )

                    form.helper.layout.fields = new_layout_fields

                    context["enrichment_form"] = form
                    context["can_manually_enrich"] = True
                else:
                    context["can_manually_enrich"] = False
            else:
                context["can_manually_enrich"] = False
        else:
            context["workflow_type"] = "group"

        # Get related tags with same variation
        context["identical_tags"] = PageTag.objects.filter(
            page__document__project=project,
            variation=tag.variation,
            variation_type=tag.variation_type,
        ).select_related("page__document").order_by("page__document__title", "page__tk_page_number")

        context["identical_count"] = context["identical_tags"].count()

        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        """Handle POST request for manual enrichment."""
        tag_id = kwargs.get("pk")

        try:
            tag = PageTag.objects.select_related(
                "page__document",
                "tag_enrichment_entry",
            ).get(pk=tag_id)

            # Check project access
            if tag.page.document.project.id != self.get_project().id:
                messages.error(request, "Tag not found in current project.")
                return redirect("twf:tags_all")

            # Check if tag is reserved
            if tag.is_reserved:
                messages.error(request, "Cannot enrich: tag is reserved in a workflow.")
                return redirect("twf:tags_detail", pk=tag_id)

            # Check if already enriched
            if tag.tag_enrichment_entry:
                messages.error(request, "Tag is already enriched.")
                return redirect("twf:tags_detail", pk=tag_id)

            # Get enrichment type
            project = self.get_project()
            enrichment_types = get_enrichment_types(project)
            enrichment_config = enrichment_types.get(tag.variation_type, {})
            enrichment_type = enrichment_config.get("form_type")

            # Get form class and process submission
            form_class = get_enrichment_form_class(enrichment_type)
            if not form_class:
                messages.error(request, "Invalid enrichment type.")
                return redirect("twf:tags_detail", pk=tag_id)

            form = form_class(request.POST, project=project, tag=tag)

            if form.is_valid():
                form.save(user=request.user)
                messages.success(request, "Tag enriched successfully.")
                return redirect("twf:tags_detail", pk=tag_id)
            else:
                messages.error(request, "Please correct the errors in the form.")
                # Re-render with form errors
                context = self.get_context_data(**kwargs)
                context["tag"] = tag
                context["page"] = tag.page
                context["document"] = tag.page.document
                context["workflow_type"] = "enrich"
                context["enrichment_config"] = enrichment_config
                context["enrichment_form"] = form
                context["can_manually_enrich"] = True

                # Add identical tags context
                context["identical_tags"] = PageTag.objects.filter(
                    page__document__project=project,
                    variation=tag.variation,
                    variation_type=tag.variation_type,
                ).select_related("page__document").order_by("page__document__title", "page__tk_page_number")
                context["identical_count"] = context["identical_tags"].count()

                return self.render_to_response(context)

        except PageTag.DoesNotExist:
            messages.error(request, "Tag not found.")
            return redirect("twf:tags_all")
