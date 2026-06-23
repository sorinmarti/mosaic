"""Forms for the twf app."""

from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Column, Row, Div
from collections import defaultdict
from django_select2.forms import Select2Widget

from twf.models import DictionaryEntry, Dictionary


class DictionaryForm(forms.ModelForm):
    """Form for creating and updating a dictionary."""

    class Meta:
        model = Dictionary
        fields = ["label", "type"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column("label", css_class="form-group col-md-6 mb-0"),
                Column("type", css_class="form-group col-md-6 mb-0"),
                css_class="row form-row",
            ),
            Div(
                Submit("submit", "Save Dictionary", css_class="btn btn-dark"),
                css_class="text-end pt-3",
            ),
        )


class DictionaryEntryForm(forms.ModelForm):
    """Form for creating and updating a dictionary entry."""

    class Meta:
        model = DictionaryEntry
        fields = ["label", "review_status", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column("label", css_class="form-group col-12 mb-0"),
                css_class="row form-row",
            ),
            Row(
                Column("review_status", css_class="form-group col-12 mb-0"),
                css_class="row form-row",
            ),
            Row(
                Column("notes", css_class="form-group col-12 mb-0"),
                css_class="row form-row",
            ),
            Div(
                Submit("save_entry", "Save Dictionary Entry", css_class="btn btn-dark"),
                css_class="text-end pt-3",
            ),
        )


class DictionaryImportForm(forms.Form):
    """Form for importing a dictionary."""

    type_selection = forms.ChoiceField(
        choices=(("csv", "CSV"), ("json", "JSON")), label="File Type"
    )
    file = forms.FileField(label="Dictionary File")
    label = forms.CharField(max_length=100, label="Label")
    type = forms.CharField(label="Type")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column("type_selection", css_class="form-group col-md-12 mb-0"),
                css_class="row form-row",
            ),
            Row(
                Column("file", css_class="form-group col-md-12 mb-0"),
                css_class="row form-row",
            ),
            Row(
                Column("label", css_class="form-group col-md-6 mb-0"),
                Column("type", css_class="form-group col-md-6 mb-0"),
                css_class="row form-row",
            ),
            Div(
                Submit("submit", "Import Dictionary", css_class="btn btn-dark"),
                css_class="text-end pt-3",
            ),
        )


class MergeEntriesForm(forms.Form):
    """Form for merging dictionary entries with optgroups."""

    remaining_entry = forms.ChoiceField(
        label="Remaining Entry",
        required=True,
        widget=Select2Widget,
        help_text="This entry will remain after the merge.",
    )

    merge_entry = forms.ChoiceField(
        label="Entry to Merge",
        required=True,
        widget=Select2Widget,
        help_text="This entry will be merged into the remaining entry and then deleted.",
    )

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)

        if not project:
            raise ValueError("Project is required for MergeEntriesForm")

        # Get all dictionaries and their entries
        dictionaries = project.selected_dictionaries.all()
        entries = (
            DictionaryEntry.objects.filter(dictionary__in=dictionaries)
            .select_related("dictionary")
            .order_by("dictionary__label", "label")
        )

        # Organize entries by dictionary for optgroups
        entries_by_dict = defaultdict(list)
        for entry in entries:
            entries_by_dict[entry.dictionary.label].append((entry.id, entry.label))

        # Build choices with optgroups
        choices = [("", "Select an entry")]
        for dict_label in sorted(entries_by_dict.keys()):
            choices.append((dict_label, entries_by_dict[dict_label]))

        # Set choices for both fields
        self.fields["remaining_entry"].choices = choices
        self.fields["merge_entry"].choices = choices

        # Setup crispy forms
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            Row(
                Column("remaining_entry", css_class="form-group col-md-6 mb-3"),
                Column("merge_entry", css_class="form-group col-md-6 mb-3"),
                css_class="row",
            ),
            Div(
                Submit("merge", "Merge Entries", css_class="btn btn-dark"),
                css_class="mt-3",
            ),
        )
