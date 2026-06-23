from twf.forms.base_batch_forms import BaseBatchForm


class TagsExtractionBatchForm(BaseBatchForm):
    """Base form for batches of dictionaries."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_button_label(self):
        """Get the label for the submit button."""
        return "Extract Tags From Transkribus Export"

    def get_dynamic_fields(self):
        """Get the dynamic fields for the form."""
        return []
