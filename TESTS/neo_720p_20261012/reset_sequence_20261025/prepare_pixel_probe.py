#!/usr/bin/env python3
"""Observe the three stages of command capture. Same R15 logic/CST/SDC."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from load_r15 import HERE,ROOT,BUILD as PARENT,BIT_SHA,preflight
sys.path.insert(0,str(ROOT/'tools'))
from board_contract import before_build,record_build
from gowin_toolchain import IDE,environment

OUT=ROOT/'tang/impl/console_neo_n56r16_gao_pixels'
GAO_ID='0101011010110000'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def manifest(root):return {str(p.relative_to(root)):sha(p) for p in sorted(root.rglob('*')) if p.is_file()}
def block(text,name):
    matches=re.findall(r'^module '+re.escape(name)+r'\b.*?^endmodule',text,re.M|re.S)
    assert len(matches)==1,name
    return matches[0]
def pins(body,instance):
    m=re.search(r'^\s*\w+\s+'+re.escape(instance)+r'\s*\((.*?)\);',body,re.M|re.S)
    assert m,instance
    return {p:re.sub(r'\s+','',v).replace('\\','') for p,v in re.findall(r'\.(\w+)\(([^()]+)\)',m[1])}

def probes(text):
    geometry=block(text,'gpu_geometry');pixel=block(text,'gpu_v1')
    bindings=pins(geometry,'u_pixels')
    sources={};destinations={};data={}
    for bit in range(32):
        src=pins(geometry,f'captured_command_{bit}_s0')
        dst=pins(pixel,f'packet_{bit}_s0')
        assert src['Q']==f'gpu_observe_packet_words[{bit}]'
        assert dst['Q']==f'gpu_observe_packet_words[{bit+32}]'
        assert dst['CLK']=='gpu_clk' and dst['CE']=='n37565_3' and dst['RESET']=='n1617_5'
        sources[str(bit)]=f'gpu_observe_packet_words[{bit}]'
        destinations[str(bit)]=f'gpu_observe_packet_words_177[{bit+32}]'
        # Resolve the actual destination D through the shader instance port.
        # Bits 29/30/31 share shader_command[31]; do not sample floating aliases.
        data[str(bit)]='u_accel/u_v1/'+bindings[dst['D']]
    controls={
        'pixel_capture_enable':'u_accel/u_v1/u_pixels/n37565_3',
        'pixel_reset_active_high':'u_accel/u_v1/u_pixels/n1617_5',
        'shader_start':'u_accel/u_v1/shader_start',
        'shader_done':'u_accel/u_v1/shader_done',
        'pixel_idle':'u_accel/u_v1/u_pixels/state[0]',
        'pixel_bad':'u_accel/u_v1/u_pixels/state[1]',
        'pixel_finish':'u_accel/u_v1/u_pixels/state[2]',
        'pixel_decode_wait':'u_accel/u_v1/u_pixels/state[48]',
        'pixel_decode':'u_accel/u_v1/u_pixels/state[45]',
        'geometry_idle':'u_accel/u_v1/state[0]',
        'geometry_decode':'u_accel/u_v1/state[67]',
        'geometry_wait_pixels':'u_accel/u_v1/state[1]',
        'geometry_capture_enable':'u_accel/u_v1/n56220_6',
        'shader_payload_enable':'u_accel/u_v1/n22253_18',
        'geometry_reset_n':'gpu_debug_state[46]',
        'pixel_reset_n':'gpu_debug_state[48]',
        'video_reset_n':'vid_hrstn',
        'ddr_ready':'ddr_init',
        'cpu_release_request':'trial_request',
    }
    unique=list(dict.fromkeys([*sources.values(),*data.values(),*destinations.values(),*controls.values()]))
    assert len(unique)==113
    # Check each selected bus bit/scalar has a declaration before GAO insertion.
    bodies={'':block(text,'console_neo'),'u_accel/u_v1/':geometry,'u_accel/u_v1/u_pixels/':pixel}
    for net in [*unique,'gpu_clk']:
        prefix=max((p for p in bodies if net.startswith(p)),key=len)
        local=net[len(prefix):]
        m=re.fullmatch(r'(\w+)(?:\[(\d+)\])?',local);assert m,net
        decl=re.search(r'^(?:input|output|wire)\s+(?:\[(\d+):(\d+)\]\s+)?'+re.escape(m[1])+r'\s*;',bodies[prefix],re.M)
        assert decl,net
        assert (m[2] is None)==(decl[1] is None),net
        if m[2] is not None:assert min(int(decl[1]),int(decl[2]))<=int(m[2])<=max(int(decl[1]),int(decl[2])),net
    return dict(geometry_header=sources,actual_pixel_D=data,pixel_Q=destinations,controls=controls,unique_signals=unique)

def prepare():
    preflight();contract=before_build('neo',candidate=True)
    proof=HERE/'command_mapped_02/result.json';assert json.loads(proof.read_text())['passed']
    observed=HERE/'warm_long_01/result.json';old=json.loads(observed.read_text())
    assert old['measurement_complete'] and old['reset_observed'] and not old['fpga_reloaded']
    text=(PARENT/'console_neo.vg').read_text();mapping=probes(text)
    OUT.mkdir(exist_ok=False)
    shutil.copytree(PARENT/'source',OUT/'source')
    for n in ['console_neo.vg','font8x16.hex','rtl/video/font8x16.hex','rtl/usbhost/usb_hid_host_rom.hex']:
        (OUT/n).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(PARENT/n,OUT/n)
    config=ET.fromstring((PARENT/'source/tang/boards/neo/reset_trial.gao').read_bytes())
    core=config.find('AoCore')
    core.set('sample_clock','gpu_clk');core.set('storage_depth','512');core.set('capture_amount','512');core.set('trigger_pos','32')
    core.set('capture_init_data_enabled','true')
    signals=core.find('SignalList');signals.clear()
    for n in mapping['unique_signals']:ET.SubElement(signals,'Signal',capture_enable='true').text=n
    core.find('Triggers/Trigger/SignalList/Signal').text=mapping['controls']['shader_start']
    config.find('GAO_ID').text=GAO_ID
    ET.indent(config,space='    ')
    gao=OUT/'source/tang/boards/neo/pixel_capture.gao'
    gao.write_bytes(ET.tostring(config,encoding='utf-8',xml_declaration=True)+b'\n')
    current=manifest(OUT/'source');original=json.loads((PARENT/'sources.json').read_text())
    assert {k:v for k,v in current.items() if k in original}==original
    assert set(current)-set(original)=={'tang/boards/neo/pixel_capture.gao'}
    (OUT/'sources.json').write_text(json.dumps(current,indent=2)+'\n')
    tcl=(PARENT/'build.tcl').read_text().replace(str(PARENT),str(OUT))
    assert tcl.count('/reset_trial.gao}')==1
    tcl=tcl.replace('/reset_trial.gao}','/pixel_capture.gao}')
    (OUT/'build.tcl').write_text(tcl)
    record_build(OUT,contract)
    record=dict(candidate=True,qualification='PENDING',hardware_access=False,loaded=False,
        parent=str(PARENT),parent_bitstream_sha256=BIT_SHA,
        same_application_netlist=sha(OUT/'console_neo.vg')==sha(PARENT/'console_neo.vg'),
        source_change='Add GAO observation config only; no RTL, PLL, DDR, reset, CST or SDC change',
        same_reset_delay_ms=50,gao_id=GAO_ID,mapping=mapping,
        sample_clock='gpu_clk, same domain as geometry/pixels',nominal_sample_period_ns=1000/75,
        trigger='First shader_start==1 after configuration; send TARGET only after confirming zero GPU commands',
        trace_rule='Synchronous sample before edge: when RESET=0 and CE=1, Q on following sample must equal D on this sample; no analog/glitch inference',
        physical_limit='Inserting new probes requires new PNR and can change routes/fanout. Failure must reproduce on instrumented build before attributing cause.',
        proof_sha256={str(proof):sha(proof),str(observed):sha(observed),str(Path(__file__)):sha(Path(__file__))},
        inputs={n:sha(OUT/n) for n in ['console_neo.vg','sources.json','build.tcl','source/tang/boards/neo/neo.cst','source/tang/boards/neo/neo.sdc','source/tang/boards/neo/pixel_capture.gao',
            'font8x16.hex','rtl/video/font8x16.hex','rtl/usbhost/usb_hid_host_rom.hex']})
    assert record['same_application_netlist']
    (OUT/'observation_preparation.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(dict(prepared=str(OUT),signals=len(mapping['unique_signals']),same_netlist=True,hardware_access=False)),flush=True)

def route():
    preflight();contract=before_build('neo',candidate=True)
    record=json.loads((OUT/'observation_preparation.json').read_text())
    for n,d in record['inputs'].items():assert sha(OUT/n)==d,n
    assert manifest(OUT/'source')==json.loads((OUT/'sources.json').read_text())
    assert sha(OUT/'console_neo.vg')==sha(PARENT/'console_neo.vg')
    record_build(OUT,contract)
    tool=PARENT/'public_license_runtime/bin/gw_sh'
    assert sha(tool)==sha(IDE/'bin/gw_sh')
    started=time.time()
    with (OUT/'build.log').open('x') as log:
        child=subprocess.Popen([str(tool),'build.tcl'],cwd=OUT,env=environment(),stdout=log,stderr=log)
        (OUT/'route_launch.json').write_text(json.dumps(dict(pid=child.pid,started_unix=started,tool=str(tool),tool_sha256=sha(tool),candidate=str(OUT),loaded=False),indent=2)+'\n')
        print('R16_OBSERVATION_ROUTE_STARTED pid='+str(child.pid),flush=True)
        rc=child.wait()
    log=(OUT/'build.log').read_text()
    passed=rc==0 and not re.search(r'^ERROR',log,re.M) and 'Bitstream generation completed' in log
    (OUT/'route_result.json').write_text(json.dumps(dict(returncode=rc,status='ROUTED_NOT_QUALIFIED' if passed else 'ROUTING_FAILED',started_unix=started,finished_unix=time.time(),loaded=False),indent=2)+'\n')
    if not passed:raise SystemExit('Observation route failed; evidence retained')
    print('R16 routing complete; mapping/timing audits and hardware pending',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--route',action='store_true');args=parser.parse_args()
    route() if args.route else prepare()
