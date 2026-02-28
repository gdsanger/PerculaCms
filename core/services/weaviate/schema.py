"""
Weaviate schema management – Schema v1.

Defines the ``PageContext`` collection and ensures it exists before first use.

Schema version: 1
Collection: PageContext

Upgrade strategy (v2+):
    When properties need to be added or changed, increment SCHEMA_VERSION and
    implement a migration function (e.g. ``migrate_v1_to_v2(client)``) that
    handles the transition.  ``ensure_schema()`` should compare the stored
    schema version (persisted as a Weaviate object metadata field or via a
    dedicated version collection) against SCHEMA_VERSION and call the
    appropriate migration path.  Destructive changes (property removal, type
    changes) require an explicit data-migration strategy and should be gated
    behind a maintenance window.
"""

import logging

import weaviate
import weaviate.classes.config as wc

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

_schema_ensured = False

_PAGE_CONTEXT_PROPERTIES = [
    wc.Property(name="source_type", data_type=wc.DataType.TEXT),
    wc.Property(name="source_id", data_type=wc.DataType.TEXT),
    wc.Property(name="title", data_type=wc.DataType.TEXT),
    wc.Property(name="text", data_type=wc.DataType.TEXT),
    wc.Property(name="tags", data_type=wc.DataType.TEXT_ARRAY),
    wc.Property(name="url", data_type=wc.DataType.TEXT),
    wc.Property(name="updated_at", data_type=wc.DataType.DATE),
]


def ensure_schema(client: weaviate.WeaviateClient) -> None:
    """
    Ensure the ``PageContext`` collection exists in Weaviate.

    Lazy: called only on first service use.
    Cached: runs only once per process (module-level flag).

    Args:
        client: An already-connected Weaviate v4 client.
    """
    global _schema_ensured
    if _schema_ensured:
        return

    collection_name = "PageContext"
    if client.collections.exists(collection_name):
        logger.debug("Weaviate schema v%d: collection '%s' already exists.", SCHEMA_VERSION, collection_name)
    else:
        client.collections.create(
            name=collection_name,
            properties=_PAGE_CONTEXT_PROPERTIES,
        )
        logger.debug("Weaviate schema v%d: collection '%s' created.", SCHEMA_VERSION, collection_name)

    _schema_ensured = True
    logger.debug("Weaviate schema ensured (v%d).", SCHEMA_VERSION)


def reset_schema_cache() -> None:
    """Reset the in-process schema cache. Intended for use in tests only."""
    global _schema_ensured
    _schema_ensured = False
