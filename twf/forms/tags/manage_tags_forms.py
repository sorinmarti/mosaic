"""Forms for bulk tag management operations."""

from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Div, HTML
from twf.models import PageTag


class ManageTagsForm(forms.Form):
    """Form for bulk tag management operations."""

    tag_type = forms.ChoiceField(
        label="Tag Type",
        required=True,
        help_text="Select the tag type you want to perform operations on.",
    )

    action = forms.ChoiceField(
        label="Action",
        required=True,
        choices=[
            ("", "--- Select an action ---"),
            ("unpark", "Unpark all tags of this type"),
            ("remove_dict", "Remove dictionary assignments for this type"),
            ("remove_enrichment", "Remove enrichment data for this type"),
        ],
        help_text="Choose the bulk operation to perform on the selected tag type.",
    )

    confirm = forms.BooleanField(
        label="I understand this action cannot be undone",
        required=True,
        help_text="Check this box to confirm the bulk operation.",
    )

    def __init__(self, *args, **kwargs):
        project = kwargs.pop("project", None)
        super().__init__(*args, **kwargs)

        # Populate tag types from the project
        if project:
            tag_types = (
                PageTag.objects.filter(page__document__project=project)
                .values_list("variation_type", flat=True)
                .distinct()
                .order_by("variation_type")
            )
            choices = [("", "--- Select a tag type ---")] + [
                (tag_type, tag_type) for tag_type in tag_types
            ]
            self.fields["tag_type"].choices = choices

        # Setup form helper
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            Div(
                HTML(
                    '<div class="alert alert-warning">'
                    '<i class="fas fa-exclamation-triangle"></i> '
                    '<strong>Warning:</strong> These operations affect multiple tags at once and cannot be undone. '
                    'Please ensure you have selected the correct tag type and action before proceeding.'
                    '</div>'
                ),
                "tag_type",
                "action",
                "confirm",
                Div(
                    Submit("submit", "Execute Operation", css_class="btn-danger"),
                    css_class="mt-3",
                ),
            )
        )