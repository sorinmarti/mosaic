import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from twf.clients.geonames_client import search_location
from twf.clients.gnd_client import search_gnd
from twf.clients.wikidata_client import search_wikidata_entities
from twf.models import Dictionary, DictionaryEntry, PageTag, Variation
from twf.permissions import check_permission
from twf.tasks.instant_tasks import (
    save_instant_task_add_dictionary,
    save_instant_task_remove_dictionary_from_project,
    save_instant_task_delete_dictionary_entry,
    save_instant_task_delete_variation,
)
from twf.utils.metadata_utils import set_nested_value, delete_nested_key
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


@login_required
def update_dictionary_entry_metadata(request, pk, base_key):
    """Update a single metadata value on a DictionaryEntry."""
    if request.method == "POST":
        data = json.loads(request.body)
        key = data.get("key")
        value = data.get("value")

        try:
            entry = DictionaryEntry.objects.get(pk=pk)
            base = entry.metadata.get(base_key, {})
            set_nested_value(base, key, value)
            entry.metadata[base_key] = base
            entry.save(current_user=request.user)
        except DictionaryEntry.DoesNotExist:
            return JsonResponse({"error": "DictionaryEntry does not exist."}, status=404)

        return JsonResponse({"new_value": value})


@csrf_exempt
def delete_dictionary_entry_metadata(request, pk, base_key):
    """Delete a single metadata key from a DictionaryEntry."""
    if request.method == "POST":
        key = None
        if request.body.strip():
            try:
                data = json.loads(request.body)
                key = data.get("key") or None
            except json.JSONDecodeError:
                pass

        try:
            entry = DictionaryEntry.objects.get(pk=pk)
            if key:
                base = entry.metadata.get(base_key, {})
                delete_nested_key(base, key)
                entry.metadata[base_key] = base
            else:
                entry.metadata.pop(base_key, None)
            entry.save(current_user=request.user)
        except DictionaryEntry.DoesNotExist:
            return JsonResponse({"error": "DictionaryEntry does not exist."}, status=404)
        except KeyError:
            return JsonResponse({"error": "Key does not exist."}, status=404)

        return JsonResponse({"success": True})


@login_required
def save_entry_metadata_json(request, pk):
    """Replace the full metadata JSONField of a DictionaryEntry with submitted raw JSON."""
    entry = get_object_or_404(DictionaryEntry, pk=pk)

    if request.method == "POST":
        raw = request.POST.get("metadata_json", "").strip()
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError("Metadata must be a JSON object.")
        except (json.JSONDecodeError, ValueError) as exc:
            messages.error(request, f"Invalid JSON: {exc}")
            return get_referrer_or_default(request, default='twf:dictionaries')

        entry.metadata = parsed
        entry.save(current_user=request.user)
        messages.success(request, "Metadata updated successfully.")

    return get_referrer_or_default(request, default='twf:dictionaries')


@login_required
def search_entry_geonames(request, pk):
    """Synchronous Geonames search for a dictionary entry — returns multiple candidates as JSON."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    entry = get_object_or_404(DictionaryEntry, pk=pk)
    project = TWFView.s_get_project(request)

    data = json.loads(request.body) if request.body else {}
    search_term = data.get('search_term') or entry.label
    country = data.get('country') or None
    threshold = int(data.get('threshold', 80))

    geonames_username = project.get_credentials('geonames').get('username', '')
    if not geonames_username:
        return JsonResponse({'error': 'Geonames username not configured in project settings.'}, status=400)

    try:
        raw = search_location(search_term, geonames_username, False, country, threshold)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)

    if not raw:
        return JsonResponse({'results': []})

    results = [{'data': loc, 'similarity': sim} for loc, sim in raw]
    return JsonResponse({'results': results})


@login_required
def search_entry_gnd(request, pk):
    """Synchronous GND search for a dictionary entry — returns multiple candidates as JSON."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    entry = get_object_or_404(DictionaryEntry, pk=pk)
    data = json.loads(request.body) if request.body else {}
    search_term = data.get('search_term') or entry.label
    earliest = data.get('earliest_birth_year')
    latest = data.get('latest_birth_year')
    show_empty = bool(data.get('show_empty', False))

    try:
        results = search_gnd(
            search_term,
            earliest_birth_year=int(earliest) if earliest else None,
            latest_birth_year=int(latest) if latest else None,
            show_empty=show_empty,
        )
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)

    return JsonResponse({'results': results or []})


@login_required
def search_entry_wikidata(request, pk):
    """Synchronous Wikidata search for a dictionary entry — returns multiple candidates as JSON."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    entry = get_object_or_404(DictionaryEntry, pk=pk)
    data = json.loads(request.body) if request.body else {}
    search_term = data.get('search_term') or entry.label
    entity_type = data.get('entity_type', 'person')
    language = data.get('language', 'en')

    try:
        results = search_wikidata_entities(search_term, entity_type, language)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)

    if results:
        for r in results:
            if isinstance(r.get('coordinates'), tuple):
                r['coordinates'] = list(r['coordinates'])

    return JsonResponse({'results': results or []})


@login_required
def save_entry_lookup(request, pk):
    """Save a user-selected authority file result to a dictionary entry's metadata."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    entry = get_object_or_404(DictionaryEntry, pk=pk)
    data = json.loads(request.body)
    provider = data.get('provider')
    result_data = data.get('data')

    if not provider or result_data is None:
        return JsonResponse({'error': 'provider and data are required'}, status=400)

    entry.metadata[provider] = result_data
    entry.save(current_user=request.user)

    return JsonResponse({'success': True})
