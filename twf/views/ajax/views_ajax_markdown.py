"""Views for AJAX requests related to Markdown processing."""

import json

from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from markdown import markdown

from twf.models import Project
from twf.clients.zenodo_client import create_project_md


@csrf_exempt
def ajax_markdown_generate(request):
    """Generates a default markdown description for a project."""
    if request.method == "POST":
        data = json.loads(request.body)
        project_id = data.get("project_id")
        try:
            project = Project.objects.get(id=project_id)
            project_md = create_project_md(project)
            return HttpResponse(project_md, content_type="text/plain")
        except Project.DoesNotExist:
            return JsonResponse({"error": "Project not found"}, status=404)
    return JsonResponse({"error": "Invalid request"}, status=400)


@csrf_exempt
def ajax_markdown_preview(request):
    """Returns rendered HTML from Markdown input."""
    if request.method == "POST":
        data = json.loads(request.body)
        markdown_text = data.get("text", "")

        html_output = markdown(markdown_text)
        return HttpResponse(html_output, content_type="text/html")
    return JsonResponse({"error": "Invalid request"}, status=400)
