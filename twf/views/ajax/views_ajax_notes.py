"""
AJAX views for handling notes operations.

This module contains AJAX endpoints for saving and managing notes,
including saving AI query results as notes.
"""

import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from twf.models import Note
from twf.tasks.instant_tasks import save_instant_task_create_note
from twf.views.views_base import TWFView


@csrf_exempt  # Using csrf_exempt since we're handling the token manually in JavaScript
def save_ai_result_as_note(request):
    """
    Save an AI query result as a project note.

    This endpoint accepts a POST request with the AI result text
    and creates a new Note object associated with the current project.

    Args:
        request: The HTTP request object containing POST data with the AI result

    Returns:
        JsonResponse: A JSON response indicating success or failure
    """
    if request.method == "POST":
        data = json.loads(request.body)
        ai_result = data.get("ai_result")

        if not ai_result:
            return JsonResponse({"error": "No AI result provided"}, status=400)

        project = TWFView.s_get_project(request)

        # Create a new note with the AI result
        note = Note(project=project, title=ai_result[:20], note=ai_result)
        note.save(current_user=request.user)

        # Save instant task
        save_instant_task_create_note(project, request.user, note.title, note.id)

        return JsonResponse({"success": True, "note_id": note.id}, status=200)

    return JsonResponse({"error": "Invalid request"}, status=400)
