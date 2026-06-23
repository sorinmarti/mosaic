"""
Base forms for batch processing in TWF.

This module contains the base form classes used for various batch processing operations,
including AI interactions with both text-only and multimodal (text + images) capabilities.
"""

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, HTML, Div, Button
from django import forms


class BaseBatchForm(forms.Form):
    """
    Base form for batch processing operations.

    This abstract class provides the foundation for all batch processing forms in TWF,
    including progress tracking, task control, and consistent UI elements.
    """

    project = None
    task_data = {}
    progress_details = forms.CharField(label="Progress", required=False)

    def __init__(self, *args, **kwargs):
        """
        Initialize the batch form.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
                project: The project instance (required).
                data-start-url: The URL to start the task.
                data-message: Confirmation message when starting the task.
                data-progress-url-base: Base URL for progress updates.
                data-progress-bar-id: ID of the progress bar element.
                data-log-textarea-id: ID of the log textarea element.

        Raises:
            ValueError: If project is not provided.
        """
        self.project = kwargs.pop("project", None)

        self.task_data["data-start-url"] = kwargs.pop("data-start-url", None)
        self.task_data["data-message"] = kwargs.pop(
            "data-message", "Are you sure you want to start the task?"
        )
        self.task_data["data-progress-url-base"] = kwargs.pop(
            "data-progress-url-base", "/celery/status/"
        )
        self.task_data["data-progress-bar-id"] = kwargs.pop(
            "data-progress-bar-id", "#taskProgressBar"
        )
        self.task_data["data-log-textarea-id"] = kwargs.pop(
            "data-log-textarea-id", "#id_progress_details"
        )

        super().__init__(*args, **kwargs)

        if self.project is None:
            raise ValueError("Project must be provided.")

        progress_bar_html = """
        <div class="col-12 border text-center">
          <span>Progress:</span>
          <div class="progress">
            <div class="progress-bar bg-dark" role="progressbar" 
                 style="width: 0;" id="taskProgressBar" aria-valuenow="0" 
                 aria-valuemin="0" aria-valuemax="100">0%</div>
            </div>
        </div>"""

        self.fields["progress_details"].widget = forms.Textarea()
        self.fields["progress_details"].widget.attrs = {"readonly": True, "rows": 5}

        self.helper = FormHelper()
        self.helper.form_method = "post"

        button_kwargs = {
            "css_class": "btn btn-dark show-confirm-modal",
            "data_message": self.task_data.get("data-message"),
            "data_start_url": self.task_data.get("data-start-url"),
            "data_progress_url_base": self.task_data.get("data-progress-url-base"),
            "data_progress_bar_id": self.task_data.get("data-progress-bar-id"),
            "data_log_textarea_id": self.task_data.get("data-log-textarea-id"),
        }

        cancel_kwargs = {
            "css_class": "btn btn-danger show-danger-modal",
            "data_message": "Are you sure you want to cancel the task?",
            "disabled": "disabled",
        }

        # Filter out None or empty values
        filtered_kwargs = {key: value for key, value in button_kwargs.items() if value}

        self.helper.layout = Layout(
            *self.get_dynamic_fields() or [],
            HTML(progress_bar_html),
            Row(
                Column("progress_details", css_class="form-group col-12 mb-0"),
                css_class="row form-row",
            ),
            Div(
                Button("cancelBatch", self.get_cancel_button_label(), **cancel_kwargs),
                Button("startBatch", self.get_button_label(), **filtered_kwargs),
                css_class="text-end pt-3",
            )
        )

    def get_button_label(self):
        """
        Get the label for the submit button.

        Returns:
            str: The button label.
        """
        return "Start Batch"

    def get_cancel_button_label(self):
        """
        Get the label for the cancel button.

        Returns:
            str: The cancel button label.
        """
        return "Cancel"

    def get_dynamic_fields(self):
        """
        Get the dynamic fields for the form.

        This method should be overridden by subclasses to add form-specific fields.

        Returns:
            list: A list of form field layouts.
        """
        return []


class BaseAIBatchForm(BaseBatchForm):
    """
    Base form for AI batch operations.

    This class extends the base batch form with AI configuration selection.
    All AI settings (provider, model, prompt, role, etc.) are stored in the
    selected AIConfiguration object.
    """

    class Meta:
        js = ("twf/js/ai_prompt_manager.js",)

    def __init__(self, *args, **kwargs):
        """
        Initialize the AI batch form.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        super().__init__(*args, **kwargs)

        # Import here to avoid circular imports
        from twf.models import AIConfiguration

        self.fields["ai_configuration"] = forms.ModelChoiceField(
            queryset=AIConfiguration.objects.filter(project=self.project),
            required=True,
            label="AI Configuration",
            help_text="Select an AI configuration. All settings (provider, model, prompt, etc.) are defined in the configuration.",
            empty_label="(Select AI Configuration...)"
        )

    def get_dynamic_fields(self):
        """
        Get the dynamic fields for the AI form.

        Returns:
            list: A list of form field layouts including AI-specific fields.
        """
        manage_button_html = """
         <div class="text-end mb-3">
            <a href="{% url 'twf:project_ai_configs' %}" class="btn btn-sm btn-dark" target="_blank"
             data-bs-toggle="tooltip" title="Open AI Configurations page to create or edit configurations">
             <i class="fa fa-gear"></i> Manage AI Configs</a>
        </div>"""

        preview_html = """
        <div id="ai-config-preview" class="card mb-3" style="display: none;">
            <div class="card-header bg-light">
                <strong>Configuration Preview</strong>
            </div>
            <div class="card-body">
                <div class="row">
                    <div class="col-md-6">
                        <p class="mb-1"><strong>Provider:</strong> <span id="preview-provider"></span></p>
                        <p class="mb-1"><strong>Model:</strong> <span id="preview-model"></span></p>
                    </div>
                    <div class="col-md-6">
                        <p class="mb-1"><strong>Temperature:</strong> <span id="preview-temperature"></span></p>
                        <p class="mb-1"><strong>Max Tokens:</strong> <span id="preview-max-tokens"></span></p>
                    </div>
                </div>
                <hr>
                <p class="mb-1"><strong>System Role:</strong></p>
                <p class="text-muted small" id="preview-role"></p>
                <p class="mb-1"><strong>Prompt Template:</strong></p>
                <p class="text-muted small" id="preview-prompt"></p>
            </div>
        </div>"""

        fields = super().get_dynamic_fields() or []

        # Add manage button
        fields.append(HTML(manage_button_html))

        # Add AI Configuration selector
        fields.append(
            Row(
                Column("ai_configuration", css_class="form-group col-12 mb-0"),
                css_class="row form-row",
            )
        )

        # Add preview area
        fields.append(HTML(preview_html))

        return fields


class BaseMultiModalAIBatchForm(BaseAIBatchForm):
    """
    Base form for AI batches with multimodal capabilities.

    This class extends the AI batch form with additional fields and functionality
    to support multimodal (text + images) interactions with AI providers.
    """

    class Meta:
        js = ("twf/js/ai_prompt_manager.js",)

    # Mode choices for the prompt type
    PROMPT_MODE_CHOICES = [
        ("text_only", "Text only"),
        ("images_only", "Images only"),
        ("text_and_images", "Text + Images"),
    ]

    def __init__(self, *args, **kwargs):
        """
        Initialize the multimodal AI batch form.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
                multimodal_support (bool): Whether this form should include multimodal fields.
                                           Defaults to True.
        """
        # Get the multimodal_support parameter and remove it from kwargs
        self.multimodal_support = kwargs.pop("multimodal_support", True)

        super().__init__(*args, **kwargs)

        if self.multimodal_support:
            # Add prompt mode selector
            self.fields["prompt_mode"] = forms.ChoiceField(
                label="Sending Mode",
                choices=self.PROMPT_MODE_CHOICES,
                initial="text_only",
                required=True,
                help_text="Select how to send the prompt to the AI model",
            )

            # Note: We no longer need a separate image_pages field since
            # we'll automatically select up to 5 images per document

    def get_dynamic_fields(self):
        """
        Get the dynamic fields for the form including multimodal fields if supported.

        Returns:
            list: A list of form field layouts including multimodal-specific fields if supported.
        """
        fields = super().get_dynamic_fields()

        if self.multimodal_support:
            # Add the mode selector
            fields.append(
                Row(
                    Column("prompt_mode", css_class="form-group col-12 mb-0"),
                    css_class="row form-row",
                )
            )

            # Add the fixed message about image limits
            image_info_html = """
            <div class="multimodal-info alert alert-info mt-2" style="display: none;">
                <small>
                    <i class="fas fa-info-circle"></i>
                    Up to 5 images per document will be included in the request (first 5 pages only).
                </small>
            </div>
            """

            fields.append(HTML(image_info_html))

            # Add JavaScript to show/hide the message based on mode selection
            modal_script = """
            <script>
                document.addEventListener('DOMContentLoaded', function() {
                    const modeSelector = document.getElementById('id_prompt_mode');
                    const infoMessage = document.querySelector('.multimodal-info');
                    
                    function toggleInfoMessage() {
                        // Show message for any mode that includes images
                        const showMessage = modeSelector.value !== 'text_only';
                        infoMessage.style.display = showMessage ? 'block' : 'none';
                    }
                    
                    // Initial state
                    toggleInfoMessage();
                    
                    // Toggle on change
                    modeSelector.addEventListener('change', toggleInfoMessage);
                });
            </script>
            """

            fields.append(HTML(modal_script))

        return fields
