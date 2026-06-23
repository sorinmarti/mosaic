"""Contains all forms concerning batch processes."""

from crispy_forms.layout import Row, Column, Fieldset
from django import forms
from django.forms import TextInput
from django_select2.forms import Select2Widget

from twf.forms.base_batch_forms import BaseBatchForm, BaseAIBatchForm


class DictionaryBatchForm(BaseBatchForm):
    """Base form for batches of dictionaries."""

    dictionary = forms.ChoiceField(
        label="Dictionary",
        required=True,
        widget=Select2Widget(attrs={"style": "width: 100%;"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["dictionary"].choices = [("", "Select a dictionary")] + [
            (d.pk, d.label) for d in self.project.selected_dictionaries.all()
        ]

    def get_button_label(self):
        """Get the label for the submit button."""
        return "Start Batch"

    def get_dynamic_fields(self):
        """Get the dynamic fields for the form."""
        return super().get_dynamic_fields() + [
            Row(
                Column("dictionary", css_class="form-group col-12 mb-0"),
                css_class="row form-row",
            )
        ]


class DictionaryAIBatchForm(BaseAIBatchForm):
    """Base form for batches of dictionaries."""

    dictionary = forms.ChoiceField(
        label="Dictionary",
        required=True,
        widget=Select2Widget(attrs={"style": "width: 100%;"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["dictionary"].choices = [("", "Select a dictionary")] + [
            (d.pk, d.label) for d in self.project.selected_dictionaries.all()
        ]

    def get_button_label(self):
        """Get the label for the submit button."""
        return "Start Batch"

    def get_dynamic_fields(self):
        """Get the dynamic fields for the form."""
        return super().get_dynamic_fields() + [
            Row(
                Column("dictionary", css_class="form-group col-12 mb-0"),
                css_class="row form-row",
            )
        ]


class UnifiedDictionaryAIBatchForm(DictionaryAIBatchForm):
    """
    Unified form for AI batch processing of dictionary entries.

    Uses AIConfiguration objects which contain all settings
    (provider, model, prompt, role, etc.). The form only selects
    which configuration to use and dictionary-specific options.
    """

    def get_button_label(self):
        """
        Get the label for the submit button.

        Returns:
            str: The button label.
        """
        return "Start AI Batch"


class UnifiedDictionaryAIRequestForm(DictionaryAIBatchForm):
    """
    Unified form for AI request (supervised) processing of dictionary entries.

    Uses AIConfiguration objects which contain all settings
    (provider, model, prompt, role, etc.). The form only selects
    which configuration to use and dictionary-specific options.
    """

    def get_button_label(self):
        """
        Get the label for the submit button.

        Returns:
            str: The button label.
        """
        return "Send AI Request"


class GeonamesBatchForm(DictionaryBatchForm):
    """Form for batch processing Geonames data."""

    geonames_username = forms.CharField(
        required=False,
        label="GeoNames Username",
        widget=TextInput(attrs={"placeholder": "GeoNames Username"}),
        help_text="Your GeoNames account username (register at geonames.org)",
    )

    only_search_in = forms.CharField(
        label="Only search in",
        required=False,
        help_text="Enter a country code (ISO-3166) to only search in that country."
        "Leave empty to search in all countries.",
    )
    similarity_threshold = forms.IntegerField(
        label="Similarity threshold",
        required=False,
        help_text="The similarity threshold for the search results. " "Default is 80.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["similarity_threshold"].initial = 80

        # Populate GeoNames username from project if available
        if self.project:
            geonames_creds = self.project.get_credentials("geonames")
            if geonames_creds:
                self.fields["geonames_username"].initial = geonames_creds.get("username", "")

    def get_button_label(self):
        """Get the label for the submit button."""
        return "Start Geonames Batch"

    def get_dynamic_fields(self):
        """Get the dynamic fields for the form."""
        fields = super().get_dynamic_fields()
        fields.insert(0,
            Fieldset(
                "GeoNames Credentials",
                Row(
                    Column("geonames_username", css_class="form-group col-12 mb-3"),
                    css_class="row form-row",
                ),
            )
        )
        fields.append(
            Row(
                Column("only_search_in", css_class="form-group col-6 mb-0"),
                Column("similarity_threshold", css_class="form-group col-6 mb-0"),
                css_class="row form-row",
            )
        )
        return fields

    def save_credentials(self):
        """Save GeoNames credentials to the project."""
        if self.project and self.is_valid():
            username = self.cleaned_data.get("geonames_username")

            # Get existing credentials
            credentials = self.project.conf_credentials or {}

            # Update GeoNames credentials
            credentials["geonames"] = {
                "username": username or "",
            }

            # Save back to project
            self.project.conf_credentials = credentials
            self.project.save()


class GNDBatchForm(DictionaryBatchForm):
    """Form for batch processing Geonames data."""

    earliest_birth_year = forms.IntegerField(
        label="Earliest Birth Year", required=False
    )
    latest_birth_year = forms.IntegerField(label="Latest Birth Year", required=False)
    show_empty = forms.BooleanField(
        label="Include results without birth dates/years", required=False
    )

    def get_button_label(self):
        return "Start GND Batch"

    def get_dynamic_fields(self):
        """Get the dynamic fields for the form."""
        fields = super().get_dynamic_fields()
        fields.append(
            Row(
                Column("earliest_birth_year", css_class="form-group col-4 mb-0"),
                Column("latest_birth_year", css_class="form-group col-4 mb-0"),
                Column("show_empty", css_class="form-group col-4 mb-0"),
                css_class="row form-row",
            )
        )
        return fields


class WikidataBatchForm(DictionaryBatchForm):
    """Form for batch processing Geonames data."""

    entity_type = forms.ChoiceField(
        label="Entity Type",
        required=True,
        choices=[
            ("city", "City"),
            ("person", "Person"),
            ("event", "Event"),
            ("ship", "Ship"),
            ("building", "Building"),
        ],
        widget=Select2Widget(attrs={"style": "width: 100%;"}),
    )
    language = forms.CharField(label="Language", required=True, initial="en")

    def get_button_label(self):
        """Get the label for the submit button."""
        return "Start Wikidata Batch"

    def get_dynamic_fields(self):
        """Get the dynamic fields for the form."""
        fields = super().get_dynamic_fields()
        fields.append(
            Row(
                Column("entity_type", css_class="form-group col-6 mb-0"),
                Column("language", css_class="form-group col-6 mb-0"),
                css_class="row form-row",
            )
        )
        return fields
