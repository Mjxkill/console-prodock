#!/usr/bin/env python3
"""Protected compiler/acceptance harness; real RTL, bounded fault scenarios."""
from pathlib import Path
import json
import re
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent


def main():
    with tempfile.TemporaryDirectory(prefix='neo-clear-chain-') as tmp:
        binary = str(Path(tmp) / 'obj/Vbench')
        command = ['/usr/bin/verilator', '--binary', '--timing', '-j', '2', '-Wno-fatal',
                   '-MAKEFLAGS', 'VM_PARALLEL_BUILDS=0', '--top-module', 'bench',
                   '--Mdir', str(Path(tmp) / 'obj'), 'bench.sv', 'native_monitor.sv']
        command += [p.name for p in sorted(HERE.glob('*.v'))]
        compile_run = subprocess.run(command, cwd=HERE, capture_output=True, text=True, timeout=48)
        if compile_run.returncode:
            print(compile_run.stdout[-3000:] + compile_run.stderr[-6000:])
            return 1
        print('FULL_CHAIN_COMPILE_PASS')
        cases = []
        for seed, fault in [(1, 0), (8, 0), (1, 1), (1, 2), (1, 3), (1, 4), (1, 5)]:
            run = subprocess.run([binary, f'+seed={seed}', f'+fault={fault}'], cwd=HERE,
                                 capture_output=True, text=True, timeout=3)
            log = run.stdout + run.stderr
            print(f'CASE seed={seed} fault={fault} returncode={run.returncode}\n{log}')
            if fault == 0:
                ok = run.returncode == 0 and bool(re.search(r'BASELINE_PASS accepted=1 words=16 stalls=[1-9]', log))
            elif fault in (1, 2):
                ok = run.returncode != 0 and 'CHECK_FAIL COMPLETION' in log and 'accepted=0' in log
            elif fault == 3:
                ok = run.returncode != 0 and 'CHECK_FAIL' in log and bool(re.search(r'accepted=[1-9]', log))
            elif fault == 5:
                ok = run.returncode != 0 and 'CHECK_FAIL NATIVE_COMMAND' in log
            else:
                ok = run.returncode == 0 and 'RESET_RECOVERY_PASS' in log
            cases.append({'seed': seed, 'fault': fault, 'passed': ok})
        print(json.dumps({'passed': all(case['passed'] for case in cases), 'cases': cases}))
        return int(not all(case['passed'] for case in cases))


if __name__ == '__main__':
    raise SystemExit(main())
