#!/usr/bin/env python3
"""Run the integration bench and its expected-failing test mutants.

Returns nonzero if any positive/negative case fails or if a mutant is not
detected by the unchanged packet scoreboard. RESULTS.json records the actual
exit statuses and captured output; limitations are stated, not hidden.
"""
import datetime
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
import build  # noqa: E402

# Each entry is (id, hclk_half_ps, mem_clk_half_ps, required_marker, extra_args).
# extra_args are real plusargs appended after the clock configuration.
POS = [
    ("positive_80_75", 6250, 6667, "POSITIVE_PASS", ()),
    ("positive_125_124p9", 4000, 4003, "POSITIVE_PASS", ()),
    ("positive_125_125p2", 4000, 3994, "POSITIVE_PASS", ()),
    ("stress_80_75", 6250, 6667, "STRESS_PASS", ("+STRESS",)),
]
NEG = [("sentinel_w7_80_75", 6250, 6667, "SENTINEL_REJECT_PASS", ())]
MUT = [
    ("mutant_swap_dims_80_75", 6250, 6667, "MUT_SWAP", ("+MUT_SWAP",)),
    ("mutant_duplicate_word_80_75", 6250, 6667, "MUT_DUP", ("+MUT_DUP",)),
    # Same source mutation, but exercised through the bounded stress path so
    # the stress scoreboard itself is shown to be sensitive.
    ("mutant_swap_dims_stress_80_75", 6250, 6667, "MUT_SWAP",
     ("+MUT_SWAP", "+STRESS")),
]


def run_one(binary, cwd, name, hh, hm, marker, extra=(), expect_fail=False):
    cmd = [binary, "+HALF_H=%d" % hh, "+HALF_M=%d" % hm]
    cmd.extend(extra)
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=180)
        rc = p.returncode
        out = p.stdout + p.stderr
        timed_out = False
    except subprocess.TimeoutExpired as e:
        rc = 124
        out = (e.stdout or "") + (e.stderr or "") + "\nWATCHDOG_TIMEOUT"
        timed_out = True
    elapsed = time.time() - t0
    if expect_fail:
        passed = rc != 0 and "MUTANT_DETECTED" in out and not timed_out
        expected = "nonzero + MUTANT_DETECTED"
    else:
        passed = rc == 0 and marker in out and not timed_out
        expected = "zero + " + marker
    print("%-30s rc=%3d %s (%.3fs)" % (name, rc, "PASS" if passed else "FAIL", elapsed))
    if not passed:
        print(out[-4000:])
    return {
        "id": name,
        "clock_half_ps": [hh, hm],
        "command": " ".join(cmd),
        "extra_args": list(extra),
        "expected": expected,
        "returncode": rc,
        "elapsed_seconds": round(elapsed, 6),
        "watchdog_timeout": timed_out,
        "marker_seen": marker in out,
        "mutant_detected": "MUTANT_DETECTED" in out,
        "pass": passed,
        "output_tail": out[-2500:],
    }


def main():
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    manifest = build.build(verbose=True)
    binary, cwd = manifest["binary"], manifest["build_dir"]
    cases = []
    for name, hh, hm, mark, extra in POS:
        cases.append(run_one(binary, cwd, name, hh, hm, mark, extra, False))
    for name, hh, hm, mark, extra in NEG:
        cases.append(run_one(binary, cwd, name, hh, hm, mark, extra, False))
    for name, hh, hm, mark, extra in MUT:
        cases.append(run_one(binary, cwd, name, hh, hm, mark, extra, True))

    ok = all(c["pass"] for c in cases)
    results = {
        "task": "command transport coverage 2026-11-03",
        "started_utc": started,
        "finished_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "build": {
            "dir": cwd,
            "generation_command": manifest["generation_command"],
            "compile_command": manifest["compile_command"],
            "link_command": manifest["link_command"],
            "compile_jobs": manifest["compile_jobs"],
            "translation_units": manifest["translation_units"],
            "verilator": manifest["verilator"],
            "inputs": manifest["inputs"],
            "font_sha256": manifest["font"],
            "log": manifest["log"],
        },
        "cases": cases,
        "passed": ok,
        "limits": [
            "Transaction-level testbench; DDR ports are a deterministic transaction driver, not a DRAM/PHY/board model.",
            "Two banked neo_command_ff128 instances are pin-level shadows driven from real RTL pins; equality of their registered DO with consumed words is NOT a full substituted mapped-application proof.",
            "The banked helper is compiled with owned/helpers.sv DFFRE INIT/RESET/CE shim because Verilator 5.020 rejects the vendor extract deassign; GSR timing and the vendor primitive are not qualified.",
            "No synthesis, place-and-route, static timing, CDC/metastability proof, card programming, hardware mask6014 or firstFIFO cause claim is made.",
            "Clock ratios are simulation half-periods (80/75, 125/124.9, 125/125.2 MHz equivalents); no physical jitter or clock-tree skew is modelled.",
            "Mutants alter only the bench command source; immutable RTL is unchanged. They prove scoreboard sensitivity, not a hardware defect.",
            "The stress case uses a finite test-side DDR not-ready gate and a bounded 40-command backlog; it is not an infinite or random traffic test.",
        ],
    }
    with open(os.path.join(ROOT, "RESULTS.json"), "w") as f:
        json.dump(results, f, indent=1)
    print("RESULTS", "PASS" if ok else "FAIL", os.path.join(ROOT, "RESULTS.json"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
