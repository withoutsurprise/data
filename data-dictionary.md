# Data dictionaries

## models/models.json

| Field | Type | Notes |
|---|---|---|
| `id` | string | `<source>/<model-id>` unique key |
| `vendor` | string | provider/organization |
| `mode` | string? | LiteLLM mode (chat, embedding, audio, …) |
| `context_window` | int? | max input tokens |
| `max_output_tokens` | int? | |
| `source` | enum | litellm, openrouter |
| `source_url` | string | where the record came from |
| `collected` | date | ISO date gathered |

## pricing/pricing.json

| Field | Type | Notes |
|---|---|---|
| `model_id` | string | references models.json `id` |
| `unit` | const | `usd_per_mtok` |
| `prompt` | float? | USD per 1M input tokens |
| `completion` | float? | USD per 1M output tokens |
| `provider` | string | selling provider |
| `source`, `source_url`, `collected` | | provenance |

## providers/providers.json

| Field | Type | Notes |
|---|---|---|
| `name` | string | |
| `category` | enum | hyperscaler, gpu-cloud, serverless-gpu, neocloud |
| `gpus` | string[] | GPU types offered (as published) |
| `notes` | string | what it is for, book-relevant characteristics |
| `homepage` | string | verified URL |
