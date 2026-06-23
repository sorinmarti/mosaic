"""Forms for managing metadata blocks."""

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Div, Submit
from django import forms
from twf.models import Document, Page


class MetadataManagementForm(forms.Form):
    """Form for managing (deleting) metadata blocks from documents and pages."""

    target_type = forms.ChoiceField(
        label="Target Type",
        choices=[("document", "Documents"), ("page", "Pages")],
        required=True,
        widget=forms.Select(attrs={"class": "form-control"}),
        help_text="Select whether to manage document or page metadata.",
    )

    metadata_key = forms.ChoiceField(
        label="Metadata Block",
        required=True,
        widget=forms.Select(attrs={"class": "form-control"}),
        help_text="Select the metadata block (key) to delete. "
                  "This will remove the entire block from all documents/pages.",
    )

    def __init__(self, *args, project=None, **kwargs):
        if not project:
            raise ValueError("Project is required.")

        super().__init__(*args, **kwargs)
        self.project = project

        # Get available metadata keys based on target_type
        # Default to document keys initially
        doc_keys = Document.get_distinct_metadata_keys()
        page_keys = Page.get_distinct_metadata_keys()

        # Combine and deduplicate for initial display
        all_keys = sorted(set(doc_keys + page_keys))

        if all_keys:
            self.fields["metadata_key"].choices = [(key, key) for key in all_keys]
        else:
            self.fields["metadata_key"].choices = [("", "No metadata blocks found")]
            self.fields["metadata_key"].disabled = True

        # Setup crispy forms
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_id = "metadata-delete-form"
        self.helper.layout = Layout(
            Row(
                Column("target_type", css_class="form-group col-md-6 mb-3"),
                Column("metadata_key", css_class="form-group col-md-6 mb-3"),
                css_class="row",
            ),
            Div(
                Submit(
                    'delete_block',
                    'Delete Metadata Block',
                    css_class='btn btn-danger show-danger-modal',
                    css_id='delete-metadata-btn',
                    data_message='Are you sure you want to delete this metadata block? This will permanently remove it from all documents/pages and cannot be undone.'
                ),
                css_class="text-end",
            ),
        )

    def clean(self):
        """Validate the form."""
        cleaned_data = super().clean()
        target_type = cleaned_data.get("target_type")
        metadata_key = cleaned_data.get("metadata_key")

        if target_type and metadata_key:
            # Verify the key exists for the target type
            if target_type == "document":
                keys = Document.get_distinct_metadata_keys()
            else:
                keys = Page.get_distinct_metadata_keys()

            if metadata_key not in keys:
                raise forms.ValidationError(
                    f"The metadata key '{metadata_key}' does not exist in {target_type}s."
                )

        return cleaned_data

    def save(self, user):
        """Delete the specified metadata block from all documents or pages."""
        target_type = self.cleaned_data["target_type"]
        metadata_key = self.cleaned_data["metadata_key"]

        deleted_count = 0

        if target_type == "document":
            # Delete from all documents in project
            documents = Document.objects.filter(project=self.project)
            for doc in documents:
                if metadata_key in doc.metadata:
                    del doc.metadata[metadata_key]
                    doc.save(current_user=user)
                    deleted_count += 1

        else:  # page
            # Delete from all pages in project
            pages = Page.objects.filter(document__project=self.project)
            for page in pages:
                if metadata_key in page.metadata:
                    del page.metadata[metadata_key]
                    page.save(current_user=user)
                    deleted_count += 1

        return deleted_count
