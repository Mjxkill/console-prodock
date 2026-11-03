#!/usr/bin/env python3
"""Build the real-source gpu_accel integration bench in a unique /tmp tree.

Only immutable inputs are read. Verilator ccode goes to a /tmp build dir.
The generated sources are compiled one translation unit at a time instead of
Verilator's single --binary ALL.cpp, because this sandbox enforces a 512 MiB
per-process address-space limit and a 64 MiB file-size limit. Both make the
one-TU shortcut and the generated PCH fail for this design. Splitting is a
sandbox adaptation only; the RTL and testbench are unchanged.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(ROOT)
VERILATOR_ROOT = "/usr/share/verilator"

# Real R19 snapshot files needed by gpu_accel plus the qualified banked helper.
SOURCES = [
    "snapshot/gpu_accel.v", "snapshot/blitter.v", "snapshot/gpu_blit_dma.v",
    "snapshot/font_ram.v", "snapshot/gpu_raster.v", "snapshot/gpu_geometry.v",
    "snapshot/gpu_v1.v", "snapshot/gpu_copy565.v", "snapshot/gpu_triangle.v",
    "snapshot/gpu_texture_cache.v", "snapshot/gpu_geom_div.v",
    "snapshot/gpu_perspective.v", "snapshot/ddr_dcfifo.v", "snapshot/cdc_word.v",
    "primitives/luts.v", "banked/banked_words32.v",
    "owned/bench.sv", "owned/helpers.sv",
]
FONT = "snapshot/font8x16.hex"

CPPFLAGS = [
    "-Os", "-I.", "-I" + VERILATOR_ROOT + "/include",
    "-I" + VERILATOR_ROOT + "/include/vltstd",
    "-DVM_COVERAGE=0", "-DVM_SC=0", "-DVM_TRACE=0", "-DVM_TRACE_FST=0",
    "-DVM_TRACE_VCD=0", "-faligned-new", "-fcf-protection=none",
    "-Wno-bool-operation", "-Wno-overloaded-virtual", "-Wno-shadow",
    "-Wno-sign-compare", "-Wno-uninitialized", "-Wno-unused-but-set-parameter",
    "-Wno-unused-but-set-variable", "-Wno-unused-parameter",
    "-Wno-unused-variable", "-DVL_TIME_CONTEXT", "-fcoroutines",
]
GLOBALS = ["verilated.cpp", "verilated_timing.cpp", "verilated_threads.cpp"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_inputs():
    """Refuse to build if any declared immutable input changed."""
    inputs = json.load(open(os.path.join(WORK, "INPUTS.json")))["files"]
    hashes, bad = {}, []
    for item in inputs:
        p = os.path.join(WORK, item["path"])
        if not os.path.isfile(p):
            bad.append(("missing", item["path"]))
            continue
        got = sha256(p)
        hashes[item["path"]] = got
        if got != item["sha256"]:
            bad.append((item["path"], got, item["sha256"]))
    if bad:
        raise SystemExit("INPUT_HASH_FAIL %r" % (bad,))
    return hashes


def _write_compile_makefile(objdir, cpp):
    cpp_flags = " ".join(CPPFLAGS)
    objs = [os.path.splitext(os.path.basename(s))[0] + ".o" for s in cpp]
    objs += [os.path.splitext(n)[0] + ".o" for n in GLOBALS]
    lines = ["CXXFLAGS = " + cpp_flags, "OBJS = " + " ".join(objs),
             "all: tb_sim", "tb_sim: $(OBJS)",
             "\tg++ -o $@ $(OBJS) -pthread -lpthread -latomic", "%.o: %.cpp",
             "\tg++ $(CXXFLAGS) -c -o $@ $<"]
    for name in GLOBALS:
        stem = os.path.splitext(name)[0]
        lines += ["%s.o: %s/include/%s" % (stem, VERILATOR_ROOT, name),
                  "\tg++ $(CXXFLAGS) -c -o $@ $<"]
    with open(os.path.join(objdir, "Bench.mk"), "w") as f:
        f.write("\n".join(lines) + "\n")
    return objs


def build(verbose=True):
    hashes = verify_inputs()
    build_dir = tempfile.mkdtemp(prefix="gpuaccel-integ-")
    objdir = os.path.join(build_dir, "obj")
    for rel in SOURCES:
        shutil.copy2(os.path.join(WORK, rel),
                     os.path.join(build_dir, os.path.basename(rel)))
    shutil.copy2(os.path.join(WORK, FONT), os.path.join(build_dir, "font8x16.hex"))

    gen_cmd = [
        "verilator", "--cc", "--timing", "--main", "--exe", "-Wno-fatal",
        "-j", "2", "--output-split", "400", "--output-split-cfuncs", "400",
        "--top-module", "tb", "--Mdir", objdir, "-o", "tb_sim",
    ] + [os.path.basename(s) for s in SOURCES]
    log = os.path.join(build_dir, "build.log")
    if verbose:
        print("BUILD_DIR", build_dir)
        print("GEN_COMMAND", " ".join(gen_cmd))
    p = subprocess.run(gen_cmd, cwd=build_dir, capture_output=True, text=True)
    with open(log, "w") as f:
        f.write("$ " + " ".join(gen_cmd) + "\n" + p.stdout + p.stderr)
    if p.returncode != 0:
        sys.stderr.write(p.stdout[-2000:] + p.stderr[-8000:])
        raise SystemExit("VERILATOR_GEN_FAIL rc=%d log=%s" % (p.returncode, log))

    cpp = sorted(os.path.join(objdir, n) for n in os.listdir(objdir)
                 if n.startswith("Vtb") and n.endswith(".cpp"))
    objs = _write_compile_makefile(objdir, cpp)
    jobs = os.environ.get("BENCH_COMPILE_JOBS", "16")
    make_cmd = ["make", "-j", jobs, "-f", "Bench.mk"]
    if verbose:
        print("MAKE_COMMAND", " ".join(make_cmd), len(objs), "units")
    p = subprocess.run(make_cmd, cwd=objdir, capture_output=True, text=True)
    with open(log, "a") as f:
        f.write("$ " + " ".join(make_cmd) + "\n" + p.stdout[-4000:] + p.stderr[-8000:])
    if p.returncode != 0:
        sys.stderr.write(p.stdout[-3000:] + p.stderr[-8000:])
        raise SystemExit("CXX_COMPILE_FAIL rc=%d log=%s" % (p.returncode, log))

    binary = os.path.join(objdir, "tb_sim")
    if not os.path.isfile(binary):
        raise SystemExit("LINK_OUTPUT_MISSING " + binary)
    manifest = {
        "build_dir": build_dir,
        "generation_command": " ".join(gen_cmd),
        "compile_makefile": os.path.join(objdir, "Bench.mk"),
        "compile_command": "make -j %s -f Bench.mk" % jobs,
        "link_command": "g++ -o tb_sim <objects> -pthread -lpthread -latomic",
        "compile_jobs": int(jobs),
        "translation_units": len(objs),
        "inputs": {s: hashes.get(s, sha256(os.path.join(WORK, s))) for s in SOURCES},
        "font": sha256(os.path.join(WORK, FONT)),
        "verilator": subprocess.run(["verilator", "--version"], capture_output=True,
                                    text=True).stdout.strip(),
        "binary": binary,
        "log": log,
    }
    with open(os.path.join(build_dir, "build_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    if verbose:
        print("BUILD_OK", binary)
    return manifest


if __name__ == "__main__":
    build()
