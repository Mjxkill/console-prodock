#!/usr/bin/env python3
"""Isolated R15 netlist instrumentation; no shared RTL edits or board access."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools'))
sys.path.insert(0,str(HERE.parent/'reset_sequence_20261025'))
from board_contract import before_build,record_build
from gowin_toolchain import IDE,environment
from load_r15 import BUILD as PARENT,BIT_SHA,preflight
from prepare_pixel_probe import probes,block,pins
OUT=ROOT/'tang/impl/console_neo_n56r18_local_capture'
HELPERS=('neo_capture_local','neo_capture_bus')
CHANNELS={'trace_arm_req':('input',''),'trace_snap_req':('input',''),
          'trace_arm_ack':('output',''),'trace_snap_ack':('output',''),
          'trace_ready':('output',''),'trace_heartbeat':('output',''),
          'trace_held':('output','[63:0] ')}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def manifest(root):return {str(p.relative_to(root)):sha(p) for p in sorted(root.rglob('*')) if p.is_file()}
def once(s,a,b):
    assert s.count(a)==1,a
    return s.replace(a,b,1)
def save(p,value):p.write_text(json.dumps(value,indent=2)+'\n')
def verify_proof(path):
    r=json.loads(path.read_text());assert r['passed']
    for p,h in r['inputs'].items():assert sha(Path(p))==h,p
    return r

def prepare(proof):
    preflight();contract=before_build('neo',candidate=True);verify_proof(proof)
    OUT.mkdir(exist_ok=False);shutil.copytree(PARENT/'source',OUT/'source')
    for n in ('console_neo.vg','font8x16.hex','rtl/video/font8x16.hex','rtl/usbhost/usb_hid_host_rom.hex'):
        dest=OUT/('parent.vg' if n=='console_neo.vg' else n)
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(PARENT/n,dest)
    for name in HELPERS:
        src=OUT/'source/tang/boards/neo'/(name+'.v');shutil.copy2(HERE/(name+'.v'),src)
        folder=OUT/'capture_ip'/name;folder.mkdir(parents=True)
        project=ET.Element('Project');ET.SubElement(project,'Version').text='beta'
        ET.SubElement(project,'Device',id='GW5AST-138C',package='PBGA484A',speed='1',partNumber='GW5AST-LV138PG484AC1/I0')
        files=ET.SubElement(project,'FileList');ET.SubElement(files,'File',path=str(src),type='verilog')
        options=ET.SubElement(project,'OptionList')
        for k,v in [('disable_insert_pad','1'),('enable_dsrm','0'),('output_file',name+'.vg'),('top_module',name),('vcc','0.9'),('vccx','1.8'),('verilog_language','sysv-2017')]:ET.SubElement(options,'Option',type=k,value=v)
        ET.indent(project);ET.ElementTree(project).write(folder/'helper.prj',encoding='utf-8',xml_declaration=True)
    current=manifest(OUT/'source');original=json.loads((PARENT/'sources.json').read_text())
    assert {k:v for k,v in current.items() if k in original}==original
    assert set(current)-set(original)=={'tang/boards/neo/'+n+'.v' for n in HELPERS}
    save(OUT/'sources.json',current);record_build(OUT,contract)
    save(OUT/'preparation.json',dict(candidate=True,parent=str(PARENT),parent_bitstream=BIT_SHA,
        original_netlist=sha(OUT/'parent.vg'),rtl_proof=str(proof.resolve()),rtl_proof_sha256=sha(proof),
        inputs={str(p.relative_to(OUT)):sha(p) for p in [OUT/'parent.vg',OUT/'sources.json',*[OUT/'capture_ip'/n/'helper.prj' for n in HELPERS]]},
        common_sources_modified=False,hardware_access=False,gao=False))
    print('Prepared '+str(OUT),flush=True)

def check_prepared():
    preflight();before_build('neo',candidate=True)
    p=json.loads((OUT/'preparation.json').read_text())
    assert sha(Path(p['rtl_proof']))==p['rtl_proof_sha256'];verify_proof(Path(p['rtl_proof']))
    for name,digest in p['inputs'].items():assert sha(OUT/name)==digest,name
    assert manifest(OUT/'source')==json.loads((OUT/'sources.json').read_text())

def refresh_unbuilt(proof):
    # A pre-synthesis review may change a helper. Preserve that preparation;
    # never use this path after synthesis, assembly, or route has started.
    preflight();contract=before_build('neo',candidate=True);verify_proof(proof)
    assert not (OUT/'console_neo.vg').exists() and not (OUT/'route_launch.json').exists()
    assert not list((OUT/'capture_ip').rglob('*.vg')) and not list((OUT/'capture_ip').rglob('*.log'))
    revision=OUT/'preparation_before_reset_review';revision.mkdir(exist_ok=False)
    for name in ('preparation.json','sources.json'):shutil.copy2(OUT/name,revision/name)
    for name in HELPERS:
        target=OUT/'source/tang/boards/neo'/(name+'.v')
        shutil.copy2(target,revision/(name+'.v'));shutil.copy2(HERE/(name+'.v'),target)
    save(OUT/'sources.json',manifest(OUT/'source'))
    r=json.loads((OUT/'preparation.json').read_text())
    r.update(rtl_proof=str(proof.resolve()),rtl_proof_sha256=sha(proof),
             review='Async reset assertion in AHB observer, two-cycle release; stopped-HCLK reset covered before any synthesis')
    r['inputs']['sources.json']=sha(OUT/'sources.json');save(OUT/'preparation.json',r)
    record_build(OUT,contract);print('Unbuilt preparation revised; initial helper/preparation archived',flush=True)

def revalidate(proof):
    preflight();before_build('neo',candidate=True);p=verify_proof(proof)
    assert not (OUT/'route_launch.json').exists()
    for name in HELPERS:
        src=HERE/(name+'.v')
        assert p['inputs'][str(src)]==sha(OUT/'source/tang/boards/neo'/(name+'.v'))==sha(src)
    revision=OUT/'preparation_before_test_expansion.json';assert not revision.exists()
    shutil.copy2(OUT/'preparation.json',revision)
    r=json.loads((OUT/'preparation.json').read_text())
    r.update(rtl_proof=str(proof.resolve()),rtl_proof_sha256=sha(proof),
             expanded_tests='Unknown values rejected, arm/sequence/epoch and reset/CE flags checked, old AHB command preserved; helper RTL unchanged')
    save(OUT/'preparation.json',r);print('Expanded RTL validation bound; synthesized helper RTL unchanged',flush=True)

def synthesize():
    check_prepared();tool=PARENT/'public_license_runtime/bin/GowinSynthesis';assert sha(tool)==sha(IDE/'bin/GowinSynthesis')
    for name in HELPERS:
        folder=OUT/'capture_ip'/name
        with (folder/'synth.log').open('x') as log:
            done=subprocess.run([str(tool),'-prj',str(folder/'helper.prj')],cwd=folder,env=environment(),stdout=log,stderr=log,timeout=180)
        log=(folder/'synth.log').read_text()
        assert done.returncode==0 and 'GowinSynthesis finish' in log and not re.search(r'^ERROR',log,re.M),log[-3000:]
        vg=folder/(name+'.vg');assert not re.search(r'^\s*(?:I|O|IO)BUF\s',vg.read_text(),re.M)
        save(folder/'result.json',dict(passed=True,netlist_sha256=sha(vg),log_sha256=sha(folder/'synth.log'),hardware=False))
    print('Both helpers synthesized; mapped tests required',flush=True)

def add_ports(text,name,ports):
    text=once(text,'module '+name+' (\n','module '+name+' (\n'+''.join('  '+n+',\n' for n in ports))
    first=re.search(r'^(?:input|output|inout) ',text,re.M).start()
    return text[:first]+''.join(d+' '+w+n+';\n' for n,(d,w) in ports.items())+text[first:]
def add_child_ports(text,instance,ports):
    m=re.search(r'^\s*\w+\s+'+re.escape(instance)+r'\s*\(\n',text,re.M);assert m
    return text[:m.end()]+''.join('    .'+n+'('+v+'),\n' for n,v in ports.items())+text[m.end():]
def extra_before_end(text,addition):return once(text,'endmodule',addition+'\nendmodule')

def assemble(proof):
    check_prepared();verify_proof(proof)
    original=(OUT/'parent.vg').read_text();mapping=probes(original)
    helper=''
    for name in HELPERS:
        p=OUT/'capture_ip'/name/(name+'.vg');s=p.read_text()
        assert sha(p)==json.loads((p.parent/'result.json').read_text())['netlist_sha256']
        assert sha(p)==json.loads(proof.read_text())['helper_netlists'][str(p)]
        s,n=re.subn(r'  GSR GSR \(\s*\.GSRI\(VCC\)\s*\);','',s);assert n==1
        helper+='\n'+s
    ports={'trace_resetn':('input',''),**CHANNELS}
    changed={}
    for name,child in [('gpu_accel','u_v1'),('gpu_geometry','u_pixels'),('gpu_v1',None)]:
        b=block(original,name);new=add_ports(b,name,ports)
        if child:new=add_child_ports(new,child,{n:n for n in ports})
        else:
            actual=[pins(b,f'packet_{i}_s0')['D'] for i in range(31,23,-1)]
            sample='{shader_done,state[1],state[45],state[48],state[0],shader_start,n1617_5,n37565_3,gpu_observe_packet_words[63:56],'+','.join(actual)+'}'
            addition='''  neo_capture_local u_capture (
    .clk(gpu_clk),.resetn(trace_resetn),.sample(SAMPLE),
    .arm_req(trace_arm_req),.snap_req(trace_snap_req),.arm_ack(trace_arm_ack),
    .snap_ack(trace_snap_ack),.ready(trace_ready),.heartbeat(trace_heartbeat),.held(trace_held));
'''.replace('SAMPLE',sample)
            new=extra_before_end(new,addition)
        changed[name]=(b,new)
    b=block(original,'neo_gpu_debug_0')
    reverse={n:('output' if d=='input' else 'input',w) for n,(d,w) in CHANNELS.items()}
    new=add_ports(b,'neo_gpu_debug_0',reverse)
    new=once(new,'wire bus_write;','wire [31:0] trace_legacy_data;\nwire bus_write;')
    assert new.count('.Q(debug_hrdata[')==32
    new=new.replace('.Q(debug_hrdata[','.Q(trace_legacy_data[')
    new=extra_before_end(new,'''  neo_capture_bus u_capture_bus (
    .clk(vid_hclk),.resetn(vid_hrstn),.legacy_wait(read_wait),
    .write_pending(bus_write),.write_bit(bus_hwdata[0]),.write_addr(bus_addr),
    .read_addr({bus_haddr_7,bus_haddr_6,bus_haddr_5,bus_haddr_4,bus_haddr_3,bus_haddr_2,bus_haddr_1,bus_haddr_0}),
    .legacy_data(trace_legacy_data),.hrdata(debug_hrdata),
    .arm_req(trace_arm_req),.snap_req(trace_snap_req),.arm_ack(trace_arm_ack),
    .snap_ack(trace_snap_ack),.ready(trace_ready),.heartbeat(trace_heartbeat),.held(trace_held));
''')
    changed['neo_gpu_debug_0']=(b,new)
    b=block(original,'console_neo');new=once(b,'wire clk_d;',''.join('wire '+w+n+';\n' for n,(d,w) in CHANNELS.items())+'wire clk_d;')
    new=add_child_ports(new,'u_accel',{'trace_resetn':'vid_hrstn',**{n:n for n in CHANNELS}})
    new=add_child_ports(new,'u_gpu_debug',{n:n for n in CHANNELS});changed['console_neo']=(b,new)
    merged=original
    for before,after in changed.values():merged=once(merged,before,after)
    restored=merged
    for before,after in changed.values():restored=once(restored,after,before)
    assert restored==original
    names=set(re.findall(r'^module (\w+)',original,re.M))
    assert not (names & set(re.findall(r'^module (\w+)',helper,re.M)))
    assert all(block(merged,n)==block(original,n) for n in names-changed.keys())
    assert not (OUT/'console_neo.vg').exists();(OUT/'console_neo.vg').write_text(merged+helper)
    tcl=(PARENT/'build.tcl').read_text().replace(str(PARENT),str(OUT))
    tcl,n=re.subn(r'^add_file -type gao .*\n','',tcl,flags=re.M);assert n==1
    (OUT/'build.tcl').write_text(tcl)
    save(OUT/'assembly.json',dict(candidate=True,hardware_access=False,gao=False,
        builder_sha256=sha(Path(__file__)),
        mapped_proof=str(proof.resolve()),mapped_proof_sha256=sha(proof),complete_parent_recovered_by_undo=True,
        changed_modules=sorted(changed),unchanged_modules=sorted(names-changed.keys()),mapping=mapping,
        application_changes='New observation loads and ports only; existing debug HRDATA passes through new address mux; no GPU, DDR, PLL or reset sequencer driver changed',
        inputs={n:sha(OUT/n) for n in ('console_neo.vg','sources.json','build.tcl','source/tang/boards/neo/neo.cst','source/tang/boards/neo/neo.sdc')},
        note='source/ preserves R15 application RTL; authoritative application is the mapped parent plus this reversible ECO'))
    shutil.copy2(Path(__file__),OUT/'build_capture.py')
    record_build(OUT,before_build('neo',candidate=True));print('Assembled; exact mapped integration test and route audit still required',flush=True)

def route(proof):
    check_prepared();verify_proof(proof);r=json.loads((OUT/'assembly.json').read_text())
    for n,h in r['inputs'].items():assert sha(OUT/n)==h
    assert sha(Path(__file__))==r['builder_sha256']
    proofdata=json.loads(proof.read_text());assert proofdata['netlist_sha256']==sha(OUT/'console_neo.vg')
    with (OUT/'route.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);assert not (OUT/'route_launch.json').exists()
        record_build(OUT,before_build('neo',candidate=True));tool=PARENT/'public_license_runtime/bin/gw_sh';assert sha(tool)==sha(IDE/'bin/gw_sh')
        started=time.time()
        with (OUT/'build.log').open('x') as log:
            child=subprocess.Popen([str(tool),'build.tcl'],cwd=OUT,env=environment(),stdout=log,stderr=log)
            save(OUT/'route_launch.json',dict(pid=child.pid,started_unix=started,tool=str(tool),tool_sha256=sha(tool),candidate=str(OUT),loaded=False,gao=False))
            print('R18_LOCAL_CAPTURE_ROUTE_STARTED pid='+str(child.pid),flush=True);rc=child.wait()
        log=(OUT/'build.log').read_text();ok=rc==0 and not re.search(r'^ERROR',log,re.M) and 'Bitstream generation completed' in log
        save(OUT/'route_result.json',dict(returncode=rc,status='ROUTED_NOT_QUALIFIED' if ok else 'ROUTING_FAILED',started_unix=started,finished_unix=time.time(),loaded=False))
        if not ok:raise SystemExit('Route failed; evidence retained')
        print('R18 routed; output review and hardware pending',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','refresh-unbuilt','revalidate','synth','assemble','route']);p.add_argument('--proof',type=Path)
    a=p.parse_args()
    if a.action!='synth' and not a.proof:p.error('--proof required')
    {'prepare':prepare,'refresh-unbuilt':refresh_unbuilt,'revalidate':revalidate,'synth':lambda _:synthesize(),'assemble':assemble,'route':route}[a.action](a.proof)
