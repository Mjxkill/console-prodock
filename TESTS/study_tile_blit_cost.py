#!/usr/bin/env python3
"""L11 study: GPU time to draw a screen of tiles with the blitter (COPY, ZOOM 1:1).

This is the software approach that L11 did not retain; its figures are
quoted in ARCHI/GPU_L11_TILEMAPS.md. It runs the current RTL with a copy of
gpu_accel_tb.sv that also reports cycle counts, in /tmp, and compares every
pixel with an independent Python model. Simulated time, not a board
measurement: the bench applies its own DDR back-pressure.
"""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = Path('/tmp/console_tile_blit_cost')
W, H, SLOT = 800, 480, 1 << 20
MEM_HZ, BUS_HZ = 75e6, 80e6


def build():
    OUT.mkdir(exist_ok=True)
    tb = (ROOT / 'TESTS/rtl/gpu_accel_tb.sv').read_text()
    # Couverture propre à la régression d'origine : sans objet pour une mesure.
    old_cov = 'if(stalls==0 || full_writes<100 || cpu_reads<100 || scan_reads<100) $fatal(1,"Missing queue/burst/read coverage");'
    assert old_cov in tb
    tb = tb.replace(old_cov, '')
    old_loop = "for(integer i=0;i<ncmd*8;i++) write_reg('h10,commands[i]);"
    assert old_loop in tb
    tb = tb.replace(old_loop, 'start_cycle=cycle; ' + old_loop + ' sent_cycle=cycle;')
    old_pass = '$display("PASS: %0d commands'
    assert old_pass in tb
    tb = tb.replace(old_pass, '$display("MEASURE mem_cycles_total=%0d mem_cycles_submit=%0d",cycle-start_cycle,sent_cycle-start_cycle); ' + old_pass)
    tb = tb.replace('integer errors=0;', 'integer errors=0, start_cycle=0, sent_cycle=0;')
    # Le banc d'origine relit DONE toutes les 100 périodes : réduire à 10 pour la résolution.
    assert 'repeat(100) @(posedge hc);' in tb
    tb = tb.replace('repeat(100) @(posedge hc);', 'repeat(10) @(posedge hc);')
    tb = tb.replace('reg [31:0] commands [0:8191];', 'reg [31:0] commands [0:65535];')
    (OUT / 'tb.sv').write_text(tb)
    sources = [f'tang/rtl/video/{n}.v' for n in ('gpu_geometry','gpu_geom_div','gpu_v1','gpu_raster','gpu_texture_cache','gpu_copy565','gpu_perspective')]+['tang/rtl/video/gpu_accel.v', 'tang/rtl/video/blitter.v', 'tang/rtl/video/gpu_blit_dma.v',
               'tang/rtl/video/font_ram.v', 'tang/rtl/video/gpu_triangle.v', 'tang/rtl/board/ddr_dcfifo.v',
               'tang/rtl/board/cdc_word.v', 'tang/rtl/board/ddr_gpu_arb.v']
    (OUT / 'font8x16.hex').write_text((ROOT / 'tang/rtl/video/font8x16.hex').read_text())
    with (OUT / 'build.log').open('w') as log:
        subprocess.run(['verilator', '--binary', '--timing', '-Wno-fatal', '--top-module', 'gpu_accel_tb',
                        '--Mdir', str(OUT / 'obj'), str(OUT / 'tb.sv')] + [str(ROOT / s) for s in sources],
                       stdout=log, stderr=log, check=True)


def scenario(name, tile, op, scroll, cols=None, rows=None, only=None):
    """Atlas en page 1 (contenu initial du banc), destination page 0."""
    memory = bytearray((i * 29 + (i >> 11)) & 255 for i in range(3 * SLOT))
    atlas = bytes(memory[SLOT:SLOT + W * H])
    commands = []
    per_row = W // tile
    sx0, sy0 = scroll
    cols = cols if cols is not None else (W + sx0 + tile - 1) // tile
    rows = rows if rows is not None else (H + sy0 + tile - 1) // tile
    count = 0
    for r in range(rows):
        for c in range(cols):
            if only and not only(r, c, rows, cols):
                continue
            index = (r * 37 + c * 11) % (per_row * (H // tile))
            sx, sy = (index % per_row) * tile, (index // per_row) * tile
            x, y = c * tile - sx0, r * tile - sy0
            words = [(op << 24) | (0 << 20) | (1 << 16), ((x & 65535) << 16) | (y & 65535),
                     (tile << 16) | tile, (sx << 16) | sy]
            words += [(tile << 16) | tile, 65536, 65536, 0] if op == 11 else [0, 0, 0, 0]
            commands += words
            count += 1
            for yy in range(max(0, y), min(H, y + tile)):
                for xx in range(max(0, x), min(W, x + tile)):
                    color = atlas[(sy + yy - y) * W + sx + xx - x]
                    if op == 8 or color:
                        memory[yy * W + xx] = color
    (OUT / 'commands.hex').write_text(''.join(f'{w:08x}\n' for w in commands))
    (OUT / 'expected.hex').write_text(''.join(f'{v:02x}\n' for v in memory))
    result = subprocess.run([str(OUT / 'obj/Vgpu_accel_tb'), f'+ncmd={count}', '+bad=0'], cwd=OUT,
                            capture_output=True, text=True)
    if result.returncode:
        print(f'{name}: ÉCHEC\n{result.stdout[-1500:]}{result.stderr[-500:]}', flush=True)
        return
    line = next(l for l in result.stdout.splitlines() if l.startswith('MEASURE'))
    fields = dict(f.split('=') for f in line.split()[1:])
    total, submit = int(fields['mem_cycles_total']), int(fields['mem_cycles_submit'])
    print(f'{name}: commandes={count} total={total} cycles ({total / MEM_HZ * 1e3:.2f} ms) '
          f'soumission={submit / MEM_HZ * 1e3:.2f} ms par_commande={total / count:.0f} cycles pixels=exacts', flush=True)


if __name__ == '__main__':
    build()
    edge = lambda r, c, rows, cols: r == rows - 1 or c == cols - 1
    for tile in (16, 32, 8):
        if len(sys.argv) > 1 and str(tile) not in sys.argv[1:]:
            continue
        scenario(f'COPY plein écran tuiles {tile}', tile, 8, (5, 7))
        scenario(f'ZOOM 1:1 plein écran tuiles {tile}', tile, 11, (5, 7))
        scenario(f'COPY ligne+colonne exposées tuiles {tile}', tile, 8, (5, 7), only=edge)
