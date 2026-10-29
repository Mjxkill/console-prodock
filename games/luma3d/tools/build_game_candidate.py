#!/usr/bin/env python3
"""Freeze an isolated native game candidate; never install it or alter a board.

The optional R2 renderer comes from its hash-checked hardware source archive.
The current benchmark harness is common to both comparisons. World assets stay
separate from the active tree. PC command generation is not hardware FPS.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import zlib

REPO = Path(__file__).resolve().parents[3]
GAME = REPO / 'games/luma3d'
COMMON = [
    'src/main.c', 'src/game.c', 'src/world.c', 'src/render.c',
    'include/luma3d_game.h', 'include/luma3d_render.h',
]
SUPPORT = [
    'fw_console/gpu.h', 'fw_console/gpu_v1.h', 'fw_console/gpu_v1.c',
    'fw_console/gpu_geometry.h', 'fw_console/gpu_geometry.c',
    'linux/drivers/prodock-uapi.h', 'linux/drivers/prodock-validate.h',
]
WORLD = ['data.c', 'generated.h', 'heightfield.json', 'meshes.json', 'scene.json']
FLAGS = ['-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
         '-Wno-misleading-indentation', '-ffp-contract=off',
         '-ffunction-sections', '-fdata-sections']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate', action='store_true', required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--world', type=Path, default=GAME/'world')
    p.add_argument('--renderer', choices=['current', 'r2'], default='current')
    p.add_argument('--renderer-tree', type=Path,
                   help='Explicit game-shaped tree supplying only src/render.c and include/luma3d_render.h')
    p.add_argument('--world-header', action='append', default=[],
                   help='Additional named header in the selected world directory; repeat when needed')
    p.add_argument('--capture', action='store_true')
    a = p.parse_args()
    out, world = a.out.resolve(), a.world.resolve()
    out.relative_to(GAME/'build')
    world.relative_to(REPO)
    renderer_tree = a.renderer_tree.resolve() if a.renderer_tree else None
    if renderer_tree:
        renderer_tree.relative_to(REPO)
        if a.renderer != 'current':
            p.error('--renderer-tree cannot be combined with --renderer r2')
    if len(set(a.world_header)) != len(a.world_header):
        p.error('Duplicate --world-header')
    for header in a.world_header:
        if Path(header).name != header or not header.endswith('.h') or header in WORLD:
            p.error('--world-header must name a distinct .h file directly inside --world')
    out.mkdir(parents=True, exist_ok=False)
    manifest = dict(candidate=True, hardware_tested=False, renderer='explicit_tree' if renderer_tree else a.renderer,
                    world=str(world.relative_to(REPO)), files={}, commands=[],
                    status='incomplete', tool_sha256=sha(Path(__file__).read_bytes()),
                    scope='Native executable; immutable source snapshot; no FPGA, kernel, SD or flash changes')
    if renderer_tree:
        manifest['renderer_tree'] = str(renderer_tree.relative_to(REPO))
    manifest['world_headers'] = a.world_header
    source = out/'source'

    def write(rel, data, origin):
        dest = source/rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        manifest['files'][rel] = dict(sha256=sha(data), bytes=len(data), origin=origin)

    def copy(path, rel):
        assert path.is_file() and not path.is_symlink(), path
        write(rel, path.read_bytes(), str(path.relative_to(REPO)))

    def run(cmd, label):
        manifest['commands'].append(cmd)
        with (out/(label+'.log')).open('wb') as log:
            subprocess.run(cmd, cwd=source, stdout=log, stderr=subprocess.STDOUT,
                           check=True, timeout=600)

    try:
        for name in COMMON:
            copy(GAME/name, 'games/luma3d/'+name)
        for name in SUPPORT:
            copy(REPO/name, name)
        for name in WORLD:
            copy(world/name, 'games/luma3d/world/'+name)
        for name in a.world_header:
            copy(world/name, 'games/luma3d/world/'+name)
        if renderer_tree:
            for name in ['src/render.c', 'include/luma3d_render.h']:
                copy(renderer_tree/name, 'games/luma3d/'+name)
        if a.renderer == 'r2':
            archive = GAME/'tests/hardware/valley_20261024_r2/game_sources_exact.tar.gz'
            reference = GAME/'build/frozen_20261024_r2/manifest.json'
            expected = json.loads(reference.read_text())['sources']
            manifest['r2_archive_sha256'] = sha(archive.read_bytes())
            manifest['r2_manifest_sha256'] = sha(reference.read_bytes())
            with tarfile.open(archive, 'r:gz') as tar:
                for name in ['games/luma3d/src/render.c', 'games/luma3d/include/luma3d_render.h']:
                    member = tar.getmember(name)
                    assert member.isfile()
                    data = tar.extractfile(member).read()
                    assert sha(data) == expected[name]
                    write(name, data, str(archive.relative_to(REPO))+'!'+name)
        includes = ['-Igames/luma3d/include', '-Igames/luma3d/world',
                    '-Ifw_console', '-Ilinux/drivers']
        sources = ['games/luma3d/'+s for s in COMMON if s.endswith('.c')]
        sources += ['games/luma3d/world/data.c', 'fw_console/gpu_v1.c', 'fw_console/gpu_geometry.c']
        cc = str(REPO/'linux/build/userbin/riscv32-prodock-linux-gcc')
        manifest['cross_wrapper_sha256'] = sha(Path(cc).read_bytes())
        manifest['cross_version'] = subprocess.check_output([cc, '--version'], text=True)
        host_cc = shutil.which('cc')
        manifest['host_compiler'] = host_cc
        for label, compiler, extra in [('host', host_cc, []), ('riscv', cc, ['-static'])]:
            cmd = [compiler, *includes, *FLAGS, *extra, *sources,
                   '-Wl,--gc-sections', '-lm', '-o', str(out/('luma3d-'+label))]
            run(cmd, 'compile_'+label)
            binary = (out/('luma3d-'+label)).read_bytes()
            manifest[label] = dict(sha256=sha(binary), bytes=len(binary), crc32=f'{zlib.crc32(binary):08x}')
        # Exercise the same frozen harness used by the later board comparison.
        run([str(out/'luma3d-host'), '--host', '--benchmark', '--frames', '4',
             '--warmup', '3', '--advance', '700'], 'benchmark_smoke')
        if a.capture:
            (out/'captures').mkdir()
            manifest['captures'] = {}
            for wide in [False, True]:
                for pose in [0, 700, 1600, 2200]:
                    name = f'frame_{pose}'+('_720' if wide else '')
                    prefix = out/'captures'/name
                    run([str(out/'luma3d-host'), '--host', '--frames', '1',
                         '--advance', str(pose), '--capture', str(prefix),
                         *(['--720p'] if wide else [])], name+'_capture')
                    run([sys.executable, str(GAME/'tools/render_reference.py'), str(prefix)], name+'_oracle')
                    info = json.loads(prefix.with_suffix('.reference.json').read_text())
                    manifest['captures'][name] = info
        # Detect a source mutation during compilation, rather than associating
        # a binary with later contents of a live source tree.
        for rel, entry in manifest['files'].items():
            assert sha((source/rel).read_bytes()) == entry['sha256'], rel
        manifest['status'] = 'built_not_hardware_qualified'
    except BaseException as exc:
        manifest['error'] = repr(exc)
        raise
    finally:
        (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({k:manifest[k] for k in ['status', 'renderer', 'world', 'riscv']}))


if __name__ == '__main__':
    main()
