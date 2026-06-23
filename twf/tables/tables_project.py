import django_tables2 as tables
from django.utils.safestring import mark_safe

from twf.models import Task, Prompt, Note, UserProfile
from django.utils.html import format_html
from django.template.loader import render_to_string

class TaskTable(tables.Table):
    title = tables.Column(verbose_name="Task")
    status = tables.Column()
    user = tables.Column(verbose_name="Started By")
    start_time = tables.DateTimeColumn(verbose_name="Start", format="Y-m-d H:i")
    end_time = tables.DateTimeColumn(verbose_name="End", format="Y-m-d H:i")
    progress = tables.Column(empty_values=())

    actions = tables.Column(empty_values=(), verbose_name="Options")

    def render_status(self, value):
        class_map = {
            "SUCCESS": "success",
            "FAILURE": "danger",
            "STARTED": "info",
            "PENDING": "secondary",
            "CANCELLED": "dark",
        }
        color = class_map.get(value.upper(), "secondary")
        return format_html('<span class="badge bg-{}">{}</span>', color, value.capitalize())

    def render_progress(self, record):
        if record.status in ["STARTED", "PROGRESS"]:
            return format_html(
                '<div class="progress" style="height: 20px;"><div class="progress-bar progress-bar-striped progress-bar-animated bg-dark" '
                'role="progressbar" style="width: {}%">{}</div></div>',
                record.progress,
                f"{record.progress}%",
            )
        elif record.status == "SUCCESS":
            return format_html(
                '<div class="progress" style="height: 20px;"><div class="progress-bar bg-success" '
                'role="progressbar" style="width: 100%">{}</div></div>',
                'Completed'
            )
        elif record.status == "FAILURE":
            return format_html(
                '<div class="progress" style="height: 20px;"><div class="progress-bar bg-danger" '
                'role="progressbar" style="width: 100%">{}</div></div>',
                'Failed'
            )
        elif record.status == "CANCELED":
            return format_html(
                '<div class="progress" style="height: 20px;"><div class="progress-bar bg-dark" '
                'role="progressbar" style="width: 100%">{}</div></div>',
                'Cancelled'
            )
        return "-"

    def render_actions(self, record):
        from django.urls import reverse
        view_url = reverse('twf:task_detail', kwargs={'pk': record.pk})
        cancel_url = reverse('twf:celery_task_cancel', kwargs={'task_id': record.pk})
        remove_url = reverse('twf:celery_task_remove', kwargs={'task_id': record.pk})
        
        # Only show cancel button for tasks that are in progress
        cancel_button = ''
        if record.status in ['STARTED', 'PENDING', 'PROGRESS']:
            cancel_button = format_html(
                '<a href="#" class="btn btn-sm btn-warning me-1 show-confirm-modal" '
                'data-redirect-url="{}" '
                'data-message="Are you sure you want to cancel this task? This will interrupt any ongoing processing." '
                'title="Cancel Task"><i class="fa fa-ban"></i></a>',
                cancel_url
            )
        
        # Delete button uses the danger modal - only show for completed or cancelled tasks
        delete_button = ''
        if record.status in ['SUCCESS', 'FAILURE', 'CANCELED']:  
            delete_button = format_html(
                '<a href="#" class="btn btn-sm btn-danger show-danger-modal" '
                'data-redirect-url="{}" '
                'data-message="Are you sure you want to remove this task? This action cannot be undone." '
                'title="Remove Task"><i class="fa fa-trash"></i></a>',
                remove_url
            )
        
        # View button stays the same
        view_button = format_html(
            '<a href="{}" class="btn btn-sm btn-dark me-1" title="View Details"><i class="fa fa-eye"></i></a>',
            view_url
        )
        
        return format_html(
            '{}{}{}',
            view_button, cancel_button, delete_button
        )

    class Meta:
        model = Task
        template_name = "django_tables2/bootstrap4.html"
        fields = ("title", "status", "user", "start_time", "end_time", "progress")
        attrs = {"class": "table table-striped table-hover"}



class PromptTable(tables.Table):
    system_role = tables.Column(verbose_name="Role", attrs={"td": {"class": "fw-bold"}})

    prompt_preview = tables.Column(empty_values=(), verbose_name="Prompt")

    created_at = tables.DateTimeColumn(format="Y-m-d H:i", verbose_name="Created")
    modified_at = tables.DateTimeColumn(format="Y-m-d H:i", verbose_name="Modified")

    actions = tables.Column(empty_values=(), verbose_name="Options")

    class Meta:
        model = Prompt
        fields = ("system_role", "prompt_preview", "created_at", "modified_at")
        attrs = {"class": "table table-striped table-hover table-sm"}

    def render_prompt_preview(self, record):
        return format_html('<span title="{}">{}</span>', record.prompt,
                           record.prompt[:80] + "..." if len(record.prompt) > 80 else record.prompt)

    def render_actions(self, record):
        from django.urls import reverse
        view_url = reverse('twf:prompt_detail', kwargs={'pk': record.pk})
        edit_url = reverse('twf:project_edit_prompt', kwargs={'pk': record.pk})
        delete_url = reverse('twf:project_delete_prompt', kwargs={'pk': record.pk})
        
        return format_html(
            '<a href="{}" class="btn btn-sm btn-dark me-1" title="View Details"><i class="fa fa-eye"></i></a>'
            '<a href="{}" class="btn btn-sm btn-dark me-1" title="Edit"><i class="fa fa-edit"></i></a>'
            '<a href="#" class="btn btn-sm btn-danger show-danger-modal" '
            'data-redirect-url="{}" '
            'data-message="Are you sure you want to delete this prompt? This action cannot be undone." '
            'title="Delete Prompt"><i class="fa fa-trash"></i></a>',
            view_url,
            edit_url,
            delete_url
        )


class NoteTable(tables.Table):
    note = tables.Column(verbose_name="Note")
    created_at = tables.DateTimeColumn(format="Y-m-d H:i", verbose_name="Created")
    modified_at = tables.DateTimeColumn(format="Y-m-d H:i", verbose_name="Modified")

    actions = tables.Column(empty_values=(), verbose_name="Options")

    class Meta:
        model = Note
        fields = ("note", "created_at", "modified_at")
        attrs = {"class": "table table-striped table-hover table-sm"}

    def render_note(self, record):
        return format_html('<span>{}</span>',
                           record.note[:80] + "..." if len(record.note) > 80 else record.note)

    def render_actions(self, record):
        from django.urls import reverse
        
        # These URLs need to be updated when Note detail/edit/delete views are implemented
        view_url = reverse('twf:project_notes_view', kwargs={'pk': record.pk})
        edit_url = reverse('twf:project_notes_edit', kwargs={'pk': record.pk})
        delete_url = reverse('twf:project_notes_delete', kwargs={'pk': record.pk})
        
        return format_html(
            '<a href="{}" class="btn btn-sm btn-dark me-1" title="View Details"><i class="fa fa-eye"></i></a>'
            '<a href="{}" class="btn btn-sm btn-dark me-1" title="Edit"><i class="fa fa-edit"></i></a>'
            '<a href="#" class="btn btn-sm btn-danger show-danger-modal" '
            'data-redirect-url="{}" '
            'data-message="Are you sure you want to delete this note? This action cannot be undone." '
            'title="Delete Note"><i class="fa fa-trash"></i></a>',
            view_url,
            edit_url,
            delete_url
        )


class ProjectUserTable(tables.Table):
    """Table for displaying users in a project with their permissions."""
    project = None

    user = tables.Column(accessor='user.username', verbose_name="Username", orderable=False)
    user_type = tables.Column(empty_values=(), verbose_name="User Type", orderable=False)
    role = tables.Column(empty_values=(), verbose_name="Permission Role", orderable=False)
    function = tables.Column(empty_values=(), verbose_name="Function", orderable=False)
    actions = tables.Column(empty_values=(), verbose_name="Actions", orderable=False)

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop('project')
        super(ProjectUserTable, self).__init__(*args, **kwargs)

    class Meta:
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
            return format_html('<span class="badge bg-dark">{}</span>', 'Superuser')

        # Check if user is the project owner
        if self.project.owner == record:
            return format_html('<span class="badge bg-primary">{}</span>', 'Owner')

        # Otherwise, user is a member
        return format_html('<span class="badge bg-secondary">{}</span>', 'Member')

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
            perm_keys = [k for k in project_permissions.keys() if k != 'function' and '.' in k]
            if not perm_keys:
                role_display = "None"
                role_class = "secondary"  # Match the 'none' role button color
                override_badge = ""
                return format_html('<span class="badge bg-{}">{}</span>{}',
                                  role_class, role_display, override_badge)

            # Count permissions by level and entity type
            permission_counts = {'none': 0, 'view': 0, 'edit': 0, 'manage': 0}
            entity_levels = {}  # To track the level for each entity type

            # Process each permission
            for perm_key in project_permissions:
                if perm_key != 'function' and '.' in perm_key:
                    entity_type, level = perm_key.split('.')

                    # Track this entity type's permission level
                    entity_levels[entity_type] = level

                    # Count this permission level
                    permission_counts[level] += 1

            # Calculate the dominant role based on which level has the highest count
            # Sort levels by priority (for ties, higher permission wins)
            sorted_counts = sorted(
                permission_counts.items(),
                key=lambda x: (x[1], ['none', 'view', 'edit', 'manage'].index(x[0])),
                reverse=True
            )

            # Get the most common permission level and convert to corresponding role name
            perm_level = sorted_counts[0][0]

            # Map permission level to role name
            role_map = {
                'none': 'none',
                'view': 'viewer',
                'edit': 'editor',
                'manage': 'manager'
            }
            role = role_map[perm_level]

            # Assign color based on role to match role assignment buttons
            if role == 'manager':
                role_class = "danger"
            elif role == 'editor':
                role_class = "warning"
            elif role == 'viewer':
                role_class = "info"
            else:  # none
                role_class = "secondary"

            role_display = role.capitalize() if role != 'none' else "None"

            # Show overrides if different permission levels exist
            # (i.e., not all permissions are at the same level)
            unique_levels = set(entity_levels.values())
            has_overrides = len(unique_levels) > 1
            override_badge = ""
            if has_overrides:
                override_badge = mark_safe('<span class="badge bg-secondary ms-1" title="Has custom permission overrides"><i class="fa fa-asterisk"></i></span>')

        return format_html('<span class="badge bg-{}">{}</span>{}',
                          role_class, role_display, override_badge)
    
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
            record.id, record.user.username
        )
        
        return edit_button