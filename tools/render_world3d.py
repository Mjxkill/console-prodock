#!/usr/bin/env python3
"""Live world state -> C command stream -> independent G3D1/pixel reference."""
import argparse
import ctypes
import json
import struct
import subprocess
import tempfile
import zlib
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from render_astrilla import ROOT, FastAstrillaModel
from render_gpu_demo import brace_block
from gpu_geometry_model import Geometry


class State(ctypes.Structure):
    _fields_ = [(name, ctypes.c_float) for name in
                ('x', 'y', 'z', 'yaw', 'pitch', 'actor_x', 'actor_y', 'actor_z', 'actor_heading')]


class Info(ctypes.Structure):
    _fields_ = [('objects', ctypes.c_uint), ('billboards', ctypes.c_uint)]


class World:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='world3d_')
        work = Path(self.tmp.name)
        driver = (ROOT/'fw_console/gpu.c').read_text()
        code = '#define ASTRILLA_HOST 1\n#include "world3d_scene.h"\n'
        code += '\n'.join(brace_block(driver, signature) for signature in (
            'gpu_command gpu_make_command(', 'gpu_layer gpu_make_layer(', 'gpu_sprite gpu_make_sprite('))
        code += '''
static gpu_command commands[4096];static unsigned count;
static void emit(const gpu_command *c){if(count<4096)commands[count]=*c;++count;}
unsigned command_count(void){return count;}
uint32_t *command_words(void){return commands[0].words;}
int prepare(uint8_t *p){return world_prepare(p,p+AS3_HW_BYTES);}
void automatic(unsigned t,world3d_state *s){*s=world_auto(t);}
int valid(const world3d_state *s){return world_state_valid(s);}
int render(unsigned t,const world3d_state *s,world3d_info *i){
 count=0;as3_enemy_triangles=0;gpu_v1_context c;gpu_v1_init(&c,emit);return world_render(&c,t,0,s,i)&&count<=4096;}
'''
        (work/'world.c').write_text(code)
        subprocess.run(['cc', '-std=c11', '-O2', '-ffp-contract=off', '-Wall', '-Wextra',
                        '-Wno-unused-function', '-Werror', '-fsanitize=undefined,float-cast-overflow',
                        '-fno-sanitize-recover=all', '-shared', '-fPIC', '-I', str(ROOT/'fw_console'), '-I', str(ROOT/'games/world3d/src'), '-I', str(ROOT/'games/common/astrilla'),
                        str(work/'world.c'), str(ROOT/'fw_console/gpu_v1.c'),
                        str(ROOT/'fw_console/gpu_geometry.c'), '-o', str(work/'world.so')], check=True)
        self.lib = ctypes.CDLL(str(work/'world.so'))
        self.lib.command_words.restype = ctypes.POINTER(ctypes.c_uint32)
        mesh = (ctypes.c_uint8 * 33792)()
        assert self.lib.prepare(mesh)
        self.mesh = bytes(mesh)
        self.assets = (ROOT/'games/astrilla/assets/packed/astrilla.bin').read_bytes()
        self.base = json.loads((ROOT/'games/astrilla/assets/packed/manifest.json').read_text())['base']

    def state(self, frame):
        state = State()
        self.lib.automatic(frame, ctypes.byref(state))
        return state

    def commands(self, frame, state):
        info = Info()
        assert self.lib.render(frame, ctypes.byref(state), ctypes.byref(info))
        count = self.lib.command_count()
        words = self.lib.command_words()
        return [[words[8*i+j] for j in range(8)] for i in range(count)], info

    def render(self, frame, state, poison=0xa5):
        commands, info = self.commands(frame, state)
        pixels = FastAstrillaModel(self.assets, self.base, poison)
        old_at = pixels.at
        pixels.at = lambda a: 5*(1<<20)+a-0x06000000 if 0x06000000<=a<0x06008400 else old_at(a)
        pixels.memory[5*(1<<20):5*(1<<20)+len(self.mesh)] = self.mesh
        geometry = Geometry(pixels)
        for command in commands:
            geometry.command(command)
        for page in (0, 2):
            assert pixels.memory[page*(1<<20)+192000:(page+1)*(1<<20)] == bytes([poison])*((1<<20)-192000)
        assert pixels.memory[1<<20:2<<20] == bytes([poison])*(1<<20)
        assert pixels.memory[5*(1<<20):5*(1<<20)+len(self.mesh)] == self.mesh
        assert pixels.memory[8*(1<<20):] == self.assets
        raw = bytes(pixels.memory[:192000])
        values = np.frombuffer(raw, dtype='<u2').reshape(240, 400).astype(np.uint32)
        rgb = np.stack(((values>>11)*255//31, ((values>>5)&63)*255//63, (values&31)*255//31), axis=-1)
        record = dict(frame=frame, state=list(struct.unpack('<9f', bytes(state))), commands=len(commands),
                      crc565=f'{zlib.crc32(raw):08x}', objects=info.objects, sprites3d=info.billboards,
                      vertices=geometry.vertices, triangles=geometry.triangles, clipped=geometry.clipped,
                      slivers=geometry.slivers, fragments=pixels.passed)
        return Image.fromarray(rgb.astype(np.uint8)), record


def cases(world):
    for frame in (0, 550, 1100, 2200, 3300, 4099, 4101, 4102, 4104, 4400, 5500, 6599):
        yield f'auto_{frame}', frame, world.state(frame)
    # Same simulation time, independent camera and actor edits, including inside geometry.
    for name, values in (
        ('front', (0, -2, 1, 0, 8, 0, -.7, 14, 64)),
        ('side', (13, -1, 14, -64, 0, 0, -.7, 14, 0)),
        ('near', (0, -.7, 13.8, 0, 0, 0, -.7, 14, 64)),
        ('up', (0, 1, 14, 32, -48, 0, -4, 14, 64)),
        ('actor', (0, -2, 1, 0, 8, 4, -2, 7, 90)),
        ('away', (0, -2, 1, 128, 0, 0, -.7, 14, 64)),
    ):
        yield name, 1111, State(*values)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT/'TESTS/gpu_geometry_20261010/world_reference')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    world = World()
    # Full automatic path submission under sanitizers; invalid game states emit nothing.
    for frame in range(6600):
        commands, info = world.commands(frame, world.state(frame))
        assert info.objects == 17 and info.billboards == 24 and len(commands) < 512
    for bad in (float('nan'), float('inf'), -float('inf'), 513, -513):
        for index in range(9):
            values = list(struct.unpack('<9f', bytes(world.state(0))))
            values[index] = bad
            state = State(*values)
            assert not world.lib.render(0, ctypes.byref(state), ctypes.byref(Info()))
            assert world.lib.command_count() == 0
    records = []
    render_cases = list(cases(world))
    sheet = Image.new('RGB', (1200, 240*((len(render_cases)+2)//3)))
    for index, (name, frame, state) in enumerate(render_cases):
        image, record = world.render(frame, state)
        record['name'] = name
        image.resize((800, 480)).save(args.out/f'{name}.png')
        ImageDraw.Draw(image).text((4, 4), name, fill='white')
        sheet.paste(image, (index%3*400, index//3*240))
        records.append(record)
        print(json.dumps(record), flush=True)
    sheet.save(args.out/'contact.png')
    (args.out/'expected.json').write_text(json.dumps(records, indent=2)+'\n')
    (args.out/'sweep.json').write_text(json.dumps(dict(status='PASS', states=6600, invalid=45, sanitizer=True), indent=2)+'\n')


if __name__ == '__main__':
    main()
