"""
Adapter for generic-llm-api-client to match MOSAIC's expected AI client interface.

This adapter wraps the generic-llm-api-client to provide backward compatibility
with MOSAIC's existing code that expects a specific API:
- prompt() returns (response_text, elapsed_time) tuple instead of LLMResponse
- Provides add_image_resource() and clear_image_resources() methods
- Provides has_multimodal_support() method

The adapter allows MOSAIC to use the PyPI-published generic-llm-api-client package
without modifying existing task code.
"""

from typing import Tuple, List, Optional
from ai_client import create_ai_client as _create_ai_client, BaseAIClient


class TWFAIClientAdapter:
    """
    Adapter that wraps generic-llm-api-client to match MOSAIC's expected interface.

    This class maintains state for images (add/clear pattern) while delegating
    to the underlying stateless generic-llm-api-client.
    """

    def __init__(self, client: BaseAIClient):
        """
        Initialize the adapter with a generic-llm-api-client instance.

        Args:
            client: An instance from create_ai_client()
        """
        self._client = client
        self._pending_images: List[str] = []

    def prompt(self, model: str, prompt: str, **kwargs) -> Tuple[str, float]:
        """
        Send a prompt to the AI model.

        This method matches MOSAIC's expected signature: returns (text, duration) tuple.

        Args:
            model: Model identifier
            prompt: Text prompt
            **kwargs: Additional parameters passed to the underlying client

        Returns:
            Tuple of (response_text, elapsed_time_seconds)
        """
        # Pass any pending images to the underlying client
        images = self._pending_images if self._pending_images else None

        # Call the underlying client's prompt method
        response = self._client.prompt(
            model=model, prompt=prompt, images=images, **kwargs
        )

        # Return in the format expected by TWF: (text, duration)
        return response.text, response.duration

    def add_image_resource(self, resource: str):
        """
        Add an image resource to be included in the next prompt.

        Args:
            resource: Either a local file path or a URL to an image
        """
        if self._client.SUPPORTS_MULTIMODAL:
            self._pending_images.append(resource)

    def clear_image_resources(self):
        """Clear all pending image resources."""
        self._pending_images = []

    def has_multimodal_support(self) -> bool:
        """
        Check if the underlying provider supports multimodal content.

        Returns:
            True if the provider supports images, False otherwise
        """
        return self._client.SUPPORTS_MULTIMODAL


def create_ai_client(
    provider: str, api_key: str, system_prompt: Optional[str] = None, **settings
) -> TWFAIClientAdapter:
    """
    Factory function to create an AI client compatible with TWF's interface.

    This wraps generic-llm-api-client's create_ai_client() and returns an adapter
    that matches TWF's expected API.

    Args:
        provider: AI provider ID ('openai', 'genai', 'anthropic', 'mistral', etc.)
        api_key: API key for the provider
        system_prompt: System prompt/role description
        **settings: Additional provider-specific settings

    Returns:
        TWFAIClientAdapter: An adapted client matching TWF's interface

    Example:
        >>> client = create_ai_client('openai', api_key='sk-...')
        >>> response = client.prompt('gpt-4', 'Hello!')
        >>> print(f"Response: {response}")
    """
    # Create the underlying generic-llm-api-client
    underlying_client = _create_ai_client(
        provider=provider, api_key=api_key, system_prompt=system_prompt, **settings
    )

    # Wrap it in our adapter
    return TWFAIClientAdapter(underlying_client)
