""" This module contains the views for the Collection model. """
import logging
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.generic import FormView
from django_filters.views import FilterView
from django_tables2 import SingleTableView

from twf.forms.filters.filters import CollectionItemFilter, CollectionFilter
from twf.permissions import check_permission
from twf.tables.tables_collection import CollectionTable

logger = logging.getLogger(__name__)
from twf.forms.collections.collections_forms import CollectionCreateForm, CollectionAddDocumentForm, CollectionUpdateForm, \
    CollectionItemReviewForm, CollectionItemUpdateForm
from twf.models import CollectionItem, Collection, Workflow, Document
from twf.tables.tables_collection import CollectionItemTable
from twf.views.collections.views_crud import fill_collection_item, clean_annotation
from twf.views.views_base import TWFView


class TWFCollectionsView(LoginRequiredMixin, TWFView):
    """ View for the project collections page. """

    template_name = None
    page_title = None

    def get_context_data(self, **kwargs):
        """Get the context data for the view."""
        context = super().get_context_data(**kwargs)
        context['collections'] = Collection.objects.filter(project_id=self.request.session.get('project_id'))
        return context

    def get_sub_navigation(self):
        """Get the sub-navigation for the view."""
        sub_nav = [
            {
                'name': 'Overview',
                'options': [
                    {"url": reverse('twf:collections'), "value": "Overview"},
                    {"url": reverse('twf:collections_view'),
                     "value": "Your Collections", "permission": "collection.view"},
                    {"url": reverse('twf:project_collections_create'),
                     "value": "Create New Collection", "permission": "collection.manage"}
                ]
            },
            {
                'name': 'Automated Workflows',
                'options': self.get_ai_batch_options()
            },
            {
                'name': 'Supervised Workflows',
                'options': [
                    {"url": reverse('twf:collections_review'),
                     "value": "Review Collections", "permission": "collection.edit"},
                ] + self.get_ai_request_options()
            }
        ]

        return sub_nav

    def get_navigation_index(self):
        """Get the index of the navigation item."""
        return 6

    def get_ai_batch_options(self):
        """
        Get the AI batch options.
        Returns simplified navigation with unified AI Batch processing.
        """
        options = [
            {'url': reverse('twf:collections_batch_ai_unified'),
             'value': 'AI Batch Processing',
             'permission': 'ai.manage'}
        ]
        return options

    def get_ai_request_options(self):
        """
        Get the AI request options.
        Returns simplified navigation with unified AI Request processing.
        """
        options = [
            {'url': reverse('twf:collections_request_ai_unified'),
             'value': 'AI Request',
             'permission': 'collection.edit'}
        ]
        return options


class TWFCollectionOverviewView(TWFCollectionsView):
    """ View for the collection overview page. """

    template_name = 'twf/collections/collections_overview.html'
    page_title = 'Collections'
    show_context_help = False

    def post(self, request, *args, **kwargs):
        """Handle the post request."""
        logger.debug("Collection post request: %s", request.POST)
        if "delete_collection" in request.POST:
            collection = Collection.objects.get(pk=request.POST.get('collection_id'))
            collection.delete()
            messages.success(request, 'Collection has been deleted successfully.')

    def get_context_data(self, **kwargs):
        """Get the context data for the view."""
        context = super().get_context_data(**kwargs)

        open_workflows = Workflow.objects.filter(project=self.get_project(), workflow_type="review_collection",
                                                 status='started').count()
        total_items = CollectionItem.objects.filter(collection__project=self.get_project()).count()
        reviewed_items = CollectionItem.objects.filter(collection__project=self.get_project(),
                                                       status='reviewed').count()
        percentage_reviewed = reviewed_items / total_items * 100 if total_items > 0 else 0

        context['open_workflows'] = open_workflows
        context['percentage_reviewed'] = percentage_reviewed

        return context


class TWFCollectionListView(SingleTableView, FilterView, TWFCollectionsView):
    """View for listing all collections."""
    template_name = 'twf/collections/collections_list.html'
    page_title = 'Collection List'
    table_class = CollectionTable
    filterset_class = CollectionFilter
    paginate_by = 10
    model = Collection
    strict = False
    
    def get_queryset(self):
        """Get the queryset for the view."""
        queryset = Collection.objects.filter(project_id=self.request.session.get('project_id'))
        return queryset
    
    def get(self, request, *args, **kwargs):
        """Handle GET requests."""
        # Set up initial queryset
        queryset = self.get_queryset()
        
        # Initialize the filter
        self.filterset = self.filterset_class(
            request.GET or None,
            queryset=queryset
        )
        
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
        context['filter'] = self.filterset
        return context


class TWFCollectionsEditView(FormView, TWFCollectionsView):
    """ View for creating a new collection. """

    template_name = 'twf/collections/collections_edit.html'
    page_title = 'Edit Collection'
    form_class = CollectionUpdateForm
    success_url = reverse_lazy('twf:collections')

    def get_initial(self):
        """Initialize form with the object's data."""
        self.object = get_object_or_404(Collection, pk=self.kwargs['pk'])
        return {
            'title': self.object.title,
            'description': self.object.description,
        }

    def form_valid(self, form):
        """Handle valid form submission."""
        collection = get_object_or_404(Collection, pk=self.kwargs['pk'])
        collection.title = form.cleaned_data['title']
        collection.description = form.cleaned_data['description']
        collection.save()
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        """Add additional context data if needed."""
        context = super().get_context_data(**kwargs)
        context['page_title'] = self.page_title
        return context


class TWFCollectionItemView(TWFCollectionsView):
    """ View for viewing a collection item. """

    template_name = 'twf/collections/collection_item_view.html'
    page_title = 'View Collection Item'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['item'] = CollectionItem.objects.get(pk=self.kwargs['pk'])
        return context

class TWFCollectionItemEditView(FormView, TWFCollectionsView):
    """ View for editing a collection item. """

    template_name = 'twf/collections/collection_item_edit.html'
    page_title = 'Edit Collection Item'
    form_class = CollectionItemUpdateForm

    def get_form_kwargs(self):
        """Pass instance to the form."""
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = get_object_or_404(CollectionItem, pk=self.kwargs['pk'])
        return kwargs

    def form_valid(self, form):
        """Handle valid form submission."""
        form.instance.title = form.cleaned_data['title']
        form.instance.review_notes = form.cleaned_data['review_notes']
        form.instance.save()
        return super().form_valid(form)

    def get_success_url(self):
        """Return the success URL with the pk of the form instance."""
        item = get_object_or_404(CollectionItem, pk=self.kwargs['pk'])
        return reverse('twf:collections_view', kwargs={'pk': item.collection.pk})

    def get_context_data(self, **kwargs):
        """Add additional context data if needed."""
        context = super().get_context_data(**kwargs)
        context['page_title'] = self.page_title
        return context


class TWFCollectionsCreateView(FormView, TWFCollectionsView):
    """ View for creating a new collection. """

    template_name = 'twf/collections/collections_create.html'
    page_title = 'Create New Collection'
    form_class = CollectionCreateForm
    success_url = reverse_lazy('twf:collections')

    def form_valid(self, form):
        """Save the form and redirect to the success URL."""
        # Save the form
        self.object = form.save(commit=False)
        self.object.project = self.get_project()
        self.object.save(current_user=self.request.user)

        # Create collection items according to the creation routine
        routine = form.cleaned_data['creation_routine']
        structure_tag_filter = form.cleaned_data['structure_tag_filter']
        structure_tag_filter_list = structure_tag_filter.split(',')
        skip_empty_types = form.cleaned_data['skip_empty_types']

        if routine == 'manual':
           messages.success(self.request, 'Collection has been created successfully. '
                                          'You now can items to the collection.')
        elif routine == 'an_item_per_document':
            all_documents = Document.get_active_documents(self.get_project())
            for doc in all_documents:
                item = CollectionItem(document=doc, collection=self.object, document_configuration={'annotations': []})
                item.title = f'Item for {doc.document_id}'
                for page in doc.get_active_pages():
                    fill_collection_item(item, page, skip_empty_types, structure_tag_filter_list)
                item.save(current_user=self.request.user)
            messages.success(self.request, 'Collection has been created successfully. '
                                           'An item has been created for each document.')
        elif routine == 'an_item_per_page':
            all_documents = Document.get_active_documents(self.get_project())
            for doc in all_documents:
                for page in doc.get_active_pages():
                    item = CollectionItem(document=doc, collection=self.object, document_configuration={'annotations': []})
                    item.title = f'Item in {doc.document_id} - Page {page.tk_page_number}'
                    fill_collection_item(item, page, skip_empty_types, structure_tag_filter_list)
                    item.save(current_user=self.request.user)
            messages.success(self.request, 'Collection has been created successfully. '
                                           'An item has been created for each page.')
        elif routine == 'structure_tag_based':
            all_documents = Document.get_active_documents(self.get_project())
            structure_tags = []
            for doc in all_documents:
                for page in doc.get_active_pages():
                    annotations = page.get_annotations()
                    for annotation in annotations:
                        cleaned_annotation = clean_annotation(annotation)
                        if cleaned_annotation['type'] not in structure_tags:
                            structure_tags.append(cleaned_annotation['type'])

            for tag in structure_tags:
                item = CollectionItem(collection=self.object, document_configuration={'annotations': []})
                item.title = f'Item for structure tag: {tag}'
                for doc in all_documents:
                    for page in doc.get_active_pages():
                        annotations = page.get_annotations()
                        for annotation in annotations:
                            cleaned_annotation = clean_annotation(annotation)
                            if cleaned_annotation['type'] == tag:
                                item.document_configuration['annotations'].append(cleaned_annotation)

                item.save(current_user=self.request.user)
            messages.success(self.request, 'Collection has been created successfully. '
                                           'An item has been created for each structure tag.')


        # Redirect to the success URL
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        """Get the context data for the view."""
        context = super().get_context_data(**kwargs)
        return context


class TWFCollectionsDetailView(SingleTableView, FilterView, TWFCollectionsView):
    """ View for the collection detail page. """

    template_name = "twf/collections/collection_view.html"
    page_title = 'View Collection'
    table_class = CollectionItemTable
    filterset_class = CollectionItemFilter
    paginate_by = 10
    model = CollectionItem
    strict = False  # Don't enforce form validation for filters

    def get_queryset(self):
        """Get the queryset for the view."""
        queryset = CollectionItem.objects.filter(collection_id=self.kwargs.get("pk"))
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset)
        return self.filterset.qs
    
    def get(self, request, *args, **kwargs):
        """Handle GET requests with proper filter handling."""
        # Set up initial queryset
        queryset = CollectionItem.objects.filter(collection_id=self.kwargs.get("pk"))
        
        # Initialize the filter
        self.filterset = self.filterset_class(
            request.GET or None,
            queryset=queryset
        )
        
        # Set object_list either to all items or filtered items
        if request.GET and self.filterset.is_bound:
            self.object_list = self.filterset.qs
        else:
            self.object_list = queryset
            
        # Get context and render response
        context = self.get_context_data()
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        """Get the context data for the view."""
        context = super().get_context_data(**kwargs)
        context['collection'] = Collection.objects.get(pk=self.kwargs.get('pk'))
        context['filter'] = self.filterset
        return context


class TWFCollectionsAddDocumentView(FormView, TWFCollectionsView):
    """ View for adding a document to a collection. """

    template_name = 'twf/collections/collections_add_doc.html'
    page_title = 'Add Document To Collection'
    form_class = CollectionAddDocumentForm
    success_url = reverse_lazy('twf:collections')

    def form_valid(self, form):
        """Save the form and redirect to the success URL."""
        # Save the form
        doc = form.cleaned_data['document']
        collection = Collection.objects.get(pk=self.kwargs.get('pk'))
        collection_item = CollectionItem(document=doc, collection=collection)
        collection_item.save(current_user=self.request.user)

        # Add a success message
        messages.success(self.request, 'Document has been added to the collection successfully.')

        # Redirect to the success URL
        return super().form_valid(form)

    def get_form_kwargs(self):
        """Get the form keyword arguments."""
        kwargs = super().get_form_kwargs()
        # Add your custom argument here
        kwargs['collection'] = Collection.objects.get(pk=self.kwargs.get('pk'))
        return kwargs

    def get_context_data(self, **kwargs):
        """Get the context data for the view."""
        context = super().get_context_data(**kwargs)
        return context


class TWFCollectionsReviewView(FormView, TWFCollectionsView):
    """View for naming documents."""
    template_name = 'twf/collections/review_collections.html'
    page_title = 'Review Collections'
    form_class = CollectionItemReviewForm
    next_item = None
    workflow = None
    workflow_active = False

    def setup(self, request, *args, **kwargs):
        """Setup method to initialize workflow and next item."""
        super().setup(request, *args, **kwargs)

        self.workflow = Workflow.objects.filter(project=self.get_project(), workflow_type="review_collection",
                                                user=self.request.user, status='started').order_by('created_at').first()
        if self.workflow:
            self.workflow_active = True
            self.next_item = self.workflow.get_next_item()


    def get_form_kwargs(self):
        """Pass instance to the form."""
        kwargs = super().get_form_kwargs()
        if self.next_item:
            kwargs['instance'] = get_object_or_404(CollectionItem, pk=self.next_item.pk)
        return kwargs

    def form_valid(self, form):
        """Handle valid form submission."""
        action_r = self.request.POST.get('submit-r')
        action_f = self.request.POST.get('submit-f')
        action_d = self.request.POST.get('submit-d')
        action_u = self.request.POST.get('submit-u')

        if action_d:
            logger.info("Deleting collection item %s", self.next_item)
            if check_permission(self.request.user, 'collection.manage', self.next_item.id):
                self.next_item.delete()
                messages.success(self.request, 'Collection item has been deleted successfully.')
            else:
                messages.error(self.request, 'You do not have permission to delete this collection item.')
        elif action_r or action_f:
            logger.info("Updating collection item and continuing workflow: %s", self.next_item)
            self.next_item.title = form.cleaned_data['title']
            self.next_item.review_notes = form.cleaned_data['review_notes']

            # Save custom field data if workflow has custom fields
            custom_fields = self.workflow.get_custom_fields()
            if custom_fields:
                workflow_data = {}
                for field_name in custom_fields.keys():
                    field_value = self.request.POST.get(field_name)
                    if field_value:
                        workflow_data[field_name] = field_value

                if workflow_data:
                    # Store in collection item's metadata or document_configuration
                    if 'workflow_review' not in self.next_item.document_configuration:
                        self.next_item.document_configuration['workflow_review'] = {}
                    self.next_item.document_configuration['workflow_review'].update(workflow_data)

            if action_r:
                self.next_item.status = 'reviewed'
            if action_f:
                self.next_item.status = 'faulty'
            self.next_item.save()

            if self.workflow.has_more_items():
                self.workflow.advance()
            else:
                self.workflow.finish()
        elif action_u:
            logger.info("Updating collection item: %s", self.next_item)
            logger.debug("New title: %s", form.cleaned_data['title'])
            logger.debug("New review notes: %s", form.cleaned_data['review_notes'])
            self.next_item.title = form.cleaned_data['title']
            self.next_item.review_notes = form.cleaned_data['review_notes']
            self.next_item.save()
            messages.success(self.request, 'Collection item has been updated successfully.')

        return super().form_valid(form)

    def get_success_url(self):
        """Return the success URL with the pk of the form instance."""
        return reverse('twf:collections_review')

    def get_context_data(self, **kwargs):
        """Add additional context data if needed."""
        context = super().get_context_data(**kwargs)
        context['page_title'] = self.page_title

        context['collections'] = Collection.objects.filter(project=self.get_project())

        if not self.workflow_active:
            context['has_active_workflow'] = False
            # Still provide workflow definition for the start page
            if self.workflow:
                context['workflow_definition'] = self.workflow.get_workflow_definition()
            else:
                context['workflow_definition'] = self.get_project().get_workflow_definition('review_collection')
            context['workflow_instructions'] = ''
            context['custom_fields'] = {}
            return context

        context['has_active_workflow'] = True

        # Fetch the next document
        context['workflow'] = self.workflow
        context['collection_item'] = self.next_item

        # Add workflow configuration
        context['workflow_definition'] = self.workflow.get_workflow_definition()
        context['workflow_instructions'] = self.workflow.get_instructions()
        context['custom_fields'] = self.workflow.get_custom_fields()

        return context

    """def post(self, request, *args, **kwargs):
        
        workflow = Workflow.objects.filter(project=self.get_project(), workflow_type="review_collection",
                                           user=self.request.user, status='started').order_by('created_at').first()

        if not workflow:
            messages.error(request, "No active workflow found.")
            return redirect('twf:collections_review')  #

        collection_item_id = request.POST.get('document_id')
        action = request.POST.get('action')

        if collection_item_id and action:
            collection_item = CollectionItem.objects.filter(id=collection_item_id).first()

            if collection_item:
                # Mark the document based on user action
                if action == 'set_reviewed':
                    collection_item.status = 'reviewed'
                elif action == 'set_parked':
                    collection_item.is_parked = True
                elif action == 'set_faulty':
                    collection_item.status = 'faulty'

                collection_item.save(current_user=request.user)

                # Log the action in the workflow if needed
                if workflow.has_more_items():
                    workflow.advance()
                else:
                    workflow.finish()

        return redirect('twf:collections_review')"""


