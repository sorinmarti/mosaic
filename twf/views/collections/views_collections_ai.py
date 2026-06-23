"""Views for AI collection processing."""

import json
from django.urls import reverse_lazy

from twf.forms.collections.collections_forms_batches import (
    UnifiedCollectionAIBatchForm,
    UnifiedCollectionAIRequestForm,
)
from twf.views.collections.views_collections import TWFCollectionsView
from twf.views.views_base import AIFormView, ProjectPermissionMixin


class TWFUnifiedCollectionAIBatchView(ProjectPermissionMixin, AIFormView, TWFCollectionsView):
    """
    Unified view for AI batch processing of collections.

    This view provides a single interface for batch processing with all supported
    AI providers. The provider is selected via a dropdown in the form.
    """

    required_permission = "ai.manage"
    template_name = "twf/base/base_ai_batch.html"
    page_title = "AI Batch Processing"
    form_class = UnifiedCollectionAIBatchForm
    success_url = reverse_lazy("twf:collections_batch_ai_unified")
    message = "Do you want to start the AI batch process now?"

    # Provider configuration (only 4 providers for collections)
    PROVIDER_CONFIG = {
        "openai": {
            "label": "OpenAI (ChatGPT)",
            "credentials_key": "openai",
            "credentials_tab": "openai",
            "description": "OpenAI will process collection items using ChatGPT models.",
        },
        "genai": {
            "label": "Google Gemini",
            "credentials_key": "genai",
            "credentials_tab": "genai",
            "description": "Gemini will process collection items.",
        },
        "anthropic": {
            "label": "Anthropic Claude",
            "credentials_key": "anthropic",
            "credentials_tab": "anthropic",
            "description": "Claude will process collection items.",
        },
        "mistral": {
            "label": "Mistral",
            "credentials_key": "mistral",
            "credentials_tab": "mistral",
            "description": "Mistral will process collection items.",
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
        kwargs["data-start-url"] = reverse_lazy("twf:task_collections_batch_unified")
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
            context["ai_heading"] = f"{provider_info['label']} Collection Batch"
            context["ai_lead"] = provider_info["description"]
            creds = self.get_ai_credentials(provider_info["credentials_key"])
            has_api_key = creds and "api_key" in creds and creds["api_key"]
            context["has_api_key"] = has_api_key
            context["ai_credentials_url"] = (
                reverse_lazy("twf:project_ai_configs")
                + f"?tab={provider_info['credentials_tab']}"
            )
        else:
            # Fallback defaults
            context["ai_heading"] = self.page_title
            context["ai_lead"] = "AI will process collection items."
            context["has_api_key"] = False
            context["ai_credentials_url"] = reverse_lazy(
                "twf:project_ai_configs"
            )

        # Build provider config for JavaScript with credentials check
        provider_config_for_js = {}
        for provider_key, provider_info in self.PROVIDER_CONFIG.items():
            creds = self.get_ai_credentials(provider_info["credentials_key"])
            has_api_key = creds and "api_key" in creds and creds["api_key"]
            default_model = creds.get("default_model", "") if creds else ""

            provider_config_for_js[provider_key] = {
                "label": provider_info["label"],
                "description": provider_info["description"],
                "multimodal": False,  # Collections don't support multimodal
                "multimodal_info": "",
                "credentials_url": str(reverse_lazy("twf:project_ai_configs"))
                + f"?tab={provider_info['credentials_tab']}",
                "has_api_key": has_api_key,
                "default_model": default_model,
            }
        context["provider_config_json"] = json.dumps(provider_config_for_js)

        return context


class TWFUnifiedCollectionAIRequestView(ProjectPermissionMixin, AIFormView, TWFCollectionsView):
    """
    Unified view for AI request (supervised) processing of collection items.

    This view provides a single interface for supervised, single-item processing
    with all supported AI providers. The provider is selected via a dropdown in the form.
    """

    required_permission = "collection.edit"
    template_name = "twf/base/base_ai_batch.html"
    page_title = "AI Request"
    form_class = UnifiedCollectionAIRequestForm
    success_url = reverse_lazy("twf:collections_request_ai_unified")
    message = "Do you want to send this AI request now?"

    # Provider configuration (same 4 providers)
    PROVIDER_CONFIG = {
        "openai": {
            "label": "OpenAI (ChatGPT)",
            "credentials_key": "openai",
            "credentials_tab": "openai",
            "description": "OpenAI will process this collection item using ChatGPT models.",
        },
        "genai": {
            "label": "Google Gemini",
            "credentials_key": "genai",
            "credentials_tab": "genai",
            "description": "Gemini will process this collection item.",
        },
        "anthropic": {
            "label": "Anthropic Claude",
            "credentials_key": "anthropic",
            "credentials_tab": "anthropic",
            "description": "Claude will process this collection item.",
        },
        "mistral": {
            "label": "Mistral",
            "credentials_key": "mistral",
            "credentials_tab": "mistral",
            "description": "Mistral will process this collection item.",
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
        kwargs["data-start-url"] = reverse_lazy("twf:task_collections_request_unified")
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
            context["ai_heading"] = f"{provider_info['label']} Collection Request"
            context["ai_lead"] = provider_info["description"]
            creds = self.get_ai_credentials(provider_info["credentials_key"])
            has_api_key = creds and "api_key" in creds and creds["api_key"]
            context["has_api_key"] = has_api_key
            context["ai_credentials_url"] = (
                reverse_lazy("twf:project_ai_configs")
                + f"?tab={provider_info['credentials_tab']}"
            )
        else:
            # Fallback defaults
            context["ai_heading"] = self.page_title
            context["ai_lead"] = "AI will process this collection item."
            context["has_api_key"] = False
            context["ai_credentials_url"] = reverse_lazy(
                "twf:project_ai_configs"
            )

        # Build provider config for JavaScript with credentials check
        provider_config_for_js = {}
        for provider_key, provider_info in self.PROVIDER_CONFIG.items():
            creds = self.get_ai_credentials(provider_info["credentials_key"])
            has_api_key = creds and "api_key" in creds and creds["api_key"]
            default_model = creds.get("default_model", "") if creds else ""

            provider_config_for_js[provider_key] = {
                "label": provider_info["label"],
                "description": provider_info["description"],
                "multimodal": False,  # Collections don't support multimodal
                "multimodal_info": "",
                "credentials_url": str(reverse_lazy("twf:project_ai_configs"))
                + f"?tab={provider_info['credentials_tab']}",
                "has_api_key": has_api_key,
                "default_model": default_model,
            }
        context["provider_config_json"] = json.dumps(provider_config_for_js)

        return context
