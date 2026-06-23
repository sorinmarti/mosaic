from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404

from twf.models import Workflow, Document, CollectionItem, Collection
from twf.tasks.instant_tasks import start_related_task
from twf.views.views_base import TWFView


def create_collection_workflow(project, user, collection, item_count=None):
    """
    Create a new workflow for reviewing collection items and pre-select the items.

    Parameters
    ----------
    project : Project
        The project to create the workflow for
    user : User
        The user creating the workflow
    collection : Collection
        The collection to review items from
    item_count : int, optional
        Number of items to review. If None, uses configured batch size from workflow definition.
    """
    # Use configured batch size if item_count not provided
    if item_count is None:
        workflow_def = project.get_workflow_definition('review_collection')
        item_count = workflow_def.get('batch_size', 5)

    # Get available collection item IDs that are not reserved and not reviewed
    available_collection_item_ids = list(
        CollectionItem.objects.filter(collection=collection,
                                      is_reserved=False, status='open')
        .values_list('id', flat=True)[:item_count]
    )

    if len(available_collection_item_ids) == 0:
        return False

    if len(available_collection_item_ids) < item_count:
        item_count = len(available_collection_item_ids)

    # Mark the documents as reserved
    CollectionItem.objects.filter(id__in=available_collection_item_ids).update(is_reserved=True)

    task = start_related_task(project, user,
                              "Review Collection",
                              "Review collection items a collection in the project.",
                              "The user has started a workflow to review documents.")

    # Create the workflow
    workflow = Workflow.objects.create(
        project=project,
        collection=collection,
        user=user,
        workflow_type='review_collection',
        item_count=item_count,
        related_task=task
    )

    # Assign documents to the workflow
    workflow.assigned_collection_items.set(CollectionItem.objects.filter(id__in=available_collection_item_ids))

    return True



def start_review_collection_workflow(request, collection_id):
    """Start a collection review workflow using configured batch size."""
    project = TWFView.s_get_project(request)
    user = request.user
    collection = Collection.objects.get(pk=collection_id)

    # Use None to let create_collection_workflow use the configured batch size
    started_workflow = create_collection_workflow(project, user, collection, item_count=None)
    if not started_workflow:
        messages.error(request, "No items available for review.")
        return redirect('twf:collections_review')

    return redirect('twf:collections_review')