"""Forms for tags."""

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, HTML, Div, Submit, Field
from django import forms
from django.urls import reverse

from twf.utils.date_utils import parse_date_string


class DateNormalizationForm(forms.Form):
    """Form for date normalization."""

    resolve_to = forms.ChoiceField(
        label="Resolve to",
        choices=[("year", "Year"), ("month", "Month"), ("day", "Day")],
        required=True,
        widget=forms.Select(attrs={"class": "form-control"}),
        help_text="Choose the level of resolution for the date normalization. For example, if the date is '2022', "
        "the resolved date will be '2022-XX-XX' if you choose 'Day'.",
    )

    input_date_format = forms.ChoiceField(
        label="Input Date Format",
        choices=[
            ("DMY", "Day-Month-Year"),
            ("MDY", "Month-Day-Year"),
            ("YMD", "Year-Month-Day"),
        ],
        required=True,
        widget=forms.Select(attrs={"class": "form-control"}),
        help_text="If you have ambiguous formats like '01/02/2022', '2022-02-01', etc., choose the appropriate format.",
    )

    resulting_date = forms.CharField(
        label="Resulting Date",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        help_text="This is a proposal of the resulting date after normalization. ",
    )

    date_tag = forms.IntegerField(widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        project = kwargs.pop("project", None)
        date_tag = kwargs.pop("date_tag", None)
        super().__init__(*args, **kwargs)

        if not project or not date_tag:
            raise ValueError("Project and date_tag are required.")

        conf = project.get_task_configuration("date_normalization")

        resolve_to = conf.get("resolve_to", "day")
        input_date_format = conf.get("input_date_format", "DMY")
        normalized_date = parse_date_string(
            date_tag.variation, resolve_to=resolve_to, date_format=input_date_format
        )

        self.fields["input_date_format"].initial = input_date_format
        self.fields["resolve_to"].initial = resolve_to
        self.fields["resulting_date"].initial = normalized_date
        self.fields["date_tag"].initial = date_tag.pk

        self.helper = FormHelper()
        self.helper.method = "post"

        self.helper.layout = Layout()

        # Build context display HTML using PageTag's built-in get_highlighted_context()
        context_html = ""
        if date_tag.line_text:  # New explicit field from parser v0.0.22+
            # Use PageTag's built-in method for clean KWIC display
            highlighted_text = date_tag.get_highlighted_context(context_chars=100)

            # Generate URLs
            document_url = reverse(
                "twf:view_document", args=[date_tag.page.document.pk]
            )
            transkribus_url = date_tag.get_transkribus_url()
            document_title = (
                date_tag.page.document.title or date_tag.page.document.document_id
            )

            context_html = f"""
            <div class="mt-3 p-2 bg-light border rounded">
                <p class="small mb-1 text-muted"><i class="fa fa-quote-left me-2"></i>
                Context from document:</p>
                <p class="mb-0 small">{highlighted_text}</p>
                <p class="small text-muted mb-0 mt-1">
                    <i class="fa fa-file-text me-1"></i>Page {date_tag.page.tk_page_number}
                    | <i class="fa fa-book me-1"></i><a href="{document_url}" 
                    class="text-decoration-none">{document_title}</a>
                    | <a href="{transkribus_url}" target="_blank" 
                    class="text-decoration-none" title="Open in Transkribus">
                    <i class="fa fa-external-link me-1"></i>Transkribus</a>
                </p>
            </div>"""

        # Generate park URL
        park_url = reverse("twf:tags_park", args=[date_tag.pk])

        input_string_html = f"""
        <div class="col-12 border text-center" style="background-color: khaki">
            <p class="text-center" style="color: #7c7c7c">Try to normalize:
                <a href="{park_url}" class="btn btn-secondary float-end">Park</a>
            </p>
            <p class="display-6 text-center">{ date_tag.variation }</p>
            {context_html}
        </div>"""

        self.helper.layout.append(
            Field(
                "date_tag", type="hidden"
            )  # Ensures `date_tag` is included in the form as a hidden input
        )

        self.helper.layout.append(
            Row(
                Column("input_date_format", css_class="form-group col-6 mb-3"),
                Column("resolve_to", css_class="form-group col-6 mb-3"),
                css_class="row form-row",
            )
        )

        self.helper.layout.append(
            Row(HTML(input_string_html), css_class="row form-row")
        )

        self.helper.layout.append(
            Row(
                Column("resulting_date", css_class="form-group col-12 mb-3"),
                css_class="row form-row",
            )
        )

        self.helper.layout.append(
            Div(
                Submit("submit", "Accept & Next", css_class="btn btn-dark"),
                css_class="text-end pt-3",
            )
        )
