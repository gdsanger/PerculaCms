# AI Core Service

The AI Core Service provides a unified interface for interacting with multiple AI providers (OpenAI, Gemini) from within PerculaCMS.  Every call is automatically logged to `AIJobsHistory` for cost tracking and auditing.

---

## Package Layout

```
core/services/
├── __init__.py
├── base.py                  # Shared exceptions
└── ai/
    ├── __init__.py
    ├── router.py            # AIRouter – public entry-point
    ├── base_provider.py     # Abstract provider interface
    ├── openai_provider.py   # OpenAI adapter
    ├── gemini_provider.py   # Google Gemini adapter
    ├── pricing.py           # Cost calculation
    └── schemas.py           # AIResponse / ProviderResponse dataclasses
```

---

## Database Models

### `AIProvider`

Stores configuration for a single AI provider account.

| Field             | Description                                                          |
|-------------------|----------------------------------------------------------------------|
| `name`            | Human-readable label (e.g. *"OpenAI Production"*)                   |
| `provider_type`   | `OpenAI` / `Gemini` / `Claude`                                       |
| `api_key`         | Provider API key – stored in the database; never logged or exposed   |
| `organization_id` | OpenAI organisation ID (optional)                                    |
| `is_active`       | Provider is available for routing                                    |

### `AIModel`

A specific model offered by a provider.

| Field                       | Description                                       |
|-----------------------------|---------------------------------------------------|
| `provider`                  | FK → `AIProvider`                                 |
| `name`                      | Human-readable label (e.g. *"GPT-4o"*)            |
| `model_id`                  | Provider model string (e.g. `gpt-4o`)             |
| `input_price_per_1m_tokens` | USD cost per 1 M input tokens (optional)          |
| `output_price_per_1m_tokens`| USD cost per 1 M output tokens (optional)         |
| `active`                    | Model is available for routing                    |

### `AIJobsHistory`

Audit log – one row per AI API call.

| Field          | Description                                              |
|----------------|----------------------------------------------------------|
| `agent`        | Caller label, e.g. `core.ai` or `manual`                |
| `user`         | FK → `AUTH_USER_MODEL` (optional)                        |
| `provider`     | FK → `AIProvider`                                        |
| `model`        | FK → `AIModel`                                           |
| `status`       | `Pending` → `Completed` / `Error`                        |
| `client_ip`    | Caller IP address                                        |
| `input_tokens` | Tokens consumed by the prompt                            |
| `output_tokens`| Tokens produced in the response                          |
| `costs`        | Calculated USD cost (null when tokens/prices unavailable)|
| `timestamp`    | When the job was created                                 |
| `duration_ms`  | Elapsed time in milliseconds                             |
| `error_message`| Exception message on failure                             |

---

## Default Routing Logic

When `AIRouter.chat()` / `AIRouter.generate()` is called the router selects a model using the following priority:

1. **Explicit match** – both `provider_type` and `model_id` provided → exact DB lookup.
2. **Provider only** – only `provider_type` provided → first active model of that provider.
3. **No hint** – neither provided → first active *OpenAI* model; if none, first active *Gemini* model.

If no active model is found a `ServiceNotConfigured` exception is raised.

---

## Logging & Cost Calculation

For every call the router:

1. Creates an `AIJobsHistory` row with `status=Pending`.
2. Calls the provider adapter and measures wall-clock duration.
3. Updates the row with `status=Completed`, token counts, cost, and `duration_ms`.
4. On failure sets `status=Error` and records `error_message`.

Cost formula (`pricing.py`):

```
cost = (input_tokens / 1_000_000 * input_price_per_1m)
     + (output_tokens / 1_000_000 * output_price_per_1m)
```

If any of tokens or prices is `None` the cost is `None`.

---

## Usage Examples

### `chat()`

```python
from core.services.ai import AIRouter

router = AIRouter()

response = router.chat(
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user",   "content": "Summarise PerculaCMS in one sentence."},
    ],
    provider_type="OpenAI",
    model_id="gpt-4o",
    user=request.user,        # optional Django User
    client_ip="127.0.0.1",   # optional
    agent="content.summariser",
    temperature=0.7,
    max_tokens=256,
)

print(response.text)
print(f"Tokens: {response.input_tokens} in / {response.output_tokens} out")
```

### `generate()`

```python
from core.services.ai import AIRouter

router = AIRouter()

response = router.generate(
    prompt="Write a short product description for PerculaCMS.",
    temperature=0.8,
)

print(response.text)
```

---

## Exceptions

| Exception              | When raised                                                   |
|------------------------|---------------------------------------------------------------|
| `ServiceNotConfigured` | No active AI model matches the requested provider / model_id  |
| `ServiceDisabled`      | Reserved for future use (provider explicitly disabled)        |

Import from `core.services.base`:

```python
from core.services.base import ServiceNotConfigured, ServiceDisabled
```
