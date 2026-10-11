#!/usr/bin/env python3
"""Render the full 300 s ASTRILLA reference movie (software, not LCD capture)."""
import argparse
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
import hashlib
import json
import multiprocessing
from pathlib import Path
import subprocess
from render_astrilla import Scene, ROOT


def initialize(hardware_geometry=False):
    global scene
    scene = Scene(geometry=hardware_geometry)
    scene.cached = lru_cache(maxsize=1461)(scene.cached)


def frame(t):
    return scene.render(t, fast=True)[0].tobytes()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--jobs', type=int, default=4)
    p.add_argument('--fps', type=int, default=55)
    p.add_argument('--first-frame', type=int, default=0)
    p.add_argument('--last-frame', type=int, default=16500)
    p.add_argument('--hardware-geometry', action='store_true', help='G3D1 scene, including R19 portals and crystal bloom')
    p.add_argument('--firmware-manifest', type=Path, help='Manifest matching the rendered G3D1 application')
    a = p.parse_args()
    if not 1 <= a.jobs <= 4 or not 1 <= a.fps <= 55:
        p.error('jobs: 1..4; fps: 1..55')
    if not 0 <= a.first_frame < a.last_frame <= 16500:
        p.error('Invalid phase interval')
    if a.hardware_geometry and not a.firmware_manifest:
        p.error('--hardware-geometry requires --firmware-manifest')
    snapshot = json.loads((a.firmware_manifest or ROOT/'assets/astrilla/packed/firmware.json').read_text())
    if a.hardware_geometry and snapshot.get('geometry_abi') != 'G3D1':
        p.error('The supplied manifest does not identify G3D1')
    count = (a.last_frame-a.first_frame)*a.fps//55
    if count < 2*a.jobs:
        p.error('Interval too short')
    a.out.parent.mkdir(parents=True, exist_ok=True)
    commands = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pixel_format',
                'rgb24', '-video_size', '800x480', '-framerate', str(a.fps),
                '-i', '-', '-an', '-c:v', 'libx264', '-threads', '2', '-preset',
                'fast', '-crf', '22', '-maxrate', '2500k', '-bufsize', '5000k',
                '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(a.out)]
    # Bound outstanding full RGB frames, including out-of-order worker results.
    phases = iter(a.first_frame+i*55//a.fps for i in range(count))
    with ProcessPoolExecutor(max_workers=a.jobs, initializer=initialize,
                             initargs=(a.hardware_geometry,),
                             mp_context=multiprocessing.get_context('spawn')) as pool:
        with subprocess.Popen(commands, stdin=subprocess.PIPE) as encoder:
            try:
                pending = deque(pool.submit(frame, next(phases)) for _ in range(2*a.jobs))
                done = 0
                while pending:
                    encoder.stdin.write(pending.popleft().result())
                    phase = next(phases, None)
                    if phase is not None:
                        pending.append(pool.submit(frame, phase))
                    done += 1
                    if done % (10*a.fps) == 0:
                        print(f'PREVIEW {done/a.fps:.0f}/{count/a.fps:g} s', flush=True)
            finally:
                encoder.stdin.close()
            if encoder.wait(timeout=60):
                raise RuntimeError('Video encoder failed')
    manifest = dict(source='software GPU/pixel/composition reference, not LCD capture',
                    duration_seconds=count/a.fps, frames=count, fps=a.fps, audio=False,
                    first_frame=a.first_frame, last_frame=a.last_frame,
                    sha256=hashlib.sha256(a.out.read_bytes()).hexdigest(),
                    firmware=snapshot, hardware_geometry=a.hardware_geometry)
    a.out.with_suffix('.json').write_text(json.dumps(manifest, indent=2)+'\n')


if __name__ == '__main__':
    main()
