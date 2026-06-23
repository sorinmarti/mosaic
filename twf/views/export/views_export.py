"""Views for exporting data from the TWF."""
import json
import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import FormView
from django_filters.views import FilterView
from django_tables2 import SingleTableView

from twf.clients.zenodo_client import get_zenodo_uploads
from twf.forms.dictionaries.dictionaries_forms import DictionaryImportForm
from twf.forms.export_forms import ExportProjectForm, ExportZenodoForm, \
    ExportConfigurationForm, RunExportForm
from twf.forms.filters.filters import ExportFilter, ExportConfigFilter
from twf.models import Export, ExportConfiguration, Project, Document, Page, CollectionItem, DictionaryEntry
from twf.tables.tables_export import ExportTable, ExportConfigTable
from twf.utils.export_utils import ExportCreator
from twf.views.views_base import TWFView

logger = logging.getLogger(__name__)


class TWFExportView(LoginRequiredMixin, TWFView):
    """Base view for all export views."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

    def get_navigation_index(self):
        return 7

    def get_sub_navigation(self):
        sub_nav = [
            {
                'name': 'Overview',
                'options': [
                    {'url': reverse_lazy('twf:export_overview'), 'value': 'Export Overview'},
                    {'url': reverse_lazy('twf:export_view_export_confs'),
                     'value': 'Export Configurations', 'permission': 'import_export.view'},
                    {'url': reverse_lazy('twf:export_view_exports'),
                     'value': 'Exports', 'permission': 'import_export.view'},
                ]
            },
            {
                'name': 'Import Data',
                'options': [
                    {'url': reverse_lazy('twf:import_dictionaries'),
                     'value': 'Import Dictionaries', 'permission': 'import_export.manage'},
                ]
            },
            {
                'name': 'Export Data',
                'options': [
                    {'url': reverse_lazy('twf:export_configure'),
                     'value': 'Configure Exports', 'permission': 'import_export.edit'},
                    {'url': reverse_lazy('twf:export_run'),
                     'value': 'Run Exports', 'permission': 'import_export.manage'},
                    {'url': reverse_lazy('twf:export_project'),
                     'value': 'Export Project', 'permission': 'import_export.manage'},
                    {'url': reverse_lazy('twf:export_to_zenodo'),
                     'value': 'Connect to Zenodo', 'permission': 'import_export.manage'},
                ]
            },

        ]
        return sub_nav


class TWFExportOverviewView(TWFExportView):
    """View for the export overview."""

    template_name = "twf/export/export_overview.html"
    page_title = 'Import/Export'
    show_context_help = False

    def get_context_data(self, **kwargs):
        """Get the context data for the view."""
        context = super().get_context_data(**kwargs)
        return context
        
    def get_breadcrumbs(self):
        """Get the breadcrumbs for the view."""
        breadcrumbs = [
            {'url': reverse_lazy('twf:home'), 'value': '<i class="fas fa-home"></i>'},
            {'url': '#', 'value': self.page_title}
        ]
        return breadcrumbs


class TWFExportListView(SingleTableView, FilterView, TWFExportView):
    """View for the export overview."""

    template_name = "twf/export/export_list.html"
    page_title = 'Export Overview'
    table_class = ExportTable
    filterset_class = ExportFilter
    paginate_by = 10
    model = Export
    navigation_anchor = reverse_lazy('twf:export_view_exports')
    navigation_anchor = "export_view_exports"
    
    def get_breadcrumbs(self):
        """Get the breadcrumbs for the view."""
        breadcrumbs = [
            {'url': reverse_lazy('twf:home'), 'value': '<i class="fas fa-home"></i>'},
            {'url': reverse_lazy('twf:export_overview'), 'value': 'Import/Export'},
            {'url': '#', 'value': self.page_title}
        ]
        return breadcrumbs

    def get_queryset(self):
        """Get the queryset for the view."""
        queryset = Export.objects.filter(export_configuration__project_id=self.request.session.get('project_id')).order_by('-created_at')
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get(self, request, *args, **kwargs):
        """Get the view."""
        self.object_list = self.get_queryset()
        context = self.get_context_data()
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        """Get the context data for the view."""
        context = super().get_context_data(**kwargs)
        context['filter'] = self.get_filterset(self.filterset_class)
        return context


class TWFExportConfListView(SingleTableView, FilterView, TWFExportView):
    """View for the export overview."""

    template_name = "twf/export/export_conf_list.html"
    page_title = 'Export Configurations Overview'
    table_class = ExportConfigTable
    filterset_class = ExportConfigFilter
    paginate_by = 10
    model = ExportConfiguration
    navigation_anchor = reverse_lazy('twf:export_view_export_confs')
    
    def get_breadcrumbs(self):
        """Get the breadcrumbs for the view."""
        breadcrumbs = [
            {'url': reverse_lazy('twf:home'), 'value': '<i class="fas fa-home"></i>'},
            {'url': reverse_lazy('twf:export_overview'), 'value': 'Import/Export'},
            {'url': '#', 'value': self.page_title}
        ]
        return breadcrumbs

    def get_queryset(self):
        """Get the queryset for the view."""
        queryset = ExportConfiguration.objects.filter(project_id=self.request.session.get('project_id')).order_by('-created_at')
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get(self, request, *args, **kwargs):
        """Get the view."""
        self.object_list = self.get_queryset()
        context = self.get_context_data()
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        """Get the context data for the view."""
        context = super().get_context_data(**kwargs)
        context['filter'] = self.get_filterset(self.filterset_class)
        return context


class TWFExportSampleView(TWFExportView):
    template_name = "twf/export/export_configuration_sample.html"
    page_title = 'View Sample Export'
    navigation_anchor = reverse_lazy('twf:export_view_export_confs')

    def get_context_data(self, **kwargs):
        """Get the context data for the view."""
        context = super().get_context_data(**kwargs)
        export_conf = ExportConfiguration.objects.get(pk=self.kwargs['pk'], project=self.get_project())
        context['export_conf'] = export_conf
        export_creator = ExportCreator(self.get_project(), export_conf)
        context['sample_data'] = export_creator.create_sample_data()
        return context
        
    def get_breadcrumbs(self):
        """Get the breadcrumbs for the view."""
        breadcrumbs = [
            {'url': reverse_lazy('twf:home'), 'value': '<i class="fas fa-home"></i>'},
            {'url': reverse_lazy('twf:export_overview'), 'value': 'Import/Export'},
            {'url': reverse_lazy('twf:export_view_export_confs'), 'value': 'Export Configurations'},
            {'url': '#', 'value': self.page_title}
        ]
        return breadcrumbs

class TWFExportConfigurationView(FormView, TWFExportView):
    """View for exporting documents."""

    template_name = "twf/export/export_configuration.html"
    page_title = 'Export Configuration'
    form_class = ExportConfigurationForm
    success_url = reverse_lazy('twf:export_view_export_confs')
    navigation_anchor = reverse_lazy('twf:export_configure')
    
    def get_breadcrumbs(self):
        """Get the breadcrumbs for the view."""
        breadcrumbs = [
            {'url': reverse_lazy('twf:home'), 'value': '<i class="fas fa-home"></i>'},
            {'url': reverse_lazy('twf:export_overview'), 'value': 'Import/Export'},
            {'url': '#', 'value': self.page_title}
        ]
        return breadcrumbs

    def get_context_data(self, **kwargs):
        """Get the context data for the view."""
        context = super().get_context_data(**kwargs)

        (db_fields, special_fields,
         metadata_doc_services, metadata_doc_fields,
         metadata_page_service, metadata_page_fields,
         metadata_entry_service, metadata_entry_fields) = self.get_export_context_data()
        context['db_fields_json'] = json.dumps(db_fields)
        context['all_db_fields_json'] = json.dumps(db_fields)  # All fields available in all sections
        context['special_fields_json'] = json.dumps(special_fields)
        context['metadata_doc_services_json'] = json.dumps(metadata_doc_services)
        context['metadata_doc_fields_json'] = json.dumps(metadata_doc_fields)
        context['metadata_page_services_json'] = json.dumps(metadata_page_service)
        context['metadata_page_fields_json'] = json.dumps(metadata_page_fields)
        context['metadata_entry_services_json'] = json.dumps(metadata_entry_service)
        context['metadata_entry_fields_json'] = json.dumps(metadata_entry_fields)

        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        project = self.get_project()
        kwargs['project'] = project
        if 'pk' in self.kwargs:
            instance = ExportConfiguration.objects.get(pk=self.kwargs['pk'], project=project)

            if instance.content_object:
                if instance.export_type == 'collection':
                    kwargs.setdefault('initial', {})['collection'] = instance.content_object
                elif instance.export_type == 'dictionary':
                    kwargs.setdefault('initial', {})['dictionary'] = instance.content_object

            kwargs['instance'] = instance

        return kwargs

    def form_valid(self, form):
        export_conf = form.save(commit=False)
        export_conf.project = self.get_project()

        raw_config = form.cleaned_data.get('config', '{}')
        try:
            export_conf.config = json.loads(raw_config)
        except json.JSONDecodeError:
            export_conf.config = {}

        # Set GenericForeignKey fields conditionally
        export_type = export_conf.export_type

        if export_type == 'collection' and form.cleaned_data.get('collection'):
            collection = form.cleaned_data['collection']
            export_conf.content_type = ContentType.objects.get_for_model(collection)
            export_conf.object_id = collection.pk

        elif export_type == 'dictionary' and form.cleaned_data.get('dictionary'):
            dictionary = form.cleaned_data['dictionary']
            export_conf.content_type = ContentType.objects.get_for_model(dictionary)
            export_conf.object_id = dictionary.pk
        else:
            export_conf.content_type = None
            export_conf.object_id = None

        export_conf.save(current_user=self.request.user)
        return super().form_valid(form)

    def get_export_context_data(self):
        project = self.get_project()
        sample_doc = project.documents.first()
        sample_page = sample_doc.pages.first()
        sample_entry = project.selected_dictionaries.first().entries.first()

        db_fields = {
            'general': [
                ('project.id', 'Mosaic Project ID', project.id),
                ('project.title', 'Project Title', project.title),
                ('project.description', 'Project Description', project.description),
                ('project.collection_id', 'Transkribus Collection ID', project.collection_id),
                ('project.downloaded_at', 'Downloaded At', project.downloaded_at.strftime('%Y-%m-%d %H:%M:%S')),
            ],
            'documents': [
                ('document.id', 'Mosaic Document ID', sample_doc.id),
                ('document.title', 'Document Title', sample_doc.title),
                ('document.document_id', 'Transkribus Document ID', sample_doc.document_id),
                ('document.is_parked', 'Is Parked', sample_doc.is_parked),
                ('document.workflow_remarks', 'Workflow Remarks', sample_doc.workflow_remarks),
                ('document.status', 'Status', sample_doc.status),
            ],
            'pages': [
                ('page.id', 'Mosaic Page ID', sample_page.id),
                ('page.tk_page_id', 'Transkribus Page ID', sample_page.tk_page_id),
                ('page.tk_page_number', 'Transkribus Page Number', sample_page.tk_page_number),
                ('page.is_ignored', 'Is Ignored', sample_page.is_ignored),
            ],
            'items': [
                ('collection_item.title', 'Collection Item Title', ''),
                ('collection_item.description', 'Collection Item Description', ''),
            ],
            'entries': [],
            'tags': []
        }

        special_fields = {
            'general_project': [
                ('project_members', 'List of Project Members', '[{"name": "User 1", "orcid": "123-123", ...}]'),
                ('dictionaries', 'List of used Dictionaries', '[{"name": "Dictionary 1", "id": 1, ...}]'),
                ('no_of_docs', 'Number of Documents', '123'),
            ],
            'general_collection': [
                ('collection_items_count', 'Number of Collection Items', '123'),
            ],
            'documents': [
                ('tag_list', 'List of tags', '["tag1", "tag2", ...]'),
                ('tag_list_unique', 'Unique List of tags', '["tag1", "tag2", ...]'),
                ('tags_count', 'Number of tags', '123'),
                ('linked_tags_list', 'List of linked tags', '["tag1", "tag2", ...]'),
                ('linked_tags_list_unique', 'Unique List of linked tags', '["tag1", "tag2", ...]'),
                ('linked_tags_count', 'Number of linked tags', '123'),
                ('entry_list', 'List of Dictionary entries', '[{"name": "Entry 1", "id": 1, ...}]'),
                ('word_count', 'Word Count', '123'),
                ('last_twf_edit', 'Last TWF Edit', '2025-10-01 12:00:00'),
            ],
            'pages': [
                ('tag_list', 'List of tags', '["tag1", "tag2", ...]'),
                ('tag_list_unique', 'Unique List of tags', '["tag1", "tag2", ...]'),
                ('tags_count', 'Number of tags', '123'),
                ('linked_tags_list', 'List of linked tags', '["tag1", "tag2", ...]'),
                ('linked_tags_list_unique', 'Unique List of linked tags', '["tag1", "tag2", ...]'),
                ('linked_tags_count', 'Number of linked tags', '123'),
                ('entry_list', 'List of Dictionary entries', '[{"name": "Entry 1", "id": 1, ...}]'),
                ('word_count', 'Word Count', '123'),
                ('last_twf_edit', 'Last TWF Edit', '2025-10-01 12:00:00'),
            ],
            'items': [
                ('no_of_annotations', 'Number of Annotations', '12'),
                ('item_context', 'Item Context', '{"type": "document", "id": 1}'),
            ],
            'entries': [
                ('last_twf_edit', 'Last TWF Edit', '2025-10-01 12:00:00'),
            ],
            'tags': [
                ('last_twf_edit', 'Last TWF Edit', '2025-10-01 12:00:00'),
            ]
        }

        # Collect all unique metadata keys across all documents
        metadata_doc_services = []
        metadata_doc_fields = {}
        all_doc_metadata_keys = {}

        # Iterate through all documents to find all unique metadata keys
        for doc in project.documents.all():
            if doc.metadata:
                for key, value in doc.metadata.items():
                    if key not in all_doc_metadata_keys:
                        all_doc_metadata_keys[key] = value

        # Build metadata services and fields from all unique keys
        for key, value in all_doc_metadata_keys.items():
            metadata_doc_services.append((key, key, str(value)))
            metadata_doc_fields[key] = self.flatten_metadata('', value)

        # Collect all unique metadata keys across all pages
        metadata_page_service = []
        metadata_page_fields = {}
        all_page_metadata_keys = {}

        # Iterate through all pages to find all unique metadata keys
        for doc in project.documents.all():
            for page in doc.pages.all():
                if page.metadata:
                    for key, value in page.metadata.items():
                        if key not in all_page_metadata_keys:
                            all_page_metadata_keys[key] = value

        # Build metadata services and fields from all unique keys
        for key, value in all_page_metadata_keys.items():
            metadata_page_service.append((key, key, str(value)))
            metadata_page_fields[key] = self.flatten_metadata('', value)

        # Collect all unique metadata keys across all dictionary entries
        metadata_entry_service = []
        metadata_entry_fields = {}
        all_entry_metadata_keys = {}

        # Iterate through all dictionary entries to find all unique metadata keys
        for dictionary in project.selected_dictionaries.all():
            for entry in dictionary.entries.all():
                if entry.metadata:
                    for key, value in entry.metadata.items():
                        if key not in all_entry_metadata_keys:
                            all_entry_metadata_keys[key] = value

        # Build metadata services and fields from all unique keys
        for key, value in all_entry_metadata_keys.items():
            metadata_entry_service.append((key, key, str(value)))
            metadata_entry_fields[key] = self.flatten_metadata('', value)

        return (db_fields, special_fields, metadata_doc_services,
                metadata_doc_fields, metadata_page_service, metadata_page_fields,
                metadata_entry_service, metadata_entry_fields)

    def flatten_metadata(self, prefix, metadata, max_list_items=3):
        fields = []
        if isinstance(metadata, dict):
            for key, value in metadata.items():
                full_key = f"{prefix}.{key}" if prefix else key
                if isinstance(value, dict):
                    fields.extend(self.flatten_metadata(full_key, value, max_list_items))
                elif isinstance(value, list):
                    # Handle lists: take first few elements only
                    for idx, item in enumerate(value[:max_list_items]):
                        item_key = f"{full_key}[{idx}]"
                        if isinstance(item, dict):
                            fields.extend(self.flatten_metadata(item_key, item, max_list_items))
                        else:
                            fields.append((item_key, f"{key}[{idx}]", str(item)))
                else:
                    fields.append((full_key, full_key, str(value)))
        return fields


class TWFExportRunView(FormView, TWFExportView):
    """View for the export overview."""

    template_name = "twf/export/export_documents.html"
    page_title = 'Run Export'
    form_class = RunExportForm
    success_url = reverse_lazy('twf:export_run')
    navigation_anchor = reverse_lazy('twf:export_run')
    
    def get_breadcrumbs(self):
        """Get the breadcrumbs for the view."""
        breadcrumbs = [
            {'url': reverse_lazy('twf:home'), 'value': '<i class="fas fa-home"></i>'},
            {'url': reverse_lazy('twf:export_overview'), 'value': 'Import/Export'},
            {'url': '#', 'value': self.page_title}
        ]
        return breadcrumbs

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['project'] = self.get_project()

        kwargs['data-start-url'] = reverse_lazy('twf:task_export')
        kwargs['data-message'] = "Are you sure you want to start the export?"

        return kwargs

    def get_context_data(self, **kwargs):
        """Get the context data for the view."""
        context = super().get_context_data(**kwargs)
        return context


class TWFExportProjectView(FormView, TWFExportView):
    """View for exporting a project"""

    template_name = "twf/export/export_project.html"
    page_title = 'Export Project'
    form_class = ExportProjectForm
    success_url = reverse_lazy('twf:export_project')
    navigation_anchor = reverse_lazy('twf:export_project')
    
    def get_breadcrumbs(self):
        """Get the breadcrumbs for the view."""
        breadcrumbs = [
            {'url': reverse_lazy('twf:home'), 'value': '<i class="fas fa-home"></i>'},
            {'url': reverse_lazy('twf:export_overview'), 'value': 'Import/Export'},
            {'url': '#', 'value': self.page_title}
        ]
        return breadcrumbs

    def get_context_data(self, **kwargs):
        """Get the context data for the view."""
        context = super().get_context_data(**kwargs)
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['project'] = self.get_project()

        kwargs['data-start-url'] = reverse_lazy('twf:task_export_project')
        kwargs['data-message'] = "Are you sure you want to export your project?"

        return kwargs


class TWFExportZenodoView(TWFExportView):
    """ View for exporting a project to Zenodo.
    This view allows users to create and/or connect their project to a Zenodo deposition,
    or unlink the two. Furthermore, it provides the starting point for the
    actual upload process. If a connection between TWF and Zenodo is established,
    a user can select the export they want to upload to Zenodo and review their
    upload metadata.
    This view does not handle the actual upload process."""
    template_name = "twf/export/export_zenodo.html"
    page_title = 'Export to Zenodo'

    def get_context_data(self, **kwargs):
        """Get the context data for the view."""
        context = super().get_context_data(**kwargs)
        context['has_zenodo_token'] = self.get_project().get_credentials('zenodo').get('zenodo_token') not in [None, '']
        context['existing_zenodo_uploads'] = get_zenodo_uploads(self.get_project())
        context['exports'] = Export.objects.filter(export_configuration__project=self.get_project())
        return context

    def post(self, request, *args, **kwargs):
        """Handle 'Prepare Upload' Form"""
        export_id = request.POST.get('export_id')
        if export_id:
            return redirect('twf:zenodo_upload', export_id=int(export_id))


class TWFExportZenodoVersionView(FormView, TWFExportView):
    """View for exporting a project to Zenodo.
    This view is called from the Zenodo upload view. A connection
    to the Zenodo repository is required to upload the export."""

    template_name = "twf/export/export_zenodo_upload.html"
    page_title = 'Upload Export to Zenodo'
    form_class = ExportZenodoForm
    navigation_anchor = reverse_lazy('twf:export_to_zenodo')

    def get_success_url(self):
        """Get the success URL for the view."""
        return reverse_lazy('twf:zenodo_upload', export_id=self.kwargs['export_id'])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['project'] = self.get_project()
        kwargs['hidden-export-id'] = self.kwargs['export_id']
        kwargs['data-start-url'] = reverse_lazy('twf:task_export_zenodo')
        kwargs['data-message'] = "Are you sure you want to upload your data to Zenodo?"

        return kwargs

    def get_context_data(self, **kwargs):
        """Get the context data for the view."""
        context = super().get_context_data(**kwargs)
        export = Export.objects.get(pk=self.kwargs['export_id'])
        context['export'] = export
        context['total_size'] = len(self.get_project().workflow_description) + export.export_file.size
        return context

class TWFImportDictionaryView(FormView, TWFExportView):
    """View for importing a dictionary."""

    template_name = 'twf/export/import_dictionaries.html'
    page_title = 'Import Dictionary'
    form_class = DictionaryImportForm   # TODO Move form class
    navigation_anchor = reverse_lazy('twf:import_dictionaries')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        return kwargs
        
    def get_breadcrumbs(self):
        """Get the breadcrumbs for the view."""
        breadcrumbs = [
            {'url': reverse_lazy('twf:home'), 'value': '<i class="fas fa-home"></i>'},
            {'url': reverse_lazy('twf:export_overview'), 'value': 'Import/Export'},
            {'url': '#', 'value': self.page_title}
        ]
        return breadcrumbs
