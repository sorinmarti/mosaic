"""This module contains functions to gather statistics for a project."""
from collections import defaultdict

from django.db.models import Avg, Count
from twf.models import Document, Page, PageTag, Dictionary, Collection


def get_document_statistics(project):
    """Get statistics for documents."""

    total_documents = project.documents.count()
    total_pages = Page.objects.filter(document__project=project).count()
    average_pages_per_document = (Page.objects.filter(document__project=project).values('document').
                                  annotate(count=Count('id')).aggregate(Avg('count')))
    ignored_pages = Page.objects.filter(document__project=project, is_ignored=True).count()
    largest_document = (Document.objects.annotate(num_pages=Count('pages'))
                        .filter(project=project).order_by('-num_pages').first())
    smallest_document = (Document.objects.annotate(num_pages=Count('pages'))
                         .filter(project=project).order_by('num_pages').first())

    return {
        'total_documents': total_documents,
        'total_pages': total_pages,
        'ignored_pages': ignored_pages,
        'ignored_percentage': (ignored_pages / total_pages * 100) if total_pages > 0 else 0,
        'average_pages_per_document': average_pages_per_document,
        'largest_document': largest_document,
        'smallest_document': smallest_document
    }


def get_tag_statistics(project):
    """Get statistics for tags."""

    total_tags = PageTag.objects.filter(page__document__project=project).count()
    total_pages = Page.objects.filter(document__project=project).count()
    
    # Calculate tags per page
    tags_per_page = round(total_tags / total_pages, 1) if total_pages > 0 else 0
    
    # Calculate open and resolved tags
    open_tags = PageTag.objects.filter(page__document__project=project, is_parked=False).count()
    resolved_tags = PageTag.objects.filter(page__document__project=project, is_parked=True).count()
    
    # Get tag types distribution
    tag_types = PageTag.objects.filter(page__document__project=project).values('variation_type').annotate(count=Count('id')).order_by('-count')[:5]
    
    return {
        'total_tags': total_tags,
        'tags_per_page': tags_per_page,
        'open_tags': open_tags,
        'resolved_tags': resolved_tags,
        'tag_types': tag_types
    }


def get_dictionary_statistics(project):
    """Get statistics for dictionaries."""

    # Total number of dictionaries
    total_dictionaries = Dictionary.objects.count()

    # Top entries per dictionary type
    top_entries_per_type = defaultdict(list)
    entry_counts = PageTag.objects.filter(
        page__document__project=project
    ).values(
        'dictionary_entry__id',
        'dictionary_entry__label',
        'dictionary_entry__dictionary__type'
    ).annotate(
        count=Count('id')
    ).order_by('dictionary_entry__dictionary__type', '-count')

    # Find the mostly referenced dictionary entry and category
    mostly_referenced_entry = None
    mostly_referenced_category = None
    highest_entry_count = 0
    highest_category_count = 0
    category_counts = defaultdict(int)

    for entry in entry_counts:
        dtype = entry['dictionary_entry__dictionary__type']

        # Add entry to top entries per type (up to 20 per type)
        if len(top_entries_per_type[dtype]) < 20:
            top_entries_per_type[dtype].append(entry)

        # Track the mostly referenced dictionary entry
        if entry['count'] > highest_entry_count:
            highest_entry_count = entry['count']
            mostly_referenced_entry = entry

        # Track the mostly referenced category
        category_counts[dtype] += entry['count']
        if category_counts[dtype] > highest_category_count:
            highest_category_count = category_counts[dtype]
            mostly_referenced_category = dtype

    return {
        'total_dictionaries': total_dictionaries,
        'top_entries_per_type': dict(top_entries_per_type),
        'mostly_referenced_entry': mostly_referenced_entry,
        'mostly_referenced_category': mostly_referenced_category
    }


def get_collection_statistics():
    """Get statistics for collections in a project."""
    # Example: total number of collections
    total_collections = Collection.objects.count()
    return {
        'total_collections': total_collections
    }


def get_import_export_statistics():
    """Get statistics for import/export operations."""
    # Here you can add stats for import/export operations if tracked
    pass


def get_transkribus_statistics(project):
    """
    Get statistics for Transkribus labels and statuses.

    Processes two metadata blocks:
    - metadata['transkribus_api']: Contains labels for documents and pages
    - metadata['transkribus']: Contains page status (in_progress, done, ground_truth, etc.)

    Args:
        project: The project to gather statistics for

    Returns:
        Dictionary containing:
        - page_label_counts: Distribution of page labels (from transkribus_api)
        - page_status_counts: Distribution of page statuses (from transkribus)
        - document_label_counts: Distribution of document labels (from transkribus_api)
        - total_pages_with_labels: Count of pages that have Transkribus API labels
        - total_pages_with_status: Count of pages that have Transkribus status
        - total_documents_with_labels: Count of documents that have Transkribus API labels
    """
    from collections import Counter

    # Initialize counters
    page_label_counter = Counter()
    page_status_counter = Counter()
    document_label_counter = Counter()
    pages_with_labels = 0
    pages_with_status = 0
    documents_with_labels = 0

    # Get all documents in the project
    documents = Document.objects.filter(project=project)

    # Process document-level labels (from transkribus_api)
    for document in documents:
        if not isinstance(document.metadata, dict):
            continue

        transkribus_api_data = document.metadata.get('transkribus_api', {})
        doc_labels = transkribus_api_data.get('labels', [])

        if doc_labels:
            documents_with_labels += 1
            # Count each label
            for label in doc_labels:
                if isinstance(label, dict):
                    label_name = label.get('name', 'Unknown')
                    document_label_counter[label_name] += 1
                elif isinstance(label, str):
                    document_label_counter[label] += 1

    # Process page-level data
    pages = Page.objects.filter(document__project=project)

    for page in pages:
        if not isinstance(page.metadata, dict):
            continue

        # Process labels from transkribus_api
        transkribus_api_data = page.metadata.get('transkribus_api', {})
        page_labels = transkribus_api_data.get('labels', [])

        if page_labels:
            pages_with_labels += 1
            # Count each label
            for label in page_labels:
                if isinstance(label, dict):
                    label_name = label.get('name', 'Unknown')
                    page_label_counter[label_name] += 1
                elif isinstance(label, str):
                    page_label_counter[label] += 1

        # Process status from transkribus metadata
        transkribus_data = page.metadata.get('transkribus', {})
        page_status = transkribus_data.get('status')

        if page_status:
            pages_with_status += 1
            page_status_counter[page_status] += 1

    # Prepare result dictionary
    result = {
        'page_label_counts': dict(page_label_counter.most_common()),
        'page_status_counts': dict(page_status_counter.most_common()),
        'document_label_counts': dict(document_label_counter.most_common()),
        'total_pages_with_labels': pages_with_labels,
        'total_pages_with_status': pages_with_status,
        'total_documents_with_labels': documents_with_labels,
        'total_pages': pages.count(),
        'total_documents': documents.count(),
    }

    # Calculate percentages
    if result['total_pages'] > 0:
        result['pages_with_labels_percentage'] = (pages_with_labels / result['total_pages']) * 100
        result['pages_with_status_percentage'] = (pages_with_status / result['total_pages']) * 100
    else:
        result['pages_with_labels_percentage'] = 0
        result['pages_with_status_percentage'] = 0

    if result['total_documents'] > 0:
        result['documents_with_labels_percentage'] = (
            documents_with_labels / result['total_documents']
        ) * 100
    else:
        result['documents_with_labels_percentage'] = 0

    return result


def gather_statistics():
    """Gather statistics for a project."""
    return {
        'documents': get_document_statistics(),
        'tags': get_tag_statistics(),
        'dictionaries': get_dictionary_statistics(),
        'collections': get_collection_statistics(),
        # Add more sections as needed
    }
