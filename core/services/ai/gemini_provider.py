"""Google Gemini provider adapter."""

import logging
from typing import Any, Optional

from .base_provider import BaseProvider
from .schemas import ProviderResponse

logger = logging.getLogger(__name__)

# Gemini role mapping: OpenAI → Gemini
_ROLE_MAP = {
    'user': 'user',
    'assistant': 'model',
    # system messages are handled separately as system_instruction
    'system': 'user',
}


def _convert_messages(messages: list[dict]) -> tuple[Optional[str], list[dict]]:
    """Split an OpenAI-style message list into a system instruction + Gemini contents.

    Returns:
        A tuple of ``(system_instruction_text, gemini_contents)`` where
        *system_instruction_text* is ``None`` when no system message is present.
    """
    system_parts: list[str] = []
    contents: list[dict] = []

    for msg in messages:
        role = msg.get('role', 'user')
        content = msg.get('content', '')
        if role == 'system':
            system_parts.append(content)
        else:
            contents.append({'role': _ROLE_MAP.get(role, 'user'), 'parts': [{'text': content}]})

    system_instruction = '\n'.join(system_parts) if system_parts else None
    return system_instruction, contents


class GeminiProvider(BaseProvider):
    """Calls the Google Gemini API via the ``google-genai`` SDK."""

    provider_type = 'Gemini'

    def chat(
        self,
        messages: list[dict],
        model_id: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        try:
            from google import genai  # noqa: PLC0415
            from google.genai import types as genai_types  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                'google-genai package is required for GeminiProvider. '
                'Install it with: pip install google-genai'
            ) from exc

        client = genai.Client(api_key=self._api_key)

        system_instruction, contents = _convert_messages(messages)

        config_kwargs: dict[str, Any] = {}
        if temperature is not None:
            config_kwargs['temperature'] = temperature
        if max_tokens is not None:
            config_kwargs['max_output_tokens'] = max_tokens
        if system_instruction:
            config_kwargs['system_instruction'] = system_instruction

        generate_config = genai_types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

        call_kwargs: dict[str, Any] = {'model': model_id, 'contents': contents}
        if generate_config is not None:
            call_kwargs['config'] = generate_config

        response = client.models.generate_content(**call_kwargs)

        text = response.text or ''

        input_tokens: Optional[int] = None
        output_tokens: Optional[int] = None
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            meta = response.usage_metadata
            input_tokens = getattr(meta, 'prompt_token_count', None)
            output_tokens = getattr(meta, 'candidates_token_count', None)

        return ProviderResponse(
            text=text,
            raw=response,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
