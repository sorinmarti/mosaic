"""Forms for metadata review settings configuration."""

import json
import logging

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Div, HTML
from django import forms
from django.utils.safestring import mark_safe

from twf.models import Document, Page

logger = logging.getLogger(__name__)


def _collect_flat_keys(d, prefix, result, depth=0, max_depth=4):
    """
    Recursively collect dotted metadata keys from a nested dict.

    Leaf nodes (non-dict values, or dicts at max_depth) are added as keys.
    """
    if depth >= max_depth:
        return
    for key, value in d.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict) and value:
            _collect_flat_keys(value, full_key, result, depth + 1, max_depth)
        else:
            result.add(full_key)


def _get_project_flat_metadata_keys(queryset):
    """
    Return sorted list of flat (dotted-path) metadata keys found in queryset objects.

    For example, metadata {"geonames": {"id": "1", "name": "Rome"}} yields
    ["geonames.id", "geonames.name"].
    """
    keys = set()
    for metadata in queryset.values_list("metadata", flat=True):
        if isinstance(metadata, dict):
            _collect_flat_keys(metadata, "", keys)
    return sorted(keys)


class MetadataReviewSettingsForm(forms.Form):
    """Form for configuring metadata review settings using a table interface."""

    FIELD_TYPE_CHOICES = [
        ("text", "Text (single line)"),
        ("textarea", "Textarea (multi-line)"),
        ("number", "Number"),
        ("date", "Date"),
        ("select", "Select (dropdown)"),
    ]

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)

        if not project:
            raise ValueError("Project is required for MetadataReviewSettingsForm")

        self.project = project

        # Collect flat metadata keys scoped to this project
        self.doc_flat_keys = _get_project_flat_metadata_keys(
            Document.objects.filter(project=project)
        )
        self.page_flat_keys = _get_project_flat_metadata_keys(
            Page.objects.filter(document__project=project)
        )

        # Load existing configuration
        conf_tasks = project.conf_tasks or {}
        metadata_config = conf_tasks.get("metadata_review", {})

        doc_field_config = {}
        page_field_config = {}

        if "document_field_config" in metadata_config:
            try:
                doc_field_config = json.loads(metadata_config["document_field_config"])
            except (json.JSONDecodeError, TypeError):
                pass

        if "page_field_config" in metadata_config:
            try:
                page_field_config = json.loads(metadata_config["page_field_config"])
            except (json.JSONDecodeError, TypeError):
                pass

        # Create form fields for each document metadata key (index-based to avoid collisions)
        for i, metadata_key in enumerate(self.doc_flat_keys):
            existing = doc_field_config.get(metadata_key, {})
            prefix = f"doc_{i}"

            self.fields[f"{prefix}_include"] = forms.BooleanField(
                label="",
                required=False,
                initial=existing.get("include", False),
                widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
            )
            self.fields[f"{prefix}_label"] = forms.CharField(
                label="",
                required=False,
                initial=existing.get("label", ""),
                widget=forms.TextInput(attrs={
                    "class": "form-control form-control-sm",
                    "placeholder": "Display label",
                }),
            )
            self.fields[f"{prefix}_type"] = forms.ChoiceField(
                label="",
                choices=self.FIELD_TYPE_CHOICES,
                initial=existing.get("type", "text"),
                widget=forms.Select(attrs={"class": "form-control form-control-sm"}),
            )

        # Create form fields for each page metadata key
        for i, metadata_key in enumerate(self.page_flat_keys):
            existing = page_field_config.get(metadata_key, {})
            prefix = f"page_{i}"

            self.fields[f"{prefix}_include"] = forms.BooleanField(
                label="",
                required=False,
                initial=existing.get("include", False),
                widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
            )
            self.fields[f"{prefix}_label"] = forms.CharField(
                label="",
                required=False,
                initial=existing.get("label", ""),
                widget=forms.TextInput(attrs={
                    "class": "form-control form-control-sm",
                    "placeholder": "Display label",
                }),
            )
            self.fields[f"{prefix}_type"] = forms.ChoiceField(
                label="",
                choices=self.FIELD_TYPE_CHOICES,
                initial=existing.get("type", "text"),
                widget=forms.Select(attrs={"class": "form-control form-control-sm"}),
            )

        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_class = "metadata-review-settings-form"
        self.helper.layout = Layout(
            Div(
                HTML('<h4 class="mb-3">Metadata Review Configuration</h4>'),
                HTML(
                    '<p class="text-muted">Select which metadata fields to include in review workflows. '
                    'Nested fields are shown as dotted paths (e.g. <code>geonames.name</code>).</p>'
                ),
                HTML(self._build_table_html()),
                Div(
                    Submit("submit", "Save Settings", css_class="btn btn-dark mt-3"),
                    css_class="mt-3",
                ),
                css_class="metadata-review-settings-container",
            )
        )

    def _build_table_html(self):
        """Build HTML tables for document and page metadata field configuration."""
        html = '<div class="metadata-config-section mb-5">'
        html += '<h5 class="mb-3"><i class="fa fa-file-alt me-2"></i>Document Metadata Fields</h5>'

        if self.doc_flat_keys:
            html += (
                '<div class="table-responsive">'
                '<table class="table table-hover table-sm">'
                '<thead><tr>'
                '<th style="width:5%">Include</th>'
                '<th style="width:40%">Metadata Path</th>'
                '<th style="width:30%">Display Label</th>'
                '<th style="width:25%">Field Type</th>'
                '</tr></thead><tbody>'
            )
            for i, metadata_key in enumerate(self.doc_flat_keys):
                prefix = f"doc_{i}"
                html += (
                    f'<tr>'
                    f'<td class="text-center"><div class="form-check">'
                    f'{{{{ form.{prefix}_include }}}}'
                    f'</div></td>'
                    f'<td class="align-middle"><code>{metadata_key}</code></td>'
                    f'<td>{{{{ form.{prefix}_label }}}}</td>'
                    f'<td>{{{{ form.{prefix}_type }}}}</td>'
                    f'</tr>'
                )
            html += '</tbody></table></div>'
        else:
            html += (
                '<div class="alert alert-info">'
                '<i class="fa fa-info-circle me-1"></i>'
                'No document metadata found in this project.</div>'
            )

        html += '</div>'
        html += '<div class="metadata-config-section">'
        html += '<h5 class="mb-3"><i class="fa fa-file me-2"></i>Page Metadata Fields</h5>'

        if self.page_flat_keys:
            html += (
                '<div class="table-responsive">'
                '<table class="table table-hover table-sm">'
                '<thead><tr>'
                '<th style="width:5%">Include</th>'
                '<th style="width:40%">Metadata Path</th>'
                '<th style="width:30%">Display Label</th>'
                '<th style="width:25%">Field Type</th>'
                '</tr></thead><tbody>'
            )
            for i, metadata_key in enumerate(self.page_flat_keys):
                prefix = f"page_{i}"
                html += (
                    f'<tr>'
                    f'<td class="text-center"><div class="form-check">'
                    f'{{{{ form.{prefix}_include }}}}'
                    f'</div></td>'
                    f'<td class="align-middle"><code>{metadata_key}</code></td>'
                    f'<td>{{{{ form.{prefix}_label }}}}</td>'
                    f'<td>{{{{ form.{prefix}_type }}}}</td>'
                    f'</tr>'
                )
            html += '</tbody></table></div>'
        else:
            html += (
                '<div class="alert alert-info">'
                '<i class="fa fa-info-circle me-1"></i>'
                'No page metadata found in this project.</div>'
            )

        html += '</div>'
        return mark_safe(html)

    def save(self):
        """Save the form data to the project configuration."""
        if not self.is_valid():
            return False

        # Build doc field config using the indexed field names
        doc_field_config = {}
        for i, metadata_key in enumerate(self.doc_flat_keys):
            prefix = f"doc_{i}"
            include = self.cleaned_data.get(f"{prefix}_include", False)
            if include:
                doc_field_config[metadata_key] = {
                    "include": True,
                    "label": self.cleaned_data.get(f"{prefix}_label", "").strip() or metadata_key,
                    "type": self.cleaned_data.get(f"{prefix}_type", "text"),
                }

        # Build page field config
        page_field_config = {}
        for i, metadata_key in enumerate(self.page_flat_keys):
            prefix = f"page_{i}"
            include = self.cleaned_data.get(f"{prefix}_include", False)
            if include:
                page_field_config[metadata_key] = {
                    "include": True,
                    "label": self.cleaned_data.get(f"{prefix}_label", "").strip() or metadata_key,
                    "type": self.cleaned_data.get(f"{prefix}_type", "text"),
                }

        # Build a fresh copy of conf_tasks to avoid JSONField in-place mutation issues
        import copy
        conf_tasks = copy.deepcopy(self.project.conf_tasks) if self.project.conf_tasks else {}
        if "metadata_review" not in conf_tasks:
            conf_tasks["metadata_review"] = {}

        conf_tasks["metadata_review"]["document_field_config"] = (
            json.dumps(doc_field_config) if doc_field_config else ""
        )
        conf_tasks["metadata_review"]["page_field_config"] = (
            json.dumps(page_field_config) if page_field_config else ""
        )

        # Re-assign to trigger Django's change detection and save
        self.project.conf_tasks = conf_tasks
        self.project.save(update_fields=["conf_tasks"])
        logger.info("Metadata review settings saved for project %s", self.project.id)
        return True