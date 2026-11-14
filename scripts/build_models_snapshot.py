#!/usr/bin/env python3
"""Build the curated model + pricing snapshot from public sources.

Sources:
  - LiteLLM model_prices_and_context_window.json (GitHub raw)
  - OpenRouter public /api/v1/models
  - TrustedRouter public /v1/models (OpenRouter-compatible shape)

Output (committed):
  models/models.json          one normalized record per model
  pricing/pricing.json        normalized price points with source attribution

Prices are normalized to USD per 1M tokens (prompt / completion).
Never hand-edit models.json or pricing.json; edit this script or add sources.
"""
import json, datetime, urllib.request, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
LITELLM_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
OPENROUTER_URL = "https://openrouter.ai/api/v1/models"
TRUSTEDROUTER_URL = "https://trustedrouter.com/v1/models"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "withoutsurprise-feeds"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def per_mtok(s):
    """LiteLLM stores USD per token; OpenRouter per token as strings. -> USD per 1M."""
    if s in (None, "", "0"):
        return None
    v = float(s)
    return round(v * 1_000_000, 6)


def main():
    litellm = fetch(LITELLM_URL)
    openrouter = fetch(OPENROUTER_URL)["data"]
    today = datetime.date.today().isoformat()

    models, pricing = {}, []
    for mid, m in litellm.items():
        if mid == "sample_spec" or not m.get("litellm_provider"):
            continue
        prompt = per_mtok(m.get("input_cost_per_token"))
        completion = per_mtok(m.get("output_cost_per_token"))
        models[mid] = {
            "id": mid,
            "vendor": m.get("litellm_provider"),
            "mode": m.get("mode"),
            "context_window": m.get("max_input_tokens"),
            "max_output_tokens": m.get("max_output_tokens"),
            "source": "litellm",
            "source_url": LITELLM_URL,
            "collected": today,
        }
        if prompt is not None or completion is not None:
            pricing.append({
                "model_id": mid, "unit": "usd_per_mtok", "prompt": prompt,
                "completion": completion, "provider": m.get("litellm_provider"),
                "source": "litellm", "source_url": LITELLM_URL, "collected": today,
            })

    for m in openrouter:
        mid = f"openrouter/{m['id']}"
        p = m.get("pricing", {})
        pr, co = per_mtok(p.get("prompt")), per_mtok(p.get("completion"))
        models[mid] = {
            "id": mid,
            "vendor": m["id"].split("/")[0],
            "context_window": m.get("context_length"),
            "source": "openrouter",
            "source_url": OPENROUTER_URL,
            "collected": today,
        }
        if pr is not None or co is not None:
            pricing.append({
                "model_id": mid, "unit": "usd_per_mtok", "prompt": pr,
                "completion": co, "provider": "openrouter",
                "source": "openrouter", "source_url": OPENROUTER_URL, "collected": today,
            })

    for m in fetch(TRUSTEDROUTER_URL)["data"]:
        mid = f"trustedrouter/{m['id']}"
        p = m.get("pricing", {})
        pr, co = per_mtok(p.get("prompt")), per_mtok(p.get("completion"))
        models[mid] = {
            "id": mid,
            "vendor": m["id"].split("/")[0],
            "context_window": m.get("context_length"),
            "source": "trustedrouter",
            "source_url": TRUSTEDROUTER_URL,
            "collected": today,
        }
        if pr is not None or co is not None:
            pricing.append({
                "model_id": mid, "unit": "usd_per_mtok", "prompt": pr,
                "completion": co, "provider": "trustedrouter",
                "source": "trustedrouter", "source_url": TRUSTEDROUTER_URL, "collected": today,
            })

    models_out = {"updated": today, "sources": [LITELLM_URL, OPENROUTER_URL, TRUSTEDROUTER_URL],
                  "count": len(models), "models": list(models.values())}
    pricing_out = {"updated": today, "unit": "usd_per_mtok",
                   "sources": [LITELLM_URL, OPENROUTER_URL, TRUSTEDROUTER_URL],
                   "count": len(pricing), "prices": pricing}

    for path, blob in [(ROOT / "models/models.json", models_out),
                       (ROOT / "pricing/pricing.json", pricing_out)]:
        n = len(blob.get("models") or blob.get("prices"))
        path.write_text(json.dumps(blob, indent=2) + "\n")
        print(f"wrote {path} ({n} records)")


if __name__ == "__main__":
    main()
