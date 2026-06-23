from django.contrib import messages
from django.shortcuts import redirect

from twf.models import Workflow, Document
from twf.tasks.instant_tasks import start_related_task
from twf.views.views_base import TWFView


def create_document_workflow(project, user, item_count=None):
    """
    Create a new workflow for reviewing documents and pre-select the documents.

    Parameters
    ----------
    project : Project
        The project to create the workflow for
    user : User
        The user creating the workflow
    item_count : int, optional
        Number of documents to review. If None, uses configured batch size from workflow definition.
    """
    # Use configured batch size if item_count not provided
    if item_count is None:
        workflow_def = project.get_workflow_definition('review_documents')
        item_count = workflow_def.get('batch_size', 5)

    # Get available document IDs that are not reserved and not reviewed
    available_document_ids = list(
        Document.objects.filter(project=project, is_reserved=False, status='open')
        .values_list('id', flat=True)[:item_count]
    )

    if len(available_document_ids) == 0:
        return False

    if len(available_document_ids) < item_count:
        item_count = len(available_document_ids)

    # Mark the documents as reserved
    Document.objects.filter(id__in=available_document_ids).update(is_reserved=True)

    task = start_related_task(project, user,
                              "Review Documents",
                              "Review documents in the project.",
                              "The user has started a workflow to review documents.")

    # Create the workflow
    workflow = Workflow.objects.create(
        project=project,
        user=user,
        workflow_type='review_documents',
        item_count=item_count,
        related_task=task
    )

    # Assign documents to the workflow
    workflow.assigned_document_items.set(Document.objects.filter(id__in=available_document_ids))

    return True



def start_review_document_workflow(request):
    """Start a document review workflow using configured batch size."""
    project = TWFView.s_get_project(request)
    user = request.user

    # Use None to let create_document_workflow use the configured batch size
    started_workflow = create_document_workflow(project, user, item_count=None)
    if not started_workflow:
        messages.error(request, "No documents available for review.")
        return redirect('twf:documents_review')

    return redirect('twf:documents_review')