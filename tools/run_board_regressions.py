#!/usr/bin/env python3
"""Run local Pro Dock + Neo regressions and bind results to exact input hashes.

No FPGA programming, no remote connection, no board access. Hardware validation
is always a separate pending step for a changed production build.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from board_contract import ROOT, CACHE, audit, digest, regression_inputs, sha


def commands(out):
    py = sys.executable
    reference = ROOT/'tang/impl/gpu_geometry_g22r0/source'
    return [
        ('contract', [py, '-m', 'unittest', 'TESTS.test_board_contract']),
        ('bridge', [py, 'TESTS/test_ahb_exts_bridge_equivalence.py', '--reference',
                    str(reference/'tang/rtl/board/ahb_exts_bridge.v'), '--out', str(out/'bridge')]),
        ('ddr_prodock', [py, 'tools/check_ahb_ddr_cdc.py', '--prodock-ddr', '--out', str(out/'ddr_prodock')]),
        # Current Neo base retains the original Pro Dock adapter; only its
        # four-slot CPU FIFO is replaced. The tagged Neo adapter is historical.
        ('ddr_neo', [py, 'tools/check_ahb_ddr_cdc.py', '--prodock-ddr', '--fifo-registers', '--out', str(out/'ddr_neo')]),
        ('usb_msc', [py, 'tools/check_usb_msc_sim.py', '--output', str(out/'usb_msc.json')]),
        ('geometry', [py, 'TESTS/test_gpu_geometry.py', '--bus-stage', '--mixed-raster',
                      '--invalid-descriptors', '--reset-phases', '--out', str(out/'geometry')]),
        ('scanout_prodock', [py, 'linux/tests/test_nebula_scanout.py', '--out', str(out/'scanout_prodock')]),
        ('scanout_neo', [py, 'linux/tests/test_nebula_scanout.py', '--720p', '--out', str(out/'scanout_neo')]),
        ('text_both', [py, 'linux/tests/test_text_model.py']),
        ('dashboard_both', [py, 'linux/tests/test_dashboard.py']),
        ('nebula_both', [py, 'linux/tests/test_nebula.py']),
        ('spi_pio', [py, 'linux/tests/test_spi_pio.py', '--out', str(out/'spi_pio.json')]),
        ('spi_uboot', [py, 'linux/tests/test_spi_uboot.py', '--out', str(out/'spi_uboot.json')]),
        ('spi_linux', [py, 'linux/tests/test_spi_linux.py', '--out', str(out/'spi_linux.json')]),
        ('mmc_spi_init', [py, 'linux/tests/test_mmc_spi_init.py', '--out', str(out/'mmc_spi_init.json')]),
    ]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    out = a.out.resolve()
    if not out.is_relative_to(ROOT/'TESTS/dual_board'):
        p.error('Results must be under TESTS/dual_board/<new-run>')
    before = regression_inputs()
    reference = audit()
    out.mkdir(parents=True, exist_ok=False)
    result = dict(passed=False, inputs=before, inputs_digest=digest(before), tests=[],
                  reference=reference, started_utc=datetime.now(timezone.utc).isoformat(),
                  hardware_validation=False, scope='Local tests of common working-tree sources; no board access')
    path = out/'result.json'
    def save():
        path.write_text(json.dumps(result, indent=2)+'\n')
    save()
    for name, command in commands(out):
        print('Testing '+name, flush=True)
        log = out/(name+'.log')
        error = None
        with log.open('w') as handle:
            try:
                rc = subprocess.run(command, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT,
                                    timeout=1800).returncode
            except (OSError, subprocess.TimeoutExpired) as exc:
                rc, error = -1, str(exc)
        result['tests'].append(dict(name=name, command=command, passed=rc == 0, returncode=rc,
                                   error=error, log=str(log.relative_to(ROOT)), log_sha256=sha(log)))
        save()
    result['inputs_unchanged'] = before == regression_inputs()
    result['passed'] = result['inputs_unchanged'] and all(t['passed'] for t in result['tests'])
    result['completed_utc'] = datetime.now(timezone.utc).isoformat()
    save()
    latest = ROOT/CACHE
    pending = latest.with_suffix('.tmp')
    pending.write_text(json.dumps(dict(result=str(path.relative_to(ROOT)), sha256=sha(path)), indent=2)+'\n')
    pending.replace(latest)
    print(json.dumps(dict(passed=result['passed'], tests=len(result['tests']), hardware_validation=False)))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
