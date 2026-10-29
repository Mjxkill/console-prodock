#!/usr/bin/env python3
"""Run local decoding and exact frozen GPU RTL tests; never invokes board tools."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RTL = ROOT / 'tang/impl/console_neo_n56r22r1_utw1_reports/source/tang/rtl/video'
IVL = Path('/tmp/console-usb-sim-tools/extracted/usr/bin/iverilog')
VVP = IVL.with_name('vvp')
SOURCES = [RTL / (name + '.v') for name in
           ('gpu_v1', 'gpu_copy565', 'gpu_texture_cache', 'gpu_triangle', 'gpu_perspective')]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    out = HERE / 'local_checks_01'
    out.mkdir(exist_ok=False)
    commands = [
        ['python3', '-B', '-m', 'unittest', '-v', 'test_umsc_decode'],
        [str(IVL), '-B', '/tmp/console-usb-sim-tools/extracted/usr/lib/x86_64-linux-gnu/ivl',
         '-g2012', '-s', 'tb_clear_footprint', '-o', str(out / 'sim.vvp'),
         str(HERE / 'tb_clear_footprint.v'), *map(str, SOURCES)],
        [str(VVP), str(out / 'sim.vvp')],
    ]
    results = []
    for index, command in enumerate(commands):
        process = subprocess.run(command, cwd=HERE, capture_output=True, text=True, timeout=30)
        log = out / f'{index}.log'
        log.write_text(process.stdout + process.stderr)
        results.append(dict(command=command, returncode=process.returncode,
                            log=str(log.relative_to(ROOT)), log_sha256=sha(log)))
        if process.returncode:
            (out / 'failure.json').write_text(json.dumps(results, indent=2) + '\n')
            raise RuntimeError(process.stdout + process.stderr)
    if 'PASS exact frozen RTL footprint' not in process.stdout:
        raise RuntimeError('expected RTL test conclusion absent')
    inputs = SOURCES + [HERE / name for name in
                       ('umsc_decode.py', 'test_umsc_decode.py', 'tb_clear_footprint.v', 'run_local_checks.py')]
    result = dict(passed=True, hardware_access=False, complete_integration=False,
                  commands=results, inputs={str(path.relative_to(ROOT)): sha(path) for path in inputs},
                  tools={str(IVL): sha(IVL), str(VVP): sha(VVP)},
                  limits=['direct gpu_v1 boundary only', 'no memory ownership proof',
                          'no routed timing or CPU/native DDR qualification'])
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, hardware_access=False)))


if __name__ == '__main__':
    main()
