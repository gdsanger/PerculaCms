"""
Weaviate public service API – Schema v1.

Provides upsert, delete and query operations for the ``PageContext`` collection.

Deterministic object IDs:
    source_key = f"{source_type}:{str(source_id)}"
    object_uuid = uuid.uuid5(NAMESPACE_UUID, source_key)

NAMESPACE_UUID is a stable constant (never regenerated at runtime).
"""

import logging
import uuid
from datetime import datetime, timezone as dt_timezone
from typing import Union

import weaviate
from weaviate.exceptions import ObjectAlreadyExistsError, UnexpectedStatusCodeError

from .client import get_client
from .schema import ensure_schema

logger = logging.getLogger(__name__)

# Stable namespace UUID for deterministic object IDs.
# Must never be changed once objects have been written to Weaviate.
NAMESPACE_UUID = uuid.UUID("f47ac10b-58cc-4372-a567-0e02b2c3d479")


def _make_uuid(source_type: str, source_id: Union[str, int]) -> uuid.UUID:
    """Return a deterministic UUID5 for the given source key."""
    source_key = f"{source_type}:{str(source_id)}"
    return uuid.uuid5(NAMESPACE_UUID, source_key)


class WeaviateService:
    """
    High-level service for the Weaviate ``PageContext`` collection.

    Usage::

        svc = WeaviateService()
        try:
            doc_id = svc.upsert_document(
                source_type="page",
                source_id=42,
                title="My Page",
                text="Full page content …",
            )
        finally:
            svc.close()

    Or as a context manager::

        with WeaviateService() as svc:
            svc.upsert_document(...)
    """

    def __init__(self, client: weaviate.WeaviateClient | None = None) -> None:
        """
        Initialise the service.

        Args:
            client: Optional pre-built Weaviate client (useful for testing).
                    If not provided, ``get_client()`` is called on first use.
        """
        self._client: weaviate.WeaviateClient | None = client
        self._owns_client = client is None

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------

    def _get_client(self) -> weaviate.WeaviateClient:
        if self._client is None:
            self._client = get_client()
        return self._client

    def close(self) -> None:
        """Close the underlying Weaviate connection (if owned by this instance)."""
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "WeaviateService":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _collection(self):
        client = self._get_client()
        ensure_schema(client)
        return client.collections.get("PageContext")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def upsert_document(
        self,
        source_type: str,
        source_id: Union[str, int],
        title: str,
        text: str,
        tags: list[str] | None = None,
        url: str | None = None,
        updated_at: datetime | None = None,
    ) -> str:
        """
        Insert or update a document in the ``PageContext`` collection.

        Returns:
            The object UUID as a string.
        """
        obj_uuid = _make_uuid(source_type, source_id)

        if updated_at is None:
            updated_at = datetime.now(tz=dt_timezone.utc)

        # Ensure updated_at is timezone-aware (Weaviate requires RFC3339)
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=dt_timezone.utc)

        properties = {
            "source_type": source_type,
            "source_id": str(source_id),
            "title": title,
            "text": text,
            "tags": tags or [],
            "url": url or "",
            "updated_at": updated_at.isoformat(),
        }

        collection = self._collection()

        try:
            collection.data.insert(properties=properties, uuid=obj_uuid)
            logger.debug(
                "Weaviate upsert_document: inserted uuid=%s source_type=%s source_id=%s",
                obj_uuid,
                source_type,
                source_id,
            )
        except (ObjectAlreadyExistsError, UnexpectedStatusCodeError):
            # Object already exists; replace it.
            collection.data.replace(properties=properties, uuid=obj_uuid)
            logger.debug(
                "Weaviate upsert_document: replaced uuid=%s source_type=%s source_id=%s",
                obj_uuid,
                source_type,
                source_id,
            )

        return str(obj_uuid)

    def delete_document(
        self,
        source_type: str,
        source_id: Union[str, int],
    ) -> None:
        """
        Delete the document identified by the given source key.

        Args:
            source_type: The source type (e.g. ``"page"``).
            source_id:   The source identifier.
        """
        obj_uuid = _make_uuid(source_type, source_id)
        collection = self._collection()
        collection.data.delete_by_id(obj_uuid)
        logger.debug(
            "Weaviate delete_document: uuid=%s source_type=%s source_id=%s",
            obj_uuid,
            source_type,
            source_id,
        )

    def query(
        self,
        query_text: str,
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[dict]:
        """
        Search the ``PageContext`` collection using BM25 (keyword) search.

        Args:
            query_text: The search query string.
            top_k:      Maximum number of results to return (default: 10).
            filters:    **Not supported in schema v1.** Accepted but ignored.

        Returns:
            A list of result dicts, each containing:
            ``source_type``, ``source_id``, ``title``, ``score``,
            ``text_preview`` (max 1000 chars), ``url``.
        """
        if filters is not None:
            logger.debug(
                "Weaviate query: filters not supported in schema v1; ignoring filters=%r",
                list(filters.keys()) if isinstance(filters, dict) else filters,
            )

        collection = self._collection()

        response = collection.query.bm25(
            query=query_text,
            limit=top_k,
            return_metadata=weaviate.classes.query.MetadataQuery(score=True),
        )

        results = []
        for obj in response.objects:
            props = obj.properties
            score = obj.metadata.score if obj.metadata else None
            text = props.get("text", "") or ""
            results.append(
                {
                    "source_type": props.get("source_type", ""),
                    "source_id": props.get("source_id", ""),
                    "title": props.get("title", ""),
                    "score": score,
                    "text_preview": text[:1000],
                    "url": props.get("url", ""),
                }
            )

        return results
