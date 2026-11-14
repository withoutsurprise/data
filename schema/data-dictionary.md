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

## skus/skus.json

Top level: `providers` (id, short `name`, `provider` = the `name` in
providers.json, `category`), `classes` (id, `label`, `group` cpu/gpu/chip,
`unit`, `blurb`), `skus`, and `anatomy`.

### skus[]

| Field | Type | Notes |
|---|---|---|
| `class` | string | references `classes[].id`: the kind of capacity being compared |
| `provider` | string | references `providers[].id` |
| `sku` | string | the SKU name exactly as the provider sells it |
| `unit_price_usd` | float? | list price per comparison unit (the class `unit`: `vcpu_hour`, `gpu_hour`, `chip_hour`); null when the provider publishes no price |
| `purchase` | enum | `on_demand`, `per_second`, `reservation_only`, `ask_sales` |
| `machine_price_usd_hr` | float? | list price of the whole machine per hour, when sold that way |
| `units_per_machine` | int? | vCPUs, GPUs or chips in that machine |
| `spec` | string | what is in the box, as published |
| `note` | string | caveat a reader needs before using the number |
| `routes` | object[] | cheaper published ways to buy the same SKU: `label`, `unit_price_usd` |
| `source`, `source_url`, `collected` | | provenance: what was read, and when |
| `page_url` | string | the provider's public price page for a human reader |

### anatomy

Per class, per provider: the SKU name split into `parts`, each with `text`,
`kind` (tier, family, gen, cpu, size, feat, chip, count, or null for a
separator) and `meaning`. The joined `text` must equal a `sku` in that class.
