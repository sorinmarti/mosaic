"""This module contains the models for the twf app. The models are used to store data in the database.
Each module class represents a table in the database. The classes are subclasses of Django's models.Model class.

The main model is the Project model, which represents a project in the app. Most other models rely directly or
indirectly on the Project model. Most models extend the TimeStampedModel class, which provides self-updating
'created' and 'modified' fields. This means, every time an object is created or modified, the 'created_at' and
'modified_at' fields are updated automatically, but the user who created or modified the object must be provided.
"""

import json
from datetime import timedelta

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from django.utils.timezone import now
from twf.permissions import get_role_permissions

from twf.templatetags.tk_tags import tk_iiif_url, tk_bounding_box

# The User model is retrieved dynamically to allow for custom user models
User = get_user_model()


class TimeStampedModel(models.Model):
    """
    TimeStampedModel
    ----------------
    An abstract base class model that provides self-updating 'created' and 'modified' fields.
    Most models in the app extend this class to provide these fields.

    Attributes
    ~~~~~~~~~~
    created_at : DateTimeField
        The date and time the object was created.
    modified_at : DateTimeField
        The date and time the object was last modified.
    created_by : ForeignKey
        The user who created the object.
    modified_by : ForeignKey
        The user who last modified the object.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    """The date and time the object was created."""

    modified_at = models.DateTimeField(auto_now=True)
    """The date and time the object was last modified."""

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="created_%(class)s_set",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    """The user who created the object."""

    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="modified_%(class)s_set",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    """The user who last modified the object."""

    class Meta:
        """Meta options for the TimeStampedModel."""

        abstract = True

    def save(self, *args, **kwargs):
        """Save the object."""
        user = kwargs.pop("current_user", None)
        if user is not None:
            if not self.pk:  # Check if this is a new object
                self.created_by = user
            self.modified_by = user
        super().save(*args, **kwargs)


class UserProfile(models.Model):
    """
    User Profile Model
    ------------------
    User profiles are used to store additional information about users. This model extends the Django User model
    and provides additional fields to store user-specific data. The UserProfile model is linked to the User model
    via a OneToOneField, which means that each user can have only one profile.

    Attributes
    ~~~~~~~~~~
    user : OneToOneField
        The user this profile belongs to.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    """The user this profile belongs to."""

    orc_id = models.CharField(max_length=255, blank=True, null=True)
    """The ORCID of the user."""

    affiliation = models.CharField(max_length=255, blank=True, null=True)
    """The affiliation of the user."""

    permissions = models.JSONField(default=dict)

    def get_projects(self):
        """Return the projects the user is a member or owner of."""

        owned_projects = Project.objects.filter(owner=self, status="open")
        member_projects = Project.objects.filter(members=self, status="open")
        all_projects = owned_projects | member_projects
        all_projects = all_projects.distinct().order_by("id")
        return all_projects

    def is_owner_of(self, project):
        """Check if the user is the owner of a project."""
        return self.user == project.owner.user

    def get_project_permissions(self, project):
        """Return the permissions of the user for a project."""
        return self.permissions.get(str(project.id), {})

    def get_project_function(self, project):
        """Return the role af the user for a project."""
        permissions = self.get_project_permissions(project)
        return permissions.get("function", None)

    def set_role_permissions(self, project, role):
        """Set a user's role for a project with optional permission overrides."""
        # First, get all current permissions
        current_permissions = self.get_project_permissions(project)

        # Remove all existing permissions except function
        function_desc = current_permissions.get("function")
        project_id_str = str(project.id)

        if project_id_str in self.permissions:
            # Create new empty permissions dict, but keep function if it exists
            self.permissions[project_id_str] = {}
            if function_desc:
                self.permissions[project_id_str]["function"] = function_desc

            # Save to ensure we're starting fresh
            self.save()

        # Get base permissions for the new role
        permissions = get_role_permissions(role)

        # Add all permissions for the new role
        for permission in permissions:
            self.add_permission(permission, project)

    def set_role(self, project, role, overrides=None):
        """
        Set a user's role in a project with optional permission overrides.

        This method:
        1. Applies the base permissions for the given role
        2. Applies any permission overrides specified

        Args:
            project: The project to set permissions for
            role: The role to assign ('none', 'viewer', 'editor', or 'manager')
            overrides: Optional dict of permission overrides {permission: bool}
        """
        # First, clear existing permissions for this project
        if str(project.id) in self.permissions:
            # Preserve the function description if it exists
            function_desc = self.get_project_function(project)
            # Create a new empty permissions dict for this project
            self.permissions[str(project.id)] = {}
            # Restore function description if it existed
            if function_desc:
                self.permissions[str(project.id)]["function"] = function_desc
            self.save()

        # If role is 'none', we just clear permissions and don't apply any new ones
        if role == "none":
            return

        # Apply base role permissions
        self.set_role_permissions(project, role)

        # Apply any permission overrides
        if overrides:
            for entity_type, entity_overrides in overrides.items():
                for perm_type, value in entity_overrides.items():
                    permission = f"{entity_type}.{perm_type}"
                    if value:
                        self.add_permission(permission, project)
                    else:
                        self.remove_permission(permission, project)

    def has_permission(self, action, project, object_id=None):
        """
        Check if the user has a specific permission.

        Supports hierarchical permissions where higher levels (manage > edit > view)
        automatically grant lower level permissions for the same entity type.
        """
        # Superusers have all permissions
        if self.user.is_superuser:
            return True

        # Project owners have all permissions
        if project.owner == self:
            return True

        # Get permissions for this project
        project_permissions = self.permissions.get(str(project.id), {})

        # Handle hierarchical permissions if this is a dotted action (entity_type.permission_level)
        if "." in action:
            entity_type, permission_level = action.split(".")

            # Direct check - does the user have this exact permission?
            if action in project_permissions:
                return True

            # Hierarchical check - if requesting a lower permission, check if higher ones exist
            if permission_level == "view":
                # 'manage' or 'edit' also grants 'view'
                if (
                    f"{entity_type}.manage" in project_permissions
                    or f"{entity_type}.edit" in project_permissions
                ):
                    return True
            elif permission_level == "edit":
                # 'manage' also grants 'edit'
                if f"{entity_type}.manage" in project_permissions:
                    return True

        # If not found via hierarchy, check if it exists directly
        return project_permissions.get(action, False)  # Default to False

    def add_permission(self, action, project):
        """
        Grant a new permission to the user.
        Uses the best permission level system: If adding a higher level permission,
        lower levels for the same object_type are redundant and can be removed.
        """
        # Parse the action to get object_type and permission_level
        if "." in action:
            object_type, permission_level = action.split(".")

            # Get current permissions and ensure project permissions dict exists
            project_permissions = self.get_project_permissions(project)

            # Check if we're adding a higher-level permission
            if permission_level == "manage":
                # Remove view and edit permissions for the same object type (they're redundant)
                view_perm = f"{object_type}.view"
                edit_perm = f"{object_type}.edit"
                project_permissions.pop(view_perm, None)
                project_permissions.pop(edit_perm, None)
            elif permission_level == "edit":
                # Remove view permission for the same object type (it's redundant)
                view_perm = f"{object_type}.view"
                project_permissions.pop(view_perm, None)

                # Check if manage permission already exists (don't downgrade)
                manage_perm = f"{object_type}.manage"
                if manage_perm in project_permissions:
                    # If user already has manage permission, don't add edit
                    self.permissions[str(project.id)] = project_permissions
                    self.save()
                    return
            elif permission_level == "view":
                # Check if edit or manage permission already exists (don't downgrade)
                edit_perm = f"{object_type}.edit"
                manage_perm = f"{object_type}.manage"
                if (
                    edit_perm in project_permissions
                    or manage_perm in project_permissions
                ):
                    # If user already has higher permission, don't add view
                    self.permissions[str(project.id)] = project_permissions
                    self.save()
                    return

            # Add the new permission
            project_permissions[action] = True
            self.permissions[str(project.id)] = project_permissions
            self.save()
        else:
            # For non-standard permission format, just add it directly
            project_permissions = self.get_project_permissions(project)
            project_permissions[action] = True
            self.permissions[str(project.id)] = project_permissions
            self.save()

    def remove_permission(self, action, project):
        """
        Remove a permission from the user.
        When removing a higher level permission, we might need to add back lower levels.
        """
        project_permissions = self.get_project_permissions(project)

        # If permission exists, remove it
        if action in project_permissions:
            # Parse the action to get object_type and permission_level
            if "." in action:
                object_type, permission_level = action.split(".")

                # If removing a higher-level permission, might need to add back lower ones
                if permission_level == "manage":
                    # Check if edit permission should be added
                    if f"{object_type}.edit" not in project_permissions:
                        project_permissions[f"{object_type}.edit"] = True
                elif permission_level == "edit":
                    # Check if view permission should be added
                    if f"{object_type}.view" not in project_permissions:
                        project_permissions[f"{object_type}.view"] = True

            # Remove the permission
            del project_permissions[action]
            self.permissions[str(project.id)] = project_permissions
            self.save()

    def set_project_function(self, project, function_desc):
        """Set a functional description for the user in a project."""
        project_permissions = self.get_project_permissions(project)
        if function_desc:
            project_permissions["function"] = function_desc
        else:
            # Remove the function if it's empty
            project_permissions.pop("function", None)
        self.permissions[str(project.id)] = project_permissions
        self.save()

    def get_role_and_overrides(self, project):
        """
        Determine a user's role in the project and identify any permission overrides.

        This method analyzes the user's permissions for the project and returns:
        1. The highest role that occurs most frequently in their permission set
        2. Any permission overrides where an entity's permission level differs from the dominant role

        Args:
            project: The project to check permissions for

        Returns:
            tuple: (role, overrides) where:
                role (str): 'manager', 'editor', 'viewer', or 'none'
                overrides (dict): Dictionary of permission overrides
        """
        # Get the user's current permissions for this project
        permissions = self.get_project_permissions(project)

        # Filter out non-permission keys
        perm_keys = [k for k in permissions.keys() if k != "function" and "." in k]

        # Find overrides (permissions that differ from the standard set)
        overrides = {}

        # Check if the user has any permissions at all
        if not perm_keys:
            role = "none"
            return role, overrides

        # Count permissions by level and track entity levels
        permission_counts = {"none": 0, "view": 0, "edit": 0, "manage": 0}
        entity_levels = {}  # To track the level for each entity type

        # Process each permission
        for perm_key in perm_keys:
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

        # Check if we have multiple permission levels
        unique_levels = set(entity_levels.values())
        has_multiple_levels = len(unique_levels) > 1

        # If multiple levels exist, identify all permissions that differ from the dominant role
        if has_multiple_levels:
            for entity_type, level in entity_levels.items():
                if level != role:
                    # This entity has a different permission level than the dominant role
                    overrides[f"{entity_type}.{level}"] = True

        return role, overrides

    def get_user_activity(self):
        """Get activity statistics for a specific user."""
        # Get the current date and time
        current_time = now()

        # Define the time ranges
        last_day = current_time - timedelta(days=1)
        last_week = current_time - timedelta(weeks=1)
        last_month = current_time - timedelta(days=30)

        _models = [
            Project,
            Document,
            Page,
            Dictionary,
            DictionaryEntry,
            PageTag,
            Variation,
            DateVariation,
        ]

        stats = {
            "created_last_day": 0,
            "edited_last_day": 0,
            "created_last_week": 0,
            "edited_last_week": 0,
            "created_last_month": 0,
            "edited_last_month": 0,
            "created_total": 0,
            "edited_total": 0,
        }

        for model in _models:
            stats["created_last_day"] += model.objects.filter(
                created_by=self.user, created_at__gte=last_day
            ).count()
            stats["edited_last_day"] += model.objects.filter(
                modified_by=self.user, modified_at__gte=last_day
            ).count()

            stats["created_last_week"] += model.objects.filter(
                created_by=self.user, created_at__gte=last_week
            ).count()
            stats["edited_last_week"] += model.objects.filter(
                modified_by=self.user, modified_at__gte=last_week
            ).count()

            stats["created_last_month"] += model.objects.filter(
                created_by=self.user, created_at__gte=last_month
            ).count()
            stats["edited_last_month"] += model.objects.filter(
                modified_by=self.user, modified_at__gte=last_month
            ).count()

            stats["created_total"] += model.objects.filter(created_by=self.user).count()
            stats["edited_total"] += model.objects.filter(modified_by=self.user).count()

        return stats

    def __str__(self):
        """Return the string representation of the UserProfile."""
        return self.user.username


class Project(TimeStampedModel):
    """
    Project Model
    -------------
    Projects are the main entities in the app. Each project represents a collection of documents and pages that
    are related to a specific task or topic. Projects can have multiple members, each with different roles and
    permissions. The Project model extends the TimeStampedModel, which provides self-updating 'created' and 'modified'
    fields.
    """

    STATUS_CHOICES = (
        ("open", "Open"),
        ("closed", "Closed"),
    )
    """The choices for the status of the project."""

    title = models.CharField(
        max_length=100,
        verbose_name="Project Title",
        help_text="The title of the project. This can be any string, needs to be less than 100 "
        "characters. Can be used in data exports.",
        unique=True,
    )
    """The title of the project."""

    collection_id = models.CharField(
        max_length=30,
        verbose_name="Transkribus Collection ID",
        help_text="The Transkribus collection ID. "
        "Needed to export your data from Transkribus.",
    )
    """The Transkribus collection ID."""

    transkribus_job_id = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        verbose_name="Transkribus Job ID",
        help_text="This value is set by the system and should only be changed "
        "to manually point TWF to a finished export job.",
    )
    """The Transkribus job ID of the last requested export."""

    job_download_url = models.URLField(
        blank=True,
        null=True,
        verbose_name="Transkribus Job Download URL",
        help_text="The download URL of the last requested export."
        "This value is set by the system and should only be changed "
        "to manually point TWF to a finished export job.",
    )
    """The download URL of the last requested export."""

    downloaded_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Last Export Downloaded At",
        help_text="The time the last export was downloaded.",
    )
    """The time the last export was downloaded."""

    downloaded_zip_file = models.FileField(
        upload_to="transkribus_exports/",
        blank=True,
        null=True,
        verbose_name="Last Export File",
        help_text="The last downloaded export file.",
    )
    """The last downloaded export file."""

    description = models.TextField(
        blank=True,
        default="",
        verbose_name="Project Description",
        help_text="The description of the project. Should be brief. "
        "Can be used in data exports.",
    )
    """The description of the project."""

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="open",
        verbose_name="Project Status",
        help_text="The status of the project.",
    )
    """The status of the project."""

    owner = models.ForeignKey(
        UserProfile,
        related_name="owned_projects",
        on_delete=models.PROTECT,
        verbose_name="Project Owner",
        help_text="The owner of the project. This user has all the permissions.",
    )
    """The owner of the project. This user has all the permissions."""

    members = models.ManyToManyField(
        UserProfile,
        related_name="projects",
        blank=True,
        verbose_name="Project Members",
        help_text="The members of the project. Their roles can be adjusted"
        "in the user management section.",
    )
    """The members of the project. Their permissions can be adjusted in the user management section."""

    selected_dictionaries = models.ManyToManyField(
        "Dictionary",
        related_name="selected_projects",
        blank=True,
        verbose_name="Selected Dictionaries",
        help_text="The dictionaries selected for this project."
        "These will be used for assigning tags.",
    )
    """The dictionaries selected for this project."""

    conf_credentials = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Credentials Configurations",
        help_text="A dictionary of credential configurations.",
    )
    """A dictionary of credential configurations. In order to keep these settings as dynamic as possible, they are
    stored as JSONField. The keys in the dictionary are the services, and the values are the credentials for the 
    services."""

    conf_tasks = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Task Configurations",
        help_text="A dictionary of task configurations.",
    )
    """A dictionary of task configurations. In order to keep these settings as dynamic as possible, they are
    stored as JSONField. The keys in the dictionary are the services, and the values are the task configurations."""

    conf_ai_settings = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="AI Settings",
        help_text="Configurations for AI providers including temperature, token limits, etc.",
    )
    """A dictionary of AI settings for different providers. Includes temperature, max tokens, and other parameters
    that control the behavior of AI providers like OpenAI, Google Gemini, Anthropic Claude, and Mistral."""

    conf_display = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Display Configurations",
        help_text="A dictionary of display configurations.",
    )
    """A dictionary of display configurations. In order to keep these settings as dynamic as possible, they are
    stored as JSONField. The keys in the dictionary are the services, and the values are the display configurations."""

    keywords = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Keywords",
        help_text="Keywords for the project. These can be used for data exports.",
    )
    """Keywords for the project. These can be used for data exports."""

    license = models.CharField(
        max_length=255,
        blank=True,
        default="CC BY 4.0",
        verbose_name="License",
        help_text="The license of the project. This can be used for data exports.",
    )
    """The license of the project. This can be used for data exports."""

    version = models.CharField(
        max_length=255,
        blank=True,
        default="1.0",
        verbose_name="Version",
        help_text="The version of the project. This can be used for data exports.",
    )

    workflow_description = models.TextField(
        blank=True,
        default="",
        verbose_name="Workflow Description",
        help_text="The description of the workflow for this project."
        "You can use Markdown to format the text.",
    )
    """The description of the workflow for this project. You can use Markdown to format the text."""

    zenodo_deposition_id = models.CharField(max_length=128, blank=True, null=True)

    project_doi = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Project DOI",
        help_text="The DOI of the project.",
    )

    def get_project_members(self):
        """Return the project members plus the project's owner."""
        return UserProfile.objects.filter(
            Q(id=self.owner_id) | Q(id__in=self.members.values_list("id", flat=True))
        ).order_by("user__username")

    def get_credentials(self, service):
        """Return the credentials for a service.

        Available services
        ------------------
        - transkribus: The Transkribus credentials Username, password).
        - openai: The OpenAI credentials (API key, default model).
        - genai: The GenAI credentials (API key, default model).
        - anthropic: The Anthropic credentials (API key, default model).
        - geonames: The Geonames credentials (Username).
        """
        return self.conf_credentials.get(service, {})

    def get_task_configuration(self, service, return_json=True):
        """Return the task configuration for a service.
        Available services
        ------------------
        - google_sheet: The Google Sheet configuration.
        - metadata_review: The metadata review configuration.
        - date_normalization: The date normalization configuration.
        - tag_types: The tag types configuration.
        """
        if return_json:
            value = self.conf_tasks.get(service, None)
            if value:
                if isinstance(value, dict):
                    return value
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return {}
            return {}
        return self.conf_tasks.get(service, {})

    def get_tag_enrichment_config(self, tag_type):
        """Get enrichment configuration for a tag type.

        Parameters
        ----------
        tag_type : str
            The tag type to get configuration for

        Returns
        -------
        dict
            Enrichment configuration with workflow_title, form_type, wikidata_entity_type
        """
        conf_tasks = self.conf_tasks or {}
        tag_types_config = conf_tasks.get("tag_types", {})
        enrichment_types = {}

        if "enrichment_types_config" in tag_types_config:
            try:
                enrichment_types = json.loads(tag_types_config["enrichment_types_config"])
            except (json.JSONDecodeError, TypeError):
                pass

        return enrichment_types.get(tag_type, {})

    def get_dictionary_enrichment_config(self, dictionary_type):
        """Get enrichment configuration for a dictionary type.

        Parameters
        ----------
        dictionary_type : str
            The dictionary type to get configuration for

        Returns
        -------
        dict
            Enrichment configuration with enrichment_types, wikidata_entity_type, workflow_title
        """
        conf_tasks = self.conf_tasks or {}
        dictionary_types = conf_tasks.get("dictionary_types", {})
        return dictionary_types.get(dictionary_type, {})

    def get_workflow_definition(self, workflow_type):
        """Return workflow definition with defaults for backward compatibility.

        Parameters
        ----------
        workflow_type : str
            The type of workflow ('review_documents' or 'review_collection')

        Returns
        -------
        dict
            Workflow definition with fields: title, description, instructions,
            instruction_format, fields, batch_size
        """
        definitions = self.conf_tasks.get("workflow_definitions", {})
        defaults = {
            "review_documents": {
                "title": "Review Documents",
                "description": "Review documents in the project",
                "instructions": "",
                "instruction_format": "markdown",
                "fields": {},
                "batch_size": 5,
            },
            "review_collection": {
                "title": "Review Collection",
                "description": "Review collection items",
                "instructions": "",
                "instruction_format": "markdown",
                "fields": {},
                "batch_size": 5,
            },
            "review_tags_grouping": {
                "title": "Group Tags",
                "description": "Group tag variations into dictionary entries",
                "instructions": "",
                "instruction_format": "markdown",
                "fields": {},
                "batch_size": 10,
            },
            "review_tags_dates": {
                "title": "Normalize Dates",
                "description": "Normalize date tags to EDTF format",
                "instructions": "",
                "instruction_format": "markdown",
                "fields": {},
                "batch_size": 20,
            },
            "review_tags_enrichment": {
                "title": "Enrich Tags",
                "description": "Enrich tags with normalized data",
                "instructions": "",
                "instruction_format": "markdown",
                "fields": {},
                "batch_size": 20,
            },
        }
        # Deep merge configured with defaults
        default = defaults.get(workflow_type, {})
        configured = definitions.get(workflow_type, {})
        result = {**default, **configured}
        if "fields" in default:
            result["fields"] = {**default["fields"], **configured.get("fields", {})}
        return result

    def get_transkribus_url(self):
        """Return the URL to the Transkribus collection."""
        return f"https://app.transkribus.org/collection/{self.collection_id}"

    def __str__(self):
        """Return the string representation of the Project."""
        return self.title.__str__()


class Task(models.Model):
    """
    Task Model
    ----------
    Tasks are used to track operations in the database. This includes Celery background tasks,
    instant operations (deletes, creates, updates), and workflow progress tracking.
    The Task model is linked to the Project model via a ForeignKey.

    Task Types
    ~~~~~~~~~~
    - instant: Operations that complete immediately (single deletes, creates, updates)
    - celery: Background tasks processed by Celery (AI processing, exports, bulk operations)
    - workflow: User workflows with step-by-step progress tracking (review workflows)

    Attributes
    ~~~~~~~~~~
    project : ForeignKey
        The project this task belongs to.
    user : ForeignKey
        The user who created the task.
    celery_task_id : CharField
        The unique ID of the task (Celery task ID or generated UUID).
    progress : IntegerField
        Progress percentage (0-100).
    status : CharField
        The status of the task (PENDING, STARTED, SUCCESS, FAILURE, PROGRESS, CANCELED).
    start_time : DateTimeField
        The time the task was started.
    end_time : DateTimeField
        The time the task was completed.
    title : CharField
        The title of the task.
    description : TextField
        The description of the task.
    text : TextField
        Detailed log text for the task.
    meta : JSONField
        Additional metadata for the task.
    task_type : CharField
        The type of task (instant, celery, workflow).
    category : CharField
        The category of the task (create, delete, ai_processing, etc.).
    total_items : IntegerField
        Total number of items to process in this task.
    processed_items : IntegerField
        Number of items processed so far.
    successful_items : IntegerField
        Number of items processed successfully.
    failed_items : IntegerField
        Number of items that failed to process.
    workflow_steps : JSONField
        For workflow tasks, tracks the progression through workflow steps.
    """

    TASK_STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("STARTED", "Started"),
        ("SUCCESS", "Success"),
        ("FAILURE", "Failure"),
        ("PROGRESS", "Progress"),
        ("CANCELED", "Cancelled"),
    ]

    TASK_TYPE_CHOICES = [
        ("instant", "Instant"),
        ("celery", "Celery Background Task"),
        ("workflow", "Workflow"),
    ]

    CATEGORY_CHOICES = [
        ("create", "Create"),
        ("update", "Update"),
        ("delete", "Delete"),
        ("bulk_delete", "Bulk Delete"),
        ("import", "Import/Extract"),
        ("export", "Export"),
        ("ai_processing", "AI Processing"),
        ("enrichment", "Enrichment"),
        ("workflow", "Workflow"),
        ("system", "System"),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    """The project this task belongs to."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tasks")
    """The user who created the task."""

    celery_task_id = models.CharField(max_length=255, unique=True)
    """The ID of the Celery task."""

    progress = models.IntegerField(default=0)
    """The progress of the task."""

    status = models.CharField(
        max_length=10, choices=TASK_STATUS_CHOICES, default="PENDING"
    )
    """The status of the task."""

    start_time = models.DateTimeField(default=timezone.now)
    """The time the task was started."""

    end_time = models.DateTimeField(null=True, blank=True)
    """The time the task was completed."""

    title = models.CharField(max_length=255, blank=True, default="")
    """The title of the task."""

    description = models.TextField(blank=True, default="")
    """The description of the task."""

    text = models.TextField(blank=True, default="")
    """The text of the task."""

    meta = models.JSONField(default=dict, blank=True)
    """Additional metadata for the task."""

    task_type = models.CharField(
        max_length=20, choices=TASK_TYPE_CHOICES, default="celery"
    )
    """The type of task (instant, celery, or workflow)."""

    category = models.CharField(
        max_length=30, choices=CATEGORY_CHOICES, null=True, blank=True
    )
    """The category of the task (create, delete, ai_processing, etc.)."""

    total_items = models.IntegerField(null=True, blank=True)
    """Total number of items to process in this task."""

    processed_items = models.IntegerField(default=0)
    """Number of items processed so far."""

    successful_items = models.IntegerField(default=0)
    """Number of items processed successfully."""

    failed_items = models.IntegerField(default=0)
    """Number of items that failed to process."""

    workflow_steps = models.JSONField(default=dict, blank=True)
    """For workflow tasks, tracks the progression through workflow steps."""

    def __str__(self):
        return f"Task - {self.celery_task_id} ({self.status})"


class Document(TimeStampedModel):
    """
    Document Model
    --------------
    Documents are used to store information about the documents in a project. Each document belongs to a specific
    project and can have multiple pages. The Document model extends the TimeStampedModel, which provides self-updating
    'created' and 'modified' fields.

    Attributes
    ~~~~~~~~~~
    project : ForeignKey
        The project this document belongs to.
    title : CharField
        The title of the document.
    document_id : CharField
        The Transkribus document ID.
    metadata : JSONField
        Metadata for the document.
    last_parsed_at : DateTimeField
        The last time the document was parsed.
    is_parked : BooleanField
        Whether the document is parked (MOSAIC workflow state).
    is_ignored : BooleanField
        Whether the document is excluded from corpus (Transkribus 'Exclude' label).
    workflow_remarks : TextField
        Workflow remarks for the document.
    """

    STATUS_CHOICES = [
        ("open", "Open"),
        ("needs_tk_work", "Needs Correction on Transkribus"),
        ("reviewed", "Reviewed"),
    ]

    project = models.ForeignKey(
        Project, related_name="documents", on_delete=models.CASCADE
    )
    """The project this document belongs to."""

    title = models.CharField(max_length=512, blank=True, default="")
    """The title of the document."""

    document_id = models.CharField(max_length=30)
    """The Transkribus document ID."""

    metadata = models.JSONField(default=dict, blank=True)
    """Metadata for the document."""

    last_parsed_at = models.DateTimeField(null=True, blank=True)
    """The last time the document was parsed."""

    is_parked = models.BooleanField(default=False, blank=True)
    """Whether the document is parked (MOSAIC workflow state for deferred processing)."""

    is_ignored = models.BooleanField(default=False)
    """Whether the document is excluded from corpus (set from Transkribus 'Exclude' label)."""

    workflow_remarks = models.TextField(blank=True, default="")
    """Workflow remarks for the document."""

    is_reserved = models.BooleanField(default=False)
    """Whether the document is reserved for a workflow."""

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")

    class Meta:
        """Meta options for the Document model."""

        ordering = ["document_id"]

    def get_transkribus_url(self):
        """Return the URL to the Transkribus document."""
        return f"https://app.transkribus.org/collection/{self.project.collection_id}/doc/{self.document_id}"

    def get_active_pages(self):
        """Return the active pages of the document (non-excluded pages)."""
        return self.pages.filter(is_ignored=False)

    @staticmethod
    def get_active_documents(project):
        """Return active (non-excluded) documents for a project.

        Excludes documents with is_ignored=True (Transkribus 'Exclude' label).
        Does NOT exclude parked documents (is_parked=True) as those are workflow state.

        Args:
            project: Project instance

        Returns:
            QuerySet of non-excluded documents
        """
        return Document.objects.filter(project=project, is_ignored=False)

    def get_text(self):
        """
        Get the full text content of the document by concatenating all pages.

        Returns:
            str: Combined text from all pages in the document
        """
        text = ""
        for page in self.pages.all():
            text += page.get_text() + "\n"
        return text

    @staticmethod
    def get_distinct_metadata_keys():
        """
        Get all unique metadata keys across all documents.

        Returns:
            list: Sorted list of unique metadata keys found in document metadata fields
        """
        keys = set()
        for item in Document.objects.values_list("metadata", flat=True):
            if isinstance(item, dict):
                keys.update(item.keys())
        return sorted(keys)

    def __str__(self):
        """Return the string representation of the Document."""
        if self.title:
            return self.title

        return f"Document {self.document_id}"


class DocumentSyncHistory(TimeStampedModel):
    """
    DocumentSyncHistory Model
    -------------------------

    Tracks synchronization history for individual documents from Transkribus exports.
    Each sync operation creates DocumentSyncHistory records for affected documents,
    providing a detailed audit trail of what changed during each sync.

    This model enables users to:
    - View when a document was last synced
    - See exactly what changed (pages added/removed, tags updated, etc.)
    - Track which user performed the sync
    - Link to the full task details for more information

    Attributes
    ~~~~~~~~~~
    document : ForeignKey
        The document this sync history entry relates to.
    task : ForeignKey
        The Task that performed this sync operation.
    project : ForeignKey
        The project this document belongs to (denormalized for faster queries).
    user : ForeignKey
        The user who triggered the sync.
    sync_type : CharField
        Type of change: 'created', 'updated', 'unchanged', or 'deleted'.
    changes : JSONField
        Detailed JSON structure documenting all changes during sync.
        Structure:
        {
            "pages": {
                "added": [page_ids],
                "updated": [page_ids],
                "deleted": [page_ids]
            },
            "tags": {
                "added": int,
                "updated": int,
                "deleted": int,
                "preserved_assignments": int,
                "preserved_parked": int,
                "auto_assigned": int,
                "offset_shifts": [
                    {"line": "r_tl_1", "tag": "Wagner", "old_offset": 15, "new_offset": 16}
                ]
            },
            "metadata_updated": bool,
            "transcription_changes": bool,
            "warnings": [str]
        }
    synced_at : DateTimeField
        Timestamp when this sync occurred.
    """

    SYNC_TYPE_CHOICES = [
        ("created", "Created"),
        ("updated", "Updated"),
        ("unchanged", "Unchanged"),
        ("deleted", "Deleted"),
    ]

    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="sync_history"
    )
    """The document this sync history entry relates to."""

    task = models.ForeignKey(
        "Task", on_delete=models.CASCADE, related_name="document_syncs"
    )
    """The Task that performed this sync operation."""

    project = models.ForeignKey(
        "Project", on_delete=models.CASCADE, related_name="document_sync_history"
    )
    """The project this document belongs to."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="document_syncs"
    )
    """The user who triggered the sync."""

    sync_type = models.CharField(
        max_length=20, choices=SYNC_TYPE_CHOICES, default="updated"
    )
    """Type of change that occurred during sync."""

    changes = models.JSONField(default=dict, blank=True)
    """Detailed JSON structure documenting all changes during sync."""

    synced_at = models.DateTimeField(auto_now_add=True)
    """Timestamp when this sync occurred."""

    class Meta:
        """Meta options for the DocumentSyncHistory model."""

        ordering = ["-synced_at"]
        indexes = [
            models.Index(fields=["document", "-synced_at"]),
            models.Index(fields=["task"]),
            models.Index(fields=["project", "-synced_at"]),
        ]
        verbose_name = "Document Sync History"
        verbose_name_plural = "Document Sync Histories"

    def get_summary(self):
        """
        Return a human-readable summary of changes.

        Returns:
            str: Summary like "+5 tags, -2 tags, ~3 tags" or "No changes"
        """
        if self.sync_type == "unchanged":
            return "No changes"

        if self.sync_type == "created":
            return "Document created"

        if self.sync_type == "deleted":
            return "Document deleted"

        parts = []
        tags = self.changes.get("tags", {})

        if tags.get("added", 0) > 0:
            parts.append(f"+{tags['added']} tags")
        if tags.get("deleted", 0) > 0:
            parts.append(f"-{tags['deleted']} tags")
        if tags.get("updated", 0) > 0:
            parts.append(f"~{tags['updated']} tags")

        pages = self.changes.get("pages", {})
        if pages.get("added"):
            parts.append(f"+{len(pages['added'])} pages")
        if pages.get("deleted"):
            parts.append(f"-{len(pages['deleted'])} pages")

        if self.changes.get("transcription_changes"):
            parts.append("text changed")

        return ", ".join(parts) if parts else "Updated"

    def __str__(self):
        """Return the string representation of the DocumentSyncHistory."""
        return (
            f"Sync: {self.document.document_id} at {self.synced_at} ({self.sync_type})"
        )


def page_directory_path(instance, filename):
    """Gets the project name, processes it into a slug (a URL-friendly format without spaces or special characters)"""
    collection_id = instance.document.project.collection_id
    return f"transkribus_exports/{collection_id}/{filename}"


class Page(TimeStampedModel):
    """
    Page Model
    ----------

    Pages are used to store information about the pages in a document. Each page belongs to a specific document and
    can have multiple tags. The Page model extends the TimeStampedModel, which provides self-updating 'created' and
    'modified' fields.

    Attributes
    ~~~~~~~~~~
    document : ForeignKey
        The document this page belongs to.
    metadata : JSONField
        Metadata for the page.
    xml_file : FileField
        The XML file of the page.
    tk_page_id : CharField
        The Transkribus page ID.
    tk_page_number : IntegerField
        The page number in the Transkribus document.
    parsed_data : JSONField
        The parsed data of the page.
    num_tags : IntegerField
        The number of tags on the page.
    is_ignored : BooleanField
        Whether the page is ignored.
    """

    document = models.ForeignKey(
        Document, related_name="pages", on_delete=models.CASCADE
    )
    """The document this page belongs to."""

    metadata = models.JSONField(default=dict, blank=True)
    """Metadata for the page."""

    xml_file = models.FileField(
        upload_to=page_directory_path, null=False, blank=False, max_length=255
    )
    """The XML file of the page."""

    tk_page_id = models.CharField(max_length=30)
    """The Transkribus page ID."""

    tk_page_number = models.IntegerField(default=0)
    """The page number in the Transkribus document."""

    parsed_data = models.JSONField(default=dict, blank=True)
    """The parsed data of the page."""

    num_tags = models.IntegerField(default=0)
    """The number of tags on the page."""

    is_ignored = models.BooleanField(default=False)
    """Whether the page is ignored."""

    class Meta:
        ordering = ["tk_page_number"]

    def get_text(self):
        """Return the text of the page."""
        text = ""
        for element in self.parsed_data["elements"]:
            if "text" in element:
                text += element["text"] + "\n"
        return text  # TODO CHeck if this is correct

    def get_transkribus_url(self):
        """Return the URL to the Transkribus page."""
        return (
            f"https://app.transkribus.org/collection/{self.document.project.collection_id}/doc/"
            f"{self.document.document_id}/edit?pageNr={self.tk_page_number}"
        )

    @staticmethod
    def get_distinct_metadata_keys():
        """
        Get all unique metadata keys across all pages.

        Returns:
            list: Sorted list of unique metadata keys found in page metadata fields
        """
        keys = set()
        for item in Page.objects.values_list("metadata", flat=True):
            if isinstance(item, dict):
                keys.update(item.keys())
        return sorted(keys)

    def get_annotations(self):
        """Return the annotations of the page."""
        ret_items = []
        anno_types = []
        if "elements" in self.parsed_data:
            # print("Elements found ({})".format(len(self.parsed_data['elements'])))
            for item in self.parsed_data["elements"]:
                ret_item = {}
                element_data = item["element_data"]
                el_type = None
                el_coords = None

                ret_item["text"] = "\n".join(element_data["text_lines"])

                if "structure" in element_data["custom_structure"]:
                    el_type = element_data["custom_structure"]["structure"]["type"]
                    ret_item["type"] = el_type
                if "coords" in element_data:
                    el_coords = element_data["coords"]

                try:
                    file_url = self.parsed_data["file"]["imgUrl"]
                    coords = tk_bounding_box(el_coords)
                    url = tk_iiif_url(
                        file_url,
                        coords=",".join([str(c) for c in coords]),
                        image_size="pct:25",
                    )
                    ret_item["url"] = url
                except AttributeError:
                    ret_item["url"] = ""
                    # print("No file URL found")

                ret_item["id"] = element_data["id"]

                ret_items.append(ret_item)
                anno_types.append(el_type)

        return ret_items

    def get_image_url(self, scale_percent=None):
        """
        Get the URL to the page image with optional scaling.

        This method retrieves the image URL from the page's parsed data and
        optionally applies scaling using the IIIF protocol. This is particularly
        useful for multimodal AI prompts where you may want to optimize image
        size for better API performance or to stay within usage limitations.

        The scaled image maintains the same aspect ratio as the original but
        is resized to the specified percentage of its original dimensions.

        Args:
            scale_percent (int, optional): Percentage to scale the image (1-100).
                                         If None, returns the original URL without scaling.

        Returns:
            str: URL to the page image (either original or scaled via IIIF),
                 or None if no image URL is available for this page.

        Example:
            >>> page = Page.objects.get(pk=123)
            >>> # Get full resolution image URL
            >>> original_url = page.get_image_url()
            >>> # Get image scaled to 50% of original size
            >>> scaled_url = page.get_image_url(scale_percent=50)
        """
        try:
            if (
                "file" not in self.parsed_data
                or "imgUrl" not in self.parsed_data["file"]
            ):
                return None

            image_url = self.parsed_data["file"]["imgUrl"]

            # Return original URL if no scaling requested
            if scale_percent is None:
                return image_url

            # Apply scaling via IIIF
            return tk_iiif_url(image_url, image_size=f"pct:{scale_percent}")
        except Exception:
            return None

    def __str__(self):
        return f"Page {self.tk_page_number} of {self.document.document_id}"


class Dictionary(TimeStampedModel):
    """
    Dictionary Model
    ----------------
    Dictionaries are used to store dictionaries in the app. Each dictionary can have multiple entries. The Dictionary
    model extends the TimeStampedModel, which provides self-updating 'created' and 'modified' fields.

    Attributes
    ~~~~~~~~~~
    label : CharField
        The label of the dictionary. This should be unique and descriptive.
    type : CharField
        The type of the dictionary.
    """

    label = models.CharField(
        max_length=100,
        unique=True,
        help_text="The label of the dictionary. This should be unique and descriptive.",
    )
    """The label of the dictionary."""

    type = models.CharField(
        max_length=100,
        help_text="The type of the dictionary. This means the Transkribus tag type.",
    )
    """The type of the dictionary."""

    class Meta:
        """Meta options for the Dictionary model."""

        ordering = ["label"]

    def __str__(self):
        """Return the string representation of the Dictionary."""
        return self.label.__str__()


class DictionaryEntry(TimeStampedModel):
    """
    DictionaryEntry Model
    ---------------------
    DictionaryEntries are used to store entries in a dictionary. Each entry belongs to a specific dictionary and can
    have additional information about the entry. The DictionaryEntry model extends the TimeStampedModel, which provides
    self-updating 'created' and 'modified' fields.

    Attributes
    ~~~~~~~~~~
    dictionary : ForeignKey
        The dictionary this entry belongs to.
    label : CharField
        The label of the entry.
    metadata : JSONField
        Authorization data for the entry.
    notes : TextField
        Notes for the entry.
    """

    dictionary = models.ForeignKey(
        Dictionary, related_name="entries", on_delete=models.CASCADE
    )
    """The dictionary this entry belongs to."""

    label = models.CharField(max_length=255)
    """The label of the entry."""

    metadata = models.JSONField(default=dict, blank=True)
    """Metadata data for the entry."""

    notes = models.TextField(blank=True, default="")
    """Notes for the entry."""

    is_reserved = models.BooleanField(default=False)
    """Whether the entry is reserved for a workflow."""

    is_parked = models.BooleanField(default=False)
    """Whether the entry is parked (temporarily set aside during workflow)."""

    REVIEW_STATUS_CHOICES = [("pending", "Pending"), ("reviewed", "Reviewed")]
    review_status = models.CharField(
        max_length=20, choices=REVIEW_STATUS_CHOICES, default="pending"
    )
    """Review status of the entry (pending or reviewed)."""

    class Meta:
        """Meta options for the DictionaryEntry model."""

        ordering = ["label"]

    def get_text(self):
        """Return the text of the entry."""
        return self.label

    def get_documents(self):
        """Return the documents that contain this entry."""
        return Document.objects.filter(pages__tags__dictionary_entry=self).distinct()

    def get_num_usages(self):
        """Return the number of times this entry is used."""
        return PageTag.objects.filter(dictionary_entry=self).count()

    # Enrichment protocol methods
    def get_variation(self):
        """Return the text to be enriched."""
        return self.label

    def get_enrichment(self):
        """Return the enrichment data dictionary."""
        return self.metadata

    def set_enrichment(self, enrichment_type, normalized_value, enrichment_data, user=None):
        """
        Set enrichment data for this dictionary entry.

        Args:
            enrichment_type: Type of enrichment (e.g., "verse", "date", "authority_id")
            normalized_value: Human-readable normalized value
            enrichment_data: Dictionary of structured enrichment data
            user: User performing the enrichment (optional, for audit trail)
        """
        import logging
        logger = logging.getLogger(__name__)

        if self.metadata is None:
            self.metadata = {}

        self.metadata[enrichment_type] = {
            "normalized_value": normalized_value,
            "enrichment_data": enrichment_data,
        }
        logger.debug(f"DictionaryEntry.set_enrichment: ID={self.id}, label='{self.label}', type={enrichment_type}, value={normalized_value}")
        logger.debug(f"DictionaryEntry.set_enrichment: metadata before save={self.metadata}")
        self.save(current_user=user)
        # Reload from database to confirm
        self.refresh_from_db()
        logger.debug(f"DictionaryEntry.set_enrichment: After save, has_enrichment({enrichment_type})={self.has_enrichment(enrichment_type)}")

    def has_enrichment(self, enrichment_type=None):
        """
        Check if entry has enrichment data.

        Args:
            enrichment_type: Specific type to check, or None to check if any enrichment exists

        Returns:
            bool: True if enrichment exists
        """
        if not self.metadata:
            return False
        if enrichment_type is None:
            return len(self.metadata) > 0
        return enrichment_type in self.metadata

    def __str__(self):
        """Return the string representation of the DictionaryEntry."""
        return self.label


class PageTag(TimeStampedModel):
    """
    PageTag Model
    -------------

    PageTags are used to store tags on pages. Each PageTag belongs to a specific page and can have additional
    information about the tag. The PageTag model extends the TimeStampedModel, which provides self-updating 'created'
    and 'modified' fields.

    Attributes
    ~~~~~~~~~~
    page : ForeignKey
        The page this tag belongs to.
    variation : CharField
        The text of the tag.
    variation_type : CharField
        The type of the tag.
    dictionary_entry : ForeignKey
        The dictionary entry this tag is assigned to.
    additional_information : JSONField
        Additional information about the tag (DEPRECATED - use specific fields).
    date_variation_entry : ForeignKey
        The date variation entry.
    is_parked : BooleanField
        Whether the tag is parked.
    region_index : IntegerField
        Index of the TextRegion in reading order (0-based).
    line_index_in_region : IntegerField
        Index of line within region by readingOrder (0-based).
    line_index_global : IntegerField
        Sequential line number across entire page (0-based).
    line_text : TextField
        The actual text of this specific line (not joined region text).
    offset_in_line : IntegerField
        Character offset within the specific line.
    length : IntegerField
        Length of the tag text.
    """

    page = models.ForeignKey(Page, related_name="tags", on_delete=models.CASCADE)
    """The page this tag belongs to."""

    variation = models.CharField(max_length=255)
    """The text of the tag."""

    variation_type = models.CharField(max_length=100)
    """The type of the tag."""

    dictionary_entry = models.ForeignKey(
        DictionaryEntry, on_delete=models.SET_NULL, null=True, blank=True
    )
    """The dictionary entry this tag is assigned to."""

    additional_information = models.JSONField(default=dict, blank=True)
    """Additional information about the tag."""

    date_variation_entry = models.ForeignKey(
        "DateVariation", on_delete=models.SET_NULL, null=True, blank=True
    )
    """DEPRECATED: The date variation entry. Use tag_enrichment_entry instead."""

    tag_enrichment_entry = models.ForeignKey(
        "TagEnrichment", on_delete=models.SET_NULL, null=True, blank=True
    )
    """Generic enrichment entry for tags that need direct normalization."""

    enrichment = models.JSONField(default=dict, blank=True)
    """
    Unified enrichment data storage. Format:
    {
        enrichment_type: {
            "normalized_value": str,
            "enrichment_data": dict
        }
    }
    Examples: "verse", "date", "authority_id"
    """

    is_parked = models.BooleanField(default=False)
    """Whether the tag is parked."""

    is_reserved = models.BooleanField(default=False)
    """Whether the tag is reserved in an active workflow."""

    # New fields for clean positional tracking (from simple-alto-parser v0.0.22+)
    region_index = models.IntegerField(default=0)
    """Index of the TextRegion in reading order (0-based)"""

    line_index_in_region = models.IntegerField(default=0)
    """Index of line within region by readingOrder (0-based)"""

    line_index_global = models.IntegerField(default=0)
    """Sequential line number across entire page (0-based)"""

    line_text = models.TextField(default="", blank=True)
    """The actual text of this specific line (not joined region text)"""

    offset_in_line = models.IntegerField(default=0)
    """Character offset within the specific line"""

    length = models.IntegerField(default=0)
    """Length of the tag text"""

    class Meta:
        """Meta options for the PageTag model."""

        ordering = ["variation"]

    def is_resolved(self):
        """
        Return True if the tag has been resolved.

        A tag is considered resolved if it has been assigned to either:
        - A dictionary entry (dictionary_entry is not None), or
        - A date variation entry (date_variation_entry is not None), or
        - A tag enrichment entry (tag_enrichment_entry is not None), or
        - Has enrichment data in the enrichment field (enrichment is not empty)

        Future resolution criteria (e.g., specific additional_information fields)
        can be added here to centralize the logic.
        """
        return (
            self.dictionary_entry is not None
            or self.date_variation_entry is not None
            or self.tag_enrichment_entry is not None
            or bool(self.enrichment)
        )

    # Enrichment protocol methods
    def get_variation(self):
        """Return the text to be enriched."""
        return self.variation

    def get_enrichment(self):
        """Return the enrichment data dictionary."""
        return self.enrichment

    def set_enrichment(self, enrichment_type, normalized_value, enrichment_data, user=None):
        """
        Set enrichment data for this tag.

        Args:
            enrichment_type: Type of enrichment (e.g., "verse", "date", "authority_id")
            normalized_value: Human-readable normalized value
            enrichment_data: Dictionary of structured enrichment data
            user: User performing the enrichment (optional, for audit trail)
        """
        if self.enrichment is None:
            self.enrichment = {}

        self.enrichment[enrichment_type] = {
            "normalized_value": normalized_value,
            "enrichment_data": enrichment_data,
        }
        self.save(current_user=user)

    def has_enrichment(self, enrichment_type=None):
        """
        Check if tag has enrichment data.

        Args:
            enrichment_type: Specific type to check, or None to check if any enrichment exists

        Returns:
            bool: True if enrichment exists
        """
        if not self.enrichment:
            return False
        if enrichment_type is None:
            return len(self.enrichment) > 0
        return enrichment_type in self.enrichment

    def get_date(self):
        """Return the date in the format YYYY-MM-DD."""

        val = ""
        if "year" in self.additional_information:
            val = self.additional_information["year"]
        val += "-"
        if "month" in self.additional_information:
            val += f"{int(self.additional_information['month']):02}"
        val += "-"
        if "day" in self.additional_information:
            val += f"{int(self.additional_information['day']):02}"
        return val

    def get_transkribus_url(self):
        """Return the URL to the Transkribus page."""
        return (
            f"https://app.transkribus.org/collection/{self.page.document.project.collection_id}/doc/"
            f"{self.page.document.document_id}/edit?pageNr={self.page.tk_page_number}"
        )

    def get_context(self, context_chars=50):
        """
        Get KWIC (KeyWord In Context) view.

        Args:
            context_chars: Number of characters to show before/after the tag

        Returns:
            dict with 'before', 'tag', 'after', 'full_line' keys
        """
        if not self.line_text:
            return {"before": "", "tag": self.variation, "after": "", "full_line": ""}

        # IMPORTANT: PAGE XML offsets appear to be off by 1 (possibly 1-based indexing issue)
        # Adding +1 correction to get accurate text extraction
        adjusted_offset = self.offset_in_line + 1

        start = max(0, adjusted_offset - context_chars)
        end = min(len(self.line_text), adjusted_offset + self.length + context_chars)

        before = self.line_text[start:adjusted_offset]
        tag_text = self.line_text[adjusted_offset : adjusted_offset + self.length]
        after = self.line_text[adjusted_offset + self.length : end]

        return {
            "before": before,
            "tag": tag_text,
            "after": after,
            "full_line": self.line_text,
        }

    def get_highlighted_context(self, context_chars=50):
        """
        Get HTML with highlighted tag.

        Args:
            context_chars: Number of characters to show before/after the tag

        Returns:
            HTML string with tag highlighted
        """
        ctx = self.get_context(context_chars)
        return (
            f'{ctx["before"]}<mark class="bg-warning">{ctx["tag"]}</mark>{ctx["after"]}'
        )

    def __str__(self):
        """Return the string representation of the PageTag."""
        return f"{self.variation_type}: {self.variation} ({self.page.document.project.title})"


class Variation(TimeStampedModel):
    """
    Variation Model
    ---------------
    Variations are used to store different variations of dictionary entries. This model is used to store variations
    of dictionary entries and to link them to the dictionary entries. The Variation model is linked to the
    DictionaryEntry model via a ForeignKey, which means that each variation belongs to a specific dictionary entry.

    Attributes
    ~~~~~~~~~~
    entry : ForeignKey
        The dictionary entry this variation belongs to.
    variation : CharField
        The text of the variation.
    """

    entry = models.ForeignKey(
        DictionaryEntry, related_name="variations", on_delete=models.CASCADE
    )
    """The dictionary entry this variation belongs to."""

    variation = models.CharField(max_length=255)
    """The text of the variation."""

    class Meta:
        """Meta options for the Variation model."""

        ordering = ["variation"]

    def __str__(self):
        """Return the string representation of the Variation."""
        return self.variation


class DateVariation(TimeStampedModel):
    """
    DateVariation Model
    -------------------

    DateVariations are used to store different variations of dates. This model is used to store variations of dates
    and to link them to the dictionary entries. The DateVariation model is linked to the DictionaryEntry model via a
    ForeignKey, which means that each date variation belongs to a specific dictionary entry.

    Attributes
    ~~~~~~~~~~
    entry : ForeignKey
        The dictionary entry this date variation belongs to.
    variation : CharField
        The text of the variation.
    normalized_variation : JSONField
        The normalized version of the variation.
    edt_of_normalized_variation : CharField
        The EDTF of the normalized variation.
    """

    variation = models.CharField(max_length=255)
    """The text of the variation."""

    normalized_variation = models.JSONField(default=dict, blank=True)
    """The normalized version of the variation."""

    edtf_of_normalized_variation = models.CharField(max_length=100)
    """The EDTF of the normalized variation."""

    class Meta:
        """Meta options for the Variation model."""

        ordering = ["variation"]

    def __str__(self):
        """Return the string representation of the Variation."""
        return self.variation


class TagEnrichment(TimeStampedModel):
    """
    TagEnrichment Model
    -------------------

    Generic model for one-to-one tag enrichments (dates, verses, locations, etc.)
    that need normalization but not grouping into dictionary entries.

    Attributes
    ~~~~~~~~~~
    variation : CharField
        The original text variation to be enriched.
    enrichment_type : CharField
        The type of enrichment: 'date', 'verse', 'location', etc.
    normalized_value : CharField
        Human-readable normalized form (e.g., 'Hebrews 13:7', '1823-12-05').
    enrichment_data : JSONField
        Structured data specific to enrichment type.
        Examples:
        - Date: {"year": 1823, "month": 12, "day": 5, "edtf": "1823-12-05"}
        - Verse: {"book": "Hebrews", "chapter": 13, "verse": 7, "testament": "NT"}
    """

    variation = models.CharField(max_length=255)
    """Original text variation."""

    enrichment_type = models.CharField(max_length=50)
    """Type of enrichment: 'date', 'verse', 'location', etc."""

    normalized_value = models.CharField(max_length=500)
    """Human-readable normalized form (e.g., 'Hebrews 13:7', '1823-12-05')."""

    enrichment_data = models.JSONField(default=dict, blank=True)
    """Structured data specific to enrichment type."""

    class Meta:
        """Meta options for the TagEnrichment model."""

        ordering = ["variation"]
        indexes = [
            models.Index(fields=["enrichment_type", "variation"]),
        ]

    def __str__(self):
        """Return the string representation of the TagEnrichment."""
        return f"{self.variation} → {self.normalized_value}"


class Collection(TimeStampedModel):
    """
    Collection Model
    ----------------
    Collections are (who would've thought) collections of documents or document parts.
    A collection belongs to a project and can be used to group its documents in a meaningful way.
    This model extends the TimeStampedModel, which provides self-updating 'created' and 'modified' fields.

    Attributes
    ~~~~~~~~~~
    project : ForeignKey
        The project this collection belongs to.
    title : CharField
        The title of the collection. This is descriptive and should be unique within the project.
    description : TextField
        The description of the collection

    """

    project = models.ForeignKey(
        Project, related_name="collections", on_delete=models.CASCADE
    )
    """The project this collection belongs to."""

    title = models.CharField(max_length=255)
    """The title of the collection. This is descriptive and should be unique within the project."""

    description = models.TextField(blank=True, default="")
    """The description of the collection."""

    def __str__(self):
        """Return the string representation of the Collection."""
        return self.title

    class Meta:
        """Meta options for the Collection model."""

        ordering = ["title"]


class CollectionItem(TimeStampedModel):
    """
    CollectionItem Model
    --------------------

    CollectionItems are used to store items in a collection. Each CollectionItem belongs to a specific collection
    and can have additional information about the item. The CollectionItem model extends the TimeStampedModel, which
    provides self-updating 'created' and 'modified' fields.

    Attributes
    ~~~~~~~~~~
    collection : ForeignKey
        The collection this item belongs to.
    document : ForeignKey
        The document this item belongs to.
    document_configuration : JSONField
        The configuration of the document in the collection.
    title : CharField
        The title of the item.
    status : CharField
        The status of the item.
    review_notes : TextField
        Notes from the review of the item.
    """

    STATUS_CHOICES = (
        ("open", "Open"),
        ("reviewed", "Reviewed"),
        ("faulty", "Faulty"),
    )

    collection = models.ForeignKey(
        Collection, related_name="items", on_delete=models.CASCADE
    )
    """The collection this item belongs to."""

    document = models.ForeignKey(
        Document,
        related_name="collections",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    """The document this item belongs to."""

    document_configuration = models.JSONField(default=dict, blank=True)
    """The configuration of the document in the collection."""

    title = models.CharField(max_length=255)
    """The title of the item."""

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="open")
    """The status of the item."""

    metadata = models.JSONField(default=dict, blank=True)

    review_notes = models.TextField(blank=True, default="")
    """Notes from the review of the item."""

    is_reserved = models.BooleanField(default=False)
    """Whether the item is reserved for a workflow."""

    def __str__(self):
        """Return the string representation of the CollectionItem."""
        return f"{self.collection.title}: {self.title}"

    def get_text(self):
        """
        Get the full text content of the collection item from its annotations.

        Returns:
            str: Combined text from all annotations in the document configuration
        """
        annotations = self.document_configuration.get("annotations", [])
        collection_item_text = ""
        for anno in annotations:
            if "text" in anno:
                collection_item_text += anno["text"] + "\n"
        return collection_item_text

    def split(self, index, user=None):
        """Split the collection item at the given index."""
        annotations = self.document_configuration.get("annotations", [])

        # Validate the index
        if index < 0 or index > len(annotations):
            return None

        # Set user to the current modifier if none is provided
        if user is None:
            user = self.modified_by

        # Split annotations into two parts
        remaining_annotations = annotations[:index]
        new_annotations = annotations[index:]

        # If there's nothing to split (e.g., index is at the start or end), return None
        if not new_annotations or not remaining_annotations:
            return None

        # Create the new collection item
        new_item = CollectionItem(
            collection=self.collection,
            title=f"{self.title} (Part 2)",
            document_configuration={"annotations": new_annotations},
            status=self.status,
            review_notes=self.review_notes,
        )
        new_item.save(current_user=user)

        # Update the current item with remaining annotations
        self.document_configuration["annotations"] = remaining_annotations
        self.save(current_user=user)

        return new_item

    def delete_annotation(self, index, user=None):
        """Delete the annotation at the given index."""
        annotations = self.document_configuration.get("annotations", [])
        index = index - 1
        print("Index: ", index)
        # Validate the index
        if index < 0 or index >= len(annotations):
            return None

        # Set user to the current modifier if none is provided
        if user is None:
            user = self.modified_by

        # Remove the annotation
        annotations.pop(index)
        self.document_configuration["annotations"] = annotations
        self.save(current_user=user)

        return self

    class Meta:
        """Meta options for the Collection model."""

        ordering = ["title"]


class AIConfiguration(TimeStampedModel):
    """
    AIConfiguration Model
    ---------------------

    Reusable AI configuration that bundles everything needed for an AI call.
    Replaces the separation between Prompts, Credentials, and AI Settings.

    Each configuration includes:
    - Provider and model selection
    - API credentials
    - System role and prompt template
    - Execution settings (temperature, max_tokens, etc.)
    - Context relationships (documents, pages, collections)

    Attributes
    ~~~~~~~~~~
    project : ForeignKey
        The project this AI configuration belongs to.
    name : CharField
        Display name for the configuration (e.g., "Document Summarizer (GPT-4)").
    description : TextField
        What this configuration is used for.
    provider : CharField
        AI provider (openai, anthropic, genai, mistral, deepseek, qwen).
    model : CharField
        Model identifier (e.g., "gpt-4", "claude-3-opus-20240229").
    api_key : CharField
        API key for this provider.
    system_role : TextField
        System role/instructions for the AI.
    prompt_template : TextField
        Prompt template with {placeholders} for context variables.
    temperature : FloatField
        Sampling temperature (0.0-2.0).
    max_tokens : IntegerField
        Maximum tokens to generate.
    top_p : FloatField
        Nucleus sampling threshold.
    frequency_penalty : FloatField
        Frequency penalty (-2.0 to 2.0).
    presence_penalty : FloatField
        Presence penalty (-2.0 to 2.0).
    seed : IntegerField
        Random seed for deterministic sampling.
    document_context : ManyToManyField
        Documents to include in context.
    page_context : ManyToManyField
        Pages to include in context.
    collection_context : ManyToManyField
        Collection items to include in context.
    is_active : BooleanField
        Whether this configuration is active and visible in selectors.
    usage_count : IntegerField
        Number of times this configuration has been used.
    """

    PROVIDER_CHOICES = [
        ("openai", "OpenAI (ChatGPT)"),
        ("anthropic", "Anthropic (Claude)"),
        ("genai", "Google (Gemini)"),
        ("mistral", "Mistral AI"),
        ("deepseek", "DeepSeek"),
        ("qwen", "Qwen"),
    ]

    project = models.ForeignKey(
        Project, related_name="ai_configs", on_delete=models.CASCADE
    )
    """The project this AI configuration belongs to."""

    # Identity
    name = models.CharField(
        max_length=200,
        help_text="Display name, e.g., 'Document Summarizer (GPT-4)'",
    )
    """Display name for the configuration."""

    description = models.TextField(
        blank=True, help_text="What this configuration is used for"
    )
    """Description of what this configuration is used for."""

    # Provider & Model
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES)
    """AI provider selection."""

    model = models.CharField(
        max_length=100,
        help_text="Model identifier, e.g., 'gpt-4', 'claude-3-opus-20240229'",
    )
    """Model identifier."""

    # Credentials
    api_key = models.CharField(
        max_length=500, help_text="API key for this provider"
    )
    """API key for this provider."""

    # Prompt Configuration
    system_role = models.TextField(
        help_text="System role/instructions for the AI"
    )
    """System role/instructions for the AI."""

    prompt_template = models.TextField(
        help_text="Prompt template with {placeholders} for context. "
        "Example: 'Summarize: {document_text}'"
    )
    """Prompt template with placeholders for context variables."""

    # Execution Settings (optional overrides)
    temperature = models.FloatField(
        null=True, blank=True, default=0.5, help_text="Sampling temperature (0.0-2.0)"
    )
    """Sampling temperature."""

    max_tokens = models.IntegerField(
        null=True, blank=True, default=2048, help_text="Maximum tokens to generate"
    )
    """Maximum tokens to generate."""

    top_p = models.FloatField(
        null=True, blank=True, default=1.0, help_text="Nucleus sampling threshold"
    )
    """Nucleus sampling threshold."""

    frequency_penalty = models.FloatField(
        null=True,
        blank=True,
        default=0.0,
        help_text="Frequency penalty (-2.0 to 2.0)",
    )
    """Frequency penalty."""

    presence_penalty = models.FloatField(
        null=True, blank=True, default=0.0, help_text="Presence penalty (-2.0 to 2.0)"
    )
    """Presence penalty."""

    seed = models.IntegerField(
        null=True, blank=True, help_text="Random seed for deterministic sampling"
    )
    """Random seed for deterministic sampling."""

    # Context relationships (preserved from Prompt model)
    document_context = models.ManyToManyField(
        Document, related_name="ai_configs", blank=True
    )
    """Documents to include in context."""

    page_context = models.ManyToManyField(Page, related_name="ai_configs", blank=True)
    """Pages to include in context."""

    collection_context = models.ManyToManyField(
        CollectionItem, related_name="ai_configs", blank=True
    )
    """Collection items to include in context."""

    # Metadata
    is_active = models.BooleanField(
        default=True, help_text="Disable to hide from workflow selectors"
    )
    """Whether this configuration is active."""

    usage_count = models.IntegerField(
        default=0, help_text="Track how often this config is used"
    )
    """Number of times this configuration has been used."""

    class Meta:
        """Meta options for the AIConfiguration model."""

        ordering = ["name"]
        unique_together = [["project", "name"]]

    def __str__(self):
        """Return the string representation of the AIConfiguration."""
        return f"{self.name} ({self.get_provider_display()})"

    def execute(self, context_variables: dict) -> tuple:
        """
        Execute this AI configuration with given context variables.

        Parameters
        ----------
        context_variables : dict
            Variables to fill into prompt_template, e.g., {"document_text": "..."}

        Returns
        -------
        tuple[str, float]
            (response_text, duration_seconds)
        """
        from twf.clients.ai_client_adapter import create_ai_client

        # Fill in prompt template
        filled_prompt = self.prompt_template.format(**context_variables)

        # Create client with minimal settings
        client = create_ai_client(
            provider=self.provider,
            api_key=self.api_key,
            system_prompt=self.system_role,
        )

        # Execute with just model and prompt - no extra parameters
        response_text, duration = client.prompt(
            model=self.model,
            prompt=filled_prompt
        )

        # Track usage
        self.usage_count += 1
        self.save()

        return response_text, duration

    def test_connection(self) -> bool:
        """
        Test if the API credentials are valid.

        Returns
        -------
        bool
            True if connection is successful, False otherwise.
        """
        try:
            self.execute({"test": "connection"})
            return True
        except Exception:
            return False


class Workflow(models.Model):
    """Model to store workflow information."""

    WORKFLOW_TYPE_CHOICES = [
        ("review_documents", "Review Documents"),
        ("review_collection", "Review Collection"),
        ("supervised_dictionary", "Supervised Dictionary Workflow"),
        ("review_tags_grouping", "Review Tag Grouping"),
        ("review_tags_dates", "Review Date Normalization"),  # Backward compatibility
        ("review_tags_enrichment", "Review Tag Enrichment"),  # Generic enrichment
        ("review_dictionary_enrichment", "Review Dictionary Enrichment"),
        ("review_dictionary_entries", "Review Dictionary Entries"),
        ("review_metadata_documents", "Review Document Metadata"),
        ("review_metadata_pages", "Review Page Metadata"),
    ]

    project = models.ForeignKey("Project", on_delete=models.CASCADE)
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="workflows"
    )

    workflow_type = models.CharField(max_length=50, choices=WORKFLOW_TYPE_CHOICES)
    status = models.CharField(
        max_length=20,
        choices=[("started", "Started"), ("ended", "Ended")],
        default="started",
    )
    item_count = models.PositiveIntegerField()
    current_item_index = models.PositiveIntegerField(default=0)

    collection = models.ForeignKey(
        "Collection", on_delete=models.SET_NULL, null=True, blank=True
    )
    dictionary = models.ForeignKey(
        "Dictionary", on_delete=models.SET_NULL, null=True, blank=True
    )
    related_task = models.OneToOneField(
        "Task",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workflow",
    )
    metadata = models.JSONField(default=dict, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Newly added field to store assigned documents
    assigned_document_items = models.ManyToManyField(
        "Document", related_name="workflows"
    )
    assigned_dictionary_entries = models.ManyToManyField(
        "DictionaryEntry", related_name="workflows"
    )
    assigned_collection_items = models.ManyToManyField(
        "CollectionItem", related_name="workflows"
    )
    assigned_tag_items = models.ManyToManyField(
        "PageTag", related_name="workflows", blank=True
    )
    assigned_page_items = models.ManyToManyField(
        "Page", related_name="workflows", blank=True
    )

    def get_next_item(self):
        """Fetch the next item to work on."""
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"===== Workflow.get_next_item CALLED: type={self.workflow_type}, index={self.current_item_index}/{self.item_count} =====")

        try:
            if self.workflow_type == "review_documents":
                if self.current_item_index < self.item_count:
                    item = self.assigned_document_items.all().order_by("pk")[
                        self.current_item_index
                    ]
                    return item
            if self.workflow_type == "review_collection":
                if self.current_item_index < self.item_count:
                    item = self.assigned_collection_items.all().order_by("pk")[
                        self.current_item_index
                    ]
                    return item
            if self.workflow_type == "review_tags_grouping":
                # For tag grouping, get next unassigned tag from reserved items
                return (
                    self.assigned_tag_items.filter(
                        dictionary_entry__isnull=True, is_parked=False
                    )
                    .order_by("pk")
                    .first()
                )
            if self.workflow_type == "review_tags_dates":
                # For date normalization, get next unresolved date tag
                return (
                    self.assigned_tag_items.filter(
                        date_variation_entry__isnull=True, is_parked=False
                    )
                    .order_by("pk")
                    .first()
                )
            if self.workflow_type == "review_tags_enrichment":
                # For generic enrichment, get next unenriched tag
                # A tag is unenriched if BOTH:
                # - No old tag_enrichment_entry AND
                # - No new enrichment data (null or empty dict)
                from django.db.models import Q
                return (
                    self.assigned_tag_items.filter(
                        tag_enrichment_entry__isnull=True,
                        is_parked=False
                    )
                    .filter(
                        Q(enrichment__isnull=True) | Q(enrichment={})
                    )
                    .order_by("pk")
                    .first()
                )
            if self.workflow_type == "review_dictionary_enrichment":
                # For dictionary enrichment, get next unenriched entry
                # Check if entry has the specific enrichment type from metadata
                enrichment_type = self.metadata.get("enrichment_type")
                logger.debug(f"DICT ENRICH: enrichment_type={enrichment_type}, current_index={self.current_item_index}/{self.item_count}")

                if not enrichment_type:
                    logger.error("DICT ENRICH: No enrichment_type in workflow metadata!")
                    return None

                # We need to check each entry individually since metadata structure varies
                all_entries = list(self.assigned_dictionary_entries.all().order_by("pk"))
                logger.debug(f"DICT ENRICH: Checking {len(all_entries)} assigned entries")

                for idx, entry in enumerate(all_entries):
                    # Refresh from database to ensure we have latest data
                    entry.refresh_from_db()
                    logger.debug(f"DICT ENRICH: Entry {idx}: ID={entry.id}, label='{entry.label}', is_parked={entry.is_parked}, metadata keys={list(entry.metadata.keys() if entry.metadata else [])}")

                    # Skip parked entries
                    if entry.is_parked:
                        logger.debug(f"DICT ENRICH: ✗ Skipping entry {idx} (parked)")
                        continue

                    has_enrich = entry.has_enrichment(enrichment_type)
                    logger.debug(f"DICT ENRICH: Entry {idx}: has_enrichment({enrichment_type})={has_enrich}")

                    if not has_enrich:
                        logger.debug(f"DICT ENRICH: ✓ Returning entry {idx} (ID={entry.id}, label='{entry.label}')")
                        return entry
                    else:
                        logger.debug(f"DICT ENRICH: ✗ Skipping entry {idx} (already enriched)")

                logger.debug("DICT ENRICH: No unenriched entries found, returning None")
                return None
            if self.workflow_type == "review_dictionary_entries":
                if self.current_item_index < self.item_count:
                    item = self.assigned_dictionary_entries.all().order_by("pk")[
                        self.current_item_index
                    ]
                    return item
            if self.workflow_type == "review_metadata_documents":
                if self.current_item_index < self.item_count:
                    item = self.assigned_document_items.all().order_by("pk")[
                        self.current_item_index
                    ]
                    return item
            if self.workflow_type == "review_metadata_pages":
                if self.current_item_index < self.item_count:
                    item = self.assigned_page_items.all().order_by("pk")[
                        self.current_item_index
                    ]
                    return item
        except IndexError:
            return None

        return None

    def advance(self, item_description=None):
        """
        Advance the workflow to the next item and log progress.

        Args:
            item_description: Optional description of the completed item (e.g., "Document 12345")
        """
        self.current_item_index += 1
        self.save()

        # Update the related task with progress
        if self.related_task:
            # Calculate progress percentage
            progress = int((self.current_item_index / self.item_count) * 100) if self.item_count > 0 else 0

            # Build progress message
            if item_description:
                progress_msg = f"✓ Completed: {item_description} ({self.current_item_index}/{self.item_count})\n"
            else:
                progress_msg = f"✓ Progress: {self.current_item_index}/{self.item_count} items completed\n"

            # Update task
            self.related_task.text += progress_msg
            self.related_task.progress = progress
            self.related_task.title = f"Review Workflow: {self.current_item_index}/{self.item_count} completed ({progress}%)"

            # Update workflow_steps in the task
            if not self.related_task.workflow_steps:
                self.related_task.workflow_steps = {
                    "current_step": 0,
                    "total_steps": self.item_count,
                    "steps": []
                }

            # Mark previous step as completed if it exists
            if self.related_task.workflow_steps.get("steps"):
                last_step_index = len(self.related_task.workflow_steps["steps"]) - 1
                if last_step_index >= 0:
                    self.related_task.workflow_steps["steps"][last_step_index]["status"] = "completed"
                    self.related_task.workflow_steps["steps"][last_step_index]["completed_at"] = timezone.now().isoformat()

            # Add new step
            self.related_task.workflow_steps["current_step"] = self.current_item_index
            self.related_task.workflow_steps["steps"].append({
                "index": self.current_item_index,
                "description": item_description or f"Item {self.current_item_index}",
                "status": "in_progress" if self.current_item_index < self.item_count else "completed",
                "started_at": timezone.now().isoformat()
            })

            self.related_task.save(update_fields=["text", "progress", "title", "workflow_steps"])

    def finish(self, with_error=False):
        """Mark the workflow as ended and finalize the related task."""
        self.status = "ended"
        self.save()

        # Update the related task status if linked
        if self.related_task:
            # Calculate duration
            if self.related_task.start_time:
                duration = (timezone.now() - self.related_task.start_time).total_seconds()
                duration_str = f"{int(duration // 60)}m {int(duration % 60)}s" if duration > 60 else f"{duration:.0f}s"
            else:
                duration_str = "unknown"

            # Add completion summary
            self.related_task.text += "\n" + "=" * 60 + "\n"
            if with_error:
                self.related_task.text += "WORKFLOW ENDED WITH ERRORS\n"
                self.related_task.status = "FAILURE"
                self.related_task.title = f"Review Workflow: Failed after {self.current_item_index}/{self.item_count}"
            else:
                self.related_task.text += "WORKFLOW COMPLETED SUCCESSFULLY\n"
                self.related_task.status = "SUCCESS"
                self.related_task.title = f"Review Workflow: Completed {self.current_item_index}/{self.item_count} items"

            self.related_task.text += "=" * 60 + "\n"
            self.related_task.text += f"Items completed: {self.current_item_index}/{self.item_count}\n"
            self.related_task.text += f"Duration: {duration_str}\n"
            self.related_task.progress = 100
            self.related_task.end_time = timezone.now()

            # Finalize workflow_steps - mark last step as completed
            if self.related_task.workflow_steps and self.related_task.workflow_steps.get("steps"):
                last_step_index = len(self.related_task.workflow_steps["steps"]) - 1
                if last_step_index >= 0 and self.related_task.workflow_steps["steps"][last_step_index].get("status") == "in_progress":
                    self.related_task.workflow_steps["steps"][last_step_index]["status"] = "completed"
                    self.related_task.workflow_steps["steps"][last_step_index]["completed_at"] = timezone.now().isoformat()

                # Add summary to workflow_steps
                self.related_task.workflow_steps["completed"] = True
                self.related_task.workflow_steps["completed_at"] = timezone.now().isoformat()
                self.related_task.workflow_steps["with_error"] = with_error
                self.related_task.workflow_steps["duration_seconds"] = duration if self.related_task.start_time else None

            self.related_task.save(update_fields=["text", "status", "title", "progress", "end_time", "workflow_steps"])

        # Restore the reserved status of the items
        if self.workflow_type == "review_documents":
            for item in self.assigned_document_items.all():
                item.is_reserved = False
                item.save()
        if self.workflow_type == "review_collection":
            for item in self.assigned_collection_items.all():
                item.is_reserved = False
                item.save()
        if self.workflow_type in [
            "review_tags_grouping",
            "review_tags_dates",
            "review_tags_enrichment",
        ]:
            self.assigned_tag_items.all().update(is_reserved=False)
        if self.workflow_type == "review_dictionary_enrichment":
            self.assigned_dictionary_entries.all().update(is_reserved=False)

    def cancel(self):
        """Cancel the workflow and release reserved items."""
        self.status = "ended"
        self.save()

        # Release reserved items
        if self.workflow_type == "review_documents":
            self.assigned_document_items.all().update(is_reserved=False)
        elif self.workflow_type == "review_collection":
            self.assigned_collection_items.all().update(is_reserved=False)
        elif self.workflow_type in [
            "review_tags_grouping",
            "review_tags_dates",
            "review_tags_enrichment",
        ]:
            self.assigned_tag_items.all().update(is_reserved=False)
        elif self.workflow_type == "review_dictionary_enrichment":
            self.assigned_dictionary_entries.all().update(is_reserved=False)

    def has_more_items(self):
        """Check if there are more items to work on."""
        return self.current_item_index + 1 < self.item_count

    def get_progress(self):
        """Calculate workflow progress.

        Returns
        -------
        dict
            Dictionary with keys: total, completed, remaining, percentage
        """
        if self.workflow_type == "review_tags_grouping":
            total = self.assigned_tag_items.count()
            remaining = self.assigned_tag_items.filter(
                dictionary_entry__isnull=True, is_parked=False
            ).count()
        elif self.workflow_type == "review_tags_dates":
            total = self.assigned_tag_items.count()
            remaining = self.assigned_tag_items.filter(
                date_variation_entry__isnull=True, is_parked=False
            ).count()
        elif self.workflow_type == "review_tags_enrichment":
            total = self.assigned_tag_items.count()
            from django.db.models import Q
            remaining = self.assigned_tag_items.filter(
                tag_enrichment_entry__isnull=True, is_parked=False
            ).filter(Q(enrichment__isnull=True) | Q(enrichment={})).count()
        elif self.workflow_type == "review_dictionary_enrichment":
            total = self.assigned_dictionary_entries.count()
            enrichment_type = self.metadata.get("enrichment_type")
            # Count entries that don't have this specific enrichment type
            remaining = 0
            for entry in self.assigned_dictionary_entries.all():
                if not entry.has_enrichment(enrichment_type):
                    remaining += 1
        else:
            # For document and collection workflows, use index-based progress
            total = self.item_count
            remaining = total - self.current_item_index

        completed = total - remaining
        percentage = (completed / total * 100) if total > 0 else 0

        return {
            "total": total,
            "completed": completed,
            "remaining": remaining,
            "percentage": round(percentage, 1),
        }

    def get_workflow_definition(self):
        """Get workflow definition from project configuration.

        Returns
        -------
        dict
            Workflow definition containing title, description, instructions,
            instruction_format, fields, and batch_size
        """
        return self.project.get_workflow_definition(self.workflow_type)

    def get_instructions(self):
        """Get workflow instructions as HTML.

        Returns
        -------
        str
            HTML-formatted instructions (from markdown if configured)
        """
        definition = self.get_workflow_definition()
        instructions = definition.get("instructions", "")
        if instructions and definition.get("instruction_format") == "markdown":
            from markdown import markdown

            return markdown(instructions)
        return instructions

    def get_custom_fields(self):
        """Get custom field definitions.

        Returns
        -------
        dict
            Dictionary of custom field definitions
        """
        return self.get_workflow_definition().get("fields", {})


class ExportConfiguration(TimeStampedModel):
    """
    ExportConfiguration Model
    """
    EXPORT_TYPES = [
        ("document", "Document Export"),
        ("page", "Page Export"),
        ("collection", "Collection Export"),
        ("dictionary", "Dictionary Export"),
        ("tag_report", "Tag Occurrence Report"),
    ]

    OUTPUT_FORMATS = [
        ("json", "JSON"),
        ("csv", "CSV"),
    ]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="export_configurations"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    export_type = models.CharField(max_length=20, choices=EXPORT_TYPES)
    output_format = models.CharField(
        max_length=10, choices=OUTPUT_FORMATS, default="json"
    )
    config = models.JSONField(default=dict)

    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    def __str__(self):
        return self.name


class Export(TimeStampedModel):
    """Model to store export information."""

    export_configuration = models.ForeignKey(
        ExportConfiguration, on_delete=models.CASCADE, related_name="exports"
    )
    export_file = models.FileField(upload_to="exports/", blank=True, null=True)

    def __str__(self):
        return f"Export - {self.export_configuration}"


class Note(TimeStampedModel):
    """Model to store notes for a project."""

    project = models.ForeignKey(Project, related_name="notes", on_delete=models.CASCADE)
    """The project this note belongs to."""

    title = models.CharField(max_length=255)
    """The title of the note."""

    note = models.TextField()
    """The content of the note."""

    def __str__(self):
        return f"Note - {self.title}"
