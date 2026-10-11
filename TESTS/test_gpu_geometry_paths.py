#!/usr/bin/env python3
"""Check every automatic world pose against the integer geometry specification.

This complements pixel/RTL tests: it exercises all 6,600 camera states while
skipping the already-tested pixel renderer. Attribute approximations are
permitted only for the four known triangles that cover no pixel centers.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from gpu_geometry_model import Geometry
from render_world3d import World
from test_gpu_accel import triangle_pixels


class MeshSink:
    def __init__(self, mesh):
        self.memory = mesh

    def at(self, address):
        offset = address-0x06000000
        assert 0 <= offset <= len(self.memory)-32, hex(address)
        return offset

    def apply(self, command):
        pass

    def plane(self, index, origin, dx, dy):
        assert 0 <= index < 4
        assert -(1 << 47) <= origin < (1 << 47), (index, origin)
        assert all(-(1 << 31) <= value < (1 << 31) for value in (dx, dy))

    def triangle(self, points):
        assert all(0 <= x <= 400 and 0 <= y <= 240 for x, y in points)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    world = World()
    sink = MeshSink(world.mesh)
    maxima = dict(vertices=0, triangles=0, clipped=0, slivers=0)
    fallback_frames = []
    for frame in range(6600):
        commands, info = world.commands(frame, world.state(frame))
        geometry = Geometry(sink)
        for command in commands:
            geometry.command(command)
        assert geometry.vertices == 892 and info.objects == 17 and info.billboards == 24
        for name in maxima:
            maxima[name] = max(maxima[name], getattr(geometry, name))
        if geometry.slivers:
            details=[]
            for approximation in geometry.approximations:
                covered=list(triangle_pixels(*[v for p in approximation['points'] for v in p],width=400,height=240))
                assert not covered, (frame, approximation, covered)
                details.append(dict(**approximation, covered_pixels=len(covered)))
            fallback_frames.append(dict(frame=frame, slivers=geometry.slivers, details=details))
        if frame % 550 == 0:
            print('WORLD GEOMETRY', frame, maxima, flush=True)
    expected=[(4099,1),(4101,1),(4102,1),(4104,1)]
    matched=[(r['frame'],r['slivers']) for r in fallback_frames]==expected
    result = dict(status='PASS' if matched else 'FAIL', poses=6600,
                  maxima=maxima, fallback_frames=fallback_frames,
                  scope='integer geometry and C commands; no pixel rendering or FPGA measurement')
    (args.out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(result, flush=True)
    assert matched, 'Changed attribute approximation coverage'


if __name__ == '__main__':
    main()
