"""OpenAI provider adapter."""

import logging
from typing import Any, Optional

from .base_provider import BaseProvider
from .schemas import ProviderResponse

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseProvider):
    """Calls the OpenAI Chat Completions API."""

    provider_type = 'OpenAI'

    def __init__(self, api_key: str, organization_id: str = '', **kwargs: Any) -> None:
        super().__init__(api_key, **kwargs)
        self._organization_id = organization_id

    def chat(
        self,
        messages: list[dict],
        model_id: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        try:
            import openai  # noqa: PLC0415 – lazy import keeps SDK optional at import time
        except ImportError as exc:
            raise ImportError(
                'openai package is required for OpenAIProvider. '
                'Install it with: pip install openai'
            ) from exc

        client_kwargs: dict[str, Any] = {'api_key': self._api_key}
        if self._organization_id:
            client_kwargs['organization'] = self._organization_id

        client = openai.OpenAI(**client_kwargs)

        call_kwargs: dict[str, Any] = {'model': model_id, 'messages': messages}
        if temperature is not None:
            call_kwargs['temperature'] = temperature
        if max_tokens is not None:
            call_kwargs['max_tokens'] = max_tokens
        call_kwargs.update(kwargs)

        response = client.chat.completions.create(**call_kwargs)

        text = response.choices[0].message.content or ''
        input_tokens: Optional[int] = None
        output_tokens: Optional[int] = None
        if response.usage:
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens

        return ProviderResponse(
            text=text,
            raw=response,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
