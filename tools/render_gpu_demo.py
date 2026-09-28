#!/usr/bin/env python3
"""Render the actual G2 firmware reference and palette as an 800x480 PNG.

Runs the firmware's C reference rasterizer on the host with RAM-backed pages.
No independent copy of the drawing commands, algorithms, or palette is kept.
Requires a C compiler and Pillow; does not build or program the FPGA.
"""
import argparse
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def brace_block(source, marker):
    """Extract a known C function/loop including its balanced brace block."""
    start = source.index(marker)
    opening = source.index('{', start)
    depth = 0
    for end in range(opening, len(source)):
        if source[end] == '{':
            depth += 1
        elif source[end] == '}':
            depth -= 1
            if depth == 0:
                return source[start:end+1]
    raise ValueError(f'Unclosed C block: {marker}')


def render(output, hardware_log=None):
    if sys.byteorder != 'little':
        raise SystemExit('This host reference requires little-endian C text words')
    firmware = ROOT / 'fw_console'
    demo = (firmware / 'gpu_demo.h').read_text()
    reference, scene = demo.split('static int gpu_accel_demo(void)', 1)
    setup = scene[scene.index('    uint8_t *target='):scene.index('    unsigned before=')]
    make_command = brace_block((firmware / 'gpu.c').read_text(), 'gpu_command gpu_make_command(')
    palette = 'for(unsigned i=0;i<256;++i) GPU[0x100+i]=gpu_demo_palette_color(i);'
    source = '''#include <stdint.h>
#include <stdio.h>
#include "gpu.h"
static uint8_t pages[16][GPU_PAGE_BYTES];
static uint32_t registers[512];
#undef GPU_PAGE_ADDR
#define GPU_PAGE_ADDR(p) ((uintptr_t)pages[(p)])
#define GPU registers
void gpu_publish_surface(unsigned long address, unsigned long bytes) {}
void gpu_font_write(unsigned address, const uint8_t *bytes, unsigned count) {}
''' + make_command + '\n' + reference + '\nint main(void) {\n' + setup + '''
    for (unsigned i=0; i<demo_count; ++i) reference_draw(&demo_commands[i],ref);
''' + palette + '''
    if (fwrite(ref,1,bytes,stdout)!=bytes) return 1;
    if (fwrite(&registers[0x100],sizeof(uint32_t),256,stdout)!=256) return 1;
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix='console_gpu_render_') as directory:
        work = Path(directory)
        (work / 'build').mkdir()
        subprocess.run([sys.executable, str(ROOT / 'tools/gen_gpu_font.py'),
                        str(ROOT / 'tang/rtl/video/font8x16.hex'),
                        str(work / 'build/gpu_font.h')], check=True)
        (work / 'render.c').write_text(source)
        subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Wno-unused-parameter',
                        '-I', str(firmware), str(work / 'render.c'), '-o', str(work / 'render')], check=True)
        raw = subprocess.run([str(work / 'render')], check=True, capture_output=True).stdout
    pixels = 800 * 480
    if len(raw) != pixels + 256 * 4:
        raise SystemExit(f'Unexpected reference output size: {len(raw)}')
    indices = raw[:pixels]
    checksum = sum(v[0] for v in struct.iter_unpack('<I', indices)) & 0xffffffff
    # Compare against the recorded image verified pixel by pixel on the board.
    if hardware_log is not None:
        expected = re.findall(r'BLIT END errors=0 commands=\d+ sum=([0-9a-fA-F]+)', hardware_log.read_text())
        if not expected or any(checksum != int(value, 16) for value in expected):
            raise SystemExit(f'Reference checksum {checksum:08x} differs from the recorded hardware image')
    rgb = []
    for (color,) in struct.iter_unpack('<I', raw[pixels:]):
        rgb.extend((((color >> shift) & 63) * 255 + 31) // 63 for shift in (12, 6, 0))
    picture = Image.frombytes('P', (800, 480), indices)
    picture.putpalette(rgb)
    output.parent.mkdir(parents=True, exist_ok=True)
    picture.convert('RGB').save(output)
    suffix = ', matches hardware log' if hardware_log is not None else ', software reference'
    print(f'{output}: 800x480, framebuffer checksum {checksum:08x}{suffix}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'TESTS/images/gpu_g2_ramps_expected.png')
    parser.add_argument('--hardware-log', type=Path)
    args=parser.parse_args()
    render(args.output,args.hardware_log)
