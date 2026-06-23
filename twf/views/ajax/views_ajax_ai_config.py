"""AJAX views for AI Configuration operations."""

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from twf.models import AIConfiguration
from twf.views.views_base import TWFView


@require_http_methods(["GET"])
def load_ai_configuration(request, config_id):
    """
    Load an AI configuration by ID and return its data as JSON.

    Args:
        request: HTTP request object
        config_id: ID of the AI configuration to load

    Returns:
        JsonResponse with configuration data or error message
    """
    project = TWFView.s_get_project(request)

    if not project:
        return JsonResponse({"error": "No project selected"}, status=400)

    # Get the AI configuration
    ai_config = get_object_or_404(
        AIConfiguration,
        id=config_id,
        project=project
    )

    # Return configuration data
    return JsonResponse({
        "id": ai_config.id,
        "name": ai_config.name,
        "description": ai_config.description,
        "provider": ai_config.provider,
        "model": ai_config.model,
        "system_role": ai_config.system_role,
        "prompt_template": ai_config.prompt_template,
        "temperature": float(ai_config.temperature) if ai_config.temperature else 0.7,
        "max_tokens": ai_config.max_tokens if ai_config.max_tokens else 1000,
        "top_p": float(ai_config.top_p) if ai_config.top_p else 1.0,
        "frequency_penalty": float(ai_config.frequency_penalty) if ai_config.frequency_penalty else 0.0,
        "presence_penalty": float(ai_config.presence_penalty) if ai_config.presence_penalty else 0.0,
    }, status=200)