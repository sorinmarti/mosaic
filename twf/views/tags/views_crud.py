"""Views for command actions."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect

from twf.models import PageTag
from twf.permissions import check_permission
from twf.tasks.instant_tasks import (
    save_instant_task_delete_tag,
    save_instant_task_park_tag,
    save_instant_task_unpark_tag,
)
from twf.views.views_base import get_referrer_or_default, TWFView
from twf.utils.tags_utils import assign_tag, get_excluded_types


def park_tag(request, pk):
    """Parks a tag."""
    # Check tag.edit permission
    project = TWFView.s_get_project(request)
    if not check_permission(request.user, "tag.edit", project):
        messages.error(request, "You do not have permission to park tags.")
        return get_referrer_or_default(request, default="twf:tags_overview")

    tag = get_object_or_404(PageTag, pk=pk)

    # Capture info before parking
    tag_variation = tag.variation

    # Save instant task
    save_instant_task_park_tag(project, request.user, tag_variation, tag.id)

    tag.is_parked = True
    tag.save(current_user=request.user)
    messages.success(request, f"Tag {pk} has been parked.")

    return get_referrer_or_default(request, default="twf:tags_overview")


def park_all_identical_tags(request, pk):
    """Parks all tags with the same variation as the specified tag."""
    # Check tag.edit permission
    project = TWFView.s_get_project(request)
    if not check_permission(request.user, "tag.edit", project):
        messages.error(request, "You do not have permission to park tags.")
        return get_referrer_or_default(request, default="twf:tags_overview")

    tag = get_object_or_404(PageTag, pk=pk)
    project = tag.page.document.project

    # Find all unparked tags with the same variation in the same project
    identical_tags = PageTag.objects.filter(
        page__document__project=project, variation=tag.variation, is_parked=False
    )

    count = identical_tags.count()

    # Park all identical tags
    for identical_tag in identical_tags:
        identical_tag.is_parked = True
        identical_tag.save(current_user=request.user)

    messages.success(
        request, f'Parked {count} tag(s) with variation "{tag.variation}".'
    )

    return get_referrer_or_default(request, default="twf:tags_overview")


def unpark_tag(request, pk):
    """Unparks a tag."""
    # Check tag.edit permission
    project = TWFView.s_get_project(request)
    if not check_permission(request.user, "tag.edit", project):
        messages.error(request, "You do not have permission to unpark tags.")
        return get_referrer_or_default(request, default="twf:tags_overview")

    tag = get_object_or_404(PageTag, pk=pk)

    # Capture info before unparking
    tag_variation = tag.variation

    # Save instant task
    save_instant_task_unpark_tag(project, request.user, tag_variation, tag.id)

    tag.is_parked = False
    tag.save(current_user=request.user)
    messages.success(request, f"Tag {pk} has been unparked.")

    return get_referrer_or_default(request, default="twf:tags_overview")


def ungroup_tag(request, pk):
    """Ungroups a tag and removes all processing data (dictionary, enrichment, date)."""
    # Check tag.edit permission
    project = TWFView.s_get_project(request)
    if not check_permission(request.user, "tag.edit", project):
        messages.error(request, "You do not have permission to modify tags.")
        return get_referrer_or_default(request, default="twf:tags_overview")

    tag = get_object_or_404(PageTag, pk=pk)
    tag.dictionary_entry = None
    tag.date_variation_entry = None
    tag.tag_enrichment_entry = None
    tag.save(current_user=request.user)
    messages.success(request, f"Tag {pk} processing data has been removed.")

    return get_referrer_or_default(request, default="twf:tags_overview")


def delete_tag(request, pk):
    """Deletes a tag."""
    # Check tag.manage permission
    project = TWFView.s_get_project(request)
    if not check_permission(request.user, "tag.manage", project):
        messages.error(request, "You do not have permission to delete tags.")
        return get_referrer_or_default(request, default="twf:tags_overview")

    tag = get_object_or_404(PageTag, pk=pk)

    # Capture info before deletion
    tag_variation = tag.variation

    # Save instant task before deletion
    save_instant_task_delete_tag(project, request.user, tag_variation, tag.id)

    tag.delete()
    messages.success(request, f"Tag {pk} has been deleted.")

    return get_referrer_or_default(request, default="twf:tags_overview")


def unpark_tags_by_type(request):
    """Unpark all tags of a specific type."""
    project = TWFView.s_get_project(request)
    tag_type = request.GET.get("type")

    if not tag_type:
        messages.error(request, "No tag type specified.")
        return redirect("twf:tags_manage")

    if not check_permission(request.user, "tag.edit", project):
        messages.error(request, "You do not have permission to unpark tags.")
        return redirect("twf:tags_manage")

    # Unpark all tags of this type
    tags = PageTag.objects.filter(
        page__document__project=project, variation_type=tag_type, is_parked=True
    )
    count = tags.count()
    tags.update(is_parked=False)

    messages.success(request, f"Unparked {count} tags of type '{tag_type}'.")
    return redirect("twf:tags_manage")


def remove_dict_assignments_by_type(request):
    """Remove dictionary assignments for all tags of a specific type."""
    project = TWFView.s_get_project(request)
    tag_type = request.GET.get("type")

    if not tag_type:
        messages.error(request, "No tag type specified.")
        return redirect("twf:tags_manage")

    if not check_permission(request.user, "tag.edit", project):
        messages.error(request, "You do not have permission to modify tags.")
        return redirect("twf:tags_manage")

    # Remove dictionary assignments for this type
    tags = PageTag.objects.filter(
        page__document__project=project,
        variation_type=tag_type,
        dictionary_entry__isnull=False,
    )
    count = tags.count()
    tags.update(dictionary_entry=None)

    messages.success(
        request,
        f"Removed dictionary assignments from {count} tags of type '{tag_type}'.",
    )
    return redirect("twf:tags_manage")


def remove_enrichment_by_type(request):
    """Remove enrichment data for all tags of a specific type."""
    project = TWFView.s_get_project(request)
    tag_type = request.GET.get("type")

    if not tag_type:
        messages.error(request, "No tag type specified.")
        return redirect("twf:tags_manage")

    if not check_permission(request.user, "tag.edit", project):
        messages.error(request, "You do not have permission to modify tags.")
        return redirect("twf:tags_manage")

    # Remove enrichment data for this type (both old and new formats)
    from django.db.models import Q
    tags = PageTag.objects.filter(
        page__document__project=project,
        variation_type=tag_type,
    ).filter(
        Q(tag_enrichment_entry__isnull=False)
        | (Q(enrichment__isnull=False) & ~Q(enrichment={}))
    )
    count = tags.count()
    tags.update(tag_enrichment_entry=None, enrichment={})

    messages.success(
        request, f"Removed enrichment data from {count} tags of type '{tag_type}'."
    )
    return redirect("twf:tags_manage")


def remove_all_dict_assignments(request):
    """Remove all dictionary assignments from all tags in the project."""
    project = TWFView.s_get_project(request)

    if not check_permission(request.user, "tag.edit", project):
        messages.error(request, "You do not have permission to modify tags.")
        return redirect("twf:tags_manage")

    # Remove all dictionary assignments
    tags = PageTag.objects.filter(
        page__document__project=project, dictionary_entry__isnull=False
    )
    count = tags.count()
    tags.update(dictionary_entry=None)

    messages.success(
        request, f"Removed dictionary assignments from {count} tags in the project."
    )
    return redirect("twf:tags_manage")


def remove_all_enrichment(request):
    """Remove all enrichment data from all tags in the project."""
    project = TWFView.s_get_project(request)

    if not check_permission(request.user, "tag.edit", project):
        messages.error(request, "You do not have permission to modify tags.")
        return redirect("twf:tags_manage")

    # Remove all enrichment data (both old and new formats)
    from django.db.models import Q
    tags = PageTag.objects.filter(
        page__document__project=project
    ).filter(
        Q(tag_enrichment_entry__isnull=False)
        | (Q(enrichment__isnull=False) & ~Q(enrichment={}))
    )
    count = tags.count()
    tags.update(tag_enrichment_entry=None, enrichment={})

    messages.success(
        request, f"Removed enrichment data from {count} tags in the project."
    )
    return redirect("twf:tags_manage")


def auto_group_all_tags(request):
    """Automatically assign all unassigned tags to dictionary entries by exact match."""
    project = TWFView.s_get_project(request)

    if not check_permission(request.user, "tag.edit", project):
        messages.error(request, "You do not have permission to modify tags.")
        return redirect("twf:tags_manage")

    # Get all unassigned tags (excluding ignored types)
    excluded_types = get_excluded_types(project)
    unassigned_tags = PageTag.objects.filter(
        page__document__project=project, dictionary_entry__isnull=True
    ).exclude(variation_type__in=excluded_types)

    total = unassigned_tags.count()
    assigned_count = 0

    # Try to assign each tag
    for tag in unassigned_tags:
        if assign_tag(tag, request.user):
            assigned_count += 1

    messages.success(
        request,
        f"Auto-grouped {assigned_count} out of {total} unassigned tags. "
        f"{total - assigned_count} tags could not be matched to dictionary entries.",
    )
    return redirect("twf:tags_manage")


def auto_group_tags_by_type(request):
    """Automatically assign unassigned tags of a specific type to dictionary entries."""
    project = TWFView.s_get_project(request)
    tag_type = request.GET.get("type")

    if not tag_type:
        messages.error(request, "No tag type specified.")
        return redirect("twf:tags_manage")

    if not check_permission(request.user, "tag.edit", project):
        messages.error(request, "You do not have permission to modify tags.")
        return redirect("twf:tags_manage")

    # Get unassigned tags of this type
    unassigned_tags = PageTag.objects.filter(
        page__document__project=project,
        variation_type=tag_type,
        dictionary_entry__isnull=True,
    )

    total = unassigned_tags.count()
    assigned_count = 0

    # Try to assign each tag
    for tag in unassigned_tags:
        if assign_tag(tag, request.user):
            assigned_count += 1

    messages.success(
        request,
        f"Auto-grouped {assigned_count} out of {total} unassigned '{tag_type}' tags. "
        f"{total - assigned_count} tags could not be matched to dictionary entries.",
    )
    return redirect("twf:tags_manage")
