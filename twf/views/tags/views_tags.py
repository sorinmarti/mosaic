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
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import FormView
from django_filters.views import FilterView
from django_tables2 import SingleTableMixin

from twf.forms.filters.filters import TagFilter
from twf.forms.tags.tags_forms import DateNormalizationForm
from twf.models import PageTag, DateVariation, Dictionary, DictionaryEntry, Variation
from twf.tables.tables_tags import TagTable
from twf.utils.tags_utils import get_date_types, get_all_tag_types, get_translated_tag_type, get_excluded_types, \
    get_closest_variations
from twf.views.views_base import TWFView


class TWFTagsView(LoginRequiredMixin, TWFView):
    """Base class for all tag views."""

    template_name = None

    def get_sub_navigation(self):
        """Get the sub navigation."""
        sub_nav = [
            {
                'name': 'Data',
                'options': [
                    {'url': reverse('twf:tags_overview'), 'value': 'Overview'},
                    {'url': reverse('twf:tags_all'),
                     'value': 'All Tags', 'permission': 'tag.view'},
                ]
            },
            {
                'name': 'Tag Workflows',
                'options': [
                    {'url': reverse('twf:tags_group'),
                     'value': 'Grouping Wizard', 'permission': 'tag.edit'},
                    {'url': reverse('twf:tags_dates'),
                     'value': 'Date Normalization', 'permission': 'tag.edit'},
                ]
            },
            {
                'name': 'Tag Views',
                'options': [
                    {'url': reverse('twf:tags_view_open'),
                     'value': 'Open Tags', 'permission': 'tag.view'},
                    {'url': reverse('twf:tags_view_parked'),
                     'value': 'Parked Tags', 'permission': 'tag.view'},
                    {'url': reverse('twf:tags_view_resolved'),
                     'value': 'Resolved Tags', 'permission': 'tag.view'},
                    {'url': reverse('twf:tags_view_ignored'),
                     'value': 'Ignored Tags', 'permission': 'tag.view'},
                ]
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
            messages.warning(self.request, 'Please select a project first.')
            return redirect('twf:home')  # Replace with your redirect URL
        return super().dispatch(*args, **kwargs)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.page_title is None:
            self.page_title = kwargs.get('page_title', 'Tags View')


class TWFTagsOverviewView(TWFTagsView):
    """View for the tags overview."""
    template_name = 'twf/tags/overview.html'
    page_title = 'Tags'
    show_context_help = False

    def get_context_data(self, **kwargs):
        """Get the context data."""
        context = super().get_context_data(**kwargs)

        project = self.get_project()
        total_pagetags = PageTag.objects.filter(page__document__project=project).count()
        excluded_types = get_excluded_types(project)

        # Organize by dictionary type to find the most used entry per type
        entry_counts = PageTag.objects.filter(
            page__document__project=project
        ).values(
            'dictionary_entry__id',
            'dictionary_entry__label',
            'dictionary_entry__dictionary__type'
        ).annotate(
            count=Count('id')
        ).order_by('dictionary_entry__dictionary__type', '-count')

        # Prepare a dictionary to hold top 10 entries for each dictionary type
        top_entries_per_type = defaultdict(list)

        for entry in entry_counts:
            dtype = entry['dictionary_entry__dictionary__type']
            if len(top_entries_per_type[dtype]) < 20:
                top_entries_per_type[dtype].append(entry)

        # Counting each variation_type in PageTags within a specific project
        # Split into main (non-ignored) and ignored
        variation_type_edit_counts_all = PageTag.objects.filter(
            page__document__project=project
        ).values('variation_type').annotate(
            count=Count('variation_type')
        ).order_by('-count')

        # Separate main and ignored tags
        main_variation_types = []
        ignored_variation_types = []

        for variation in variation_type_edit_counts_all:
            # Add tag type translation
            tag_type = variation['variation_type']
            translated_type = get_translated_tag_type(project, tag_type)
            variation['dict_type'] = translated_type if translated_type != tag_type else None

            variation['percentage'] = (variation['count'] / total_pagetags * 100) if total_pagetags > 0 else 0

            if variation['variation_type'] in get_date_types(project):
                variation['grouped'] = PageTag.objects.filter(
                    page__document__project=project,
                    variation_type=variation['variation_type'],
                    date_variation_entry__isnull=False
                ).count()

                variation['unresolved'] = PageTag.objects.filter(
                    page__document__project=project,
                    variation_type=variation['variation_type'],
                    date_variation_entry__isnull=True,
                    is_parked=False
                ).count()
            else:
                variation['grouped'] = PageTag.objects.filter(
                    page__document__project=project,
                    variation_type=variation['variation_type'],
                    dictionary_entry__isnull=False
                ).count()

                variation['unresolved'] = PageTag.objects.filter(
                    page__document__project=project,
                    variation_type=variation['variation_type'],
                    dictionary_entry__isnull=True,
                    is_parked=False
                ).count()

            variation['grouped_percentage'] = (variation['grouped'] / variation['count'] * 100) \
                if variation['count'] > 0 else 0
            variation['parked'] = PageTag.objects.filter(
                page__document__project=project,
                variation_type=variation['variation_type'],
                is_parked=True
            ).count()
            variation['parked_percentage'] = (variation['parked'] / variation['count'] * 100) \
                if variation['count'] > 0 else 0
            variation['unresolved_percentage'] = (variation['unresolved'] / variation['count'] * 100) \
                if variation['count'] > 0 else 0

            # Categorize as main or ignored
            if tag_type in excluded_types:
                ignored_variation_types.append(variation)
            else:
                main_variation_types.append(variation)

        # Calculate average grouped percentage for main tags
        grouped_percentages = [v['grouped_percentage'] for v in main_variation_types]
        average_grouped_percentage = sum(grouped_percentages) / len(grouped_percentages) if grouped_percentages else 0

        total_tag_types = len(main_variation_types)

        context['stats'] = {
            'most_used_entries_per_type': dict(top_entries_per_type),
            'variation_type_edit_counts': main_variation_types,
            'ignored_variation_type_counts': ignored_variation_types,
            'total_tag_types': total_tag_types,
            'total_tags': total_pagetags,
            'average_grouped_percentage': average_grouped_percentage,
            'has_ignored_tags': len(ignored_variation_types) > 0
        }

        return context


class TWFTagsGroupView(TWFTagsView):
    """View for the tag grouping wizard."""
    template_name = 'twf/tags/grouping.html'
    page_title = 'Tag Grouping Wizard'

    def post(self, request, *args, **kwargs):
        """Handle the post request."""

        # Create a new dictionary entry
        if 'create_new' in request.POST:
            new_entry_label = request.POST.get('new_entry_label', None)
            if new_entry_label:
                tag_to_assign = PageTag.objects.get(pk=request.POST.get('tag_id', None))
                dictionary = Dictionary.objects.get(pk=request.POST.get('dictionary_id', None))
                new_entry = DictionaryEntry(dictionary=dictionary, label=new_entry_label,
                                            notes=self.request.POST.get('notes_on_entry', ''))
                new_entry.save(current_user=self.request.user)

                variation = Variation(entry=new_entry, variation=tag_to_assign.variation)
                variation.save(current_user=self.request.user)
                tag_to_assign.dictionary_entry = new_entry
                tag_to_assign.save(current_user=self.request.user)

                number_of_tags = self.save_other_tags(tag_to_assign, new_entry, self.request.user)
                messages.success(request, f'Created "{new_entry_label}" and assigned '
                                          f'{number_of_tags+1} tags to it.')
            else:
                messages.error(request, 'Please provide a label for the new entry.')

        # Add to existing dictionary entry
        elif 'add_to_existing' in request.POST:
            selected_entry = request.POST.get('selected_entry', None)
            if selected_entry:
                self.add_variation_to_entry(selected_entry, request.POST.get('tag_id', ''), self.request.user)
            else:
                messages.error(request, 'Please select an entry to add the tag to.')
        # Add to selected existing dictionary entry
        else:
            for key in request.POST.keys():
                if key.startswith('add_to_'):
                    selected_entry = key.replace('add_to_', '')
                    if selected_entry:
                        self.add_variation_to_entry(selected_entry, request.POST.get('tag_id', ''), self.request.user)
                    else:
                        messages.error(request, 'Please select an entry to add the tag to.')
        return super().get(request, *args, **kwargs)

    def add_variation_to_entry(self, entry_id, tag_id, user):
        """Add a variation to an existing dictionary entry."""
        try:
            entry = DictionaryEntry.objects.get(pk=entry_id)
            tag = PageTag.objects.get(pk=tag_id)
            variation = Variation(entry=entry, variation=tag.variation)
            variation.save(current_user=user)
            tag.dictionary_entry = entry
            tag.save(current_user=user)

            number_of_tags =  self.save_other_tags(tag, entry, user)

            messages.success(self.request, f'Variation added to entry {entry.label} '
                                           f'(and {number_of_tags} other tags).')
        except DictionaryEntry.DoesNotExist:
            messages.error(self.request, 'Entry does not exist: ' + entry_id)

    @staticmethod
    def save_other_tags(tag, entry, user):
        """Save all other tags of the same variation to the same dictionary entry."""
        other_tags = PageTag.objects.filter(variation=tag.variation, dictionary_entry=None)
        for other_tag in other_tags:
            other_tag.dictionary_entry = entry
            other_tag.save(current_user=user)
        return other_tags.count()

    def get_next_unassigned_tag(self, tag_type):
        """Get the next unassigned tag."""
        project = self.get_project()
        unassigned_tag = PageTag.objects.filter(page__document__project=project,
                                                dictionary_entry=None,
                                                variation_type=tag_type,
                                                is_parked=False).first()
        return unassigned_tag

    def get_context_data(self, **kwargs):
        """Get the context data."""
        context = super().get_context_data(**kwargs)
        project = self.get_project()
        tag_types = get_all_tag_types(project)
        selected_type = None
        dict_type = None
        unassigned_tag = None

        if len(tag_types) > 0:
            selected_type = self.request.GET.get('tag_type', tag_types[0])
            dict_type = get_translated_tag_type(project, selected_type)
            unassigned_tag = self.get_next_unassigned_tag(selected_type)

        context['tag_types'] = tag_types
        context['selected_type'] = selected_type
        context['selected_dict_type'] = dict_type
        context['tag'] = unassigned_tag
        if unassigned_tag:
            context['closest'] = get_closest_variations(unassigned_tag)
            # Count identical unparked tags with same variation
            identical_count = PageTag.objects.filter(
                page__document__project=project,
                variation=unassigned_tag.variation,
                is_parked=False
            ).count()
            context['identical_tag_count'] = identical_count
        try:
            dictionary = self.get_project().selected_dictionaries.get(type=dict_type)
            context['dictionary'] = dictionary
            context['dict_entries'] = DictionaryEntry.objects.filter(dictionary=dictionary).order_by('label')
        except Dictionary.DoesNotExist:
            context['dictionary'] = None
            context['dict_entries'] = []
        return context


class TWFTagsAssignTagView(TWFTagsView):
    """View for the tag grouping wizard."""
    template_name = 'twf/tags/assign.html'
    page_title = 'Assign Tag'


class TWFProjectTagsView(SingleTableMixin, FilterView, TWFTagsView):
    """Base class for all tag views."""
    template_name = 'twf/tags/all_tags.html'
    page_title = 'All Tags'
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
                result.append({
                    'Document ID': item.page.document.id,
                    'Transkribus ID': item.page.document.document_id,
                    'Transkribus Doc URL': item.page.document.get_transkribus_url(),
                    'Document Title': item.page.document.title,
                    'Page ID': item.page.id,
                    'Transkribus Page ID': item.page.tk_page_id,
                    'Transkribus Page URL': item.get_transkribus_url(),
                    'Page Number': item.page.tk_page_number,
                    'Tag ID': item.id,
                    'Tag Type': item.variation_type,
                    'Tag Variation': item.variation,
                    'Tag Additional Information': item.additional_information,
                    'Tag Dictionary Entry': item.dictionary_entry.label if item.dictionary_entry else '',
                    'Tag Date Variation': item.date_variation_entry.edtf_of_normalized_variation
                        if item.date_variation_entry else '',
                    'Tag Is Parked': item.is_parked,
                    'Tag Is Resolved': item.is_resolved()
                })

            df = pd.DataFrame(result)
            csv_buffer = StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_data = csv_buffer.getvalue()
            response = HttpResponse(csv_data, content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="tags_export.csv"'
            return response

        return redirect('twf:tags_all')

    def get_filterset(self, filterset_class):
        """Get the filterset."""
        project = self.get_project()
        excluded = get_excluded_types(project)
        return filterset_class(self.request.GET or None, queryset=self.get_queryset(),
                               project=project, excluded=excluded)

    def get_queryset(self):
        """Get the queryset."""
        project = self.get_project()
        excluded_types = get_excluded_types(project)

        return PageTag.objects.filter(
            page__document__project=project
        ).exclude(variation_type__in=excluded_types)

    def get(self, request, *args, **kwargs):
        """Handle GET requests."""
        # Set up initial queryset
        queryset = self.get_queryset()
        
        # Initialize the filter
        project = self.get_project()
        excluded = get_excluded_types(project)
        self.filterset = self.filterset_class(
            request.GET or None,
            queryset=queryset,
            project=project,
            excluded=excluded
        )
        
        # Set object_list either to all items or filtered items
        if request.GET and self.filterset.is_bound:
            self.object_list = self.filterset.qs
        else:
            self.object_list = queryset
            
        # Log filter results for debugging
        logger.debug(f"Initial tags queryset count: {queryset.count()}")
        if hasattr(self, 'filterset') and self.filterset:
            logger.debug(f"Filtered tags queryset count: {self.filterset.qs.count()}")
        
        # Get context and render response
        context = self.get_context_data()
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        """Get the context data."""
        context = super().get_context_data(**kwargs)

        # Basic context
        context['page_title'] = self.page_title
        context['filter'] = self.filterset

        # Tag statistics
        project = self.get_project()
        all_tags = PageTag.objects.filter(page__document__project=project)
        excluded_types = get_excluded_types(project)

        # Tag statistics for the header
        # Note: Using Q objects for database-level filtering (more efficient than
        # loading all objects and calling is_resolved() method)
        stats = {
            'total': all_tags.exclude(variation_type__in=excluded_types).count(),
            'resolved': all_tags.exclude(variation_type__in=excluded_types).filter(
                Q(dictionary_entry__isnull=False) | Q(date_variation_entry__isnull=False)
            ).count(),
            'open': all_tags.exclude(variation_type__in=excluded_types).filter(
                dictionary_entry__isnull=True,
                date_variation_entry__isnull=True,
                is_parked=False
            ).count(),
            'parked': all_tags.exclude(variation_type__in=excluded_types).filter(is_parked=True).count(),
            'ignored': all_tags.filter(variation_type__in=excluded_types).count()
        }
        context['tag_stats'] = stats

        return context


class TWFProjectTagsOpenView(TWFProjectTagsView):
    """View for the open tags."""
    template_name = 'twf/tags/open.html'
    page_title = 'Open Tags'
    filterset = None

    def get_queryset(self):
        project = self.get_project()
        excluded = get_excluded_types(project)
        queryset = self.model.objects.filter(page__document__project=project,
                                             dictionary_entry=None,
                                             date_variation_entry=None,
                                             is_parked=False).exclude(variation_type__in=excluded)
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset,
                                              project=project,
                                              excluded=excluded)
        return self.filterset.qs


class TWFProjectTagsParkedView(TWFProjectTagsView):
    """View for the parked tags."""
    template_name = 'twf/tags/parked.html'
    page_title = 'Parked Tags'
    filterset = None

    def get_queryset(self):
        project = self.get_project()
        excluded = get_excluded_types(project)
        queryset = self.model.objects.filter(page__document__project=project,
                                         dictionary_entry=None,
                                         is_parked=True).exclude(variation_type__in=excluded)
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset,
                                              project=project,
                                              excluded=excluded)
        return self.filterset.qs


class TWFProjectTagsResolvedView(TWFProjectTagsView):
    """View for the resolved tags."""
    template_name = 'twf/tags/resolved.html'
    page_title = 'Resolved Tags'
    filterset = None

    def get_queryset(self):
        project = self.get_project()
        excluded = get_excluded_types(project)
        queryset1 = self.model.objects.filter(page__document__project=project,
                                              dictionary_entry__isnull=False,
                                              is_parked=False).exclude(variation_type__in=excluded)
        queryset2 = self.model.objects.filter(page__document__project=project,
                                              date_variation_entry__isnull=False,
                                              variation_type__in=get_date_types(project),
                                              is_parked=False).exclude(variation_type__in=excluded)
        queryset = queryset1 | queryset2
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset,
                                              project=project,
                                              excluded=excluded)
        return self.filterset.qs


class TWFProjectTagsIgnoredView(TWFProjectTagsView):
    """View for the ignored tags."""
    template_name = 'twf/tags/ignored.html'
    page_title = 'Ignored Tags'
    filterset = None

    def get_queryset(self):
        """Get the queryset."""
        project = self.get_project()
        excluded = get_excluded_types(project)
        queryset = self.model.objects.filter(page__document__project=project,
                                             variation_type__in=excluded)
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset,
                                              project=project,
                                              excluded=excluded)
        return self.filterset.qs


class TWFTagsDatesGroupView(FormView, TWFTagsView):
    """View for the date tags."""
    template_name = 'twf/tags/dates.html'
    page_title = 'Date Tags'
    form_class = DateNormalizationForm

    def form_valid(self, form):
        """Handle the form submission."""
        logger.debug("Date normalization form is valid")
        tag_id = form.cleaned_data['date_tag']
        tag = PageTag.objects.get(pk=tag_id)
        date_variation = DateVariation(
            variation=tag.variation,
            edtf_of_normalized_variation=form.cleaned_data['resulting_date'])
        date_variation.save(current_user=self.request.user)
        tag.date_variation_entry = date_variation
        tag.save(current_user=self.request.user)
        messages.success(self.request, 'Date normalized successfully.')
        return redirect('twf:tags_dates')

    def get(self, request, *args, **kwargs):
        """Override the get method to handle no more tags scenario."""
        # Check for the next available date tag
        project = self.get_project()
        next_date = PageTag.objects.filter(
            page__document__project=project,
            variation_type__in=get_date_types(project),
            is_parked=False,
            date_variation_entry__isnull=True
        ).first()

        if next_date is None:
            messages.info(request, "No more date tags are available for normalization.")
            return redirect(reverse_lazy('twf:tags_overview'))

        # If `next_date` exists, proceed with the normal flow
        return super().get(request, *args, **kwargs)

    def get_form_kwargs(self):
        """Get the form kwargs."""
        kwargs = super().get_form_kwargs()

        project = self.get_project()
        next_date = PageTag.objects.filter(page__document__project=project,
                                           variation_type__in=get_date_types(project),
                                           is_parked=False,
                                           date_variation_entry__isnull=True).first()

        kwargs['project'] = self.get_project()
        kwargs['date_tag'] = next_date
        return kwargs

    def get_context_data(self, **kwargs):
        """Get the context data."""
        context = super().get_context_data(**kwargs)
        project = self.get_project()
        context['has_next_tag'] = PageTag.objects.filter(page__document__project=project,
                                                         variation_type__in=get_date_types(project),
                                                         is_parked=False,
                                                         date_variation_entry__isnull=True).exists()
        return context
