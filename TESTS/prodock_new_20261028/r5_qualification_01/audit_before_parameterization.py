#!/usr/bin/env python3
"""Collect R4 evidence after tool completion; never perform board operations.

Reuse the R3 report readers while preserving their frozen report. Timing
minima/top-N counts remain distinct from complete endpoint violation totals.
"""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / 'r3_qualification_01'))
from audit import collect, sha
from rom_check import compare


def main():
    target = HERE / 'result.json'
    if target.exists():
        raise FileExistsError(target)
    base = ROOT / 'tang/impl/prodock_sd_boot_20261029_r4'
    done = json.loads((base / 'build_result.json').read_text())
    assert done.get('tool_returncode') == 0 and done.get('tool_error') is False
    before = ROOT / 'tang/impl/gpu_geometry_g22r0'
    old, old_rom = collect('gpu_geometry_g22r0', 'console_gpu_geometry_g22r0')
    new, new_rom = collect(base.name, 'console_' + base.name)
    manifest = json.loads((before / 'sources.json').read_text())
    changes = []
    for name, expected in manifest.items():
        assert sha(before / 'source' / name) == expected, name
        if sha(base / 'source' / name) != expected:
            changes.append(name)
    current = json.loads((base / 'sources.json').read_text())
    assert all(sha(base / 'source' / name) == expected for name, expected in current.items())
    source_boot = base / 'source/boot_firmware'
    binary = (source_boot / 'sd_boot.bin').read_bytes()
    lanes = [bytes(int(x, 16) for x in (source_boot / 'itcm' / ('itcm'+str(i))).read_text().split())
             for i in range(4)]
    assert len(set(map(len, lanes))) == 1
    assert bytes(x for word in zip(*lanes) for x in word) == binary
    previous_sdc = (before / 'source/diagnostics/timing_reports.sdc').read_text().splitlines(keepends=True)
    now_sdc = (base / 'source/diagnostics/timing_reports.sdc').read_text().splitlines(keepends=True)
    assigned = {k: row for k, row in new['pins'].items() if row[1] != '-'}
    differences = [dict(location=k, before=old['pins'].get(k), after=row)
                   for k, row in assigned.items() if row != old['pins'].get(k)]
    negative = {k: v['listed_negative'] for k, v in new['timing']['paths'].items()}
    record = dict(schema=1, hardware_access=False, hardware_validated=False,
                  compiler_success=True, reference=old, candidate=new,
                  rom=compare(new_rom, binary), source_lanes_equal_binary=True,
                  complete_rom_equal_g22=new_rom == old_rom,
                  protected_sources_checked=len(manifest), current_sources_checked=len(current),
                  historical_sources_changed=changes,
                  sdc_diff_reports_only=[x for x in previous_sdc if not x.startswith('report_timing ')] == now_sdc,
                  cst_identical=sha(before/'constraints_resolved.cst') == sha(base/'constraints_resolved.cst'),
                  assigned_pin_rows=len(assigned), assigned_pin_differences=differences,
                  global_clock_rows_identical=old['global_clocks'] == new['global_clocks'],
                  published_negative_paths_by_type=negative,
                  timing_closed=False if any(negative.values()) else None,
                  timing_limit='No positive full closure claim from top-N published paths alone',
                  tool_sha256=sha(Path(__file__)),
                  imported_readers_sha256=sha(HERE.parent/'r3_qualification_01/audit.py'),
                  rom_checker_sha256=sha(HERE.parent/'r3_qualification_01/rom_check.py'))
    target.write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps({k: v for k,v in record.items() if k not in ('reference','candidate')}, indent=2))


if __name__ == '__main__':
    main()
