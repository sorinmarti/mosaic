"""Views for AI Configuration management."""

import json
import logging

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.views.generic import (
    ListView,
    CreateView,
    UpdateView,
    DetailView,
    DeleteView,
    FormView,
)

from twf.forms.project.ai_config_forms import (
    AIConfigurationForm,
    AIConfigurationTestForm,
)
from twf.models import AIConfiguration
from twf.tasks.instant_tasks import (
    save_instant_task_create_ai_config,
    save_instant_task_delete_ai_config,
    save_instant_task_update_ai_config,
)
from twf.views.project.views_project import TWFProjectView
from twf.views.views_base import ProjectPermissionMixin

logger = logging.getLogger(__name__)


class TWFProjectAIConfigsView(ProjectPermissionMixin, ListView, TWFProjectView):
    """List all AI configurations for the project."""
    required_permission = "ai.manage"

    model = AIConfiguration
    template_name = "twf/project/ai_configs/list.html"
    page_title = "AI Configurations"
    context_object_name = "ai_configs"
    paginate_by = None  # No pagination for now

    def get_queryset(self):
        """Get AI configurations for the current project."""
        return AIConfiguration.objects.filter(
            project=self.get_project()
        ).order_by("-is_active", "name")

    def get(self, request, *args, **kwargs):
        """Handle GET requests."""
        # Set up object_list explicitly (required for ListView)
        self.object_list = self.get_queryset()

        # Get context and render response
        context = self.get_context_data()
        return self.render_to_response(context)


class TWFProjectAIConfigCreateView(ProjectPermissionMixin, CreateView, TWFProjectView):
    """Create a new AI configuration."""
    required_permission = "ai.manage"

    model = AIConfiguration
    form_class = AIConfigurationForm
    template_name = "twf/project/ai_configs/form.html"
    page_title = "Create AI Configuration"

    def get(self, request, *args, **kwargs):
        """Handle GET requests."""
        self.object = None  # Required for CreateView
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """Handle POST requests."""
        self.object = None  # Required for CreateView
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        """Set the project before saving."""
        form.instance.project = self.get_project()
        form.instance.created_by = self.request.user
        form.instance.modified_by = self.request.user
        messages.success(
            self.request,
            f"AI Configuration '{form.instance.name}' created successfully.",
        )
        self.object = form.save()

        # Save instant task
        save_instant_task_create_ai_config(
            self.get_project(), self.request.user, self.object.name, self.object.id
        )

        return redirect("twf:project_ai_config_detail", pk=self.object.pk)

    def get_context_data(self, **kwargs):
        """Add context data."""
        context = super().get_context_data(**kwargs)
        context["is_create"] = True
        return context


class TWFProjectAIConfigEditView(ProjectPermissionMixin, UpdateView, TWFProjectView):
    """Edit an existing AI configuration."""
    required_permission = "ai.manage"

    model = AIConfiguration
    form_class = AIConfigurationForm
    template_name = "twf/project/ai_configs/form.html"
    page_title = "Edit AI Configuration"

    def get_queryset(self):
        """Only allow editing configs from current project."""
        return AIConfiguration.objects.filter(project=self.get_project())

    def get(self, request, *args, **kwargs):
        """Handle GET requests."""
        self.object = self.get_object()  # Required for UpdateView
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """Handle POST requests."""
        self.object = self.get_object()  # Required for UpdateView
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        """Update modified_by before saving."""
        form.instance.modified_by = self.request.user

        # Track what changed
        changes = ", ".join(form.changed_data) if form.changed_data else "configuration updated"

        messages.success(
            self.request,
            f"AI Configuration '{form.instance.name}' updated successfully.",
        )
        self.object = form.save()

        # Save instant task
        save_instant_task_update_ai_config(
            self.get_project(), self.request.user, self.object.name, self.object.id, changes
        )

        return redirect("twf:project_ai_config_detail", pk=self.object.pk)

    def get_context_data(self, **kwargs):
        """Add context data."""
        context = super().get_context_data(**kwargs)
        context["is_create"] = False
        return context


class TWFProjectAIConfigDetailView(ProjectPermissionMixin, DetailView, TWFProjectView):
    """View details of an AI configuration."""
    required_permission = "ai.manage"

    model = AIConfiguration
    template_name = "twf/project/ai_configs/detail.html"
    context_object_name = "ai_config"

    def get_queryset(self):
        """Only show configs from current project."""
        return AIConfiguration.objects.filter(project=self.get_project())

    def get(self, request, *args, **kwargs):
        """Handle GET requests."""
        self.object = self.get_object()  # Required for DetailView
        return super().get(request, *args, **kwargs)

    def get_page_title(self):
        """Dynamic page title."""
        return f"AI Config: {self.object.name}"


class TWFProjectAIConfigDeleteView(ProjectPermissionMixin, DeleteView, TWFProjectView):
    """Delete an AI configuration."""
    required_permission = "ai.manage"

    model = AIConfiguration
    template_name = "twf/project/ai_configs/delete.html"
    context_object_name = "ai_config"

    def get_queryset(self):
        """Only allow deleting configs from current project."""
        return AIConfiguration.objects.filter(project=self.get_project())

    def get(self, request, *args, **kwargs):
        """Handle GET requests."""
        self.object = self.get_object()  # Required for DeleteView
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """Handle POST requests."""
        self.object = self.get_object()  # Required for DeleteView
        return super().post(request, *args, **kwargs)

    def get_success_url(self):
        """Redirect to list view after deletion."""
        return reverse("twf:project_ai_configs")

    def delete(self, request, *args, **kwargs):
        """Add success message and save instant task."""
        ai_config = self.object

        # Save instant task before deletion
        save_instant_task_delete_ai_config(
            self.get_project(), request.user, ai_config.name, ai_config.id
        )

        messages.success(
            request, f"AI Configuration '{ai_config.name}' deleted successfully."
        )
        return super().delete(request, *args, **kwargs)


class TWFProjectAIConfigTestView(ProjectPermissionMixin, FormView, TWFProjectView):
    """Test an AI configuration with sample context."""
    required_permission = "ai.manage"

    form_class = AIConfigurationTestForm
    template_name = "twf/project/ai_configs/test.html"

    def get_ai_config(self):
        """Get the AI configuration being tested."""
        return get_object_or_404(
            AIConfiguration,
            pk=self.kwargs["pk"],
            project=self.get_project(),
        )

    def get_page_title(self):
        """Dynamic page title."""
        return f"Test: {self.get_ai_config().name}"

    def get_context_data(self, **kwargs):
        """Add AI config to context."""
        context = super().get_context_data(**kwargs)
        context["ai_config"] = self.get_ai_config()
        return context

    def form_valid(self, form):
        """Execute the AI config with test context."""
        ai_config = self.get_ai_config()
        test_context = form.cleaned_data["test_context"]

        try:
            # Execute the configuration
            response, duration = ai_config.execute(test_context)

            messages.success(
                self.request,
                f"Test successful! Response received in {duration:.2f} seconds.",
            )

            # Store result in session for display
            self.request.session["test_result"] = {
                "response": response,
                "duration": duration,
                "context": test_context,
            }

        except Exception as e:
            logger.error(f"AI config test failed: {e}")
            messages.error(
                self.request,
                f"Test failed: {str(e)}",
            )

        return redirect("twf:project_ai_config_test", pk=ai_config.pk)


def ajax_test_ai_config(request, pk):
    """AJAX endpoint for testing AI configuration."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        # Get project from session
        project_id = request.session.get("current_project")
        if not project_id:
            return JsonResponse({"error": "No project selected"}, status=400)

        # Get AI config
        ai_config = get_object_or_404(
            AIConfiguration,
            pk=pk,
            project_id=project_id,
        )

        # Get test context from request
        try:
            test_context = json.loads(request.POST.get("test_context", "{}"))
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON in test context"}, status=400)

        # Execute the configuration
        response, duration = ai_config.execute(test_context)

        return JsonResponse(
            {
                "success": True,
                "response": response,
                "duration": duration,
                "message": f"Test successful! Response received in {duration:.2f} seconds.",
            }
        )

    except Exception as e:
        logger.error(f"AI config AJAX test failed: {e}")
        return JsonResponse({"error": str(e)}, status=500)
