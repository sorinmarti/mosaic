"""Views for the project documents."""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt

from twf.models import Document
from twf.permissions import check_permission
from twf.tasks.instant_tasks import (
    save_instant_task_delete_document,
    save_instant_task_update_document,
)
from twf.utils.metadata_utils import delete_nested_key, set_nested_value
from twf.views.views_base import get_referrer_or_default, TWFView


@login_required
def delete_document(request, pk, doc_pk):
    """Deletes a document."""
    # Check document.manage permission
    project = TWFView.s_get_project(request)
    if not check_permission(request.user, "document.manage", project):
        messages.error(request, "You do not have permission to delete documents.")
        return get_referrer_or_default(request, default="twf:documents_overview")

    document = get_object_or_404(Document, pk=doc_pk)

    # Capture info before deletion
    document_title = document.title

    # Save instant task before deletion
    save_instant_task_delete_document(
        project, request.user, document_title, document.id
    )

    for page in document.pages.all():
        page.xml_file.delete()
        page.delete()
    document.delete()
    messages.success(request, f"Document {doc_pk} has been deleted.")

    return get_referrer_or_default(request, default="twf:document")


def update_document_metadata(request, pk, base_key):
    """
    Update a nested metadata value for a document.

    Args:
        request: Django HTTP request with JSON body containing key and value
        pk: Primary key of the document
        base_key: Top-level metadata key to update within

    Returns:
        JsonResponse: Response with the new value or error message
    """
    # Check metadata.edit permission
    project = TWFView.s_get_project(request)
    if not check_permission(request.user, "metadata.edit", project):
        return JsonResponse(
            {"error": "You do not have permission to edit metadata."},
            status=403
        )

    if request.method == "POST":
        data = json.loads(request.body)
        key = data.get("key")
        value = data.get("value")

        try:
            doc = Document.objects.get(pk=pk)
            base = doc.metadata.get(base_key, {})
            set_nested_value(base, key, value)
            doc.metadata[base_key] = base
            doc.save(current_user=request.user)
        except Document.DoesNotExist:
            return JsonResponse({"error": "Document does not exist."}, status=404)

        return JsonResponse({"new_value": value})


@csrf_exempt
def delete_document_metadata(request, pk, base_key):
    """
    Delete a nested metadata key from a document.

    Args:
        request: Django HTTP request with JSON body containing key to delete
        pk: Primary key of the document
        base_key: Top-level metadata key to delete from

    Returns:
        JsonResponse: Success response or error message
    """
    # Check metadata.edit permission
    project = TWFView.s_get_project(request)
    if not check_permission(request.user, "metadata.edit", project):
        return JsonResponse(
            {"error": "You do not have permission to edit metadata."},
            status=403
        )

    if request.method == "POST":
        data = json.loads(request.body)
        key = data.get("key")

        try:
            doc = Document.objects.get(pk=pk)
            base = doc.metadata.get(base_key, {})
            delete_nested_key(base, key)
            doc.metadata[base_key] = base
            doc.save(current_user=request.user)
        except Document.DoesNotExist:
            return JsonResponse({"error": "Document does not exist."}, status=404)
        except KeyError:
            return JsonResponse({"error": "Key does not exist."}, status=404)

        return JsonResponse({"success": True})


@login_required
def update_document_options(request, pk):
    """Update document status and workflow remarks."""
    # Check document.edit permission
    project = TWFView.s_get_project(request)
    if not check_permission(request.user, "document.edit", project):
        messages.error(request, "You do not have permission to edit documents.")
        return redirect("twf:view_document", pk=pk)

    if request.method == "POST":
        document = get_object_or_404(Document, pk=pk)

        # Track what changed
        changes = []

        # Update status if provided
        status = request.POST.get("status")
        if status and status in dict(Document.STATUS_CHOICES):
            if document.status != status:
                changes.append(f"status: {document.status} → {status}")
            document.status = status

        # Update is_parked if provided
        is_parked = request.POST.get("is_parked")
        if is_parked is not None:
            new_parked = is_parked == "true"
            if document.is_parked != new_parked:
                changes.append(f"parked: {document.is_parked} → {new_parked}")
            document.is_parked = new_parked

        # Update workflow_remarks
        workflow_remarks = request.POST.get("workflow_remarks", "")
        if document.workflow_remarks != workflow_remarks:
            changes.append("workflow_remarks updated")
        document.workflow_remarks = workflow_remarks

        # Save instant task if there were changes
        if changes:
            save_instant_task_update_document(
                project, request.user, document.title, document.id, ", ".join(changes)
            )

        document.save(current_user=request.user)
        messages.success(request, "Document options updated successfully.")

        return redirect("twf:view_document", pk=pk)

    return redirect("twf:view_document", pk=pk)
