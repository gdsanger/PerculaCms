"""Request / response dataclasses for the AI Core Service."""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ProviderResponse:
    """Raw response returned by a provider implementation."""

    text: str
    raw: Any
    input_tokens: Optional[int]
    output_tokens: Optional[int]


@dataclass
class AIResponse:
    """Structured response returned to callers of AIRouter."""

    text: str
    raw: Any
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    model: str
    provider: str
