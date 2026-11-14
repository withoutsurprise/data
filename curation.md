# Curation handbook

Owner: without-surprise-feeds agent. This file describes the loop the agent
runs to gather and keep this data current.

## Datasets and sources

| Dataset | Primary sources | Cadence |
|---|---|---|
| Model specs + token pricing | LiteLLM `model_prices_and_context_window.json`, OpenRouter `/api/v1/models` | Weekly |
| Cloud GPU / capacity providers | Vendor pricing pages (Lambda, CoreWeave, Nebius, Crusoe, RunPod, Modal, hyperscalers) | On change / monthly sweep |
| Announced-but-unpriced models | Vendor announcements | Event-driven |

## Procedure per refresh

1. Pull the machine-readable sources (`scripts/build_models_snapshot.py`).
2. Cross-check headline models (OpenAI, Anthropic, Google flagship tiers)
   against the vendors' own pricing pages; record deviations in the
   `deviations` field, not by editing the normalized number.
3. Distinguish **announced** vs **released/unpriced** — announced-but-unpriced
   models are recorded with `"status": "announced"` and no price.
4. Run `scripts/validate.py` (schema + referential checks).
5. Commit with date in the message; never commit when nothing changed.
6. When a data change belongs in the book or site, update the figure/table
   there in the same pass and leave surrounding prose alone.

## Provenance rules

- Every number has a source URL and a collection date.
- Vendor-listed prices are the record; third-party aggregators are cross-checks
  only, never the source of truth for a committed price.
- If a fetch fails, record the failure in the run notes; do not carry a stale
  number forward silently.
