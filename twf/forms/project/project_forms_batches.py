"""
Project batch processing forms.

This module contains forms for project-level batch processing operations,
including document extraction, project copying, and AI queries with multimodal support.
"""

from crispy_forms.layout import Row, Column, Fieldset
from django import forms
from django.forms import TextInput
from django_select2.forms import Select2MultipleWidget

from twf.forms.base_batch_forms import BaseBatchForm, BaseMultiModalAIBatchForm
from twf.forms.project.project_forms import PasswordInputRetain
from twf.models import Document


class TranskribusEnrichmentBatchForm(BaseBatchForm):
    """
    Form for enriching documents with Transkribus API metadata.

    This form provides the interface for fetching additional document and page metadata
    (labels, tags, excluded status) from the Transkribus API that is not available in
    the PageXML export.
    """

    transkribus_username = forms.CharField(
        required=False,
        label="Transkribus Username",
        widget=TextInput(attrs={"placeholder": "Transkribus Username"}),
        help_text="Your Transkribus account username",
    )
    transkribus_password = forms.CharField(
        required=False,
        label="Transkribus Password",
        widget=PasswordInputRetain(attrs={"placeholder": "Transkribus Password"}),
        help_text="Your Transkribus account password",
    )

    force = forms.BooleanField(
        label="Force Re-Enrichment",
        required=False,
        initial=False,
        help_text="If checked, re-fetch API metadata even for documents that already have it. "
        "Leave unchecked to only enrich documents without existing API metadata.",
    )

    def __init__(self, *args, **kwargs):
        """
        Initialize the enrichment form.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        super().__init__(*args, **kwargs)

        # Populate Transkribus credentials from project if available
        if self.project:
            transkribus_creds = self.project.get_credentials("transkribus")
            if transkribus_creds:
                self.fields["transkribus_username"].initial = transkribus_creds.get("username", "")
                self.fields["transkribus_password"].initial = transkribus_creds.get("password", "")

    def get_button_label(self):
        """
        Get the label for the submit button.

        Returns:
            str: The button label.
        """
        return "Enrich with API Metadata"

    def get_dynamic_fields(self):
        """
        Get the dynamic fields for the form.

        Returns:
            list: A list of form field layouts.
        """
        return [
            Fieldset(
                "Transkribus Credentials",
                Row(
                    Column("transkribus_username", css_class="form-group col-6 mb-3"),
                    Column("transkribus_password", css_class="form-group col-6 mb-3"),
                    css_class="row form-row",
                ),
            ),
            Row(
                Column("force", css_class="form-group col-12 mb-3"),
                css_class="row form-row",
            )
        ]

    def save_credentials(self):
        """Save Transkribus credentials to the project."""
        if self.project and self.is_valid():
            username = self.cleaned_data.get("transkribus_username")
            password = self.cleaned_data.get("transkribus_password")

            # Get existing credentials
            credentials = self.project.conf_credentials or {}

            # Update Transkribus credentials
            credentials["transkribus"] = {
                "username": username,
                "password": password,
            }

            # Save back to project
            self.project.conf_credentials = credentials
            self.project.save()


class DocumentExtractionBatchForm(BaseBatchForm):
    """
    Form for extracting documents from a Transkribus export with smart sync.

    This form provides the interface for the unified synchronization of documents,
    pages, and tags from Transkribus exports. It includes options to control the
    sync behavior.
    """

    transkribus_username = forms.CharField(
        required=False,
        label="Transkribus Username",
        widget=TextInput(attrs={"placeholder": "Transkribus Username"}),
        help_text="Your Transkribus account username",
    )
    transkribus_password = forms.CharField(
        required=False,
        label="Transkribus Password",
        widget=PasswordInputRetain(attrs={"placeholder": "Transkribus Password"}),
        help_text="Your Transkribus account password",
    )

    force_recreate_tags = forms.BooleanField(
        label="Force Recreate All Tags",
        required=False,
        initial=False,
        help_text="If checked, all tags will be deleted and recreated from scratch. "
        "This will lose all dictionary assignments and parked statuses. "
        "Leave unchecked to use smart sync that preserves user work.",
    )

    delete_removed_documents = forms.BooleanField(
        label="Delete Documents Not in Export",
        required=False,
        initial=True,
        help_text="If checked, documents that exist in the database but are not found "
        "in the Transkribus export will be deleted. Uncheck to keep all existing documents.",
    )

    def __init__(self, *args, **kwargs):
        """
        Initialize the document extraction form.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        super().__init__(*args, **kwargs)

        # Populate Transkribus credentials from project if available
        if self.project:
            transkribus_creds = self.project.get_credentials("transkribus")
            if transkribus_creds:
                self.fields["transkribus_username"].initial = transkribus_creds.get("username", "")
                self.fields["transkribus_password"].initial = transkribus_creds.get("password", "")

    def get_button_label(self):
        """
        Get the label for the submit button.

        Returns:
            str: The button label.
        """
        return "Synchronize Transkribus Export"

    def get_dynamic_fields(self):
        """
        Get the dynamic fields for the form.

        Returns:
            list: A list of form field layouts.
        """
        return [
            Fieldset(
                "Transkribus Credentials",
                Row(
                    Column("transkribus_username", css_class="form-group col-6 mb-3"),
                    Column("transkribus_password", css_class="form-group col-6 mb-3"),
                    css_class="row form-row",
                ),
            ),
            Row(
                Column("force_recreate_tags", css_class="form-group col-12 mb-3"),
                css_class="row form-row",
            ),
            Row(
                Column("delete_removed_documents", css_class="form-group col-12 mb-3"),
                css_class="row form-row",
            ),
        ]

    def save_credentials(self):
        """Save Transkribus credentials to the project."""
        if self.project and self.is_valid():
            username = self.cleaned_data.get("transkribus_username")
            password = self.cleaned_data.get("transkribus_password")

            # Get existing credentials
            credentials = self.project.conf_credentials or {}

            # Update Transkribus credentials
            credentials["transkribus"] = {
                "username": username,
                "password": password,
            }

            # Save back to project
            self.project.conf_credentials = credentials
            self.project.save()


class ProjectCopyBatchForm(BaseBatchForm):
    """
    Form for copying a project.

    This form provides the interface for creating a copy of an existing project.
    """

    new_project_name = forms.CharField(
        label="New Project Name",
        required=True,
        help_text="Please enter a name for the new project. Must be unique.",
        widget=forms.TextInput(attrs={"style": "width: 100%;"}),
    )

    def __init__(self, *args, **kwargs):
        """
        Initialize the project copy form.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        super().__init__(*args, **kwargs)
        # Set the initial value for the new project name
        self.fields["new_project_name"].initial = f"{self.project.title} (Copy)"

    def get_button_label(self):
        """
        Get the label for the submit button.

        Returns:
            str: The button label.
        """
        return "Copy Project"

    def get_dynamic_fields(self):
        """
        Get the dynamic fields for the form.

        Returns:
            list: A list of form field layouts.
        """
        return [
            Row(
                Column("new_project_name", css_class="form-group col-12 mb-3"),
                css_class="row form-row",
            )
        ]


class ProjectAIBaseForm(BaseMultiModalAIBatchForm):
    """
    Base form for querying AI models with project documents and optional images.

    This form extends the multimodal AI batch form with project-specific functionality
    for selecting documents to include in AI queries.
    """

    documents = forms.ModelMultipleChoiceField(
        label="Documents",
        required=True,
        help_text="Please select the documents to query.",
        widget=Select2MultipleWidget(attrs={"style": "width: 100%;"}),
        queryset=Document.objects.none(),
    )

    def __init__(self, *args, **kwargs):
        """
        Initialize the project AI base form.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
                multimodal_support (bool): Whether this form should include multimodal fields.
                                          Defaults to False. Provider-specific forms will override.
        """
        # Default to False - provider-specific forms will override as needed
        kwargs.setdefault("multimodal_support", False)
        super().__init__(*args, **kwargs)
        self.fields["documents"].queryset = Document.objects.filter(
            project=self.project
        )

    def get_dynamic_fields(self):
        """
        Get the dynamic fields for the form.

        Returns:
            list: A list of form field layouts including document selection.
        """
        return super().get_dynamic_fields() + [
            Row(
                Column("documents", css_class="form-group col-12 mb-3"),
                css_class="row form-row",
            ),
        ]

    def get_cancel_button_label(self):
        """
        Get the label for the cancel button.

        Returns:
            str: The cancel button label.
        """
        return "Cancel"


class UnifiedAIQueryForm(ProjectAIBaseForm):
    """
    Unified form for querying AI with configurations.

    Uses AIConfiguration objects which contain all settings
    (provider, model, prompt, role, etc.). The form only selects
    which configuration to use and query-specific options.
    """

    def get_button_label(self):
        """
        Get the label for the submit button.

        Returns:
            str: The button label.
        """
        return "Ask AI"
