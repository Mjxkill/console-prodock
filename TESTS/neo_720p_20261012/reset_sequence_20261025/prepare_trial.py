#!/usr/bin/env python3
"""Prepare a frozen Neo 50-ms reset experiment; never access either board."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from board_contract import before_build, record_build
from gowin_toolchain import IDE, environment

PARENT = ROOT / 'tang/impl/console_neo_n56r10_gao_startup'
OUT = ROOT / 'tang/impl/console_neo_n56r15_reset50ms'
SOC = 'tang/rtl/board/ae350_soc.v'
TOP = 'tang/boards/neo/console_neo.v'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest(folder):
    return {str(p.relative_to(folder)): sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}


def once(text, old, new):
    assert text.count(old) == 1, 'Ambiguous/missing replacement: ' + old
    return text.replace(old, new, 1)


def parent_check():
    assert sha(PARENT / 'console_neo.vg') == '0b5ea22b83faf2bae943f399bdb734dc1e66c8507310dc25e054290e24ad6157'
    assert sha(PARENT / 'impl/pnr/ao_0.fs') == '7ca33ea0a54a4ba557319489239e330f6fbfca69840982894ca447a705b05f28'
    actual = manifest(PARENT / 'source')
    assert actual == json.loads((PARENT / 'sources.json').read_text())
    return actual


def prepare():
    original = parent_check()
    contract = before_build('neo', candidate=True)
    assert 'PASS reset trial: real 50 ms' in (HERE / 'simulation_50ms.log').read_text()
    OUT.mkdir(exist_ok=False)
    record_build(OUT, contract)
    shutil.copytree(PARENT / 'source', OUT / 'source')
    for name in ['font8x16.hex', 'rtl/video/font8x16.hex', 'rtl/usbhost/usb_hid_host_rom.hex', 'constraint_mapping.json']:
        dest = OUT / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PARENT / name, dest)
    shutil.copy2(PARENT / 'console_neo.vg', OUT / 'parent.vg')
    for name in ['neo_reset_trial.v', 'neo_reset_trial_rx.v']:
        shutil.copy2(HERE / name, OUT / 'source/tang/boards/neo' / name)
    p = OUT / 'source' / SOC
    text = once(p.read_text(), '    input  wire        clk50,',
        '    input  wire        trial_release, // isolated Neo reset experiment\n    input  wire        clk50,')
    text = once(text, 'else init_sync <= {init_sync[0], ddr3_init_completed};',
        'else init_sync <= {init_sync[0], trial_release};')
    p.write_text(text)
    p = OUT / 'source' / TOP
    text = once(p.read_text(), '    ae350_soc u_soc (', '''    // Isolated startup experiment: default 50 ms, UART mode 0/1 for A/B.
    wire trial_request, trial_mode, trial_holding, trial_done;
    wire trial_ahb_tick, trial_rtc_tick;
    wire [3:0] trial_epoch;
    neo_reset_trial u_reset_trial (
        .clk_ref(clk), .ahb_clk(bus80_clk), .rtc_clk(rtc_clk), .serial_rx(uart_rx),
        .ddr_ready(ddr_init), .pll_ready(pll_ae350_lock), .cpu_reset_n(soc_dbg[0]),
        .release_request(trial_request), .delay_mode(trial_mode), .command_epoch(trial_epoch),
        .holding(trial_holding), .delay_done(trial_done),
        .ahb_tick(trial_ahb_tick), .rtc_tick(trial_rtc_tick));
    ae350_soc u_soc (
        .trial_release(trial_request),''')
    p.write_text(text)
    actual = manifest(OUT / 'source')
    changes = sorted(k for k in original if actual[k] != original[k])
    assert changes == sorted([SOC, TOP])
    assert sorted(set(actual) - set(original)) == [
        'tang/boards/neo/neo_reset_trial.v', 'tang/boards/neo/neo_reset_trial_rx.v']
    (OUT / 'sources.json').write_text(json.dumps(actual, indent=2) + '\n')
    ip = OUT / 'reset_ip'
    ip.mkdir()
    project = ET.Element('Project')
    ET.SubElement(project, 'Version').text = 'beta'
    ET.SubElement(project, 'Device', id='GW5AST-138C', package='PBGA484A', speed='1',
        partNumber='GW5AST-LV138PG484AC1/I0')
    files = ET.SubElement(project, 'FileList')
    for name in ['neo_reset_trial.v', 'neo_reset_trial_rx.v']:
        ET.SubElement(files, 'File', path=str(OUT / 'source/tang/boards/neo' / name), type='verilog')
    options = ET.SubElement(project, 'OptionList')
    for key, value in [('disable_insert_pad', '1'), ('enable_dsrm', '0'),
        ('output_file', 'neo_reset_trial.vg'), ('top_module', 'neo_reset_trial'),
        ('vcc', '0.9'), ('vccx', '1.8'), ('verilog_language', 'sysv-2017')]:
        ET.SubElement(options, 'Option', type=key, value=value)
    ET.indent(project)
    ET.ElementTree(project).write(ip / 'trial.prj', encoding='utf-8', xml_declaration=True)
    record = dict(candidate=True, hardware_access=False, parent=str(PARENT),
        parent_vg_sha256=sha(PARENT / 'console_neo.vg'), parent_sources_sha256=sha(PARENT / 'sources.json'),
        parent_fs_sha256=sha(PARENT / 'impl/pnr/ao_0.fs'), source_changes=changes,
        sources_sha256=sha(OUT / 'sources.json'), wait_cycles=2500000, clock_hz=50000000,
        default_mode='50 ms', mode0='no extra delay after common warm-reset pulse',
        common_warm_hold_cycles=1000, ddr_reset_changed=False, pll_reset_changed=False,
        ahb_synchronizer_changed=False, helper_project_sha256=sha(ip / 'trial.prj'),
        method='Synthesize only helper; explicit ECO on frozen parent netlist, then check mapped helper and unchanged modules before route',
        tests={name: sha(HERE / name) for name in ['neo_reset_trial.v', 'neo_reset_trial_rx.v', 'reset_trial_tb.sv', 'simulation_50ms.log']},
        limits=['Cold load defaults to 50 ms; runtime short/long is a warm-reset comparison.',
                'New routing differs from R10; A/B comparison uses the same new bitstream.',
                'No hard-macro behavioral model exists in the installed simulation library.'])
    (OUT / 'reset_preparation.json').write_text(json.dumps(record, indent=2) + '\n')
    shutil.copy2(Path(__file__), OUT / 'prepare_trial.py')
    print(json.dumps(dict(prepared=str(OUT), **record), indent=2))


def synthesize_helper(public_license=False):
    parent_check()
    before_build('neo', candidate=True)
    record = json.loads((OUT / 'reset_preparation.json').read_text())
    assert sha(OUT / 'sources.json') == record['sources_sha256']
    assert manifest(OUT / 'source') == json.loads((OUT / 'sources.json').read_text())
    ip = OUT / 'reset_ip'
    assert sha(ip / 'trial.prj') == record['helper_project_sha256']
    binary = IDE / 'bin/GowinSynthesis'
    log_path = ip / 'synth.log'
    if public_license:
        # Sipeed explicitly offers this floating server for Tang boards.
        # Use an isolated configuration and byte-identical executables, so
        # other projects keep their existing installation/configuration.
        runtime = OUT / 'public_license_runtime'
        runtime.mkdir(exist_ok=False)
        for p in IDE.iterdir():
            if p.name != 'bin':
                (runtime / p.name).symlink_to(p, target_is_directory=p.is_dir())
        (runtime / 'bin').mkdir()
        for p in (IDE / 'bin').iterdir():
            if p.name == 'gwlicense.ini':
                continue
            dest = runtime / 'bin' / p.name
            if p.name in ['GowinSynthesis', 'gw_sh', 'gw_pnr']:
                shutil.copy2(p, dest)
                assert sha(dest) == sha(p)
            else:
                dest.symlink_to(p, target_is_directory=p.is_dir())
        (runtime / 'bin/gwlicense.ini').write_text('[license]\nlic="gowinlic.sipeed.com:10559"\n')
        binary = runtime / 'bin/GowinSynthesis'
        log_path = ip / 'synth_public_license.log'
        (runtime / 'provenance.json').write_text(json.dumps(dict(
            official_service='https://wiki.sipeed.com/hardware/en/tang/tang-console/mega-console.html',
            configuration_guide='https://cdn.gowinsemi.com.cn/SUG501E.pdf',
            synthesis_executable_sha256=sha(binary),
            installed_config_unchanged=True, executable_modified=False), indent=2) + '\n')
    with log_path.open('x') as log:
        done = subprocess.run([str(binary), '-prj', str(ip / 'trial.prj')],
            cwd=ip, env=environment(), stdout=log, stderr=log, timeout=180)
    text = log_path.read_text()
    assert done.returncode == 0 and 'GowinSynthesis finish' in text and not re.search(r'^ERROR', text, re.M), text[-4000:]
    vg = ip / 'neo_reset_trial.vg'
    assert vg.is_file() and not re.search(r'^\s*(?:I|O|IO)BUF\s', vg.read_text(), re.M)
    (ip / 'result.json').write_text(json.dumps(dict(passed=True, vg_sha256=sha(vg),
        log=str(log_path), log_sha256=sha(log_path), hardware=False, timing_qualified=False), indent=2) + '\n')
    print('Helper synthesized; mapping test and integration audit required before route')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--prepare', action='store_true')
    modes.add_argument('--synth-helper', action='store_true')
    parser.add_argument('--public-license', action='store_true', help='Use Sipeed public floating license in an isolated tool configuration')
    args = parser.parse_args()
    if args.public_license and not args.synth_helper:
        parser.error('--public-license requires --synth-helper')
    prepare() if args.prepare else synthesize_helper(args.public_license)
