"""Forms for creating and updating documents."""

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Row, Column, Div, HTML
from django import forms
from django.contrib.auth import get_user_model
from django.template.defaultfilters import safe
from django_select2.forms import Select2MultipleWidget

from twf.models import Document, DictionaryEntry, Page


class DocumentSearchForm(forms.Form):
    """Form for searching documents and their contents."""

    title = forms.CharField(
        required=False,
        label="Title Contains",
        help_text="Title of the document. Can be a full title or a part of it.",
    )
    document_id = forms.CharField(
        required=False,
        label="Document ID",
        help_text="Transkribus Document ID. Can be a full ID or a part of it.",
    )
    status = forms.MultipleChoiceField(
        choices=[("parked", "Parked"), *Document.STATUS_CHOICES],
        required=False,
        label="Status",
        widget=Select2MultipleWidget(attrs={"style": "width: 100%;"}),
        help_text="Any of the selected statuses will be included in the result."
        "Documents can be parked and have an additional status.",
    )

    # Page fields
    document_text = forms.CharField(
        required=False,
        label="Text Contains",
        help_text="Text on all pages of the document. You can use regular expressions.",
    )

    use_regex_for_text = forms.BooleanField(
        required=False,
        label="Use RegEx",
        help_text="If checked, the text field will be interpreted as a regex.",
    )

    has_entries = forms.ModelMultipleChoiceField(
        queryset=DictionaryEntry.objects.all(),
        required=False,
        label="References Dictionary Entries",
        help_text="The dictionary entries associated with the tags in this document.",
        widget=Select2MultipleWidget(attrs={"style": "width: 100%;"}),
    )
    has_tags = forms.CharField(
        required=False,
        label="Tags Contain",
        help_text="Search for text which is tagged in the document.",
    )

    # Created / Modified
    created_by = forms.ModelChoiceField(
        queryset=get_user_model().objects.all(), required=False
    )
    modified_by = forms.ModelChoiceField(
        queryset=get_user_model().objects.all(), required=False
    )
    created_from = forms.DateField(
        required=False,
        label="Created After",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    created_to = forms.DateField(
        required=False,
        label="Created Before",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    modified_from = forms.DateField(
        required=False,
        label="Modified After",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    modified_to = forms.DateField(
        required=False,
        label="Modified Before",
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def __init__(self, *args, **kwargs):
        """Initialize the form."""
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_class = "form"
        controls_html_list = []
        metadata_object_list = sorted(
            set(
                Page.get_distinct_metadata_keys()
                + Document.get_distinct_metadata_keys()
            )
        )

        metadata_object_choices = [
            (metadata_object, metadata_object)
            for metadata_object in metadata_object_list
        ]
        metadata_object_choices.insert(0, ("", ""))

        for index in range(5):
            # Set no labels for rows 1–4
            label = None if index > 0 else True

            # Add the form fields
            self.fields[f"type_field_{index}"] = forms.ChoiceField(
                required=False,
                choices=[("", ""), ("document", "Document"), ("page", "Page")],
                label="Document or Page?" if label else "",
            )
            self.fields[f"has_field_{index}"] = forms.ChoiceField(
                required=False,
                choices=[
                    ("contains", "Contains"),
                    ("not_contain", "Does not contain"),
                    ("exact", "Exact match"),
                    ("regex", "Regular expression"),
                ],
                label=safe("&nbsp;") if label else "",
            )
            self.fields[f"what_field_{index}"] = forms.ChoiceField(
                required=False,
                choices=metadata_object_choices,
                label="In this metadata object" if label else "",
            )
            self.fields[f"key_field_{index}"] = forms.CharField(
                required=False,
                label="search for this key" if label else "",
            )
            self.fields[f"query_field_{index}"] = forms.CharField(
                required=False,
                label="with this content" if label else "",
            )

            # Control plus/delete buttons
            controls_html = '<div class="form-group col-md-2 mb-0">'
            if index == 0:
                controls_html += '<label class="mt-2">&nbsp;</label>'

            if index < 4 or index > 0:
                controls_html += '<div class="d-flex justify-content-between">'
                if index > 0:
                    controls_html += (
                        " <button type='button' class='btn btn-sm btn-danger mt-1 remove-field' "
                        f"data-index='{index}'>"
                        "<i class='fa fa-trash'></i></button>&nbsp;"
                    )
                if index < 4:
                    controls_html += (
                        "<button type='button' class='btn btn-sm btn-outline-dark mt-1 add-field' "
                        f"data-index='{index}'>"
                        "<i class='fa fa-plus'></i></button>"
                    )
                controls_html += "</div>"
            controls_html += "</div>"
            controls_html_list.append(controls_html)

        # Add hidden field to indicate that the form has been submitted
        self.fields["search_submitted"] = forms.CharField(
            required=False, widget=forms.HiddenInput(), initial="1"
        )

        self.helper.layout = Layout(
            Row(
                Column("document_text", css_class="form-group col-md-10 mb-0"),
                Column("use_regex_for_text", css_class="form-group col-md-2 mb-0"),
                css_class="form-row",
            ),
            Row(
                Column("title", css_class="form-group col-md-4 mb-0"),
                Column("document_id", css_class="form-group col-md-4 mb-0"),
                Column("status", css_class="form-group col-md-4 mb-0"),
                css_class="form-row",
            ),
            Row(
                Column("has_entries", css_class="form-group col-md-6 mb-0"),
                Column("has_tags", css_class="form-group col-md-6 mb-0"),
                css_class="form-row",
            ),
            Row(
                Column(
                    HTML("<hr/><h6>Metadata Filters</h6>"),
                    css_class="form-group col-md-12 mb-0",
                ),
            ),
        )

        # Add the dynamic fields for type, has, what, and query
        for index in range(5):
            self.helper.layout.append(
                Div(
                    Row(
                        Column(
                            f"type_field_{index}", css_class="form-group col-md-2 mb-0"
                        ),
                        Column(
                            f"what_field_{index}", css_class="form-group col-md-2 mb-0"
                        ),
                        Column(
                            f"key_field_{index}", css_class="form-group col-md-2 mb-0"
                        ),
                        Column(
                            f"query_field_{index}", css_class="form-group col-md-3 mb-0"
                        ),
                        Column(
                            f"has_field_{index}", css_class="form-group col-md-2 mb-0"
                        ),
                        Column(
                            HTML(
                                f"<div class='d-flex'>{controls_html_list[index]}</div>"
                            ),
                            css_class="form-group col-md-1 mb-0",
                        ),
                        css_class="form-row",
                    ),
                    css_class=f'dynamic-meta-row meta-row-{index}{" d-none" if index > 0 else ""}',
                    id=f"meta-row-{index}",
                )
            )

        self.helper.layout.append(
            Row(
                Column(
                    HTML(
                        '<div class="text-small text-muted">'
                        "You can search for metadata in the document and its pages. Use the controls to add or remove "
                        "metadata filters. All applied filters will be combined with AND logic. "
                        "</div>"
                    ),
                    css_class="form-group col-md-12 mb-0",
                ),
            ),
        )
        self.helper.layout.append(
            Row(
                Column(
                    HTML("<hr/><h6>Internal Metadata</h6>"),
                    css_class="form-group col-md-12 mb-0",
                ),
            ),
        )
        self.helper.layout.append(
            Row(
                Column("created_by", css_class="form-group col-md-2 mb-0"),
                Column("created_from", css_class="form-group col-md-2 mb-0"),
                Column("created_to", css_class="form-group col-md-2 mb-0"),
                Column("modified_by", css_class="form-group col-md-2 mb-0"),
                Column("modified_from", css_class="form-group col-md-2 mb-0"),
                Column("modified_to", css_class="form-group col-md-2 mb-0"),
                css_class="form-row",
            )
        )

        self.helper.layout.append("search_submitted")

        self.helper.layout.append(
            Div(
                Submit("submit", "Search Documents", css_class="btn btn-dark"),
                css_class="text-end pt-3",
            )
        )


class DocumentForm(forms.ModelForm):
    """Form for creating and updating documents."""

    class Meta:
        model = Document
        fields = ["title", "document_id", "metadata"]
        widgets = {
            "metadata": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        helper = FormHelper()
        helper.form_method = "post"
        helper.form_class = "form"

        helper.layout = Layout(
            Row(
                Column("title", css_class="form-group col-6 mb-3"),
                Column("document_id", css_class="form-group col-6 mb-3"),
                css_class="row form-row",
            ),
            Row(
                Column("metadata", css_class="form-group col-12 mb-3"),
                css_class="row form-row",
            ),
            Div(
                Submit("submit", "Create Document", css_class="btn btn-dark"),
                css_class="text-end pt-3",
            ),
        )

        self.helper = helper
