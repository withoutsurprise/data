#!/usr/bin/env python3
"""Build skus/skus.json: what each capacity provider sells, at list price.

One record is one SKU in one capacity class, priced per comparison unit
(vCPU-hour, GPU-hour or chip-hour) so the same hardware can be compared
across providers.

Hyperscaler figures are looked up in the dated snapshot extracts under
skus/sources/<date>/ and are never typed in:

  aws_ec2_us-east-1.json      rows from the AWS Price List bulk file
  azure_eastus_linux.json     Linux pay-as-you-go meters, Azure Retail Prices API
  gcp_accelerator.json        Compute Engine accelerator-optimized price tables
  gcp_general_memory.json     Compute Engine general-purpose / memory tables
  oci_price_list.json         Oracle Cloud price list, compute rows

GPU-cloud, TPU and Capacity Block figures are curated here from the provider's
own price page, with the page URL on every record. docs/curation.md describes
how each source is read.

Usage: python3 scripts/build_skus.py [--date YYYY-MM-DD]
"""
import argparse, json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--date", default="2026-11-13", help="snapshot directory under skus/sources/")
ARGS = ap.parse_args()
COLLECTED = ARGS.date
SRC_DIR = ROOT / "skus" / "sources" / COLLECTED


def load(name):
    return json.loads((SRC_DIR / name).read_text())


# ---------------------------------------------------------------- lookups
_aws = {}
for r in load("aws_ec2_us-east-1.json"):
    if (r["usageType"].startswith("BoxUsage") and r["CapacityStatus"] == "Used"
            and "On Demand Linux" in r["PriceDescription"] and float(r["PricePerUnit"]) > 0):
        assert r["Instance Type"] not in _aws, r["Instance Type"]
        _aws[r["Instance Type"]] = r


def aws(name):
    r = _aws[name]
    return float(r["PricePerUnit"]), int(r["vCPU"]), float(r["Memory"].split()[0].replace(",", ""))


_az = load("azure_eastus_linux.json")


def az(name):
    return _az[name]["price"]


def _usd(s):
    s = s.replace("/ 1 hour", "").replace("/1 hour", "").strip()
    return None if s in ("N/A", "\u2014", "") else float(s.replace("$", "").replace(",", ""))


_gcp = {}
_blob = load("gcp_general_memory.json")
for t in load("gcp_accelerator.json")["tables"] + _blob["general"] + _blob["memory"]:
    for row in t["sel"]:
        _gcp[row[0]] = dict(zip(t["header"], row))


def gcp(name, col):
    d = _gcp[name]
    keys = {"list": ("Price (USD) * info", "Default* (USD) info"), "spot": ("Current Spot pricing (USD)",),
            "flex": ("DWS Flex-start price (USD)",), "cud3": ("Compute Resource CUDs - 3 Year (USD)",)}[col]
    for k in keys:
        if k in d:
            return _usd(d[k])
    raise KeyError((name, col))


_oci_cpu, _oci_mem, _oci_gpu = {}, {}, {}
for r in load("oci_price_list.json"):
    c = r["cells"]
    key = re.sub(r"\s+", " ", c[0].replace("\u2013", "-").replace("*", "")).strip()
    if len(c) == 4 and c[3] == "OCPU per hour":
        _oci_cpu.setdefault(key, (_usd(c[1]), _usd(c[2])))     # (per vCPU comparison, per OCPU)
    elif len(c) == 4 and c[3].startswith("Gigabyte") and "Memory" in key:
        _oci_mem.setdefault(key, _usd(c[2]))
    elif len(c) == 5 and key.startswith(("BM.GPU", "VM.GPU")):
        # the price list prints a footnote digit straight after two shape names
        _oci_gpu.setdefault(re.sub(r"(GB[23]00\.4)[12]$", r"\1", key), (_usd(c[4]), c[1]))


def oci_cpu(series, gib_per_vcpu):
    """Per-vCPU-hour price of a Flex shape at a given memory ratio, plus the billing note."""
    per_vcpu, per_ocpu = _oci_cpu[f"Compute - Standard - {series} - OCPU"]
    mem = _oci_mem[f"Compute - Standard - {series} - Memory"]
    note = (f"Billed as ${per_ocpu:g} per OCPU-hour plus ${mem:g} per GiB-hour; "
            f"shown at {gib_per_vcpu} GiB per vCPU using Oracle's own per-vCPU comparison price.")
    return per_vcpu + gib_per_vcpu * mem, note


def oci_gpu(shape):
    return _oci_gpu[shape]


# ---------------------------------------------------------------- reference
SOURCES = {
    "aws": ("AWS Price List, us-east-1, Linux on demand",
            "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/20261114012926/us-east-1/index.json",
            "https://aws.amazon.com/ec2/pricing/on-demand/"),
    "aws_cb": ("AWS EC2 Capacity Blocks pricing page", "https://aws.amazon.com/ec2/capacityblocks/pricing",
               "https://aws.amazon.com/ec2/capacityblocks/pricing"),
    "azure": ("Azure Retail Prices API, Linux pay as you go", "https://prices.azure.com/api/retail/prices",
              "https://azure.microsoft.com/en-us/pricing/details/virtual-machines/linux/"),
    "gcp": ("Google Compute Engine pricing page", "https://cloud.google.com/products/compute/pricing/general-purpose",
            "https://cloud.google.com/products/compute/pricing/general-purpose"),
    "gcp_accel": ("Google Compute Engine pricing page", "https://cloud.google.com/products/compute/pricing/accelerator-optimized",
                  "https://cloud.google.com/products/compute/pricing/accelerator-optimized"),
    "gcp_tpu": ("Google Cloud TPU pricing page", "https://cloud.google.com/tpu/pricing", "https://cloud.google.com/tpu/pricing"),
    "oci": ("Oracle Cloud price list", "https://www.oracle.com/cloud/price-list/", "https://www.oracle.com/cloud/price-list/"),
    "coreweave": ("CoreWeave pricing page", "https://coreweave.com/pricing", "https://coreweave.com/pricing"),
    "lambda": ("Lambda pricing page", "https://lambda.com/pricing", "https://lambda.com/pricing"),
    "nebius": ("Nebius pricing page", "https://nebius.com/prices", "https://nebius.com/prices"),
    "crusoe": ("Crusoe pricing page", "https://www.crusoe.ai/cloud/pricing", "https://www.crusoe.ai/cloud/pricing"),
    "together": ("Together AI GPU clusters page", "https://www.together.ai/gpu-clusters", "https://www.together.ai/gpu-clusters"),
    "runpod": ("RunPod pricing page", "https://www.runpod.io/pricing", "https://www.runpod.io/pricing"),
    "modal": ("Modal pricing page", "https://modal.com/pricing", "https://modal.com/pricing"),
    "replicate": ("Replicate pricing page", "https://replicate.com/pricing", "https://replicate.com/pricing"),
}

# id, short name, name in providers/providers.json, category
PROVIDERS = [
    ("aws", "AWS", "Amazon Web Services", "hyperscaler"), ("azure", "Azure", "Microsoft Azure", "hyperscaler"),
    ("gcp", "Google Cloud", "Google Cloud", "hyperscaler"), ("oci", "Oracle Cloud", "Oracle Cloud", "hyperscaler"),
    ("coreweave", "CoreWeave", "CoreWeave", "gpu-cloud"), ("lambda", "Lambda", "Lambda", "gpu-cloud"),
    ("nebius", "Nebius", "Nebius", "gpu-cloud"), ("crusoe", "Crusoe", "Crusoe", "gpu-cloud"),
    ("together", "Together AI", "Together AI", "gpu-cloud"), ("runpod", "RunPod", "RunPod", "serverless-gpu"),
    ("modal", "Modal", "Modal", "serverless-gpu"), ("replicate", "Replicate", "Replicate", "serverless-gpu"),
]

# id, label, group, unit, blurb
CLASSES = [
    ("gp-x86", "General purpose, x86", "cpu", "vcpu_hour", "The default server: about 4 GiB of memory per vCPU."),
    ("gp-arm", "General purpose, Arm", "cpu", "vcpu_hour", "The same shape on each provider\u2019s Arm processors."),
    ("mem", "Memory optimized", "cpu", "vcpu_hour", "About 8 GiB per vCPU, for databases and caches."),
    ("h100", "NVIDIA H100", "gpu", "gpu_hour", "The 80 GB Hopper card."),
    ("h200", "NVIDIA H200", "gpu", "gpu_hour", "Hopper with 141 GB of memory."),
    ("b200", "NVIDIA B200", "gpu", "gpu_hour", "Blackwell in the eight-GPU HGX server."),
    ("gb200", "NVIDIA GB200", "gpu", "gpu_hour", "Blackwell in the NVL72 rack."),
    ("a100", "NVIDIA A100 80GB", "gpu", "gpu_hour", "The generation before Hopper, still widely rented."),
    ("l40s", "NVIDIA L40S", "gpu", "gpu_hour", "The 48 GB card."),
    ("custom", "Other accelerators", "chip", "chip_hour",
     "Chips the provider designed itself, and AMD\u2019s. The chips differ, so these prices are not comparable with each other."),
]

E = []


def add(cls, prov, sku, unit, purchase="on_demand", machine=None, n=None, spec="", note="", routes=None, src=None):
    name, url, page = SOURCES[src or prov]
    E.append({
        "class": cls, "provider": prov, "sku": sku,
        "unit_price_usd": None if unit is None else round(unit, 4),
        "purchase": purchase,
        "machine_price_usd_hr": None if machine is None else round(machine, 4),
        "units_per_machine": n, "spec": spec, "note": note,
        "routes": [{"label": a, "unit_price_usd": round(b, 4)} for a, b in (routes or [])],
        "source": name, "source_url": url, "page_url": page, "collected": COLLECTED,
    })


def aws_cpu(cls, name):
    p, v, m = aws(name)
    add(cls, "aws", name, p / v, machine=p, n=v, spec=f"{v} vCPU \u00b7 {m:g} GiB")


def az_cpu(cls, name, v, m, note=""):
    p = az(name)
    add(cls, "azure", name, p / v, machine=p, n=v, spec=f"{v} vCPU \u00b7 {m:g} GiB", note=note)


def gcp_cpu(cls, name):
    d = _gcp[name]
    v, m, p = int(d["Virtual CPUs"]), d["Memory"], gcp(name, "list")
    add(cls, "gcp", name, p / v, machine=p, n=v, spec=f"{v} vCPU \u00b7 {m}",
        routes=[("3-year commitment", gcp(name, "cud3") / v)])


def oci_flex(cls, series, ratio):
    unit, note = oci_cpu(series, ratio)
    add(cls, "oci", f"VM.Standard.{series}.Flex", unit, spec="Flexible: you choose cores and memory", note=note)


# ---------------------------------------------------------------- processors
for n in ("m8i.48xlarge", "m7i.48xlarge", "m8a.48xlarge"):
    aws_cpu("gp-x86", n)
az_cpu("gp-x86", "Standard_D192s_v6", 192, 768)
az_cpu("gp-x86", "Standard_D96s_v5", 96, 384)
gcp_cpu("gp-x86", "n4-standard-80")
gcp_cpu("gp-x86", "c4-standard-192")
oci_flex("gp-x86", "E5", 4)
oci_flex("gp-x86", "E4", 4)

aws_cpu("gp-arm", "m8g.48xlarge")
aws_cpu("gp-arm", "m7g.16xlarge")
az_cpu("gp-arm", "Standard_D96ps_v6", 96, 384)
gcp_cpu("gp-arm", "c4a-standard-72")
oci_flex("gp-arm", "A4", 4)
oci_flex("gp-arm", "A2", 4)

aws_cpu("mem", "r8i.48xlarge")
aws_cpu("mem", "r8g.48xlarge")
az_cpu("mem", "Standard_E96s_v5", 96, 672, note="7 GiB per vCPU.")
oci_flex("mem", "E5", 8)


# ---------------------------------------------------------------- accelerators
def aws_gpu(cls, name, n, chip, routes=None):
    p, v, m = aws(name)
    add(cls, "aws", name, p / n, machine=p, n=n, spec=f"{n}\u00d7 {chip} \u00b7 {v} vCPU \u00b7 {m:g} GiB", routes=routes)


def az_gpu(cls, name, n, chip, v, m, note="", price=None):
    p = price if price is not None else az(name)
    gpus = f"{n}\u00d7 {chip}" if chip else f"{n} GPUs"
    add(cls, "azure", name, p / n, machine=p, n=n, spec=f"{gpus} \u00b7 {v} vCPU \u00b7 {m}", note=note)


def gcp_gpu(cls, name, chip, note="", base="list", purchase="on_demand"):
    d = _gcp[name]
    n, vcpu, mem = re.match(r"GPUs: (\d+) vCPUs: (\d+) Memory: ([\d,]+) ?(?:GB|GiB)", d["Components"]).groups()
    n = int(n)
    p = gcp(name, base)
    routes = [(lab, gcp(name, col) / n) for lab, col in (("Spot", "spot"), ("3-year commitment", "cud3"), ("Flex-start", "flex"))
              if col != base and gcp(name, col) is not None]
    add(cls, "gcp", name, p / n, purchase=purchase, machine=p, n=n,
        spec=f"{n}\u00d7 {chip} \u00b7 {vcpu} vCPU \u00b7 {mem} GB", note=note, routes=routes, src="gcp_accel")


def oci_g(cls, shape):
    price, desc = oci_gpu(shape)
    desc = re.sub(r"^(\d+)x ", "\\1\u00d7 ", desc)
    desc = re.sub(r"\b(NVIDIA|Nvidia) | (Tensor|Matrix) Core", "", desc).replace("192 GB", "192GB")
    add(cls, "oci", shape, price, spec=desc + ", bare metal")


def node(cls, prov, sku, machine, n, spec="", note="", routes=None, purchase="on_demand"):
    add(cls, prov, sku, machine / n, machine=machine, n=n, spec=spec, note=note, routes=routes, purchase=purchase)


def per(cls, prov, sku, unit, spec="", note="", routes=None, purchase="on_demand"):
    add(cls, prov, sku, unit, spec=spec, note=note, routes=routes, purchase=purchase)


# H100
aws_gpu("h100", "p5.48xlarge", 8, "H100", routes=[("Capacity Block", 5.970)])
az_gpu("h100", "Standard_ND96isr_H100_v5", 8, "H100", 96, "1,900 GiB")
az_gpu("h100", "Standard_NC40ads_H100_v5", 1, "H100", 40, "320 GiB")
gcp_gpu("h100", "a3-highgpu-8g", "H100")
oci_g("h100", "BM.GPU.H100.8")
node("h100", "coreweave", "HGX H100", 49.24, 8, "8\u00d7 H100 \u00b7 128 vCPU \u00b7 2,048 GB", routes=[("Spot", 19.71 / 8)],
     note="Sold as the whole eight-GPU node.")
per("h100", "lambda", "8\u00d7 HGX H100", 3.99, "8\u00d7 H100 \u00b7 208 vCPU \u00b7 1,800 GiB",
    note="Single-GPU instances are $4.29 (SXM) or $3.29 (PCIe).")
per("h100", "nebius", "HGX H100", 4.50, "16 vCPU \u00b7 200 GB per GPU", routes=[("Preemptible, from", 0.79)])
per("h100", "crusoe", "H100 HGX", 4.50, "80 GB")
per("h100", "together", "H100 cluster", 3.99, "8 to 256 GPUs", routes=[("Reserved, from", 3.19)])
per("h100", "runpod", "H100 SXM", 3.99, "Secure Cloud pod", routes=[("Community Cloud, from", 2.69)], purchase="per_second")
per("h100", "modal", "H100 SXM5", 0.001097 * 3600, "$0.001097 per second", purchase="per_second")
per("h100", "replicate", "gpu-h100", 5.49, "$0.001525 per second", purchase="per_second")

# H200
aws_gpu("h200", "p5en.48xlarge", 8, "H200")
az_gpu("h200", "Standard_ND96isr_H200_v5", 8, "H200", 96, "1,850 GiB", price=84.80,
       note="East US 2 price. Not offered in East US; other regions run from $84.80 to $169.60.")
gcp_gpu("h200", "a3-ultragpu-8g", "H200",
        note="The price page lists this rate; Google\u2019s machine-type guide says A3 Ultra is not sold on demand.")
oci_g("h200", "BM.GPU.H200.8")
node("h200", "coreweave", "HGX H200", 50.44, 8, "8\u00d7 H200 \u00b7 128 vCPU \u00b7 2,048 GB", routes=[("Spot", 20.93 / 8)])
per("h200", "nebius", "HGX H200", 5.40, "16 vCPU \u00b7 200 GB per GPU", routes=[("Preemptible, from", 0.79)])
per("h200", "crusoe", "H200 HGX", 5.40, "141 GB")
per("h200", "together", "H200 cluster", 5.99, "256 to 1,000 GPUs", routes=[("Reserved, from", 3.99)])
per("h200", "runpod", "H200", 5.29, "Secure Cloud pod", routes=[("Community Cloud, from", 3.59)], purchase="per_second")
per("h200", "modal", "H200 SXM", 0.001261 * 3600, "$0.001261 per second", purchase="per_second")
per("h200", "replicate", "gpu-h200", None, "Committed-spend contracts only", purchase="ask_sales")

# B200
aws_gpu("b200", "p6-b200.48xlarge", 8, "B200", routes=[("Capacity Block", 14.208)])
gcp_gpu("b200", "a4-highgpu-8g", "B200", base="flex", purchase="reservation_only",
        note="No on-demand price. Shown at Google\u2019s Flex-start rate.")
oci_g("b200", "BM.GPU.B200.8")
node("b200", "coreweave", "HGX B200", 68.80, 8, "8\u00d7 B200 \u00b7 128 vCPU \u00b7 2,048 GB", routes=[("Spot", 34.11 / 8)])
per("b200", "lambda", "8\u00d7 HGX B200", 6.69, "8\u00d7 B200 \u00b7 208 vCPU \u00b7 2,900 GiB", note="A single B200 is $6.99.")
per("b200", "nebius", "HGX B200", 8.50, "20 vCPU \u00b7 224 GB per GPU", routes=[("Preemptible, from", 0.99)])
per("b200", "crusoe", "B200 HGX", 8.50, "180 GB")
per("b200", "together", "HGX B200 cluster", 8.19, "256 to 1,000+ GPUs", routes=[("Reserved, from", 6.79)])
per("b200", "modal", "B200", 0.001736 * 3600, "$0.001736 per second", purchase="per_second")

# GB200
add("gb200", "aws", "u-p6e-gb200x72", 10.582, purchase="reservation_only", machine=761.904, n=72,
    spec="72\u00d7 B200 in one NVL72 UltraServer", note="Capacity Blocks only: a dated reservation paid up front.", src="aws_cb")
az_gpu("gb200", "Standard_ND128isr_NDR_GB200_v6", 4, None, 128, "900 GiB")
add("gb200", "gcp", "A4X series", None, purchase="reservation_only", spec="18 instances make one 72-GPU NVL72 domain",
    note="No list price. Sold only as future reservations for capacity blocks.", src="gcp_accel")
oci_g("gb200", "BM.GPU.GB200.4")
node("gb200", "coreweave", "GB200 NVL72", 42.00, 4, "4 superchips \u00b7 144 vCPU \u00b7 960 GB", note="No spot price.")
per("gb200", "crusoe", "GB200 NVL72", None, "186 GB", purchase="ask_sales")
per("gb200", "together", "GB200 NVL72", None, "Reserved only, 512 to 1,000+ GPUs", purchase="ask_sales")

# A100 80GB
aws_gpu("a100", "p4de.24xlarge", 8, "A100 80GB")
az_gpu("a100", "Standard_NC24ads_A100_v4", 1, "A100 80GB", 24, "220 GiB")
oci_g("a100", "BM.GPU.A100-v2.8")
node("a100", "coreweave", "A100", 21.60, 8, "8\u00d7 A100 \u00b7 128 vCPU \u00b7 2,048 GB", routes=[("Spot", 9.65 / 8)])
per("a100", "lambda", "8\u00d7 HGX A100", 2.79, "8\u00d7 A100 80GB \u00b7 240 vCPU \u00b7 1,800 GiB")
per("a100", "crusoe", "A100 SXM", 2.30, "80 GB", note="The PCIe version is $2.00.")
per("a100", "runpod", "A100 SXM", 1.79, "Secure Cloud pod", routes=[("Community Cloud, from", 1.39)], purchase="per_second")
per("a100", "modal", "A100, 80 GB", 0.000694 * 3600, "$0.000694 per second", purchase="per_second")
per("a100", "replicate", "gpu-a100-large", 5.04, "$0.001400 per second", purchase="per_second")

# L40S
aws_gpu("l40s", "g6e.48xlarge", 8, "L40S")
oci_g("l40s", "BM.GPU.L40S.4")
node("l40s", "coreweave", "L40S", 18.00, 8, "8\u00d7 L40S \u00b7 128 vCPU \u00b7 1,024 GB", routes=[("Spot", 7.88 / 8)])
per("l40s", "nebius", "L40S (Intel)", 1.55, "8 to 40 vCPU", note="A \u201cfrom\u201d price.", routes=[("Preemptible, from", 0.74)])
per("l40s", "crusoe", "L40S", 1.50, "48 GB")
per("l40s", "modal", "L40S", 0.000542 * 3600, "$0.000542 per second", purchase="per_second")
per("l40s", "replicate", "gpu-l40s", 3.51, "$0.000975 per second", purchase="per_second")

# Other accelerators
p, v, m = aws("trn1.32xlarge")
add("custom", "aws", "trn1.32xlarge", p / 16, machine=p, n=16, spec="16\u00d7 AWS Trainium", routes=[("Capacity Block", 0.596)])
p, v, m = aws("inf2.48xlarge")
add("custom", "aws", "inf2.48xlarge", p / 12, machine=p, n=12, spec="12\u00d7 AWS Inferentia2")
for nm, pr, reg, cud in [("TPU v5e", 1.20, "us-central1", 0.54), ("TPU Trillium", 2.70, "us-east1", 1.22),
                         ("TPU v5p", 4.20, "us-east5", 1.89), ("TPU Ironwood", 12.00, "us-central1", 5.40)]:
    add("custom", "gcp", nm, pr, spec=f"Google TPU \u00b7 {reg}", routes=[("3-year commitment", cud)], src="gcp_tpu")
oci_g("custom", "BM.GPU.MI300X.8")
oci_g("custom", "BM.GPU.MI355X.8")
per("custom", "crusoe", "AMD MI300X", 3.45, "192 GB")

# ---------------------------------------------------------------- name anatomy
# Each SKU name split into parts: (text, kind, what it means). kind None = separator.
ANATOMY = {
    "h100": [
        ("aws", [("p", "family", "P: GPU accelerated"), ("5", "gen", "Fifth generation"), (".", None, ""),
                 ("48xlarge", "size", "Size: 192 vCPUs and, in this family, all eight GPUs")]),
        ("azure", [("Standard_", "tier", "Prefix on Azure VM sizes"), ("N", "family", "N: GPU family"),
                   ("D", "family", "D: sub-family within the GPU sizes"), ("96", "size", "96 vCPUs"),
                   ("i", "feat", "i: isolated, the whole host is yours"), ("s", "feat", "s: Premium Storage capable"),
                   ("r", "feat", "r: RDMA networking"), ("_", None, ""), ("H100", "chip", "The accelerator, by name"),
                   ("_", None, ""), ("v5", "gen", "Version 5")]),
        ("gcp", [("a", "family", "A: accelerator-optimized"), ("3", "gen", "Third generation"), ("-", None, ""),
                 ("highgpu", "feat", "Machine type within the series"), ("-", None, ""), ("8", "count", "Eight GPUs"),
                 ("g", "count", "g: GPUs")]),
        ("oci", [("BM", "tier", "Bare metal, not a VM"), (".", None, ""), ("GPU", "family", "GPU shape family"), (".", None, ""),
                 ("H100", "chip", "The accelerator, by name"), (".", None, ""), ("8", "count", "Eight GPUs")]),
        ("coreweave", [("HGX ", "family", "HGX: NVIDIA\u2019s multi-GPU server platform"), ("H100", "chip", "The accelerator, by name")]),
    ],
    "b200": [
        ("aws", [("p", "family", "P: GPU accelerated"), ("6", "gen", "Sixth generation"), ("-", None, ""),
                 ("b200", "chip", "Blackwell B200: from this generation AWS puts the chip in the name"),
                 (".", None, ""), ("48xlarge", "size", "Size: 192 vCPUs, eight GPUs")]),
        ("gcp", [("a", "family", "A: accelerator-optimized"), ("4", "gen", "Fourth generation"), ("-", None, ""),
                 ("highgpu", "feat", "Machine type within the series"), ("-", None, ""), ("8", "count", "Eight GPUs"),
                 ("g", "count", "g: GPUs")]),
        ("oci", [("BM", "tier", "Bare metal, not a VM"), (".", None, ""), ("GPU", "family", "GPU shape family"), (".", None, ""),
                 ("B200", "chip", "The accelerator, by name"), (".", None, ""), ("8", "count", "Eight GPUs")]),
        ("coreweave", [("HGX ", "family", "HGX: NVIDIA\u2019s multi-GPU server platform"), ("B200", "chip", "The accelerator, by name")]),
    ],
    "gp-x86": [
        ("aws", [("m", "family", "M: general purpose"), ("8", "gen", "Eighth generation"), ("i", "cpu", "i: Intel processor"),
                 (".", None, ""), ("48xlarge", "size", "Size: 192 vCPUs")]),
        ("azure", [("Standard_", "tier", "Prefix on Azure VM sizes"), ("D", "family", "D: general purpose"),
                   ("192", "size", "192 vCPUs"), ("s", "feat", "s: Premium Storage capable"), ("_", None, ""),
                   ("v6", "gen", "Version 6")]),
        ("gcp", [("n", "family", "N: a general-purpose series"), ("4", "gen", "Fourth generation"), ("-", None, ""),
                 ("standard", "feat", "standard: 4 GiB of memory per vCPU"), ("-", None, ""), ("80", "size", "80 vCPUs")]),
        ("oci", [("VM", "tier", "Virtual machine"), (".", None, ""), ("Standard", "family", "Standard shape family"), (".", None, ""),
                 ("E", "cpu", "E: AMD processor"), ("5", "gen", "Fifth generation"), (".", None, ""),
                 ("Flex", "size", "Flex: you choose the cores and the memory")]),
    ],
    "gp-arm": [
        ("aws", [("m", "family", "M: general purpose"), ("8", "gen", "Eighth generation"), ("g", "cpu", "g: AWS Graviton (Arm)"),
                 (".", None, ""), ("48xlarge", "size", "Size: 192 vCPUs")]),
        ("azure", [("Standard_", "tier", "Prefix on Azure VM sizes"), ("D", "family", "D: general purpose"), ("96", "size", "96 vCPUs"),
                   ("p", "cpu", "p: Arm processor"), ("s", "feat", "s: Premium Storage capable"), ("_", None, ""),
                   ("v6", "gen", "Version 6")]),
        ("gcp", [("c", "family", "C: a general-purpose series"), ("4", "gen", "Fourth generation"),
                 ("a", "cpu", "a: Arm (Google Axion)"), ("-", None, ""), ("standard", "feat", "standard: 4 GiB of memory per vCPU"),
                 ("-", None, ""), ("72", "size", "72 vCPUs")]),
        ("oci", [("VM", "tier", "Virtual machine"), (".", None, ""), ("Standard", "family", "Standard shape family"), (".", None, ""),
                 ("A", "cpu", "A: Ampere (Arm) processor"), ("4", "gen", "Fourth generation"), (".", None, ""),
                 ("Flex", "size", "Flex: you choose the cores and the memory")]),
    ],
}

out = {
    "updated": COLLECTED,
    "sources": [{"name": n, "url": u} for n, u, _ in sorted(set(SOURCES.values()))],
    "count": len(E),
    "providers": [{"id": a, "name": b, "provider": c, "category": d} for a, b, c, d in PROVIDERS],
    "classes": [{"id": a, "label": b, "group": c, "unit": d, "blurb": e} for a, b, c, d, e in CLASSES],
    "skus": E,
    "anatomy": {k: [{"provider": p, "parts": [{"text": t, "kind": kind, "meaning": d} for t, kind, d in segs]}
                    for p, segs in v] for k, v in ANATOMY.items()},
}
dest = ROOT / "skus" / "skus.json"
dest.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
print(f"wrote {dest.relative_to(ROOT)}: {len(E)} SKUs, {len(PROVIDERS)} providers, {len(CLASSES)} classes")
