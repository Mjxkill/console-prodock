#!/usr/bin/env python3
"""Small pixel-path cases, checked against an existing N38 RTL comparator.

The integer oracle compares all three 1-MiB windows, including their guards.
No FPGA programming or board access occurs here.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from test_gpu_v1 import Model

ROOT = Path(__file__).resolve().parents[1]
N38 = ROOT/'tang/impl/console_neo_n38r0/source'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scene(name):
    m = Model()
    initial = bytes(m.memory)
    m.target(width=64, height=32, stride=160, zstride=192)
    m.clear(color=0x1084)
    if name == 'masked_rectangles':
        for x, width, y in ((1, 1, 1), (14, 5, 4), (31, 2, 8),
                            (45, 18, 13), (0, 63, 20), (5, 30, 26)):
            m.clear(flags=3, color=0xf800 ^ (x*137), z=1000+x,
                    x=x, y=y, w=width, h=2)
    else:
        textured = name in ('textured', 'perspective')
        perspective = name == 'perspective'
        depth = name == 'depth'
        if textured:
            m.texture(w=16, h=16, stride=32, mu=1, mv=1)
            m.plane(0, dx=65536)
            m.plane(1, dy=65536)
        if perspective:
            m.plane(2, origin=65536)
        if depth:
            m.plane(3, origin=0x12340000)
        m.material(flags=int(textured) | (16 if perspective else 0) | (6 if depth else 0),
                   alpha=128 if name == 'alpha' else 256, color=0xd5ab)
        m.triangle([(5, 3), (58, 7), (9, 29)])
    return m, initial


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--simulation', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--prepare-only', action='store_true',
                   help='Write oracle vectors as PREPARED; do not claim RTL validation')
    a = p.parse_args()
    prior = json.loads((a.simulation/'result.json').read_text())
    executable = (a.simulation/'obj/Vgpu_accel_tb').resolve(strict=True)
    if not prior['pass_cycle_equivalence'] or not prior['reference_video']:
        raise ValueError('Need a successful comparator with frozen video children')
    frozen = {k: v for k, v in prior['sha256'].items()
              if k.startswith('tang/impl/console_neo_n38r0/source/')}
    if not frozen or any(sha(ROOT/k) != v for k, v in frozen.items()):
        raise ValueError('Missing or changed N38 comparator inputs')
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    summary = {}
    for name in ('masked_rectangles', 'solid', 'depth', 'alpha', 'textured', 'perspective'):
        m, initial = scene(name)
        case = out/name
        case.mkdir()
        count = len(m.commands)//8
        if not 1 <= count <= 16:
            raise ValueError('Short comparator accepts at most sixteen commands')
        for filename, data in (('initial.hex', initial), ('expected.hex', m.memory)):
            (case/filename).write_text(''.join(f'{b:02x}\n' for b in data))
        (case/'commands.hex').write_text(''.join(f'{w:08x}\n' for w in m.commands))
        shutil.copyfile(a.simulation/'font8x16.hex', case/'font8x16.hex')
        report = dict(status='PREPARED', world=False, bytes_compared=len(initial),
                      input_commands=count, invalid_commands=0, shader_rejected=m.rejected,
                      passed_pixels=m.passed, vertices=0, triangles=0, culled=0, clipped=0, slivers=0,
                      case=name, width=64, height=32, color_stride=160, depth_stride=192,
                      simulation_executable=str(executable), executable_sha256=sha(executable),
                      comparator_result_sha256=sha(a.simulation/'result.json'),
                      n38_sources_sha256=frozen,
                      generator_sha256=sha(Path(__file__)),
                      oracle_sha256=sha(ROOT/'TESTS/test_gpu_v1.py'))
        report_path = case/'result.json'
        report_path.write_text(json.dumps(report, indent=2)+'\n')
        if a.prepare_only:
            summary[name] = dict(status='PREPARED', commands=count, passed_pixels=m.passed)
            continue
        with (case/'simulation.log').open('w') as log:
            subprocess.run([str(executable), f'+ncmd={count}', '+bad=0', '+raster_bad=0',
                            '+v1_bad=0', f'+v1_pass={m.passed}',
                            f'+v1_texture={int(name in ("textured", "perspective"))}', '+rgbinit=3'],
                           cwd=case, stdout=log, stderr=log, check=True, timeout=120)
        log = (case/'simulation.log').read_text()
        if 'PASS:' not in log or 'ACCEL EQUIVALENCE:' not in log:
            raise RuntimeError('Missing RTL result')
        report.update(status='PASS', simulation_log_sha256=sha(case/'simulation.log'))
        report_path.write_text(json.dumps(report, indent=2)+'\n')
        summary[name] = dict(status='PASS', commands=count, passed_pixels=m.passed)
    (out/'result.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
