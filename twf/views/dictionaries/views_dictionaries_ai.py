"""Dictionaries Batch Views."""

import json
from django.urls import reverse_lazy
from django.views.generic import FormView

from twf.forms.dictionaries.dictionaries_forms_batches import (
    GeonamesBatchForm,
    GNDBatchForm,
    WikidataBatchForm,
    UnifiedDictionaryAIBatchForm,
    UnifiedDictionaryAIRequestForm,
)
from twf.views.dictionaries.views_dictionaries import TWFDictionaryView
from twf.views.views_base import AIFormView, ProjectPermissionMixin


class TWFDictionaryGeonamesBatchView(ProjectPermissionMixin, FormView, TWFDictionaryView):
    """Normalization Data Wizard."""
    required_permission = "dictionary.manage"

    template_name = "twf/dictionaries/batches/geonames.html"
    page_title = "Geonames Batch"
    form_class = GeonamesBatchForm
    success_url = reverse_lazy("twf:dictionaries_batch_geonames")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["project"] = self.get_project()

        kwargs["data-start-url"] = reverse_lazy("twf:task_dictionaries_batch_geonames")
        kwargs["data-message"] = "Are you sure you want to start the geonames task?"

        return kwargs


class TWFDictionaryGNDBatchView(ProjectPermissionMixin, FormView, TWFDictionaryView):
    """Normalization Data Wizard."""
    required_permission = "dictionary.manage"

    template_name = "twf/dictionaries/batches/gnd.html"
    page_title = "GND Batch"
    form_class = GNDBatchForm
    success_url = reverse_lazy("twf:dictionaries_batch_gnd")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["project"] = self.get_project()

        kwargs["data-start-url"] = reverse_lazy("twf:task_dictionaries_batch_gnd")
        kwargs["data-message"] = "Are you sure you want to start the gnd task?"

        return kwargs


class TWFDictionaryWikidataBatchView(ProjectPermissionMixin, FormView, TWFDictionaryView):
    """Normalization Data Wizard."""
    required_permission = "dictionary.manage"

    template_name = "twf/dictionaries/batches/wikidata.html"
    page_title = "Wikidata Batch"
    form_class = WikidataBatchForm
    success_url = reverse_lazy("twf:dictionaries_batch_wikidata")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["project"] = self.get_project()

        kwargs["data-start-url"] = reverse_lazy("twf:task_dictionaries_batch_wikidata")
        kwargs["data-message"] = "Are you sure you want to start the wikidata task?"

        return kwargs


class TWFDictionaryGeonamesRequestView(ProjectPermissionMixin, FormView, TWFDictionaryView):
    """Normalization Data Wizard."""
    required_permission = "dictionary.edit"

    template_name = "twf/dictionaries/requests/geonames.html"
    page_title = "Geonames Request"
    form_class = GeonamesBatchForm
    success_url = reverse_lazy("twf:dictionaries_request_geonames")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["project"] = self.get_project()
        return kwargs


class TWFDictionaryGNDRequestView(ProjectPermissionMixin, FormView, TWFDictionaryView):
    """Normalization Data Wizard."""
    required_permission = "dictionary.edit"

    template_name = "twf/dictionaries/requests/gnd.html"
    page_title = "GND Request"
    form_class = GNDBatchForm
    success_url = reverse_lazy("twf:dictionaries_request_gnd")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["project"] = self.get_project()
        return kwargs


class TWFDictionaryWikidataRequestView(ProjectPermissionMixin, FormView, TWFDictionaryView):
    """Normalization Data Wizard."""
    required_permission = "dictionary.edit"

    template_name = "twf/dictionaries/requests/wikidata.html"
    page_title = "Wikidata Request"
    form_class = WikidataBatchForm
    success_url = reverse_lazy("twf:dictionaries_request_wikidata")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["project"] = self.get_project()
        return kwargs


class TWFUnifiedDictionaryAIBatchView(ProjectPermissionMixin, AIFormView, TWFDictionaryView):
    """
    Unified view for AI batch processing of dictionary entries.

    This view provides a single interface for batch processing with all supported
    AI providers. The provider is selected via a dropdown in the form.
    """
    required_permission = "dictionary.manage"

    template_name = "twf/base/base_ai_batch.html"
    page_title = "AI Batch Processing"
    form_class = UnifiedDictionaryAIBatchForm
    success_url = reverse_lazy("twf:dictionaries_batch_ai_unified")
    message = "Do you want to start the AI batch process now?"

    # Provider configuration (only 4 providers for dictionaries)
    PROVIDER_CONFIG = {
        "openai": {
            "label": "OpenAI (ChatGPT)",
            "credentials_key": "openai",
            "credentials_tab": "openai",
            "description": "OpenAI will process dictionary entries using ChatGPT models to normalize and enrich data.",
        },
        "genai": {
            "label": "Google Gemini",
            "credentials_key": "genai",
            "credentials_tab": "genai",
            "description": "Gemini will process dictionary entries to normalize and enrich data.",
        },
        "anthropic": {
            "label": "Anthropic Claude",
            "credentials_key": "anthropic",
            "credentials_tab": "anthropic",
            "description": "Claude will process dictionary entries to normalize and enrich data.",
        },
        "mistral": {
            "label": "Mistral",
            "credentials_key": "mistral",
            "credentials_tab": "mistral",
            "description": "Mistral will process dictionary entries to normalize and enrich data.",
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
        kwargs["data-start-url"] = reverse_lazy("twf:task_dictionaries_batch_unified")
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
            context["ai_heading"] = f"{provider_info['label']} Dictionary Batch"
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
            context["ai_lead"] = (
                "AI will process dictionary entries to normalize and enrich data."
            )
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
                "multimodal": False,  # Dictionaries don't support multimodal
                "multimodal_info": "",
                "credentials_url": str(reverse_lazy("twf:project_ai_configs"))
                + f"?tab={provider_info['credentials_tab']}",
                "has_api_key": has_api_key,
                "default_model": default_model,
            }
        context["provider_config_json"] = json.dumps(provider_config_for_js)

        return context


class TWFUnifiedDictionaryAIRequestView(ProjectPermissionMixin, AIFormView, TWFDictionaryView):
    """
    Unified view for AI request (supervised) processing of dictionary entries.

    This view provides a single interface for supervised, single-entry processing
    with all supported AI providers. The provider is selected via a dropdown in the form.
    """
    required_permission = "dictionary.edit"

    template_name = "twf/base/base_ai_batch.html"
    page_title = "AI Request"
    form_class = UnifiedDictionaryAIRequestForm
    success_url = reverse_lazy("twf:dictionaries_request_ai_unified")
    message = "Do you want to send this AI request now?"

    # Provider configuration (same 4 providers)
    PROVIDER_CONFIG = {
        "openai": {
            "label": "OpenAI (ChatGPT)",
            "credentials_key": "openai",
            "credentials_tab": "openai",
            "description": "OpenAI will process this dictionary entry using "
                           "ChatGPT models to normalize and enrich data.",
        },
        "genai": {
            "label": "Google Gemini",
            "credentials_key": "genai",
            "credentials_tab": "genai",
            "description": "Gemini will process this dictionary entry to "
                           "normalize and enrich data.",
        },
        "anthropic": {
            "label": "Anthropic Claude",
            "credentials_key": "anthropic",
            "credentials_tab": "anthropic",
            "description": "Claude will process this dictionary entry to "
                           "normalize and enrich data.",
        },
        "mistral": {
            "label": "Mistral",
            "credentials_key": "mistral",
            "credentials_tab": "mistral",
            "description": "Mistral will process this dictionary entry to "
                           "normalize and enrich data.",
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
        kwargs["data-start-url"] = reverse_lazy("twf:task_dictionaries_request_unified")
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
            context["ai_heading"] = f"{provider_info['label']} Dictionary Request"
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
            context["ai_lead"] = (
                "AI will process this dictionary entry to normalize and enrich data."
            )
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
                "multimodal": False,  # Dictionaries don't support multimodal
                "multimodal_info": "",
                "credentials_url": str(reverse_lazy("twf:project_ai_configs"))
                + f"?tab={provider_info['credentials_tab']}",
                "has_api_key": has_api_key,
                "default_model": default_model,
            }
        context["provider_config_json"] = json.dumps(provider_config_for_js)

        return context
