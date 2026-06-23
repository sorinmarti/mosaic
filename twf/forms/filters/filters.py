"""Filter classes for the twf app."""
import logging
import django_filters
from django.db.models import Q
from django.forms import CheckboxInput, DateInput
from django.contrib.auth import get_user_model
from twf.models import Document, DictionaryEntry, PageTag, CollectionItem, Task, Prompt, Project, Export, Note, \
    Collection, Dictionary, ExportConfiguration

User = get_user_model()

logger = logging.getLogger(__name__)


class TagFilter(django_filters.FilterSet):
    """Filter for the tags table."""

    variation = django_filters.CharFilter(
        lookup_expr='icontains', 
        label='Tag Text Contains'
    )
    
    variation_type = django_filters.ChoiceFilter(
        field_name='variation_type',
        label='Tag Type',
        choices=[],  # Placeholder for choices, will populate dynamically
        empty_label="All Types"
    )
    
    # Filter for documents
    document_title = django_filters.CharFilter(
        field_name='page__document__title',
        lookup_expr='icontains',
        label='Document Title Contains'
    )
    
    document_id = django_filters.CharFilter(
        field_name='page__document__document_id',
        lookup_expr='icontains',
        label='Document ID Contains'
    )
    
    # Filter for resolved/unresolved tags
    is_resolved = django_filters.BooleanFilter(
        method='filter_resolved',
        label='Resolved Tags Only',
        widget=CheckboxInput()
    )

    class Meta:
        """Meta class for the tag filter."""
        model = PageTag
        fields = ['variation', 'variation_type', 'document_title', 'document_id', 'is_resolved']

    def __init__(self, *args, **kwargs):
        project = kwargs.pop('project', None)
        excluded = kwargs.pop('excluded', [])

        super().__init__(*args, **kwargs)

        # Dynamically populate the choices for variation_type
        distinct_variation_types = (
            PageTag.objects.filter(page__document__project=project)
            .exclude(variation_type__in=excluded)
            .distinct()
            .values('variation_type')
            .order_by('variation_type')
        )

        choices = [(vt['variation_type'], vt['variation_type']) for vt in distinct_variation_types]
        logger.debug("Tag variation type filter choices: %s", choices)
        self.filters['variation_type'].extra.update({
            'choices': choices
        })
        
    def filter_resolved(self, queryset, name, value):
        """Filter for resolved/unresolved tags."""
        if value:  # If checkbox is checked, show only resolved tags
            # Tags with dictionary entries or date variations are considered resolved
            # Note: Using Q objects for database-level filtering (more efficient than loading
            # all objects and calling is_resolved() method)
            return queryset.filter(
                Q(dictionary_entry__isnull=False) | Q(date_variation_entry__isnull=False)
            )
        return queryset


class DocumentFilter(django_filters.FilterSet):
    """Filter for the documents table."""

    document_id = django_filters.CharFilter(lookup_expr='icontains', label="Document ID contains")
    title = django_filters.CharFilter(lookup_expr='icontains', label="Title contains")
    status = django_filters.ChoiceFilter(
        choices=Document.STATUS_CHOICES,
        label="Status", 
        empty_label="All Statuses"
    )
    is_parked = django_filters.BooleanFilter(
        label="Show parked documents only",
        widget=CheckboxInput()
    )
    is_ignored = django_filters.BooleanFilter(
        label="Show excluded documents only",
        widget=CheckboxInput()
    )
    has_pages = django_filters.BooleanFilter(
        method='filter_has_pages',
        label="Has pages",
        widget=CheckboxInput()
    )

    class Meta:
        """Meta class for the document filter."""
        model = Document
        fields = ['document_id', 'title', 'status', 'is_parked', 'is_ignored', 'has_pages']
        
    def filter_has_pages(self, queryset, name, value):
        """Filter documents that have pages."""
        if value:
            return queryset.filter(pages__isnull=False).distinct()
        return queryset


class TaskFilter(django_filters.FilterSet):
    """Filter for the tasks table."""
    
    title = django_filters.CharFilter(lookup_expr='icontains', label="Title contains")
    description = django_filters.CharFilter(lookup_expr='icontains', label="Description contains")
    status = django_filters.ChoiceFilter(
        choices=Task.TASK_STATUS_CHOICES,
        label="Status", 
        empty_label="All Statuses"
    )
    user = django_filters.ModelChoiceFilter(
        queryset=User.objects.all(),
        label="Started By",
        empty_label="All Users"
    )
    # Date range filters with custom widgets
    start_time_after = django_filters.DateFilter(
        field_name='start_time',
        lookup_expr='gte',
        label='Started After',
        widget=DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    start_time_before = django_filters.DateFilter(
        field_name='start_time', 
        lookup_expr='lte',
        label='Started Before',
        widget=DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    end_time_after = django_filters.DateFilter(
        field_name='end_time',
        lookup_expr='gte',
        label='Completed After',
        widget=DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    end_time_before = django_filters.DateFilter(
        field_name='end_time',
        lookup_expr='lte',
        label='Completed Before',
        widget=DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    has_completed = django_filters.BooleanFilter(
        field_name='end_time',
        lookup_expr='isnull',
        exclude=True,
        label="Completed Tasks Only",
        widget=CheckboxInput()
    )

    class Meta:
        """Meta class for the task filter."""
        model = Task
        fields = [
            'title', 'description', 'status', 'user', 
            'start_time_after', 'start_time_before', 'end_time_after', 'end_time_before', 'has_completed'
        ]
        # Don't enforce form validation (important for empty filters)
        strict = False
        
    def __init__(self, *args, **kwargs):
        project = kwargs.pop('project', None)
        super().__init__(*args, **kwargs)
        
        # If project is provided, limit user choices to project members
        if project:
            self.filters['user'].queryset = User.objects.filter(
                profile__in=project.get_project_members()
            )
            
    def filter_queryset(self, queryset):
        """
        Filter the queryset with the underlying form data.
        Overridden to handle the empty filter case and debug filtering issues.
        """
        # Always log filter data for debugging
        logger.debug("Filter data: %s", self.data)
        
        # If no filter data is provided, return the entire queryset
        if not self.is_bound:
            logger.debug("Filter not bound, returning original queryset")
            return queryset
            
        # Skip validation check - use whatever valid filters are available
        result = queryset
        
        # Apply each filter individually for debugging purposes
        for name, filter_obj in self.filters.items():
            value = self.form[name].data if name in self.form.fields and name in self.data else None
            
            if value:
                filtered = filter_obj.filter(result, value)
                logger.debug(f"Applied filter {name}={value}: {result.count()} -> {filtered.count()}")
                result = filtered
        
        logger.debug(f"Final filtered count: {result.count()}")
        return result

class PromptFilter(django_filters.FilterSet):
    """Filter for the prompts table."""
    
    system_role = django_filters.CharFilter(lookup_expr='icontains', label="Role contains")
    prompt = django_filters.CharFilter(lookup_expr='icontains', label="Prompt text contains")

    class Meta:
        """Meta class for the prompt filter."""
        model = Prompt
        fields = ['system_role', 'prompt']


class NoteFilter(django_filters.FilterSet):
    """Filter for the prompts table."""

    class Meta:
        """Meta class for the prompt filter."""
        model = Note
        fields = {
            'title': ['icontains'],
            'note': ['icontains'],
        }

class ProjectFilter(django_filters.FilterSet):
    """Filter for the projects table."""

    title = django_filters.CharFilter(lookup_expr='icontains', label="Title contains")
    status = django_filters.ChoiceFilter(choices=Project.STATUS_CHOICES)
    owner__user__username = django_filters.CharFilter(lookup_expr='icontains', label="Owner username")

    class Meta:
        model = Project
        fields = ['title', 'status', 'owner__user__username']


class DictionaryFilter(django_filters.FilterSet):
    """Filter for the dictionaries table."""
    
    label = django_filters.CharFilter(lookup_expr='icontains', label="Label contains")
    type = django_filters.ChoiceFilter(
        choices=[
            ('person', 'Person'),
            ('place', 'Place'),
            ('organization', 'Organization'),
            ('topic', 'Topic'),
            ('date', 'Date'),
            ('other', 'Other')
        ],
        label="Dictionary type", 
        empty_label="All types"
    )
    
    class Meta:
        """Meta class for the dictionary filter."""
        model = Dictionary
        fields = ['label', 'type']


class DictionaryEntryFilter(django_filters.FilterSet):
    """Filter for the dictionary entry table."""
    
    label = django_filters.CharFilter(lookup_expr='icontains', label="Label contains")
    variation = django_filters.CharFilter(
        method='filter_by_variation',
        label="Variation contains"
    )
    has_metadata = django_filters.BooleanFilter(
        method='filter_has_metadata',
        label="Has normalization data",
        widget=CheckboxInput()
    )
    has_variations = django_filters.BooleanFilter(
        method='filter_has_variations',
        label="Has variations",
        widget=CheckboxInput()
    )
    modified_by = django_filters.CharFilter(
        field_name='modified_by',
        lookup_expr='icontains',
        label="Modified by"
    )
    modified_after = django_filters.DateFilter(
        field_name='modified_at',
        lookup_expr='gte',
        label='Modified after',
        widget=DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    modified_before = django_filters.DateFilter(
        field_name='modified_at',
        lookup_expr='lte',
        label='Modified before',
        widget=DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    class Meta:
        """Meta class for the dictionary entry filter."""
        model = DictionaryEntry
        fields = [
            'label', 'variation', 'has_metadata', 'has_variations',
            'modified_by', 'modified_after', 'modified_before'
        ]
        
    def filter_has_metadata(self, queryset, name, value):
        """Filter entries that have metadata."""
        if value:
            return queryset.exclude(metadata={})
        return queryset
        
    def filter_has_variations(self, queryset, name, value):
        """Filter entries that have variations."""
        if value:
            return queryset.filter(variations__isnull=False).distinct()
        return queryset
        
    def filter_by_variation(self, queryset, name, value):
        """Filter entries by variation text."""
        if value:
            return queryset.filter(variations__variation__icontains=value).distinct()
        return queryset



class CollectionFilter(django_filters.FilterSet):
    """Filter for the collections table."""
    
    title = django_filters.CharFilter(lookup_expr='icontains', label="Title contains")
    description = django_filters.CharFilter(lookup_expr='icontains', label="Description contains")
    created_by__username = django_filters.CharFilter(lookup_expr='icontains', label="Created by")
    
    class Meta:
        """Meta class for the collection filter."""
        model = Collection
        fields = ["title", "description", "created_by__username"]


class CollectionItemFilter(django_filters.FilterSet):
    """Filter for the collection item table."""

    document_id = django_filters.CharFilter(field_name="document__document_id", lookup_expr="icontains",
                                            label="Document ID")
    title = django_filters.CharFilter(lookup_expr='icontains', label="Item Title")
    document_title = django_filters.CharFilter(field_name="document__title", lookup_expr="icontains",
                                               label="Document Title")
    status = django_filters.ChoiceFilter(
        choices=CollectionItem.STATUS_CHOICES,
        label="Status", 
        empty_label="All Statuses"
    )

    class Meta:
        """Meta class for the collection item filter."""
        model = CollectionItem
        fields = ["document_id", "title", "document_title", "status"]


class UserFilter(django_filters.FilterSet):
    username = django_filters.CharFilter(lookup_expr="icontains", label="Username contains")
    email = django_filters.CharFilter(lookup_expr="icontains", label="Email contains")
    is_active = django_filters.BooleanFilter(label="Is Active")
    is_superuser = django_filters.BooleanFilter(label="Is Admin")

    class Meta:
        model = User
        fields = ["username", "email", "is_active", "is_superuser"]


class ExportFilter(django_filters.FilterSet):
    """Filter for the exports table."""

    export_configuration__name = django_filters.ModelChoiceFilter(
        queryset=ExportConfiguration.objects.all(),
        label="Export Configuration",
        empty_label="All Configurations"
    )

    created_by__username = django_filters.CharFilter(
        lookup_expr='icontains',
        label="Created by contains"
    )
    
    # Date range filters with custom widgets
    created_after = django_filters.DateFilter(
        field_name='created',
        lookup_expr='gte',
        label='Created After',
        widget=DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    created_before = django_filters.DateFilter(
        field_name='created', 
        lookup_expr='lte',
        label='Created Before',
        widget=DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    class Meta:
        """Meta class for the export filter."""
        model = Export
        fields = ["export_configuration__name", "created_by__username", "created_after", "created_before"]
        # Don't enforce form validation (important for empty filters)
        strict = False


class ExportConfigFilter(django_filters.FilterSet):
    """Filter for the export configurations table."""

    name = django_filters.CharFilter(lookup_expr='icontains', label="Name contains")

    created_by__username = django_filters.CharFilter(
        lookup_expr='icontains',
        label="Created by contains"
    )

    # Date range filters with custom widgets
    created_after = django_filters.DateFilter(
        field_name='created',
        lookup_expr='gte',
        label='Created After',
        widget=DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    created_before = django_filters.DateFilter(
        field_name='created',
        lookup_expr='lte',
        label='Created Before',
        widget=DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    class Meta:
        """Meta class for the export filter."""
        model = ExportConfiguration
        fields = ["name", "created_by__username", "created_after", "created_before"]
        # Don't enforce form validation (important for empty filters)
        strict = False