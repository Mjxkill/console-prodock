#!/usr/bin/env python3
"""Render an L11 tile map pose and check the firmware pixel reference.

The firmware scene and its CPU reference run unmodified on the host, with
the scene memory mapped at its DDR address and under UBSan. Their hash is
compared with gpu_compose.py, which shares no code with them.
"""
import argparse
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile

from PIL import Image
from render_gpu_demo import ROOT, brace_block
from gpu_compose import W, H, compose, frame_hash, palette_rgb

BASE, BYTES, POSES = 0x03000000, 0x00030000, 4


def run_firmware_scene(pose, step):
    firmware = ROOT / 'fw_console'
    driver = (firmware / 'gpu.c').read_text()
    reference = (firmware / 'gpu_layers_demo.h').read_text()
    source = '''#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include "gpu_tiles_scene.h"
static int max_int(int a,int b) { return a>b ? a : b; }
static int min_int(int a,int b) { return a<b ? a : b; }
static uint8_t layer_reference_row[GPU_WIDTH];
''' + '\n'.join(brace_block(driver, signature) for signature in (
        'gpu_layer gpu_make_layer(', 'gpu_layer gpu_make_tile_layer(', 'gpu_sprite gpu_make_sprite(')) + '\n' + '\n'.join(
        brace_block(reference, signature) for signature in (
            'static uint32_t rotate32(', 'static void reference_tile_row(', 'static unsigned gpu_scene_reference_hash(')) + '''
int main(int argc,char **argv)
{
    static gpu_layer layers[16];
    static gpu_sprite sprites[64];
    if(sizeof(TILES_BASE)<sizeof(void *)-4 || argc!=3) return 2;
    // The firmware dereferences 32-bit DDR addresses: give them real memory.
    void *memory=mmap((void *)TILES_BASE,TILES_BYTES,PROT_READ|PROT_WRITE,
        MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0);
    if(memory!=(void *)TILES_BASE) {perror("mmap at the DDR address");return 3;}
    memset(memory,0xa5,TILES_BYTES);
    tiles_scene_build();
    tiles_scene_pose((unsigned)atoi(argv[1]),atoi(argv[2]),layers,sprites);
    uint32_t hash=gpu_scene_reference_hash(layers,sprites),palette[256];
    for(unsigned i=0;i<256;++i) palette[i]=gpu_demo_palette_color(i);
    if(fwrite(memory,1,TILES_BYTES,stdout)!=TILES_BYTES || fwrite(layers,1,sizeof(layers),stdout)!=sizeof(layers)
            || fwrite(sprites,1,sizeof(sprites),stdout)!=sizeof(sprites)
            || fwrite(palette,4,256,stdout)!=256 || fwrite(&hash,4,1,stdout)!=1) return 4;
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix='console_tiles_render_') as directory:
        work = Path(directory)
        (work / 'scene.c').write_text(source)
        # The mapping above makes the 32-bit DDR addresses valid host pointers.
        subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Wno-unused-function', '-Wno-int-to-pointer-cast',
                        '-fsanitize=undefined', '-fno-sanitize-recover=all',
                        '-I', str(firmware), str(work / 'scene.c'), '-o', str(work / 'scene')], check=True)
        return subprocess.run([str(work / 'scene'), str(pose), str(step)], check=True, capture_output=True).stdout


def render(pose, output, hardware_log=None, step=0):
    raw = run_firmware_scene(pose, step)
    if len(raw) != BYTES + 512 + 1024 + 1024 + 4:
        raise SystemExit('Unexpected scene data size')
    layers = list(struct.iter_unpack('<8I', raw[BYTES:BYTES + 512]))
    sprites = list(struct.iter_unpack('<4I', raw[BYTES + 512:BYTES + 1536]))
    firmware_hash, = struct.unpack('<I', raw[-4:])

    def read(address, count):
        if not BASE <= address <= BASE + BYTES - count:
            raise SystemExit(f'Read outside the scene memory: {address:#x}')
        return raw[address - BASE:address - BASE + count]
    indices = compose(layers, sprites, read)
    checksum = frame_hash(indices)
    if checksum != firmware_hash:
        raise SystemExit(f'Firmware reference {firmware_hash:08x} differs from the host composition {checksum:08x}')
    if hardware_log:
        recorded = re.findall(rf'TILES POSE {pose} hash=([0-9a-fA-F]+)', hardware_log.read_text())
        if not recorded or any(int(value, 16) != checksum for value in recorded):
            raise SystemExit(f'Hardware image differs from {checksum:08x}')
    picture = Image.frombytes('P', (W, H), bytes(indices))
    picture.putpalette(palette_rgb(raw[-1028:-4]))
    output.parent.mkdir(parents=True, exist_ok=True)
    picture.convert('RGB').save(output)
    print(f'{output}: pose {pose}, hash {checksum:08x}, firmware reference identical'
          + (', matches hardware log' if hardware_log else ''))
    return checksum


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pose', type=int, choices=range(POSES), default=0)
    parser.add_argument('--step', type=int, default=0, help='scroll step of the W animation')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--hardware-log', type=Path)
    parser.add_argument('--sweep', action='store_true',
                        help='check every pose and the scroll steps around tile boundaries and both ends')
    args = parser.parse_args()
    if args.sweep:
        with tempfile.TemporaryDirectory(prefix='console_tiles_sweep_') as directory:
            for pose in range(POSES):
                render(pose, Path(directory) / 'pose.png', args.hardware_log)
            for step in (1, 5, 6, 15, 16, 17, 208, 415, 416):
                render(0, Path(directory) / 'step.png', step=step)
        print('PASS: firmware reference and host composition identical on every pose and step')
        sys.exit(0)
    render(args.pose, args.output or ROOT / f'TESTS/images/gpu_l11_pose{args.pose}_expected.png',
           args.hardware_log, args.step)
