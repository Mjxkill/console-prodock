#!/usr/bin/env python3
"""Exercise Neo debug AHB wait states, CDC snapshots and the real GPU bus chain.

The GPU comes from an already instrumented frozen build. The debug port and
testbenches come from this checkout, so a timing change can be tested before
starting a new full FPGA build. No board access.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-root', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    source = a.source_root.resolve()
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    debug = ROOT/'tang/boards/neo/neo_gpu_debug.v'
    unit = ROOT/'TESTS/rtl/neo_gpu_debug_tb.sv'
    chain = ROOT/'TESTS/rtl/neo_gpu_bus_chain_tb.sv'
    accel = ROOT/'TESTS/rtl/neo_gpu_debug_accel_tb.sv'
    gpu = [source/f'tang/rtl/video/{name}.v' for name in (
        'gpu_accel', 'gpu_geometry', 'gpu_geom_div', 'blitter', 'gpu_raster',
        'gpu_v1', 'gpu_texture_cache', 'gpu_copy565', 'gpu_perspective',
        'gpu_triangle', 'gpu_blit_dma', 'font_ram', 'video_bus_stage')]
    gpu += [source/f'tang/rtl/board/{name}.v' for name in (
        'ddr_dcfifo', 'cdc_word', 'ahb_exts_bridge')]
    files = [debug, unit, chain, accel, *gpu]
    result = dict(passed=False, scope='RTL only; no SDF or metastability model',
                  sha256={str(f): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}, cases=[])
    try:
        with tempfile.TemporaryDirectory(prefix='neo-debug-') as tmp:
            tmp = Path(tmp)
            iv = shutil.which('iverilog')
            if iv:
                ivcmd = [iv]
                vvp = shutil.which('vvp')
            else:
                base = Path('/tmp/console-usb-sim-tools/extracted/usr')
                ivcmd = [str(base/'bin/iverilog'), '-B', str(base/'lib/x86_64-linux-gnu/ivl')]
                vvp = str(base/'bin/vvp')
            with (out/'unit_build.log').open('w') as log:
                subprocess.run([*ivcmd, '-g2012', '-s', 'neo_gpu_debug_tb', '-o', str(tmp/'unit'),
                                str(unit), str(debug)], stdout=log, stderr=subprocess.STDOUT,
                               check=True, timeout=60)
            for name, hp, mp, phase in [('nominal', 6.25, 6.667, .371),
                                        ('drift', 6.29, 6.61, 4.777),
                                        ('125_124_5', 4, 4.016064, .213)]:
                run = subprocess.run([vvp, str(tmp/'unit'), f'+hp={hp}', f'+mp={mp}', f'+phase={phase}'],
                                     capture_output=True, text=True, timeout=30)
                (out/f'{name}.log').write_text(run.stdout+run.stderr)
                passed = run.returncode == 0 and 'PASS:' in run.stdout
                result['cases'].append(dict(name=name, hp=hp, mp=mp, phase=phase, passed=passed))
                if not passed:
                    raise RuntimeError(run.stdout+run.stderr)
                print(run.stdout.splitlines()[0], flush=True)
            for bench in (accel, chain):
                obj = tmp/bench.stem
                with (out/f'{bench.stem}_build.log').open('w') as log:
                    subprocess.run(['verilator', '--binary', '--timing', '-Wno-fatal', '-j', '2',
                                    '--top-module', bench.stem, '--Mdir', str(obj),
                                    *map(str, [bench, debug, *gpu])], cwd=ROOT, stdout=log,
                                   stderr=subprocess.STDOUT, check=True, timeout=240)
                run = subprocess.run([str(obj/f'V{bench.stem}')], cwd=ROOT,
                                     capture_output=True, text=True, timeout=30)
                (out/f'{bench.stem}.log').write_text(run.stdout+run.stderr)
                passed = run.returncode == 0 and 'PASS:' in run.stdout
                result['cases'].append(dict(name=bench.stem, passed=passed))
                if not passed:
                    raise RuntimeError(run.stdout+run.stderr)
                print(run.stdout.splitlines()[0], flush=True)
        result['passed'] = True
    finally:
        (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
