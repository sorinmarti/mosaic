"""
Tag Workflow Management
=======================

This module provides functions for creating and managing tag-related workflows.
"""

from django.db.models import Count
from django.shortcuts import redirect
from twf.models import Workflow, PageTag
from twf.tasks.instant_tasks import start_related_task
from twf.utils.tags_utils import get_date_types, get_enrichment_type_for_tag_type
from twf.workflows.workflow_utils import end_workflow
from twf.views.views_base import TWFView


def get_available_tag_count(project, tag_type):
    """
    Get count of unique unassigned variations for a tag type.

    Parameters
    ----------
    project : Project
        The project to count tags for
    tag_type : str
        The tag type to count

    Returns
    -------
    int
        Count of unique unassigned variations
    """
    return (
        PageTag.objects.filter(
            page__document__project=project,
            page__is_ignored=False,
            variation_type=tag_type,
            dictionary_entry__isnull=True,
            is_parked=False,
            is_reserved=False,
        )
        .values("variation")
        .distinct()
        .count()
    )


def get_available_date_count(project):
    """
    Get count of unresolved date tags.

    Parameters
    ----------
    project : Project
        The project to count date tags for

    Returns
    -------
    int
        Count of unresolved date tags
    """
    date_types = get_date_types(project)
    return PageTag.objects.filter(
        page__document__project=project,
        page__is_ignored=False,
        variation_type__in=date_types,
        date_variation_entry__isnull=True,
        is_parked=False,
        is_reserved=False,
    ).count()


def create_tag_grouping_workflow(project, user, tag_type, item_count=None):
    """
    Create a new workflow for tag grouping and reserve unique tag variations.

    This function reserves unique tag strings (all identical tags as one unit).
    When a unique variation is reserved, ALL matching tags with the same text
    are marked as reserved and added to the workflow.

    Parameters
    ----------
    project : Project
        The project to create the workflow for
    user : User
        The user creating the workflow
    tag_type : str
        The type of tags to group (e.g., 'person', 'location')
    item_count : int, optional
        Number of unique tag variations to reserve. If None, uses configured batch size.

    Returns
    -------
    bool or Workflow
        False if no tags available, otherwise the created Workflow instance
    """
    # Use configured batch size if item_count not provided
    if item_count is None:
        workflow_def = project.get_workflow_definition("review_tags_grouping")
        item_count = workflow_def.get("batch_size", 10)

    # Get distinct unassigned variations for this tag type
    # Exclude parked and reserved tags
    unique_variations = list(
        PageTag.objects.filter(
            page__document__project=project,
            page__is_ignored=False,
            variation_type=tag_type,
            dictionary_entry__isnull=True,
            is_parked=False,
            is_reserved=False,
        )
        .values("variation")
        .distinct()[:item_count]
    )

    if len(unique_variations) == 0:
        return False

    actual_item_count = len(unique_variations)

    # For each unique variation, get ALL matching tags
    all_tag_ids = []
    for var_dict in unique_variations:
        variation = var_dict["variation"]
        matching_tags = PageTag.objects.filter(
            page__document__project=project,
            page__is_ignored=False,
            variation=variation,
            variation_type=tag_type,
            is_parked=False,
            is_reserved=False,
        ).values_list("id", flat=True)
        all_tag_ids.extend(matching_tags)

    # Mark all matching tags as reserved
    PageTag.objects.filter(id__in=all_tag_ids).update(is_reserved=True)

    # Create task for activity logging
    task = start_related_task(
        project,
        user,
        f"Group {tag_type.title()} Tags",
        f"Group {tag_type} tag variations into dictionary entries.",
        f"The user has started a workflow to group {actual_item_count} unique {tag_type} tag(s).",
    )

    # Create the workflow with metadata
    workflow = Workflow.objects.create(
        project=project,
        user=user,
        workflow_type="review_tags_grouping",
        item_count=actual_item_count,
        related_task=task,
        metadata={"tag_type": tag_type},
    )

    # Initialize workflow_steps in the related task
    if task:
        task.workflow_steps = {
            "current_step": 0,
            "total_steps": actual_item_count,
            "steps": [],
            "workflow_type": "review_tags_grouping",
            "tag_type": tag_type,
            "started_at": task.start_time.isoformat() if task.start_time else None
        }
        task.save(update_fields=["workflow_steps"])

    # Assign all reserved tags to the workflow
    workflow.assigned_tag_items.set(PageTag.objects.filter(id__in=all_tag_ids))

    return workflow


def create_date_normalization_workflow(project, user, item_count=None):
    """
    Create a new workflow for date normalization and reserve date tags.

    This function reserves individual date tags for normalization to EDTF format.

    Parameters
    ----------
    project : Project
        The project to create the workflow for
    user : User
        The user creating the workflow
    item_count : int, optional
        Number of date tags to reserve. If None, uses configured batch size.

    Returns
    -------
    bool or Workflow
        False if no date tags available, otherwise the created Workflow instance
    """
    # Use configured batch size if item_count not provided
    if item_count is None:
        workflow_def = project.get_workflow_definition("review_tags_dates")
        item_count = workflow_def.get("batch_size", 20)

    # Get date types for this project
    date_types = get_date_types(project)

    # Get unresolved date tags
    available_tag_ids = list(
        PageTag.objects.filter(
            page__document__project=project,
            page__is_ignored=False,
            variation_type__in=date_types,
            date_variation_entry__isnull=True,
            is_parked=False,
            is_reserved=False,
        ).values_list("id", flat=True)[:item_count]
    )

    if len(available_tag_ids) == 0:
        return False

    actual_item_count = len(available_tag_ids)

    # Mark tags as reserved
    PageTag.objects.filter(id__in=available_tag_ids).update(is_reserved=True)

    # Create task for activity logging
    task = start_related_task(
        project,
        user,
        "Normalize Date Tags",
        "Normalize date tags to EDTF format.",
        f"The user has started a workflow to normalize {actual_item_count} date tag(s).",
    )

    # Create the workflow
    workflow = Workflow.objects.create(
        project=project,
        user=user,
        workflow_type="review_tags_dates",
        item_count=actual_item_count,
        related_task=task,
    )

    # Initialize workflow_steps in the related task
    if task:
        task.workflow_steps = {
            "current_step": 0,
            "total_steps": actual_item_count,
            "steps": [],
            "workflow_type": "review_tags_dates",
            "started_at": task.start_time.isoformat() if task.start_time else None
        }
        task.save(update_fields=["workflow_steps"])

    # Assign date tags to the workflow
    workflow.assigned_tag_items.set(PageTag.objects.filter(id__in=available_tag_ids))

    return workflow


def create_enrichment_workflow(project, user, tag_type, item_count=None):
    """
    Create workflow for direct tag enrichment (dates, verses, etc.).

    Generic workflow creator that handles any enrichment type configuration.
    Replaces specific implementations like create_date_normalization_workflow.

    Parameters
    ----------
    project : Project
        The project to create the workflow for
    user : User
        The user creating the workflow
    tag_type : str
        The specific tag type (e.g., 'date', 'bible_verse')
    item_count : int, optional
        Number of tags to enrich. If None, uses configured batch size.

    Returns
    -------
    bool or Workflow
        False if no enrichment config or no tags available,
        otherwise the created Workflow instance
    """
    # Get enrichment config for this tag type
    enrichment_config = get_enrichment_type_for_tag_type(project, tag_type)
    if not enrichment_config:
        return False

    # Use configured batch size if not provided
    if item_count is None:
        workflow_def = project.get_workflow_definition("review_tags_enrichment")
        item_count = workflow_def.get("batch_size", 20)

    # Find unresolved tags of this type
    # A tag is unenriched if it has no old tag_enrichment_entry AND no new enrichment data
    from django.db.models import Q
    available_tags = list(
        PageTag.objects.filter(
            page__document__project=project,
            page__is_ignored=False,
            variation_type=tag_type,
            tag_enrichment_entry__isnull=True,
            is_parked=False,
            is_reserved=False,
        )
        .filter(Q(enrichment__isnull=True) | Q(enrichment={}))
        .values_list("id", flat=True)[:item_count]
    )

    if not available_tags:
        return False

    # Mark as reserved
    PageTag.objects.filter(id__in=available_tags).update(is_reserved=True)

    # Create task
    workflow_title = enrichment_config.get(
        "workflow_title", f"Enrich {tag_type.title()} Tags"
    )
    task = start_related_task(
        project,
        user,
        workflow_title,
        f"Enrich {tag_type} tags with normalized data.",
        f"The user has started a workflow to enrich {len(available_tags)} {tag_type} tag(s).",
    )

    # Create workflow with metadata
    workflow_metadata = {
        "tag_type": tag_type,
        "enrichment_type": enrichment_config.get("form_type", tag_type),
    }

    # Add wikidata_entity_type if configured
    if enrichment_config.get("wikidata_entity_type"):
        workflow_metadata["wikidata_entity_type"] = enrichment_config["wikidata_entity_type"]

    workflow = Workflow.objects.create(
        project=project,
        user=user,
        workflow_type="review_tags_enrichment",
        item_count=len(available_tags),
        related_task=task,
        metadata=workflow_metadata,
    )

    # Initialize workflow_steps in the related task
    if task:
        task.workflow_steps = {
            "current_step": 0,
            "total_steps": len(available_tags),
            "steps": [],
            "workflow_type": "review_tags_enrichment",
            "tag_type": tag_type,
            "enrichment_type": enrichment_config.get("form_type", tag_type),
            "started_at": task.start_time.isoformat() if task.start_time else None
        }
        task.save(update_fields=["workflow_steps"])

    # Assign tags
    workflow.assigned_tag_items.set(PageTag.objects.filter(id__in=available_tags))

    return workflow


# End workflow functions
def end_tag_grouping_workflow(request):
    """End/cancel the current tag grouping workflow."""
    project = TWFView.s_get_project(request)
    user = request.user

    end_workflow(request, project, user, "review_tags_grouping", "twf:tags_group")

    return redirect("twf:tags_group")


def end_tag_enrichment_workflow(request):
    """End/cancel the current tag enrichment workflow."""
    project = TWFView.s_get_project(request)
    user = request.user

    end_workflow(request, project, user, "review_tags_enrichment", "twf:tags_enrichment")

    return redirect("twf:tags_enrichment")
