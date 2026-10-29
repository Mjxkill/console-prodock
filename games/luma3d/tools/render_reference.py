#!/usr/bin/env python3
"""Replay actual C renderer commands through the independent integer GPU model.

No software projection in the native renderer. This offline oracle models the
FPGA command stream, and is never a playback resource on the board.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import time
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'TESTS')]
from render_astrilla import FastAstrillaModel
from gpu_geometry_model import Geometry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('prefix', type=Path)
    args = parser.parse_args()
    prefix = str(args.prefix)
    info = json.loads(Path(prefix+'.json').read_text())
    memory = Path(prefix+'.memory').read_bytes()
    commands = Path(prefix+'.commands').read_bytes()
    assert len(memory) == info['bytes'] and len(commands) == info['commands']*32
    model = FastAstrillaModel(b'', 0x08000000)
    model.memory = bytearray(memory)
    def address(a):
        assert 0x800000 <= a < 0x800000+len(memory), hex(a)
        return a-0x800000
    model.at = address
    geometry = Geometry(model)
    start = time.monotonic()
    for c in struct.iter_unpack('<8I', commands):
        geometry.command(list(c))
    assert model.memory[8<<20:] == memory[8<<20:], 'Immutable asset region overwritten'
    page = info['page']*info['page_bytes']
    w,h,pitch = info['width'],info['height'],info['pitch']
    raw = b''.join(model.memory[page+y*pitch:page+y*pitch+w*2] for y in range(h))
    a = np.frombuffer(raw, dtype='<u2').reshape(h,w).astype(np.uint32)
    rgb = np.stack(((a>>11)*255//31,((a>>5)&63)*255//63,(a&31)*255//31),axis=-1).astype(np.uint8)
    Image.fromarray(rgb).resize((w*2,h*2),Image.Resampling.NEAREST).save(prefix+'.png')
    Path(prefix+'.rgb565').write_bytes(raw)
    info.update(model_seconds=time.monotonic()-start,vertices=geometry.vertices,
                triangles=geometry.triangles,clipped=geometry.clipped,culled=geometry.culled,
                slivers=geometry.slivers,fragments=model.passed,
                command_sha256=hashlib.sha256(commands).hexdigest(),
                asset_sha256=hashlib.sha256(memory[8<<20:]).hexdigest(),
                image_sha256=hashlib.sha256(raw).hexdigest(),
                scope='Independent integer GPU command oracle; no hardware timing or FPS claim')
    Path(prefix+'.reference.json').write_text(json.dumps(info,indent=2)+'\n')
    print(json.dumps(info))


if __name__ == '__main__':
    main()
