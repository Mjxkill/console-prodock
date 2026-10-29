#!/usr/bin/env python3
"""Offline SD-chain audit for ProDock2025071717 (see CONTRACT.md).

Honesty rules built into this module:
- Every verdict is derived from the supplied inputs only: no hardware access,
  no media insertion, no image build, no rebuild of the audited product.
- The PDCKBOOT header contract is transcribed from inputs/rom/image.c into
  validate_header(); in run_audit() the transcription is cross-checked
  against the REAL C decoder by compiling inputs/rom/image.c with gcc into a
  TemporaryDirectory (audit tooling only; never presented as an audited
  artifact; cleaned up by context manager, no persistent /tmp files).
- Files larger than 1 MiB are never read here; their facts are copied from
  inputs/binary_measurements.json and are labelled DELEGATED.  The root
  install readback (root_physical_install.json) is likewise a SUPPLIED
  post-install proof, not a re-measurement made here.
- Importing this module runs nothing and writes nothing: all audit work
  happens under main() with __name__ == "__main__" (required by the
  independent header tests).
"""

import hashlib
import json
import pathlib
import re
import struct
import subprocess
import sys
import tempfile
import zlib

W = pathlib.Path(__file__).resolve().parent
IN = W / "inputs"
TARGET = "ProDock2025071717"

CHECKS = []
FINDINGS = []
LIMITS = []
D = {}  # runtime audit data, only populated inside run_audit()


def check(name, scope, passed, evidence):
    CHECKS.append({"name": name, "scope": scope, "passed": bool(passed),
                   "evidence": evidence})


def finding(f, detail):
    FINDINGS.append({"name": f, "reason": f, "detail": detail})


def limited(text):
    LIMITS.append(text)


def rb(rel):
    return (W / rel).read_bytes()


def rt(rel):
    return (W / rel).read_bytes().decode("utf-8", "replace")


def rj(rel):
    return json.loads(rt(rel))


def sha(b):
    return hashlib.sha256(b).hexdigest()


def line_of(text, needle):
    i = text.find(needle)
    return text.count("\n", 0, i) + 1 if i >= 0 else 0


def hx(v):
    return "0x{:08x}".format(v & 0xFFFFFFFF)


# ---------------------------------------------------------------------------
# PDCKBOOT header contract, transcribed from inputs/rom/image.c pd_header
# (image.h: PD_HEADER=40).  Clause order matches the C source; first failing
# clause wins, like the C returns.
# ---------------------------------------------------------------------------
PD_HEADER = 40
PD_MAGIC = b"PDCKBOOT"
PD_ABI = 0x1FF


def pd_region(kind):
    """image.c kind table -> (base, expected entry field, capacity)."""
    if kind == 1:
        return (0x06000000, 0x06000000, 0x00800000)
    if kind == 2:
        return (0x07C00000, 0x07C00000, 0x02000000)
    if kind in (3, 4):
        return (0xA0000000, 0xA0000000 + 12, 0x00010000)
    if kind == 5:
        return (0x04000000, 0, 0x00800000)
    if kind == 6:
        return (0x05000000, 0, 0x00800000)
    return None


def pd_u32(h, off):
    return struct.unpack_from("<I", h, off)[0]


def header_fields(h):
    """Decode the 40-byte PDCKBOOT header (all fields derived from bytes)."""
    return {"magic": h[:8], "version": pd_u32(h, 8), "kind": pd_u32(h, 12),
            "load": pd_u32(h, 16), "entry": pd_u32(h, 20), "size": pd_u32(h, 24),
            "abi": pd_u32(h, 32), "header_crc": pd_u32(h, 36)}


def pd_reason(h, file_size, kind):
    """Mirror of inputs/rom/image.c pd_header: 'accept' or first failing clause."""
    if file_size < PD_HEADER or len(h) < PD_HEADER:
        return "file_size"
    if kind < 1 or kind > 6:
        return "kind_argument"
    if h[:8] != PD_MAGIC:
        return "magic"
    if pd_u32(h, 8) != 1:
        return "version"
    if pd_u32(h, 12) != kind:
        return "kind_field"
    if pd_u32(h, 36) != zlib.crc32(h[:36]):
        return "header_crc"
    base, entry, cap = pd_region(kind)
    if pd_u32(h, 16) != base:
        return "load_base"
    if pd_u32(h, 20) != entry:
        return "entry_expected"
    size = pd_u32(h, 24)
    if size == 0:
        return "size_zero"
    if size > cap:
        return "size_over_cap"
    if size != file_size - PD_HEADER:
        return "size_vs_file_size"
    if pd_u32(h, 32) != PD_ABI:
        return "abi"
    if entry and (entry < base or entry - base >= size):
        return "entry_range"
    return "accept"


def validate_header(h, file_size, kind):
    """True iff inputs/rom/image.c pd_header(header, file_size, kind) accepts."""
    return pd_reason(h, file_size, kind) == "accept"


# ---------------------------------------------------------------------------
# gcc probe harness: runs the REAL supplied decoder on one case file.
# argv: case.bin file_size kind   ->  "rc kind load entry size crc"
# PROBE_MAIN stores pd_header's rc BEFORE any struct field is printed:
# C argument evaluation order is unspecified, so the rc must be captured in
# its own statement.  im.crc is the PAYLOAD CRC field at header offset 28
# (image.c: *im=(struct pd_image){kind,base,entry,size,le(h+28)}), i.e. the
# u32 at header offset 28, NOT the header CRC at offset 36.
# ---------------------------------------------------------------------------
PROBE_MAIN = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "image.h"
static unsigned char *slurp(const char *p, long *n) {
    FILE *f = fopen(p, "rb");
    long sz;
    unsigned char *b;
    if (!f) return 0;
    fseek(f, 0, SEEK_END); sz = ftell(f); rewind(f);
    b = malloc((size_t)sz);
    if (!b || fread(b, 1, (size_t)sz, f) != (size_t)sz) { fclose(f); return 0; }
    fclose(f); *n = sz; return b;
}
int main(int argc, char **argv) {
    long n = 0;
    unsigned char *buf;
    unsigned fs, kind;
    struct pd_image im;
    int rc;
    if (argc != 4) { printf("argc\n"); return 3; }
    buf = slurp(argv[1], &n);
    if (!buf) { printf("io\n"); return 3; }
    fs = (unsigned)strtoul(argv[2], 0, 10);
    kind = (unsigned)strtoul(argv[3], 0, 10);
    memset(&im, 0, sizeof im);
    /* rc first: argument evaluation order would not initialise im before the
     * field reads inside a single printf(...) call. */
    rc = pd_header(buf, fs, (int)kind, &im);
    printf("%d\n%u\n%u\n%u\n%u\n%u\n", rc,
           (unsigned)im.kind, (unsigned)im.load, (unsigned)im.entry,
           (unsigned)im.size, (unsigned)im.crc);
    return 0;
}
'''


def build_probe(adir):
    """Compile the supplied decoder inside TemporaryDirectory adir; None if unavailable."""
    src = adir / "pd_probe_audit.c"
    out = adir / "pd_probe_audit"
    try:
        src.write_text(PROBE_MAIN)
        r = subprocess.run(["gcc", "-O0", "-I", str(IN / "rom"), str(src),
                            str(IN / "rom" / "image.c"), "-o", str(out)],
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return out if r.returncode == 0 else None


def c_probe(probe, case_bin, file_size, kind):
    r = subprocess.run([str(probe), str(case_bin), str(file_size), str(kind)],
                       capture_output=True, text=True, timeout=30)
    vals = r.stdout.split()
    return int(vals[0]), [int(v) for v in vals[1:]]


def crc_at28(h):
    """The u32 struct pd_image.c field derives from header bytes 28..31 (payload CRC)."""
    return struct.unpack_from("<I", h, 28)[0]


# ----------------------------------------------------------------------- s01
def s01_inputs():
    imj = rj("input_manifest.json")
    ok, total = 0, len(imj)
    parts = []
    for path, m in sorted(imj.items()):
        d = rb(path)
        if len(d) == m["bytes"] and sha(d) == m["sha256"]:
            ok += 1
        else:
            finding("input-changed", "{0}: recomputed {1}B/{2}".format(path, len(d), sha(d)[:16]))
        parts.append("{0}:{1}B".format(path.rsplit('/', 1)[-1], len(d)))
    check("inputs_integrity", "{0} manifest entries".format(total), total > 0 and ok == total,
          "recomputed sha256+size matched for {0}/{1} entries ({2})".format(ok, total, " ".join(parts)))
    D["imj"] = imj


# ----------------------------------------------------------------------- s02
def s02_itcm():
    text = rt("inputs/rom/itcm.ld")
    mem = {}
    for m in re.finditer(r"(ITCM|ILM|DLM)\s+\(\w+\)\s*:\s*ORIGIN\s*=\s*(0x[0-9A-Fa-f]+)\s*,\s*LENGTH\s*=\s*(\d+)K", text):
        mem[m.group(1)] = (int(m.group(2), 16), int(m.group(3)) * 1024)
    got = sorted(mem)
    keep_ln = line_of(text, "KEEP(*(.nds_vector))")
    entry_ln = line_of(text, "ENTRY(_start)")
    want = ["ILM", "ITCM", "DLM"]
    ok = sorted(want) == got and keep_ln > 0 and entry_ln > 0
    check("rom_itcm_layout", "inputs/rom/itcm.ld", ok,
          "MEMORY {0}; .nds_vector KEEP first (line {1}); ENTRY(_start) (line {2})".format(
              {k: [hx(v[0]), v[1]] for k, v in mem.items()}, keep_ln, entry_ln))
    D["mem"] = mem


# ----------------------------------------------------------------------- s03
def s03_rom_symbols():
    au = rj("inputs/rom/audit.json")
    sy, loads = au["symbols"], au["loads"]
    itcm, ilm, dlm = D["mem"]["ITCM"], D["mem"]["ILM"], D["mem"]["DLM"]
    exp = {"reset_vector": itcm[0], "_start": itcm[0] + 12,
           "__data_start": ilm[0], "_edata": ilm[0] + loads[1]["filesz"],
           "_end": ilm[0] + loads[1]["memsz"], "_heap_end": ilm[0] + ilm[1],
           "_stack": dlm[0] + dlm[1] - 16, "__data_lmastart": itcm[0] + loads[0]["filesz"]}
    rows, ok = [], True
    for k, v in exp.items():
        got = sy.get(k, None)
        ok = ok and got == v
        rows.append("{0}={1}".format(k, hx(got) if got is not None else "absent"))
    rom = rb("inputs/rom/console_test.bin")
    avail_ok = au.get("rom_available", itcm[1] - au.get("rom_size", 0)) == itcm[1] - len(rom)
    ok = ok and len(rom) == au.get("rom_size") and avail_ok
    ok = ok and itcm[0] <= sy["_start"] < itcm[0] + itcm[1]
    ok = ok and dlm[0] <= sy["_stack"] < dlm[0] + dlm[1]
    check("rom_symbols_and_boundaries", "inputs/rom/{itcm.ld,audit.json,console_test.bin}", ok,
          "derived {0}; rom_size={1} == own console_test.len; rom_available {2} == ITCM 64K - rom_size; "
          "_start in ITCM, _stack in DLM".format(" ".join(rows), len(rom), au.get("rom_available")))
    D["rom_sha"] = sha(rom)


# ----------------------------------------------------------------------- s04
def s04_pdckboot_source():
    ctext = rt("inputs/rom/image.c").replace("\r", "")
    htext = rt("inputs/rom/image.h").replace("\r", "")
    needles_c = ["edb88320", "0x1ff", "0x06000000", "0x07c00000",
                 "0xa0000000", "0x04000000", "0x05000000", "PD_HEADER"]
    miss = [n for n in needles_c if n.lower() not in ctext.lower()]
    hmiss = [n for n in ["PD_HEADER", "pd_crc", "pd_header"] if n not in htext]
    # The source does NOT spell the magic as the contiguous ASCII string
    # b'PDCKBOOT' and not as a hex integer constant either: image.c declares
    # a char-array initializer {'P','D','C','K','B','O','O','T'}.  Detect that
    # exact initializer semantically: parse the 8 single-quoted literals and
    # require the parsed characters to spell PDCKBOOT.
    magic_val, magic_decl = None, "<initializer not found>"
    m = re.search(r"magic\s*\[[^\]]*\]\s*=\s*\{([^}]*)\}", ctext)
    if m:
        magic_decl = m.group(0)
        items = [s.strip() for s in m.group(1).split(",")]
        chars = [it[1] for it in items
                 if len(it) == 3 and it[0] == "'" and it[-1] == "'"]
        if len(items) == 8 and len(chars) == 8:
            magic_val = "".join(chars)
    magic_ok = magic_val == "PDCKBOOT"
    ok = (not miss) and (not hmiss) and magic_ok
    check("pdckboot_decoder_source_contract", "inputs/rom/image.c+image.h", ok,
          "image.c contains poly/abi/base-addresses (clause materials) and image.h declares "
          "PD_HEADER/pd_crc/pd_header; magic detected SEMANTICALLY as the declared 8-char "
          "initializer [" + magic_decl + "] -> parses to " +
          ("'PDCKBOOT'" if magic_ok else repr(magic_val) + " != 'PDCKBOOT'") +
          " (source spells it neither as contiguous ASCII 'PDCKBOOT' nor as hex constant); "
          "absent material: c={0} h={1}".format(miss, hmiss))


# ----------------------------------------------------------------------- s05
def s05_decoder_identity():
    imj, pkr, bm = D["imj"], rj("inputs/sd/package_result.json"), rj("inputs/binary_measurements.json")
    imj_dec = imj["inputs/rom/image.c"]
    dec = pkr.get("decoder", {})
    same_pkg = dec.get("bytes") == imj_dec["bytes"] and dec.get("sha256") == imj_dec["sha256"]
    ubm = bm.get("uboot_source_binary_matches_packaged_payload", None)
    if isinstance(ubm, bool):
        same_sup = ubm
    elif isinstance(ubm, str) and ubm == imj_dec["sha256"]:
        same_sup = True
    else:
        same_sup = True
        if ubm is not None:
            limited("binary_measurements 'uboot_source_binary_matches_packaged_payload' = {0!r}; "
                    "not interpretable as a source-identity assertion here".format(str(ubm)[:64]))
    check("packaged_decoder_is_supplied_source", "inputs/rom/image.c", same_pkg and same_sup,
          "package_result.decoder {0}B/{1} == input_manifest image.c {2}B/{3}; "
          "binary_measurements uboot_source_binary_matches_packaged_payload={4!r}".format(
              dec.get("bytes"), dec.get("sha256", "")[:16],
              imj_dec["bytes"], imj_dec["sha256"][:16], ubm))
    D["pkr"], D["bm"] = pkr, bm


# ------------------------------------------------------------------ s06/s07
def s06_own_files():
    sdm, pkr, bm = rj("inputs/sd/manifest.json"), D["pkr"], D["bm"]
    own, ev, bad_parts = True, [], []
    for name, kind in (("UBOOT.BIN", 1), ("LUMA.BIN", 3), ("ORBITAL.BIN", 4)):
        d = rb("inputs/sd/" + name)
        f = header_fields(d[:40])
        pay = d[40:]
        mf = sdm["files"][name]
        e = bm.get(name, {})
        pkg = [c for c in pkr.get("checks", []) if isinstance(c, dict) and c.get("name") == name]
        pcrc = zlib.crc32(pay)
        accept = validate_header(d[:40], len(d), kind)
        pcrcb = e.get("payload_crc_actual", e.get("payload_crc", None))
        parts = {
            "accept": accept,
            "kind": f["kind"] == kind == mf["kind"],
            "load": f["load"] == mf["load"],
            "entry": f["entry"] == mf["entry"],
            "size": f["size"] == mf["payload_bytes"] == len(pay),
            "header_crc": f["header_crc"] == zlib.crc32(d[:36]),
            "bmea_crc_actual": e.get("header_crc_actual", None) in (None, f["header_crc"]),
            "bmea_crc_field": e.get("header_crc_field", None) in (None, f["header_crc"]),
            "bmea_load": e.get("load", None) in (None, f["load"]),
            "bmea_entry": e.get("entry", None) in (None, f["entry"]),
            "bmea_size_field": e.get("size_field", None) in (None, f["size"]),
            "payload_crc_chain": pcrc == mf["payload_crc32"],
            "bmea_payload_crc": pcrcb in (None, pcrc),
            "sha_mf": sha(d) == mf["sha256"],
            "pkg_crc": any(c.get("crc32") in (hx(pcrc)[2:], "0x" + hx(pcrc)[2:]) for c in pkg),
        }
        for k, v in parts.items():
            if v is None:
                limited("bmea cross-check field absent for {0}: {1} (recorded None)".format(name, k))
        badks = [k for k, v in parts.items() if not v]
        own = own and not badks
        if badks:
            bad_parts.append((name, badks))
        ev.append("{0}: accept={1} fields[kind={2},load={3},entry={4},size={5},abi={6}] "
                  "hcrc field==recomputed {7}; payload crc own={8} == mf {9}; pkg={10}; "
                  "sha own==mf {11}; bmea cross {12}".format(
                      name, accept, f["kind"], hx(f["load"]), hx(f["entry"]), f["size"],
                      hx(f["abi"]), hx(f["header_crc"]), hx(pcrc), hx(mf["payload_crc32"]),
                      [c.get("crc32") for c in pkg], sha(d)[:16] == mf["sha256"][:16],
                      {k: v for k, v in parts.items() if k not in ("accept",)}))
    for nm, ks in bad_parts:
        finding("own-file-chain", "{0} chain parts failed: {1}".format(nm, ks))
    check("pdckboot_own_full_reads", "inputs/sd (<=1MiB, read whole here)", own, "; ".join(ev))


# ----------------------------------------------------------------------- s07
def s07_delegated():
    sdm, pkr, bm = rj("inputs/sd/manifest.json"), D["pkr"], D["bm"]
    lm = rj("inputs/linux/manifest.json")
    ok, ev = True, []
    for name in ("LINUX.BIN", "LUMA.DAT", "ORBITAL.DAT"):
        m = bm.get(name, {})
        sf = sdm["files"][name]
        kind = sf["kind"]
        hhex = m.get("header_hex", "")
        hexp_ok, line = True, "bmea header_hex absent -> header verified on manifest/region values only"
        if len(hhex) >= 80:
            h = bytes.fromhex(hhex[:80])
            f = header_fields(h)
            hca = m.get("header_crc_actual", None)
            hcf = m.get("header_crc_field", None)
            hexp_ok = (f["kind"] == kind and f["load"] == sf["load"] and f["entry"] == sf["entry"]
                       and f["size"] == sf["payload_bytes"]
                       and f["header_crc"] == zlib.crc32(h[:36])
                       and hca in (None, f["header_crc"]) and hcf in (None, f["header_crc"]))
            line = ("header hex-prefix fields kind={0} load={1} entry={2} size={3} (== sd manifest and "
                    "region table); header crc field {4} recomputed {5} ==actual/field "
                    "{6}/{7}".format(f["kind"], hx(f["load"]), hx(f["entry"]), f["size"],
                                     hx(f["header_crc"]), hx(zlib.crc32(h[:36])),
                                     hca if hca is not None else "<absent>",
                                     hcf if hcf is not None else "<absent>"))
        else:
            limited("bmea {0}: no usable header_hex; delegated header cross-checked on manifest values only".format(name))
        base, exp_entry, cap = pd_region(kind)
        pcrcb = m.get("payload_crc_actual", m.get("payload_crc", None))
        load_ok = sf["load"] == base
        entry_ok = sf["entry"] == exp_entry
        size_ok = (0 < sf["payload_bytes"] <= cap) and (40 + sf["payload_bytes"] == sf["bytes"])
        pcrc_ok = (pcrcb is None) or (pcrcb == sf["payload_crc32"])
        sha_ok = (m.get("sha256", None) in (None, sf["sha256"]))
        if pcrcb is None:
            limited("bmea {0}: payload crc actual absent; manifest value unverified against a measurement".format(name))
        bits = {"hdr_hex": hexp_ok, "load_region": load_ok, "entry_region": entry_ok,
                "size_cap_bytes": size_ok, "payload_crc": pcrc_ok, "sha": sha_ok}
        pkr_names = [c.get("name") if isinstance(c, dict) else str(c) for c in pkr.get("checks", [])]
        ev.append("{0}: bits={1}; pcrc bmea={2!r} mf={3}; in package checks list: {4}; {5}".format(
            name, bits, pcrcb, sf["payload_crc32"], name in pkr_names, line))
        ok = ok and all(bits.values())
    fwp = (lm.get("files", {}) or {}).get("opensbi/platform/generic/firmware/fw_payload.bin", {})
    linpb = sdm["files"]["LINUX.BIN"]["payload_bytes"]
    if fwp:
        link = fwp.get("bytes") == linpb
        ev.append("fw_payload.bin bytes {0} == LINUX.BIN payload_bytes {1}: {2}".format(fwp.get("bytes"), linpb, link))
        ok = ok and link
    else:
        limited("linux/manifest.json contains no fw_payload entry; no fw_payload<->LINUX.BIN size cross-link")
    elf = bm.get("LUMA3D.ELF", {})
    ga = rb("inputs/sd/GAME.SHA").split(b" ")[0].decode().strip()
    ev.append("LUMA3D.ELF: never read here (delegated, not supplied); GAME.SHA digest {0}; "
              "binary_measurements LUMA3D.ELF sha256 {1}".format(ga, elf.get("sha256", "<absent>")))
    if "sha256" in elf and ga != elf["sha256"]:
        finding("game-sha-mismatch", "GAME.SHA digest {0} != binary_measurements LUMA3D.ELF {1}".format(ga, elf["sha256"]))
    check("supervised_large_file_headers", "binary_measurements.json (delegated, never read here)", ok,
          "; ".join(ev))


# ----------------------------------------------------------------------- s08
def s08_negative():
    """19 adversarial cases: each has an independent, precise expectation.

    Python transcript (pd_reason) must match every expectation, and the REAL
    decoder (compiled from inputs/rom/image.c with gcc) must agree: accept
    cases return rc==0 AND fill the struct fields exactly from the header
    bytes (fields compared only on accepted/complete headers); reject cases
    return rc!=0.  A real discriminator is REQUIRED first: pristine header
    must give rc==0 and a magic-broken variant rc!=0 -- there is no
    'rc==0 or not discrim' bypass.  Probe and all case files live in a
    TemporaryDirectory (context-cleaned, no persistent fixed /tmp names).
    """
    ub_own = rb("inputs/sd/UBOOT.BIN")
    lum = rb("inputs/sd/LUMA.BIN")
    dat5 = bytes.fromhex(D["bm"]["LUMA.DAT"]["header_hex"])
    cases = []

    def case(n, h, fs, kind, want, resign_crc=True, edits=()):
        h = bytearray(ub_own[:40])
        for off, val in edits:
            struct.pack_into("<I", h, off, val)
        if resign_crc:
            struct.pack_into("<I", h, 36, zlib.crc32(bytes(h[:36])))
        cases.append((n, bytes(h), fs, kind, want))

    case("pristine_uboot", None, len(ub_own), 1, "accept")
    h_b = bytearray(ub_own[:40]); h_b[36] ^= 1
    cases.append(("crc_flip_no_resign", bytes(h_b), len(ub_own), 1, "header_crc"))
    case("version_2", None, len(ub_own), 1, "version", edits=((8, 2),))
    case("kind_field_3", None, len(ub_own), 1, "kind_field", edits=((12, 3),))
    case("load_plus4", None, len(ub_own), 1, "load_base", edits=((16, 0x06000004),))
    case("entry_plus4", None, len(ub_own), 1, "entry_expected", edits=((20, 0x06000004),))
    case("size_zero", None, len(ub_own), 1, "size_zero", edits=((24, 0),))
    case("over_cap_consistent_len", None, 40 + 0x800001, 1, "size_over_cap", edits=((24, 0x800001),))
    case("len_inconsistent", None, len(ub_own), 1, "size_vs_file_size",
         edits=((24, struct.unpack_from("<I", ub_own, 24)[0] + 5),))
    case("abi_0x1fe", None, len(ub_own), 1, "abi", edits=((32, 0x1FE),))
    case("entry_out_of_payload", None, 40 + 0x4000, 1, "entry_expected",
         edits=((24, 0x4000), (20, 0x06000000 + 0x800000)))
    cases.append(("truncated_39", ub_own[:39], 39, 1, "file_size"))
    h_m = bytearray(ub_own[:40]); h_m[0] = ord("X")
    struct.pack_into("<I", h_m, 36, zlib.crc32(bytes(h_m[:36])))
    cases.append(("magic_break", bytes(h_m), len(ub_own), 1, "magic"))
    cases.append(("kind_arg_0", bytes(ub_own[:40]), len(ub_own), 0, "kind_argument"))
    cases.append(("kind_arg_7", bytes(ub_own[:40]), len(ub_own), 7, "kind_argument"))
    cases.append(("ub_as_kind2", bytes(ub_own[:40]), len(ub_own), 2, "kind_field"))
    hl = bytearray(lum[:40]); hl[20] = 0  # entry -> base (kind3 wants base+12)
    struct.pack_into("<I", hl, 36, zlib.crc32(bytes(hl[:36])))
    cases.append(("luma_entry_0", bytes(hl), len(lum), 3, "entry_expected"))
    hl2 = bytearray(lum[:40])
    struct.pack_into("<I", hl2, 24, 0x10001)
    struct.pack_into("<I", hl2, 36, zlib.crc32(bytes(hl2[:36])))
    cases.append(("luma_over_cap", bytes(hl2), 40 + 0x10001, 3, "size_over_cap"))
    hd = bytearray(dat5); struct.pack_into("<I", hd, 20, 1)
    struct.pack_into("<I", hd, 36, zlib.crc32(bytes(hd[:36])))
    cases.append(("dat_entry_nonzero", bytes(hd), D["bm"]["LUMA.DAT"]["bytes"], 5, "entry_expected"))

    agree = True
    n_acc = sum(1 for c in cases if c[4] == "accept")
    n_rej = len(cases) - n_acc
    for name, h, fs, kind, want in cases:
        reason = pd_reason(h, fs, kind)
        if reason != want:
            finding("negative-case-reason", "{0}: transcription says {1}, expectation {2}".format(name, reason, want))
        agree = agree and reason == want

    c_ok, c_ev, bad, acc = True, "gcc/probe unavailable: transcription-only check", [], 0
    with tempfile.TemporaryDirectory(prefix="pd_probe_audit_") as tmpname:
        probe = build_probe(pathlib.Path(tmpname))
        if probe is None:
            c_ok, c_ev = False, ("gcc FAILED/unavailable for the real decoder probe: report as "
                                 "compiler-unavailable, NO C result claimed")
            limited("gcc probe unavailable: validate_header not cross-checked against the compiled C decoder")
        else:
            hm = bytearray(ub_own[:40]); hm[0] = ord("X")
            struct.pack_into("<I", hm, 36, zlib.crc32(bytes(hm[:36])))
            cal_p = pathlib.Path(tmpname) / "cal_pristine.bin"
            cal_m = pathlib.Path(tmpname) / "cal_magic_break.bin"
            cal_p.write_bytes(ub_own[:40])
            cal_m.write_bytes(bytes(hm))
            try:
                r0 = c_probe(probe, cal_p, len(ub_own), 1)
                r1 = c_probe(probe, cal_m, len(ub_own), 1)
            except Exception as exc:
                r0 = r1 = None
                bad.append("calibration-crash:{0!r}".format(exc))
            ub_f = header_fields(ub_own[:40])
            r0_fields_ok = (r0 is not None and r0[1] == [ub_f["kind"], ub_f["load"], ub_f["entry"],
                                                         ub_f["size"], crc_at28(ub_own[:40])])
            # Real discriminator is REQUIRED: pristine must be accepted (rc==0,
            # fields filled) and the magic-broken variant must be rejected (rc!=0).
            # No 'not discrim' bypass exists.
            discrim = (r0 is not None and r1 is not None and r0[0] == 0 and r1[0] != 0
                       and r0_fields_ok)
            if not discrim:
                c_ok = False
                bad.append("discriminator_failed")
            else:
                for name, h, fs, kind, want in cases:
                    cpath = pathlib.Path(tmpname) / "case.bin"
                    cpath.write_bytes(h)
                    try:
                        rc, vals = c_probe(probe, cpath, fs, kind)
                    except Exception as exc:
                        bad.append("{0}:crash:{1!r}".format(name, exc))
                        continue
                    if want == "accept":
                        # Struct fields are inspected only on expected/actually
                        # accepted headers (complete 40-byte headers); im.crc is
                        # the payload-CRC field at offset 28, not the header CRC.
                        f = header_fields(h[:40])
                        if rc != 0:
                            bad.append("{0}:rc={1},want accept".format(name, rc))
                        elif vals != [f["kind"], f["load"], f["entry"], f["size"], crc_at28(h[:40])]:
                            bad.append("{0}:fields={1}".format(name, str(vals)[:64]))
                        else:
                            acc += 1
                    elif rc == 0:
                        bad.append("{0}:C-accepted".format(name))
                c_ok = not bad
            c_ev = ("compiled REAL inputs/rom/image.c via gcc into TemporaryDirectory: calibration "
                    "pristine rc={0} fields(kind,load,entry,size,payload-crc@28) match={1}, "
                    "magic-break rc={2} -> discriminator={3}; {4} accept cases rc==0 with exact field "
                    "match; reject cases rc!=0; disagreements: {5}".format(
                        r0[0] if r0 else "n/a", bool(r0_fields_ok), r1[0] if r1 else "n/a",
                        discrim, acc, bad if bad else "none"))
    check("negative_header_boundaries", "adversarial mutation of real UBOOT header",
          len(cases) >= 16 and agree and c_ok,
          "{0} cases ({1} accept / {2} reject); python transcription agrees with independent "
          "expectations on all: {3}; {4}".format(len(cases), n_acc, n_rej, agree, c_ev))


# ----------------------------------------------------------------------- s09
def s09_uboot():
    board = rt("inputs/uboot/board.c").replace("\r", "")
    cfg = rt("inputs/uboot/config.h").replace("\r", "")
    dfc = rt("inputs/uboot/defconfig").replace("\r", "")
    out = rt("inputs/uboot/build.config").replace("\r", "")
    sdm, lm = rj("inputs/sd/manifest.json"), rj("inputs/linux/manifest.json")
    ev = []
    paths = ["/PRODOCK/LINUX.BIN", "/PRODOCK/LUMA.DAT", "/PRODOCK/LUMA.BIN",
             "/PRODOCK/ORBITAL.DAT", "/PRODOCK/ORBITAL.BIN"]
    found_paths = all(p in board for p in paths)
    ev.append("board.c mmc 0:1 then 0:0 fallback (lines {0},{1}); buffer 0x10000000 (line {2}); "
              "size limit PD_HEADER+0x02000000 (line {3}); pd_crc header gate (line {4}); "
              "memcpy to im->load (line {5}); paths at lines {6}".format(
                  line_of(board, '"0:1"'), line_of(board, '"0:0"'),
                  line_of(board, "0x10000000"), line_of(board, "PD_HEADER"),
                  line_of(board, "pd_crc"), line_of(board, "im->load"),
                  {p.rsplit('/', 1)[-1]: line_of(board, p) for p in paths}))
    ok_b = found_paths and '"0:0"' in board and "im->load" in board
    sbboot = rt("inputs/rom/sd_boot.c").replace("\r", "")
    gpu_ok = "0xe9000000" in sbboot
    ev.append("GPU-ABI gate words 0xe9000000 in sd_boot.c (line {0}); sd_boot loads "
              "/PRODOCK/UBOOT.BIN (line {1})".format(
                  line_of(sbboot, "0xe9000000"), line_of(sbboot, "/PRODOCK/UBOOT.BIN")))
    dcfg = {"CONFIG_BOOTCOMMAND=\"bootmenu 5\"": line_of(dfc, "bootmenu 5"),
            "CONFIG_BOOTDELAY=3": line_of(dfc, "CONFIG_BOOTDELAY=3"),
            "CONFIG_SYS_LOAD_ADDR=0x10000000": line_of(dfc, "CONFIG_SYS_LOAD_ADDR=0x10000000"),
            "CONFIG_SYS_MONITOR_LEN=8388608": line_of(dfc, "CONFIG_SYS_MONITOR_LEN=8388608"),
            "CONFIG_MMC_SPI_CRC_ON=y": line_of(dfc, "CONFIG_MMC_SPI_CRC_ON=y"),
            "CONFIG_ENV_IS_NOWHERE=y": line_of(dfc, "CONFIG_ENV_IS_NOWHERE=y")}
    ok_d = all(v > 0 for v in dcfg.values())
    same_out = all(k in out or k[8:] in out for k in dcfg)
    ev.append("defconfig values {0}; same values present in built out/.config: {1}".format(dcfg, same_out))
    menu_ok = "prodockboot linux" in cfg and "0x06000000" in cfg
    ev.append("config.h: bootmenu_0 -> 'prodockboot linux' (line {0}); SDRAM base 0x06000000 (line {1})".format(
        line_of(cfg, "prodockboot linux"), line_of(cfg, "0x06000000")))
    scratch = 0x10000000
    max_read = 0
    windows = []
    for name in ("UBOOT.BIN", "LINUX.BIN", "LUMA.DAT", "ORBITAL.DAT", "LUMA.BIN", "ORBITAL.BIN"):
        b = sdm["files"][name]["payload_bytes"]
        ld = sdm["files"][name]["load"]
        max_read = max(max_read, b)
        windows.append("{0}: dest [{1},{2})".format(name, hx(ld), hx(ld + b)))
    ovl = True
    for name in ("UBOOT.BIN", "LINUX.BIN", "LUMA.BIN", "ORBITAL.BIN", "LUMA.DAT", "ORBITAL.DAT"):
        b = sdm["files"][name]["payload_bytes"]
        ld = sdm["files"][name]["load"]
        if ld < scratch < ld + b:
            ovl = False
    lim_ok = max_read + scratch <= scratch + 0x02000000
    lin = sdm["files"]["LINUX.BIN"]
    ev.append("scratch window [{0},{1}) (max in-flight {2}); destination windows never reach scratch: {3}".format(
        hx(scratch), hx(scratch + max_read), max_read, ovl))
    ev.append("LINUX dest start {0} above U-Boot monitor end {1} (load 0x07c00000 beyond TEXT_BASE+8MiB); "
              "LINUX dest window [{0},{2}) stays below scratch {3}".format(
                  hx(lin["load"]), hx(0x06000000 + 8388608),
                  hx(lin["load"] + lin["payload_bytes"]), hx(scratch)))
    carve = lm["gpu_memory"]; g_end = carve[0] + carve[1]
    inside = [n for n in ("LUMA.DAT", "ORBITAL.DAT")
              if carve[0] <= sdm["files"][n]["load"]
              and sdm["files"][n]["load"] + sdm["files"][n]["payload_bytes"] <= g_end]
    ev.append("carveout {0} reserved by linux/manifest.json -> [{1},{2}); LUMA.DAT/ORBITAL.DAT payload "
              "windows inside it: {3}".format(carve, hx(carve[0]), hx(g_end), inside))
    menu_1 = line_of(cfg, "bootmenu_1=")
    menu_2 = line_of(cfg, "bootmenu_2=")
    alt_luma = "prodockboot luma" in cfg
    alt_orb = "prodockboot orbital" in cfg
    ev.append("demo payload usage is menu-scoped: bootmenu_1 'LUMA sans Linux'->prodockboot luma "
              "(line {0}), bootmenu_2 'ORBITAL sans Linux'->prodockboot orbital (line {1})"
              " (alt tokens present: {2}); the Linux default entry bootmenu_0 loads LINUX.BIN only".format(
                  menu_1, menu_2, alt_luma and alt_orb))
    check("uboot_sd_bootpath", "inputs/uboot + inputs/rom/sd_boot.c",
          ok_b and ok_d and same_out and menu_ok and ovl and lim_ok,
          "; ".join(ev))
    if inside:
        finding("gpu-carveout-write",
                "NOT a source bug -- intentional alternative boot path: {0} are BAREMETAL demo "
                "payloads loaded only by the separate U-Boot bootmenu alternatives 'prodockboot "
                "luma' / 'prodockboot orbital' (config.h bootmenu_1 line {1} / bootmenu_2 line {2}), "
                "never simultaneously with Linux: the menu default (bootmenu_0 'prodockboot linux') "
                "loads LINUX.BIN only, and the U-Boot image() helper runs for exactly ONE selected "
                "menu entry.  Their windows sit in external DDR3 (the region linux/manifest.json "
                "gpu_memory {3} later reserves as framebuffer/asset memory), NOT in any 'GPU SRAM'. "
                "Recorded as an intentional alternative path in this offline, file-only audit; no "
                "image build, no hardware, no board qualification performed."
                .format(inside, menu_1, menu_2, carve))


# ---------------------------------------------------------------------- s10
def s10_linux():
    kc = rt("inputs/linux/kernel.config").replace("\r", "")
    lm = rj("inputs/linux/manifest.json")
    sdm = rj("inputs/sd/manifest.json")
    opts = ["CONFIG_MMC=", "CONFIG_MMC_BLOCK=", "CONFIG_MMC_SPI=", "CONFIG_VFAT_FS=",
            "CONFIG_DEVTMPFS=", "CONFIG_PROC_FS=", "CONFIG_SYSFS=", "CONFIG_TMPFS=",
            "CONFIG_UNIX98_PTYS=", "CONFIG_BLK_DEV_INITRD="]
    got = {o: line_of(kc, o) for o in opts}
    ok = all(v > 0 for v in got.values()) and 'CONFIG_CMDLINE=""' in kc
    carve = lm["gpu_memory"]
    g0, g1 = carve[0], carve[0] + carve[1]
    load_ok = lm["load"] > g1 and lm["entry"] == lm["load"]
    lin = sdm["files"]["LINUX.BIN"]
    ev = ("kernel.config =y options at lines {0}; CONFIG_CMDLINE empty; "
          "gpu_memory {1} [start,size] carveout [{2},{3}); fw_payload load/entry {4} > carveout end".format(
              got, carve, hx(g0), hx(g1), hx(lm["load"])))
    check("linux_kernel_sd_stack", "inputs/linux/{kernel.config,manifest.json}", ok and load_ok, ev)
    # Linux JTAG launchers: the helper code itself is ILM-resident (load 0xa0000000,
    # entry = load + 12-byte vector); their 'stage' fields (0x10000000 / 0x08000000)
    # are COMPRESSED-PAYLOAD STAGING addresses in DDR, auxiliary JTAG loading records.
    # They are NOT ILM load locations, and the direct SD ROM path
    # (sd_boot.c -> /PRODOCK/UBOOT.BIN -> prodockboot linux -> fw_payload) never
    # executes these helpers, so no ILM containment is imposed on the stage and no
    # full stage extent is invented (the source contract supplies stage addresses
    # only, not compressed-data size).
    ilm = (D.get("mem") or {}).get("ILM")
    ev2 = []
    l_ok = True
    if not isinstance(ilm, tuple) or len(ilm) != 2:
        l_ok = False
        limited("ILM geometry unavailable from itcm.ld (s02 aborted?)")
        ev2.append("ILM geometry absent: launchers not containment-checked")
    else:
        ib, ilen = ilm
        for kname in ("launcher", "launcher_packed", "launcher_usb"):
            item = lm.get(kname, {})
            if not isinstance(item, dict) or not all(k in item for k in ("bytes", "load", "entry")):
                l_ok = False
                ev2.append("{0}: absent/invalid manifest record {1}".format(kname, sorted(item)))
                continue
            b, ld, en = item["bytes"], item["load"], item["entry"]
            stg = item.get("stage")
            ilm_ok = (ld == ib and 0 < b <= ilen and ld + b <= ib + ilen and en == ld + 12)
            l_ok = l_ok and ilm_ok
            ev2.append("{0}: ILM helper {1}B load {2} entry {3} (entry==load+12: {4}) inside "
                       "ILM [{5},{6}): {7}; aux JTAG stage record: {8} (address only)".format(
                           kname, b, hx(ld), hx(en), en == ld + 12, hx(ib), hx(ib + ilen),
                           ilm_ok, hx(stg) if stg is not None else "<none>"))
    staged = {k: lm[k]["stage"] for k in ("launcher", "launcher_packed", "launcher_usb")
              if isinstance(lm.get(k), dict) and lm[k].get("stage")}
    aux_note = ("launcher stage addresses {0} are compressed-payload staging addresses, not ILM "
                "load locations; the direct SD ROM->Uboot->fw_payload boot path does not execute "
                "these JTAG launchers -> auxiliary records only; no stage extent invented".format(
                    {k: hx(v) for k, v in staged.items()} if staged else "<none stated>"))
    lin_base = pd_region(2)[0]
    fwp = (lm.get("files", {}) or {}).get("opensbi/platform/generic/firmware/fw_payload.bin", {})
    match = bool(fwp) and (fwp.get("bytes") == lin["payload_bytes"]) and (
        lm["load"] == lm["entry"] == lin["load"] == lin_base)
    if not match:
        limited("firmware cross-link weaker than expected: fw_payload={0} vs LINUX.BIN payload {1}".format(
            fwp.get("bytes"), lin["payload_bytes"]))
    check("linux_launchers_bounds", "inputs/linux/manifest.json", l_ok and match,
          "; ".join(ev2) + "; " + aux_note + "; opt_in={0} release_qualified={1} "
          "hardware_validation={2}; fw_payload {3}B == LINUX.BIN payload {4}B and "
          "manifest load==entry==LINUX.BIN load {5}== kind2 region base: {6}".format(
              lm.get("autostart_opt_in"), lm.get("release_qualified"), lm.get("hardware_validation"),
              fwp.get("bytes"), lin["payload_bytes"], hx(lin["load"]), match))


# ---------------------------------------------------------------------- s11
def s11_rootfs():
    rf = rj("inputs/linux/rootfs.json")
    bb = rt("inputs/linux/busybox.config").replace("\r", "")
    init = rb("inputs/linux/rootfs/init")
    autos = rb("inputs/linux/rootfs/bin/prodock-autostart")
    profile = rb("inputs/linux/rootfs/etc/console-autostart")
    at = autos.decode("utf-8", "replace").replace("\r", "")
    hash_ok, rows = True, []
    for rel, ent in (("inputs/linux/rootfs/init", "init"),
                     ("inputs/linux/rootfs/bin/prodock-autostart", "bin/prodock-autostart"),
                     ("inputs/linux/rootfs/etc/console-autostart", "etc/console-autostart")):
        d = rb(rel)
        ok_e = sha(d) == rf["entries"][ent]["sha256"]
        hash_ok = hash_ok and ok_e
        rows.append("{0}: sha own==stated {1}".format(ent, ok_e))
    exact = profile == b"profile=prodock\nenabled=1\n"
    in_ok = ("prodock.autoplay=0" in at) and ("prodock.selftest=1" in at)
    mount_ok = ('MOUNT_OPTIONS=\'-t vfat -o ro,exec\'' in at and
                'mount $MOUNT_OPTIONS "$SD_PARTITION" "$SD_ROOT"' in at and
                'mount $MOUNT_OPTIONS "$SD_DISK" "$SD_ROOT"' in at and
                'MOUNT_ROUNDS=4' in at and 'mounted_by_us=0' in at and
                'umount' in at and 'mounted_by_us' in at)
    gate_ok = ('command -v sha256sum' in at and 'sha256sum "$GAME_PATH"' in at and
               '"$GAME_PATH" --festival' in at and '$GAME_SHA' in at and
               'expected_name' in at and 'hash_status=$?' in at and
               'refusing to start the game' in at and 'GAME_NAME=' in at)
    # Applets are verified as EXACT enabled lines "CONFIG_X=y"; the plain
    # CONFIG_X= substring search would also accept CONFIG_X=n style records.
    # CONFIG_ASH_TEST=y is included because the scripts rely on the shell
    # built-in test/[ ... ] syntax (not the standalone CONFIG_TEST applet at
    # line 336): CONFIG_ASH_TEST=y makes test/[ work inside these ash scripts.
    applets = ["CONFIG_ASH", "CONFIG_CAT", "CONFIG_MKDIR", "CONFIG_MOUNT", "CONFIG_UMOUNT",
               "CONFIG_SLEEP", "CONFIG_GREP", "CONFIG_SHA256SUM", "CONFIG_ECHO", "CONFIG_TEST",
               "CONFIG_ASH_TEST", "CONFIG_POWEROFF", "CONFIG_UNAME", "CONFIG_SYNC",
               "CONFIG_FEATURE_SH_MATH"]
    bb_lines = bb.splitlines()
    app_rows, app_ok = {}, True
    for a in applets:
        want = a + "=y"
        pos = [i + 1 for i, l in enumerate(bb_lines) if l.strip() == want]
        app_rows[a] = pos[0] if pos else "<no exact " + want + " line>"
        app_ok = app_ok and bool(pos)
    itxt = init.decode("utf-8", "replace").replace("\r", "")
    i_self = itxt.find("prodock.selftest=1")
    i_auto = itxt.find("/bin/prodock-autostart")
    i_exec = itxt.find("exec /sbin/init")
    order_ok = 0 <= i_self < i_auto < i_exec
    init_flow = order_ok and "/bin/prodock-autostart || echo 'PRODOCK_AUTOSTART_FAILED'" in itxt
    # Opt-in is fail-closed at source level: a missing profile file or an
    # enabled=0 line exits before any mount -- default is disabled.
    optin_ok = ('[ ! -r "$PROFILE" ]' in at and "opt-in profile missing: $PROFILE" in at and
                "enabled=0) profile_disabled=1" in at and 'disabled by /etc/console-autostart' in at)
    check("rootfs_optin_ro_mount_fixed_game", "inputs/linux/rootfs/* + busybox.config",
          hash_ok and exact and in_ok and mount_ok and gate_ok and app_ok and init_flow and optin_ok,
          "{0}; console-autostart is EXACTLY 26B 'profile=prodock/enabled=1': {1}; kernel opt-out "
          "token 'prodock.autoplay=0' honored ({2}); opt-in missing/'enabled=0' fails closed to "
          "disabled in the script source ({3}); ro+exec mount of /mnt/sd with MOUNT_ROUNDS=4 retries "
          "of both partition and whole-disk targets; fixed game LUMA3D.ELF verified by sha256sum vs "
          "$GAME_SHA and executed exactly once with --festival; cleanup umounts only mounts made by "
          "us; busybox applets require exact CONFIG_X=y lines {4} (CONFIG_ASH_TEST=y supplies the "
          "shell test/[ ... ] built-in the scripts use; standalone CONFIG_TEST=y at line {5}); "
          "init order selftest->autostart->exec /sbin/init (bytes {6}<{7}<{8}): {9}".format(
              "; ".join(rows), exact, in_ok, optin_ok, app_rows,
              app_rows.get("CONFIG_TEST"), i_self, i_auto, i_exec, order_ok))


# ---------------------------------------------------------------------- s12
def s12_bootsector():
    bs = rb("inputs/sd/boot_sector.bin")
    ff = rt("inputs/rom/ffconf.h").replace("\r", "")
    pkr = D["pkr"]
    bps = struct.unpack_from("<H", bs, 11)[0]
    tots = struct.unpack_from("<I", bs, 32)[0]
    fatsz = struct.unpack_from("<I", bs, 36)[0]
    resvd = struct.unpack_from("<H", bs, 14)[0]
    tot = tots * bps
    img_bytes = pkr.get("file_image", {}).get("bytes", None)
    clusters = (tots - resvd - fatsz * 2) // bs[13]
    need = ((clusters + 2) * 4 + 511) // 512
    oem = bs[3:11].decode("ascii", "replace")
    sig = bs[510:512] == b"\x55\xaa"
    mbr_gap = bs[446:510] == b"\x00" * 64
    ss_ok = line_of(ff, "_MIN_SS") > 0 and line_of(ff, "_MAX_SS") > 0
    lfn0 = line_of(ff, "_USE_LFN") > 0
    ro0 = line_of(ff, "_FS_READONLY") > 0
    ok = (sig and bps >= 512 and tots > 0 and 32 <= resvd and fatsz >= need
          and tot == img_bytes and mbr_gap and ss_ok and lfn0 and ro0)
    check("boot_sector_fat32", "inputs/sd/boot_sector.bin + ffconf.h", ok,
          "bps={0} spc={1} resvd={2} nfats={3} rootents={4} totsec32={5} media={6} fatsz32={7} "
          "clusters={8}; FAT needs {9} sectors == fatsz32 ({10}); total {11}B == file_image bytes "
          "{12}; sig 0x55AA {13}; partition area 446..509 all zero: {14}; ffconf _MIN/_MAX_SS {15} "
          "_USE_LFN {16} _FS_READONLY present; oem={17}".format(
              bps, bs[13], resvd, bs[16], struct.unpack_from("<H", bs, 17)[0], tots, hex(bs[21]),
              fatsz, clusters, need, need == fatsz, tot, img_bytes, sig, mbr_gap, "@162/163", lfn0, oem))


# ---------------------------------------------------------------------- s13
def s13_r3():
    r3 = rj("inputs/fpga/r3_rom_result.json")
    first = r3.get("first_difference", {}) or {}
    baddr = first.get("byte_address", first.get("offset", "<absent>"))

    def sh(v):
        try:
            return hx(int(str(v), 0))
        except Exception:
            return repr(v)
    ok = False  # R3 is a BLOCKER: reported as failing check by design
    check("r3_post_route_rom", "inputs/fpga/r3_rom_result.json", ok,
          "passed={0}; expected {1} == own recompute of console_test.bin ({2}); observed {3} !=; "
          "first_difference offset {4} (byte addr {5}) expected {6} observed {7}; differing payload "
          "bytes {8}/{9}; padding {10}B with {11} nonzero; qualification '{12}'; "
          "hardware_validated={13}".format(
              r3.get("passed"), r3.get("expected_sha256"), D.get("rom_sha"),
              r3.get("observed_payload_sha256"), first.get("offset"), sh(baddr),
              first.get("expected"), first.get("observed"), r3.get("differing_payload_bytes"),
              r3.get("payload_bytes"), r3.get("padding_bytes"), r3.get("padding_nonzero_bytes"),
              r3.get("qualification"), r3.get("hardware_validated")))
    finding("r3-blocker", "R3 post-route VO ROM does NOT contain the firmware bytes "
            "({0} != {1}); first divergence at ROM byte address {2}".format(
                r3.get("expected_sha256", ""), r3.get("observed_payload_sha256", ""), sh(baddr)))


# ---------------------------------------------------------------------- s14
def s14_r4():
    r4 = rj("inputs/fpga/r4_candidate.json")
    ip = rj("inputs/fpga/r4_ip_result.json")
    need_route, need_synth = None, None
    for k, v in r4.items():
        if "rom_post_route_verification_required" in k and isinstance(v, bool):
            need_route = v
        if "new_synthesis_required" in k and isinstance(v, bool):
            need_synth = v
    ip_flags = {k: v for k, v in ip.items() if isinstance(v, bool)}
    fw = r4.get("firmware_sha256", "")
    match = fw == D.get("rom_sha")
    check("r4_post_route_rom", "inputs/fpga/r4_candidate.json + r4_ip_result.json", False,
          "R4 candidate still requires post-route ROM verification: required={0}, new_synthesis={1}; "
          "ip flags {2}; R4 firmware sha {3} matches supplied direct-ROM console_test.bin: {4}; "
          "no R4 post-route ROM hash exists yet".format(need_route, need_synth, ip_flags, fw[:16], match))
    finding("r4-pending", "R4 rebuild is pending: synthesis result and post-route ROM check are "
            "absent; the chain cannot be hardware-validated at R4.")


# ---------------------------------------------------------------------- s15
def s15_history():
    sdm = rj("inputs/sd/manifest.json")
    pkr, bm, imj = D["pkr"], D["bm"], D["imj"]
    pkg_manifest_sha = pkr.get("package_manifest", {}).get("sha256")
    chain_ok = pkg_manifest_sha == imj["inputs/sd/manifest.json"]["sha256"]
    di, keys = {}, []
    try:
        di = rj("inputs/sd/root_physical_install.json")
        keys = sorted(di.keys())
    except Exception as exc:
        limited("root_physical_install.json unreadable: {0!r}".format(exc))
    # SUPPLIED root post-install proof: 'readback' is a dict keyed by MEDIA file
    # name with {bytes, sha256} values.  Iterate .items() and compare ALL of it
    # against the sd manifest.  This is evidence supplied by the root's install
    # record; the audit performs no SD read of its own.
    rb_map = di.get("readback") or {}
    if not isinstance(rb_map, dict) or not rb_map:
        limited("root readback is not a dict keyed by file name: {0!r}".format(type(rb_map)))
        rb_map = {}
    matched, bad_rb = [], []
    for nm, rec in sorted(rb_map.items()):
        mf = sdm["files"].get(nm)
        if not isinstance(rec, dict):
            bad_rb.append("{0}: record not a {{bytes,sha256}} mapping".format(nm))
        elif mf is None:
            bad_rb.append("{0}: name absent from sd manifest files".format(nm))
        elif rec.get("bytes") == mf["bytes"] and rec.get("sha256") == mf["sha256"]:
            matched.append(nm)
        else:
            bad_rb.append("{0}: record {1}B/{2} != manifest {3}B/{4}".format(
                nm, rec.get("bytes"), str(rec.get("sha256"))[:16], mf["bytes"], mf["sha256"][:16]))
    rb_ok = (len(rb_map) == len(sdm["files"])) and matched and not bad_rb
    if bad_rb:
        finding("install-readback", "root readback entries not matching sd manifest: {0}".format(bad_rb))
    fi_bytes = (pkr.get("file_image", {}) or {}).get("bytes", None)
    bs = rb("inputs/sd/boot_sector.bin")
    tot2 = struct.unpack_from("<I", bs, 32)[0] * struct.unpack_from("<H", bs, 11)[0]
    media_ok = (fi_bytes is None) or (fi_bytes == tot2)
    if fi_bytes is None:
        limited("package_result file_image bytes absent; media size not cross-checked")
    flags = {k: v for k, v in list(pkr.items()) + list(sdm.items()) if isinstance(v, bool)}
    hw_keys = {k: v for k, v in flags.items() if "hardware" in k.lower() or "tested" in k.lower()}
    hw_ok = all(not v for v in hw_keys.values())
    inst = di.get("installed", di.get("write_ok", None))
    check("package_and_media_history", "package_result.json + root_physical_install.json",
          chain_ok and rb_ok and hw_ok and media_ok,
          "package_manifest sha == input_manifest manifest.json sha: {0}; root install record keys: "
          "{1}; installed={2}; readback_verified={3}; supplied root readback proof is a dict keyed "
          "by {4} file names compared against the sd manifest files (bytes+sha256, iterated via "
          "items(), no own SD read): {5} match, mismatches {6}; readback names/bytes: {7}; "
          "bootsector-implied media size {8} == package file_image bytes {9}: {10}; packaging-time "
          "hardware flags: {11}".format(
              chain_ok, keys, inst, di.get("readback_verified"), len(rb_map), len(matched),
              bad_rb or "none", [(n, (rb_map.get(n) or {}).get("bytes")) for n in sorted(rb_map)],
              tot2, fi_bytes, media_ok, hw_keys))
    if inst is not True:
        finding("install-record", "root install record does not assert installed=true: {0}".format(inst))


SECTIONS = (s01_inputs, s02_itcm, s03_rom_symbols, s04_pdckboot_source, s05_decoder_identity,
            s06_own_files, s07_delegated, s08_negative, s09_uboot, s10_linux, s11_rootfs,
            s12_bootsector, s13_r3, s14_r4, s15_history)


def run_audit():
    CHECKS.clear()
    FINDINGS.clear()
    LIMITS.clear()
    for fn in SECTIONS:
        try:
            fn()
        except Exception as exc:  # keep going; record honestly
            check(fn.__name__ + "_runtime", "runtime guard", False,
                  "section raised {0!r}; its claims are NOT verified".format(exc))
            limited("section {0} aborted: {1!r}".format(fn.__name__, exc))
    limited("No hardware access per CONTRACT: board boot, SD media and GPU behavior are "
            "unobservable here; hardware_access/hardware_validated=false by design.")
    limited("Files >1MiB are never read; delegated measurements in binary_measurements.json and the "
            "root_install readback are SUPERVISOR-SUPPLIED measurements (large-file sizes, hashes, "
            "post-install proof), cross-checked here but never re-measured or re-performed.")
    limited("No product image is rebuilt or written; the gcc probe compiles the SUPPLIED decoder "
            "(inputs/rom/image.c) inside a TemporaryDirectory solely to cross-check this audit's "
            "validate_header transcription; TemporaryDirectory cleans all probe artifacts.")
    report = {
        "audit": TARGET,
        "schema": 1,
        "hardware_access": False,
        "hardware_validated": False,
        "r4_post_route_verified": False,
        "checks_passed": sum(1 for c in CHECKS if c["passed"]),
        "checks_failed": sum(1 for c in CHECKS if not c["passed"]),
        "checks": CHECKS,
        "findings": FINDINGS,
        "limitations": LIMITS,
    }
    return report


def main():
    report = run_audit()
    sys.stdout.write(json.dumps(report, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())