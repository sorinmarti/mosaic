"""Views for AI document processing."""

import json
from django.urls import reverse_lazy

from twf.forms.documents.documents_forms_batches import UnifiedDocumentBatchAIForm
from twf.views.documents.views_documents import TWFDocumentView
from twf.views.views_base import AIFormView, ProjectPermissionMixin


class TWFUnifiedDocumentBatchView(ProjectPermissionMixin, AIFormView, TWFDocumentView):
    """
    Unified view for batch processing documents with any AI provider.

    This view provides a single interface for batch processing with all supported
    AI providers. The provider is selected via a dropdown in the form.
    """

    required_permission = "ai.manage"
    template_name = "twf/base/base_ai_batch.html"
    page_title = "AI Batch Processing"
    form_class = UnifiedDocumentBatchAIForm
    success_url = reverse_lazy("twf:documents_batch_ai_unified")
    message = "Do you want to start the AI batch process now?"

    # Provider configuration
    PROVIDER_CONFIG = {
        "openai": {
            "label": "OpenAI (ChatGPT)",
            "credentials_key": "openai",
            "credentials_tab": "openai",
            "multimodal": True,
            "description": "ChatGPT will generate a separate response for each document by "
                           "combining your prompt with its content.",
            "multimodal_info": "The default ChatGPT-4o model supports text-only, "
                               "image-only, and text+image modes.",
        },
        "genai": {
            "label": "Google Gemini",
            "credentials_key": "genai",
            "credentials_tab": "genai",
            "multimodal": True,
            "description": "Gemini will generate a separate response for each document "
                           "by combining your prompt with its content.",
            "multimodal_info": "Gemini supports text-only, image-only, and text+image modes.",
        },
        "anthropic": {
            "label": "Anthropic Claude",
            "credentials_key": "anthropic",
            "credentials_tab": "anthropic",
            "multimodal": True,
            "description": "Claude will generate a separate response for each document "
                           "by combining your prompt with its content.",
            "multimodal_info": "Claude supports text-only, image-only, and text+image modes.",
        },
        "mistral": {
            "label": "Mistral",
            "credentials_key": "mistral",
            "credentials_tab": "mistral",
            "multimodal": False,
            "description": "Mistral will generate text based on the provided prompt "
                           "expanded with the document text.",
            "multimodal_info": "Mistral currently supports text-only processing.",
        },
        "deepseek": {
            "label": "DeepSeek",
            "credentials_key": "deepseek",
            "credentials_tab": "deepseek",
            "multimodal": True,
            "description": "DeepSeek will generate text based on the provided prompt "
                           "expanded with the document text.",
            "multimodal_info": "DeepSeek supports text-only, image-only, and text+image modes.",
        },
        "qwen": {
            "label": "Qwen",
            "credentials_key": "qwen",
            "credentials_tab": "qwen",
            "multimodal": True,
            "description": "Qwen will generate text based on the provided prompt expanded "
                           "with the document text.",
            "multimodal_info": "Qwen supports text-only, image-only, and text+image modes.",
        },
    }

    def get_form_kwargs(self):
        """
        Get the form kwargs with project and unified task URL.

        Returns:
            dict: Form kwargs.
        """
        kwargs = super().get_form_kwargs()

        # Use the unified task trigger URL
        kwargs["data-start-url"] = reverse_lazy("twf:task_documents_batch_unified")
        kwargs["data-message"] = self.message

        return kwargs

    def get_context_data(self, **kwargs):
        """
        Get the context data for the template.

        This method adds provider-specific context data dynamically based on
        the selected provider in the form.

        Args:
            **kwargs: Arbitrary keyword arguments.

        Returns:
            dict: The context data.
        """
        context = super().get_context_data(**kwargs)

        # Get selected provider from form data or default to openai
        provider = "openai"
        if self.request.method == "POST":
            provider = self.request.POST.get("ai_provider", "openai")
        elif self.request.method == "GET" and "ai_provider" in self.request.GET:
            provider = self.request.GET.get("ai_provider", "openai")

        # Set context based on provider
        if provider in self.PROVIDER_CONFIG:
            provider_info = self.PROVIDER_CONFIG[provider]
            creds = self.get_ai_credentials(provider_info["credentials_key"])
            has_api_key = creds and "api_key" in creds and creds["api_key"]

            context["ai_heading"] = f"{provider_info['label']} Document Batch"
            context["ai_lead"] = provider_info["description"]
            context["has_api_key"] = has_api_key
            context["ai_credentials_url"] = (
                reverse_lazy("twf:project_ai_configs")
                + f"?tab={provider_info['credentials_tab']}"
            )
            context["supports_multimodal"] = provider_info["multimodal"]
            context["multimodal_info"] = provider_info["multimodal_info"]
        else:
            # Fallback defaults
            context["ai_heading"] = self.page_title
            context["ai_lead"] = (
                "AI will generate a separate response for each document."
            )
            context["has_api_key"] = False
            context["ai_credentials_url"] = reverse_lazy(
                "twf:project_ai_configs"
            )
            context["supports_multimodal"] = True
            context["multimodal_info"] = "Multimodal support varies by provider."

        # Build provider config for JavaScript with credentials check
        provider_config_for_js = {}
        for provider_key, provider_info in self.PROVIDER_CONFIG.items():
            creds = self.get_ai_credentials(provider_info["credentials_key"])
            has_api_key = creds and "api_key" in creds and creds["api_key"]
            default_model = creds.get("default_model", "") if creds else ""

            provider_config_for_js[provider_key] = {
                "label": provider_info["label"],
                "description": provider_info["description"],
                "multimodal": provider_info["multimodal"],
                "multimodal_info": provider_info["multimodal_info"],
                "credentials_url": str(reverse_lazy("twf:project_ai_configs"))
                + f"?tab={provider_info['credentials_tab']}",
                "has_api_key": has_api_key,
                "default_model": default_model,
            }
        context["provider_config_json"] = json.dumps(provider_config_for_js)

        return context
