#!/usr/bin/env python3
"""Reproducible, read-only qualification evidence for R3 versus G22r0.

Resource/pin/clock equality is independent of ROM and timing qualification.
Reported top-N paths are never counted as a complete endpoint census.
"""
import hashlib
import json
from pathlib import Path
import re

from rom_check import compare, decode

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def table(text, start, end):
    section = text.split(start, 1)[1].split(end, 1)[0] if end else text.split(start, 1)[1]
    return [[x.strip() for x in line.split('|')] for line in section.splitlines() if '|' in line]


def timing(text):
    summary = dict(re.findall(r'^<([^>]+)>:(.*)$', text, re.M))
    kinds = {}
    for i, kind in enumerate(['Setup', 'Hold', 'Recovery', 'Removal'], 1):
        start = re.search(r'^3\.1\.'+str(i)+' '+kind+r' Paths Table\n', text, re.M).end()
        stop = (re.search(r'^3\.1\.'+str(i+1)+r' ', text[start:], re.M) if i < 4
                else re.search(r'^3\.2 ', text[start:], re.M))
        section = text[start:start+stop.start()]
        rows = [line.split() for line in section.splitlines()
                if re.match(r'^\s+\d+\s+-?\d+\.\d+', line)]
        assert rows, kind
        kinds[kind.lower()] = dict(
            minimum_ns=min(float(row[1]) for row in rows),
            listed_paths=len(rows), listed_negative=sum(float(row[1]) < 0 for row in rows),
            clock_pairs=sorted({(row[4], row[5]) for row in rows}),
            worst=min(rows, key=lambda row: float(row[1])))
    tns = re.search(r'^2\.4 Total Negative Slack Summary\n(.*?)^3\.', text, re.M | re.S)[1]
    tns_rows = [line.split() for line in tns.splitlines()
                if re.match(r'^\s+\w+\s+(?:setup|hold)\s+', line)]
    fmax = re.search(r'^2\.3 Max Frequency Summary\n(.*?)^2\.4', text, re.M | re.S)[1]
    fmax_rows = [line.split() for line in fmax.splitlines() if re.match(r'^\s+\d+\s+', line)]
    return dict(summary=summary, paths=kinds, per_clock_tns=tns_rows, fmax=fmax_rows)


def collect(folder, stem):
    base = ROOT/'tang/impl'/folder
    pnr = base/'impl/pnr'
    paths = [pnr/(stem+s) for s in ['.fs', '.vo', '.tr', '.rpt.txt']]
    paths += [base/'build.log', base/'constraints_resolved.cst', base/'sources.json',
              base/'source/diagnostics/timing_reports.sdc',
              base/'source/tang/rtl/board/riscv_ae350_soc_ext/riscv_ae350_soc.v']
    report = paths[3].read_text()
    resources = table(report, '3. Resource Usage Summary', '4. I/O Bank Usage Summary')
    clocks = table(report, '6. Global Clock Signals', '7. Pinout by Port Name')[1:]
    pins = {row[0]: row for row in table(report, '8. All Package Pins', None)
            if re.fullmatch(r'[A-Z]+\d+/\d+', row[0])}
    initialized, cells = decode(paths[1].read_text())
    return dict(files={str(p.relative_to(ROOT)): sha(p) for p in paths},
                timing=timing(paths[2].read_text()), resources=resources,
                global_clocks=clocks, pins=pins,
                rom_sha256=hashlib.sha256(initialized).hexdigest(), rom_cells=len(cells)), initialized


def main():
    old, oldrom = collect('gpu_geometry_g22r0', 'console_gpu_geometry_g22r0')
    new, newrom = collect('prodock_sd_boot_20261028_r3', 'console_prodock_sd_boot_20261028_r3')
    base = ROOT/'tang/impl/prodock_sd_boot_20261028_r3'
    boot = base/'source/boot_firmware'
    binary = (boot/'sd_boot.bin').read_bytes()
    lanes = [bytes(int(x, 16) for x in (boot/'itcm'/f'itcm{i}').read_text().split()) for i in range(4)]
    lane_bytes = bytes(x for word in zip(*lanes) for x in word)
    assert lane_bytes == binary
    before = ROOT/'tang/impl/gpu_geometry_g22r0'
    source_manifest = json.loads((before/'sources.json').read_text())
    changed = []
    for relative, digest in source_manifest.items():
        assert sha(before/'source'/relative) == digest
        if sha(base/'source'/relative) != digest:
            changed.append(relative)
    old_sdc = (before/'source/diagnostics/timing_reports.sdc').read_text().splitlines(keepends=True)
    new_sdc = (base/'source/diagnostics/timing_reports.sdc').read_text().splitlines(keepends=True)
    assert [line for line in old_sdc if not line.startswith('report_timing ')] == new_sdc
    assert sha(before/'constraints_resolved.cst') == sha(base/'constraints_resolved.cst')
    changed_pins = [dict(location=k, before=old['pins'][k], after=v)
                    for k, v in new['pins'].items() if v != old['pins'][k]]
    assigned = {k: v for k, v in new['pins'].items() if v[1] != '-'}
    assert all(v == old['pins'][k] for k, v in assigned.items())
    record = dict(schema=1, status='REJECTED_ROM_MISMATCH', hardware_access=False,
                  hardware_validated=False, timing_closed=False, compiler_success=True,
                  reference=old, candidate=new, rom=compare(newrom, binary),
                  source_lanes_equal_binary=True, complete_rom_equal_g22=newrom == oldrom,
                  historical_sources_checked=len(source_manifest), historical_sources_changed=changed,
                  sdc_diff_reports_only=True, cst_identical=True,
                  assigned_pin_rows=len(assigned), assigned_pins_identical=True,
                  unused_pin_changes=changed_pins,
                  global_clock_rows_identical=old['global_clocks'] == new['global_clocks'],
                  tool_sha256=sha(Path(__file__)), rom_checker_sha256=sha(HERE/'rom_check.py'))
    (HERE/'result.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps({k: v for k, v in record.items() if k not in
                     ('reference', 'candidate', 'unused_pin_changes')}, indent=2))


if __name__ == '__main__':
    main()
