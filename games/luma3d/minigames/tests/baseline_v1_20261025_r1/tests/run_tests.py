#!/usr/bin/env python3
"""Compile and verify the freestanding mini-game logic; no board access."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True,
                        help="New directory for logs, command traces and hashes")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    traces = out / "traces"
    traces.mkdir()
    inputs = [root / "l3_minigames.c", root / "l3_minigames.h",
              root / "README.md", root / "tests/test_minigames.c",
              Path(__file__).resolve()]
    before = {str(p.relative_to(root)): digest(p) for p in inputs}
    results = {}
    env = dict(os.environ)
    # LSan cannot operate under the execution environment's ptrace monitor.
    # ASan bounds/use-after-free and UBSan remain enabled. Engines use no heap.
    env["ASAN_OPTIONS"] = "detect_leaks=0:halt_on_error=1"
    env["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=1"
    with tempfile.TemporaryDirectory(prefix="luma-minigames-") as build:
        for mode in ("strict", "asan_ubsan"):
            binary = Path(build) / mode
            command = [os.environ.get("CC", "cc"), "-std=c99", "-Wall", "-Wextra",
                       "-Werror", "-pedantic", "-O2" if mode == "strict" else "-O1"]
            if mode != "strict":
                command += ["-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
            command += [str(root / "l3_minigames.c"),
                        str(root / "tests/test_minigames.c"), "-o", str(binary)]
            compiled = subprocess.run(command, capture_output=True, text=True)
            (out / (mode + "_compile.log")).write_text(compiled.stdout + compiled.stderr)
            entry = {"compile_exit": compiled.returncode, "command": command}
            if compiled.returncode == 0:
                tested = subprocess.run([str(binary), str(traces)], capture_output=True,
                                        text=True, env=env, timeout=120)
                (out / (mode + ".log")).write_text(tested.stdout + tested.stderr)
                entry["test_exit"] = tested.returncode
                print(tested.stdout, end="")
                if tested.stderr:
                    print(tested.stderr, end="")
            results[mode] = entry
    after = {str(p.relative_to(root)): digest(p) for p in inputs}
    trace_hashes = {p.name: digest(p) for p in sorted(traces.glob("*.trace"))}
    golden = root / "tests/traces"
    trace_match = len(trace_hashes) == 5 and all(
        (golden / name).is_file() and digest(golden / name) == value
        for name, value in trace_hashes.items())
    passed = (before == after and trace_match and len(results) == 2 and
              all(r.get("compile_exit") == 0 and r.get("test_exit") == 0 for r in results.values()))
    report = {"status": "PASS" if passed else "FAIL", "source_sha256": after,
              "inputs_stable": before == after, "command_traces_sha256": trace_hashes,
              "golden_traces_match": trace_match, "results": results,
              "limitations": ["LeakSanitizer disabled: incompatible with ptrace execution monitor",
                              "Host software tests only; no FPGA, timing or board qualification"]}
    (out / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"{report['status']}: {out / 'result.json'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
