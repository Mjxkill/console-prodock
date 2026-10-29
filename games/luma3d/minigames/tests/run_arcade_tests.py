#!/usr/bin/env python3
"""Independent tests for additive arcade modules; never changes v1 inputs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--module", choices=("simon", "shooter", "platform"), required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    module = args.module
    inputs = [root / f"l3_{module}.c", root / f"l3_{module}.h",
              root / "l3_minigames.h", root / f"tests/test_{module}.c",
              root / f"{module.upper()}.md", Path(__file__).resolve()]
    initial = {str(x.relative_to(root)): sha(x) for x in inputs}
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    entries = {}
    env = dict(os.environ, ASAN_OPTIONS="detect_leaks=0:halt_on_error=1",
               UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
    with tempfile.TemporaryDirectory(prefix="luma-arcade-") as tmp:
        for mode in ("strict", "asan_ubsan"):
            binary = Path(tmp) / mode
            flags = ["-O2"] if mode == "strict" else ["-O1", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
            command = [os.environ.get("CC", "cc"), "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", *flags,
                       str(root / f"l3_{module}.c"), str(root / f"tests/test_{module}.c"), "-o", str(binary)]
            result = subprocess.run(command, text=True, capture_output=True)
            (out / (mode + "_compile.log")).write_text(result.stdout + result.stderr)
            entry = {"compile_exit": result.returncode, "command": command}
            if not result.returncode:
                trace = out / (mode + ".trace")
                run = subprocess.run([str(binary), str(trace)], text=True, capture_output=True, env=env, timeout=120)
                (out / (mode + ".log")).write_text(run.stdout + run.stderr)
                print(run.stdout + run.stderr, end="")
                entry.update(test_exit=run.returncode, trace_sha256=sha(trace) if trace.exists() else None)
            entries[mode] = entry
    final = {str(x.relative_to(root)): sha(x) for x in inputs}
    golden = sha(root / f"tests/traces/{module}_win.trace")
    passed = initial == final and all(x.get("compile_exit") == 0 and x.get("test_exit") == 0 and
                                     x.get("trace_sha256") == golden for x in entries.values())
    report = {"status": "PASS" if passed else "FAIL", "module": module, "source_sha256": final,
              "inputs_stable": initial == final, "golden_trace_sha256": golden, "results": entries,
              "limitations": ["LeakSanitizer disabled because ptrace monitor is incompatible",
                              "Host-only logic tests, no FPGA/timing/board qualification"]}
    (out / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"{report['status']}: {out / 'result.json'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
