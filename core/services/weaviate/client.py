"""
Weaviate client factory (weaviate-python-client v4).

Configuration is loaded exclusively from environment variables:

    WEAVIATE_ENABLED   – "true" / "false"  (default: "true")
    WEAVIATE_URL       – host / IP of the Weaviate instance  (required)
    WEAVIATE_HTTP_PORT – HTTP port                           (required)
    WEAVIATE_GRPC_PORT – gRPC port                           (required)
    WEAVIATE_API_KEY   – optional API key

No network I/O is performed at import time.
"""

import logging
import os

import weaviate
from weaviate.auth import AuthApiKey

from core.services.base import ServiceDisabled, ServiceNotConfigured

logger = logging.getLogger(__name__)


def _load_config() -> dict:
    """Read and validate Weaviate configuration from environment variables."""
    enabled_raw = os.environ.get("WEAVIATE_ENABLED", "true").strip().lower()
    if enabled_raw == "false":
        raise ServiceDisabled(
            "Weaviate service is disabled (WEAVIATE_ENABLED=false)."
        )

    url = os.environ.get("WEAVIATE_URL", "").strip()
    http_port_raw = os.environ.get("WEAVIATE_HTTP_PORT", "").strip()
    grpc_port_raw = os.environ.get("WEAVIATE_GRPC_PORT", "").strip()

    missing = [
        name
        for name, val in [
            ("WEAVIATE_URL", url),
            ("WEAVIATE_HTTP_PORT", http_port_raw),
            ("WEAVIATE_GRPC_PORT", grpc_port_raw),
        ]
        if not val
    ]
    if missing:
        raise ServiceNotConfigured(
            f"Required Weaviate environment variable(s) not set: {', '.join(missing)}"
        )

    try:
        http_port = int(http_port_raw)
    except ValueError:
        raise ServiceNotConfigured(
            f"WEAVIATE_HTTP_PORT must be an integer, got: {http_port_raw!r}"
        )

    try:
        grpc_port = int(grpc_port_raw)
    except ValueError:
        raise ServiceNotConfigured(
            f"WEAVIATE_GRPC_PORT must be an integer, got: {grpc_port_raw!r}"
        )

    api_key = os.environ.get("WEAVIATE_API_KEY", "").strip() or None

    return {
        "url": url,
        "http_port": http_port,
        "grpc_port": grpc_port,
        "api_key": api_key,
    }


def get_client() -> weaviate.WeaviateClient:
    """
    Create and return a connected Weaviate v4 client.

    Raises:
        ServiceDisabled: if WEAVIATE_ENABLED is explicitly set to "false".
        ServiceNotConfigured: if required ENV vars are missing or invalid.
        weaviate.exceptions.WeaviateConnectionError: if the server is unreachable.
    """
    cfg = _load_config()

    auth = AuthApiKey(cfg["api_key"]) if cfg["api_key"] else None

    logger.debug(
        "Connecting to Weaviate at %s (http=%s, grpc=%s)",
        cfg["url"],
        cfg["http_port"],
        cfg["grpc_port"],
    )

    client = weaviate.connect_to_local(
        host=cfg["url"],
        port=cfg["http_port"],
        grpc_port=cfg["grpc_port"],
        auth_credentials=auth,
    )
    return client


def is_available() -> bool:
    """
    Return True if Weaviate is configured and reachable, False otherwise.

    Never raises; safe to call as a health/readiness probe.
    """
    try:
        client = get_client()
        ready = client.is_ready()
        client.close()
        return ready
    except Exception:
        return False
