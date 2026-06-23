"""Forms for Google Sheets configuration."""

import logging
import re

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Div, HTML, Row, Column
from django import forms
from django.utils.safestring import mark_safe

logger = logging.getLogger(__name__)


class GoogleSheetsSettingsForm(forms.Form):
    """Form for configuring Google Sheets connection."""

    google_sheet_id = forms.CharField(
        label="Google Sheet ID",
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Google Sheet ID"}
        ),
        help_text=mark_safe(
            "The ID from your Google Sheets URL:<br/>"
            "<code>https://docs.google.com/spreadsheets/d/<strong>GOOGLE_SHEET_ID</strong>/edit</code>"
        ),
    )

    google_sheet_range = forms.CharField(
        label="Sheet Range",
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Sheet1!A1:D100"}
        ),
        help_text="Range in A1 notation (e.g., Sheet1!A1:D100 or A1:D100)",
    )

    google_sheet_valid_columns = forms.CharField(
        label="Valid Columns",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "column1,column2,column3",
            }
        ),
        help_text="Comma-separated list of column names to import",
    )

    google_sheet_document_id_column = forms.CharField(
        label="Document ID Column",
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "document_id"}
        ),
        help_text="Name of the column containing document IDs",
    )

    google_sheet_document_title_column = forms.CharField(
        label="Document Title Column",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "title"}),
        help_text="Name of the column containing document titles",
    )

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)

        if not project:
            raise ValueError("Project is required for GoogleSheetsSettingsForm")

        self.project = project

        # Load existing configuration
        conf_tasks = project.conf_tasks or {}
        google_sheet_config = conf_tasks.get("google_sheet", {})

        # Populate fields with existing values
        self.fields["google_sheet_id"].initial = google_sheet_config.get("sheet_id", "")
        self.fields["google_sheet_range"].initial = google_sheet_config.get("range", "")
        self.fields["google_sheet_valid_columns"].initial = google_sheet_config.get(
            "valid_columns", ""
        )
        self.fields["google_sheet_document_id_column"].initial = (
            google_sheet_config.get("document_id_column", "")
        )
        self.fields["google_sheet_document_title_column"].initial = (
            google_sheet_config.get("document_title_column", "")
        )

        # Setup crispy forms helper
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_class = "google-sheets-settings-form"
        self.helper.layout = Layout(
            Div(
                HTML('<h4 class="mb-3">Google Sheets Connection</h4>'),
                HTML(
                    '<p class="text-muted">Configure connection to Google Sheets for metadata import.</p>'
                ),
                Row(
                    Column("google_sheet_id", css_class="col-12 mb-3"),
                ),
                Row(
                    Column("google_sheet_range", css_class="col-md-6 mb-3"),
                    Column("google_sheet_valid_columns", css_class="col-md-6 mb-3"),
                ),
                Row(
                    Column(
                        "google_sheet_document_id_column", css_class="col-md-6 mb-3"
                    ),
                    Column(
                        "google_sheet_document_title_column", css_class="col-md-6 mb-3"
                    ),
                ),
                Div(
                    Submit("submit", "Save Settings", css_class="btn btn-dark mt-3"),
                    css_class="mt-3",
                ),
                css_class="google-sheets-settings-container",
            )
        )

    def clean(self):
        """Validate the form data."""
        cleaned_data = super().clean()

        # Get values
        sheet_id = cleaned_data.get("google_sheet_id")
        sheet_range = cleaned_data.get("google_sheet_range")
        valid_cols = cleaned_data.get("google_sheet_valid_columns")
        doc_id_col = cleaned_data.get("google_sheet_document_id_column")
        doc_title_col = cleaned_data.get("google_sheet_document_title_column")

        # Require sheet_id if any other field is set
        if (sheet_range or valid_cols or doc_id_col or doc_title_col) and not sheet_id:
            self.add_error(
                "google_sheet_id",
                "This field is required if other Google Sheet fields are set.",
            )

        # Validate sheet range using regex
        # Format: Sheet1!A1:D100 or A1:D100
        if sheet_range:
            pattern = r"^([a-zA-Z0-9_ ]+!)?[A-Z]+\d+(:[A-Z]+\d+)?$"
            if not re.match(pattern, sheet_range):
                self.add_error(
                    "google_sheet_range",
                    "Invalid range format. Use A1:B10 or Sheet1!A1:B10.",
                )

        # Validate valid columns as comma-separated list
        if valid_cols:
            cols = [c.strip() for c in valid_cols.split(",")]
            if not all(cols):
                self.add_error(
                    "google_sheet_valid_columns",
                    "Please enter a comma-separated list of column names.",
                )
            elif any(" " in col for col in cols):
                self.add_error(
                    "google_sheet_valid_columns",
                    "Column names should not contain spaces.",
                )

        # Validate doc_id_col and doc_title_col to be non-empty and space-free (if filled)
        if doc_id_col and " " in doc_id_col:
            self.add_error(
                "google_sheet_document_id_column",
                "Column name must not contain spaces.",
            )
        if doc_title_col and " " in doc_title_col:
            self.add_error(
                "google_sheet_document_title_column",
                "Column name must not contain spaces.",
            )

        return cleaned_data

    def save(self):
        """Save the form data to the project configuration."""
        if not self.is_valid():
            return False

        # Get cleaned data
        sheet_id = self.cleaned_data.get("google_sheet_id")
        sheet_range = self.cleaned_data.get("google_sheet_range")
        valid_cols = self.cleaned_data.get("google_sheet_valid_columns")
        doc_id_col = self.cleaned_data.get("google_sheet_document_id_column")
        doc_title_col = self.cleaned_data.get("google_sheet_document_title_column")

        # Update project configuration
        if not self.project.conf_tasks:
            self.project.conf_tasks = {}

        self.project.conf_tasks["google_sheet"] = {
            "sheet_id": sheet_id,
            "range": sheet_range,
            "valid_columns": valid_cols,
            "document_id_column": doc_id_col,
            "document_title_column": doc_title_col,
        }

        self.project.save()
        logger.info(f"Google Sheets settings saved for project {self.project.id}")

        return True
