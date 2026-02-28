# Weaviate Service

PerculaCMS uses an optional Weaviate vector-database service for context storage
and semantic / keyword retrieval.  The service is part of the infrastructure
layer (`core/services/weaviate/`) and has **no side-effects on import**.

---

## Schema v1

### Collection

| Property      | Type        | Notes                                  |
|---------------|-------------|----------------------------------------|
| `source_type` | `text`      | E.g. `"page"`, `"snippet"`            |
| `source_id`   | `text`      | Stringified identifier of the source  |
| `title`       | `text`      | Document title                        |
| `text`        | `text`      | Full document body                    |
| `tags`        | `text[]`    | Optional list of tag strings          |
| `url`         | `text`      | Optional canonical URL                |
| `updated_at`  | `date`      | RFC 3339 datetime                     |

Collection name: **`PageContext`** (fixed, v1 contains exactly this one collection).

---

## UUID Strategy

Object identifiers are deterministic and derived from the source key:

```
source_key  = f"{source_type}:{str(source_id)}"
object_uuid = uuid.uuid5(NAMESPACE_UUID, source_key)
```

`NAMESPACE_UUID` is a **stable constant** defined in `service.py`
(`f47ac10b-58cc-4372-a567-0e02b2c3d479`).  It must never be changed once data
has been written to Weaviate.

This makes `upsert_document()` fully idempotent: calling it twice with the same
`(source_type, source_id)` always writes to the same Weaviate object.

---

## Configuration

The service is configured **exclusively via environment variables** (no database
persistence).

| ENV Variable         | Required | Default  | Description                              |
|----------------------|----------|----------|------------------------------------------|
| `WEAVIATE_ENABLED`   | No       | `"true"` | Set to `"false"` to disable the service |
| `WEAVIATE_URL`       | **Yes**  | —        | Host / IP of the Weaviate instance       |
| `WEAVIATE_HTTP_PORT` | **Yes**  | —        | HTTP REST port (e.g. `8080`)             |
| `WEAVIATE_GRPC_PORT` | **Yes**  | —        | gRPC port (e.g. `50051`)                 |
| `WEAVIATE_API_KEY`   | No       | —        | API key (only when auth is enabled)      |

### Enable / Disable

```bash
# Disable:
export WEAVIATE_ENABLED=false

# Enable (default):
export WEAVIATE_ENABLED=true
```

When disabled, any call to `get_client()` raises `ServiceDisabled`.
When required ENV vars are absent, `ServiceNotConfigured` is raised.

### Typical local setup

```bash
export WEAVIATE_URL=localhost
export WEAVIATE_HTTP_PORT=8080
export WEAVIATE_GRPC_PORT=50051
```

---

## API Examples

### Upsert a document

```python
from core.services.weaviate import WeaviateService

with WeaviateService() as svc:
    doc_id = svc.upsert_document(
        source_type="page",
        source_id=42,
        title="My Page",
        text="Full page content goes here …",
        tags=["product", "feature"],
        url="https://example.com/page/42",
    )
print(doc_id)  # deterministic UUID string
```

### Query (BM25 keyword search)

```python
with WeaviateService() as svc:
    results = svc.query("product features", top_k=5)

for hit in results:
    print(hit["title"], hit["score"], hit["text_preview"][:80])
```

Each result dict contains:

| Key            | Type    | Description                        |
|----------------|---------|------------------------------------|
| `source_type`  | `str`   | Stored source type                 |
| `source_id`    | `str`   | Stored source ID                   |
| `title`        | `str`   | Document title                     |
| `score`        | `float` | BM25 relevance score               |
| `text_preview` | `str`   | First 1000 characters of `text`   |
| `url`          | `str`   | Canonical URL (may be empty)       |

> **Note:** The `filters` parameter is accepted by `query()` but **not applied**
> in schema v1.  A debug-level log entry is emitted when filters are passed.
> Full filter support is planned for schema v2.

### Delete a document

```python
with WeaviateService() as svc:
    svc.delete_document(source_type="page", source_id=42)
```

---

## Schema Management

`ensure_schema()` is called **lazily** (before the first real operation) and
is **cached** per process – the Weaviate API is queried at most once per
process lifetime.  There is no schema initialisation on import.

### Upgrade strategy (v2+)

Increment `SCHEMA_VERSION` in `schema.py` and implement a `migrate_vN_to_vM()`
function.  `ensure_schema()` should compare the stored version against
`SCHEMA_VERSION` and run migrations as required.  Destructive changes (type
changes, property removal) must be scheduled during a maintenance window and
paired with a data-migration script.
