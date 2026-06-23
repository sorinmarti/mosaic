import django_tables2 as tables
from django.utils.safestring import mark_safe

from twf.models import Task, Note, UserProfile
from django.utils.html import format_html

class TaskTable(tables.Table):
    """
    Table for displaying tasks with status, progress, and action buttons.
    """
    title = tables.Column(verbose_name="Task")
    task_type = tables.Column(verbose_name="Type", empty_values=())
    category = tables.Column(verbose_name="Category", empty_values=())
    status = tables.Column()
    items = tables.Column(empty_values=(), verbose_name="Items", orderable=False)
    user = tables.Column(verbose_name="Started By")
    start_time = tables.DateTimeColumn(verbose_name="Start", format="Y-m-d H:i")
    end_time = tables.DateTimeColumn(verbose_name="End", format="Y-m-d H:i")
    progress = tables.Column(empty_values=())

    actions = tables.Column(empty_values=(), verbose_name="Options")

    def render_task_type(self, record):
        """
        Render task type as a colored badge.

        Args:
            record: Task model instance

        Returns:
            SafeString: Formatted HTML badge with appropriate color
        """
        type_map = {
            "instant": ("secondary", "fa-bolt", "Instant"),
            "celery": ("primary", "fa-cog", "Background"),
            "workflow": ("info", "fa-stream", "Workflow"),
        }
        color, icon, label = type_map.get(record.task_type, ("secondary", "fa-question", "Unknown"))
        return format_html(
            '<span class="badge bg-{}"><i class="fas {} me-1"></i>{}</span>',
            color, icon, label
        )

    def render_category(self, record):
        """
        Render task category as a colored badge.

        Args:
            record: Task model instance

        Returns:
            SafeString: Formatted HTML badge with appropriate color or dash if no category
        """
        if not record.category:
            return "-"

        category_map = {
            "create": ("success", "fa-plus"),
            "update": ("warning", "fa-edit"),
            "delete": ("danger", "fa-trash"),
            "bulk_delete": ("danger", "fa-trash-alt"),
            "import": ("info", "fa-download"),
            "export": ("info", "fa-upload"),
            "ai_processing": ("primary", "fa-robot"),
            "enrichment": ("secondary", "fa-sparkles"),
            "workflow": ("info", "fa-stream"),
            "system": ("dark", "fa-cog"),
        }
        color, icon = category_map.get(record.category, ("secondary", "fa-tag"))
        label = record.category.replace("_", " ").title()
        return format_html(
            '<span class="badge bg-{} text-white"><i class="fas {} me-1"></i>{}</span>',
            color, icon, label
        )

    def render_items(self, record):
        """
        Render item processing counts for tasks that process multiple items.

        Args:
            record: Task model instance

        Returns:
            SafeString: Formatted HTML showing processed/total items or dash if not applicable
        """
        if record.total_items and record.total_items > 0:
            # Show progress with color coding
            if record.status == "SUCCESS":
                badge_color = "success"
            elif record.status == "FAILURE":
                badge_color = "danger"
            else:
                badge_color = "secondary"

            success_part = ""
            if record.successful_items and record.failed_items:
                success_part = format_html(
                    ' <small class="text-muted">(<span class="text-success">{}</span>/<span class="text-danger">{}</span>)</small>',
                    record.successful_items,
                    record.failed_items
                )

            return format_html(
                '<span class="badge bg-{}">{}/{}</span>{}',
                badge_color,
                record.processed_items or 0,
                record.total_items,
                success_part
            )
        return "-"

    def render_status(self, value):
        """
        Render task status as a colored badge.

        Args:
            value: Task status string

        Returns:
            SafeString: Formatted HTML badge with appropriate color
        """
        class_map = {
            "SUCCESS": "success",
            "FAILURE": "danger",
            "STARTED": "info",
            "PENDING": "secondary",
            "CANCELLED": "dark",
        }
        color = class_map.get(value.upper(), "secondary")
        return format_html(
            '<span class="badge bg-{}">{}</span>', color, value.capitalize()
        )

    def render_progress(self, record):
        """
        Render task progress as a progress bar.

        Args:
            record: Task model instance

        Returns:
            SafeString: Formatted HTML progress bar or dash if not applicable
        """
        if record.status in ["STARTED", "PROGRESS"]:
            return format_html(
                '<div class="progress" style="height: 20px;">'
                '<div class="progress-bar progress-bar-striped progress-bar-animated bg-dark" '
                'role="progressbar" style="width: {}%">{}</div></div>',
                record.progress,
                f"{record.progress}%",
            )
        elif record.status == "SUCCESS":
            return format_html(
                '<div class="progress" style="height: 20px;"><div class="progress-bar bg-success" '
                'role="progressbar" style="width: 100%">{}</div></div>',
                "Completed",
            )
        elif record.status == "FAILURE":
            return format_html(
                '<div class="progress" style="height: 20px;"><div class="progress-bar bg-danger" '
                'role="progressbar" style="width: 100%">{}</div></div>',
                "Failed",
            )
        elif record.status == "CANCELED":
            return format_html(
                '<div class="progress" style="height: 20px;"><div class="progress-bar bg-dark" '
                'role="progressbar" style="width: 100%">{}</div></div>',
                "Cancelled",
            )
        return "-"

    def render_actions(self, record):
        """
        Render action buttons for task management.

        Args:
            record: Task model instance

        Returns:
            SafeString: Formatted HTML with view, cancel, and delete buttons as appropriate
        """
        from django.urls import reverse

        view_url = reverse("twf:task_detail", kwargs={"pk": record.pk})
        cancel_url = reverse("twf:celery_task_cancel", kwargs={"task_id": record.pk})
        remove_url = reverse("twf:celery_task_remove", kwargs={"task_id": record.pk})

        # Only show cancel button for tasks that are in progress
        cancel_button = ""
        if record.status in ["STARTED", "PENDING", "PROGRESS"]:
            cancel_button = format_html(
                '<a href="#" class="btn btn-sm btn-warning me-1 show-confirm-modal" '
                'data-redirect-url="{}" '
                'data-message="Are you sure you want to cancel this task? This will interrupt any ongoing processing." '
                'title="Cancel Task"><i class="fa fa-ban"></i></a>',
                cancel_url,
            )

        # Delete button uses the danger modal - only show for completed or cancelled tasks
        delete_button = ""
        if record.status in ["SUCCESS", "FAILURE", "CANCELED"]:
            delete_button = format_html(
                '<a href="#" class="btn btn-sm btn-danger show-danger-modal" '
                'data-redirect-url="{}" '
                'data-message="Are you sure you want to remove this task? This action cannot be undone." '
                'title="Remove Task"><i class="fa fa-trash"></i></a>',
                remove_url,
            )

        # View button stays the same
        view_button = format_html(
            '<a href="{}" class="btn btn-sm btn-dark me-1" title="View Details"><i class="fa fa-eye"></i></a>',
            view_url,
        )

        return format_html("{}{}{}", view_button, cancel_button, delete_button)

    class Meta:
        """
        Table metadata for TaskTable.
        """
        model = Task
        template_name = "django_tables2/bootstrap4.html"
        fields = ("title", "task_type", "category", "status", "items", "user", "start_time", "end_time", "progress")
        attrs = {"class": "table table-striped table-hover"}


class NoteTable(tables.Table):
    """
    Table for displaying notes associated with a project.
    """
    note = tables.Column(verbose_name="Note")
    created_at = tables.DateTimeColumn(format="Y-m-d H:i", verbose_name="Created")
    modified_at = tables.DateTimeColumn(format="Y-m-d H:i", verbose_name="Modified")

    actions = tables.Column(empty_values=(), verbose_name="Options")

    class Meta:
        """
        Table metadata for NoteTable.
        """
        model = Note
        fields = ("note", "created_at", "modified_at")
        attrs = {"class": "table table-striped table-hover table-sm"}

    def render_note(self, record):
        """
        Render a truncated preview of the note.

        Args:
            record: Note model instance

        Returns:
            SafeString: Formatted HTML with truncated note text
        """
        return format_html(
            "<span>{}</span>",
            record.note[:80] + "..." if len(record.note) > 80 else record.note,
        )

    def render_actions(self, record):
        """
        Render action buttons for note operations.

        Args:
            record: Note model instance

        Returns:
            SafeString: Formatted HTML with view, edit, and delete buttons
        """
        from django.urls import reverse

        # These URLs need to be updated when Note detail/edit/delete views are implemented
        view_url = reverse("twf:project_notes_view", kwargs={"pk": record.pk})
        edit_url = reverse("twf:project_notes_edit", kwargs={"pk": record.pk})
        delete_url = reverse("twf:project_notes_delete", kwargs={"pk": record.pk})

        return format_html(
            '<a href="{}" class="btn btn-sm btn-dark me-1" title="View Details"><i class="fa fa-eye"></i></a>'
            '<a href="{}" class="btn btn-sm btn-dark me-1" title="Edit"><i class="fa fa-edit"></i></a>'
            '<a href="#" class="btn btn-sm btn-danger show-danger-modal" '
            'data-redirect-url="{}" '
            'data-message="Are you sure you want to delete this note? This action cannot be undone." '
            'title="Delete Note"><i class="fa fa-trash"></i></a>',
            view_url,
            edit_url,
            delete_url,
        )


class ProjectUserTable(tables.Table):
    """Table for displaying users in a project with their permissions."""

    project = None

    user = tables.Column(
        accessor="user.username", verbose_name="Username", orderable=False
    )
    user_type = tables.Column(
        empty_values=(), verbose_name="User Type", orderable=False
    )
    role = tables.Column(
        empty_values=(), verbose_name="Permission Role", orderable=False
    )
    function = tables.Column(empty_values=(), verbose_name="Function", orderable=False)
    actions = tables.Column(empty_values=(), verbose_name="Actions", orderable=False)

    def __init__(self, *args, **kwargs):
        """Initialize ProjectUserTable with the associated project."""
        self.project = kwargs.pop("project")
        super(ProjectUserTable, self).__init__(*args, **kwargs)

    class Meta:
        """
        Table metadata for ProjectUserTable.
        """
        model = UserProfile
        fields = ("user", "user_type", "role", "function")
        attrs = {"class": "table table-striped table-hover user-table"}
        row_attrs = {"data-user-id": lambda record: record.id}

    def render_user_type(self, record):
        """Render the user type (Owner, Member, Superuser) with appropriate styling."""
        if not self.project:
            return "-"

        # Check if user is a superuser
        if record.user.is_superuser:
            return format_html('<span class="badge bg-dark">{}</span>', "Superuser")

        # Check if user is the project owner
        if self.project.owner == record:
            return format_html('<span class="badge bg-primary">{}</span>', "Owner")

        # Otherwise, user is a member
        return format_html('<span class="badge bg-secondary">{}</span>', "Member")

    def render_role(self, record):
        """Render the role with appropriate styling."""
        # Get the context - we need the current project
        if not self.project:
            return "-"

        # Check if user is a special user (owner or superuser)
        is_special_user = (self.project.owner == record) or record.user.is_superuser

        if is_special_user:
            # For owners and superusers, always show as managers
            role_display = "Manager"
            role_class = "danger"
            override_badge = ""
        else:
            # For regular users, calculate role based on permission counts
            project_id_str = str(self.project.id)
            project_permissions = record.permissions.get(project_id_str, {})

            # Check if the user has any actual permissions for this project
            # (exclude 'function' which is not a permission)
            perm_keys = [
                k for k in project_permissions.keys() if k != "function" and "." in k
            ]
            if not perm_keys:
                role_display = "None"
                role_class = "secondary"  # Match the 'none' role button color
                override_badge = ""
                return format_html(
                    '<span class="badge bg-{}">{}</span>{}',
                    role_class,
                    role_display,
                    override_badge,
                )

            # Count permissions by level and entity type
            permission_counts = {"none": 0, "view": 0, "edit": 0, "manage": 0}
            entity_levels = {}  # To track the level for each entity type

            # Process each permission
            for perm_key in project_permissions:
                if perm_key != "function" and "." in perm_key:
                    entity_type, level = perm_key.split(".")

                    # Track this entity type's permission level
                    entity_levels[entity_type] = level

                    # Count this permission level
                    permission_counts[level] += 1

            # Calculate the dominant role based on which level has the highest count
            # Sort levels by priority (for ties, higher permission wins)
            sorted_counts = sorted(
                permission_counts.items(),
                key=lambda x: (x[1], ["none", "view", "edit", "manage"].index(x[0])),
                reverse=True,
            )

            # Get the most common permission level and convert to corresponding role name
            perm_level = sorted_counts[0][0]

            # Map permission level to role name
            role_map = {
                "none": "none",
                "view": "viewer",
                "edit": "editor",
                "manage": "manager",
            }
            role = role_map[perm_level]

            # Assign color based on role to match role assignment buttons
            if role == "manager":
                role_class = "danger"
            elif role == "editor":
                role_class = "warning"
            elif role == "viewer":
                role_class = "info"
            else:  # none
                role_class = "secondary"

            role_display = role.capitalize() if role != "none" else "None"

            # Show overrides if different permission levels exist
            # (i.e., not all permissions are at the same level)
            unique_levels = set(entity_levels.values())
            has_overrides = len(unique_levels) > 1
            override_badge = ""
            if has_overrides:
                override_badge = mark_safe(
                    '<span class="badge bg-secondary ms-1" '
                    'title="Has custom permission overrides"><i class="fa fa-asterisk"></i></span>'
                )

        return format_html(
            '<span class="badge bg-{}">{}</span>{}',
            role_class,
            role_display,
            override_badge,
        )

    def render_function(self, record):
        """Render the user's function in the project."""
        if not self.project:
            return "-"

        function = record.get_project_function(self.project)
        if function:
            return function
        return "-"

    def render_actions(self, record):
        """Render action buttons for the user."""
        # Show edit button that triggers the permission form
        edit_button = format_html(
            '<button type="button" class="btn btn-sm btn-primary edit-permissions" '
            'data-user-id="{}" data-username="{}">'
            '<i class="fa fa-edit me-1"></i>Edit Permissions</button>',
            record.id,
            record.user.username,
        )

        return edit_button
