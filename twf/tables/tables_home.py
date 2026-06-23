"""Table classes for displaying user permissions."""

import django_tables2 as tables
from django.contrib.auth import get_user_model
from django.urls import reverse_lazy
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from twf.models import Project

User = get_user_model()


class ProjectManagementTable(tables.Table):
    """Table for managing projects."""

    title = tables.Column(verbose_name="Project", attrs={"td": {"class": "fw-bold"}})
    created_at = tables.DateTimeColumn(format="Y-m-d H:i", verbose_name="Created")
    modified_at = tables.DateTimeColumn(format="Y-m-d H:i", verbose_name="Last Updated")
    status = tables.Column(orderable=False, verbose_name="Project Status")
    owner = tables.Column(accessor="owner", verbose_name="Owner")
    actions = tables.Column(empty_values=(), verbose_name="Options", orderable=False)

    class Meta:
        """
        Table metadata
        """
        model = Project
        fields = ("title", "created_at", "modified_at", "owner", "status")
        template_name = "django_tables2/bootstrap4.html"
        attrs = {"class": "table table-striped table-hover"}

    def render_status(self, value):
        """
        Render project status as a colored badge.

        Args:
            value: Project status string

        Returns:
            SafeString: Formatted HTML badge with appropriate color
        """
        class_map = {
            "open": "success",
            "closed": "secondary",
        }
        color = class_map.get(value.lower(), "dark")
        return format_html(
            '<span class="badge bg-{}">{}</span>', color, value.capitalize()
        )

    def render_owner(self, value):
        """
        Render project owner username with tooltip.

        Args:
            value: UserProfile instance

        Returns:
            SafeString: Formatted HTML with username and tooltip
        """
        if value:
            return format_html(
                '<span title="{}">{}</span>',
                f"User: {value.user.username}",
                value.user.username,
            )

    def render_actions(self, record):
        """
        Render action buttons for project management.

        Args:
            record: Project model instance

        Returns:
            SafeString: Formatted HTML with view, status toggle, and delete buttons
        """
        # Status toggle button (close/reopen)
        if record.status == "open":
            status_button = format_html(
                '<a href="#" class="btn btn-sm btn-warning me-1 show-confirm-modal" title="Close Project" '
                'data-message="Are you sure you want to close the project <strong>{}</strong>?"'
                'data-redirect-url="{}"><i class="fa fa-toggle-off"></i></a>',
                record.title,
                reverse_lazy("twf:project_do_close", kwargs={"pk": record.pk}),
            )
        else:  # closed
            status_button = format_html(
                '<a href="#" class="btn btn-sm btn-success me-1 show-confirm-modal" title="Reopen Project" '
                'data-message="Are you sure you want to reopen the project <strong>{}</strong>?"'
                'data-redirect-url="{}"><i class="fa fa-toggle-on"></i></a>',
                record.title,
                reverse_lazy("twf:project_do_reopen", kwargs={"pk": record.pk}),
            )

        # Delete button
        delete_button = format_html(
            '<a href="#" class="btn btn-sm btn-danger show-danger-modal" title="Delete" '
            'data-message="Are you sure you want to delete the project <strong>{}</strong>? '
            'This action cannot be undone!"'
            'data-redirect-url="{}"><i class="fa fa-trash"></i></a>',
            record.title,
            reverse_lazy("twf:project_do_delete", kwargs={"pk": record.pk}),
        )

        # View button
        view_button = format_html(
            '<a href="{}" class="btn btn-sm btn-secondary me-1" title="View"><i class="fa fa-eye"></i></a>',
            f"/project/view/{record.pk}",
        )

        return format_html("{} {} {}", view_button, status_button, delete_button)


class UserManagementTable(tables.Table):
    """Table for managing users."""

    username = tables.Column(verbose_name="Username")
    email = tables.Column(verbose_name="Email")
    date_joined = tables.DateTimeColumn(format="Y-m-d", verbose_name="Joined")
    last_login = tables.DateTimeColumn(
        format="Y-m-d", verbose_name="Last Login", default="-"
    )
    status = tables.Column(empty_values=(), verbose_name="Status", orderable=False)
    owned_projects = tables.Column(
        empty_values=(), verbose_name="Owns Projects", orderable=False
    )
    actions = tables.Column(empty_values=(), verbose_name="Options", orderable=False)

    class Meta:
        """
        Table metadata
        """
        model = User
        fields = ("username", "email", "date_joined", "last_login")
        template_name = "django_tables2/bootstrap4.html"
        attrs = {"class": "table table-striped table-hover"}

    def render_date_joined(self, value):
        """Render the date joined in YYYY-MM-DD format."""
        return value.strftime("%Y-%m-%d")

    def render_last_login(self, value):
        """Render the last login date in YYYY-MM-DD format, or '-' if never logged in."""
        if value:
            return value.strftime("%Y-%m-%d")
        return "-"

    def render_owned_projects(self, record):
        """
        Render count of projects owned by the user.

        Args:
            record: User model instance

        Returns:
            SafeString: Formatted HTML badge with project count
        """
        # Check if the user has a profile and owns any projects
        if hasattr(record, "profile"):
            owned_count = record.profile.owned_projects.count()
            if owned_count > 0:
                return format_html(
                    '<span class="badge bg-warning">{}</span>', owned_count
                )
        return format_html('<span class="text-muted">{}</span>', "0")

    def render_status(self, record):
        """
        Render user status badges (admin, staff, inactive, etc).

        Args:
            record: User model instance

        Returns:
            SafeString: Formatted HTML with status badges
        """
        status_tags = []

        if record.is_superuser:
            status_tags.append('<span class="badge bg-success">admin</span>')
        elif record.is_staff:
            status_tags.append('<span class="badge bg-primary">staff</span>')

        if not record.is_active:
            status_tags.append('<span class="badge bg-dark">inactive</span>')

        if record == self.context.get("request").user:
            status_tags.append('<span class="badge bg-info">you</span>')

        if not status_tags:
            status_tags.append('<span class="badge bg-light text-dark">user</span>')

        return mark_safe(" ".join(status_tags))

    def render_actions(self, record):
        """
        Render action buttons for user management.

        Args:
            record: User model instance

        Returns:
            SafeString: Formatted HTML with edit and delete buttons
        """
        request = self.context.get("request")

        # Check if user can be deleted (can't delete yourself or users who own projects)
        can_delete = True
        delete_tooltip = "Delete User"

        if record == request.user:
            can_delete = False
            delete_tooltip = "Cannot delete yourself"

        # Check if user owns projects
        has_owned_projects = False
        if hasattr(record, "profile"):
            has_owned_projects = record.profile.owned_projects.exists()
            if has_owned_projects:
                can_delete = False
                delete_tooltip = "User owns projects and cannot be deleted"

        # Generate buttons based on state
        buttons = []

        # View button
        view_btn = format_html(
            '<a href="{}" class="btn btn-sm btn-secondary me-1" '
            'data-bs-toggle="tooltip" data-bs-placement="top" title="View User Details">'
            '<i class="fa-solid fa-eye"></i>'
            "</a>",
            reverse_lazy("twf:user_view", kwargs={"pk": record.pk}),
        )
        buttons.append(view_btn)

        # Reset password button
        reset_btn = format_html(
            '<a href="#" class="btn btn-sm btn-dark me-1 show-confirm-modal" '
            'data-message="Are you sure you want to reset password for <strong>{}</strong>? '
            'A new random password will be generated and sent to their email." '
            'data-redirect-url="{}" '
            'data-bs-toggle="tooltip" data-bs-placement="top" title="Reset Password">'
            '<i class="fa-solid fa-rotate"></i>'
            "</a>",
            record.username,
            reverse_lazy("twf:user_adm_reset_password", kwargs={"pk": record.pk}),
        )
        buttons.append(reset_btn)

        # Activate/deactivate button
        if record.is_active:
            toggle_btn = format_html(
                '<a href="#" class="btn btn-sm btn-warning me-1 show-confirm-modal" '
                'data-message="Are you sure you want to deactivate <strong>{}</strong>?" '
                'data-redirect-url="{}" '
                'data-bs-toggle="tooltip" data-bs-placement="top" title="Deactivate User">'
                '<i class="fa-solid fa-lock"></i>'
                "</a>",
                record.username,
                reverse_lazy("twf:user_adm_deactivate", kwargs={"pk": record.pk}),
            )
        else:
            toggle_btn = format_html(
                '<a href="#" class="btn btn-sm btn-success me-1 show-confirm-modal" '
                'data-message="Are you sure you want to activate <strong>{}</strong>?" '
                'data-redirect-url="{}" '
                'data-bs-toggle="tooltip" data-bs-placement="top" title="Activate User">'
                '<i class="fa-solid fa-unlock"></i>'
                "</a>",
                record.username,
                reverse_lazy("twf:user_adm_activate", kwargs={"pk": record.pk}),
            )
        buttons.append(toggle_btn)

        # Delete button (with different states)
        if can_delete:
            delete_btn = format_html(
                '<a href="#" class="btn btn-sm btn-danger show-danger-modal" '
                'data-message="Are you sure you want to delete the user <strong>{}</strong>?'
                'This action cannot be undone!" '
                'data-bs-toggle="tooltip" data-bs-placement="top" title="Delete User" '
                'data-redirect-url="{}">'
                '<i class="fa-solid fa-trash"></i>'
                "</a>",
                record.username,
                reverse_lazy("twf:user_adm_delete", kwargs={"pk": record.pk}),
            )
        else:
            delete_btn = format_html(
                '<a href="#" class="btn btn-sm btn-outline-danger" '
                'disabled data-bs-toggle="tooltip" data-bs-placement="top" title="{}">'
                '<i class="fa-solid fa-trash"></i>'
                "</a>",
                delete_tooltip,
            )
        buttons.append(delete_btn)

        return mark_safe("".join(buttons))
