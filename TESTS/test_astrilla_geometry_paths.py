#!/usr/bin/env python3
"""Exercise every ASTRILLA frame's hardware geometry, without pixel rendering."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from render_astrilla import Scene
from gpu_geometry_model import Geometry
from test_gpu_geometry_paths import MeshSink
from test_gpu_accel import triangle_pixels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    scene = Scene(geometry=True)
    sink = MeshSink(scene.geometry_bytes)
    maxima = dict(vertices=0, triangles=0, clipped=0, slivers=0)
    approximations = []
    affected_pixels = 0
    for frame in range(16500):
        geometry = Geometry(sink)
        for command in scene.commands(frame):
            geometry.command(command)
        for key in maxima:
            maxima[key] = max(maxima[key], getattr(geometry, key))
        for item in geometry.approximations:
            covered = list(triangle_pixels(*[v for p in item['points'] for v in p], width=400, height=240))
            affected_pixels += len(covered)
            approximations.append(dict(frame=frame, **item, covered_pixels=len(covered)))
        if frame % 550 == 0:
            print('ASTRILLA GEOMETRY', frame, maxima, 'affected_pixels', affected_pixels, flush=True)
    result = dict(status='PASS' if not affected_pixels else 'FAIL', poses=16500,
                  maxima=maxima, approximations=approximations, affected_pixels=affected_pixels,
                  scope='integer geometry and C commands; no pixel rendering or FPGA measurement')
    (args.out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(result, flush=True)
    assert not affected_pixels, 'Visible attribute approximation in ASTRILLA'


if __name__ == '__main__':
    main()
