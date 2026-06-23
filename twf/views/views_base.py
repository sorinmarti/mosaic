"""
Base views for all TWF views.

This module contains the base view classes used throughout the application,
including the foundation for AI interactions with both text-only and 
multimodal (text + images) capabilities.
"""

from abc import ABC, abstractmethod

from django.contrib import messages
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.template import TemplateDoesNotExist
from django.template.loader import get_template
from django.urls import reverse
from django.views.generic import TemplateView, FormView
from django.conf import settings
from twf.models import Project
from twf.permissions import check_permission


def get_referrer_or_default(request, default="twf:home", kwargs=None):
    """Get the referrer URL or a default URL."""
    redirect_to_view = request.GET.get("redirect_to_view")
    if redirect_to_view:
        return redirect(redirect_to_view)

    referer = request.META.get("HTTP_REFERER")
    if referer:
        return HttpResponseRedirect(referer)

    if kwargs:
        return redirect(default, **kwargs)
    return redirect(default)


class ProjectPermissionMixin:
    """
    Mixin to enforce permission checking on project-related views.

    Usage:
        class MyView(ProjectPermissionMixin, TWFProjectView):
            required_permission = "document.edit"
            # ... rest of view

    Attributes:
        required_permission (str): The permission required to access this view.
            Should be in format "entity_type.permission_level" (e.g., "document.edit").
            If None, no permission check is performed.
        permission_denied_message (str): Custom message to display when permission is denied.
            If None, a default message is used.
        permission_denied_redirect (str): URL name to redirect to when permission is denied.
            Defaults to "twf:project_overview".
    """

    required_permission = None
    permission_denied_message = None
    permission_denied_redirect = "twf:project_overview"

    def dispatch(self, request, *args, **kwargs):
        """
        Check required permission before dispatching the request.

        If required_permission is set and the user doesn't have it,
        redirect with an error message.
        """
        if self.required_permission:
            # Get the project context (assumes view has get_project method)
            project = self.get_project() if hasattr(self, 'get_project') else None

            # Check permission
            if not check_permission(request.user, self.required_permission, project):
                # Use custom message or generate a default one
                if self.permission_denied_message:
                    message = self.permission_denied_message
                else:
                    message = f"You do not have permission to access this page. Required permission: {self.required_permission}"

                messages.error(request, message)
                return redirect(self.permission_denied_redirect)

        return super().dispatch(request, *args, **kwargs)


class TWFView(TemplateView, ABC):
    """
    Base view for all TWF views.

    This abstract base class provides common functionality for all views in the TWF application,
    including project context, navigation, breadcrumbs, and help content integration.
    """

    project_required = True
    page_title = None
    navigation_anchor = None
    show_context_help = True  # Flag to control visibility of the context help button

    def __init__(self, *args, **kwargs):
        """
        Initialize the TWF view.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
                page_title: The title of the page.
        """
        super().__init__(*args, **kwargs)
        if self.page_title is None:
            self.page_title = kwargs.get("page_title", None)

    def dispatch(self, request, *args, **kwargs):
        """
        Dispatch the request.

        This method checks if a project is required and set before proceeding.

        Args:
            request: The HTTP request.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            HttpResponse: The HTTP response.
        """
        if self.project_required:
            project = self.get_project()
            if project is None:
                messages.error(request, "No project is set. Select a project first")
                return redirect("twf:home")  # Redirect if no project is set
        return super().dispatch(request, *args, **kwargs)

    def is_project_set(self):
        """
        Check if a project is set.

        Returns:
            bool: True if a project is set, False otherwise.
        """
        return self.s_is_project_set(self.request)

    @staticmethod
    def s_is_project_set(request):
        """
        Check if a project is set (static method).

        Args:
            request: The HTTP request.

        Returns:
            bool: True if a project is set, False otherwise.
        """
        return request.session.get("project_id", None) is not None

    def get_project(self):
        """
        Get the current project.

        Returns:
            Project: The current project or None if not set.
        """
        return self.s_get_project(self.request)

    @staticmethod
    def s_get_project(request):
        """
        Get the current project (static method).

        Args:
            request: The HTTP request.

        Returns:
            Project: The current project or None if not set.
        """
        project = None
        if TWFView.s_is_project_set(request):
            project_id = request.session.get("project_id")
            try:
                project = Project.objects.get(pk=project_id)
            except Project.DoesNotExist:
                request.session["project_id"] = None
        return project

    def get_breadcrumbs(self):
        """
        Get the breadcrumbs for the current page.

        Returns:
            list: A list of breadcrumb items, each with 'url' and 'value' keys.
        """
        breadcrumbs = [
            {"url": reverse("twf:home"), "value": '<i class="fas fa-home"></i>'},
        ]
        if len(self.get_navigation_items()) > self.get_navigation_index() > 0:
            breadcrumbs.append(self.get_navigation_items()[self.get_navigation_index()])

        # Only add current page if it has a `page_title` and isn't already part of the nav
        if hasattr(self, "page_title") and self.page_title != breadcrumbs[-1]["value"]:
            breadcrumbs.append(
                {
                    "value": self.page_title,
                    "url": self.request.path,
                }
            )

        return breadcrumbs

    def get_navigation_items(self):
        """
        Get the main navigation items.

        Returns:
            list: A list of navigation items, each with 'url' and 'value' keys.
        """
        if not self.is_project_set():
            return [
                {"url": reverse("twf:home"), "value": "Home", "active": True},
            ]

        nav = [
            {"url": reverse("twf:home"), "value": "Home"},
            {"url": reverse("twf:project_overview"), "value": "Project"},
            {"url": reverse("twf:documents_overview"), "value": "Documents"},
            {"url": reverse("twf:tags_overview"), "value": "Tags"},
            {"url": reverse("twf:metadata_overview"), "value": "Metadata"},
            {"url": reverse("twf:dictionaries_overview"), "value": "Dictionaries"},
            {"url": reverse("twf:collections"), "value": "Collections"},
            {"url": reverse("twf:export_overview"), "value": "Import/Export"},
        ]
        return nav

    @abstractmethod
    def get_sub_navigation(self):
        """
        Get the sub-navigation items.

        This method must be implemented by subclasses.

        Returns:
            list: A list of sub-navigation items.
        """

    @abstractmethod
    def get_navigation_index(self):
        """
        Get the index of the active navigation item.

        This method must be implemented by subclasses.

        Returns:
            int: The index of the active navigation item.
        """

    def get_context_data(self, **kwargs):
        """
        Get the context data for the template.

        This method adds common context data like project, navigation, breadcrumbs, etc.

        Args:
            **kwargs: Arbitrary keyword arguments.

        Returns:
            dict: The context data.
        """
        context = super().get_context_data(**kwargs)

        context.update(
            {
                "page_title": self.page_title,
                "project_set": self.is_project_set(),
                "project": self.get_project(),
                "breadcrumbs": self.get_breadcrumbs(),
                "navigation": {
                    "items": self.get_navigation_items(),
                },
                "context_nav": {"groups": self.get_sub_navigation()},
                "navigation_anchor": self.navigation_anchor,
                "show_context_help": self.show_context_help,  # Add the flag to the context
                "version": settings.TWF_VERSION,
            }
        )

        if len(context["navigation"]["items"]) > self.get_navigation_index():
            context["navigation"]["items"][self.get_navigation_index()]["active"] = True
        return context


def help_content(request, view_name):
    """
    Get the help content for a specific view.

    Args:
        request: The HTTP request.
        view_name: The name of the view to get help content for.

    Returns:
        HttpResponse: The HTML content for the help overlay.
    """
    template_path = f"twf/help/{view_name}.html"
    try:
        template = get_template(template_path)
        return HttpResponse(template.render({}, request))
    except TemplateDoesNotExist:
        return HttpResponse("<p>Help content not found.</p>", status=404)


class AIFormView(FormView):
    """
    Base view for AI interaction forms.

    This view provides a foundation for all AI-related forms in the application,
    including multimodal forms that can process both text and images. It handles:

    1. Proper form initialization with project context
    2. AI credential validation
    3. Task URL and confirmation message setup
    4. Support for multimodal (text + images) capabilities

    The multimodal support allows:
    - Configuring forms with provider-specific multimodal capabilities
    - Handling different prompt modes (text-only, images-only, text+images)
    - Automating the collection and processing of document images
    - Providing appropriate context data for the template

    When extended by specific AI provider views (like TWFProjectOpenAIView),
    it configures the appropriate form with the project's credentials and
    starts the correct Celery task when the form is submitted.

    Attributes:
        start_url (str): The URL to start the AI task
        message (str): Confirmation message to display before starting the task
    """

    start_url = None
    message = None

    def get_form_kwargs(self):
        """
        Prepare keyword arguments for the form initialization.

        This method extends the standard form kwargs with project-specific
        information and AI task configuration parameters. For multimodal forms,
        it can also pass the multimodal_support flag based on the provider.

        Returns:
            dict: Dictionary of keyword arguments for the form, including:
                - project: The current Project object
                - data-start-url: URL to start the AI task
                - data-message: Confirmation message to display
                - multimodal_support: (Optional) Boolean indicating multimodal support
        """
        kwargs = super().get_form_kwargs()
        kwargs["project"] = self.get_project()

        kwargs["data-start-url"] = self.start_url
        kwargs["data-message"] = self.message

        return kwargs

    def get_ai_credentials(self, client_name):
        """
        Get the AI credentials for a specific provider from the project.

        This method retrieves the credentials needed to interact with the specified
        AI provider, including API keys and default model settings.

        Args:
            client_name (str): The name of the AI provider to get credentials for
                              ('openai', 'genai', 'anthropic', or 'mistral')

        Returns:
            dict: A dictionary containing the credentials for the specified provider,
                 typically including 'api_key' and 'default_model' keys
        """
        project = self.get_project()
        if project is None:
            return {}
        return project.get_credentials(client_name)

    def has_ai_credentials(self, client_name):
        """
        Check if valid AI credentials are set for a specific provider.

        This method verifies that both an API key and a default model are
        configured for the specified AI provider. It's used to determine
        if the AI provider can be used for queries.

        Args:
            client_name (str): The name of the AI provider to check
                              ('openai', 'genai', 'anthropic', or 'mistral')

        Returns:
            bool: True if both api_key and default_model are set, False otherwise
        """
        creds = self.get_ai_credentials(client_name)
        if creds is None:
            return False

        if "api_key" in creds and creds["api_key"]:
            if "default_model" in creds and creds["default_model"]:
                return True

        return False

    def get_provider_name(self):
        """
        Get the name of the AI provider for this view.

        This method should be overridden by provider-specific views to return
        the appropriate provider name.

        Returns:
            str: The name of the AI provider ('openai', 'claude', 'gemini', 'mistral')
        """
        return None

    def get_task_function(self):
        """
        Get the task function to call when the form is submitted.

        This method should be overridden by provider-specific views to return
        the appropriate task function.

        Returns:
            function: The task function to call
        """
        return None

    def form_valid(self, form):
        """
        Process the valid form submission.

        This method is called when the form has been successfully validated.
        It extracts the form data and starts the appropriate AI task.
        For multimodal forms, it includes the prompt_mode parameter.

        Args:
            form: The validated form.

        Returns:
            HttpResponse: The HTTP response, usually a redirect to the task monitor.
        """
        # This method should be implemented by provider-specific views
        return super().form_valid(form)
