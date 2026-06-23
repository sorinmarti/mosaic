"""Forms for creating and updating project settings.
The settings views are separated into different forms for each section of the settings."""

import json

from crispy_forms.bootstrap import TabHolder, Tab
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Row, Column, Div, Field, HTML, Fieldset
from django import forms
from django.forms import TextInput
from django.urls import reverse
from django.utils.safestring import mark_safe
from django_select2.forms import Select2MultipleWidget, Select2Widget, Select2TagWidget
from markdown import markdown

from twf.clients import zenodo_client
from twf.models import Project, Note
from twf.permissions import ENTITY_TYPES


class DisplaySettingsForm(forms.ModelForm):
    """Form for creating and updating display settings.

    This form provides controls for configuring various display-related settings
    for the project, such as pagination, table views, and UI preferences.
    """

    active_tab = forms.CharField(widget=forms.HiddenInput(), required=False)

    # Table display settings
    table_items_per_page = forms.IntegerField(
        label="Items Per Page",
        required=False,
        min_value=5,
        max_value=100,
        initial=10,
        help_text="Number of items to display per page in tables (min: 5, max: 100, default: 10)",
    )

    table_compact_view = forms.BooleanField(
        label="Use Compact Table View",
        required=False,
        initial=False,
        help_text="Display tables in a more compact format with less padding",
    )

    # Document display settings
    document_show_metadata = forms.BooleanField(
        label="Show Metadata in Document View",
        required=False,
        initial=True,
        help_text="Always display document metadata in document views",
    )

    document_show_images = forms.BooleanField(
        label="Show Images in Document View",
        required=False,
        initial=True,
        help_text="Display page images when viewing documents",
    )

    # Collection display settings
    collection_show_annotations = forms.BooleanField(
        label="Show Annotations in Collection View",
        required=False,
        initial=True,
        help_text="Display annotations when viewing collections",
    )

    # Dashboard display settings
    dashboard_show_statistics = forms.BooleanField(
        label="Show Statistics on Dashboard",
        required=False,
        initial=True,
        help_text="Display project statistics on the dashboard",
    )

    dashboard_show_recent_activity = forms.BooleanField(
        label="Show Recent Activity on Dashboard",
        required=False,
        initial=True,
        help_text="Display recent project activity on the dashboard",
    )

    # Advanced display settings
    enable_dark_mode = forms.BooleanField(
        label="Enable Dark Mode",
        required=False,
        initial=False,
        help_text="Use dark color scheme for the UI",
    )

    class Meta:
        model = Project
        fields = ["conf_display"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Populate fields from conf_display JSON if data exists
        conf_display = self.instance.conf_display or {}

        # Table settings
        table_settings = conf_display.get("table", {})
        self.fields["table_items_per_page"].initial = table_settings.get(
            "items_per_page", 10
        )
        self.fields["table_compact_view"].initial = table_settings.get(
            "compact_view", False
        )

        # Document settings
        document_settings = conf_display.get("document", {})
        self.fields["document_show_metadata"].initial = document_settings.get(
            "show_metadata", True
        )
        self.fields["document_show_images"].initial = document_settings.get(
            "show_images", True
        )

        # Collection settings
        collection_settings = conf_display.get("collection", {})
        self.fields["collection_show_annotations"].initial = collection_settings.get(
            "show_annotations", True
        )

        # Dashboard settings
        dashboard_settings = conf_display.get("dashboard", {})
        self.fields["dashboard_show_statistics"].initial = dashboard_settings.get(
            "show_statistics", True
        )
        self.fields["dashboard_show_recent_activity"].initial = dashboard_settings.get(
            "show_recent_activity", True
        )

        # Advanced settings
        advanced_settings = conf_display.get("advanced", {})
        self.fields["enable_dark_mode"].initial = advanced_settings.get(
            "dark_mode", False
        )

        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_class = "form form-control"
        self.helper.layout = Layout(
            TabHolder(
                Tab(
                    "Table Display",
                    Row(
                        Column("table_items_per_page", css_class="col-6"),
                        Column("table_compact_view", css_class="col-6"),
                    ),
                    css_id="table",
                ),
                Tab(
                    "Document Display",
                    Row(
                        Column("document_show_metadata", css_class="col-6"),
                        Column("document_show_images", css_class="col-6"),
                    ),
                    css_id="document",
                ),
                Tab(
                    "Collection Display",
                    Row(
                        Column("collection_show_annotations", css_class="col-12"),
                    ),
                    css_id="collection",
                ),
                Tab(
                    "Dashboard Display",
                    Row(
                        Column("dashboard_show_statistics", css_class="col-6"),
                        Column("dashboard_show_recent_activity", css_class="col-6"),
                    ),
                    css_id="dashboard",
                ),
                Tab(
                    "Advanced",
                    Row(
                        Column("enable_dark_mode", css_class="col-12"),
                    ),
                    css_id="advanced",
                ),
            ),
            Div(
                Submit("submit", "Save Settings", css_class="btn btn-dark"),
                css_class="text-end pt-3",
            ),
            "active_tab",
        )

    def clean(self):
        """Clean and save display settings data back into the JSONField `conf_display`."""
        cleaned_data = super().clean()
        self.instance.conf_display = {
            "table": {
                "items_per_page": cleaned_data.get("table_items_per_page"),
                "compact_view": cleaned_data.get("table_compact_view"),
            },
            "document": {
                "show_metadata": cleaned_data.get("document_show_metadata"),
                "show_images": cleaned_data.get("document_show_images"),
            },
            "collection": {
                "show_annotations": cleaned_data.get("collection_show_annotations"),
            },
            "dashboard": {
                "show_statistics": cleaned_data.get("dashboard_show_statistics"),
                "show_recent_activity": cleaned_data.get(
                    "dashboard_show_recent_activity"
                ),
            },
            "advanced": {
                "dark_mode": cleaned_data.get("enable_dark_mode"),
            },
        }
        return cleaned_data


class CreateProjectForm(forms.ModelForm):
    """
    Form for creating a new project.
    """

    class Meta:
        """Metaclass for CreateProjectForm."""
        model = Project
        fields = ["title", "description", "collection_id", "owner", "members"]
        widgets = {
            "members": Select2MultipleWidget(attrs={"style": "width: 100%;"}),
            "owner": Select2Widget(attrs={"style": "width: 100%;"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_class = "form"
        self.helper.layout = Layout(
            Row(
                Column("title", css_class="form-group col-6 mb-3"),
                Column("collection_id", css_class="form-group col-6 mb-3"),
                css_class="row form-row",
            ),
            Row(
                Column("description", css_class="form-group col-12 mb-3"),
                css_class="row form-row",
            ),
            Row(
                Column("owner", css_class="form-group col-6 mb-3"),
                Column("members", css_class="form-group col-6 mb-3"),
                css_class="row form-row",
            ),
            Div(
                Submit("submit", "Create Project", css_class="btn btn-dark"),
                css_class="text-end pt-3",
            ),
        )


class PasswordInputRetain(forms.PasswordInput):
    """A PasswordInput widget that retains the value when the form is re-rendered.
    This is used for password fields in the settings forms."""

    def render(self, name, value, attrs=None, renderer=None):
        """Render the widget with the value retained."""
        if value is None:
            value = ""
        # Set the value attribute if there's a value present
        if value:
            attrs = attrs or {}
            attrs["value"] = value
        return super().render(name, value, attrs, renderer)


class TranskribusCredentialsForm(forms.Form):
    """Simple form for managing Transkribus credentials."""

    transkribus_username = forms.CharField(
        required=False,
        label="Transkribus Username",
        widget=TextInput(attrs={"placeholder": "Transkribus Username"}),
    )
    transkribus_password = forms.CharField(
        required=False,
        label="Transkribus Password",
        widget=PasswordInputRetain(attrs={"placeholder": "Transkribus Password"}),
    )

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop("project", None)
        super().__init__(*args, **kwargs)

        # Populate from existing credentials
        if self.project:
            transkribus_creds = self.project.get_credentials("transkribus")
            if transkribus_creds:
                self.fields["transkribus_username"].initial = transkribus_creds.get("username", "")
                self.fields["transkribus_password"].initial = transkribus_creds.get("password", "")

        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_class = "form form-control"
        self.helper.layout = Layout(
            Fieldset(
                "Transkribus Credentials",
                Row(
                    Column("transkribus_username", css_class="form-group col-6 mb-3"),
                    Column("transkribus_password", css_class="form-group col-6 mb-3"),
                    css_class="row form-row",
                ),
            ),
            Div(
                Submit("submit", "Save Credentials", css_class="btn btn-dark"),
                css_class="text-end pt-3",
            ),
        )

    def save(self):
        """Save credentials to project."""
        if self.project and self.is_valid():
            username = self.cleaned_data.get("transkribus_username")
            password = self.cleaned_data.get("transkribus_password")

            credentials = self.project.conf_credentials or {}
            credentials["transkribus"] = {
                "username": username or "",
                "password": password or "",
            }
            self.project.conf_credentials = credentials
            self.project.save()


class ZenodoCredentialsForm(forms.Form):
    """Simple form for managing Zenodo credentials."""

    zenodo_token = forms.CharField(
        required=False,
        label="Zenodo Access Token",
        widget=TextInput(attrs={"placeholder": "Zenodo Access Token"}),
        help_text="Get your access token from zenodo.org (Account → Applications → Personal access tokens)",
    )

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop("project", None)
        super().__init__(*args, **kwargs)

        # Populate from existing credentials
        if self.project:
            zenodo_creds = self.project.get_credentials("zenodo")
            if zenodo_creds:
                self.fields["zenodo_token"].initial = zenodo_creds.get("zenodo_token", "")

        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_class = "form form-control"
        self.helper.layout = Layout(
            Fieldset(
                "Zenodo Credentials",
                Row(
                    Column("zenodo_token", css_class="form-group col-12 mb-3"),
                    css_class="row form-row",
                ),
            ),
            Div(
                Submit("submit", "Save Credentials", css_class="btn btn-dark"),
                css_class="text-end pt-3",
            ),
        )

    def save(self):
        """Save credentials to project."""
        if self.project and self.is_valid():
            token = self.cleaned_data.get("zenodo_token")

            credentials = self.project.conf_credentials or {}
            credentials["zenodo"] = {
                "zenodo_token": token or "",
            }
            self.project.conf_credentials = credentials
            self.project.save()


class GeneralSettingsForm(forms.ModelForm):
    """Form for creating and updating general settings.

    General settings include the project title, description, owner, members, and selected dictionaries.

    It enforces the following restrictions:
    1. Project owners cannot change ownership to another user
    2. Project members cannot remove themselves from the project
    """

    class Meta:
        model = Project
        fields = ["title", "description", "owner", "members"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "owner": Select2Widget(attrs={"style": "width: 100%;"}),
            "members": Select2MultipleWidget(attrs={"style": "width: 100%;"}),
        }

    def __init__(self, *args, **kwargs):
        # Get the current user from kwargs
        self.current_user = kwargs.pop("current_user", None)

        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_class = "form form-control"

        instance = kwargs.get("instance")

        # If the current user is the owner, disable the owner field
        if (
            self.current_user
            and instance
            and hasattr(instance, "owner")
            and hasattr(self.current_user, "profile")
        ):
            if instance.owner == self.current_user.profile:
                self.fields["owner"].disabled = True
                self.fields["owner"].help_text = (
                    "You cannot change ownership as the current owner."
                )

        self.helper.layout = Layout(
            Row(
                Column("title", css_class="form-group col-12 mb-3"),
                css_class="row form-row",
            ),
            Row(
                Column(
                    Row(
                        Column("owner", css_class="form-group col-12 mb-3"),
                        Column("members", css_class="form-group col-12 mb-3"),
                        css_class="row form-ow",
                    ),
                    css_class="form-group col-4 mb-3",
                ),
                Column("description", css_class="form-group col-8 mb-3"),
                css_class="row form-row",
            ),
            Div(
                Submit("submit", "Save Settings", css_class="btn btn-dark"),
                css_class="text-end pt-3",
            ),
        )

    def clean(self):
        """
        Validate that:
        1. The current user is not changing ownership if they are the owner
        2. The current user is not removing themselves from members if they are a member
        """
        cleaned_data = super().clean()

        if not self.current_user or not hasattr(self.current_user, "profile"):
            return cleaned_data

        # Check if owner is being changed by the current owner
        if self.instance and self.instance.owner == self.current_user.profile:
            # Ensure owner hasn't been changed
            if (
                "owner" in cleaned_data
                and cleaned_data["owner"] != self.current_user.profile
            ):
                self.add_error(
                    "owner",
                    "As the current owner, you cannot transfer ownership to another user.",
                )

        # Check if the current user is removing themselves from members
        if self.instance and self.current_user.profile in self.instance.members.all():
            members_after = cleaned_data.get("members", [])
            if self.current_user.profile not in members_after:
                # Add the current user back to the members list
                members_list = list(members_after)
                members_list.append(self.current_user.profile)
                cleaned_data["members"] = members_list
                self.add_error(
                    "members", "You cannot remove yourself from the project members."
                )

        return cleaned_data

    def save(self, commit=True):
        """
        Override the save method to handle permission changes when adding or removing users.
        - When a user is added, they get 'viewer' permissions
        - When a user is removed, their permissions for this project are completely removed
        """
        project = super().save(commit)

        if self.instance and self.changed_data and "members" in self.changed_data:
            # Get previous and current members
            previous_members = set(self.instance.members.all())
            current_members = set(self.cleaned_data["members"])

            # Find added and removed members
            added_members = current_members - previous_members
            removed_members = previous_members - current_members

            # Handle added members - set viewer permissions
            for member in added_members:
                # Skip owners and superusers (they already have all permissions by default)
                if member == self.instance.owner or member.user.is_superuser:
                    continue

                # Set viewer permissions for new members
                from twf.permissions import get_role_permissions

                project_id_str = str(self.instance.id)

                # Initialize permissions dict for this project if it doesn't exist
                if project_id_str not in member.permissions:
                    member.permissions[project_id_str] = {}

                # Set viewer permissions (all entity types with 'view' level)
                for permission in get_role_permissions("viewer"):
                    member.permissions[project_id_str][permission] = True

                # Save the updated permissions
                member.save()

            # Handle removed members - completely remove all permissions for this project
            for member in removed_members:
                # Skip owners and superusers (they can't be removed)
                if member == self.instance.owner or member.user.is_superuser:
                    continue

                # Clear permissions for this project
                project_id_str = str(self.instance.id)
                if project_id_str in member.permissions:
                    # Remove the permissions dictionary for this project completely
                    member.permissions.pop(project_id_str, None)

                    # Save the updated permissions
                    member.save()

        return project


class CredentialsForm(forms.ModelForm):
    """Form for creating and updating credentials."""

    active_tab = forms.CharField(widget=forms.HiddenInput(), required=False)

    transkribus_username = forms.CharField(
        required=False, widget=TextInput(attrs={"placeholder": "Transkribus Username"})
    )
    transkribus_password = forms.CharField(
        required=False,
        widget=PasswordInputRetain(attrs={"placeholder": "Transkribus Password"}),
    )

    geonames_username = forms.CharField(
        required=False, widget=TextInput(attrs={"placeholder": "Geonames Username"})
    )

    zenodo_token = forms.CharField(
        required=False, widget=TextInput(attrs={"placeholder": "Zenodo Access Token"})
    )

    class Meta:
        model = Project
        fields = ["conf_credentials", "active_tab"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Populate the fields from `conf_credentials` JSON if data exists
        conf_credentials = self.instance.conf_credentials or {}

        self.fields["transkribus_username"].initial = conf_credentials.get(
            "transkribus", {}
        ).get("username", "")
        self.fields["transkribus_password"].initial = conf_credentials.get(
            "transkribus", {}
        ).get("password", "")

        self.fields["geonames_username"].initial = conf_credentials.get(
            "geonames", {}
        ).get("username", "")

        self.fields["zenodo_token"].initial = conf_credentials.get("zenodo", {}).get(
            "zenodo_token", ""
        )

        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_class = "form form-control"

        self.helper.layout = Layout(
            Fieldset(
                "Transkribus",
                Row(
                    Column("transkribus_username", css_class="col-6"),
                    Column("transkribus_password", css_class="col-6"),
                ),
            ),
            Fieldset(
                "GeoNames",
                Row(Column("geonames_username", css_class="col-12")),
            ),
            Fieldset(
                "Zenodo",
                Row(Column("zenodo_token", css_class="col-12")),
            ),
            Div(
                Submit("submit", "Save Settings", css_class="btn btn-dark"),
                css_class="text-end pt-3",
            ),
        )

    def clean(self):
        """Clean and save credential data back into the JSONField `conf_credentials`."""
        cleaned_data = super().clean()

        # Preserve existing AI provider credentials
        existing_credentials = self.instance.conf_credentials or {}

        self.instance.conf_credentials = {
            # Update non-AI credentials from form
            "transkribus": {
                "username": cleaned_data.get("transkribus_username"),
                "password": cleaned_data.get("transkribus_password"),
            },
            "geonames": {"username": cleaned_data.get("geonames_username")},
            "zenodo": {"zenodo_token": cleaned_data.get("zenodo_token")},
        }
        return cleaned_data


class TaskSettingsForm(forms.ModelForm):
    """Form for configuring date normalization settings.

    This form manages how dates are detected, parsed, and normalized throughout
    the project. It controls the input date format detection and the precision
    to which dates should be resolved.
    """

    active_tab = forms.CharField(widget=forms.HiddenInput(), required=False)

    # Date normalization settings
    date_input_format = forms.ChoiceField(
        required=False,
        choices=[
            ("", "Select Date Format"),
            ("auto", "Auto Detect"),
            ("DMY", "DMY"),
            ("YMD", "YMD"),
        ],
        widget=Select2Widget(attrs={"style": "width: 100%;"}),
    )
    resolve_to_date = forms.ChoiceField(
        required=False,
        label="Resolve to Precision",
        choices=[
            ("", "Select Resolve to Precision"),
            ("day", "Day"),
            ("month", "Month"),
            ("year", "Year"),
        ],
        widget=Select2Widget(attrs={"style": "width: 100%;"}),
    )

    class Meta:
        model = Project
        fields = ["conf_tasks"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_class = "form form-control"

        # Populate the fields from `conf_tasks` JSON if data exists
        conf_tasks = self.instance.conf_tasks or {}
        self.fields["date_input_format"].initial = conf_tasks.get(
            "date_normalization", {}
        ).get("date_input_format", "")
        self.fields["resolve_to_date"].initial = conf_tasks.get(
            "date_normalization", {}
        ).get("resolve_to_date", "")

        self.helper.layout = Layout(
            TabHolder(
                Tab(
                    "Date Normalization Settings",
                    Row(
                        Column("date_input_format", css_class="col-6"),
                        Column("resolve_to_date", css_class="col-6"),
                    ),
                    css_id="date_normalization",
                ),
            ),
            Div(
                Submit("submit", "Save Settings", css_class="btn btn-dark"),
                css_class="text-end pt-3",
            ),
            "active_tab",
        )

    def clean(self):
        cleaned_data = super().clean()

        # Preserve existing configurations
        existing_tag_types = (
            self.instance.conf_tasks.get("tag_types", {})
            if self.instance.conf_tasks
            else {}
        )
        existing_metadata_review = (
            self.instance.conf_tasks.get("metadata_review", {})
            if self.instance.conf_tasks
            else {}
        )
        existing_google_sheet = (
            self.instance.conf_tasks.get("google_sheet", {})
            if self.instance.conf_tasks
            else {}
        )

        self.instance.conf_tasks = {
            "google_sheet": existing_google_sheet,  # Preserve existing google_sheet config
            "metadata_review": existing_metadata_review,  # Preserve existing metadata_review config
            "date_normalization": {
                "date_input_format": cleaned_data.get("date_input_format"),
                "resolve_to_date": cleaned_data.get("resolve_to_date"),
            },
            "tag_types": existing_tag_types,  # Preserve existing tag_types config
        }

        return cleaned_data


class WorkflowSettingsForm(forms.ModelForm):
    """Form for configuring workflow definitions."""

    # Document Review Workflow
    doc_review_title = forms.CharField(
        required=False,
        label="Workflow Title",
        initial="Review Documents",
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    doc_review_description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
        label="Short Description",
        help_text="Brief description of what this workflow does",
    )
    doc_review_instructions = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 10, "class": "form-control"}),
        label="Detailed Instructions (Markdown)",
        help_text="Provide guidance for reviewers. Supports Markdown formatting.",
    )
    doc_review_batch_size = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=50,
        initial=5,
        label="Batch Size",
        help_text="Number of documents to review per workflow session",
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    doc_review_custom_fields = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 5, "class": "form-control font-monospace"}
        ),
        label="Custom Fields (JSON)",
        help_text="Define custom fields to collect data during review. Example: "
        '{"quality": {"type": "select", "label": "Quality", "choices": [["1", "Poor"], ["2", "Good"]]}}',
    )

    # Collection Review Workflow
    col_review_title = forms.CharField(
        required=False,
        label="Workflow Title",
        initial="Review Collection",
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    col_review_description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
        label="Short Description",
        help_text="Brief description of what this workflow does",
    )
    col_review_instructions = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 10, "class": "form-control"}),
        label="Detailed Instructions (Markdown)",
        help_text="Provide guidance for reviewers. Supports Markdown formatting.",
    )
    col_review_batch_size = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=50,
        initial=5,
        label="Batch Size",
        help_text="Number of collection items to review per workflow session",
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    col_review_custom_fields = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 5, "class": "form-control font-monospace"}
        ),
        label="Custom Fields (JSON)",
        help_text="Define custom fields to collect data during review. Example: "
        '{"notes": {"type": "textarea", "label": "Review Notes"}}',
    )

    # Tag Grouping Workflow
    tag_grouping_title = forms.CharField(
        required=False,
        label="Workflow Title",
        initial="Group Tags",
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    tag_grouping_description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
        label="Short Description",
        help_text="Brief description of what this workflow does",
    )
    tag_grouping_instructions = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 10, "class": "form-control"}),
        label="Detailed Instructions (Markdown)",
        help_text="Instructions for grouping tags into dictionary entries. Supports Markdown formatting.",
    )
    tag_grouping_batch_size = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        initial=10,
        label="Batch Size",
        help_text="Number of unique tag variations to group per workflow session",
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )

    # Date Normalization Workflow
    date_norm_title = forms.CharField(
        required=False,
        label="Workflow Title",
        initial="Normalize Dates",
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    date_norm_description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
        label="Short Description",
        help_text="Brief description of what this workflow does",
    )
    date_norm_instructions = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 10, "class": "form-control"}),
        label="Detailed Instructions (Markdown)",
        help_text="Instructions for normalizing date tags to EDTF format. Supports Markdown formatting.",
    )
    date_norm_batch_size = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        initial=20,
        label="Batch Size",
        help_text="Number of date tags to normalize per workflow session",
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )

    class Meta:
        model = Project
        fields = ["conf_tasks"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Pre-populate form with existing workflow definitions
        if self.instance and self.instance.conf_tasks:
            workflow_defs = self.instance.conf_tasks.get("workflow_definitions", {})

            # Document review
            doc_def = workflow_defs.get("review_documents", {})
            if doc_def:
                self.initial["doc_review_title"] = doc_def.get(
                    "title", "Review Documents"
                )
                self.initial["doc_review_description"] = doc_def.get("description", "")
                self.initial["doc_review_instructions"] = doc_def.get(
                    "instructions", ""
                )
                self.initial["doc_review_batch_size"] = doc_def.get("batch_size", 5)
                doc_fields = doc_def.get("fields", {})
                if doc_fields:
                    self.initial["doc_review_custom_fields"] = json.dumps(
                        doc_fields, indent=2
                    )

            # Collection review
            col_def = workflow_defs.get("review_collection", {})
            if col_def:
                self.initial["col_review_title"] = col_def.get(
                    "title", "Review Collection"
                )
                self.initial["col_review_description"] = col_def.get("description", "")
                self.initial["col_review_instructions"] = col_def.get(
                    "instructions", ""
                )
                self.initial["col_review_batch_size"] = col_def.get("batch_size", 5)
                col_fields = col_def.get("fields", {})
                if col_fields:
                    self.initial["col_review_custom_fields"] = json.dumps(
                        col_fields, indent=2
                    )

            # Tag grouping
            tag_grouping_def = workflow_defs.get("review_tags_grouping", {})
            if tag_grouping_def:
                self.initial["tag_grouping_title"] = tag_grouping_def.get(
                    "title", "Group Tags"
                )
                self.initial["tag_grouping_description"] = tag_grouping_def.get(
                    "description", ""
                )
                self.initial["tag_grouping_instructions"] = tag_grouping_def.get(
                    "instructions", ""
                )
                self.initial["tag_grouping_batch_size"] = tag_grouping_def.get(
                    "batch_size", 10
                )

            # Date normalization
            date_norm_def = workflow_defs.get("review_tags_dates", {})
            if date_norm_def:
                self.initial["date_norm_title"] = date_norm_def.get(
                    "title", "Normalize Dates"
                )
                self.initial["date_norm_description"] = date_norm_def.get(
                    "description", ""
                )
                self.initial["date_norm_instructions"] = date_norm_def.get(
                    "instructions", ""
                )
                self.initial["date_norm_batch_size"] = date_norm_def.get(
                    "batch_size", 20
                )

    def clean_doc_review_custom_fields(self):
        """Validate document review custom fields JSON."""
        raw_value = self.cleaned_data.get("doc_review_custom_fields")
        if raw_value and raw_value.strip():
            try:
                return json.loads(raw_value)
            except json.JSONDecodeError as e:
                raise forms.ValidationError(f"Must be valid JSON: {str(e)}")
        return {}

    def clean_col_review_custom_fields(self):
        """Validate collection review custom fields JSON."""
        raw_value = self.cleaned_data.get("col_review_custom_fields")
        if raw_value and raw_value.strip():
            try:
                return json.loads(raw_value)
            except json.JSONDecodeError as e:
                raise forms.ValidationError(f"Must be valid JSON: {str(e)}")
        return {}

    def save(self, commit=True):
        """Save workflow definitions to conf_tasks."""
        # Get existing conf_tasks
        existing_conf_tasks = self.instance.conf_tasks or {}

        # Build workflow_definitions structure
        workflow_definitions = {}

        # Document review
        doc_fields = self.cleaned_data.get("doc_review_custom_fields", {})
        workflow_definitions["review_documents"] = {
            "title": self.cleaned_data.get("doc_review_title", "Review Documents"),
            "description": self.cleaned_data.get("doc_review_description", ""),
            "instructions": self.cleaned_data.get("doc_review_instructions", ""),
            "instruction_format": "markdown",
            "fields": doc_fields,
            "batch_size": self.cleaned_data.get("doc_review_batch_size", 5),
        }

        # Collection review
        col_fields = self.cleaned_data.get("col_review_custom_fields", {})
        workflow_definitions["review_collection"] = {
            "title": self.cleaned_data.get("col_review_title", "Review Collection"),
            "description": self.cleaned_data.get("col_review_description", ""),
            "instructions": self.cleaned_data.get("col_review_instructions", ""),
            "instruction_format": "markdown",
            "fields": col_fields,
            "batch_size": self.cleaned_data.get("col_review_batch_size", 5),
        }

        # Tag grouping
        workflow_definitions["review_tags_grouping"] = {
            "title": self.cleaned_data.get("tag_grouping_title", "Group Tags"),
            "description": self.cleaned_data.get("tag_grouping_description", ""),
            "instructions": self.cleaned_data.get("tag_grouping_instructions", ""),
            "instruction_format": "markdown",
            "fields": {},
            "batch_size": self.cleaned_data.get("tag_grouping_batch_size", 10),
        }

        # Date normalization
        workflow_definitions["review_tags_dates"] = {
            "title": self.cleaned_data.get("date_norm_title", "Normalize Dates"),
            "description": self.cleaned_data.get("date_norm_description", ""),
            "instructions": self.cleaned_data.get("date_norm_instructions", ""),
            "instruction_format": "markdown",
            "fields": {},
            "batch_size": self.cleaned_data.get("date_norm_batch_size", 20),
        }

        # Merge with existing conf_tasks
        existing_conf_tasks["workflow_definitions"] = workflow_definitions
        self.instance.conf_tasks = existing_conf_tasks

        if commit:
            self.instance.save()
        return self.instance


class RepositorySettingsForm(forms.ModelForm):
    """Form for updating repository settings."""

    license = forms.ChoiceField(
        choices=zenodo_client.LICENSE_CHOICES,
        widget=Select2Widget(attrs={"style": "width: 100%;"}),
        required=True,
    )

    keywords = forms.JSONField(
        widget=Select2TagWidget(
            attrs={
                "style": "width: 100%;",
                "data-token-separators": json.dumps(
                    [","]
                ),  # Only use comma as separator
            }
        ),
        required=False,
    )

    workflow_description_preview = forms.CharField(
        required=False,
    )

    class Meta:
        model = Project
        fields = ["keywords", "license", "version", "workflow_description"]
        widgets = {
            "version": TextInput(attrs={"placeholder": "Version"}),
            "workflow_description": forms.Textarea(
                attrs={"rows": 20, "id": "workflow_description"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_class = "form form-control"

        if self.instance and self.instance.keywords:
            if isinstance(self.instance.keywords, str):
                try:
                    self.initial["keywords"] = json.loads(
                        self.instance.keywords
                    )  # Ensure it's a list
                except json.JSONDecodeError:
                    self.initial["keywords"] = []
            else:
                self.initial["keywords"] = self.instance.keywords  # Expecting a list

            # Add the value as a data attribute
            self.fields["keywords"].widget.attrs["data-value"] = json.dumps(
                self.initial["keywords"]
            )

        self.helper.layout = Layout(
            Row(
                Column("version", css_class="form-group col-6 mb-3"),
                Column("license", css_class="form-group col-6 mb-3"),
                css_class="row form-row",
            ),
            Row(
                Column("keywords", css_class="form-group col-12 mb-3"),
                css_class="row form-row",
            ),
            Row(
                Column(
                    HTML(
                        '<button type="button" class="btn btn-secondary mt-2" '
                        'id="generate_md">Generate Default</button>'
                    ),
                    css_class="form-group col-12 mb-3",
                ),
                css_class="row form-row",
            ),
            Row(
                Column("workflow_description", css_class="form-group col-6 mb-3"),
                Column(
                    "workflow_description_preview", css_class="form-group col-6 mb-3"
                ),
                css_class="row form-row",
            ),
            Div(
                Submit("submit", "Save Settings", css_class="btn btn-dark"),
                css_class="text-end pt-3",
            ),
        )

    def clean(self):
        cleaned_data = super().clean()
        if "workflow_description" in cleaned_data:
            cleaned_data["workflow_description_preview"] = mark_safe(
                markdown(cleaned_data["workflow_description"])
            )

        if "keywords" in cleaned_data:
            if isinstance(cleaned_data["keywords"], str):
                try:
                    cleaned_data["keywords"] = json.loads(
                        cleaned_data["keywords"]
                    )  # Convert to list
                except json.JSONDecodeError:
                    cleaned_data["keywords"] = (
                        []
                    )  # Default to an empty list if parsing fails
            elif not cleaned_data["keywords"]:
                cleaned_data["keywords"] = (
                    []
                )  # Ensure it's an empty list instead of None

        return cleaned_data


class NoteForm(forms.ModelForm):
    """Form for creating and updating prompts."""

    class Meta:
        model = Note
        fields = ["title", "note"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_class = "form form-control"
        self.helper.layout = Layout(
            Row(
                Column("title", css_class="form-group col-12 mb-3"),
                css_class="row form-row",
            ),
            Row(
                Column("note", css_class="form-group col-12 mb-3"),
                css_class="row form-row",
            ),
            Div(
                Submit("submit", "Save Note", css_class="btn btn-dark"),
                css_class="text-end pt-3",
            ),
        )


class UserPermissionForm(forms.Form):
    """
    Form for managing user permissions within a project.

    This form allows setting a user's role (viewer, editor, manager) and optionally
    overriding specific permissions. It also provides a field for setting a function
    description for the user in the project.
    """

    # Hidden field for user_id to identify which user we're editing
    user_id = forms.IntegerField(widget=forms.HiddenInput())

    # We use a hidden field for the role, will be set by the button clicks
    role = forms.CharField(
        required=False,  # Make it not required so special users don't need it
        widget=forms.HiddenInput(),
        initial="viewer",  # Default to viewer if no role is specified
    )

    # Function description for the user in this project
    function = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": 'E.g., "Lead Researcher", "Content Editor"',
            }
        ),
        help_text="Optional functional description for this user in the project",
    )

    # We'll dynamically add permission override fields in __init__

    def __init__(self, *args, **kwargs):
        """
        Initialize the form with dynamic permission fields.

        Args:
            user_profile: The UserProfile object we're editing permissions for
            project: The Project object these permissions apply to
        """
        # Extract user_profile and project from kwargs
        self.user_profile = kwargs.pop("user_profile", None)
        self.project = kwargs.pop("project", None)

        super().__init__(*args, **kwargs)

        # Set up form helper for crispy-forms
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_class = "form"

        # Check if user is the project owner or a superuser
        is_special_user = False
        if self.user_profile and self.project:
            is_special_user = (
                self.project.owner == self.user_profile
            ) or self.user_profile.user.is_superuser

        # For project owners and superusers, only show the function field
        if is_special_user:
            # Set initial function value
            if self.user_profile:
                self.fields["function"].initial = (
                    self.user_profile.get_project_function(self.project)
                )

            # Remove the role field completely for special users
            if "role" in self.fields:
                self.fields.pop("role")

            # Create a simpler layout for owners and superusers
            self.helper.layout = Layout(
                "user_id",  # Include hidden user_id field
                Div(
                    HTML(
                        '<div class="alert alert-info mb-4">'
                        '<i class="fa fa-info-circle me-2"></i>'
                        "This user has full access to the project as an owner or administrator."
                        "</div>"
                    ),
                    css_class="mb-3",
                ),
                Row(Column("function", css_class="col-md-12"), css_class="mb-3"),
                Div(
                    Submit(
                        "submit",
                        "Save Function Description",
                        css_class="btn btn-primary",
                    ),
                    css_class="text-end mt-3",
                ),
            )

            return  # Exit early - we don't need to add permission fields

        # For regular members, add permission override fields dynamically
        for entity_type, permissions in ENTITY_TYPES.items():
            for perm_name, perm_data in permissions.items():
                field_name = f"permission_{entity_type}_{perm_name}"
                self.fields[field_name] = forms.BooleanField(
                    label=perm_data["label"],
                    help_text=perm_data["description"],
                    required=False,
                )

        # Set initial values if user_profile and project are provided
        if self.user_profile and self.project:
            # Set user_id
            self.fields["user_id"].initial = self.user_profile.id

            # Set initial role
            role, _ = self.user_profile.get_role_and_overrides(self.project)
            self.fields["role"].initial = role

            # Set initial function
            self.fields["function"].initial = self.user_profile.get_project_function(
                self.project
            )

            # Set initial permission values
            for entity_type, permissions in ENTITY_TYPES.items():
                for perm_name in permissions:
                    permission = f"{entity_type}.{perm_name}"
                    field_name = f"permission_{entity_type}_{perm_name}"
                    # Check if this permission exists directly in the user's permissions
                    # without using the hierarchical permission logic
                    project_permissions = self.user_profile.get_project_permissions(
                        self.project
                    )
                    self.fields[field_name].initial = permission in project_permissions

        # Create form layout with crispy-forms for regular members
        permission_rows = []
        for entity_type, permissions in ENTITY_TYPES.items():
            # Create a card for each entity type
            permission_fields = []
            for perm_name in permissions:
                permission_fields.append(
                    Field(
                        f"permission_{entity_type}_{perm_name}",
                    )
                )

            # Add the entity type card to the layout
            permission_rows.append(
                Column(
                    Div(
                        HTML(f"<h6>{entity_type.title()}</h6>"),
                        *permission_fields,
                        css_class="card-body",
                    ),
                    css_class="col-md-6 mb-3",
                )
            )

        # Function field
        function_row = Row(Column("function", css_class="col-md-12"), css_class="mb-3")

        # Role selection radio buttons
        role_buttons = Div(
            HTML("<h6>Role Assignment:</h6>"),
            Div(
                HTML(
                    """
                <div class="btn-group role-btn-group mb-3" role="group" aria-label="User Role">
                    <input type="radio" class="btn-check" name="role_btn" id="role_none" 
                    autocomplete="off" data-role="none">
                    <label class="btn btn-outline-secondary" for="role_none">None</label>

                    <input type="radio" class="btn-check" name="role_btn" id="role_viewer" 
                    autocomplete="off" data-role="viewer">
                    <label class="btn btn-outline-info" for="role_viewer">Viewer</label>

                    <input type="radio" class="btn-check" name="role_btn" id="role_editor" 
                    autocomplete="off" data-role="editor">
                    <label class="btn btn-outline-warning" for="role_editor">Editor</label>

                    <input type="radio" class="btn-check" name="role_btn" id="role_manager" 
                    autocomplete="off" data-role="manager">
                    <label class="btn btn-outline-danger" for="role_manager">Manager</label>
                </div>
                """
                ),
                css_class="mb-3",
            ),
            "role",
            css_class="mb-3",
        )

        # Build the complete layout for regular members
        self.helper.layout = Layout(
            "user_id",  # Include hidden user_id field
            function_row,
            role_buttons,
            HTML('<h5 class="mt-4 mb-3">Permissions</h5>'),
            Row(*permission_rows),
            Div(
                Submit("submit", "Save Permissions", css_class="btn btn-primary"),
                css_class="text-end mt-3",
            ),
        )

    def _determine_role(self, permissions):
        """
        Determine the user's role based on their current permissions.

        Args:
            permissions: The user's current permissions for the project

        Returns:
            str: The determined role ('none', 'viewer', 'editor', or 'manager')
        """
        # If there are no permissions, or only a function description, return 'none'
        perm_keys = [k for k in permissions.keys() if k != "function"]
        if not perm_keys:
            return "none"

        # Check for Manager permissions
        manager_perms = [f"{entity}.manage" for entity in ENTITY_TYPES.keys()]
        if any(perm in permissions for perm in manager_perms):
            return "manager"

        # Check for Editor permissions
        editor_perms = [f"{entity}.edit" for entity in ENTITY_TYPES.keys()]
        if any(perm in permissions for perm in editor_perms):
            return "editor"

        # If there are any permissions, but no editor or manager permissions, it's a viewer
        return "viewer"

    def save(self):
        """
        Save the form data to the user profile.

        This method applies the selected role and any permission overrides
        to the user's permissions for the specific project.
        """
        if not self.user_profile or not self.project:
            return

        # Check if this is a special user (owner or superuser)
        is_special_user = (
            self.project.owner == self.user_profile
        ) or self.user_profile.user.is_superuser

        # Get function (always present)
        function = self.cleaned_data.get("function")

        # For special users, we only update the function description
        if is_special_user:
            # Set function description if provided
            self.user_profile.set_project_function(self.project, function)
            return

        # For regular users, process role and permissions
        role = self.cleaned_data.get("role", None)  # Default to None if not present

        # For the 'none' role, we clear all permissions
        if role == "none":
            # Clear all permissions but preserve the function description
            if str(self.project.id) in self.user_profile.permissions:
                # Keep only the function description if it exists
                project_permissions = {}
                if function:
                    project_permissions["function"] = function
                self.user_profile.permissions[str(self.project.id)] = (
                    project_permissions
                )
                self.user_profile.save()
        else:
            # For any other role, we need to clean up existing permissions first
            # and then set the new role permissions
            # The set_role_permissions method now handles this properly
            self.user_profile.set_role_permissions(self.project, role)

        # Set function description if provided
        self.user_profile.set_project_function(self.project, function)

        # First, group permissions by entity type to find the highest level for each
        entity_permissions = {}

        # Collect all permission states from form
        for field_name, value in self.cleaned_data.items():
            if field_name.startswith("permission_"):
                # Extract entity_type and perm_name from field name
                _, entity_type, perm_name = field_name.split("_", 2)

                # Initialize the entity type if not present
                if entity_type not in entity_permissions:
                    entity_permissions[entity_type] = {
                        "view": False,
                        "edit": False,
                        "manage": False,
                    }

                # Set the permission state based on checkbox
                entity_permissions[entity_type][perm_name] = value

        # Now apply the permissions by entity type, only setting the highest level
        project_id_str = str(self.project.id)
        if project_id_str not in self.user_profile.permissions:
            self.user_profile.permissions[project_id_str] = {}

        # Preserve function if it exists
        if function:
            self.user_profile.permissions[project_id_str]["function"] = function

        # Process each entity type separately
        for entity_type, perms in entity_permissions.items():
            # Remove any existing permissions for this entity type
            for level in ["view", "edit", "manage"]:
                permission = f"{entity_type}.{level}"
                if permission in self.user_profile.permissions[project_id_str]:
                    self.user_profile.permissions[project_id_str].pop(permission)

            # Add only the highest level permission that is checked
            if perms["manage"]:
                self.user_profile.permissions[project_id_str][
                    f"{entity_type}.manage"
                ] = True
            elif perms["edit"]:
                self.user_profile.permissions[project_id_str][
                    f"{entity_type}.edit"
                ] = True
            elif perms["view"]:
                self.user_profile.permissions[project_id_str][
                    f"{entity_type}.view"
                ] = True

        # Save the updated permissions
        self.user_profile.save()
