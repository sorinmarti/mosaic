"""Views for CRUD operations on collections. These views do not render
HTML pages, but redirect to the appropriate URL after the operation is
completed."""

import json
import logging

from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.safestring import mark_safe
from django.views.decorators.csrf import csrf_exempt

from twf.models import Collection, CollectionItem, Workflow
from twf.permissions import check_permission
from twf.tasks.instant_tasks import (
    save_instant_task_delete_collection,
    save_instant_task_delete_collection_item,
)
from twf.views.views_base import TWFView, get_referrer_or_default

logger = logging.getLogger(__name__)


def delete_collection_item_annotation(request, pk, index):
    """Delete an annotation from a collection item."""
    is_allowed = check_permission(request.user, "collection.edit", pk)
    if not is_allowed:
        messages.error(
            request,
            "You do not have permission to delete annotations from this collection item.",
        )
        return redirect("twf:collections")

    collection_item = CollectionItem.objects.get(id=pk)
    collection_item.delete_annotation(index)
    messages.success(request, "Annotation deleted.")

    if request.GET.get("redirect_to_view"):
        return redirect(request.GET.get("redirect_to_view"))

    return redirect("twf:collection_item_edit", pk=pk)


def delete_collection_item(request, pk):
    """Delete a collection item."""
    is_allowed = check_permission(request.user, "collection.edit", pk)
    if not is_allowed:
        messages.error(
            request, "You do not have permission to delete this collection item."
        )
        return redirect("twf:collections")

    collection_item = CollectionItem.objects.get(id=pk)
    collection_id = collection_item.collection.id

    # Capture info before deletion
    project = TWFView.s_get_project(request)
    item_title = collection_item.title
    collection_title = collection_item.collection.title if collection_item.collection else "Unknown"

    # Save instant task before deletion
    save_instant_task_delete_collection_item(
        project, request.user, item_title, collection_item.id, collection_title
    )

    collection_item.delete()
    messages.success(request, "Collection item deleted.")

    return get_referrer_or_default(
        request, default="twf:collections_view", kwargs={"pk": collection_id}
    )


def copy_collection_item(request, pk):
    """Copy a collection item."""
    # Check user permission
    if not check_permission(request.user, "collection.edit", pk):
        messages.error(
            request, "You do not have permission to copy this collection item."
        )
        return redirect("twf:collections")

    # Get the collection item and perform the copy
    try:
        collection_item = CollectionItem.objects.get(id=pk)
        new_item = collection_item
        new_item.title = f"{collection_item.title} (copy)"
        new_item.pk = None
        new_item.save(current_user=request.user)

        if new_item is None:
            messages.error(request, "Could not copy collection item.")
        else:
            edit_url = reverse_lazy("twf:collection_item_edit", args=[new_item.id])
            messages.success(
                request,
                mark_safe(
                    f'Collection item copied successfully! <a href="{edit_url}">Edit the new item</a>'
                ),
            )
    except CollectionItem.DoesNotExist:
        messages.error(request, "Collection item not found.")
    except Exception as e:
        messages.error(
            request, "An unexpected error occurred while copying the collection item."
        )

    return get_referrer_or_default(
        request, default="twf:collection_item_edit", kwargs={"pk": pk}
    )


def split_collection_item(request, pk, index):
    """Split a collection item."""
    # Check user permission
    if not check_permission(request.user, "collection.edit", pk):
        messages.error(
            request, "You do not have permission to split this collection item."
        )
        return redirect("twf:collections")

    # Get the collection item and perform the split
    try:
        collection_item = CollectionItem.objects.get(id=pk)
        new_item = collection_item.split(index, request.user)

        if new_item is None:
            messages.error(
                request,
                "Could not split collection item. Please check the index and try again.",
            )
        else:
            edit_url = reverse_lazy("twf:collection_item_edit", args=[new_item.id])
            messages.success(
                request,
                mark_safe(
                    f'Collection item split successfully! <a href="{edit_url}">Edit the new item</a>'
                ),
            )
    except CollectionItem.DoesNotExist:
        messages.error(request, "Collection item not found.")
    except Exception as e:
        messages.error(
            request, "An unexpected error occurred while splitting the collection item."
        )

    return get_referrer_or_default(
        request, default="twf:collection_item_edit", kwargs={"pk": pk}
    )


def download_collection_item_txt(request, pk):
    """Download the text of a collection item as a .txt file."""
    # Check collection.view permission
    if not check_permission(request.user, "collection.view", pk):
        messages.error(
            request, "You do not have permission to download this collection item."
        )
        return redirect("twf:collections")

    item = CollectionItem.objects.get(id=pk)
    text = f"Title: {item.title}\n"
    for annotation in item.document_configuration["annotations"]:
        text += f"\n{annotation['text']}\n"

    response = HttpResponse(text, content_type="text/plain")
    response["Content-Disposition"] = f'attachment; filename="{item.title}.txt"'
    return response


def download_collection_item_json(request, pk):
    """Download the annotations of a collection item as a .json file."""
    # Check collection.view permission
    if not check_permission(request.user, "collection.view", pk):
        messages.error(
            request, "You do not have permission to download this collection item."
        )
        return redirect("twf:collections")

    item = CollectionItem.objects.get(id=pk)
    json = item.document_configuration
    json["title"] = item.title
    response = HttpResponse(json, content_type="application/json")
    response["Content-Disposition"] = f'attachment; filename="{item.title}.json"'
    return response


def set_col_item_status_open(request, pk):
    """Set the status of a collection item to open."""

    # TODO - Implement permission check
    return set_col_item_status(request, pk, "open")


def set_col_item_status_reviewed(request, pk):
    """Set the status of a collection item to reviewed."""

    # TODO - Implement permission check
    return set_col_item_status(request, pk, "reviewed")


def set_col_item_status_faulty(request, pk):
    """Set the status of a collection item to faulty."""

    # TODO - Implement permission check
    return set_col_item_status(request, pk, "faulty")


def set_col_item_status(request, collection_item_id, status):
    """Set the status of a collection item to open."""
    is_allowed = check_permission(request.user, "collection.edit", collection_item_id)
    if not is_allowed:
        messages.error(
            request,
            "You do not have permission to change the status of this collection item.",
        )
        return redirect("twf:collections")

    collection_item = CollectionItem.objects.get(id=collection_item_id)
    collection_item.status = status
    collection_item.save()
    messages.success(request, f"Collection item status set to '{status}'.")
    return get_referrer_or_default(
        request, default="twf:collection_item_edit", kwargs={"pk": collection_item_id}
    )


def delete_collection(request, collection_id):
    """Delete a collection."""
    is_allowed = check_permission(request.user, "collection.manage", collection_id)
    if not is_allowed:
        messages.error(request, "You do not have permission to delete this collection.")
        return redirect("twf:collections")

    collection = Collection.objects.get(id=collection_id)

    # Capture info before deletion
    project = TWFView.s_get_project(request)
    collection_title = collection.title

    # Save instant task before deletion
    save_instant_task_delete_collection(
        project, request.user, collection_title, collection.id
    )

    workflows = Workflow.objects.filter(collection=collection)
    for workflow in workflows:
        logger.info("Ending workflow %s due to collection deletion", workflow.id)
        workflow.finish(with_error=True)

    collection.delete()
    messages.success(request, "Collection deleted.")

    return get_referrer_or_default(request, "twf:collections")


def fill_collection_item(
    item, page, skip_empty_types=False, structure_tag_filter_list=None
):
    """Create a collection item."""

    # TODO Not sure if I need a permission check here

    if structure_tag_filter_list is None:
        structure_tag_filter_list = []

    annotations = page.get_annotations()
    for annotation in annotations:
        cleaned_annotation = clean_annotation(annotation)
        annotation_type = cleaned_annotation["type"]

        if annotation_type == "empty" and skip_empty_types:
            continue

        if annotation_type in structure_tag_filter_list:
            continue

        item.document_configuration["annotations"].append(cleaned_annotation)


def clean_annotation(annotation):
    """Clean an annotation."""
    cleaned_annotation = annotation.copy()
    if "type" not in cleaned_annotation:
        cleaned_annotation["type"] = "empty"
    if "text" not in cleaned_annotation:
        cleaned_annotation["text"] = ""
    return cleaned_annotation


@csrf_exempt
def update_collection_item_metadata(request, pk):
    """
    Update a metadata key-value pair for a collection item.

    Args:
        request: Django HTTP request with JSON body containing key and value
        pk: Primary key of the collection item

    Returns:
        JsonResponse: Response with the new value (placeholder implementation)
    """
    if request.method == "POST":
        data = json.loads(request.body)
        key = data.get("key")
        value = data.get("value")

        # TODO - Implement

        return JsonResponse({"new_value": value})


@csrf_exempt
def delete_collection_item_metadata(request, pk):
    """
    Delete a metadata key from a collection item.

    Args:
        request: Django HTTP request with JSON body containing key to delete
        pk: Primary key of the collection item

    Returns:
        JsonResponse: Success response (placeholder implementation)
    """
    if request.method == "POST":
        data = json.loads(request.body)
        key = data.get("key")

        # TODO - Implement

        return JsonResponse({"success": True})
