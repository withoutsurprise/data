# Curation handbook

Owner: without-surprise-feeds agent. This file describes the loop the agent
runs to gather and keep this data current.

## Datasets and sources

| Dataset | Primary sources | Cadence |
|---|---|---|
| Model specs + token pricing | LiteLLM `model_prices_and_context_window.json`, OpenRouter `/api/v1/models`, TrustedRouter `/v1/models` | Weekly |
| Cloud GPU / capacity providers | Vendor pricing pages (Lambda, CoreWeave, Nebius, Crusoe, RunPod, Modal, hyperscalers) | On change / monthly sweep |
| Announced-but-unpriced models | Vendor announcements | Event-driven |
| SKU comparison (`skus/skus.json`) | AWS Price List bulk file, Azure Retail Prices API, Google and Oracle price pages, GPU-cloud price pages | Snapshot; re-collect on request or with the monthly provider sweep |

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

## SKU comparison: how each source is read

A refresh makes a new `skus/sources/<date>/` directory, then runs
`python3 scripts/build_skus.py --date <date>`. Figures in the script that come
from a snapshot file are looked up, never typed.

- **AWS**: the AmazonEC2 Price List bulk file for us-east-1 (CSV form, about
  300 MB). Keep the rows for the instance types in use. The on-demand row is
  `BoxUsage`, `CapacityStatus=Used`, Linux, shared tenancy, no pre-installed
  software, description containing "On Demand". GPU families also carry $0
  Capacity Block rows with the same usage type; never key on usage type alone.
  Accelerator names and counts come from the EC2 accelerated-computing
  instance-types page, because the price list does not name the GPU.
- **Azure**: the Retail Prices API for `eastus`, Consumption type. One SKU
  returns Linux, Windows, Cloud Services, Spot and Low Priority meters; keep the
  Linux pay-as-you-go meter. A SKU missing from a region is queried by
  `armSkuName` across regions before it is called absent. Specs come from the
  per-series size pages on Microsoft Learn.
- **Google**: the Compute Engine pricing tables render only in a browser. The
  accelerator table carries list, Flex-start, calendar, spot and commitment
  columns; list can be N/A, which is recorded as `reservation_only`.
- **Oracle**: the price list renders only in a browser. The compute table has
  two price columns: Oracle's comparison price per vCPU, then the unit price per
  OCPU. Memory is a separate per-GiB line. Flex shapes are recorded per vCPU at
  a stated memory ratio.
- **GPU clouds and serverless GPU**: the provider's own price page, curated in
  the script with the page URL. Providers whose prices could only be found on
  third-party aggregators (Vultr, Vast.ai on 2026-11-13) are left out.
- Coverage is what was collected. A provider with no record in a class has not
  been shown to lack that capacity.
