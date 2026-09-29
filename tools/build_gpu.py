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


def resolve_constraints(netlist, constraints, resolved):
    """Retarget placement constraints on cells that synthesis names itself.

    A line `// @driver module=M instance=I pin=P` in the constraint file says
    that the next INS_LOC places the cell driving pin P of instance I in
    module M. Synthesis numbers such a cell differently from one netlist to
    the next; its location and its function do not change.
    """
    text = netlist.read_text()
    lines = constraints.read_text().splitlines()
    for number, line in enumerate(lines):
        directive = re.fullmatch(r'// @driver module=(\S+) instance=(\S+) pin=(\S+)', line.strip())
        if not directive:
            continue
        module, instance, pin = directive.groups()
        body = re.search(rf'^module {re.escape(module)} \(.*?^endmodule', text, re.S | re.M)
        if not body:
            raise SystemExit(f'{constraints}:{number+1}: module {module} is not in {netlist}')
        cell = re.search(rf'^\s*\w+ {re.escape(instance)} \((.*?)\);', body.group(0), re.S | re.M)
        net = cell and re.search(rf'\.{re.escape(pin)}\((\w+)\)', cell.group(1))
        if not net:
            raise SystemExit(f'{constraints}:{number+1}: no pin {pin} on {module}/{instance}')
        drivers = re.findall(rf'^\s*\w+ (\w+) \([^;]*?\.F\({net.group(1)}\)', body.group(0), re.S | re.M)
        if len(drivers) != 1:
            raise SystemExit(f'{constraints}:{number+1}: {len(drivers)} drivers of {net.group(1)}, expected one')
        target = re.fullmatch(r'(INS_LOC "(?:[^"/]+/)*)([^"/]+)(" .*)', lines[number+1])
        if not target:
            raise SystemExit(f'{constraints}:{number+2}: expected the INS_LOC of the @driver above')
        if target.group(2) != drivers[0]:
            print(f'Constraint retargeted: {target.group(2)} is named {drivers[0]} in this netlist', flush=True)
            lines[number+1] = target.group(1) + drivers[0] + target.group(3)
    resolved.write_text('\n'.join(lines) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', default='gpu_g5')
    parser.add_argument('--resolve-constraints', nargs=3, type=Path, metavar=('NETLIST', 'CST', 'RESOLVED'),
                        help='internal: called by the generated build script between synthesis and placement')
    args = parser.parse_args()
    if args.resolve_constraints:
        resolve_constraints(*args.resolve_constraints)
        return
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
            if dest.suffix == '.cst':
                # The frozen copy stays identical to the source; placement
                # reads a copy completed from the netlist of this build.
                constraints, dest = dest, stage / 'constraints_resolved.cst'
                shutil.copy2(constraints, dest)
            line = f'add_file {{{dest}}}'
        elif line == 'run all':
            netlist = stage / f'impl/gwsynthesis/console_{args.name}.vg'
            lines += ['run syn', f'puts [exec python3 {{{Path(__file__).resolve()}}} --resolve-constraints '
                      f'{{{netlist}}} {{{constraints}}} {{{stage / "constraints_resolved.cst"}}}]']
            line = 'run pnr'
        elif line.startswith('set_option -output_base_name '):
            line = f'set_option -output_base_name console_{args.name}'
        elif line.startswith('set_option -include_path '):
            line = f'set_option -include_path {{{stage / "source/tang/rtl"}}}'
        lines.append(line)
    (stage / 'build.tcl').write_text('\n'.join(lines) + '\n')
    for name in ('gpu_diag.c', 'gpu_demo.h', 'gpu.c', 'gpu.h', 'gpu_palette.h', 'gpu_layers_demo.h', 'gpu_sprites_demo.h', 'gpu_3d_scene.h', 'gpu_3d_demo.h', 'racer_scene.h', 'racer_demo.h', 'gpu_tiles_scene.h', 'gpu_tiles_demo.h', 'build/gpu_font.h',
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
