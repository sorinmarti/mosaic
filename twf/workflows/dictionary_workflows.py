"""
Dictionary Workflow Management
===============================

This module provides functions for creating and managing dictionary-related workflows.
"""

from django.db.models import Q
from django.shortcuts import redirect
from twf.models import Workflow, DictionaryEntry, Dictionary
from twf.tasks.instant_tasks import start_related_task
from twf.workflows.workflow_utils import end_workflow
from twf.views.views_base import TWFView


def create_dictionary_enrichment_workflow(project, user, dictionary_id, enrichment_type, item_count=None):
    """
    Create workflow for dictionary entry enrichment.

    Parameters
    ----------
    project : Project
        The project to create the workflow for
    user : User
        The user creating the workflow
    dictionary_id : int
        The dictionary ID to enrich entries from
    enrichment_type : str
        The enrichment type (e.g., 'verse', 'date', 'authority_id')
    item_count : int, optional
        Number of entries to enrich. If None, uses configured batch size.

    Returns
    -------
    bool or Workflow
        False if no entries available, otherwise the created Workflow instance
    """
    # Get the dictionary
    try:
        dictionary = Dictionary.objects.get(id=dictionary_id, selected_projects=project)
    except Dictionary.DoesNotExist:
        return False

    # Use configured batch size if not provided
    if item_count is None:
        workflow_def = project.get_workflow_definition("review_dictionary_enrichment")
        item_count = workflow_def.get("batch_size", 20)

    # Find unenriched entries in this dictionary
    # An entry is unenriched if it has no enrichment data for this specific type
    import logging
    logger = logging.getLogger(__name__)
    logger.debug(f"CREATE WORKFLOW: Dictionary={dictionary.label}, enrichment_type={enrichment_type}, batch_size={item_count}")

    available_entries = []
    all_candidates = DictionaryEntry.objects.filter(
        dictionary=dictionary,
        is_reserved=False,
        is_parked=False,
    ).order_by('pk')  # Check all unreserved/unparked entries

    total_candidates = all_candidates.count()
    logger.debug(f"CREATE WORKFLOW: Checking {total_candidates} candidate entries (unreserved, unparked)")

    for idx, entry in enumerate(all_candidates):
        entry.refresh_from_db()  # Ensure fresh data
        has_enrich = entry.has_enrichment(enrichment_type)
        metadata_keys = list(entry.metadata.keys()) if entry.metadata else []

        logger.debug(f"CREATE WORKFLOW: Entry {idx}: ID={entry.id}, label='{entry.label}', is_parked={entry.is_parked}, has_enrichment({enrichment_type})={has_enrich}, metadata_keys={metadata_keys}")

        # Check if entry has this specific enrichment type
        if not has_enrich:
            available_entries.append(entry.id)
            logger.debug(f"CREATE WORKFLOW: ✓ Added entry {entry.id} to workflow")
            if len(available_entries) >= item_count:
                logger.debug(f"CREATE WORKFLOW: Reached batch size limit ({item_count})")
                break
        else:
            logger.debug(f"CREATE WORKFLOW: ✗ Skipped entry {entry.id} (already enriched)")

    logger.debug(f"CREATE WORKFLOW: Found {len(available_entries)} unenriched entries")

    if not available_entries:
        logger.warning(f"CREATE WORKFLOW: No unenriched entries found for {enrichment_type}")
        return False

    # Mark as reserved
    DictionaryEntry.objects.filter(id__in=available_entries).update(is_reserved=True)

    # Create task
    workflow_title = f"Enrich {dictionary.label} Entries ({enrichment_type})"
    task = start_related_task(
        project,
        user,
        workflow_title,
        f"Enrich dictionary entries with {enrichment_type} data.",
        f"The user has started a workflow to enrich {len(available_entries)} entries from '{dictionary.label}'.",
    )

    # Create workflow with metadata
    workflow_metadata = {
        "dictionary_id": dictionary_id,
        "dictionary_title": dictionary.label,
        "enrichment_type": enrichment_type,
    }

    # Add wikidata_entity_type if configured and enrichment type is wikidata
    if enrichment_type == "wikidata":
        dict_config = project.get_dictionary_enrichment_config(dictionary.type)
        wikidata_entity_type = dict_config.get("wikidata_entity_type")
        if wikidata_entity_type:
            workflow_metadata["wikidata_entity_type"] = wikidata_entity_type

    workflow = Workflow.objects.create(
        project=project,
        user=user,
        workflow_type="review_dictionary_enrichment",
        item_count=len(available_entries),
        related_task=task,
        metadata=workflow_metadata,
    )

    # Initialize workflow_steps in the related task
    if task:
        task.workflow_steps = {
            "current_step": 0,
            "total_steps": len(available_entries),
            "steps": [],
            "workflow_type": "review_dictionary_enrichment",
            "dictionary_id": dictionary.id,
            "dictionary_type": dictionary.type,
            "enrichment_type": enrichment_type,
            "started_at": task.start_time.isoformat() if task.start_time else None
        }
        task.save(update_fields=["workflow_steps"])

    # Assign entries using the assigned_dictionary_entries M2M field
    workflow.assigned_dictionary_entries.set(
        DictionaryEntry.objects.filter(id__in=available_entries)
    )

    return workflow


def get_available_dictionary_entry_count(project, dictionary_id, enrichment_type):
    """
    Get count of unenriched entries in a dictionary for a specific enrichment type.

    Parameters
    ----------
    project : Project
        The project
    dictionary_id : int
        The dictionary ID
    enrichment_type : str
        The enrichment type to check

    Returns
    -------
    int
        Count of unenriched entries
    """
    try:
        dictionary = Dictionary.objects.get(id=dictionary_id, selected_projects=project)
    except Dictionary.DoesNotExist:
        return 0

    count = 0
    for entry in DictionaryEntry.objects.filter(
        dictionary=dictionary,
        is_reserved=False,
        is_parked=False,
    ):
        if not entry.has_enrichment(enrichment_type):
            count += 1

    return count


def end_dictionary_enrichment_workflow(request):
    """End/cancel the current dictionary enrichment workflow."""
    project = TWFView.s_get_project(request)
    user = request.user

    end_workflow(request, project, user, "review_dictionary_enrichment", "twf:dictionaries_enrichment")

    return redirect("twf:dictionaries_enrichment")


def create_dictionary_review_workflow(project, user, dictionary_id, batch_size=20):
    """
    Create a workflow for reviewing dictionary entries.

    Finds pending (not yet reviewed, not parked, not reserved) entries in the
    given dictionary, reserves them, and creates a Workflow of type
    'review_dictionary_entries'.

    Parameters
    ----------
    project : Project
        The project to create the workflow for.
    user : User
        The user creating the workflow.
    dictionary_id : int
        The dictionary ID to review entries from.
    batch_size : int, optional
        Number of entries to include in the workflow. Defaults to 20.

    Returns
    -------
    Workflow or False
        The created Workflow instance, or False if no entries are available.
    """
    try:
        dictionary = Dictionary.objects.get(id=dictionary_id, selected_projects=project)
    except Dictionary.DoesNotExist:
        return False

    available_entries = list(
        DictionaryEntry.objects.filter(
            dictionary=dictionary,
            is_reserved=False,
            is_parked=False,
            review_status="pending",
        ).exclude(metadata={}).order_by("pk")[:batch_size].values_list("id", flat=True)
    )

    if not available_entries:
        return False

    # Mark entries as reserved
    DictionaryEntry.objects.filter(id__in=available_entries).update(is_reserved=True)

    # Create related task
    task = start_related_task(
        project,
        user,
        f"Review {dictionary.label} Entries",
        f"Review dictionary entries for '{dictionary.label}'.",
        f"The user started a review workflow for {len(available_entries)} entries from '{dictionary.label}'.",
    )

    # Create workflow
    workflow = Workflow.objects.create(
        project=project,
        user=user,
        workflow_type="review_dictionary_entries",
        item_count=len(available_entries),
        related_task=task,
        metadata={
            "dictionary_id": dictionary_id,
            "dictionary_title": dictionary.label,
        },
    )

    workflow.assigned_dictionary_entries.set(
        DictionaryEntry.objects.filter(id__in=available_entries)
    )

    return workflow


def end_dictionary_review_workflow(request):
    """End/cancel the current dictionary entries review workflow."""
    project = TWFView.s_get_project(request)
    user = request.user

    end_workflow(request, project, user, "review_dictionary_entries", "twf:dictionaries_review_entries")

    return redirect("twf:dictionaries_review_entries")
