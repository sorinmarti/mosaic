"""
This module implements a simplified permissions system for TWF, based on a view/edit/manage model
for different entity types. This system allows for role-based permissions with the ability to
override specific permissions on a per-user basis.
"""

from django.utils.safestring import mark_safe


# Define user roles with default permissions
ROLES = {
    "viewer": "Users who can view content but not modify it",
    "editor": "Users who can edit content but not change project settings",
    "manager": "Users who can manage all aspects of a project",
}


# Define entity types and their permissions
ENTITY_TYPES = {
    "project": {
        "view": {
            "label": "View project",
            "description": "Access project information and settings",
        },
        "edit": {
            "label": "Edit project",
            "description": "Change project settings and information",
        },
        "manage": {
            "label": "Manage project",
            "description": mark_safe(
                "Advanced project operations including delete and export. "
                '<span class="text-danger">Some actions cannot be undone.</span>'
            ),
        },
    },
    "document": {
        "view": {
            "label": "View documents",
            "description": "View documents in the project",
        },
        "edit": {
            "label": "Edit documents",
            "description": "Edit document metadata and content",
        },
        "manage": {
            "label": "Manage documents",
            "description": "Create, delete, and batch process documents",
        },
    },
    "tag": {
        "view": {
            "label": "View tags",
            "description": "View tags in documents",
        },
        "edit": {
            "label": "Edit tags",
            "description": "Edit and assign tags",
        },
        "manage": {
            "label": "Manage tags",
            "description": "Extract tags, create tag types, and batch process tags",
        },
    },
    "metadata": {
        "view": {
            "label": "View metadata",
            "description": "View metadata for documents",
        },
        "edit": {
            "label": "Edit metadata",
            "description": "Edit document metadata",
        },
        "manage": {
            "label": "Manage metadata",
            "description": "Load metadata from external sources and configure metadata fields",
        },
    },
    "dictionary": {
        "view": {
            "label": "View dictionaries",
            "description": "View dictionaries and their entries",
        },
        "edit": {
            "label": "Edit dictionaries",
            "description": "Edit dictionary entries and manage variations",
        },
        "manage": {
            "label": "Manage dictionaries",
            "description": "Create, delete and batch process dictionaries",
        },
    },
    "collection": {
        "view": {
            "label": "View collections",
            "description": "View collections and their items",
        },
        "edit": {
            "label": "Edit collections",
            "description": "Edit collection items and their properties",
        },
        "manage": {
            "label": "Manage collections",
            "description": "Create, delete, and batch process collections",
        },
    },
    "import-export": {
        "view": {
            "label": "View exports",
            "description": "View and download available exports",
        },
        "edit": {
            "label": "Configure exports",
            "description": "Configure export settings and create exports",
        },
        "manage": {
            "label": "Manage imports/exports",
            "description": "Import data and manage export configurations",
        },
    },
    "task": {
        "view": {
            "label": "View tasks",
            "description": "View tasks and their status",
        },
        "edit": {
            "label": "Cancel tasks",
            "description": "Cancel running tasks",
        },
        "manage": {
            "label": "Manage tasks",
            "description": "Remove tasks and configure task settings",
        },
    },
    "prompt": {
        "view": {
            "label": "View prompts",
            "description": "View saved prompts",
        },
        "edit": {
            "label": "Edit prompts",
            "description": "Edit saved prompts",
        },
        "manage": {
            "label": "Manage prompts",
            "description": "Create and delete prompts",
        },
    },
    "note": {
        "view": {
            "label": "View notes",
            "description": "View project notes",
        },
        "edit": {
            "label": "Edit notes",
            "description": "Edit project notes",
        },
        "manage": {
            "label": "Manage notes",
            "description": "Create and delete project notes",
        },
    },
    "ai": {
        "view": {
            "label": "View AI settings",
            "description": "View AI configuration",
        },
        "edit": {
            "label": "Use AI features",
            "description": "Use AI features for individual operations",
        },
        "manage": {
            "label": "Manage AI features",
            "description": "Configure AI settings and run batch operations",
        },
    },
    "system": {
        "view": {
            "label": "View system information",
            "description": "View system health, statistics, and configuration",
        },
        "edit": {
            "label": "Manage users",
            "description": "Manage user accounts, activate/deactivate users, and reset passwords",
        },
        "manage": {
            "label": "Manage system",
            "description": mark_safe(
                "Full system administration including project management, user deletion, and system configuration. "
                '<span class="text-danger">Restricted to superusers and staff only.</span>'
            ),
        },
    },
}


def check_permission(user, action, project, object_id=None):
    """
    Check if a user has permission to perform an action in a project.
    This function maintains backward compatibility with the old permission system
    while using the new simplified model.

    Args:
        user: The user to check permissions for
        action: The action to check (can be old granular permission or new entity_type.permission)
        project: The project context
        object_id: Optional object ID for more specific permission checks

    Returns:
        bool: Whether the user has permission
    """
    # Check if user is authenticated
    if not user.is_authenticated or not user.is_active:
        return False

    # Superusers and staff have all permissions
    if user.is_superuser or user.is_staff:
        return True

    # For system-level permissions (no project context), only staff/superusers have access
    # Regular users cannot have system permissions
    if project is None:
        return False

    # Check if the user is the project owner - owners have all permissions
    if hasattr(user, "profile") and project.owner == user.profile:
        return True

    # Parse the action to check if it has the entity_type.permission format
    if "." in action:
        entity_type, permission_level = action.split(".")

        # Get current permissions for the project
        project_permissions = user.profile.get_project_permissions(project)

        # Direct check for the exact permission first
        if action in project_permissions:
            return True

        # Check if user has a higher level permission for the same entity_type
        if permission_level == "view":
            # Check if user has edit or manage permission for this entity_type
            if (
                f"{entity_type}.edit" in project_permissions
                or f"{entity_type}.manage" in project_permissions
            ):
                return True
        elif permission_level == "edit":
            # Check if user has manage permission for this entity_type
            if f"{entity_type}.manage" in project_permissions:
                return True

        # No higher permission level found
        return False

    # For non-standard permission format, check directly
    return user.profile.has_permission(action, project, object_id)


def get_role_permissions(role):
    """
    Get all permissions for a specific role based on fixed view/edit/manage rules.

    Args:
        role: The role name (none, viewer, editor, manager)

    Returns:
        list: List of permissions for the given role
    """
    # The 'none' role has no permissions
    if role == "none":
        return []

    if role not in ROLES and role != "none":
        return []

    permissions = []

    # Apply permissions based on role
    for entity_type in ENTITY_TYPES:
        if role == "viewer":
            # Viewers only get 'view' permissions
            permissions.append(f"{entity_type}.view")
        elif role == "editor":
            # Editors get 'view' and 'edit' permissions
            permissions.append(f"{entity_type}.view")
            permissions.append(f"{entity_type}.edit")
        elif role == "manager":
            # Managers get all permissions (view, edit, manage)
            permissions.append(f"{entity_type}.view")
            permissions.append(f"{entity_type}.edit")
            permissions.append(f"{entity_type}.manage")

    return permissions
