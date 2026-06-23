"""Forms for tag settings configuration."""

import json
import logging

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Div, HTML
from django import forms
from django.utils.safestring import mark_safe

from twf.models import PageTag

logger = logging.getLogger(__name__)


class TagTypeConfigForm(forms.Form):
    """Form for configuring a single tag type."""

    WORKFLOW_CHOICES = [
        ("group", "Group (assign to dictionary)"),
        ("enrich", "Enrich (direct enrichment workflow)"),
        ("ignore", "Ignore (exclude from processing)"),
    ]

    WIKIDATA_ENTITY_CHOICES = [
        ("", "-- Select Entity Type --"),
        ("person", "Person"),
        ("city", "City"),
        ("event", "Event"),
        ("ship", "Ship"),
        ("building", "Building"),
    ]

    tag_type = forms.CharField(widget=forms.HiddenInput(), required=True)

    translation = forms.CharField(
        label="Dictionary Type",
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "e.g., person, place"}
        ),
        help_text='Connect this tag type to a dictionary type (e.g., "sender_person" → "person")',
    )

    workflow_type = forms.ChoiceField(
        label="Workflow",
        choices=WORKFLOW_CHOICES,
        initial="group",
        widget=forms.Select(attrs={"class": "form-control workflow-type-select"}),
        help_text="How should this tag type be processed?",
    )

    workflow_title = forms.CharField(
        label="Workflow Title",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control enrichment-field",
                "placeholder": "e.g., Normalize Bible Verses",
            }
        ),
        help_text='Title shown in enrichment workflow (only for "enrich" type)',
    )

    FORM_TYPE_CHOICES = [
        ("", "-- Select Form Type --"),
        ("date", "Date Normalization"),
        ("verse", "Bible Verse"),
        ("authority_id", "Authority ID (Generic)"),
        ("gnd", "GND (German National Library)"),
        ("wikidata", "Wikidata"),
        ("geonames", "GeoNames (Geographic Locations)"),
    ]

    form_type = forms.ChoiceField(
        label="Form Type",
        required=False,
        choices=FORM_TYPE_CHOICES,
        widget=forms.Select(
            attrs={"class": "form-control enrichment-field"}
        ),
        help_text='Form type for enrichment (only for "enrich" workflow)',
    )

    wikidata_entity_type = forms.ChoiceField(
        label="Wikidata Entity Type",
        required=False,
        choices=WIKIDATA_ENTITY_CHOICES,
        widget=forms.Select(
            attrs={"class": "form-control enrichment-field"}
        ),
        help_text='Entity type for Wikidata searches (only for "wikidata" form type)',
    )

    def __init__(self, *args, **kwargs):
        self.tag_type_value = kwargs.pop("tag_type", None)
        self.count = kwargs.pop("count", 0)
        super().__init__(*args, **kwargs)

        if self.tag_type_value:
            self.fields["tag_type"].initial = self.tag_type_value


class TagSettingsForm(forms.Form):
    """Form for configuring tag-specific settings using individual fields per tag type."""

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)

        if not project:
            raise ValueError("Project is required for TagSettingsForm")

        self.project = project

        # Get all distinct tag types from the project
        tag_types_qs = (
            PageTag.objects.filter(page__document__project=project)
            .values("variation_type")
            .distinct()
            .order_by("variation_type")
        )

        tag_types = [item["variation_type"] for item in tag_types_qs]

        # Get counts for each tag type
        tag_counts = {}
        for tag_type in tag_types:
            count = PageTag.objects.filter(
                page__document__project=project, variation_type=tag_type
            ).count()
            tag_counts[tag_type] = count

        # Load existing configuration
        conf_tasks = project.conf_tasks or {}
        tag_types_config = conf_tasks.get("tag_types", {})

        # Parse existing configurations
        tag_type_translator = {}
        ignored_types = []
        date_types = []
        enrichment_types = {}

        if "tag_type_translator" in tag_types_config:
            try:
                tag_type_translator = json.loads(
                    tag_types_config["tag_type_translator"]
                )
            except (json.JSONDecodeError, TypeError):
                pass

        if "ignored_tag_types" in tag_types_config:
            try:
                ignored_config = json.loads(tag_types_config["ignored_tag_types"])
                ignored_types = ignored_config.get("ignored", [])
                date_types = ignored_config.get("dates", [])
            except (json.JSONDecodeError, TypeError):
                pass

        if "enrichment_types_config" in tag_types_config:
            try:
                enrichment_types = json.loads(
                    tag_types_config["enrichment_types_config"]
                )
            except (json.JSONDecodeError, TypeError):
                pass

        # Create fields for each tag type
        for tag_type in sorted(tag_types):
            count = tag_counts.get(tag_type, 0)
            prefix = f"tag_{tag_type}"

            # Determine workflow type
            if tag_type in ignored_types:
                workflow_type = "ignore"
            elif tag_type in enrichment_types or tag_type in date_types:
                workflow_type = "enrich"
            else:
                workflow_type = "group"

            # Translation field
            self.fields[f"{prefix}_translation"] = forms.CharField(
                label="",
                required=False,
                initial=tag_type_translator.get(tag_type, ""),
                widget=forms.TextInput(
                    attrs={
                        "class": "form-control form-control-sm",
                        "placeholder": "Dictionary type",
                    }
                ),
            )

            # Workflow type field
            self.fields[f"{prefix}_workflow"] = forms.ChoiceField(
                label="",
                choices=TagTypeConfigForm.WORKFLOW_CHOICES,
                initial=workflow_type,
                widget=forms.Select(
                    attrs={
                        "class": "form-control form-control-sm workflow-type-select",
                        "data-tag-type": tag_type,
                    }
                ),
            )

            # Enrichment configuration fields
            enrichment_config = enrichment_types.get(tag_type, {})

            self.fields[f"{prefix}_workflow_title"] = forms.CharField(
                label="",
                required=False,
                initial=enrichment_config.get("workflow_title", ""),
                widget=forms.TextInput(
                    attrs={
                        "class": "form-control form-control-sm enrichment-field",
                        "placeholder": "Workflow title",
                        "data-tag-type": tag_type,
                    }
                ),
            )

            self.fields[f"{prefix}_form_type"] = forms.ChoiceField(
                label="",
                required=False,
                choices=TagTypeConfigForm.FORM_TYPE_CHOICES,
                initial=enrichment_config.get("form_type", ""),
                widget=forms.Select(
                    attrs={
                        "class": "form-control form-control-sm enrichment-field",
                        "data-tag-type": tag_type,
                    }
                ),
            )

            self.fields[f"{prefix}_wikidata_entity_type"] = forms.ChoiceField(
                label="",
                required=False,
                choices=TagTypeConfigForm.WIKIDATA_ENTITY_CHOICES,
                initial=enrichment_config.get("wikidata_entity_type", ""),
                widget=forms.Select(
                    attrs={
                        "class": "form-control form-control-sm enrichment-field",
                        "data-tag-type": tag_type,
                    }
                ),
            )

        self.tag_types = tag_types
        self.tag_counts = tag_counts

        # Setup crispy forms helper
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_class = "tag-settings-form"
        self.helper.layout = Layout(
            Div(
                HTML('<h4 class="mb-3">Tag Type Configuration</h4>'),
                HTML(
                    '<p class="text-muted">Configure how each tag type is processed in your project.</p>'
                ),
                HTML(self._build_table_html()),
                Div(
                    Submit("submit", "Save Settings", css_class="btn btn-dark mt-3"),
                    css_class="mt-3",
                ),
                css_class="tag-settings-container",
            )
        )

    def _build_table_html(self):
        """Build HTML table for tag type configuration."""
        html = """
        <div class="table-responsive">
            <table class="table table-hover table-sm">
                <thead>
                    <tr>
                        <th>Tag Type</th>
                        <th>Count</th>
                        <th>Dictionary Type</th>
                        <th>Workflow</th>
                        <th>Workflow Title <small class="text-muted">(enrich only)</small></th>
                        <th>Form Type <small class="text-muted">(enrich only)</small></th>
                        <th>Wikidata Entity <small class="text-muted">(wikidata only)</small></th>
                    </tr>
                </thead>
                <tbody>
        """

        for tag_type in sorted(self.tag_types):
            count = self.tag_counts.get(tag_type, 0)
            prefix = f"tag_{tag_type}"

            html += f"""
                <tr data-tag-type="{tag_type}">
                    <td class="align-middle"><strong>{tag_type}</strong></td>
                    <td class="align-middle text-muted">{count}</td>
                    <td>{{{{ form.{prefix}_translation }}}}</td>
                    <td>{{{{ form.{prefix}_workflow }}}}</td>
                    <td>{{{{ form.{prefix}_workflow_title }}}}</td>
                    <td>{{{{ form.{prefix}_form_type }}}}</td>
                    <td>{{{{ form.{prefix}_wikidata_entity_type }}}}</td>
                </tr>
            """

        html += """
                </tbody>
            </table>
        </div>

        <script>
        document.addEventListener('DOMContentLoaded', function() {
            // Function to toggle enrichment fields visibility
            function toggleEnrichmentFields() {
                document.querySelectorAll('.workflow-type-select').forEach(function(select) {
                    const tagType = select.getAttribute('data-tag-type');
                    const row = select.closest('tr');
                    const enrichmentFields = row.querySelectorAll('.enrichment-field');
                    const isEnrich = select.value === 'enrich';

                    enrichmentFields.forEach(function(field) {
                        field.disabled = !isEnrich;
                        if (!isEnrich) {
                            field.value = '';
                        }
                        // Visual feedback
                        field.style.opacity = isEnrich ? '1' : '0.5';
                    });
                });
            }

            // Run on page load
            toggleEnrichmentFields();

            // Run when workflow type changes
            document.querySelectorAll('.workflow-type-select').forEach(function(select) {
                select.addEventListener('change', toggleEnrichmentFields);
            });
        });
        </script>
        """

        return mark_safe(html)

    def save(self):
        """Save the form data to the project configuration."""
        if not self.is_valid():
            return False

        # Build the configuration dictionaries
        tag_type_translator = {}
        ignored_types = []
        date_types = []
        enrichment_types = {}

        for tag_type in self.tag_types:
            prefix = f"tag_{tag_type}"

            # Get workflow type
            workflow_type = self.cleaned_data.get(f"{prefix}_workflow", "group")

            # Translation (if provided)
            translation = self.cleaned_data.get(f"{prefix}_translation", "").strip()
            if translation:
                tag_type_translator[tag_type] = translation

            # Workflow configuration
            if workflow_type == "ignore":
                ignored_types.append(tag_type)
            elif workflow_type == "enrich":
                workflow_title = self.cleaned_data.get(
                    f"{prefix}_workflow_title", ""
                ).strip()
                form_type = self.cleaned_data.get(f"{prefix}_form_type", "").strip()
                wikidata_entity_type = self.cleaned_data.get(
                    f"{prefix}_wikidata_entity_type", ""
                ).strip()

                enrichment_config = {}
                if workflow_title:
                    enrichment_config["workflow_title"] = workflow_title
                if form_type:
                    enrichment_config["form_type"] = form_type
                if wikidata_entity_type:
                    enrichment_config["wikidata_entity_type"] = wikidata_entity_type

                if enrichment_config:
                    enrichment_types[tag_type] = enrichment_config

        # Build ignored_tag_types configuration
        ignored_config = {}
        if ignored_types:
            ignored_config["ignored"] = ignored_types
        if date_types:
            ignored_config["dates"] = date_types

        # Update project configuration
        if not self.project.conf_tasks:
            self.project.conf_tasks = {}

        if "tag_types" not in self.project.conf_tasks:
            self.project.conf_tasks["tag_types"] = {}

        # Store as JSON strings to maintain compatibility
        self.project.conf_tasks["tag_types"]["tag_type_translator"] = (
            json.dumps(tag_type_translator, indent=2) if tag_type_translator else ""
        )

        self.project.conf_tasks["tag_types"]["ignored_tag_types"] = (
            json.dumps(ignored_config, indent=2) if ignored_config else ""
        )

        self.project.conf_tasks["tag_types"]["enrichment_types_config"] = (
            json.dumps(enrichment_types, indent=2) if enrichment_types else ""
        )

        self.project.save()
        logger.info(f"Tag settings saved for project {self.project.id}")

        return True
