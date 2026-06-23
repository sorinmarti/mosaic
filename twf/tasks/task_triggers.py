"""
This module contains the functions for triggering Celery tasks in the TWF application.

The functions in this module handle the extraction of parameters from HTTP requests,
the validation of those parameters, and the triggering of appropriate Celery tasks.
They serve as the bridge between the web interface and the background task processing system.

Key features:
- Standardized task triggering through the trigger_task helper function
- Support for various AI operations (OpenAI, Gemini, Claude, Mistral)
- Specialized handlers for multimodal content (text + images) in project queries
- Comprehensive support for dictionary, document, collection, and export tasks
"""

import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage
from django.http import JsonResponse

from twf.tasks.structure_tasks import extract_zip_export_task
from twf.tasks.transkribus_enrich_tasks import enrich_transkribus_metadata_task
from twf.tasks.dictionary_tasks import (
    search_gnd_entries,
    search_geonames_entries,
    search_wikidata_entries,
    search_gnd_entry,
    search_geonames_entry,
    search_wikidata_entry,
)
from twf.tasks.metadata_tasks import load_sheets_metadata, load_json_metadata
from twf.tasks.project_tasks import copy_project
from twf.tasks.export_tasks import (
    export_project_task,
    export_to_zenodo_task,
    export_task,
)

# Note: Unified AI tasks are imported dynamically in their respective trigger functions to avoid circular imports
from twf.views.views_base import TWFView


def trigger_task(request, task_function, *args, **kwargs):
    """
    Trigger a Celery task and return a JSON response with the task ID.

    This is a helper function used by all task trigger handlers to standardize
    the process of starting a background task. It extracts the current project
    and user from the request, passes them to the task along with any additional
    arguments, and returns a standardized JSON response for AJAX handling.

    Args:
        request (HttpRequest): The HTTP request object
        task_function (function): The Celery task function to call
        *args, **kwargs: Additional positional and keyword arguments to pass to the task

    Returns:
        JsonResponse: A JSON response containing the task ID for client-side tracking
    """
    project = TWFView.s_get_project(request)
    user_id = request.user.id

    task = task_function.delay(project.id, user_id, *args, **kwargs)
    return JsonResponse({"status": "success", "task_id": task.id})


def trigger_ai_task(request, task_function, **kwargs):
    """
    Trigger an AI task and return a JSON response with the task ID.
    """
    prompt = request.POST.get("prompt")
    role_description = request.POST.get("role_description")
    prompt_mode = request.POST.get("prompt_mode")

    kwargs["prompt"] = prompt
    kwargs["role_description"] = role_description
    kwargs["prompt_mode"] = prompt_mode

    return trigger_task(request, task_function, **kwargs)


##############################
## PROJECT TASKS
def start_extraction(request):
    """Start Transkribus export zip extraction and unified smart sync process.

    Optional parameters:
    - force_recreate_tags: Boolean to force recreation of all tags (default: False)
    - delete_removed_documents: Boolean to delete documents not in export (default: True)
    - transkribus_username: Transkribus username (will be saved to project)
    - transkribus_password: Transkribus password (will be saved to project)
    """
    # Save Transkribus credentials if provided
    transkribus_username = request.POST.get("transkribus_username")
    transkribus_password = request.POST.get("transkribus_password")

    if transkribus_username or transkribus_password:
        from twf.views.views_base import TWFView
        project = TWFView.s_get_project(request)

        if project:
            credentials = project.conf_credentials or {}
            credentials["transkribus"] = {
                "username": transkribus_username or "",
                "password": transkribus_password or "",
            }
            project.conf_credentials = credentials
            project.save()

    # Extract optional parameters from form
    force_recreate_tags = (
        request.POST.get("force_recreate_tags", "false").lower() == "true"
    )
    delete_removed_documents = (
        request.POST.get("delete_removed_documents", "true").lower() == "true"
    )

    kwargs = {
        "force_recreate_tags": force_recreate_tags,
        "delete_removed_documents": delete_removed_documents,
    }

    return trigger_task(request, extract_zip_export_task, **kwargs)


def start_enrich_metadata(request):
    """Start Transkribus API metadata enrichment for all documents.

    Optional parameters:
    - force: Boolean to force re-enrichment even for documents with existing metadata (default: False)
    - transkribus_username: Transkribus username (will be saved to project)
    - transkribus_password: Transkribus password (will be saved to project)
    """
    # Save Transkribus credentials if provided
    transkribus_username = request.POST.get("transkribus_username")
    transkribus_password = request.POST.get("transkribus_password")

    if transkribus_username or transkribus_password:
        from twf.views.views_base import TWFView
        project = TWFView.s_get_project(request)

        if project:
            credentials = project.conf_credentials or {}
            credentials["transkribus"] = {
                "username": transkribus_username or "",
                "password": transkribus_password or "",
            }
            project.conf_credentials = credentials
            project.save()

    # Extract optional parameters from form
    # Django checkboxes send 'on' when checked, or nothing when unchecked
    force_value = request.POST.get("force", "")
    force = force_value.lower() in ("true", "on", "1")

    kwargs = {"force": force}

    return trigger_task(request, enrich_transkribus_metadata_task, **kwargs)


def start_enrich_document_metadata(request, document_pk):
    """Start Transkribus API metadata enrichment for a specific document.

    Args:
        document_pk: The primary key of the document to enrich

    Optional parameters:
    - force: Boolean to force re-enrichment even if metadata exists (default: True)
    """
    import json
    from twf.models import Document

    # Get the document to find its Transkribus document_id
    try:
        document = Document.objects.get(pk=document_pk)
    except Document.DoesNotExist:
        return JsonResponse(
            {"status": "error", "message": "Document not found"}, status=404
        )

    # Parse JSON body if present
    if request.body:
        try:
            data = json.loads(request.body)
            force = data.get("force", True)
        except json.JSONDecodeError:
            force = True
    else:
        force = request.POST.get("force", "true").lower() == "true"

    kwargs = {
        "force": force,
        "document_ids": [document.document_id],  # Pass the Transkribus document ID
    }

    return trigger_task(request, enrich_transkribus_metadata_task, **kwargs)


def start_test_export_task(request):
    """Start the test export task."""
    return JsonResponse({"status": "error", "message": "Not implemented"}, status=400)


##############################
## DICTIONARY TASKS
def start_dict_gnd_batch(request):
    """Start the GND requests as a Celery task."""
    dictionary_id = request.POST.get("dictionary")
    earliest_birth_year = request.POST.get("earliest_birth_year", None)
    latest_birth_year = request.POST.get("latest_birth_year", None)
    show_empty = request.POST.get("show_empty", False)
    if show_empty == "on":
        show_empty = True
    if earliest_birth_year != "":
        earliest_birth_year = int(earliest_birth_year)
    if latest_birth_year != "":
        latest_birth_year = int(latest_birth_year)

    return trigger_task(
        request,
        search_gnd_entries,
        dictionary_id=dictionary_id,
        earliest_birth_year=earliest_birth_year,
        latest_birth_year=latest_birth_year,
        show_empty=show_empty,
    )


def start_dict_geonames_batch(request):
    """Start the GeoNames requests as a Celery task.

    Optional parameters:
    - geonames_username: GeoNames username (will be saved to project)
    """
    # Save GeoNames credentials if provided
    geonames_username = request.POST.get("geonames_username")

    if geonames_username:
        from twf.views.views_base import TWFView
        project = TWFView.s_get_project(request)

        if project:
            credentials = project.conf_credentials or {}
            credentials["geonames"] = {
                "username": geonames_username or "",
            }
            project.conf_credentials = credentials
            project.save()

    dictionary_id = request.POST.get("dictionary")
    country_restriction = request.POST.get("only_search_in")
    similarity_threshold = request.POST.get("similarity_threshold")

    return trigger_task(
        request,
        search_geonames_entries,
        dictionary_id=dictionary_id,
        country_restriction=country_restriction,
        similarity_threshold=similarity_threshold,
    )


def start_dict_wikidata_batch(request):
    """Start the GND requests as a Celery task."""
    dictionary_id = request.POST.get("dictionary")
    entity_type = request.POST.get("entity_type")
    language = request.POST.get("language")

    return trigger_task(
        request,
        search_wikidata_entries,
        dictionary_id=dictionary_id,
        entity_type=entity_type,
        language=language,
    )


def start_dictionaries_batch_unified(request):
    """
    Unified task trigger for dictionary AI batch processing.
    Uses AIConfiguration for all AI settings (provider, model, prompt, etc.).
    """
    from twf.tasks.dictionary_tasks import search_ai_entries

    ai_configuration_id = request.POST.get("ai_configuration")
    dictionary_id = request.POST.get("dictionary")

    return trigger_ai_task(
        request,
        search_ai_entries,
        dictionary_id=dictionary_id,
        ai_configuration_id=ai_configuration_id,
    )


def start_dict_gnd_request(request):
    """
    Trigger a GND search task for a dictionary entry.

    Args:
        request: Django HTTP request containing dictionary_id, birth year filters

    Returns:
        HttpResponse: Redirect or task status response
    """
    dictionary_id = request.GET.get("dictionary_id")
    earliest_birth_year = request.POST.get("earliest_birth_year", None)
    latest_birth_year = request.POST.get("latest_birth_year", None)
    show_empty = request.POST.get("show_empty", False)
    if show_empty == "on":
        show_empty = True
    if earliest_birth_year != "":
        earliest_birth_year = int(earliest_birth_year)
    if latest_birth_year != "":
        latest_birth_year = int(latest_birth_year)

    return trigger_task(
        request,
        search_gnd_entry,
        dictionary_id=dictionary_id,
        earliest_birth_year=earliest_birth_year,
        latest_birth_year=latest_birth_year,
        show_empty=show_empty,
    )


def start_dict_geonames_request(request):
    """
    Trigger a Geonames search task for a dictionary entry.

    Args:
        request: Django HTTP request containing dictionary_id and search parameters

    Returns:
        HttpResponse: Redirect or task status response
    """
    dictionary_id = request.GET.get("dictionary_id")
    country_restriction = request.POST.get("only_search_in")
    similarity_threshold = request.POST.get("similarity_threshold")
    return trigger_task(
        request,
        search_geonames_entry,
        dictionary_id=dictionary_id,
        country_restriction=country_restriction,
        similarity_threshold=similarity_threshold,
    )


def start_dict_wikidata_request(request):
    """
    Trigger a Wikidata search task for a dictionary entry.

    Args:
        request: Django HTTP request containing dictionary_id, entity type, and language

    Returns:
        HttpResponse: Redirect or task status response
    """
    dictionary_id = request.GET.get("dictionary_id")
    entity_type = request.POST.get("entity_type")
    language = request.POST.get("language")
    return trigger_task(
        request,
        search_wikidata_entry,
        dictionary_id=dictionary_id,
        entity_type=entity_type,
        language=language,
    )


def start_dictionaries_request_unified(request):
    """
    Unified task trigger for dictionary AI request (supervised) processing.
    Uses AIConfiguration for all AI settings (provider, model, prompt, etc.).
    """
    from twf.tasks.dictionary_tasks import search_ai_entry

    ai_configuration_id = request.POST.get("ai_configuration")
    entry_id = request.GET.get("entry_id")

    return trigger_ai_task(
        request, search_ai_entry, entry_id=entry_id, ai_configuration_id=ai_configuration_id
    )


##############################
## DOCUMENT TASKS
def start_documents_batch_unified(request):
    """
    Unified task trigger for document AI batch processing.
    Uses AIConfiguration for all AI settings (provider, model, prompt, etc.).
    """
    from twf.tasks.document_tasks import search_ai_for_docs

    ai_configuration_id = request.POST.get("ai_configuration")
    request_level = request.POST.get("request_level")

    return trigger_ai_task(
        request,
        search_ai_for_docs,
        ai_configuration_id=ai_configuration_id,
        request_level=request_level,
    )


##############################
## METADATA TASKS
def start_json_metadata(request):
    """Start the metadata loading from JSON as a Celery task."""

    data_target_type = request.POST.get("data_target_type")
    metadata_storage_key = request.POST.get("metadata_storage_key", "json_import")
    json_data_key = request.POST.get("json_data_key")
    match_to_field = request.POST.get("match_to_field")

    data_file = request.FILES.get("data_file")

    if data_file:
        # Generate a unique filename
        file_name = f"metadata_upload_{uuid.uuid4().hex}.json"
        file_path = Path(settings.MEDIA_ROOT) / "temp" / file_name

        # Ensure the temp directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Save the file
        with default_storage.open(file_path, "wb") as destination:
            for chunk in data_file.chunks():
                destination.write(chunk)

    else:
        return JsonResponse(
            {"status": "error", "message": "No file uploaded"}, status=400
        )

    return trigger_task(
        request,
        load_json_metadata,
        data_file_path=file_path,
        data_target_type=data_target_type,
        metadata_storage_key=metadata_storage_key,
        json_data_key=json_data_key,
        match_to_field=match_to_field,
    )


def start_sheet_metadata(request):
    """Start the metadata loading from Google Sheets as a Celery task."""
    return trigger_task(request, load_sheets_metadata)


##############################
## COLLECTION TASKS
def start_collections_batch_unified(request):
    """
    Unified task trigger for collection AI batch processing.
    Uses AIConfiguration for all AI settings (provider, model, prompt, etc.).
    """
    from twf.tasks.collection_tasks import search_ai_for_collection

    ai_configuration_id = request.POST.get("ai_configuration")
    collection_id = request.POST.get("collection")

    return trigger_ai_task(
        request,
        search_ai_for_collection,
        collection_id=collection_id,
        ai_configuration_id=ai_configuration_id,
    )


def start_collections_request_unified(request):
    """
    Unified task trigger for collection AI request (supervised) processing.
    Uses AIConfiguration for all AI settings (provider, model, prompt, etc.).
    """
    from twf.tasks.collection_tasks import search_ai_for_collection_item

    ai_configuration_id = request.POST.get("ai_configuration")
    item_id = request.GET.get("item_id")

    return trigger_ai_task(
        request,
        search_ai_for_collection_item,
        item_id=item_id,
        ai_configuration_id=ai_configuration_id,
    )


def start_copy_project(request):
    """
    Trigger a task to copy/duplicate a project.

    Args:
        request: Django HTTP request containing new_project_name

    Returns:
        HttpResponse: Redirect or task status response
    """
    new_project_name = request.POST.get("new_project_name")
    return trigger_task(request, copy_project, new_project_name=new_project_name)


def start_query_project_unified(request):
    """
    Unified task trigger for AI queries.
    Uses AIConfiguration for all AI settings (provider, model, prompt, etc.).
    """
    from twf.tasks.project_tasks import query_project_unified

    ai_configuration_id = request.POST.get("ai_configuration")
    documents = request.POST.getlist("documents")

    return trigger_ai_task(
        request,
        query_project_unified,
        ai_configuration_id=ai_configuration_id,
        documents=documents,
    )


def start_export(request):
    """Start the export task."""
    configuration_id = request.POST.get("export_conf")
    return trigger_task(request, export_task, export_configuration_id=configuration_id)


def start_export_project(request):
    """
    Trigger a task to export complete project data.

    Args:
        request: Django HTTP request containing export options

    Returns:
        HttpResponse: Redirect or task status response
    """
    include_dictionaries = request.POST.get("include_dictionaries", False)
    include_media_files = request.POST.get("include_media_files", False)
    return trigger_task(
        request,
        export_project_task,
        include_dictionaries=include_dictionaries,
        include_media_files=include_media_files,
    )


def start_export_to_zenodo(request):
    """
    Trigger a task to upload an export to Zenodo.

    Args:
        request: Django HTTP request containing export_id

    Returns:
        HttpResponse: Redirect or task status response
    """
    return trigger_task(
        request,
        export_to_zenodo_task,
        export_id=request.POST.get("export_id"),
    )


##############################
## AI CONFIGURATION TASKS
def start_test_ai_config(request):
    """
    Trigger a task to test an AI configuration.

    Args:
        request: Django HTTP request containing ai_config_id and test_context

    Returns:
        JsonResponse: Task ID for tracking
    """
    from twf.tasks.ai_config_tasks import test_ai_config_task

    ai_config_id = request.POST.get("ai_config_id")
    test_context = request.POST.get("test_context", "{}")

    return trigger_task(
        request,
        test_ai_config_task,
        ai_config_id=int(ai_config_id),
        test_context=test_context,
    )
