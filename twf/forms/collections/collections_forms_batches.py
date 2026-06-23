from crispy_forms.layout import Row, Column
from django import forms

from twf.forms.base_batch_forms import BaseAIBatchForm
from twf.models import Collection


class CollectionBatchForm(BaseAIBatchForm):
    """Form for batch processing Geonames data."""

    collection = forms.ModelChoiceField(
        queryset=Collection.objects.none(),
        label="Collection",
        required=True,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["collection"].choices = [("", "Select a Collection")] + [
            (c.pk, c.title) for c in Collection.objects.filter(project=self.project)
        ]

    def get_dynamic_fields(self):
        """Get the dynamic fields for the form."""
        return super().get_dynamic_fields() + [
            Row(
                Column("collection", css_class="form-group col-12 mb-3"),
                css_class="row form-row",
            )
        ]

    def get_button_label(self):
        """Get the label for the submit button."""
        return "Start Batch"


class UnifiedCollectionAIBatchForm(CollectionBatchForm):
    """
    Unified form for AI batch processing of collections.

    Uses AIConfiguration objects which contain all settings
    (provider, model, prompt, role, etc.). The form only selects
    which configuration to use and collection-specific options.
    """

    def get_button_label(self):
        """
        Get the label for the submit button.

        Returns:
            str: The button label.
        """
        return "Start AI Batch"


class UnifiedCollectionAIRequestForm(CollectionBatchForm):
    """
    Unified form for AI request (supervised) processing of collection items.

    Uses AIConfiguration objects which contain all settings
    (provider, model, prompt, role, etc.). The form only selects
    which configuration to use and collection-specific options.
    """

    def get_button_label(self):
        """
        Get the label for the submit button.

        Returns:
            str: The button label.
        """
        return "Send AI Request"
