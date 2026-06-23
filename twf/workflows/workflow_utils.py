"""
Workflow Utilities
==================

Shared utilities for workflow management across all workflow types.
"""

from django.contrib import messages
from twf.models import Workflow


def end_workflow(request, project, user, workflow_type, redirect_view_name):
    """
    Generic function to end/cancel a workflow.

    Parameters
    ----------
    request : HttpRequest
        The Django request object
    project : Project
        The project the workflow belongs to
    user : User
        The user who owns the workflow
    workflow_type : str
        The type of workflow to end (e.g., 'review_documents', 'review_tags_grouping')
    redirect_view_name : str
        The name of the view to redirect to after ending

    Returns
    -------
    Workflow or None
        The ended workflow object, or None if no workflow was found
    """
    from django.shortcuts import redirect

    # Find the active workflow
    workflow = (
        Workflow.objects.filter(
            project=project,
            workflow_type=workflow_type,
            user=user,
            status="started",
        )
        .order_by("created_at")
        .first()
    )

    if not workflow:
        messages.warning(request, "No active workflow found to end.")
        return None

    # Mark workflow as ended
    workflow.finish(with_error=False)

    # Unreserve items based on workflow type
    if workflow_type == "review_documents":
        remaining_documents = workflow.assigned_document_items.filter(
            status="open", is_reserved=True
        )
        remaining_documents.update(is_reserved=False)
        item_type = "documents"

    elif workflow_type == "review_collection":
        remaining_items = workflow.assigned_collection_items.filter(
            status="open", is_reserved=True
        )
        remaining_items.update(is_reserved=False)
        item_type = "items"

    elif workflow_type in ["review_tags_grouping", "review_tags_enrichment", "review_tags_dates"]:
        # Unreserve tags
        from twf.models import PageTag
        remaining_tags = PageTag.objects.filter(
            workflows=workflow,
            is_reserved=True
        )
        remaining_tags.update(is_reserved=False)
        item_type = "tags"

    elif workflow_type in ["review_metadata_documents", "review_metadata_pages"]:
        # Metadata workflows don't reserve items, so nothing to unreserve
        item_type = "items"

    elif workflow_type == "review_dictionary_enrichment":
        # Dictionary enrichment workflows reserve dictionary entries
        from twf.models import DictionaryEntry
        if workflow.dictionary:
            remaining_entries = DictionaryEntry.objects.filter(
                dictionary=workflow.dictionary,
                is_reserved=True
            )
            remaining_entries.update(is_reserved=False)
        item_type = "entries"

    else:
        item_type = "items"

    messages.success(
        request,
        f"Workflow ended. Processed {workflow.current_item_index} of {workflow.item_count} {item_type}.",
    )

    return workflow