#!/usr/bin/env python3
"""Run a reviewed local bench against exact frozen R19 RTL, never hardware."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = HERE / 'rtl_inputs.json'
    inputs = json.loads(manifest.read_text())['sources']
    for name, digest in inputs.items():
        assert sha(ROOT / name) == digest, name
    bench = HERE / 'tb_reviewed_r2.sv'
    assert bench.is_file()
    out = HERE / 'rtl_run_02'
    out.mkdir()
    sources = [ROOT / n for n in inputs if n.endswith('.v')]
    font = next(ROOT / n for n in inputs if n.endswith('/font8x16.hex'))
    shutil.copy2(font, out / 'font8x16.hex')
    result = dict(passed=False, hardware_access=False, started_unix=time.time(),
                  scope='Frozen R19 application RTL, real gpu_accel slot and ddr_gpu_arb; external DDR endpoint model only',
                  limits=['No DDR PHY or physical routing/timing qualification.',
                          'No mapped NCP instrumentation is present in this application RTL simulation.'],
                  inputs={**inputs, str(bench.relative_to(ROOT)): sha(bench),
                          str(manifest.relative_to(ROOT)): sha(manifest),
                          str(Path(__file__).relative_to(ROOT)): sha(Path(__file__))})
    try:
        with (out / 'compile.log').open('x') as log:
            command = ['/usr/bin/verilator', '--binary', '-j', '4', '--timing',
                       '-Wno-fatal', '--top-module', 'tb', '--Mdir', str(out / 'obj'),
                       str(bench), *map(str, sources)]
            result['compile_command'] = command
            subprocess.run(command, cwd=out, stdout=log, stderr=log, check=True, timeout=180)
        with (out / 'simulation.log').open('x') as log:
            subprocess.run([str(out / 'obj/Vtb')], cwd=out, stdout=log, stderr=log,
                           check=True, timeout=90)
        result['passed'] = 'PASS R19 REAL SLOT CLEAR' in (out / 'simulation.log').read_text()
        for name, digest in result['inputs'].items():
            assert sha(ROOT / name) == digest, name
    except Exception as exc:
        result['error'] = repr(exc)
    finally:
        result['finished_unix'] = time.time()
        result['logs'] = {p.name: sha(p) for p in out.glob('*.log')}
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result), flush=True)
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
