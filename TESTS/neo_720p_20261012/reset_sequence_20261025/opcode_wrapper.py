#!/usr/bin/env python3
"""Verify the generated R17 wrapper against its frozen 32-signal manifest."""
import json
import re
import xml.etree.ElementTree as ET
from prepare_opcode_probe import HERE, ROOT, OUT as BUILD, GAO_ID, sha
from opcode_trace import parse_csv, analyze, word


def mapping():
    return json.loads((BUILD/'observation_preparation.json').read_text())['mapping']


def audit_wrapper():
    prepared=json.loads((BUILD/'observation_preparation.json').read_text())
    for name,digest in prepared['inputs'].items(): assert sha(BUILD/name)==digest,name
    m=mapping()
    config=ET.parse(BUILD/'source/tang/boards/neo/opcode_capture.gao').getroot()
    core=config.find('AoCore')
    assert config.findtext('GAO_ID')==GAO_ID
    assert core.attrib['sample_clock']=='gpu_clk'
    assert core.attrib['storage_depth']==core.attrib['capture_amount']=='512'
    assert core.attrib['trigger_pos']=='32'
    assert core.attrib['capture_init_data_enabled']=='true'
    assert [n.text for n in core.findall('SignalList/Signal')]==m['unique_signals']
    assert core.findtext('Triggers/Trigger/SignalList/Signal')==m['controls']['shader_start']
    wrapper=BUILD/'impl/gao/gw_gao_top.v'
    text=wrapper.read_text()
    data=re.search(r'\.data_i\(\{([^}]+)\}\)',text)
    assert data
    assert [v.strip().lstrip('\\') for v in data[1].split(',')]==m['unique_signals']
    assert '.clk_i(gpu_clk)' in text
    assert '.trig0_i(\\u_accel/u_v1/shader_start )' in text
    parameters=BUILD/'impl/gao/ao_0/gw_ao_parameter.v'
    p=dict(re.findall(r'^parameter (\w+) = ([^;]+);',parameters.read_text(),re.M))
    for key,value in {'SIG_PORT_WIDTH':'32','MEM_DATA_WIDTH':'33','STORAGE_DEPTH':'512',
                      'NUM_TRIG_PORTS':'1','TRIG_PORT_WIDTH_0':'1','MATCH_EN_0':'1'}.items():
        assert p[key]==value,key
    defines=BUILD/'impl/gao/ao_0/gw_ao_top_define.v'
    assert '`define CORE0_DEF_CAPTURE_INIT_DATA' in defines.read_text()
    return dict(public_wrapper_passed=True,sample_clock='gpu_clk',data_signals=32,
        trigger_also_stored=True,memory_width=33,observed_mask='0xff000000',
        internal_pipeline_verified=False,
        inputs={str(p):sha(p) for p in (wrapper,parameters,defines,
            BUILD/'observation_preparation.json',HERE/'opcode_trace.py',HERE/'opcode_wrapper.py')})


if __name__=='__main__': print(json.dumps(audit_wrapper(),indent=2))
