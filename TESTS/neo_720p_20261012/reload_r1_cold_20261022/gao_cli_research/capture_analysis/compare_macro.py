#!/usr/bin/env python3
"""Read-only extraction of routed AE350/PLL interfaces; writes only this directory."""
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
BUILDS = {
    "r10": ("console_neo_n56r10_gao_startup", "console_neo.vo"),
    "r8": ("console_neo_n56r8_hdmi_sg4", "console_neo.vo"),
    "prodock": ("gpu_geometry_g22r0", "console_gpu_geometry_g22r0.vo"),
}
SOURCES = [
    "tang/rtl/board/ae350_soc.v",
    "tang/rtl/board/pll_init.v",
    "tang/rtl/board/riscv_ae350_soc_ext/riscv_ae350_soc.v",
    "tang/rtl/board/riscv_ae350_soc_ext/cfg/riscv_ae350_config.v",
    "tang/rtl/board/riscv_ae350_soc_ext/cfg/gw_itcm_config.v",
    "tang/rtl/ae350/pll_ae350/gowin_pll_ae350.v",
    "tang/rtl/ae350/pll_ae350/gowin_pll_ae350_mod.v",
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def extract(text, kind, name=None):
    pattern = rf"^{kind}\s+([^\s]+)\s*\((.*?)\n\);"
    found = [m for m in re.finditer(pattern, text, re.S | re.M)
             if name is None or m[1] == name]
    assert len(found) == 1, (kind, name, len(found))
    m = found[0]
    ports = {n: re.sub(r"\s+", "", value)
             for n, value in re.findall(r"\.(\w+)\((.*?)\)(?:,|\s*$)", m[2], re.S)}
    assert ports
    params = {k: v for k, v in re.findall(
        rf"^defparam\s+{re.escape(m[1])}\s+\.(\w+)=(.*?);$", text, re.M)}
    return {"instance": m[1], "line": text[:m.start()].count("\n") + 1,
            "ports": ports, "parameters": params}


def differences(a, b):
    return {k: {"r10": a.get(k), "other": b.get(k)}
            for k in sorted(a.keys() | b.keys()) if a.get(k) != b.get(k)}


results = {}
for key, (build, filename) in BUILDS.items():
    base = ROOT / "tang/impl" / build
    path = base / "impl/pnr" / filename
    raw = path.read_bytes()
    text = raw.decode()
    item = {"file": str(path.relative_to(ROOT)), "sha256": sha(raw),
            **extract(text, "AE350_SOC")}
    item["pll"] = extract(text, "PLL", r"\u_pll_ae350/u_pll/PLL_inst")
    item["sources"] = {}
    for rel in SOURCES:
        p = base / "source" / rel
        item["sources"][rel] = sha(p.read_bytes()) if p.exists() else None
    assert path.read_bytes() == raw, "source modified during review"
    results[key] = item

report = {"builds": results, "comparisons": {}}
for other in ["r8", "prodock"]:
    report["comparisons"][other] = {
        "ports": differences(results["r10"]["ports"], results[other]["ports"]),
        "macro_parameters": differences(results["r10"]["parameters"], results[other]["parameters"]),
        "pll_ports": differences(results["r10"]["pll"]["ports"], results[other]["pll"]["ports"]),
        "pll_parameters": differences(results["r10"]["pll"]["parameters"], results[other]["pll"]["parameters"]),
        "source_sha256": differences(results["r10"]["sources"], results[other]["sources"]),
    }

(HERE / "macro_comparison.json").write_text(json.dumps(report, indent=2) + "\n")
for other, diff in report["comparisons"].items():
    print(other, {k: len(v) for k, v in diff.items()})
    if other == "r8":
        assert not diff["ports"] and not diff["macro_parameters"]
        assert not diff["pll_parameters"]
print("PASS: routed macro ports compared; source files unchanged; no hardware accessed")
