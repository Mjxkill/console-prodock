#!/usr/bin/env python3
"""Freeze R19 firmware for the already authorized experimental G22r0 board.

This is not a timing qualification and never rewrites the legacy asset pack.
"""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / 'pack'
FLAGS = '-ffp-contract=off -DASTRILLA_HW_GEOMETRY'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    baseline = json.loads((ROOT/'TESTS/gpu_geometry_20261011/g22r0_trial_pack/astrilla.json').read_text())
    stage = ROOT/'tang/impl/gpu_geometry_g22r0'
    assert baseline['experimental'] and baseline['timing_qualified'] is False
    assert sha(stage/'impl/pnr/console_gpu_geometry_g22r0.fs') == baseline['fpga_sha256']
    assert sha(ROOT/'assets/astrilla/packed/astrilla.bin') == baseline['assets_sha256']
    subprocess.run(['make', '-s', '-C', str(ROOT/'fw_console'), 'MAIN=astrilla_main.c',
                    'BUILD=build/astrilla_r19', 'EXTRA_SRCS=gpu_geometry.c',
                    'CFLAGS_EXTRA='+FLAGS, 'LD='+str(ROOT/'fw_console/astrilla.ld')], check=True)
    binary = ROOT/'fw_console/build/astrilla_r19/console_test.bin'
    nm = '/home/michael/gowin/GMD_2025.01_linux/GMD/toolchain/gowin/gcc_riscv/bin/riscv-none-elf-nm'
    symbols = subprocess.check_output([nm, str(binary.with_suffix('.elf'))], text=True)
    entry = int(next(s.split()[0] for s in symbols.splitlines() if s.endswith(' T _start')), 16)
    assert 0xa0000000 <= entry < 0xa0000000+binary.stat().st_size <= 0xa0010000
    OUT.mkdir(exist_ok=False)
    sources = [p for p in (ROOT/'fw_console').iterdir() if p.suffix in ('.h', '.c', '.ld', '.S') or p.name == 'Makefile']
    sources += [ROOT/'tools'/name for name in ('build_astrilla_meshes.py', 'render_astrilla.py',
                 'gpu_geometry_model.py', 'check_astrilla.py', 'load_astrilla.py')]
    for p in sources:
        target = OUT/'source'/p.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(p.read_bytes())
    meta = dict(baseline, binary='astrilla_hw.bin', revision='R19', bytes=binary.stat().st_size,
                entry=entry, sha256=sha(binary), flags=FLAGS,
                sources={str(p.relative_to(ROOT)):sha(p) for p in sources})
    (OUT/meta['binary']).write_bytes(binary.read_bytes())
    (OUT/'astrilla.json').write_text(json.dumps(meta, indent=2)+'\n')
    print('R19', meta['bytes'], meta['sha256'], 'experimental G22r0', flush=True)


if __name__ == '__main__':
    main()
