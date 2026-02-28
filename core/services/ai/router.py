"""AI Router – selects provider/model and wraps every call with AIJobsHistory logging."""

import logging
import time
from typing import Optional, Any

from django.utils import timezone

from core.services.base import ServiceNotConfigured
from .base_provider import BaseProvider
from .openai_provider import OpenAIProvider
from .gemini_provider import GeminiProvider
from .pricing import calculate_cost
from .schemas import AIResponse

logger = logging.getLogger(__name__)

_PROVIDER_CLASSES: dict[str, type[BaseProvider]] = {
    'OpenAI': OpenAIProvider,
    'Gemini': GeminiProvider,
}


class AIRouter:
    """Central entry-point for all AI calls.

    Usage::

        router = AIRouter()
        response = router.chat(messages=[{"role": "user", "content": "Hello!"}])
        response = router.generate(prompt="Summarise this text: …")
    """

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    def chat(
        self,
        messages: list[dict],
        *,
        model_id: Optional[str] = None,
        provider_type: Optional[str] = None,
        user=None,
        client_ip: Optional[str] = None,
        agent: str = 'core.ai',
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AIResponse:
        """Send a chat-completion request and return an :class:`AIResponse`.

        Args:
            messages: OpenAI-compatible ``[{"role": …, "content": …}]`` list.
            model_id: Explicit provider model string (e.g. ``'gpt-4o'``).
            provider_type: Explicit provider type (``'OpenAI'`` / ``'Gemini'``).
            user: Optional Django ``User`` instance for audit logging.
            client_ip: Caller IP address for audit logging.
            agent: Agent label written to :class:`~core.models.AIJobsHistory`.
            temperature: Sampling temperature forwarded to the provider.
            max_tokens: Max completion tokens forwarded to the provider.

        Returns:
            :class:`AIResponse` with text, token counts and provider/model info.

        Raises:
            :class:`~core.services.base.ServiceNotConfigured`: When no active
                AI model can be found matching the requested criteria.
        """
        from core.models import AIJobsHistory  # local import avoids circular deps

        ai_model, provider_record = self._resolve_model(model_id, provider_type)
        provider = self._build_provider(provider_record)

        job = AIJobsHistory.objects.create(
            agent=agent,
            user=user,
            provider=provider_record,
            model=ai_model,
            status=AIJobsHistory.Status.PENDING,
            client_ip=client_ip,
            timestamp=timezone.now(),
        )

        start = time.monotonic()
        try:
            result = provider.chat(
                messages=messages,
                model_id=ai_model.model_id,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            duration_ms = int((time.monotonic() - start) * 1000)

            cost = calculate_cost(
                result.input_tokens,
                result.output_tokens,
                ai_model.input_price_per_1m_tokens,
                ai_model.output_price_per_1m_tokens,
            )

            job.status = AIJobsHistory.Status.COMPLETED
            job.input_tokens = result.input_tokens
            job.output_tokens = result.output_tokens
            job.costs = cost
            job.duration_ms = duration_ms
            job.save(update_fields=['status', 'input_tokens', 'output_tokens', 'costs', 'duration_ms'])

            return AIResponse(
                text=result.text,
                raw=result.raw,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                model=ai_model.model_id,
                provider=provider_record.provider_type,
            )

        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            job.status = AIJobsHistory.Status.ERROR
            job.duration_ms = duration_ms
            job.error_message = str(exc)
            job.save(update_fields=['status', 'duration_ms', 'error_message'])
            raise

    def generate(
        self,
        prompt: str,
        *,
        model_id: Optional[str] = None,
        provider_type: Optional[str] = None,
        user=None,
        client_ip: Optional[str] = None,
        agent: str = 'core.ai',
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AIResponse:
        """Shortcut for single-prompt generation.

        Wraps *prompt* in a ``user`` message and delegates to :meth:`chat`.
        """
        return self.chat(
            messages=[{'role': 'user', 'content': prompt}],
            model_id=model_id,
            provider_type=provider_type,
            user=user,
            client_ip=client_ip,
            agent=agent,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

    # ---------------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------------

    def _resolve_model(self, model_id: Optional[str], provider_type: Optional[str]):
        """Return ``(AIModel, AIProvider)`` according to the routing strategy.

        Routing strategy (in priority order):
        1. Both *provider_type* and *model_id* given → exact match.
        2. If exact match fails, fall back to any active model of that provider.
        3. Only *provider_type* given → first active model of that provider.
        4. Nothing given → first active OpenAI model, then first active Gemini model.

        Raises:
            :class:`~core.services.base.ServiceNotConfigured` if no active model
            is found.
        """
        from core.models import AIModel, AIProvider  # local import

        qs = AIModel.objects.filter(active=True, provider__is_active=True).select_related('provider')

        if provider_type and model_id:
            # Try exact match first
            exact_qs = qs.filter(provider__provider_type=provider_type, model_id=model_id)
            ai_model = exact_qs.first()

            # If exact match not found, fall back to any active model of that provider
            if ai_model is None:
                logger.warning(
                    f"Model '{model_id}' not found for provider '{provider_type}'. "
                    f"Falling back to any active model of that provider."
                )
                fallback_qs = qs.filter(provider__provider_type=provider_type)
                ai_model = fallback_qs.first()

                if ai_model is not None:
                    logger.info(
                        f"Using fallback model: {ai_model.model_id} "
                        f"(provider: {ai_model.provider.name})"
                    )
        elif provider_type:
            qs = qs.filter(provider__provider_type=provider_type)
            ai_model = qs.first()
        else:
            # Default: prefer OpenAI then Gemini
            openai_qs = qs.filter(provider__provider_type=AIProvider.ProviderType.OPENAI)
            if openai_qs.exists():
                qs = openai_qs
            else:
                gemini_qs = qs.filter(provider__provider_type=AIProvider.ProviderType.GEMINI)
                if gemini_qs.exists():
                    qs = gemini_qs
            ai_model = qs.first()

        if ai_model is None:
            raise ServiceNotConfigured('No active AI model configured.')

        return ai_model, ai_model.provider

    def _build_provider(self, provider_record) -> BaseProvider:
        """Instantiate the correct :class:`BaseProvider` for *provider_record*."""
        cls = _PROVIDER_CLASSES.get(provider_record.provider_type)
        if cls is None:
            raise ServiceNotConfigured(
                f'No provider implementation for type "{provider_record.provider_type}".'
            )
        kwargs: dict[str, Any] = {}
        if provider_record.organization_id:
            kwargs['organization_id'] = provider_record.organization_id
        return cls(api_key=provider_record.api_key, **kwargs)
