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

skus = json.loads((ROOT / "skus/skus.json").read_text())
check("updated" in skus and "sources" in skus, "skus: missing updated/sources")
check(skus.get("count") == len(skus.get("skus", [])), "skus: count mismatch")
provider_names = {pr["name"] for pr in providers["providers"]}
sku_providers = {p["id"] for p in skus["providers"]}
sku_classes = {c["id"]: c for c in skus["classes"]}
for p in skus["providers"]:
    check(p["provider"] in provider_names, f"skus: provider {p['id']} not in providers.json")
seen = set()
for r in skus["skus"]:
    key = (r["class"], r["provider"], r["sku"])
    check(key not in seen, f"skus: duplicate {key}")
    seen.add(key)
    check(r["provider"] in sku_providers, f"skus: unknown provider on {key}")
    check(r["class"] in sku_classes, f"skus: unknown class on {key}")
    check(all(r.get(f) for f in ("source", "source_url", "page_url", "collected")), f"skus: missing provenance on {key}")
    check(r["purchase"] in ("on_demand", "per_second", "reservation_only", "ask_sales"), f"skus: bad purchase on {key}")
    price = r["unit_price_usd"]
    check(price is None or price > 0, f"skus: non-positive price on {key}")
    check(price is not None or r["purchase"] in ("reservation_only", "ask_sales"), f"skus: unpriced on-demand SKU {key}")
    if price is not None and r["machine_price_usd_hr"] and r["units_per_machine"]:
        check(abs(r["machine_price_usd_hr"] / r["units_per_machine"] - price) < 0.001, f"skus: unit price does not match machine price on {key}")
    for route in r["routes"]:
        check(route["unit_price_usd"] > 0 and route["label"], f"skus: bad route on {key}")
for cls, rows in skus["anatomy"].items():
    check(cls in sku_classes, f"skus: anatomy for unknown class {cls}")
    for row in rows:
        name = "".join(part["text"] for part in row["parts"]).strip()
        check(any(r["class"] == cls and r["provider"] == row["provider"] and r["sku"] == name for r in skus["skus"]),
              f"skus: anatomy name {name!r} has no SKU record in {cls}")

if errors:
    print("FAIL:")
    for e in errors[:50]:
        print(" -", e)
    sys.exit(1)
print(f"OK: {models['count']} models, {pricing['count']} price points, {providers['count']} providers, {skus['count']} SKUs")
