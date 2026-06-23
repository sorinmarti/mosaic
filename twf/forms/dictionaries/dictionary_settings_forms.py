"""Forms for dictionary settings configuration."""

import json
import logging

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Div, HTML
from django import forms
from django.utils.safestring import mark_safe
from django_select2.forms import Select2MultipleWidget

from twf.models import Dictionary

logger = logging.getLogger(__name__)


class DictionarySettingsForm(forms.Form):
    """Form for configuring dictionary enrichment settings."""

    WIKIDATA_ENTITY_CHOICES = [
        ("", "-- Select Entity Type --"),
        ("person", "Person"),
        ("city", "City"),
        ("event", "Event"),
        ("ship", "Ship"),
        ("building", "Building"),
    ]

    ENRICHMENT_TYPE_CHOICES = [
        ("date", "Date Normalization"),
        ("verse", "Bible Verse"),
        ("authority_id", "Authority ID (Generic)"),
        ("gnd", "GND (German National Library)"),
        ("wikidata", "Wikidata"),
        ("geonames", "GeoNames (Geographic Locations)"),
    ]

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)

        if not project:
            raise ValueError("Project is required for DictionarySettingsForm")

        self.project = project

        # Get all distinct dictionary types from the project
        dictionary_types_qs = (
            Dictionary.objects.filter(selected_projects=project)
            .values("type")
            .distinct()
            .order_by("type")
        )

        dictionary_types = [item["type"] for item in dictionary_types_qs]

        # Get counts for each dictionary type
        dictionary_counts = {}
        for dict_type in dictionary_types:
            dictionary_obj = Dictionary.objects.filter(
                selected_projects=project, type=dict_type
            ).first()
            if dictionary_obj:
                from twf.models import DictionaryEntry
                count = DictionaryEntry.objects.filter(dictionary=dictionary_obj).count()
                dictionary_counts[dict_type] = count

        # Load existing configuration
        conf_tasks = project.conf_tasks or {}
        dictionary_types_config = conf_tasks.get("dictionary_types", {})

        # Create fields for each dictionary type
        for dict_type in sorted(dictionary_types):
            count = dictionary_counts.get(dict_type, 0)
            prefix = f"dict_{dict_type}"

            # Get existing configuration for this dictionary type
            dict_config = dictionary_types_config.get(dict_type, {})

            # Enrichment types (multi-select as comma-separated string)
            enrichment_types = dict_config.get("enrichment_types", [])
            if isinstance(enrichment_types, str):
                enrichment_types = enrichment_types.split(",") if enrichment_types else []

            self.fields[f"{prefix}_enrichment_types"] = forms.MultipleChoiceField(
                label="",
                required=False,
                choices=self.ENRICHMENT_TYPE_CHOICES,
                initial=enrichment_types,
                widget=Select2MultipleWidget(
                    attrs={
                        "class": "form-control form-control-sm",
                        "data-dict-type": dict_type,
                    }
                ),
            )

            # Wikidata entity type
            self.fields[f"{prefix}_wikidata_entity_type"] = forms.ChoiceField(
                label="",
                required=False,
                choices=self.WIKIDATA_ENTITY_CHOICES,
                initial=dict_config.get("wikidata_entity_type", ""),
                widget=forms.Select(
                    attrs={
                        "class": "form-control form-control-sm wikidata-field",
                        "data-dict-type": dict_type,
                    }
                ),
            )

            # Workflow title
            self.fields[f"{prefix}_workflow_title"] = forms.CharField(
                label="",
                required=False,
                initial=dict_config.get("workflow_title", ""),
                widget=forms.TextInput(
                    attrs={
                        "class": "form-control form-control-sm",
                        "placeholder": "Workflow title",
                        "data-dict-type": dict_type,
                    }
                ),
            )

        self.dictionary_types = dictionary_types
        self.dictionary_counts = dictionary_counts

        # Setup crispy forms helper
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_class = "dictionary-settings-form"
        self.helper.layout = Layout(
            Div(
                HTML('<h4 class="mb-3">Dictionary Enrichment Configuration</h4>'),
                HTML(
                    '<p class="text-muted">Configure enrichment settings for each dictionary type.</p>'
                ),
                HTML(self._build_table_html()),
                Div(
                    Submit("submit", "Save Settings", css_class="btn btn-dark mt-3"),
                    css_class="mt-3",
                ),
                css_class="dictionary-settings-container",
            )
        )

    def _build_table_html(self):
        """Build HTML table for dictionary type configuration."""
        html = """
        <div class="table-responsive">
            <table class="table table-hover table-sm">
                <thead>
                    <tr>
                        <th>Dictionary Type</th>
                        <th>Count</th>
                        <th>Enrichment Types</th>
                        <th>Wikidata Entity Type <small class="text-muted">(wikidata only)</small></th>
                        <th>Workflow Title</th>
                    </tr>
                </thead>
                <tbody>
        """

        for dict_type in sorted(self.dictionary_types):
            count = self.dictionary_counts.get(dict_type, 0)
            prefix = f"dict_{dict_type}"

            html += f"""
                <tr data-dict-type="{dict_type}">
                    <td class="align-middle"><strong>{dict_type}</strong></td>
                    <td class="align-middle text-muted">{count}</td>
                    <td>{{{{ form.{prefix}_enrichment_types }}}}</td>
                    <td>{{{{ form.{prefix}_wikidata_entity_type }}}}</td>
                    <td>{{{{ form.{prefix}_workflow_title }}}}</td>
                </tr>
            """

        html += """
                </tbody>
            </table>
        </div>

        <script>
        document.addEventListener('DOMContentLoaded', function() {
            // Wait for Select2 to initialize
            setTimeout(function() {
                // Function to toggle wikidata entity type field visibility
                function toggleWikidataFields() {
                    document.querySelectorAll('tr[data-dict-type]').forEach(function(row) {
                        const dictType = row.getAttribute('data-dict-type');
                        const enrichmentTypeSelect = row.querySelector('select[data-dict-type="' + dictType + '"]');
                        const wikidataEntityField = row.querySelector('.wikidata-field');

                        if (enrichmentTypeSelect && wikidataEntityField) {
                            // Check if wikidata is selected in the multi-select
                            const selectedValues = $(enrichmentTypeSelect).val() || [];
                            const isWikidataSelected = selectedValues.includes('wikidata');

                            wikidataEntityField.disabled = !isWikidataSelected;
                            wikidataEntityField.style.opacity = isWikidataSelected ? '1' : '0.5';
                        }
                    });
                }

                // Run on page load
                toggleWikidataFields();

                // Run when enrichment type selection changes (Select2 change event)
                $('select[data-dict-type]').on('change', function() {
                    // Skip the wikidata-field selects
                    if (!$(this).hasClass('wikidata-field')) {
                        toggleWikidataFields();
                    }
                });
            }, 500);
        });
        </script>
        """

        return mark_safe(html)

    def save(self):
        """Save the form data to the project configuration."""
        if not self.is_valid():
            return False

        # Build the configuration dictionary
        dictionary_types_config = {}

        for dict_type in self.dictionary_types:
            prefix = f"dict_{dict_type}"

            # Get enrichment types (multi-select)
            enrichment_types = self.cleaned_data.get(f"{prefix}_enrichment_types", [])

            # Get wikidata entity type
            wikidata_entity_type = self.cleaned_data.get(
                f"{prefix}_wikidata_entity_type", ""
            ).strip()

            # Get workflow title
            workflow_title = self.cleaned_data.get(
                f"{prefix}_workflow_title", ""
            ).strip()

            # Only save if there's configuration
            if enrichment_types or wikidata_entity_type or workflow_title:
                dictionary_types_config[dict_type] = {}

                if enrichment_types:
                    dictionary_types_config[dict_type]["enrichment_types"] = list(enrichment_types)

                if wikidata_entity_type:
                    dictionary_types_config[dict_type]["wikidata_entity_type"] = wikidata_entity_type

                if workflow_title:
                    dictionary_types_config[dict_type]["workflow_title"] = workflow_title

        # Update project configuration
        if not self.project.conf_tasks:
            self.project.conf_tasks = {}

        self.project.conf_tasks["dictionary_types"] = dictionary_types_config

        self.project.save()
        logger.info(f"Dictionary settings saved for project {self.project.id}")

        return True
