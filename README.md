# withoutsurprise/data

Curated data for *Scale Without Surprise* and withoutsurprise.com: AI model
specs and pricing, and cloud capacity providers.

Maintained by the **without-surprise-feeds** agent. Data is gathered,
normalized, and committed here; the book and website consume it when a data
change belongs in a table, figure, or cited number.

## Layout

- `models/models.json` — normalized model records (vendor, context window,
  modalities) with source attribution and collection date.
- `pricing/pricing.json` — normalized price points, USD per 1M tokens
  (prompt / completion), one row per model per source.
- `providers/providers.json` — cloud capacity providers (hyperscalers, GPU
  clouds, serverless platforms) with capability notes.
- `schema/` — data dictionaries for each dataset.
- `docs/curation.md` — how data is gathered, verified, and updated.
- `scripts/` — generation and validation scripts.

## Rules

1. **Never hand-edit the generated JSON** (`models/models.json`,
   `pricing/pricing.json`). Edit the generating script or a source list and
   re-run.
2. Every record carries `source`, `source_url`, and `collected` (date).
3. Prices are normalized to USD per 1M tokens. Currency, unit, and
   announced-vs-released status are explicit — never guess a price.
4. `python3 scripts/validate.py` must pass before commit.

## Refresh

```sh
python3 scripts/build_models_snapshot.py   # LiteLLM + OpenRouter sources
python3 scripts/validate.py
git add -A && git commit -m "data: refresh model pricing snapshot (YYYY-MM-DD)"
```
