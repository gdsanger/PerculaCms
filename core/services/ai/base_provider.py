"""Abstract base class for AI provider implementations."""

import abc
from typing import Any, Optional

from .schemas import ProviderResponse


class BaseProvider(abc.ABC):
    """Interface that every provider adapter must implement."""

    #: String identifier matching ``AIProvider.provider_type`` (e.g. ``'OpenAI'``).
    provider_type: str = ''

    def __init__(self, api_key: str, **kwargs: Any) -> None:
        self._api_key = api_key

    @abc.abstractmethod
    def chat(
        self,
        messages: list[dict],
        model_id: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Send a chat completion request and return a :class:`ProviderResponse`.

        Args:
            messages: List of ``{"role": ..., "content": ...}`` dicts.
            model_id: Provider-side model identifier.
            temperature: Sampling temperature (optional).
            max_tokens: Maximum tokens in the response (optional).
            **kwargs: Additional provider-specific options.

        Returns:
            :class:`ProviderResponse` with ``text``, ``raw``, and token counts.
        """
