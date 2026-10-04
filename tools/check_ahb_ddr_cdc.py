#!/usr/bin/env python3
"""Exercise AE350 AHB/DDR CDC with drift, phases, bursts and clock stops."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ['TESTS/rtl/ahb_ddr_cdc_tb.sv', 'tang/rtl/board/ahb_ddr_cdc.v',
           'tang/rtl/board/ddr_dcfifo.v']
CASES = [(10, 6.667, 0), (10, 6.667, 3.127), (10.02, 6.658, 0.237),
         (9.98, 6.676, 5.137), (6.667, 10, 1.337),
         (4, 4.016064, 0.213), (4.003203, 3.99361, 3.017)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    result = dict(status='running', sources={s: hashlib.sha256((ROOT/s).read_bytes()).hexdigest()
                                            for s in SOURCES}, cases=[])
    try:
        with (out/'compile.log').open('w') as log:
            subprocess.run(['verilator', '--binary', '--timing', '-j', '2',
                            '--top-module', 'ahb_ddr_cdc_tb', '--Mdir', str(out/'obj')]
                           + SOURCES, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                           check=True, timeout=180)
        for i, (hp, up, phase) in enumerate(CASES):
            proc = subprocess.run([str(out/'obj/Vahb_ddr_cdc_tb'), f'+hp={hp}',
                                   f'+up={up}', f'+phase={phase}'], cwd=ROOT,
                                  capture_output=True, text=True, timeout=30)
            (out/f'case{i}.log').write_text(proc.stdout+proc.stderr)
            passed = proc.returncode == 0 and 'PASS hp=' in proc.stdout
            result['cases'].append(dict(hclk_mhz=500/hp, ui_clk_mhz=500/up,
                phase_ns=phase, passed=passed, log=f'case{i}.log'))
            if not passed:
                raise RuntimeError(f'Case {i} failed: {proc.stdout}{proc.stderr}')
            print(proc.stdout.splitlines()[0], flush=True)
        result['status'] = 'pass'
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
