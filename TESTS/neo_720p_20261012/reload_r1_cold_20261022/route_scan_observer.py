#!/usr/bin/env python3
"""Retarget two stale R9 constraints, proving the synthesized functions first.

Reuse the exact successful R9 synthesis. The failed build stays intact.
Only the isolated candidate CST changes; no RTL, SDC, DDR or clock change.
"""
import argparse
import difflib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from prepare_scan_observer import ROOT,HERE,sha,replace

sys.path.insert(0,str(HERE.parent/'n55_gpu_diagnosis_20261021'))
from build_local_controls import cells,norm
from audit_gpu_control_inventory import global_nets
sys.path.insert(0,str(ROOT/'tools'))
from board_contract import before_build,record_build
from gowin_toolchain import IDE,environment
from check_ddr_profile import audit

PARENT=ROOT/'tang/impl/console_neo_n56r9_scan_observer'
R8=ROOT/'tang/impl/console_neo_n56r8_hdmi_sg4'
OUT=ROOT/'tang/impl/console_neo_n56r9_route1'
NETSHA='0b5ea22b83faf2bae943f399bdb734dc1e66c8507310dc25e054290e24ad6157'
MANIFEST='17301dd7513525f5aab38b27760a0dbde0fd9815136f741e564b38aa36c48fc6'

def modules(path):
    text=path.read_text()
    return {m[1]:m[0] for m in re.finditer(r'^module (\w+)\b.*?^endmodule',text,re.M|re.S)}

def parameter(body,name):
    values={norm(n):v.lower() for n,v in re.findall(r'^\s*defparam\s+(\\\S+|\w+)\s*\.INIT\s*=\s*([^;]+);',body,re.M)}
    return values.get(name)

def unique_driver(cc,net,kind,pins):
    found=[(n,c) for n,c in cc.items() if any(c['pins'].get(p)==net for p in ('Q','F','O'))]
    assert len(found)==1 and found[0][1]==dict(kind=kind,pins=pins), (net,found)
    return found[0][0]

def proof():
    old=modules(R8/'console_neo.vg')
    new=modules(PARENT/'impl/gwsynthesis/console_neo.vg')
    ot=cells(old['console_neo']);nt=cells(new['console_neo'])
    oq=cells(old[ot['u_scan_queue']['kind']]);nq=cells(new[nt['u_scan_queue']['kind']])
    old_ready=oq['push_s2'];new_ready=nq['scan_debug_live_228_s']
    assert old_ready['kind']==new_ready['kind']=='LUT2'
    assert {k:v for k,v in old_ready['pins'].items() if k!='F'} == {k:v for k,v in new_ready['pins'].items() if k!='F'} == dict(I0='full',I1='up[1]')
    assert parameter(old['neo_scan_queue'],'push_s2')==parameter(new['neo_scan_queue'],'scan_debug_live_228_s')=="4'h4"
    assert new_ready['pins']['F']=='scan_debug_live_90[228]'
    assert nt['u_scan_queue']['pins']['scan_debug_live_90'].endswith('[228:227]')
    odb=old[ot['u_gpu_debug']['kind']];ndb=new[nt['u_gpu_debug']['kind']]
    od=cells(odb);nd=cells(ndb)
    mon_body=new[nt['u_scan_observe']['kind']];mon=cells(mon_body)
    assert nt['u_scan_observe']['pins']['scan_debug_live_224']=='scan_debug_live[224]'
    for stage in (0,1):
        a=od[f'mem_up_{stage}_s0'];b=mon[f'up_{stage}_s0']
        assert a['kind']==b['kind']=='DFFCE'
        assert a['pins']==dict(Q=f'mem_up[{stage}]',D='VCC' if stage==0 else 'mem_up[0]',CLK='gpu_clk',CLEAR='n3932_6',CE='VCC')
        assert b['pins']==dict(Q='up_3[0]' if stage==0 else 'scan_debug_live_224',D='VCC' if stage==0 else 'up_3[0]',CLK='gpu_clk',CLEAR='n6_6',CE='VCC')
        assert parameter(odb,f'mem_up_{stage}_s0')==parameter(mon_body,f'up_{stage}_s0')=="1'b0"
    # Same asynchronously asserted reset source, same two-stage release.
    unique_driver(od,'n3932_6','INV',dict(O='n3932_6',I='vid_hrstn'))
    unique_driver(mon,'n6_6','INV',dict(O='n6_6',I='vid_hrstn'))
    unique_driver(od,'n3157_5','INV',dict(O='n3157_5',I='mem_up[1]'))
    unique_driver(mon,'n237_5','INV',dict(O='n237_5',I='scan_debug_live_224'))
    assert nt['u_gpu_debug']['pins']['n237_5']==nt['u_scan_observe']['pins']['n237_5']=='n237_5'
    for name in ('req_s_0_s0','req_s_1_s0','ack_s0','held_55_s0'):
        want=dict(od[name]['pins']);want['RESET']='n237_5'
        assert nd[name]==dict(kind=od[name]['kind'],pins=want)
    # The two other retained LOCAL_CLOCK controls still have the same logic.
    oa=cells(old[ot['u_accel']['kind']]);na=cells(new[nt['u_accel']['kind']])
    og=old[oa['u_v1']['kind']];ng=new[na['u_v1']['kind']]
    for ob,nb,name,init in ((og,ng,'n56220_s2',"16'h8000"),(odb,ndb,'n2835_s1',"4'h6")):
        assert cells(ob)[name]==cells(nb)[name]
        assert parameter(ob,name)==parameter(nb,name)==init
    return dict(passed=True,scope='Two targeted constraint mappings and two unchanged CE drivers; not complete netlist equivalence',
        ready=dict(before='u_scan_queue/push_s2',after='u_scan_queue/scan_debug_live_228_s',function='!full && up[1]',lut_init="4'h4",before_cell=old_ready,after_cell=new_ready),
        reset=dict(before='u_gpu_debug/mem_up[1]',after='scan_debug_live[224]',driver='u_scan_observe/up_1_s0',
            function='two gpu_clk DFFCE stages, async clear from !vid_hrstn, init 0',
            shared_by=['u_scan_observe','u_scan_debug','u_gpu_debug'],
            limits='Synthesis merged equivalent reset synchronizers; fanout and physical distribution differ.'),
        retained_local_controls=['u_accel/u_v1/n56220_6','u_gpu_debug/n2835_5'],
        sha256={str(p):sha(p) for p in (R8/'console_neo.vg',PARENT/'impl/gwsynthesis/console_neo.vg')})

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args()
    assert not OUT.exists()
    assert sha(PARENT/'impl/gwsynthesis/console_neo.vg')==NETSHA
    assert sha(PARENT/'sources.json')==MANIFEST
    original=json.loads((PARENT/'sources.json').read_text())
    assert original=={str(p.relative_to(PARENT/'source')):sha(p) for p in (PARENT/'source').rglob('*') if p.is_file()}
    evidence=proof()
    old=(PARENT/'source/tang/boards/neo/neo.cst').read_text()
    cst=replace(old,'INS_LOC "u_scan_queue/push_s2" R[78:86]C[136:150];',
                    'INS_LOC "u_scan_queue/scan_debug_live_228_s" R[78:86]C[136:150];')
    cst=replace(cst,'CLOCK_LOC "u_gpu_debug/mem_up[1]" LOCAL_CLOCK;',
                    'CLOCK_LOC "scan_debug_live[224]" LOCAL_CLOCK;')
    ddr=audit(PARENT/'source',variant='neo-fifo-registers');assert ddr['passed']
    sim=json.loads((HERE/'scan_observer_sim/result.json').read_text())
    assert sim['passed']
    for filename,digest in sim['sources_sha256'].items():assert sha(Path(filename))==digest
    contract=before_build('neo',candidate=True)
    settings=[line.replace(str(PARENT),str(OUT)) for line in (PARENT/'build.tcl').read_text().splitlines()
        if line.startswith(('set_device ','set_option '))]
    tcl='\n'.join(settings+[f'add_file {{{OUT/"console_neo.vg"}}}',
        f'add_file {{{OUT/"source/tang/boards/neo/neo.cst"}}}',f'add_file {{{OUT/"source/tang/boards/neo/neo.sdc"}}}','run pnr',''])
    record=dict(parent=str(PARENT),netlist_sha256=NETSHA,proof=evidence,
        local_regressions=contract['local_regressions'],ddr_profile=ddr,
        script_sha256=sha(Path(__file__)),simulation_result_sha256=sha(HERE/'scan_observer_sim/result.json'),
        constraints_diff=''.join(difflib.unified_diff(old.splitlines(True),cst.splitlines(True),fromfile='N56r9',tofile='N56r9_route1')),
        hardware_access=False)
    if args.check_only:
        print(json.dumps(record,indent=2));return
    OUT.mkdir();record_build(OUT,contract)
    shutil.copytree(PARENT/'source',OUT/'source')
    (OUT/'source/tang/boards/neo/neo.cst').write_text(cst)
    shutil.copy2(PARENT/'impl/gwsynthesis/console_neo.vg',OUT/'console_neo.vg')
    for name in ('font8x16.hex','rtl/video/font8x16.hex','rtl/usbhost/usb_hid_host_rom.hex'):
        dest=OUT/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(PARENT/name,dest)
    updated={str(p.relative_to(OUT/'source')):sha(p) for p in (OUT/'source').rglob('*') if p.is_file()}
    assert {n for n in original if original[n]!=updated[n]}=={'tang/boards/neo/neo.cst'}
    (OUT/'sources.json').write_text(json.dumps(updated,indent=2)+'\n')
    (OUT/'build.tcl').write_text(tcl)
    (OUT/'route.json').write_text(json.dumps(record,indent=2)+'\n')
    (OUT/'constraint_mapping.json').write_text(json.dumps(evidence,indent=2)+'\n')
    (OUT/'constraints.diff').write_text(record['constraints_diff'])
    with (OUT/'build.log').open('w') as log:
        result=subprocess.run([str(IDE/'bin/gw_sh'),'build.tcl'],cwd=OUT,env=environment(),stdout=log,stderr=log)
    log=(OUT/'build.log').read_text()
    failed=bool(result.returncode or re.search(r'^ERROR',log,re.M) or 'Bitstream generation completed' not in log)
    (OUT/'route_result.json').write_text(json.dumps(dict(status='ROUTING_FAILED' if failed else 'ROUTED_NOT_QUALIFIED',returncode=result.returncode,hardware_access=False),indent=2)+'\n')
    if failed:raise SystemExit('Route failed; retained logs at '+str(OUT))
    with (OUT/'qualification_automatic.log').open('x') as log:
        checked=subprocess.run([sys.executable,str(ROOT/'tools/check_neo_timing.py'),str(OUT)],cwd=ROOT,stdout=log,stderr=log,timeout=600)
    local=evidence['retained_local_controls']+[evidence['reset']['after']]
    global_routes=global_nets(OUT)
    unexpected={n:global_routes[n] for n in local if n in global_routes}
    report=dict(qualification_returncode=checked.returncode,local_controls=local,
        unexpected_global_controls=unexpected,passed=checked.returncode==0 and not unexpected,hardware_access=False,
        note='Full routed observer mapping/reset/CDC review remains required before hardware load.')
    (OUT/'automatic_checks.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)
    if not report['passed']:raise SystemExit('Qualification or local-control route audit failed')

if __name__=='__main__':
    main()
