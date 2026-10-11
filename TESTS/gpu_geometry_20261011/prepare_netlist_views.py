#!/usr/bin/env python3
"""Split the already RTL-checked world into independent mapped-geometry runs.

Each view configures a complete frame. Regenerate its independent integer
oracle and require their concatenation to match the original shader trace.
This allows three official-primitive simulations to run concurrently.
"""
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'TESTS')]
from gpu_geometry_model import Geometry
from astra_preview_model import FastPixels
from test_gpu_v1 import Model

class Pixels(FastPixels, Model):
    pass

source = ROOT/'TESTS/gpu_geometry_20261011/rtl_world_validation_pipeline'
metadata = json.loads((source/'result.json').read_text())
assert metadata['status'] == 'PASS' and metadata['world'] and metadata['input_commands'] == 927
words = [int(s, 16) for s in (source/'commands.hex').read_text().split()]
original_shader = [int(s, 16) for s in (source/'shader.hex').read_text().split()]
initial = bytes.fromhex((source/'initial.hex').read_text())
combined = []
totals = {k:0 for k in ('vertices','triangles','culled','clipped','slivers')}
for index in range(3):
    out = source.parent/f'netlist_view{index}_reference'
    out.mkdir(exist_ok=False)
    pixels = Pixels()
    pixels.memory[:] = initial
    geometry = Geometry(pixels)
    commands = words[index*309*8:(index+1)*309*8]
    assert commands[0]>>24 == 22
    for offset in range(0, len(commands), 8):
        geometry.command(commands[offset:offset+8])
    assert not pixels.rejected
    combined.extend(pixels.commands)
    result = dict(status='PASS', scope='independent reference split from a passed full RTL test',
                  world=True, invalid_commands=0, input_commands=309,
                  shader_commands=len(pixels.commands)//8,
                  source=str(source), source_result_sha256=hashlib.sha256((source/'result.json').read_bytes()).hexdigest())
    for name in totals:
        result[name] = getattr(geometry, name)
        totals[name] += result[name]
    shutil.copyfile(source/'initial.hex', out/'initial.hex')
    (out/'commands.hex').write_text(''.join(f'{w:08x}\n' for w in commands))
    (out/'shader.hex').write_text(''.join(f'{w:08x}\n' for w in pixels.commands))
    (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(index, result['shader_commands'], flush=True)
assert combined == original_shader
assert all(totals[k] == metadata[k] for k in totals)
print('PASS: three independently configured views reproduce all 5385 shader commands and counters')
