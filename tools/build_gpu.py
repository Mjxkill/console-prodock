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
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
IDE = Path('/home/michael/gowin/Gowin_V1.9.12_linux/IDE')


def generate_usb_phy(stage, env, rx_mode='normal', phy_ide=IDE, system_freetype=False):
    """Regenerate the official PHY; Advance is the vendor's V_120 option."""
    if rx_mode not in ('normal', 'advance'):
        raise ValueError(f'Unsupported PHY RX mode: {rx_mode}')
    ip = stage / 'usb_phy_ip'
    ip.mkdir()
    vendor = phy_ide / 'ipcore/USBTwoSoftPHY/data'
    (ip / 'usb2_0_softphy_name.v').write_text(
        '`define module_name USB2_0_SoftPHY_Top\n'
        '`define TX_DELAY_0_BIT\n`define UTMI\n`define GW5AT\n'
        + ('`define V_120\n' if rx_mode == 'advance' else ''))
    for name in ('usb2_0_softphy_top.v', 'usb2_0_softphy.v', 'static_macro_define.v'):
        shutil.copy2(vendor / name, ip / name)
    project = ET.Element('Project')
    ET.SubElement(project, 'Version').text = 'beta'
    ET.SubElement(project, 'Device', id='GW5AST-138B', package='FCPBGA676A',
                  speed='1', partNumber='GW5AST-LV138FPG676AC1/I0')
    files = ET.SubElement(project, 'FileList')
    for name in ('usb2_0_softphy_top.v', 'usb2_0_softphy.v'):
        ET.SubElement(files, 'File', path=str(ip / name), type='verilog')
    options = ET.SubElement(project, 'OptionList')
    for key, value in [('disable_insert_pad', '1'), ('enable_dsrm', '0'),
                       ('include_path', str(ip)), ('output_file', 'usb2_0_softphy.vg'),
                       ('ram_balance', '1'), ('ram_rw_check', '1'),
                       ('top_module', 'USB2_0_SoftPHY_Top'), ('vcc', '0.9'),
                       ('vccx', '1.8'), ('verilog_language', 'sysv-2017')]:
        ET.SubElement(options, 'Option', type=key, value=value)
    ET.indent(project)
    ET.ElementTree(project).write(ip / 'phy.prj', encoding='UTF-8', xml_declaration=True)
    phy_env = dict(env, LD_LIBRARY_PATH=str(phy_ide / 'lib'))
    if phy_ide != IDE:
        # Keep the selected vendor Qt plugins with its own Qt libraries.
        # Do not alter the installed tool or another compilation's environment.
        phy_env['QT_PLUGIN_PATH'] = str(phy_ide / 'plugins/qt')
        phy_env['QT_QPA_PLATFORM_PLUGIN_PATH'] = str(phy_ide / 'plugins/qt/platforms')
    if system_freetype:
        # Ubuntu fontconfig requires FT_Done_MM_Var, absent from the FreeType
        # bundled in 1.9.12.03. Scope the compatible library to this process.
        phy_env['LD_PRELOAD'] = '/lib/x86_64-linux-gnu/libfreetype.so.6'
    run([str(phy_ide / 'bin/GowinSynthesis'), '-prj', 'phy.prj'], ip, ip / 'synth.log', phy_env)
    if 'GowinSynthesis finish' not in (ip / 'synth.log').read_text():
        raise SystemExit('USB PHY IP generation incomplete')
    return ip


def generate_usb_controller(stage, speed, env, controller_ide=IDE, system_freetype=False):
    """Generate a diagnostic IP variant through Gowin; never edit a netlist."""
    ip = stage / 'usb_ip'
    ip.mkdir()
    vendor = controller_ide / 'ipcore/USB_DEVICE_CONTROLLER/data'
    # Same endpoint configuration as the Sipeed 1.9.10.03 reference; the
    # only configuration difference between these two variants is speed.
    definitions = ['`define module_name USB_Device_Controller_Top',
                   '`define HSSUPPORT' if speed == 'high' else '`define FSSUPPORT',
                   '`define DESC_PACKET_MAX64', '`define SELFPOWERED', '`define UTMI']
    definitions += [f'`define ENDPT{ep}_{direction}_T_TYPE 0'
                    for ep in range(1, 16) for direction in ('IN', 'OUT')]
    (ip / 'usb_device_controller_define.v').write_text('\n'.join(definitions)+'\n')
    for name in ('usb_device_controller_top.v', 'usb_device_controller.v', 'static_macro_define.v'):
        shutil.copy2(vendor / name, ip / name)
    project = ET.Element('Project')
    ET.SubElement(project, 'Version').text = 'beta'
    ET.SubElement(project, 'Device', id='GW5AST-138B', package='FCPBGA676A',
                  speed='1', partNumber='GW5AST-LV138FPG676AC1/I0')
    files = ET.SubElement(project, 'FileList')
    for name in ('usb_device_controller_top.v', 'usb_device_controller.v'):
        ET.SubElement(files, 'File', path=str(ip / name), type='verilog')
    options = ET.SubElement(project, 'OptionList')
    for key, value in [('disable_insert_pad','1'), ('enable_dsrm','0'),
                       ('include_path',str(ip)), ('output_file','usb_device_controller.vg'),
                       ('ram_balance','1'), ('ram_rw_check','1'),
                       ('top_module','USB_Device_Controller_Top'), ('vcc','0.9'),
                       ('vccx','1.8'), ('verilog_language','sysv-2017')]:
        ET.SubElement(options, 'Option', type=key, value=value)
    ET.indent(project)
    ET.ElementTree(project).write(ip/'controller.prj', encoding='UTF-8', xml_declaration=True)
    controller_env = dict(env, LD_LIBRARY_PATH=str(controller_ide / 'lib'))
    if controller_ide != IDE:
        controller_env['QT_PLUGIN_PATH'] = str(controller_ide / 'plugins/qt')
        controller_env['QT_QPA_PLATFORM_PLUGIN_PATH'] = str(controller_ide / 'plugins/qt/platforms')
    if system_freetype:
        controller_env['LD_PRELOAD'] = '/lib/x86_64-linux-gnu/libfreetype.so.6'
    run([str(controller_ide/'bin/GowinSynthesis'), '-prj', 'controller.prj'], ip, ip/'synth.log', controller_env)
    if 'GowinSynthesis finish' not in (ip/'synth.log').read_text():
        raise SystemExit('USB controller IP generation incomplete')
    return ip


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
    An optional `via=I2` follows that driver through I2 to place a shared
    selector feeding the destination mux instead of the mux itself.
    """
    text = netlist.read_text()
    lines = constraints.read_text().splitlines()
    for number, line in enumerate(lines):
        directive = re.fullmatch(r'// @driver module=(\S+) instance=(\S+) pin=(\S+)(?: via=(\S+))?', line.strip())
        if not directive:
            continue
        module, instance, pin, via = directive.groups()
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
        if via:
            # Locate a mux's shared selector from a stable destination FF,
            # rather than depending on synthesis-generated LUT suffixes.
            upstream = re.search(rf'^\s*\w+ {re.escape(drivers[0])} \((.*?)\);', body.group(0), re.S | re.M)
            selected = upstream and re.search(rf'\.{re.escape(via)}\((\w+)\)', upstream.group(1))
            if not selected:
                raise SystemExit(f'{constraints}:{number+1}: no upstream pin {via}')
            drivers = re.findall(rf'^\s*\w+ (\w+) \([^;]*?\.F\({selected.group(1)}\)', body.group(0), re.S | re.M)
            if len(drivers) != 1:
                raise SystemExit(f'{constraints}:{number+1}: ambiguous upstream driver')
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
    parser.add_argument('--place-option', type=int, choices=range(5), default=0,
                        help='Gowin placement algorithm; clocks and timing exceptions are unchanged')
    parser.add_argument('--route-option', type=int, choices=range(3), default=1,
                        help='Gowin routing algorithm; preserves the production default (1)')
    parser.add_argument('--replicate-resources', type=int, choices=(0,1), default=1,
                        help='Gowin high-fanout resource replication; affects placement, not RTL or clocks')
    parser.add_argument('--usb-controller', choices=('reference', 'gowin-high', 'gowin-full'),
                        default='reference', help='select the reference or officially regenerated controller IP')
    parser.add_argument('--usb-controller-ide', type=Path, default=IDE,
                        help='vendor installation for controller IP generation; console toolchain unchanged')
    parser.add_argument('--usb-controller-system-freetype', action='store_true',
                        help='use system FreeType for the controller generator on this host')
    parser.add_argument('--usb-diagnostic', action='store_true',
                        help='diagnostic only: retain USB/AE350/DDR and replace GPU with LCD test pattern')
    parser.add_argument('--usb-phy', choices=('reference', 'gowin', 'sipeed-full'), default='reference',
                        help='USB PHY: reference HS, regenerated HS, or dedicated Sipeed FS at 60 MHz')
    parser.add_argument('--usb-phy-rx-mode', choices=('normal', 'advance'), default='normal',
                        help='official Gowin RX_Mode, requires --usb-phy gowin for Advance')
    parser.add_argument('--usb-phy-ide', type=Path, default=IDE,
                        help='vendor installation used for PHY IP generation; console toolchain unchanged')
    parser.add_argument('--usb-phy-system-freetype', action='store_true',
                        help='use system FreeType for the PHY generator Qt/fontconfig on this host')
    parser.add_argument('--usb-capture-first', action='store_true',
                        help='diagnostic only: retain the first attempt of each published EP2 packet')
    parser.add_argument('--resolve-constraints', nargs=3, type=Path, metavar=('NETLIST', 'CST', 'RESOLVED'),
                        help='internal: called by the generated build script between synthesis and placement')
    args = parser.parse_args()
    if args.resolve_constraints:
        resolve_constraints(*args.resolve_constraints)
        return
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.name):
        parser.error('name must contain only letters, digits, underscores and hyphens')
    if args.usb_controller_ide != IDE and args.usb_controller == 'reference':
        parser.error('--usb-controller-ide requires controller regeneration')
    if args.usb_controller_system_freetype and (args.usb_controller == 'reference' or
            not Path('/lib/x86_64-linux-gnu/libfreetype.so.6').is_file()):
        parser.error('--usb-controller-system-freetype requires regenerated controller and system library')
    controller_spec = None
    controller_version = None
    if args.usb_controller != 'reference':
        args.usb_controller_ide = args.usb_controller_ide.resolve(strict=True)
        specs = list((args.usb_controller_ide / 'ipcore/USB_DEVICE_CONTROLLER').glob('*.ipspec'))
        if len(specs) != 1 or not (args.usb_controller_ide / 'bin/GowinSynthesis').is_file():
            parser.error('Controller vendor installation is incomplete')
        controller_spec = specs[0]
        info = ET.parse(controller_spec).getroot().find('ip')
        if info is None or info.get('id') != 'usb20_device_controller':
            parser.error('Unexpected controller IP metadata')
        controller_version = info.get('version')
    dedicated_fs = args.usb_phy == 'sipeed-full'
    if dedicated_fs and args.usb_controller != 'gowin-full':
        parser.error('--usb-phy sipeed-full requires --usb-controller gowin-full')
    if args.usb_diagnostic and args.usb_controller == 'gowin-full' and not dedicated_fs:
        parser.error('GPU-disabled wrapper currently supports only HS controllers')
    if args.usb_phy_rx_mode != 'normal' and args.usb_phy != 'gowin':
        parser.error('--usb-phy-rx-mode advance requires --usb-phy gowin')
    if args.usb_phy_ide != IDE and args.usb_phy != 'gowin':
        parser.error('--usb-phy-ide requires --usb-phy gowin')
    if args.usb_phy_system_freetype and (args.usb_phy != 'gowin' or
            not Path('/lib/x86_64-linux-gnu/libfreetype.so.6').is_file()):
        parser.error('--usb-phy-system-freetype requires regenerated PHY and the system library')
    phy_spec = None
    phy_version = None
    if args.usb_phy == 'gowin':
        args.usb_phy_ide = args.usb_phy_ide.resolve(strict=True)
        specs = list((args.usb_phy_ide / 'ipcore/USBTwoSoftPHY').glob('*.ipspec'))
        if len(specs) != 1 or not (args.usb_phy_ide / 'bin/GowinSynthesis').is_file():
            parser.error('PHY vendor installation is incomplete')
        phy_spec = specs[0]
        info = ET.parse(phy_spec).getroot().find('ip')
        if info is None or info.get('id') != 'usb_20_softphy':
            parser.error('Unexpected PHY IP metadata')
        phy_version = info.get('version')
    if args.usb_capture_first and not args.usb_diagnostic:
        parser.error('--usb-capture-first requires --usb-diagnostic')
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
    usb_ip = (generate_usb_controller(stage, args.usb_controller.removeprefix('gowin-'), env,
                                      args.usb_controller_ide, args.usb_controller_system_freetype)
              if args.usb_controller != 'reference' else None)
    usb_phy_ip = (generate_usb_phy(stage, env, args.usb_phy_rx_mode, args.usb_phy_ide,
                                   args.usb_phy_system_freetype)
                  if args.usb_phy == 'gowin' else None)

    # Compile snapshots: later source edits cannot alter an in-progress build.
    manifest = {}
    def snapshot(src, rel=None):
        rel = src.relative_to(ROOT) if rel is None else Path(rel)
        dest = stage / 'source' / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        manifest[str(rel)] = hashlib.sha256(dest.read_bytes()).hexdigest()
        return dest

    lines = []
    for line in (ROOT / 'tang/build_gpu.tcl').read_text().splitlines():
        if line.startswith('add_file '):
            relative = Path('tang') / line[len('add_file '):]
            src = ROOT / relative
            if dedicated_fs and relative == Path('tang/rtl/console_gpu.v'):
                snapshot(src, 'usb_fs/console_gpu_base.v')
                definitions = ['CONSOLE_USB_DIAG', 'CONSOLE_USB_FULL_SPEED', 'CONSOLE_USB_FS_PHY']
                if args.usb_diagnostic:
                    pattern = snapshot(ROOT / 'tang/rtl/video/lcd_timing.v')
                    lines.append(f'add_file {{{pattern}}}')
                else:
                    definitions.append('CONSOLE_GPU')
                if args.usb_capture_first:
                    definitions.append('CONSOLE_USB_CAPTURE_FIRST')
                src = stage / 'console_usb_fs_dedicated.v'
                src.write_text(''.join(f'`define {x}\n' for x in definitions)
                               + '`include "console_top.v"\n')
                relative = Path('tang/rtl/console_usb_fs_dedicated.v')
            elif args.usb_diagnostic and relative == Path('tang/rtl/console_gpu.v'):
                pattern = snapshot(ROOT / 'tang/rtl/video/lcd_timing.v')
                lines.append(f'add_file {{{pattern}}}')
                src = ROOT / 'tang/rtl/console_usb_diag.v'
                if args.usb_capture_first:
                    snapshot(src)
                    src = ROOT / 'tang/rtl/console_usb_first.v'
                relative = src.relative_to(ROOT)
            elif args.usb_diagnostic and relative == Path('tang/constr/gpu.cst'):
                # Keep all board pin/electrical constraints verbatim. Cell
                # placements from the full GPU do not apply to this netlist.
                snapshot(src, 'diagnostic/gpu_base.cst')
                original = src.read_text()
                src = stage / 'usb_diagnostic.cst'
                src.write_text('\n'.join(x for x in original.splitlines()
                    if not x.lstrip().startswith(('INS_LOC ', '// @driver ')))+'\n')
                if args.usb_capture_first:
                    extra = snapshot(ROOT / 'tang/constr/gpu_usb_first.cst')
                    src.write_text(src.read_text()+'\n'+extra.read_text())
            elif (usb_phy_ip and phy_version == '3.5' and args.usb_phy_rx_mode == 'advance'
                  and relative == Path('tang/constr/gpu.cst')):
                # The official 3.5 Advance export names this RX packet FIFO
                # fifo_rx_pkt. Preserve the RAM location and, when present,
                # the legacy reset-FF location. Only the instance scope
                # changes. C11 deliberately removes the stale reset anchor.
                snapshot(src, 'usb_phy_ip/gpu_base.cst')
                original = src.read_text()
                old = ('u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/'
                       'u_usb2_0_softphy/u_usb_phy_hs/i_rx_phy/u_cdr_serdes_x8_dx/fifo_rx/')
                rx_cells = re.findall(r'INS_LOC "' + re.escape(old) + r'([^"]+)"', original)
                ram_cell = 'fifo_4to8_sub_inst/Equal.mem_Equal.mem_0_0_s'
                reset_cell = 'fifo_4to8_sub_inst/reset_w_1_s0'
                if (original.count(old) != len(rx_cells) or
                        sorted(rx_cells) not in ([ram_cell], sorted([ram_cell, reset_cell]))):
                    raise SystemExit('Unexpected PHY RX placement constraints; review before retargeting')
                src = stage / 'usb_phy35_advance.cst'
                retargeted = original.replace(old, old.removesuffix('fifo_rx/')+'fifo_rx_pkt/')
                # Full HS3.3/PHY3.5 r2: the old three blitter anchors force
                # 2.8/5.938/6.334 ns detours away from its new logic cluster.
                # Let the placer group these cells with their consumers.
                anchors = r'\s*INS_LOC\s+"u_accel/u_blitter/(?:n4837_s0|rw_1_s2|t_step_16_s3)"'
                rows = retargeted.splitlines()
                if sum(bool(re.match(anchors, row)) for row in rows) != 3:
                    raise SystemExit('Unexpected blitter placement anchors; review before removal')
                src.write_text('\n'.join(row for row in rows if not re.match(anchors, row))+'\n')
            elif usb_ip and relative == Path('tang/rtl/usb/usb_device_controller.v'):
                src = usb_ip / 'usb_device_controller.vg'
            elif usb_phy_ip and relative == Path('tang/rtl/usb/usb2_0_softphy.v'):
                src = usb_phy_ip / 'usb2_0_softphy.vg'
            elif dedicated_fs and relative == Path('tang/rtl/usb/usb2_0_softphy.v'):
                src = ROOT / 'tang/rtl/usb/fs_phy/usb_softphy.v'
                relative = src.relative_to(ROOT)
            elif dedicated_fs and relative == Path('tang/constr/gpu.sdc'):
                snapshot(src, 'usb_fs/gpu_base.sdc')
                original = src.read_text()
                # Only clocks absent with the dedicated FS PHY disappear.
                # All remaining periods and exceptions are preserved.
                drop = ('create_clock -name sclk ', 'create_generated_clock -name fclk_960M ',
                        'set_clock_groups -asynchronous -group [get_clocks {PHY_CLKOUT}]')
                src = stage / 'usb_fs.sdc'
                src.write_text('\n'.join(x.replace('{clk50 sclk}', '{clk50}')
                    for x in original.splitlines() if not x.startswith(drop))+'\n')
            elif args.usb_controller == 'gowin-full' and relative == Path('tang/rtl/console_gpu.v'):
                src = ROOT / 'tang/rtl/console_gpu_usb_fs.v'
                relative = src.relative_to(ROOT)
            elif args.usb_controller == 'gowin-full' and not dedicated_fs and relative == Path('tang/constr/gpu.cst'):
                # Keep the reference placement intact. This diagnostic's
                # constant propagation produces a different triangle layout.
                extra = ROOT / 'tang/constr/gpu_usb_fs.cst'
                snapshot(src, 'usb_ip/gpu_base.cst')
                snapshot(extra)
                combined = usb_ip / 'gpu_fs.cst'
                combined.write_text(src.read_text()+'\n'+extra.read_text())
                src = combined
            if dedicated_fs and relative == Path('tang/constr/gpu.cst'):
                snapshot(src, 'usb_fs/gpu_before_pin_filter.cst')
                original = src.read_text()
                src = stage / 'usb_fs.cst'
                # The removed PHY also owns two clock placements, two RAM
                # placements and a reset-cell placement. None applies to FS.
                removed = (r'\s*IO_(?:LOC|PORT)\s+"usb_(?:dxp_io|dxn_io|rxdp_i|rxdn_i)"',
                           r'\s*CLOCK_LOC\s+"fclk_960m"',
                           r'\s*(?:CLOCK_LOC|INS_LOC)\s+"u_usb_softphy_top/',
                           # FS r2 moved the arithmetic cluster; these three
                           # HS anchors add 5.9..9.9 ns of interconnect detours.
                           # Let the placer compact it; no timing exception.
                           r'\s*INS_LOC\s+"u_accel/u_blitter/(?:n4837_s0|rw_1_s2|t_step_16_s3)"')
                src.write_text('\n'.join(x for x in original.splitlines()
                    if not any(re.match(pattern, x) for pattern in removed))+'\n')
            if relative == Path('tang/constr/gpu.cst'):
                # Applies to every PHY variant. The CPU CDC bridge replaces
                # these 20 legacy RAM cells; keep production pin constraints.
                legacy_bridge = r'\s*INS_LOC\s+"u_soc/g_ddr\.u_ddr/u_bridge/'
                rows = src.read_text().splitlines()
                old_count = sum(bool(re.match(legacy_bridge, row)) for row in rows)
                if old_count:
                    if old_count != 20:
                        raise SystemExit('Unexpected legacy DDR bridge anchors; review before removal')
                    snapshot(src, 'ddr_cdc/gpu_before_bridge_filter.cst')
                    src = stage / 'gpu_ddr_cdc.cst'
                    src.write_text('\n'.join(row for row in rows
                        if not re.match(legacy_bridge, row))+'\n')
            dest = snapshot(src, relative)
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
    if not args.usb_diagnostic and not dedicated_fs:
        # Gowin reads one SDC context. Preserve every byte of the production
        # constraints as a prefix and append reporting commands only.
        # Keep both the untouched original and derived report copy in the manifest.
        production_sdc = stage / 'source/tang/constr/gpu.sdc'
        reports = stage / 'timing_reports.sdc'
        queries = '// Queries only; no additional constraints or exceptions.\n' + ''.join(
            f'report_timing -setup -from_clock [get_clocks {{{clock}}}] '
            f'-to_clock [get_clocks {{{clock}}}] -max_paths 200 -max_common_paths 1\n'
            for clock in ('ddr3_sys_clk', 'bus80_clk', 'LCD_35M', 'PHY_CLKOUT', 'sclk'))
        reports.write_bytes(production_sdc.read_bytes() + b'\n' + queries.encode())
        report_source = snapshot(reports, 'diagnostics/timing_reports.sdc')
        original_add = f'add_file {{{production_sdc}}}'
        assert lines.count(original_add) == 1
        lines[lines.index(original_add)] = f'add_file {{{report_source}}}'
    lines.insert(lines.index('run syn'), f'set_option -place_option {args.place_option}')
    routing = 'set_option -route_option 1'
    assert lines.count(routing) == 1
    lines[lines.index(routing)] = f'set_option -route_option {args.route_option}'
    replication = 'set_option -replicate_resources 1'
    assert lines.count(replication) == 1
    lines[lines.index(replication)] = f'set_option -replicate_resources {args.replicate_resources}'
    build_options = stage / 'build_options.json'
    build_options.write_text(json.dumps(dict(arguments=sys.argv[1:],
        placement_algorithm=args.place_option,
        routing_algorithm=args.route_option,
        replicate_resources=args.replicate_resources), indent=2) + '\n')
    snapshot(build_options, 'diagnostics/build_options.json')
    (stage / 'build.tcl').write_text('\n'.join(lines) + '\n')
    for name in ('gpu_diag.c', 'gpu_v1.c', 'gpu_v1.h', 'gpu_v1_scene.h', 'gpu_v1_demo.h', 'gpu_v1_expected.h', 'gpu_demo.h', 'gpu.c', 'gpu.h', 'gpu_palette.h', 'gpu_layers_demo.h', 'gpu_sprites_demo.h', 'gpu_3d_scene.h', 'gpu_3d_demo.h', 'racer_scene.h', 'racer_demo.h', 'gpu_tiles_scene.h', 'gpu_tiles_demo.h', 'gpu_affine_scene.h', 'gpu_affine_demo.h', 'gpu_raster_scene.h', 'gpu_raster_reference.h', 'gpu_raster_demo.h', 'gpu_rgb_overlay_scene.h', 'build/gpu_font.h',
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
    if args.usb_diagnostic:
        snapshot(Path(__file__).resolve())
        (stage/'usb_diagnostic.json').write_text(json.dumps(dict(
            gpu_disabled=True, display='LCD test pattern',
            firmware='unchanged GPU firmware; use only ?, X and E commands',
            packet_trace='first attempt' if args.usb_capture_first else 'latest attempts',
            constraints=('dedicated FS: absent HS pins/clocks removed; remaining constraints preserved'
                         if dedicated_fs else 'same SDC and board pins; full-design cell placements omitted'),
            purpose='isolate USB protocol without GPU timing/placement dependency'), indent=2)+'\n')
    if usb_ip:
        snapshot(controller_spec, Path('usb_ip') / controller_spec.name)
        for name in ('usb_device_controller_define.v', 'usb_device_controller_top.v',
                     'usb_device_controller.v', 'static_macro_define.v', 'controller.prj'):
            snapshot(usb_ip / name, Path('usb_ip') / name)
        snapshot(Path(__file__).resolve())
        (stage/'usb_controller.json').write_text(json.dumps(dict(
            mode=args.usb_controller, tool=str(args.usb_controller_ide), console_tool=str(IDE),
            ip_version=controller_version, system_freetype=args.usb_controller_system_freetype,
            phy=('dedicated Sipeed Full Speed PHY' if dedicated_fs else
                 'regenerated Gowin PHY' if usb_phy_ip else 'unchanged Sipeed netlist'),
            configuration='usb_ip/usb_device_controller_define.v'),
            indent=2)+'\n')
    if dedicated_fs:
        for name in ('usb_softphy.ipc', 'usb_softphy_tmp.v'):
            snapshot(ROOT / 'tang/rtl/usb/fs_phy' / name)
        snapshot(Path(__file__).resolve())
        (stage/'usb_phy.json').write_text(json.dumps(dict(
            mode=args.usb_phy, ip_version='1.0', phy_clock_mhz=60,
            expected_usb_speed_mbps=12, vendor_sources_unmodified=True,
            source='Sipeed TangMega-138KPro-example d3cebf1703f1bcd06dca8a53bf2b660c86a5ec16',
            controller=args.usb_controller, configuration='tang/rtl/usb/fs_phy/usb_softphy.ipc'),
            indent=2)+'\n')
    if usb_phy_ip:
        snapshot(phy_spec, Path('usb_phy_ip') / phy_spec.name)
        for name in ('usb2_0_softphy_name.v', 'usb2_0_softphy_top.v',
                     'usb2_0_softphy.v', 'static_macro_define.v', 'phy.prj'):
            snapshot(usb_phy_ip / name, Path('usb_phy_ip') / name)
        (stage/'usb_phy.json').write_text(json.dumps(dict(
            mode=args.usb_phy, tool=str(args.usb_phy_ide), console_tool=str(IDE),
            ip_version=phy_version,
            controller='unchanged Sipeed netlist' if usb_ip is None else args.usb_controller,
            system_freetype=args.usb_phy_system_freetype,
            rx_mode=args.usb_phy_rx_mode,
            rx_mode_configuration='V_120' if args.usb_phy_rx_mode == 'advance' else 'default without V_120',
            configuration='usb_phy_ip/usb2_0_softphy_name.v',
            vendor_sources_unmodified=True), indent=2)+'\n')
    if not args.usb_diagnostic:
        scanout_check = snapshot(ROOT / 'tools/check_gpu_scanout_synthesis.py')
        copy_check = snapshot(ROOT / 'tools/check_gpu_copy_synthesis.py')
    (stage / 'sources.json').write_text(json.dumps(manifest, indent=2) + '\n')
    run([str(IDE / 'bin/gw_sh'), 'build.tcl'], stage, stage / 'build.log', env)
    if not args.usb_diagnostic:
        run([sys.executable, str(scanout_check), '--stage', str(stage),
             '--out', str(stage / 'scanout_synthesis.json')], stage,
            stage / 'scanout_synthesis.log')
        run([sys.executable, str(copy_check), '--stage', str(stage),
             '--out', str(stage / 'copy_synthesis.json')], stage,
            stage / 'copy_synthesis.log')
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
