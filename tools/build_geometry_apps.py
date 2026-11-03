#!/usr/bin/env python3
"""Build isolated G3D1 applications; preserve the qualified legacy ASTRILLA pack."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from build_astrilla import TC

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=ROOT/'games/astrilla/assets/geometry')
    args = parser.parse_args()
    stage = args.stage.resolve(strict=True)
    bitstream = stage/f'impl/pnr/console_{stage.name}.fs'
    digest = sha(bitstream)
    if digest != (stage/'bitstream.sha256').read_text().split()[0]:
        raise RuntimeError('Bitstream hash mismatch')
    build = json.loads((stage/'geometry_build.json').read_text())
    for source in build['changes']:
        if sha(ROOT/source) != sha(stage/'source'/source):
            raise RuntimeError('FPGA snapshot predates the current RTL: '+source)
    args.out.mkdir(parents=True, exist_ok=True)
    sources = ['fw_console/'+name for name in ('gpu.c', 'gpu_raster_commands.c', 'gpu.h', 'gpu_v1.c', 'gpu_v1.h',
               'gpu_geometry.c', 'gpu_geometry.h', 'Makefile')]
    sources += ['games/common/astrilla/'+name for name in ('astrilla_geometry.h', 'astrilla_3d.h',
               'astrilla_scene.h', 'astrilla_assets.h', 'astrilla_meshes.h', 'astrilla_flight.h',
               'astrilla_hud.h', 'astrilla_hud_font.h')]
    sources += ['games/astrilla/src/astrilla.ld']
    sources += ['tools/build_geometry_apps.py', 'tools/load_astrilla.py', 'tools/gpu_geometry_model.py']
    assets = ROOT/'games/astrilla/assets/packed/astrilla.bin'
    for app, flags in [('world3d', '-ffp-contract=off'), ('astrilla', '-ffp-contract=off -DASTRILLA_HW_GEOMETRY')]:
        build = f'build/{app}_geometry'
        subprocess.run(['make', '-s', '-C', str(ROOT/'fw_console'),
                        'MAIN='+str(ROOT/f'games/{app}/src/{app}_main.c'), f'BUILD={build}',
                        'EXTRA_SRCS=gpu_geometry.c', 'CFLAGS_EXTRA='+flags,
                        'LD='+str(ROOT/'games/astrilla/src/astrilla.ld')], check=True)
        binary = ROOT/f'fw_console/{build}/console_test.bin'
        symbols = subprocess.check_output([str(TC), str(binary.with_suffix('.elf'))], text=True)
        entry = int(next(s.split()[0] for s in symbols.splitlines() if s.endswith(' T _start')), 16)
        if not 0xa0000000 <= entry < 0xa0000000+binary.stat().st_size <= 0xa0010000:
            raise RuntimeError('Application outside ILM')
        filename = app+'_hw.bin'
        (args.out/filename).write_bytes(binary.read_bytes())
        app_sources = sources+[f'games/{app}/src/{app}_main.c']
        if app == 'world3d':
            app_sources += ['games/world3d/src/world3d_scene.h', 'tools/render_world3d.py', 'tools/check_world3d.py']
        else:
            app_sources += ['tools/render_astrilla.py', 'tools/check_astrilla.py']
        meta = dict(binary=filename, geometry_abi='G3D1', entry=entry, load=0xa0000000,
                    bytes=binary.stat().st_size, sha256=sha(binary), assets_sha256=sha(assets),
                    fpga_sha256=digest, fpga_stage=stage.name, sources={s:sha(ROOT/s) for s in app_sources})
        (args.out/(app+'.json')).write_text(json.dumps(meta, indent=2)+'\n')
        print(app, meta['bytes'], hex(entry), meta['sha256'], flush=True)


if __name__ == '__main__':
    main()
