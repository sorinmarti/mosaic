"""Views for the home section of the TWF application."""

import json
import time

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.http import StreamingHttpResponse
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils.crypto import get_random_string
from django.utils.timezone import now, timedelta
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import FormView
from django_filters.views import FilterView
from django_tables2 import SingleTableView

from twf.clients.health_check import check_service_status, TWF_EXTERNAL_SERVICES
from twf.forms.filters.filters import ProjectFilter, UserFilter
from twf.forms.project.project_forms import CreateProjectForm
from twf.forms.user_forms import (
    LoginForm,
    ChangePasswordForm,
    UserProfileForm,
    CreateUserForm,
)
from twf.models import (
    Project,
    Document,
    Page,
    Dictionary,
    DictionaryEntry,
    PageTag,
    Variation,
    DateVariation,
    UserProfile,
    User,
    Task,
    CollectionItem,
)
from twf.permissions import check_permission
from twf.tables.tables_home import ProjectManagementTable, UserManagementTable
from twf.tasks.instant_tasks import save_instant_task_create_project
from twf.utils.mail_utils import send_welcome_email
from twf.utils.project_statistics import get_document_statistics
from twf.views.views_base import TWFView


class TWFHomeView(TWFView):
    """Base view for the home view."""

    project_required = False

    """Base view for the home view."""
    template_name = None

    def get_sub_navigation(self):
        """Get the sub navigation for the home pages."""
        sub_nav = [
            {
                "name": "MOSAIC",
                "options": [
                    {"url": reverse("twf:home"), "value": "Home"},
                    {"url": reverse("twf:about"), "value": "About"},
                ],
            },
            {"name": "User Options", "options": self.get_user_options()},
            {"name": "Administrator Options", "options": self.get_admin_options()},
        ]
        return sub_nav

    def get_user_options(self):
        """Get the user options."""
        user = self.request.user

        if user.is_authenticated:
            nav = []
            if self.is_project_set():
                nav = [
                    {"url": reverse("twf:project_list"), "value": "Change Project"},
                ]

            nav += [
                {"url": reverse("twf:user_overview"), "value": "Your Profile"},
                {"url": reverse("twf:user_logout"), "value": "Logout"},
            ]

            return nav

        return [
            {"url": reverse("twf:login"), "value": "Login"},
        ]

    def get_admin_options(self):
        """Get the admin options."""
        user = self.request.user
        nav = []

        if user.is_superuser or user.is_staff:
            nav.append(
                {"url": reverse("twf:project_create"), "value": "Create Project"}
            )
            nav.append(
                {
                    "url": reverse("twf:project_management"),
                    "value": "Project Management",
                }
            )
            nav.append(
                {"url": reverse("twf:twf_user_management"), "value": "User Management"}
            )
            nav.append(
                {"url": reverse("twf:twf_system_health"), "value": "System Health"}
            )
            nav.append({"url": reverse("admin:index"), "value": "Admin Interface"})

        return nav

    def get_navigation_index(self):
        return 0

    def get_context_data(self, **kwargs):
        """Add the active item to the navigation."""
        context = super().get_context_data(**kwargs)
        return context

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.page_title is None:
            self.page_title = kwargs.get("page_title", "Home View")


class TWFHomeIndexView(TWFHomeView):
    """View for the home page."""

    template_name = "twf/home/home.html"
    page_title = "Home"
    show_context_help = False  # Disable context help for the home page

    def get_context_data(self, **kwargs):
        """Add the active item to the navigation."""
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            # Get the projects the user is a member of
            context["projects"] = self.request.user.profile.get_projects()

        return context

    def get_breadcrumbs(self):
        """Get the breadcrumbs."""
        breadcrumbs = [
            {"url": reverse("twf:home"), "value": '<i class="fas fa-home"></i>'},
        ]
        return breadcrumbs


class TWFProjectListView(LoginRequiredMixin, TWFHomeView):
    """View to list all available projects for the user to select."""

    template_name = "twf/home/project_list.html"
    page_title = "Select Project"
    show_context_help = False

    def get_context_data(self, **kwargs):
        """Add projects to context."""
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            context["projects"] = self.request.user.profile.get_projects()
            context["current_project"] = self.get_project()
        return context


class TWFHomeAboutView(TWFHomeView):
    """View for the about page."""

    template_name = "twf/home/about.html"
    page_title = "About"
    show_context_help = False  # Disable context help for the about page


class TWFHomeLoginView(TWFHomeView, LoginView):
    """View to log in the user."""

    template_name = "twf/home/users/login.html"
    page_title = "Login"
    authentication_form = LoginForm
    show_context_help = False  # Disable context help for the login page


class TWFHomePasswordChangeView(TWFHomeView, PasswordChangeView):
    """View to change the password of the user."""

    template_name = "twf/home/users/change_password.html"
    page_title = "Change Password"
    form_class = ChangePasswordForm
    success_url = reverse_lazy("twf:user_overview")

    def form_valid(self, form):
        """Add success message before redirecting."""
        messages.success(self.request, "Your password has been changed successfully.")
        return super().form_valid(form)


class TWFHomeUserProfileView(LoginRequiredMixin, FormView, TWFHomeView):
    """View to display the user profile."""

    template_name = "twf/home/users/profile.html"
    page_title = "User Profile"
    form_class = UserProfileForm
    success_url = reverse_lazy("twf:user_overview")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add user projects with roles
        user = self.request.user
        owned_projects = user.profile.owned_projects.all()
        member_projects = user.profile.get_projects().exclude(owner=user.profile)

        # Get user roles for each project
        roles = {}
        for project in member_projects:
            role, overrides = user.profile.get_role_and_overrides(project)
            roles[project.id] = {
                "role": role.capitalize(),
                "has_overrides": bool(overrides),
            }

        context.update(
            {
                "owned_projects": owned_projects,
                "member_projects": member_projects,
                "project_roles": roles,
            }
        )

        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        user = self.request.user
        if not hasattr(user, "profile"):
            UserProfile.objects.create(user=user)  # Ensures profile existence

        kwargs["instance"] = user
        return kwargs

    def form_valid(self, form):
        user = self.request.user
        user.first_name = form.cleaned_data["first_name"]
        user.last_name = form.cleaned_data["last_name"]
        user.email = form.cleaned_data["email"]

        user.profile.orc_id = form.cleaned_data["orcid"]
        user.profile.affiliation = form.cleaned_data["affiliation"]
        user.profile.save()

        user.save()
        messages.success(self.request, "User profile updated successfully.")
        return super().form_valid(form)


class TWFUserDetailView(LoginRequiredMixin, TWFHomeView):
    """View to display detailed information about a specific user."""

    template_name = "twf/home/user_detail.html"
    page_title = "User Details"
    navigation_anchor = reverse_lazy("twf:twf_user_management")

    def get(self, request, *args, **kwargs):
        """Handle GET request and check permissions."""
        # Only admins and staff can view user details
        if not request.user.is_superuser and not request.user.is_staff:
            messages.error(request, "You do not have permission to view user details.")
            return redirect("twf:home")

        return super().get(request, *args, **kwargs)

    def get_breadcrumbs(self):
        """Get the breadcrumbs for the user detail view."""
        breadcrumbs = [
            {"url": reverse("twf:home"), "value": '<i class="fas fa-home"></i>'},
            {"url": reverse("twf:twf_user_management"), "value": "User Management"},
            {"url": reverse("twf:user_overview"), "value": "User Overview"},
        ]
        return breadcrumbs

    def get_context_data(self, **kwargs):
        """Add user details to the context."""
        context = super().get_context_data(**kwargs)

        # Get the user to view
        user_id = self.kwargs.get("pk")
        user = get_object_or_404(User, pk=user_id)
        context["viewed_user"] = user

        # User activity statistics
        activity_stats = user.profile.get_user_activity()
        context["activity"] = activity_stats

        # Get projects the user owns or is a member of
        owned_projects = user.profile.owned_projects.all()
        member_projects = Project.objects.filter(members=user.profile)

        context["owned_projects"] = owned_projects
        context["member_projects"] = member_projects

        # Get user roles for each project
        roles = {}
        for project in member_projects:
            role, overrides = user.profile.get_role_and_overrides(project)
            roles[project.id] = {"role": role, "has_overrides": bool(overrides)}
        context["project_roles"] = roles

        # Get recent actions performed by this user
        recent_actions = []

        # Recent created documents
        recent_documents = Document.objects.filter(created_by=user).order_by(
            "-created_at"
        )[:5]
        if recent_documents.exists():
            recent_actions.append(
                {"title": "Recent Documents", "items": recent_documents}
            )

        # Recent created collections
        from twf.models import Collection

        recent_collections = Collection.objects.filter(created_by=user).order_by(
            "-created_at"
        )[:5]
        if recent_collections.exists():
            recent_actions.append(
                {"title": "Recent Collections", "items": recent_collections}
            )

        # Recent tasks
        recent_tasks = Task.objects.filter(user=user).order_by("-start_time")[:5]
        if recent_tasks.exists():
            recent_actions.append({"title": "Recent Tasks", "items": recent_tasks})

        context["recent_actions"] = recent_actions

        return context


class TWFHomeUserOverView(LoginRequiredMixin, TWFHomeView):
    """View to display an overview of the user."""

    template_name = "twf/home/users/overview.html"
    page_title = "User Overview"

    def get_context_data(self, **kwargs):
        """Add the user summary to the context."""
        context = super().get_context_data(**kwargs)
        context["summary"] = self.get_user_summary()

        user = self.request.user
        activity_stats = user.profile.get_user_activity()
        context["activity"] = activity_stats

        context["owned_projects"] = user.profile.owned_projects.all()
        context["member_projects"] = Project.objects.filter(members=user.profile)

        return context

    def get_user_summary(self):
        """Get the summary of the user."""
        # Get the current date and time
        current_time = now()

        # Define the time ranges
        last_day = current_time - timedelta(days=1)
        last_week = current_time - timedelta(weeks=1)
        last_month = current_time - timedelta(days=30)

        models = [
            Project,
            Document,
            Page,
            Dictionary,
            DictionaryEntry,
            PageTag,
            Variation,
            DateVariation,
        ]

        summary = {
            "created_last_day": 0,
            "edited_last_day": 0,
            "created_last_week": 0,
            "edited_last_week": 0,
            "created_last_month": 0,
            "edited_last_month": 0,
            "created_total": 0,
            "edited_total": 0,
        }

        user_id = self.request.user.id
        for model in models:
            summary["created_last_day"] += model.objects.filter(
                created_by_id=user_id, created_at__gte=last_day
            ).count()
            summary["edited_last_day"] += model.objects.filter(
                modified_by_id=user_id, modified_at__gte=last_day
            ).count()

            summary["created_last_week"] += model.objects.filter(
                created_by_id=user_id, created_at__gte=last_week
            ).count()
            summary["edited_last_week"] += model.objects.filter(
                modified_by_id=user_id, modified_at__gte=last_week
            ).count()

            summary["created_last_month"] += model.objects.filter(
                created_by_id=user_id, created_at__gte=last_month
            ).count()
            summary["edited_last_month"] += model.objects.filter(
                modified_by_id=user_id, modified_at__gte=last_month
            ).count()

            summary["created_total"] += model.objects.filter(
                created_by_id=user_id
            ).count()
            summary["edited_total"] += model.objects.filter(
                modified_by_id=user_id
            ).count()

        return summary


class TWFSelectProjectView(LoginRequiredMixin, TWFHomeView):
    """View to select a project."""

    template_name = "twf/home/select_project.html"
    page_title = "Select Project"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        project = Project.objects.get(pk=self.kwargs.get("pk"))

        # Determine user role based on their relationship to the project
        if user.is_superuser:
            user_role = "admin"
        elif project.owner.user == user:
            user_role = "owner"
        elif project.members.filter(user=user).exists():
            # Use the new permission system to get the role
            role, _ = user.profile.get_role_and_overrides(project)
            user_role = role
        else:
            user_role = "no access"

        context.update(
            {
                "project_to_select": project,
                "project": self.get_project(),
                "user_role": user_role,
            }
        )

        return context


class TWFCreateProjectView(LoginRequiredMixin, FormView, TWFHomeView):
    """View to create a project."""

    template_name = "twf/home/create_project.html"
    page_title = "Create Project"
    form_class = CreateProjectForm
    success_url = reverse_lazy("twf:home")

    def form_valid(self, form):
        """Save the project and add the user as the owner. Add the selected members to the project.
        Add default permissions to the project owner and members.
        """
        project = form.save(commit=False)
        project.save(current_user=self.request.user)
        members = form.cleaned_data["members"]

        # Add members to the project
        for member in members:
            project.members.add(member)

        # Apply the manager role to the project owner
        project.owner.set_role_permissions(project, "manager")

        # For members, apply the viewer role by default
        for member in members:
            if member != project.owner:
                # Apply the viewer role to all members except the owner
                member.set_role_permissions(project, "viewer")

        save_instant_task_create_project(project, self.request.user)

        messages.success(self.request, "Project created successfully.")
        return redirect(reverse("twf:project_do_select", args=[project.id]))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class TWFManageProjectsView(
    SingleTableView, FilterView, LoginRequiredMixin, TWFHomeView
):
    """View to manage the projects."""

    template_name = "twf/home/manage_projects.html"
    page_title = "Project Management"
    table_class = ProjectManagementTable
    filterset_class = ProjectFilter
    paginate_by = 10
    model = Project

    def dispatch(self, request, *args, **kwargs):
        """Check system.manage permission before dispatching."""
        if not check_permission(request.user, "system.manage", None):
            messages.error(request, "You do not have permission to manage projects. System administration access required.")
            return redirect("twf:home")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        """Get the queryset for the view."""
        queryset = Project.objects.all().order_by("title")
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get(self, request, *args, **kwargs):
        """Get the view."""
        self.object_list = self.get_queryset()
        context = self.get_context_data()
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["projects"] = Project.objects.all()
        context["filter"] = self.get_filterset(self.filterset_class)
        return context


class TWFManageUsersView(
    SingleTableView, FilterView, LoginRequiredMixin, FormView, TWFHomeView
):
    """View to manage the projects."""

    template_name = "twf/home/manage_users.html"
    page_title = "User Management"
    form_class = CreateUserForm
    success_url = reverse_lazy("twf:twf_user_management")
    table_class = UserManagementTable
    filterset_class = UserFilter
    paginate_by = 10
    model = User

    def dispatch(self, request, *args, **kwargs):
        """Check system.edit permission before dispatching."""
        if not check_permission(request.user, "system.edit", None):
            messages.error(request, "You do not have permission to manage users. System administration access required.")
            return redirect("twf:home")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        """Get the queryset for the view."""
        queryset = User.objects.all().order_by("username")
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get(self, request, *args, **kwargs):
        """Get the view."""
        self.object_list = self.get_queryset()
        context = self.get_context_data()
        return self.render_to_response(context)

    def form_valid(self, form):
        user = form.save(commit=False)
        initial_password = get_random_string(length=8)
        user.set_password(initial_password)
        user.save()

        sent = send_welcome_email(user.email, user.username, initial_password)
        if not sent:
            messages.error(
                self.request,
                "User was created, but there was an error sending the email.",
            )
        else:
            messages.success(
                self.request, "User created successfully. Message sent to user."
            )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter"] = self.get_filterset(self.filterset_class)
        return context


class TWFSystemHealthView(LoginRequiredMixin, TWFHomeView):
    """View to manage the projects."""

    template_name = "twf/home/system_health.html"
    page_title = "System Health"

    def dispatch(self, request, *args, **kwargs):
        """Check system.view permission before dispatching."""
        if not check_permission(request.user, "system.view", None):
            messages.error(request, "You do not have permission to view system health. System administration access required.")
            return redirect("twf:home")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["twf_services"] = TWF_EXTERNAL_SERVICES
        return context


@csrf_exempt
def check_system_health(request):
    """Check the system health incrementally via SSE."""
    # Check system.view permission - only staff/superusers can access
    if not check_permission(request.user, "system.view", None):
        return StreamingHttpResponse(
            "data: " + json.dumps({"error": "Permission denied. System administration access required."}) + "\n\n",
            content_type="text/event-stream",
            status=403
        )

    def event_stream():
        services = check_service_status()
        for service, result in services.items():
            time.sleep(0.5)  # Simulated delay for better visualization
            yield f"data: {json.dumps({service: result})}\n\n"

        # Send a final "DONE" message before closing the stream
        yield "data: DONE\n\n"

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"  # Prevents buffering issues in Nginx
    return response


class TWFProjectViewDetailView(LoginRequiredMixin, TWFHomeView):
    """View for displaying detailed project information.

    This view provides a comprehensive overview of a specific project,
    including statistics, recent activities, and general project information.
    It serves as the main project view page.
    """

    template_name = "twf/home/project_view.html"
    page_title = "Project Details"
    navigation_anchor = reverse_lazy("twf:project_management")

    def get(self, request, *args, **kwargs):
        """Handle the GET request."""
        project = get_object_or_404(Project, pk=kwargs.get("pk"))

        # Check if the user has permission to view this project
        if not check_permission(request.user, "project.view", project):
            messages.error(request, "You do not have permission to view this project.")
            return redirect("twf:project_management")

        return super().get(request, *args, **kwargs)

    def get_breadcrumbs(self):
        """Get the breadcrumbs for the project view."""
        breadcrumbs = [
            {"url": reverse("twf:home"), "value": '<i class="fas fa-home"></i>'},
            {"url": reverse("twf:project_management"), "value": "Project Management"},
            {
                "url": reverse("twf:project_view", args=[self.kwargs.get("pk")]),
                "value": "Project Details",
            },
        ]
        return breadcrumbs

    def get_context_data(self, **kwargs):
        """Get the context data for the view."""
        context = super().get_context_data(**kwargs)

        project = get_object_or_404(Project, pk=self.kwargs.get("pk"))

        # Get project statistics
        doc_stats = get_document_statistics(project)

        # Get recent activity data
        recent_tasks = Task.objects.filter(project=project).order_by("-start_time")[:5]
        documents = Document.objects.filter(project=project).order_by("-created_at")[:5]
        collection_items = CollectionItem.objects.filter(
            collection__project=project
        ).order_by("-created_at")[:5]

        # Calculate the elapsed time since project creation
        days_active = (now() - project.created_at).days

        # Total activity counts
        total_docs = Document.objects.filter(project=project).count()
        total_pages = doc_stats.get("total_pages", 0)
        total_tags = PageTag.objects.filter(page__document__project=project).count()

        # Add all data to context
        context.update(
            {
                "project": project,
                "doc_stats": doc_stats,
                "recent_tasks": recent_tasks,
                "recent_documents": documents,
                "recent_items": collection_items,
                "days_active": days_active,
                "total_docs": total_docs,
                "total_pages": total_pages,
                "total_tags": total_tags,
            }
        )

        return context
