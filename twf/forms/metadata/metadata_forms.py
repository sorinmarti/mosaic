"""Forms for enriching dictionary entries"""

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Row, Column, Layout, Div, Submit
from django import forms

from twf.forms.base_batch_forms import BaseBatchForm
from twf.models import Dictionary


class LoadMetadataForm(BaseBatchForm):
    """Form for loading metadata from a CSV file."""

    data_target_type = forms.ChoiceField(
        label="Data Target Type",
        choices=[("document", "Document"), ("page", "Page")],
        required=True,
        widget=forms.Select(attrs={"class": "form-control"}),
        help_text="Your json must be aimed at transkribus documents or pages. Select if you want to load the data to "
        "the documents (you provide a doc id) or the pages (you provide a page id).",
    )
    data_file = forms.FileField(
        label="Data File",
        required=True,
        help_text="Upload a JSON file with the metadata to load. It must be a list of objects or an object with keys "
        "that match yor document or page ids.",
        widget=forms.ClearableFileInput(attrs={"accept": ".json"}),
    )

    metadata_storage_key = forms.CharField(
        label="Metadata Storage Key",
        required=False,
        initial="json_import",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "json_import"}
        ),
        help_text="Key under which to store the imported metadata in document.metadata. "
        "Leave empty to merge directly into metadata without nesting.",
    )

    json_data_key = forms.CharField(
        label="JSON Data Key (List Format Only)",
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "doc_id"}
        ),
        help_text="If your JSON is a LIST of objects, specify which field contains the document/page ID. "
        'Example: "doc_id" or "document_id". Leave empty if your JSON is an OBJECT with IDs as keys.',
    )

    match_to_field = forms.ChoiceField(
        label="Match to Field",
        choices=[("dbid", "Database ID"), ("docid", "Transkribus Document/Page ID")],
        required=False,
        initial="docid",
        widget=forms.Select(attrs={"class": "form-control"}),
        help_text="Normally you will want to match the data to the Transkribus document or page ID. If you have "
        "provided a database ID in your JSON data, you can match to that instead.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_button_label(self):
        return "Load Data"

    def get_dynamic_fields(self):
        return [
            Row(
                Column("data_target_type", css_class="form-group col-6 mb-3"),
                Column("data_file", css_class="form-group col-6 mb-3"),
                css_class="row form-row",
            ),
            Row(
                Column("metadata_storage_key", css_class="form-group col-6 mb-3"),
                Column("match_to_field", css_class="form-group col-6 mb-3"),
                css_class="row form-row",
            ),
            Row(
                Column("json_data_key", css_class="form-group col-12 mb-3"),
                css_class="row form-row",
            ),
        ]


class ExtractMetadataValuesForm(forms.Form):
    """Form for extracting metadata values from a JSON file
    and associating them with dictionary entries."""

    json_data_key = forms.CharField(
        label="JSON Data Key",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    dictionary = forms.ModelChoiceField(
        label="Dictionary",
        queryset=Dictionary.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        project = kwargs.pop("project", None)
        super().__init__(*args, **kwargs)

        self.fields["dictionary"].queryset = project.selected_dictionaries.all()

        self.helper = FormHelper()
        self.helper.method = "post"

        self.helper.layout = Layout()

        self.helper.layout.append(
            Row(
                Column("json_data_key", css_class="form-group col-6 mb-3"),
                Column("dictionary", css_class="form-group col-6 mb-3"),
                css_class="row form-row",
            )
        )

        self.helper.layout.append(
            Div(
                Submit("submit", "Load Data", css_class="btn btn-dark"),
                css_class="text-end pt-3",
            )
        )


class LoadSheetsMetadataForm(BaseBatchForm):
    """Form for loading metadata from Google Sheets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_button_label(self):
        return "Load Google Sheets Data"

    def get_dynamic_fields(self):
        return []
