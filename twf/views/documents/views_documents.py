"""Views for the project documents."""
import logging
import re

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Avg, Q
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import FormView
from django_filters.views import FilterView
from django_tables2 import SingleTableView

from twf.forms.filters.filters import DocumentFilter
from twf.forms.documents.documents_forms import DocumentSearchForm
from twf.models import Document, Workflow
from twf.tables.tables_document import DocumentTable
from twf.views.views_base import TWFView

# Create a logger for this module
logger = logging.getLogger(__name__)


class TWFDocumentView(LoginRequiredMixin, TWFView):
    """Base view for all project views."""
    template_name = None

    def get_sub_navigation(self):
        """Get the sub navigation."""
        sub_nav = [
            {
                'name': 'Your Documents',
                'options': [
                    {'url': reverse('twf:documents_overview'), 'value': 'Overview'},
                    {'url': reverse('twf:documents_browse'),
                     'value': 'Browse Documents', 'permission': 'document.view'},
                    {'url': reverse('twf:documents_search'),
                     'value': 'Search Documents', 'permission': 'document.view'},
                ]
            },
            {
                'name': 'Document Batch',
                'options': self.get_ai_batch_options()
            },
            {
                'name': 'Manual Workflows',
                'options': [
                    {'url': reverse('twf:documents_review'),
                     'value': 'Review Documents', 'permission': 'document.edit'},
                ]
            },

        ]
        return sub_nav

    def get_navigation_index(self):
        """Get the navigation index."""
        return 2

    def get_ai_batch_options(self):
        """
        Get the AI batch options.

        Returns simplified navigation with unified AI Batch processing.
        The AI Batch view provides a dropdown to select from available providers.
        """
        options = [
            {'url': reverse('twf:documents_batch_ai_unified'),
             'value': 'AI Batch Processing',
             'permission': 'ai.manage'}
        ]

        return options

    def get_context_data(self, **kwargs):
        """Get the context data for the view."""
        context = super().get_context_data(**kwargs)
        return context


class TWFDocumentsOverviewView(TWFDocumentView):
    """View for the project documents overview."""
    template_name = 'twf/documents/overview.html'
    page_title = 'Documents'
    show_context_help = False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        project = self.get_project()
        documents = project.documents.all()
        
        # Document statistics
        total_documents = documents.count()
        total_pages = sum(doc.pages.count() for doc in documents)
        
        # Average pages per document
        avg_pages = documents.annotate(num_pages=Count('pages')).aggregate(Avg('num_pages'))
        
        # Status counts
        completed_documents = documents.filter(status='completed').count()
        in_progress_documents = documents.filter(status='in_progress').count()
        parked_documents = documents.filter(is_parked=True).count()
        
        # Excluded documents/pages statistics (Transkribus 'Exclude' label)
        ignored_pages = sum(doc.pages.filter(is_ignored=True).count() for doc in documents)
        ignored_percentage = (ignored_pages / total_pages * 100) if total_pages > 0 else 0
        ignored_documents_count = documents.filter(is_ignored=True).count()
        ignored_documents_percentage = (ignored_documents_count / total_documents * 100) if total_documents > 0 else 0

        # Gather metadata keys from all documents
        metadata_keys = set()
        for document in documents:
            if isinstance(document.metadata, dict):
                metadata_keys.update(document.metadata.keys())
        
        # Tag statistics
        from twf.models import PageTag
        project_tags = PageTag.objects.filter(page__document__project=project)
        total_tags = project_tags.count()
        open_tags = project_tags.filter(is_parked=False).count()
        resolved_tags = project_tags.filter(is_parked=True).count()
        
        # Calculate tags per page
        tags_per_page = total_tags / total_pages if total_pages > 0 else 0
        
        # Get tag types distribution
        tag_types = project_tags.values('variation_type').annotate(count=Count('id')).order_by('-count')[:5]
        
        # Get a sample document for preview (most recently created)
        sample_document = documents.order_by('-created_at').first()
        
        # Get recent documents (5 most recently modified)
        recent_documents = documents.order_by('-modified_at')[:5]
        
        # Create document statistics dictionary
        doc_stats = {
            'total_documents': total_documents,
            'total_pages': total_pages,
            'average_pages_per_document': avg_pages,
            'completed_documents': completed_documents,
            'in_progress_documents': in_progress_documents,
            'parked_documents': parked_documents,
            'ignored_pages': ignored_pages,
            'ignored_percentage': ignored_percentage,
            'ignored_documents': ignored_documents_count,
            'ignored_documents_percentage': ignored_documents_percentage,
        }
        
        # Create tag statistics dictionary
        tag_stats = {
            'total_tags': total_tags,
            'open_tags': open_tags,
            'resolved_tags': resolved_tags,
            'tags_per_page': tags_per_page,
            'tag_types': tag_types,
        }

        # Get Transkribus statistics
        from twf.utils.project_statistics import get_transkribus_statistics
        transkribus_stats = get_transkribus_statistics(project)

        context.update({
            'doc_stats': doc_stats,
            'tag_stats': tag_stats,
            'transkribus_stats': transkribus_stats,
            'metadata_keys': sorted(metadata_keys),
            'sample_document': sample_document,
            'recent_documents': recent_documents,
        })

        return context


class TWFDocumentsBrowseView(SingleTableView, FilterView, TWFDocumentView):
    """View for displaying project documents."""
    template_name = 'twf/documents/documents.html'
    page_title = 'Browse Documents'
    table_class = DocumentTable
    filterset_class = DocumentFilter
    paginate_by = 10
    model = Document
    strict = False

    def get_queryset(self):
        """Get the queryset for the view.

        By default, excludes documents with is_ignored=True (Transkribus 'Exclude' label).
        Users can see excluded documents by using the 'Show excluded documents only' filter.
        """
        # Get all documents for the current project
        queryset = Document.objects.filter(project_id=self.request.session.get('project_id'))

        # By default, exclude ignored documents unless explicitly filtering for them
        if not self.request.GET.get('is_ignored'):
            queryset = queryset.filter(is_ignored=False)

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
            
        # Log filter results for debugging
        logger.debug(f"Initial document queryset count: {queryset.count()}")
        if hasattr(self, 'filterset') and self.filterset:
            logger.debug(f"Filtered document queryset count: {self.filterset.qs.count()}")
        
        # Get context and render response
        context = self.get_context_data()
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        """Get the context data for the view."""
        context = super().get_context_data(**kwargs)
        context['page_title'] = self.page_title
        context['filter'] = self.filterset
        
        # Add document statistics
        project = self.get_project()
        all_documents = project.documents.all()
        
        # Document statistics for the header
        stats = {
            'total': all_documents.count(),
            'active': all_documents.filter(is_ignored=False).count(),
            'excluded': all_documents.filter(is_ignored=True).count(),
            'parked': all_documents.filter(is_parked=True).count(),
            'reviewed': all_documents.filter(status='reviewed').count()
        }
        context['document_stats'] = stats
        
        return context


class TWFDocumentsSearchView(FormView, TWFDocumentView):
    """View for searching documents with simplified interface."""
    template_name = 'twf/documents/search_documents.html'
    page_title = 'Search Documents'
    form_class = DocumentSearchForm
    success_url = reverse_lazy('twf:documents_search')

    def form_valid(self, form):
        """Handle valid form submission."""
        # Get search results
        results = self.search_documents(form.cleaned_data)
        
        # Add results to context and render the same page
        context = self.get_context_data(form=form, results=results)
        
        # Add search term to context for highlighting if needed
        search_term = form.cleaned_data.get('search_term', '').strip()
        if search_term:
            context['search_term'] = search_term
            
        return self.render_to_response(context)
    
    def form_invalid(self, form):
        """Handle invalid form submission."""
        # Log form errors for debugging
        logger.debug(f"Form errors: {form.errors}")
        context = self.get_context_data(form=form)
        context['form_errors'] = form.errors
        return self.render_to_response(context)

    def search_documents(self, cleaned_data):
        import re
        project = self.get_project()
        queryset = Document.objects.filter(project=project).prefetch_related('pages', 'pages__tags')
        match_reasons = {}

        # Filter by title
        title = cleaned_data.get("title")
        if title:
            queryset = queryset.filter(title__icontains=title)
            for doc in queryset:
                if title.lower() in (doc.title or "").lower():
                    match_reasons.setdefault(doc.id, []).append(
                        {
                            "type": "info",
                            "text": f'Title contains “{title}”'
                        }
                    )

        # Filter by document ID
        doc_id = cleaned_data.get("document_id")
        if doc_id:
            queryset = queryset.filter(document_id__icontains=doc_id)
            for doc in queryset:
                if doc_id.lower() in doc.document_id.lower():
                    match_reasons.setdefault(doc.id, []).append(
                        {
                            "type": "info",
                            "text": f'ID contains “{doc_id}”'
                        }
                    )

        # Filter by status and parked
        statuses = cleaned_data.get("status")
        if statuses:
            status_q = Q()
            for s in statuses:
                if s == "parked":
                    status_q |= Q(is_parked=True)
                else:
                    status_q |= Q(status=s)
            queryset = queryset.filter(status_q)

        # Dictionary Entry filtering
        has_entries = cleaned_data.get("has_entries")
        if has_entries:
            queryset = queryset.filter(pages__tags__dictionary_entry__in=has_entries).distinct()
            for doc in queryset:
                matched_entries = {tag.dictionary_entry for page in doc.pages.all() for tag in page.tags.all()
                                   if tag.dictionary_entry in has_entries}
                for entry in matched_entries:
                    match_reasons.setdefault(doc.id, []).append(f'Referenced entry: “{entry.label}”')

        # Tag text filtering
        has_tags = cleaned_data.get("has_tags", "").strip()
        if has_tags:
            queryset = queryset.filter(pages__tags__variation__icontains=has_tags).distinct()
            for doc in queryset:
                for page in doc.pages.all():
                    for tag in page.tags.all():
                        if has_tags.lower() in tag.variation.lower():
                            match_reasons.setdefault(doc.id, []).append(
                                {
                                    "type": "info",
                                    "text": f'Tag text: “{tag.variation}”'
                                }
                            )
                            break

        # Search in document text
        document_text = cleaned_data.get("document_text", "").strip()
        use_regex = cleaned_data.get("use_regex_for_text")

        if document_text:
            matching_ids = []

            for doc in queryset:
                page_matches = []
                for page in doc.pages.all():
                    page_text = page.get_text()
                    match_count = 0
                    found_snippet = None

                    try:
                        if use_regex:
                            matches = list(re.finditer(document_text, page_text, flags=re.IGNORECASE))
                            match_count = len(matches)
                            if matches:
                                found_snippet = self.get_highlighted_snippet(page_text, document_text, use_regex)
                        else:
                            lowered_text = page_text.lower()
                            lowered_term = document_text.lower()
                            match_count = lowered_text.count(lowered_term)

                            if match_count > 0:
                                found_snippet = self.get_highlighted_snippet(page_text, document_text, use_regex)
                    except re.error:
                        messages.warning(self.request, "Invalid regex pattern.")
                        continue

                    if match_count > 0:
                        page_matches.append((page.tk_page_number, match_count))
                        if found_snippet:
                            if found_snippet:
                                match_reasons.setdefault(doc.id, []).append({
                                    "type": "snippet",
                                    "text": found_snippet,
                                    "page": page.tk_page_number
                                })

                if page_matches:
                    matching_ids.append(doc.id)
                    total_matches = sum(c for _, c in page_matches)
                    page_str = ", ".join(f"p{num} ({cnt})" for num, cnt in page_matches)
                    match_reasons.setdefault(doc.id, []).append({
                        "type": "info",
                        "text": f'Matched on {len(page_matches)} page(s): {page_str}, total matches: {total_matches}'
                    })

            queryset = queryset.filter(id__in=matching_ids)

        for i in range(5):
            doc_or_page = cleaned_data.get(f"type_field_{i}")
            obj = cleaned_data.get(f"what_field_{i}")
            key = cleaned_data.get(f"key_field_{i}")
            op = cleaned_data.get(f"has_field_{i}")
            val = cleaned_data.get(f"query_field_{i}", "").strip()

            if not (doc_or_page and obj and key and val):
                continue

            target_path = f"{obj}.{key}"

            def matches(value):
                try:
                    if value is None:
                        return False
                    if op == "contains":
                        return val.lower() in str(value).lower()
                    elif op == "not_contain":
                        return val.lower() not in str(value).lower()
                    elif op == "exact":
                        return str(value) == str(val)
                    elif op == "regex":
                        return re.search(val, str(value))
                    else:
                        return False
                except Exception as e:
                    messages.warning(self.request, f"Error matching {target_path}: {e}")
                    return False

            matching_ids = set()
            if doc_or_page == "document":
                for doc in queryset:
                    value = doc.metadata.get(obj, {}).get(key)
                    if matches(value):
                        matching_ids.add(doc.id)
                        match_reasons.setdefault(doc.id, []).append(
                            {"type": "info", "text": f'{obj}.{key} matched "{val}"'}
                        )
            elif doc_or_page == "page":
                for doc in queryset:
                    found = False
                    for page in doc.pages.all():
                        value = page.metadata.get(obj, {}).get(key)
                        if matches(value):
                            found = True
                            break
                    if found:
                        matching_ids.add(doc.id)
                        match_reasons.setdefault(doc.id, []).append(
                            {"type": "info", "text": f'Page {obj}.{key} matched "{val}"'}
                        )

            queryset = queryset.filter(id__in=matching_ids)

        # Internal Metadata Filters
        if cleaned_data.get("created_by"):
            queryset = queryset.filter(created_by=cleaned_data["created_by"])
            for doc in queryset:
                if doc.created_by == cleaned_data["created_by"]:
                    match_reasons.setdefault(doc.id, []).append(
                        {
                            "type": "info",
                            "text": f'Created by: {doc.created_by}'
                        }
                    )

        if cleaned_data.get("modified_by"):
            queryset = queryset.filter(modified_by=cleaned_data["modified_by"])
            for doc in queryset:
                if doc.modified_by == cleaned_data["modified_by"]:
                    match_reasons.setdefault(doc.id, []).append(
                        {
                            "type": "info",
                            "text": f'Modified by: {doc.modified_by}'
                        }
                    )

        if cleaned_data.get("created_from"):
            queryset = queryset.filter(created_at__gte=cleaned_data["created_from"])

        if cleaned_data.get("created_to"):
            queryset = queryset.filter(created_at__lte=cleaned_data["created_to"])

        if cleaned_data.get("modified_from"):
            queryset = queryset.filter(modified_at__gte=cleaned_data["modified_from"])

        if cleaned_data.get("modified_to"):
            queryset = queryset.filter(modified_at__lte=cleaned_data["modified_to"])

        # Return both results and match reasons
        self.match_reasons = match_reasons
        return queryset

    def get_context_data(self, **kwargs):
        """Get the context data for the view."""
        context = super().get_context_data(**kwargs)
        
        # Add search results if available
        if 'results' in kwargs:
            results = kwargs['results']
            context['results'] = results
            context['results_count'] = results.count()
            
            # Add search parameters for highlighting
            form = kwargs.get('form')
            if form and hasattr(form, 'cleaned_data'):
                context['search_term'] = form.cleaned_data.get('search_term', '')
                context['search_type'] = form.cleaned_data.get('search_type', 'all')
            
            # Add document statistics for the results
            stats = {
                'total': results.count(),
                'with_pages': sum(1 for doc in results if doc.pages.exists()),
                'with_tags': sum(1 for doc in results if any(page.tags.exists() for page in doc.pages.all())),
                'ignored': sum(1 for doc in results if doc.is_parked),
                'open': sum(1 for doc in results if doc.status == 'open'),
                'reviewed': sum(1 for doc in results if doc.status == 'reviewed'),
                'needs_work': sum(1 for doc in results if doc.status == 'needs_tk_work'),
                'irrelevant': sum(1 for doc in results if doc.status == 'irrelevant'),
            }
            context['result_stats'] = stats
            
        # Add document statistics
        all_documents = Document.objects.filter(project=self.get_project())
        context['document_stats'] = {
            'total': all_documents.count(),
            'active': all_documents.filter(is_ignored=False).count(),
            'excluded': all_documents.filter(is_ignored=True).count(),
            'parked': all_documents.filter(is_parked=True).count(),
            'reviewed': all_documents.filter(status='reviewed').count()
        }
            
        # Track if this is a search submission (for template display)
        is_search = False
        if self.request.method == 'POST' and self.request.POST.get('search_submitted') == '1':
            is_search = True

            
        context['search_submitted'] = is_search
        context['match_reasons'] = getattr(self, 'match_reasons', {})
        
        return context

    @staticmethod
    def get_highlighted_snippet(text, pattern, use_regex=False, context_chars=30):
        import re

        try:
            if use_regex:
                matches = list(re.finditer(pattern, text, flags=re.IGNORECASE))
                if not matches:
                    return None

                match = matches[0]
                start = max(match.start() - context_chars, 0)
                end = min(match.end() + context_chars, len(text))
                snippet = text[start:end].strip()

                highlighted = re.sub(
                    f"({pattern})", r"<mark>\1</mark>", snippet, flags=re.IGNORECASE
                )
                return highlighted

            else:
                index = text.lower().find(pattern.lower())
                if index == -1:
                    return None

                start = max(index - context_chars, 0)
                end = index + len(pattern) + context_chars
                snippet = text[start:end].strip()

                pattern_escaped = re.escape(pattern)
                highlighted = re.sub(
                    f"({pattern_escaped})", r"<mark>\1</mark>", snippet, flags=re.IGNORECASE
                )
                return highlighted
        except re.error:
            return None


class TWFDocumentDetailView(TWFDocumentView):
    """View for displaying a document."""
    template_name = 'twf/documents/document.html'
    page_title = 'Document Detail'
    navigation_anchor = reverse_lazy("twf:documents_browse")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        document = Document.objects.get(pk=self.kwargs.get('pk'))
        context["document"] = document

        # Count excluded/ignored pages
        all_pages = document.pages.all()
        excluded_pages = [p for p in all_pages if p.is_ignored]
        context["excluded_pages"] = excluded_pages
        context["excluded_count"] = len(excluded_pages)

        # Get previous and next documents for navigation
        project = self.get_project()
        documents = Document.objects.filter(project=project).order_by('document_id')

        # Find current document's position
        doc_list = list(documents.values_list('pk', flat=True))
        try:
            current_index = doc_list.index(document.pk)

            # Get previous document
            if current_index > 0:
                context['previous_document_id'] = doc_list[current_index - 1]
            else:
                context['previous_document_id'] = None

            # Get next document
            if current_index < len(doc_list) - 1:
                context['next_document_id'] = doc_list[current_index + 1]
            else:
                context['next_document_id'] = None
        except ValueError:
            # Document not in list (shouldn't happen)
            context['previous_document_id'] = None
            context['next_document_id'] = None

        return context

    def get_breadcrumbs(self):
        """Get the breadcrumbs for the view."""
        breadcrumbs = super().get_breadcrumbs()
        breadcrumbs.insert(-1, {'url': reverse('twf:documents_browse'), 'value': 'Browse Documents'})
        return breadcrumbs


class TWFDocumentNameView(TWFDocumentView):
    """View for naming documents."""
    template_name = 'twf/documents/name_documents.html'
    page_title = 'Name Documents'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class TWFDocumentReviewView(TWFDocumentView):
    """View for naming documents."""
    template_name = 'twf/documents/review_documents.html'
    page_title = 'Review Documents'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Fetch the current workflow
        workflow = Workflow.objects.filter(project=self.get_project(), workflow_type="review_documents",
                                           user=self.request.user, status='started').order_by('created_at').first()

        if not workflow:
            context['has_active_workflow'] = False
            # Still provide workflow definition for the start page
            context['workflow_definition'] = self.get_project().get_workflow_definition('review_documents')
            context['workflow_instructions'] = ''
            context['custom_fields'] = {}
            return context

        context['has_active_workflow'] = True

        # Fetch the next document
        next_document = workflow.get_next_item()
        context['workflow'] = workflow
        context['document'] = next_document

        # Add workflow configuration
        context['workflow_definition'] = workflow.get_workflow_definition()
        context['workflow_instructions'] = workflow.get_instructions()
        context['custom_fields'] = workflow.get_custom_fields()

        # Split pages into actual and excluded for preview
        if next_document:
            all_pages = next_document.pages.all()
            context['actual_pages'] = [p for p in all_pages if not p.is_ignored]
            context['excluded_pages'] = [p for p in all_pages if p.is_ignored]
            context['workflow_remarks'] = next_document.workflow_remarks
        else:
            context['workflow_remarks'] = ''

        return context

    def post(self, request, *args, **kwargs):
        workflow = Workflow.objects.filter(project=self.get_project(), workflow_type="review_documents",
                                           user=self.request.user, status='started').order_by('created_at').first()

        if not workflow:
            messages.error(request, "No active workflow found.")
            return redirect('twf:documents_review')

        document_id = request.POST.get('document_id')
        action = request.POST.get('action')

        if document_id and action:
            document = Document.objects.filter(id=document_id).first()

            if document:
                # Save custom field data to document.metadata
                custom_fields = workflow.get_custom_fields()
                if custom_fields:
                    workflow_data = {}
                    for field_name in custom_fields.keys():
                        field_value = request.POST.get(field_name)
                        if field_value:
                            workflow_data[field_name] = field_value

                    if workflow_data:
                        if 'workflow_review' not in document.metadata:
                            document.metadata['workflow_review'] = {}
                        document.metadata['workflow_review'].update(workflow_data)

                # Save workflow remarks
                workflow_remarks = request.POST.get('workflow_remarks', '').strip()
                if workflow_remarks:
                    document.workflow_remarks = workflow_remarks

                # Mark the document based on user action
                if action == 'set_reviewed':
                    document.status = 'reviewed'
                elif action == 'set_parked':
                    document.is_parked = True
                elif action == 'set_irrelevant':
                    # Mark as needs TK work (to set Exclude label in Transkribus)
                    document.status = 'needs_tk_work'
                    # Append to workflow_remarks if not already mentioned
                    irrelevant_note = "Marked as irrelevant - needs Exclude label in Transkribus"
                    if not workflow_remarks:
                        document.workflow_remarks = irrelevant_note
                    elif "irrelevant" not in workflow_remarks.lower():
                        document.workflow_remarks += f"\n[{irrelevant_note}]"
                elif action == 'set_needs_work':
                    document.status = 'needs_tk_work'

                document.save()

                # Log the action in the workflow if needed
                if workflow.has_more_items():
                    workflow.advance()
                else:
                    workflow.finish()

        return redirect('twf:documents_review')
