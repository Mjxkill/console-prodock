#!/usr/bin/env python3
"""Single explicit reset-input ECO; preserve all other parent netlist modules."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from board_contract import before_build
from gowin_toolchain import environment
from prepare_trial import OUT, PARENT, parent_check, manifest, once, sha

PROBES = ['pll_lock', 'pll_ae350_lock', 'ae350_rst_sync[1]', 'soc_dbg[0]', 'ddr_init',
    'u_soc/init_sync[0]', 'u_soc/exts_hrstn', 'vid_hrstn', 'u_pll_ae350/pll_rst',
    'u_soc/pll_lock', 'soc_dbg_177[1]', 'soc_dbg_2_3', 'trial_request', 'trial_mode',
    'trial_epoch[3]', 'trial_epoch[2]', 'trial_epoch[1]', 'trial_epoch[0]',
    'trial_holding', 'trial_done', 'trial_ahb_tick', 'trial_rtc_tick']


def body(text, name):
    hits = list(re.finditer(r'^module ' + re.escape(name) + r'\b.*?^endmodule[^\n]*', text, re.M | re.S))
    assert len(hits) == 1, name
    return hits[0].group()


def assemble():
    parent_check()
    contract = before_build('neo', candidate=True)
    mapped = HERE / 'mapped_50ms_r2/result.json'
    proof = json.loads(mapped.read_text())
    assert proof['passed'], 'Mapped helper equivalence must pass before assembly'
    assert not (OUT / 'console_neo.vg').exists()
    assert manifest(OUT / 'source') == json.loads((OUT / 'sources.json').read_text())
    original = (OUT / 'parent.vg').read_text()
    assert sha(OUT / 'parent.vg') == sha(PARENT / 'console_neo.vg')
    helper_path = OUT / 'reset_ip/neo_reset_trial.vg'
    assert sha(helper_path) == proof['netlist_sha256']
    helper = helper_path.read_text()
    helper, count = re.subn(r'  GSR GSR \(\s*\.GSRI\(VCC\)\s*\);', '', helper)
    assert count == 1
    existing = set(re.findall(r'^module (\w+)', original, re.M))
    extra = set(re.findall(r'^module (\w+)', helper, re.M))
    assert extra == {'neo_reset_trial', 'neo_reset_trial_rx'} and not (existing & extra)

    # Preserve both AHB flops including clear, clock, enable, and INIT.
    soc = body(original, 'ae350_soc')
    new_soc = once(soc, 'module ae350_soc (\n', 'module ae350_soc (\n  trial_release,\n')
    new_soc = once(new_soc, 'input vid_hclk;', 'input trial_release;\ninput vid_hclk;')
    old_dff = '  DFFCE init_sync_0_s0 (\n    .Q(init_sync[0]),\n    .D(ddr_init),'
    new_soc = once(new_soc, old_dff, old_dff.replace('.D(ddr_init)', '.D(trial_release)'))
    top = body(original, 'console_neo')
    new_top = once(top, '  ae350_soc u_soc (\n', '  ae350_soc u_soc (\n    .trial_release(trial_request),\n')
    # Gowin's mapped-netlist reader requires declarations before all uses,
    # unlike a general Verilog compiler. Keep its generated one-net-per-line form.
    declarations = ''.join('wire ' + n + ';\n' for n in [
        'trial_request', 'trial_mode', 'trial_holding', 'trial_done',
        'trial_ahb_tick', 'trial_rtc_tick']) + 'wire [3:0] trial_epoch;\n'
    new_top = once(new_top, 'wire clk_d;', declarations + 'wire clk_d;')
    addition = '''
neo_reset_trial u_reset_trial (
    .clk_ref(clk_d), .ahb_clk(vid_hclk), .rtc_clk(rtc_clk), .serial_rx(uart_rx_d),
    .ddr_ready(ddr_init), .pll_ready(pll_ae350_lock), .cpu_reset_n(soc_dbg[0]),
    .release_request(trial_request), .delay_mode(trial_mode), .command_epoch(trial_epoch[3:0]),
    .holding(trial_holding), .delay_done(trial_done),
    .ahb_tick(trial_ahb_tick), .rtc_tick(trial_rtc_tick));
'''
    new_top = once(new_top, 'endmodule', addition + 'endmodule')
    merged = once(once(original, soc, new_soc), top, new_top) + '\n' + helper
    # Exact reversibility proves the complete parent text, including protected
    # sections and all DDR/USB/GPU/PLL modules, is otherwise unchanged.
    restored = merged[:-len('\n' + helper)]
    restored = once(once(restored, new_soc, soc), new_top, top)
    assert restored == original
    assert len(re.findall(r'^\s*GSR GSR \(', merged, re.M)) == 1
    unchanged = sorted(existing - {'console_neo', 'ae350_soc'})
    assert all(body(merged, n) == body(original, n) for n in unchanged)

    (OUT / 'console_neo.vg').write_text(merged)
    config = ET.fromstring((PARENT / 'source/tang/boards/neo/startup.gao').read_bytes())
    core = config.find('AoCore')
    signals = core.find('SignalList')
    signals.clear()
    for name in PROBES:
        ET.SubElement(signals, 'Signal', capture_enable='true').text = name
    core.find('Triggers/Trigger/SignalList/Signal').text = 'trial_request'
    config.find('GAO_ID').text = '0101011010101111'
    ET.indent(config, space='    ')
    gao = OUT / 'source/tang/boards/neo/reset_trial.gao'
    gao.write_bytes(ET.tostring(config, encoding='utf-8', xml_declaration=True) + b'\n')
    (OUT / 'sources.json').write_text(json.dumps(manifest(OUT / 'source'), indent=2) + '\n')
    tcl = (PARENT / 'build.tcl').read_text().replace(str(PARENT), str(OUT))
    tcl = once(tcl, '/source/tang/boards/neo/startup.gao}', '/source/tang/boards/neo/reset_trial.gao}')
    (OUT / 'build.tcl').write_text(tcl)
    record = dict(candidate=True, release_qualified=False, hardware_access=False,
        complete_parent_recovered_by_undo=True, changed_parent_modules=['console_neo', 'ae350_soc'],
        unchanged_parent_module_count=len(unchanged), unchanged_parent_modules=unchanged,
        protected_sections_unchanged=True, helper_constant_gsr_removed=True,
        cst_unchanged=sha(OUT / 'source/tang/boards/neo/neo.cst') == sha(PARENT / 'source/tang/boards/neo/neo.cst'),
        sdc_unchanged=sha(OUT / 'source/tang/boards/neo/neo.sdc') == sha(PARENT / 'source/tang/boards/neo/neo.sdc'),
        wait_ms=50, mapped_test=str(mapped), mapped_test_sha256=sha(mapped),
        local_regressions=contract['local_regressions'], probes=PROBES,
        runtime_uart='2 Mbit/s; A5 5A 52 31 35 mode (mode XOR FF) 0D, mode=0/1',
        trigger='trial_request == 1', default_mode=1,
        inputs={str(p.relative_to(OUT)): sha(p) for p in [OUT / 'console_neo.vg', OUT / 'build.tcl', OUT / 'sources.json',
            OUT / 'source/tang/boards/neo/neo.cst', OUT / 'source/tang/boards/neo/neo.sdc', gao]})
    (OUT / 'reset_assembly.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({k:v for k,v in record.items() if k != 'unchanged_parent_modules'}, indent=2))


def route():
    parent_check()
    before_build('neo', candidate=True)
    record = json.loads((OUT / 'reset_assembly.json').read_text())
    for name, value in record['inputs'].items():
        assert sha(OUT / name) == value, name
    assert manifest(OUT / 'source') == json.loads((OUT / 'sources.json').read_text())
    runtime = OUT / 'public_license_runtime'
    tool = runtime / 'bin/gw_sh'
    assert sha(tool) == sha(Path('/home/michael/gowin/IDE/bin/gw_sh'))
    with (OUT / 'build.log').open('x') as log:
        done = subprocess.run([str(tool), 'build.tcl'], cwd=OUT,
            env=environment(), stdout=log, stderr=log)
    text = (OUT / 'build.log').read_text()
    passed = done.returncode == 0 and not re.search(r'^ERROR', text, re.M) and 'Bitstream generation completed' in text
    (OUT / 'route_result.json').write_text(json.dumps(dict(returncode=done.returncode,
        status='ROUTED_NOT_QUALIFIED' if passed else 'ROUTING_FAILED',
        hardware_access=False, loaded=False), indent=2) + '\n')
    if not passed:
        raise SystemExit('Route failed; preserve complete log')
    print('Route completed; timing and reset/probe mapping remain to be qualified')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--route', action='store_true')
    args = parser.parse_args()
    route() if args.route else assemble()
