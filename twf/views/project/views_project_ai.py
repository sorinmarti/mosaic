"""
Views for AI model interactions.

This module contains the unified view for interacting with various AI providers,
including OpenAI, Google Gemini, Anthropic Claude, Mistral, DeepSeek, and Qwen.
The unified view supports both text-only and multimodal (text + images) interactions.
"""

import json
from django.urls import reverse_lazy

from twf.forms.project.project_forms_batches import UnifiedAIQueryForm
from twf.views.project.views_project import TWFProjectView
from twf.views.views_base import AIFormView, ProjectPermissionMixin


class TWFUnifiedAIQueryView(ProjectPermissionMixin, AIFormView, TWFProjectView):
    """
    Unified view for querying any AI provider.

    This view provides a single interface for querying all supported AI providers.
    The provider is selected via a dropdown in the form, and the view dynamically
    handles credentials, task routing, and context based on the selected provider.
    """

    required_permission = "ai.edit"
    template_name = "twf/project/query/ai.html"
    page_title = "Ask AI"
    form_class = UnifiedAIQueryForm
    success_url = reverse_lazy("twf:project_ai_query_unified")
    message = "Do you want to proceed with this AI query?"

    # Provider configuration matching the form
    PROVIDER_CONFIG = {
        "openai": {
            "label": "OpenAI (ChatGPT)",
            "task_url": "twf:task_project_query_openai",
            "credentials_key": "openai",
            "credentials_tab": "openai",
            "multimodal": True,
            "description": "Use OpenAI's ChatGPT models to answer questions about your documents.",
            "multimodal_info": "The default ChatGPT-4o model supports text-only, image-only, and text+image modes.",
        },
        "genai": {
            "label": "Google Gemini",
            "task_url": "twf:task_project_query_gemini",
            "credentials_key": "genai",
            "credentials_tab": "genai",
            "multimodal": True,
            "description": "Query Google Gemini models for predictions. "
                           "All current Gemini models support multimodal input "
                           "with both text and images.",
            "multimodal_info": "Supports text-only, images-only, or text+images modes. "
                               "All Gemini models support images.",
        },
        "anthropic": {
            "label": "Anthropic Claude",
            "task_url": "twf:task_project_query_claude",
            "credentials_key": "anthropic",
            "credentials_tab": "anthropic",
            "multimodal": True,
            "description": "Query Anthropic Claude models for analysis and predictions.",
            "multimodal_info": "Claude 3 models support text and image inputs.",
        },
        "mistral": {
            "label": "Mistral",
            "task_url": "twf:task_project_query_mistral",
            "credentials_key": "mistral",
            "credentials_tab": "mistral",
            "multimodal": False,
            "description": "Query Mistral AI models for predictions.",
            "multimodal_info": "Mistral currently supports text-only queries.",
        },
        "deepseek": {
            "label": "DeepSeek",
            "task_url": "twf:task_project_query_deepseek",
            "credentials_key": "deepseek",
            "credentials_tab": "deepseek",
            "multimodal": True,
            "description": "Query DeepSeek models for predictions.",
            "multimodal_info": "DeepSeek supports text-only, image-only, and text+image modes.",
        },
        "qwen": {
            "label": "Qwen",
            "task_url": "twf:task_project_query_qwen",
            "credentials_key": "qwen",
            "credentials_tab": "qwen",
            "multimodal": True,
            "description": "Query Qwen models for predictions.",
            "multimodal_info": "Qwen supports text-only, image-only, and text+image modes.",
        },
    }

    def get_form_kwargs(self):
        """
        Get the form kwargs with project and unified task URL.

        The unified task URL will dispatch to the correct provider based on
        the ai_provider parameter in the form data.

        Returns:
            dict: Form kwargs.
        """
        kwargs = super().get_form_kwargs()

        # Use the unified task trigger URL
        # The trigger will dispatch to the correct provider based on form data
        kwargs["data-start-url"] = reverse_lazy("twf:task_project_query_unified")
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

            context["ai_heading"] = f"{self.page_title} - {provider_info['label']}"
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
                "Query AI models to answer questions about your documents."
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
