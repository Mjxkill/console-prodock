#!/usr/bin/env python3
"""Isolated Neo GAO candidate from exact R9; no programming or shared RTL edits."""
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

PARENT = ROOT / 'tang/impl/console_neo_n56r9_route9_dma_c150'
OUT = ROOT / 'tang/impl/console_neo_n56r10_gao_startup'
GAO_REL = 'tang/boards/neo/startup.gao'
PINS = {
    'sources.json': '8fecc409078515d1d7be4a11fd132f1624412268c1a8fd6dff86ca50b96ec0d1',
    'console_neo.vg': '0b5ea22b83faf2bae943f399bdb734dc1e66c8507310dc25e054290e24ad6157',
    'build.tcl': '27120bd96dfbcdf1963d49759beb7a667837281aece2b28af85c36287d9c721e',
    'source/tang/boards/neo/neo.cst': 'e08dd2bd88b2074a758a828a91393cbbbd5a870e77f99c7bc34071cf41a82c89',
    'source/tang/boards/neo/neo.sdc': 'c8da535e839157a361e78b06b2f65b2912891f8e9dc48b02d5b315ae9f953113',
    'impl/pnr/console_neo.fs': '1593a2aaf7d84e5d099520d96b5d60852340601fd861d2c21108bace846e2fde',
}
PROBES = [
    'pll_lock', 'pll_ae350_lock',
    'state_178[2]', 'state_178[1]', 'state_178[0]',
    'ae350_rst_sync[1]', 'ae350_rst_sync[0]', 'u_soc/init_sync[0]',
    'soc_dbg[0]', 'ddr_init', 'u_soc/exts_hrstn', 'vid_hrstn',
    'soc_dbg_177[1]', 'soc_dbg_2_3', 'vid_hclk', 'gpu_clk',
    'u_soc/pll_lock', 'u_soc/state_0[2]', 'u_soc/state_0[1]', 'u_soc/state_0[0]',
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_manifest(path):
    return {str(p.relative_to(path)): sha(p) for p in sorted(path.rglob('*')) if p.is_file()}


def configuration():
    # Reuse the syntax supplied with the actual installed Gowin release.
    example = IDE / 'data/examples/game/src/game.gao'
    root = ET.fromstring(example.read_bytes())
    core = root.find('AoCore')
    assert root.findtext('Mode') == 'Standard' and core is not None
    core.attrib.update(index='0', sample_clock='clk_d', trig_type='0',
        storage_depth='4096', window_num='1', capture_amount='4096',
        implementation='0', trigger_pos='128', module_name='console_neo',
        force_trigger_by_falling_edge='false', capture_init_data_enabled='true')
    signals = core.find('SignalList'); signals.clear()
    for name in PROBES:
        ET.SubElement(signals, 'Signal', capture_enable='true').text = name
    triggers = core.find('Triggers')
    for trig in triggers:
        for child in list(trig): trig.remove(child)
    ET.SubElement(ET.SubElement(triggers[0], 'SignalList'), 'Signal').text = 'ddr_init'
    units = core.find('MatchUnits')
    for index, unit in enumerate(units):
        unit.attrib.update(enabled='1' if index == 0 else '0', match_type='0',
            counter_enable='0', counter_width='2', counter='2', countinuous='0',
            func='0', value0='1' if index == 0 else '', value1='1' if index == 0 else '')
        if index == 0: unit.set('trigger', '0')
        else: unit.attrib.pop('trigger', None)
    assert core.findtext('Expressions/Expression') == 'M0'
    root.find('GAO_ID').text = '0101011010100000'
    ET.indent(root, space='    ')
    data = ET.tostring(root, encoding='utf-8', xml_declaration=True) + b'\n'
    return data, dict(path=str(example), sha256=sha(example))


def validate_nets():
    text = (PARENT / 'console_neo.vg').read_text()
    modules = {m[1]: m[2] for m in re.finditer(
        r'^module\s+(\w+)\s*\((.*?)^endmodule\b', text, re.M | re.S)}
    for path in PROBES + ['clk_d']:
        pieces = path.split('/')
        assert len(pieces) == 1 or pieces[0] == 'u_soc'
        body = modules['ae350_soc' if len(pieces) == 2 else 'console_neo']
        match = re.fullmatch(r'(\w+)(?:\[(\d+)\])?', pieces[-1])
        name, bit = match.groups()
        declaration = re.search(r'\b(?:wire|input|output)\s*(?:\[(\d+):(\d+)\]\s*)?'
                                + re.escape(name) + r'\s*;', body)
        assert declaration, 'Missing post-synthesis net: ' + path
        if bit is not None:
            hi, lo = declaration.groups()
            assert hi is not None and min(int(hi), int(lo)) <= int(bit) <= max(int(hi), int(lo)), path
    return dict(passed=True, sample_clock='clk_d', probes=PROBES,
                async_level_observation=True, raw_clock_frequency_measurement=False)


def preflight():
    for name, digest in PINS.items():
        assert sha(PARENT / name) == digest, 'Parent input changed: ' + name
    original = json.loads((PARENT / 'sources.json').read_text())
    assert source_manifest(PARENT / 'source') == original
    data, template = configuration()
    nets = validate_nets()
    return original, data, dict(parent=str(PARENT), parent_sha256=PINS,
        parent_qualification='FAIL', candidate=True, release_qualified=False,
        functional_changes=[], unchanged_hdl_netlist=True, unchanged_cst_sdc=True,
        additions=[GAO_REL], gao_sha256=hashlib.sha256(data).hexdigest(),
        probes=nets, template=template, hardware_access=False,
        capture_depth=4096, sample_clock_hz=50000000, trigger='ddr_init == 1',
        capture_initial_data=True, trigger_position=128,
        limitations=[
            'Insertion requires new placement/routing; this is not an observation of the original R9 bitstream.',
            '4096 samples at 50 MHz cover 81.92 us; this is a triggered window, not the full PLL initialization.',
            'A later forced capture is needed for final states or if DDRinit never asserts.',
            'Asynchronous levels cannot establish sub-20 ns transition ordering.',
            'Raw 80/75 MHz clocks are undersampled; constant samples do not prove clock absence.',
            'GAO records digital states, not analog DDR pin timing or internal hard-CPU state.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--check-only', action='store_true')
    modes.add_argument('--prepare', action='store_true')
    modes.add_argument('--route', action='store_true')
    args = parser.parse_args()
    original, data, record = preflight()
    contract = before_build('neo', candidate=True)
    if args.check_only:
        print(json.dumps(dict(passed=True, **record, local_regressions=contract['local_regressions'])))
        return
    if args.prepare:
        OUT.mkdir(exist_ok=False)
        record_build(OUT, contract)
        shutil.copytree(PARENT / 'source', OUT / 'source')
        (OUT / 'source' / GAO_REL).write_bytes(data)
        for name in ('console_neo.vg', 'font8x16.hex', 'rtl/video/font8x16.hex',
                     'rtl/usbhost/usb_hid_host_rom.hex', 'constraint_mapping.json'):
            dest = OUT / name; dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(PARENT / name, dest)
        actual = source_manifest(OUT / 'source')
        assert {k: v for k, v in actual.items() if k != GAO_REL} == original
        (OUT / 'sources.json').write_text(json.dumps(actual, indent=2) + '\n')
        tcl = (PARENT / 'build.tcl').read_text().replace(str(PARENT), str(OUT))
        assert tcl.count('run pnr\n') == 1
        tcl = tcl.replace('run pnr\n', 'add_file -type gao {' + str(OUT / 'source' / GAO_REL) + '}\nrun pnr\n')
        (OUT / 'build.tcl').write_text(tcl)
        record.update(build_tcl_sha256=sha(OUT / 'build.tcl'), sources_sha256=sha(OUT / 'sources.json'),
                      builder_sha256=sha(Path(__file__)), local_regressions=contract['local_regressions'])
        (OUT / 'gao_preparation.json').write_text(json.dumps(record, indent=2) + '\n')
        shutil.copy2(Path(__file__), OUT / 'builder.py')
        print(json.dumps(dict(prepared=str(OUT), hardware_access=False, route_started=False)))
        return
    saved = json.loads((OUT / 'gao_preparation.json').read_text())
    assert all(saved[k] == v for k, v in record.items()), 'Prepared GAO inputs changed'
    assert saved['builder_sha256'] == sha(Path(__file__)) == sha(OUT / 'builder.py')
    assert sha(OUT / 'build.tcl') == saved['build_tcl_sha256']
    assert sha(OUT / 'sources.json') == saved['sources_sha256']
    assert source_manifest(OUT / 'source') == json.loads((OUT / 'sources.json').read_text())
    assert sha(OUT / 'console_neo.vg') == PINS['console_neo.vg']
    assert not (OUT / 'build.log').exists(), 'Never overwrite an attempted route'
    print('Routing GAO candidate ' + str(OUT), flush=True)
    with (OUT / 'build.log').open('x') as log:
        result = subprocess.run([str(IDE / 'bin/gw_sh'), 'build.tcl'], cwd=OUT,
                                env=environment(), stdout=log, stderr=log)
    log = (OUT / 'build.log').read_text()
    failed = result.returncode != 0 or bool(re.search(r'^ERROR', log, re.M)) or 'Bitstream generation completed' not in log
    (OUT / 'route_result.json').write_text(json.dumps(dict(returncode=result.returncode,
        status='ROUTING_FAILED' if failed else 'ROUTED_NOT_QUALIFIED',
        hardware_access=False, functional_qualification=False), indent=2) + '\n')
    if failed: raise SystemExit('GAO route failed; evidence retained in ' + str(OUT))
    print('Routed, requires timing and instrumentation audit; no hardware loaded')


if __name__ == '__main__':
    main()
