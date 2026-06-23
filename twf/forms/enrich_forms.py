"""Forms for enriching dictionary entries"""

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Div, Submit
from django import forms
from jsoneditor.forms import JSONEditor

from twf.models import DictionaryEntry


class EnrichEntryManualForm(forms.ModelForm):
    """Form for manually enriching a dictionary"""

    metadata = forms.CharField(widget=JSONEditor(attrs={"style": "min-height: 400px;"}))

    class Meta:
        model = DictionaryEntry
        fields = ["metadata"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column("metadata", css_class="form-group col-md-12 mb-0"),
            ),
            Div(
                Submit("submit", "Save Data", css_class="btn btn-dark"),
                Submit("submit", "Save Data and Show next", css_class="btn btn-dark"),
                css_class="text-end pt-3",
            ),
        )


class EnrichEntryForm(forms.Form):
    """Form for enriching a dictionary entry"""

    search_term = forms.CharField(
        label="Search Term", help_text="Enter a search term to find a matching entry."
    )

    def __init__(self, *args, **kwargs):
        search_term = kwargs.pop("search_term", None)
        form_name = kwargs.pop("form_name", None)
        super().__init__(*args, **kwargs)

        self.fields["search_term"].initial = search_term

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column("search_term", css_class="form-group col-12 mb-0"),
            ),
            Div(
                Submit(f"submit_{form_name}", "Search", css_class="btn btn-dark"),
                css_class="text-end pt-3",
            ),
        )
