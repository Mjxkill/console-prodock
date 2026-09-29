#!/usr/bin/env python3
"""Build a reproducible GPU image (firmware, embedded AE350 IP, FPGA, timing)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
IDE = Path('/home/michael/gowin/Gowin_V1.9.12_linux/IDE')


def run(argv, cwd, logfile, env=None):
    print(f'Running {Path(argv[0]).name}: {logfile}', flush=True)
    with logfile.open('w') as log:
        result = subprocess.run(argv, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT)
    content = logfile.read_text(errors='replace')
    if result.returncode or re.search(r'^(ERROR|unknown option:)', content, re.M):
        raise SystemExit(content[-5000:])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', default='gpu_g5')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.name):
        parser.error('name must contain only letters, digits, underscores and hyphens')
    stage = ROOT / 'tang/impl' / args.name
    stage.mkdir(exist_ok=False)
    ipdir = stage / 'ip'
    ipdir.mkdir()
    run(['make', '-B', '-C', str(ROOT / 'fw_console'), 'MAIN=gpu_diag.c',
         f'LD={ROOT / "fw_console/itcm.ld"}', 'CFLAGS_EXTRA=-DCONSOLE_GPU'], ROOT, stage / 'firmware.log')
    cfg = ROOT / 'tang/rtl/board/riscv_ae350_soc_ext/cfg'
    shutil.copy2(cfg / 'riscv_ae350_soc.prj', ipdir)
    env = dict(os.environ, LD_LIBRARY_PATH=str(IDE / 'lib'), QT_QPA_PLATFORM='offscreen', DISPLAY='')
    run([str(IDE / 'bin/GowinSynthesis'), '-prj', 'riscv_ae350_soc.prj'], ipdir, ipdir / 'synth.log', env)
    if 'GowinSynthesis finish' not in (ipdir / 'synth.log').read_text():
        raise SystemExit('AE350 IP generation incomplete')
    for dest in (cfg / 'riscv_ae350_soc.vg', cfg.parent / 'riscv_ae350_soc.v'):
        shutil.copy2(ipdir / 'riscv_ae350_soc.vg', dest)

    # Compile snapshots: later source edits cannot alter an in-progress build.
    manifest = {}
    def snapshot(src):
        rel = src.relative_to(ROOT)
        dest = stage / 'source' / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        manifest[str(rel)] = hashlib.sha256(dest.read_bytes()).hexdigest()
        return dest

    lines = []
    for line in (ROOT / 'tang/build_gpu.tcl').read_text().splitlines():
        if line.startswith('add_file '):
            dest = snapshot(ROOT / 'tang' / line[len('add_file '):])
            line = f'add_file {{{dest}}}'
        elif line.startswith('set_option -output_base_name '):
            line = f'set_option -output_base_name console_{args.name}'
        elif line.startswith('set_option -include_path '):
            line = f'set_option -include_path {{{stage / "source/tang/rtl"}}}'
        lines.append(line)
    (stage / 'build.tcl').write_text('\n'.join(lines) + '\n')
    for name in ('gpu_diag.c', 'gpu_demo.h', 'gpu.c', 'gpu.h', 'gpu_palette.h', 'gpu_layers_demo.h', 'gpu_sprites_demo.h', 'gpu_3d_scene.h', 'gpu_3d_demo.h', 'racer_scene.h', 'racer_demo.h', 'build/gpu_font.h',
                 'itcm.ld', 'Makefile', 'build/console_test.elf', 'build/console_test.bin'):
        snapshot(ROOT / 'fw_console' / name)
    # $readmemh paths are resolved relative to the Gowin working directory.
    font = snapshot(ROOT / 'tang/rtl/video/font8x16.hex')
    font_dest = stage / 'rtl/video/font8x16.hex'
    font_dest.parent.mkdir(parents=True)
    shutil.copy2(font, font_dest)
    snapshot(ROOT / 'tools/gen_gpu_font.py')
    snapshot(ROOT / 'tang/build_gpu.tcl')
    snapshot(ROOT / 'tang/rtl/console_top.v')
    (stage / 'sources.json').write_text(json.dumps(manifest, indent=2) + '\n')
    run([str(IDE / 'bin/gw_sh'), 'build.tcl'], stage, stage / 'build.log', env)
    report = stage / f'impl/pnr/console_{args.name}.tr'
    text = report.read_text()
    slacks = [float(s) for s in re.findall(r'^Slack\s*:\s*([-\d.]+)', text, re.M)]
    tns = re.findall(r'^\s*\S+\s+(?:setup|hold)\s+([-\d.]+)\s+(\d+)\s*$', text, re.M)
    if not slacks or not tns or min(slacks) < 0 or any(float(s) < 0 or int(n) for s,n in tns):
        raise SystemExit(f'Timing check failed: {report}')
    bitstream = stage / f'impl/pnr/console_{args.name}.fs'
    digest = hashlib.sha256(bitstream.read_bytes()).hexdigest()
    (stage / 'bitstream.sha256').write_text(f'{digest}  {bitstream.name}\n')
    print(f'PASS timing: {len(slacks)} detailed paths, minimum slack {min(slacks):.3f} ns', flush=True)
    print(f'Bitstream: {bitstream}\nSHA256: {digest}', flush=True)


if __name__ == '__main__':
    main()
