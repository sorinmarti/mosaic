"""Forms for metadata settings configuration."""

import json
import logging

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Div, HTML, Row, Column
from django import forms
from django.utils.safestring import mark_safe

logger = logging.getLogger(__name__)


class MetadataSettingsForm(forms.Form):
    """Form for configuring metadata review settings."""

    page_metadata_review = forms.CharField(
        label="Page Metadata Review Configuration",
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 10, "class": "form-control font-monospace"}
        ),
        help_text=mark_safe(
            "Configure fields for page metadata review workflow.<br/>"
            'JSON format: <code>{"field.path": {"label": "Display Name", "type": "text"}}</code><br/>'
            "Example:<br/>"
            "<code>{</code><br/>"
            '<code>&nbsp;&nbsp;"json_import.author": {"label": "Author", "type": "text"},</code><br/>'
            '<code>&nbsp;&nbsp;"json_import.date": {"label": "Date", "type": "date"}</code><br/>'
            "<code>}</code>"
        ),
    )

    document_metadata_review = forms.CharField(
        label="Document Metadata Review Configuration",
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 10, "class": "form-control font-monospace"}
        ),
        help_text=mark_safe(
            "Configure fields for document metadata review workflow.<br/>"
            'JSON format: <code>{"field.path": {"label": "Display Name", "type": "text"}}</code><br/>'
            "Example:<br/>"
            "<code>{</code><br/>"
            '<code>&nbsp;&nbsp;"json_import.title": {"label": "Title", "type": "text"},</code><br/>'
            '<code>&nbsp;&nbsp;"json_import.year": {"label": "Year", "type": "number"}</code><br/>'
            "<code>}</code>"
        ),
    )

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)

        if not project:
            raise ValueError("Project is required for MetadataSettingsForm")

        self.project = project

        # Load existing configuration
        conf_tasks = project.conf_tasks or {}
        metadata_config = conf_tasks.get("metadata_review", {})

        # Get page and document configurations
        page_config = metadata_config.get("page_metadata_review", "")
        doc_config = metadata_config.get("document_metadata_review", "")

        # Handle different data types - convert dicts to formatted JSON strings
        if isinstance(page_config, dict):
            page_config = json.dumps(page_config, indent=2)
        self.fields["page_metadata_review"].initial = page_config

        if isinstance(doc_config, dict):
            doc_config = json.dumps(doc_config, indent=2)
        self.fields["document_metadata_review"].initial = doc_config

        # Setup crispy forms helper
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_class = "metadata-settings-form"
        self.helper.layout = Layout(
            Div(
                HTML('<h4 class="mb-3">Metadata Review Configuration</h4>'),
                HTML(
                    '<p class="text-muted">Configure fields for the metadata review workflows.</p>'
                ),
                Row(
                    Column("page_metadata_review", css_class="col-12 mb-3"),
                ),
                Row(
                    Column("document_metadata_review", css_class="col-12 mb-3"),
                ),
                Div(
                    Submit("submit", "Save Settings", css_class="btn btn-dark mt-3"),
                    css_class="mt-3",
                ),
                css_class="metadata-settings-container",
            )
        )

    def clean_page_metadata_review(self):
        """Validate page metadata review configuration."""
        value = self.cleaned_data.get("page_metadata_review", "")
        if value and value.strip():
            try:
                json.loads(value)
            except json.JSONDecodeError as e:
                raise forms.ValidationError(f"Invalid JSON: {e}")
        return value

    def clean_document_metadata_review(self):
        """Validate document metadata review configuration."""
        value = self.cleaned_data.get("document_metadata_review", "")
        if value and value.strip():
            try:
                json.loads(value)
            except json.JSONDecodeError as e:
                raise forms.ValidationError(f"Invalid JSON: {e}")
        return value

    def save(self):
        """Save the form data to the project configuration."""
        if not self.is_valid():
            return False

        # Update project configuration
        if not self.project.conf_tasks:
            self.project.conf_tasks = {}

        if "metadata_review" not in self.project.conf_tasks:
            self.project.conf_tasks["metadata_review"] = {}

        # Store configurations
        self.project.conf_tasks["metadata_review"]["page_metadata_review"] = (
            self.cleaned_data.get("page_metadata_review", "")
        )
        self.project.conf_tasks["metadata_review"]["document_metadata_review"] = (
            self.cleaned_data.get("document_metadata_review", "")
        )

        self.project.save()
        logger.info(f"Metadata settings saved for project {self.project.id}")

        return True
