#!/usr/bin/env python3
"""Independent audit of stable generated GAO inputs/outputs before PNR ends.

Never starts a toolchain, touches a board or modifies the candidate directory.
Encrypted core internals and the future routed VO are explicitly outside scope.
"""
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BUILD = ROOT/'tang/impl/console_neo_n56r10_gao_startup'
PARENT = ROOT/'tang/impl/console_neo_n56r9_route9_dma_c150'
EXPECTED = ['pll_lock','pll_ae350_lock','state_178[2]','state_178[1]','state_178[0]',
    'ae350_rst_sync[1]','ae350_rst_sync[0]','u_soc/init_sync[0]','soc_dbg[0]','ddr_init',
    'u_soc/exts_hrstn','vid_hrstn','soc_dbg_177[1]','soc_dbg_2_3','vid_hclk','gpu_clk',
    'u_soc/pll_lock','u_soc/state_0[2]','u_soc/state_0[1]','u_soc/state_0[0]']


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def normalize(text): return re.sub(r'\s+', '', text).replace('\\', '')


def parameters(text):
    raw = dict(re.findall(r'^parameter (\w+)\s*=\s*([^;]+);', text, re.M))
    def number(value):
        match = re.fullmatch(r"\d+'([hb])(\w+)", value)
        return int(match[2], 16 if match[1] == 'h' else 2) if match else int(value)
    return {k:number(v) for k,v in raw.items()}


def main():
    generated = BUILD/'impl/gao'
    files = sorted(p for p in generated.rglob('*') if p.is_file())
    files += [BUILD/'source/tang/boards/neo/startup.gao', BUILD/'gao_preparation.json',
        BUILD/'console_neo.vg', BUILD/'source/tang/boards/neo/neo.sdc',
        BUILD/'source/tang/boards/neo/neo.cst', BUILD/'sources.json', BUILD/'build.tcl']
    hashes = {str(p):sha(p) for p in files}
    assert sha(BUILD/'console_neo.vg') == sha(PARENT/'console_neo.vg') == '0b5ea22b83faf2bae943f399bdb734dc1e66c8507310dc25e054290e24ad6157'
    for name in ('neo.cst','neo.sdc'):
        assert sha(BUILD/'source/tang/boards/neo'/name) == sha(PARENT/'source/tang/boards/neo'/name)
    config = ET.parse(BUILD/'source/tang/boards/neo/startup.gao').getroot()
    cores = config.findall('AoCore'); assert len(cores) == 1
    core = cores[0]
    assert core.attrib == dict(index='0', sample_clock='clk_d', trig_type='0',
        storage_depth='4096', window_num='1', capture_amount='4096', implementation='0',
        trigger_pos='128', module_name='console_neo', force_trigger_by_falling_edge='false',
        capture_init_data_enabled='true')
    assert [x.text for x in core.find('SignalList')] == EXPECTED
    assert all(x.get('capture_enable') == 'true' for x in core.find('SignalList'))
    assert core.findtext('Triggers/Trigger/SignalList/Signal') == 'ddr_init'
    assert core.findtext('Expressions/Expression') == 'M0'
    enabled = [x for x in core.find('MatchUnits') if x.get('enabled') == '1']
    assert len(enabled) == 1 and all(enabled[0].get(k) == v for k,v in
        dict(index='0',match_type='0',func='0',value0='1',value1='1',trigger='0',counter_enable='0').items())

    wrapper = (generated/'gw_gao_top.v').read_text()
    data = re.search(r'\.data_i\(\{([^}]+)\}\)', wrapper)[1]
    assert [normalize(n) for n in data.split(',')] == EXPECTED
    assert re.search(r'\.trig0_i\(ddr_init\)', wrapper) and re.search(r'\.clk_i\(clk_d\)', wrapper)
    inputs = [normalize(s) for s in re.findall(r'^input ([^;]+);', wrapper, re.M)]
    assert set(inputs) == set(EXPECTED+['clk_d','tms_pad_i','tck_pad_i','tdi_pad_i'])

    synthesized = (generated/'gao.v').read_text()
    assert '`pragma protect begin_protected' in synthesized
    top = re.search(r'^module gw_gao\s*\(.*?^endmodule\b', synthesized, re.M|re.S)[0]
    sinputs = [normalize(s) for s in re.findall(r'^input ([^;]+);', top, re.M)]
    assert set(sinputs) == set(inputs)
    instance = re.search(r'ao_top_0\s+u_la0_top\s*\((.*?)\);', top, re.S)[1]
    pins = {normalize(k):normalize(v) for k,v in re.findall(r'\.(\\\S+|\w+)\s*\(([^)]*)\)',instance)}
    assert pins['clk_d'] == 'clk_d'
    for name in EXPECTED:
        assert list(pins.values()).count(name) == 1, (name,pins)
    assert 'GW_JTAG u_gw_jtag' in top

    params = parameters((generated/'ao_0/gw_ao_parameter.v').read_text())
    required = dict(DATA_OUT_SHIFT_WIDTH=21,MEM_DATA_WIDTH=21,SIG_PORT_WIDTH=20,
        CAPTURE_DATA=1,TRIG_OUT_EN=0,NUM_TRIG_PORTS=1,STORAGE_DEPTH=4096,TRIG_TYPE=0,
        CAPTURE_TRIG_0=1,TRIG_PORT_WIDTH_0=1,MATCH_EN_0=1,MATCH_CNT_WIDTH_0=0,
        MATCH_TYPE_0=0,MATCHER_0=0)
    assert all(params[k] == v for k,v in required.items())
    assert all(params['MATCH_EN_'+str(i)] == 0 for i in range(1,16))
    initial = parameters((generated/'ao_0/gw_ao_init.v').read_text())
    assert initial['MAX_DATA_DEPTH_INIT'] == 4095 and initial['DATA_DEPTH_INIT'] == 3965
    assert initial['NUM_WINDOWS_INIT'] == 0 and initial['TRIG_LEVELS_INIT'] == 0
    assert initial['MATCH0_REG_M0_INIT'] == initial['MATCH0_REG_M1_INIT'] == 1
    assert initial['MATCH0_REG_M2_INIT'] == initial['MATCH0_REG_CTRL_INIT'] == initial['MATCH0_TRIG_CNT_INIT'] == 0
    defines = (generated/'ao_0/gw_ao_top_define.v').read_text()
    assert '`define CORE0_DEF_CAPTURE_INIT_DATA' in defines
    assert '`define CORE0_DEF_SYN_BSRAM' in defines
    assert re.search(r'^`define CORE0_DF_AO_EXPRESSION_0\s+match\[0\]$',
                     (generated/'ao_0/gw_ao_expression.v').read_text(), re.M)
    assert parameters((generated/'ao_control/gw_con_parameter.v').read_text())['NUMBER_AOS'] == 1

    vg = (BUILD/'console_neo.vg').read_text()
    assert re.search(r'IBUF clk_ibuf\s*\(\s*\.O\(clk_d\),\s*\.I\(clk\)\s*\)', vg)
    sdc = (BUILD/'source/tang/boards/neo/neo.sdc').read_text()
    assert 'create_clock -name clk50 -period 20 -waveform {0 10} [get_ports {clk}]' in sdc
    resource = ET.parse(generated/'gao_syn_rsc.xml').getroot()
    assert resource.get('name') == 'gw_gao'
    resources = {k:int(resource.get(k)) for k in ('Register','Alu','Lut','Bsram')}
    assert resources == dict(Register=354,Alu=15,Lut=556,Bsram=6)
    project = ET.parse(generated/'gao_std.prj').getroot()
    assert project.find('Device').get('partNumber') == 'GW5AST-LV138PG484AC1/I0'
    external = [Path(x.get('path')) for x in project.findall('FileList/File') if not Path(x.get('path')).is_relative_to(BUILD)]
    assert all(p.is_file() for p in external)
    hashes.update({str(p):sha(p) for p in external})
    # Never hash an actively changing PNR log. All audited generated files
    # must be identical before and after these checks.
    assert all(sha(Path(name)) == digest for name,digest in hashes.items())
    result = dict(passed=True, scope='Generated GAO wrapper/configuration and synthesis report before routed-VO audit',
        hardware_access=False, toolchain_started=False, route_complete_asserted=False,
        functional_qualification=False, final_bindings_verified=False,
        input_sha256=hashes, audit_script_sha256=sha(Path(__file__)),
        original_application_netlist_unchanged=True, application_cst_sdc_unchanged=True,
        generated_capture_input_connections=[dict(data_i_bit=19-i, net=name) for i,name in enumerate(EXPECTED)],
        synthesized_capture_connections=pins, sample_clock=dict(net='clk_d',input_port='clk',period_ns=20,
            frequency_hz=50000000,frequency_is_design_constraint_not_measurement=True),
        trigger=dict(port='trig0_i',net='ddr_init',enabled_match_unit=0,expression='M0',value=1),
        capture=dict(depth_samples=4096,initial_capture_define_present=True,
            requested_trigger_position=128,requested_pretrigger_us=2.56,total_window_us=81.92,
            probe_bits=20,captured_trigger_bits=1,memory_width_bits=21,
            max_data_depth_init=4095,data_depth_init=3965,
            internal_threshold_pipeline_offset_independently_verified=False),
        gao_only_synthesis_resources=resources, encrypted_core_internals=True,
        required_post_route_checks=['Exact20application-net-to-GAO bindings in final VO',
            'No application logic mutation beyond instrumentation loads',
            'GAO clock/global routes and application reset/clock distributions',
            'Final resources, timing, expected output artifacts and hashes',
            'GAO readout metadata/bit ordering and fresh candidate identity before hardware'],
        limitations=['gao.v exposes the top-level connections; internal vendor cores are protected.',
            'Generated initial-capture settings do not establish successful hardware capture.',
            '21-bit storage contains an additional captured trigger; raw memory bit encoding is not inferred.',
            '16/20ns asynchronous ordering and undersampled80/75MHz probes cannot be interpreted as frequency measurements.',
            '4096 points cover a trigger window, not the full multi-ms PLL initialization.',
            'Resource counts describe GAO synthesis only, not the final routed whole design.'])
    with (HERE/'result.json').open('x') as out: json.dump(result,out,indent=2); out.write('\n')
    print(json.dumps(dict(passed=True, scope=result['scope'], resources=resources,
                         result_sha256=sha(HERE/'result.json'))))


if __name__ == '__main__': main()
