#!/usr/bin/env python3
"""Validate the curated datasets: structure, required fields, referential checks."""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
errors = []


def check(cond, msg):
    if not cond:
        errors.append(msg)


models = json.loads((ROOT / "models/models.json").read_text())
pricing = json.loads((ROOT / "pricing/pricing.json").read_text())
providers = json.loads((ROOT / "providers/providers.json").read_text())

for name, blob in [("models", models), ("pricing", pricing), ("providers", providers)]:
    check("updated" in blob and "sources" in blob, f"{name}: missing updated/sources")
    check(blob.get("count") == len(blob.get("models") or blob.get("prices") or blob.get("providers")),
          f"{name}: count mismatch")

model_ids = {m["id"] for m in models["models"]}
for p in pricing["prices"]:
    check(p["model_id"] in model_ids, f"pricing: unknown model_id {p['model_id']}")
    check(p.get("unit") == "usd_per_mtok", f"pricing: bad unit on {p['model_id']}")
    check("source" in p and "collected" in p, f"pricing: missing provenance on {p['model_id']}")

for m in models["models"]:
    check("source" in m and "collected" in m, f"models: missing provenance on {m['id']}")

for pr in providers["providers"]:
    check("name" in pr and "category" in pr, "providers: name/category required")

if errors:
    print("FAIL:")
    for e in errors[:50]:
        print(" -", e)
    sys.exit(1)
print(f"OK: {models['count']} models, {pricing['count']} price points, {providers['count']} providers")
