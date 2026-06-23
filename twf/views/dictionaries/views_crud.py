from django.contrib import messages
from django.shortcuts import get_object_or_404

from twf.models import Dictionary, DictionaryEntry, PageTag, Variation
from twf.permissions import check_permission
from twf.tasks.instant_tasks import (
    save_instant_task_add_dictionary,
    save_instant_task_remove_dictionary_from_project,
    save_instant_task_delete_dictionary_entry,
    save_instant_task_delete_variation,
)
from twf.views.views_base import TWFView, get_referrer_or_default


def remove_dictionary_from_project(request, pk):
    """Remove a dictionary from the project."""
    # Check dictionary.manage permission
    project = TWFView.s_get_project(request)
    if not check_permission(request.user, "dictionary.manage", project):
        messages.error(request, "You do not have permission to manage dictionaries.")
        return get_referrer_or_default(request, default="twf:dictionaries")

    dictionary = get_object_or_404(Dictionary, pk=pk)
    project = TWFView.s_get_project(request)

    # Save instant task before removing
    save_instant_task_remove_dictionary_from_project(
        project, request.user, dictionary.label, dictionary.id
    )

    project.selected_dictionaries.remove(dictionary)
    project.save(current_user=request.user)

    messages.success(
        request, f"Dictionary {dictionary.label} has been removed from your project."
    )

    return get_referrer_or_default(request, default="twf:dictionaries")


def delete_variation(request, pk):
    """Delete a variation."""
    # Check dictionary.edit permission
    project = TWFView.s_get_project(request)
    if not check_permission(request.user, "dictionary.edit", project):
        messages.error(request, "You do not have permission to edit dictionary entries.")
        return get_referrer_or_default(request, default="twf:dictionaries")

    variation = get_object_or_404(Variation, pk=pk)

    # Capture info before deletion
    variation_text = variation.variation
    entry_label = variation.entry.label if variation.entry else "Unknown"

    # Save instant task before deletion
    save_instant_task_delete_variation(
        project, request.user, variation_text, variation.id, entry_label
    )

    all_page_tags = PageTag.objects.filter(variation=variation)
    for page_tag in all_page_tags:
        page_tag.dictionary_entry = None
        page_tag.save()

    variation.delete()
    messages.success(request, f"Variation {pk} has been deleted.")

    return get_referrer_or_default(request, default="twf:dictionaries")


def delete_entry(request, pk):
    """Delete a dictionary entry."""
    # Check dictionary.manage permission
    project = TWFView.s_get_project(request)
    if not check_permission(request.user, "dictionary.manage", project):
        messages.error(request, "You do not have permission to delete dictionary entries.")
        return get_referrer_or_default(request, default="twf:dictionaries")

    entry = get_object_or_404(DictionaryEntry, pk=pk)

    # Capture info before deletion
    entry_label = entry.label
    dictionary_label = entry.dictionary.label if entry.dictionary else "Unknown"

    # Save instant task before deletion
    save_instant_task_delete_dictionary_entry(
        project, request.user, entry_label, entry.id, dictionary_label
    )

    entry.delete()
    messages.success(request, f"Dictionary entry {pk} has been deleted.")

    return get_referrer_or_default(request, default="twf:dictionaries")


def skip_entry(request, pk):
    """Skip a dictionary entry."""
    # Check dictionary.edit permission
    project = TWFView.s_get_project(request)
    if not check_permission(request.user, "dictionary.edit", project):
        messages.error(request, "You do not have permission to edit dictionary entries.")
        return get_referrer_or_default(request, default="twf:dictionaries")

    entry = get_object_or_404(DictionaryEntry, pk=pk)
    entry.save(current_user=request.user)
    messages.success(request, f"Dictionary entry {pk} has been skipped.")

    return get_referrer_or_default(request, default="twf:dictionaries")


def add_dictionary_to_project(request, pk):
    """Add a dictionary to the project."""
    # Check dictionary.manage permission
    project = TWFView.s_get_project(request)
    if not check_permission(request.user, "dictionary.manage", project):
        messages.error(request, "You do not have permission to manage dictionaries.")
        return get_referrer_or_default(request, default="twf:dictionaries")

    dictionary = get_object_or_404(Dictionary, pk=pk)
    project = TWFView.s_get_project(request)
    project.selected_dictionaries.add(dictionary)
    project.save(current_user=request.user)

    save_instant_task_add_dictionary(
        project, request.user, f"Added dictionary {dictionary.label} to project"
    )

    messages.success(
        request, f"Dictionary {dictionary.label} has been added to your project."
    )

    return get_referrer_or_default(request, default="twf:dictionaries")


def delete_dictionary_entry(request, pk):
    """Delete a dictionary entry."""
    # Check dictionary.manage permission
    project = TWFView.s_get_project(request)
    if not check_permission(request.user, "dictionary.manage", project):
        messages.error(request, "You do not have permission to delete dictionary entries.")
        return get_referrer_or_default(request, default="twf:dictionaries")

    entry = get_object_or_404(DictionaryEntry, pk=pk)

    # Capture info before deletion
    entry_label = entry.label
    dictionary_label = entry.dictionary.label if entry.dictionary else "Unknown"

    # Save instant task before deletion
    save_instant_task_delete_dictionary_entry(
        project, request.user, entry_label, entry.id, dictionary_label
    )

    entry.delete()
    messages.success(request, f"Dictionary entry {pk} has been deleted.")

    return get_referrer_or_default(request, default="twf:dictionaries")
