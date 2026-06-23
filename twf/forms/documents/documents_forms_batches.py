"""Forms for creating and updating documents."""

from crispy_forms.layout import Row, Column
from django import forms

from twf.forms.base_batch_forms import BaseMultiModalAIBatchForm


class DocumentBatchAIForm(BaseMultiModalAIBatchForm):
    """Form for running a batch of documents through OpenAI."""

    REQUEST_LEVEL_CHOICES = [("document", "Document"), ("page", "Page")]

    def __init__(self, *args, **kwargs):
        """Initialize the form."""
        super().__init__(*args, **kwargs)
        self.fields["request_level"] = forms.ChoiceField(
            label="Request Level",
            choices=self.REQUEST_LEVEL_CHOICES,
            initial="document",
            help_text="Select the level of detail for the request.",
        )

    def get_dynamic_fields(self):
        fields = super().get_dynamic_fields()
        fields.append(
            Row(
                Column("request_level", css_class="form-group col-12 mb-0"),
                css_class="row form-row",
            )
        )
        return fields


class UnifiedDocumentBatchAIForm(DocumentBatchAIForm):
    """
    Unified form for batch processing documents with AI configurations.

    This form uses AIConfiguration objects which contain all settings
    (provider, model, prompt, role, etc.). The form only needs to select
    which configuration to use and document-specific options.
    """

    def get_button_label(self):
        """
        Get the label for the submit button.

        Returns:
            str: The button label.
        """
        return "Run AI Batch"
