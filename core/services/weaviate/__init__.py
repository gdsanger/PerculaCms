"""
Weaviate service package.

Exports the public API surface; no network I/O or initialisation on import.
"""

from .client import get_client, is_available
from .service import WeaviateService

__all__ = [
    "WeaviateService",
    "get_client",
    "is_available",
]
