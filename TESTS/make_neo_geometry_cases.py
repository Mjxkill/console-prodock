#!/usr/bin/env python3
"""Isolate the three faces of the validated Neo geometry scene.

Reuse the already compiled RTL comparator, but rerun every byte comparison
against an independently calculated image for each case. No board access.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from gpu_geometry_model import Geometry
from test_gpu_v1 import Model


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vectors', type=Path, required=True)
    p.add_argument('--simulation', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    reference = json.loads((a.vectors/'result.json').read_text())
    simulation = json.loads((a.simulation/'result.json').read_text())
    executable = (a.simulation/'obj/Vgpu_accel_tb').resolve(strict=True)
    words = [int(w, 16) for w in (a.vectors/'commands.hex').read_text().split()]
    initial = bytes.fromhex((a.vectors/'initial.hex').read_text())
    if (reference['status'] != 'PASS' or reference['input_commands'] != 11
            or not simulation['pass_cycle_equivalence'] or simulation['commands'] != 11
            or len(words) != 88 or len(initial) != 3*1024*1024):
        raise ValueError('Expected the validated eleven-command first-mesh scene')
    if words[80:85] != [0x22000000, 0x1740000, 0x1748000, 0x90003, 1]:
        raise ValueError('Unexpected source mesh; do not silently change the experiment')
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    results = {}
    for face, name in enumerate(('inside', 'near_clip', 'side_clip')):
        case = out/name
        case.mkdir()
        commands = list(words)
        commands[82] += face*32
        commands[83] = 0x90001
        pixels = Model()
        pixels.memory[:] = initial
        geometry = Geometry(pixels)
        for n in range(0, len(commands), 8):
            geometry.command(commands[n:n+8])
        for filename in ('initial.hex', 'font8x16.hex'):
            shutil.copyfile(a.simulation/filename, case/filename)
        (case/'commands.hex').write_text(''.join(f'{w:08x}\n' for w in commands))
        (case/'expected.hex').write_text(''.join(f'{b:02x}\n' for b in pixels.memory))
        report = dict(status='PREPARED', world=False, bytes_compared=len(initial),
                      input_commands=11, invalid_commands=0, shader_rejected=pixels.rejected,
                      passed_pixels=pixels.passed,
                      **{k:getattr(geometry,k) for k in ('vertices','triangles','culled','clipped','slivers')},
                      face=face, simulation_executable=str(executable),
                      executable_sha256=digest(executable),
                      comparator_result_sha256=digest(a.simulation/'result.json'),
                      source_vectors_sha256={n:digest(a.vectors/n) for n in ('commands.hex','initial.hex','result.json')})
        report_path = case/'result.json'
        report_path.write_text(json.dumps(report, indent=2)+'\n')
        with (case/'simulation.log').open('w') as log:
            subprocess.run([str(executable), '+ncmd=11', '+bad=0', '+raster_bad=0',
                            '+v1_bad=0', f'+v1_pass={pixels.passed}', '+rgbinit=3'],
                           cwd=case, stdout=log, stderr=log, check=True, timeout=120)
        log = (case/'simulation.log').read_text()
        if 'PASS:' not in log or 'ACCEL EQUIVALENCE:' not in log:
            raise RuntimeError('Missing RTL comparison result')
        report['status'] = 'PASS'
        report['simulation_log_sha256'] = digest(case/'simulation.log')
        report_path.write_text(json.dumps(report, indent=2)+'\n')
        results[name] = {k:report[k] for k in ('status','vertices','triangles','culled','clipped','passed_pixels')}
    (out/'result.json').write_text(json.dumps(results, indent=2)+'\n')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
