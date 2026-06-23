"""
Template tags for the new permissions system.
"""

from django import template
from django.utils.safestring import mark_safe
from twf.permissions import check_permission, ENTITY_TYPES

register = template.Library()


@register.simple_tag
def user_has_permission(profile, action, project):
    """Custom filter to check if a profile has a specific permission."""
    if action == "" or action is None:
        return True
    # Use the user object and check_permission for compatibility
    return check_permission(profile.user, action, project)


@register.simple_tag
def has_permission(user, permission_action_pair, project):
    """
    Check if a user has a specific permission using the new dot notation.

    Usage:
        {% has_permission user 'document.edit' project as has_perm %}
        {% if has_perm %}...{% endif %}
    """
    return check_permission(user, permission_action_pair, project)


@register.filter
def get_user_role(profile, project):
    """
    Get the user's role in a project.

    Returns a formatted badge showing the user's role (Viewer, Editor, Manager).
    For project owners and superusers, always returns "Manager".

    Usage:
        {{ user.profile|get_user_role:project }}
    """
    # Check if user is owner or superuser
    if profile.user.is_superuser or project.owner == profile:
        return "Manager"

    # Get role for regular users
    role, overrides = profile.get_role_and_overrides(project)

    # Convert permission level to role name if needed
    if "." in role:
        permission_to_role = {
            "view": "viewer",
            "edit": "editor",
            "manage": "manager",
            "none": "none",
        }
        role = permission_to_role.get(role, role)

    # Capitalize and return
    return role.capitalize() if role else "None"


@register.simple_tag
def show_user_permissions(profile, project):
    """
    Display a formatted representation of a user's permissions in a project.

    This template tag shows:
    - The user's role (viewer, editor, or manager)
    - The function description if set
    - A categorized list of the user's permissions

    Usage:
        {% show_user_permissions request.user.profile project %}
    """
    role, overrides = profile.get_role_and_overrides(project)
    function = profile.get_project_function(project) or "Not specified"

    # Get all permissions for this user
    project_permissions = profile.get_project_permissions(project)
    permission_keys = [
        key for key in project_permissions.keys() if key != "function" and "." in key
    ]

    # HTML output
    output = []

    # Show user type (Owner, Member, Superuser)
    user_type = ""
    is_special_user = profile.user.is_superuser or project.owner == profile

    if profile.user.is_superuser:
        user_type = "<span class='badge bg-dark'>Superuser</span>"
    elif project.owner == profile:
        user_type = "<span class='badge bg-primary'>Owner</span>"
    else:
        user_type = "<span class='badge bg-secondary'>Member</span>"

    # Show user type, permission role, and function
    output.append(f"<div class='mb-3'><strong>User Type:</strong> {user_type}</div>")

    # For special users (owners and superusers), always show as managers
    if is_special_user:
        role_display = "Manager"
        role_class = "danger"
        output.append(
            f"<div class='mb-3'><strong>Permission Role:</strong> "
            f"<span class='badge bg-{role_class}'>{role_display}</span></div>"
        )
        # Add a note that special users have all permissions
    else:
        # Determine proper role name and class based on role
        # Convert from permission level (view) to role name (viewer) if needed
        if "." in role:
            # This would be a permission level, not a role - this shouldn't happen
            # But handle it gracefully just in case
            permission_to_role = {
                "view": "viewer",
                "edit": "editor",
                "manage": "manager",
                "none": "none",
            }
            role = permission_to_role.get(role, role)

        # Set role badge color for regular users to match role assignment buttons
        if role == "manager":
            role_class = "danger"
            role_display = "Manager"
        elif role == "editor":
            role_class = "warning"
            role_display = "Editor"
        elif role == "viewer":
            role_class = "info"
            role_display = "Viewer"
        else:  # none
            role_class = "secondary"
            role_display = "None"

        output.append(
            f"<div class='mb-3'><strong>Permission Role:</strong> "
            f"<span class='badge bg-{role_class}'>{role_display}</span></div>"
        )
    output.append(f"<div class='mb-3'><strong>Function:</strong> {function}</div>")

    # Show permissions by entity type
    output.append("<div class='mb-3'><strong>Permissions:</strong></div>")

    # For special users (owners/superusers), we'll show they have all permissions
    if is_special_user:
        output.append(
            "<div class='alert alert-info mb-3'><i class='fa fa-info-circle me-2'></i>"
            "As a project owner or administrator, "
            "you have full access to all project features "
            "regardless of specific permission settings.</div>"
        )
        # Create a visual representation showing all permissions as manager
        return mark_safe("\n".join(output))

    # For regular users, show their actual permissions
    output.append("<div class='row'>")

    # Group permissions by entity type
    entity_permissions = {}
    for key in permission_keys:
        if "." in key:
            entity_type, perm_level = key.split(".")
            if entity_type not in entity_permissions:
                entity_permissions[entity_type] = []
            entity_permissions[entity_type].append(perm_level)

    # Display permissions by entity type
    for entity_type, permissions in sorted(entity_permissions.items()):
        output.append("<div class='col-md-6 mb-3'>")

        # If this entity type's highest permission level differs from the dominant role,
        # highlight it
        entity_max_perm = max(
            permissions, key=lambda x: ["view", "edit", "manage"].index(x)
        )
        is_entity_override = f"{entity_type}.{entity_max_perm}" in overrides
        override_indicator = (
            " <span class='badge bg-secondary ms-2' title='Different from dominant role'>"
            "<i class='fa fa-asterisk'></i></span>"
            if is_entity_override
            else ""
        )

        output.append(
            "<div class='card h-100'><div class='card-header'><h6 class='mb-0'>"
            f"{entity_type.title()}{override_indicator}</h6></div>"
        )
        output.append("<div class='card-body'><ul class='list-group'>")

        # Get proper permission descriptions from ENTITY_TYPES
        entity_data = ENTITY_TYPES.get(entity_type, {})
        for perm_level in sorted(permissions):
            perm_data = entity_data.get(perm_level, {})
            label = perm_data.get("label", f"{entity_type}.{perm_level}")

            # Apply styling based on permission level
            if perm_level == "manage":
                badge_class = "bg-danger"
            elif perm_level == "edit":
                badge_class = "bg-warning"
            else:  # view
                badge_class = "bg-info"

            output.append(
                f"<li class='list-group-item'>"
                f"<span class='badge {badge_class} me-2'>{perm_level}</span> {label}</li>"
            )

        output.append("</ul></div></div>")
        output.append("</div>")

    output.append("</div>")

    return mark_safe("\n".join(output))
