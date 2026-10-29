#!/usr/bin/env python3
"""Route3: keep the observed scanout reset net on local routing.

One CLOCK_LOC addition to route2, exact same synthesized netlist. No RTL,
DDR, SDC, frequency, pin, HDMI or placement-option change. No board access.
"""
import argparse
import difflib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

from route_scan_observer_placement import (ROOT, HERE, NETSHA, SDC, sha, modules,
    cells, parameter, audit, before_build, record_build, IDE, environment, LOCAL)
from audit_geometry_controls import indexed_netlist
from audit_gpu_control_inventory import global_nets, CLOCK, pin_base
import audit_scan_observer as observer

PARENT=ROOT/'tang/impl/console_neo_n56r9_route2'
OUT=ROOT/'tang/impl/console_neo_n56r9_route3_scan_reset'
PREPARED=HERE/'n56r9_route3_prepared'
NET='scan_debug_live_178[1]'
BIT='150bd72724ef7ec79c511afe2cc1c01f5976113ec00c39e8fc15e1f272731a01'
CST='d5c5f2a5e0752bec77160bf465cba8beb1cfb89e31e60ecb752409c43e2e284d'
MANIFEST='29e2255165ff6acf2310e09b66858500c880f2f27c6bde7ad1d0255af83017d9'
ADDITION=f'\n// R9 route2 hardware: scanout reset remains 01; test local distribution.\nCLOCK_LOC "{NET}" LOCAL_CLOCK;\n'


def inputs():
    for name,digest in {'sources.json':MANIFEST,'console_neo.vg':NETSHA,
            'impl/pnr/console_neo.fs':BIT,'source/tang/boards/neo/neo.cst':CST,
            'source/tang/boards/neo/neo.sdc':SDC}.items():
        assert sha(PARENT/name)==digest,name
    original=json.loads((PARENT/'sources.json').read_text())
    assert original=={str(p.relative_to(PARENT/'source')):sha(p)
        for p in (PARENT/'source').rglob('*') if p.is_file()}
    old=(PARENT/'source/tang/boards/neo/neo.cst').read_text()
    assert not re.search(r'CLOCK_LOC\s+"'+re.escape(NET)+'"',old)
    bodies=modules(PARENT/'console_neo.vg');top=cells(bodies['console_neo'])
    body=bodies[top['u_gpu']['kind']];gpu=cells(body)
    routed,params,drivers,loads=indexed_netlist(PARENT/'impl/pnr/console_neo.vo')
    reset='u_scan_observe/gowin_split_inv_from_n6_s2_onet'
    assert routed['u_scan_observe/gowin_split_inv_from_n6_s2']==dict(kind='INV',pins=dict(I='vid_hrstn',O=reset))
    stages=[]
    for i in (0,1):
        name=f'mrst_{i}_s0';global_name='u_gpu/'+name
        expected=dict(kind='DFFCE',pins=dict(Q=f'scan_debug_live_{i}',
            D='VCC' if i==0 else 'scan_debug_live_0',CLK='gpu_clk',CLEAR='n6_6',CE='VCC'))
        assert gpu[name]==expected and parameter(body,name)=="1'b0"
        assert top['u_gpu']['pins'][f'scan_debug_live_{i}']==f'scan_debug_live_178[{i}]'
        expected_routed=dict(kind='DFFCE',pins=dict(Q=f'scan_debug_live_178[{i}]',
            D='VCC' if i==0 else 'scan_debug_live_178[0]',CLK='gpu_clk',CLEAR=reset,CE='VCC'))
        assert routed[global_name]==expected_routed and params[global_name]==dict(INIT="1'b0")
        stages.append(dict(instance=global_name,synthesized=expected,routed=expected_routed,init="1'b0"))
    assert drivers[NET]==[('u_gpu/mrst_1_s0','DFFCE','Q')]
    assert len(loads[NET])==21 and not any(CLOCK.fullmatch(pin_base(p)) for _,_,p in loads[NET])
    globals_before=global_nets(PARENT)
    assert globals_before[NET]=='LW' and globals_before['gpu_clk']=='PRIMARY'
    ddr=audit(PARENT/'source',variant='neo-fifo-registers');assert ddr['passed']
    trial_file=HERE/'r9_route2_rgb_observer/result.json'
    trial=json.loads(trial_file.read_text())
    assert trial['trial_completed'] and trial['cpu_left_halted'] and trial['bitstream_sha256']==BIT
    for snapshot in trial['snapshots'].values():
        assert snapshot['flags']['mrst0'] and not snapshot['flags']['mrst1']
        assert snapshot['accepted_by_queue']==snapshot['accepted_by_arbiter']==snapshot['returned']==0
    sim_file=HERE/'scan_observer_sim/result.json'
    sim=json.loads(sim_file.read_text());assert sim['passed']
    for name,digest in sim['sources_sha256'].items():assert sha(Path(name))==digest
    paths=[Path(__file__),Path(observer.__file__),trial_file,HERE/'r9_route2_rgb_observer/rgb_observer.log',
        sim_file,PARENT/'console_neo.vg',PARENT/'impl/pnr/console_neo.vo',PARENT/'impl/pnr/console_neo.rpt.txt',
        PARENT/'sources.json',PARENT/'source/tang/boards/neo/neo.cst',PARENT/'source/tang/boards/neo/neo.sdc',PARENT/'build.tcl']
    proof=dict(net=NET,stages=stages,direct_loads=[list(load) for load in loads[NET]],parent_route='LW',clock_pin_loads=0,
        source_alias="u_gpu.scan_debug_live_1 = scanout mrst[1]",parent_global_nets=globals_before)
    return original,old+ADDITION,dict(parent=str(PARENT),netlist_sha256=NETSHA,bitstream_parent_sha256=BIT,
        local_controls=LOCAL+[NET],ddr_profile=ddr,reset_proof=proof,
        inputs_sha256={str(p):sha(p) for p in paths},
        constraints_diff=''.join(difflib.unified_diff(old.splitlines(True),(old+ADDITION).splitlines(True),
            fromfile='N56r9_route2',tofile='N56r9_route3_scan_reset')),
        hardware_access=False,synthesis=False,
        limits=['Observed reset state is measured on a timing-failing diagnostic build.',
                'LW routing is a hypothesis; Pro Dock also uses LW for its scanout reset.',
                'One constraint change still recomputes whole placement/routing; recheck all timing and functional behavior.'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args()
    assert not OUT.exists()
    original,candidate,record=inputs()
    contract=before_build('neo',candidate=True)
    record['local_regressions']=contract['local_regressions']
    if args.check_only:
        PREPARED.mkdir(exist_ok=True)
        (PREPARED/'review.json').write_text(json.dumps(record,indent=2)+'\n')
        (PREPARED/'constraints.diff').write_text(record['constraints_diff'])
        print(json.dumps(dict(passed=True,net=NET,addition=ADDITION,hardware_access=False),indent=2));return
    assert record==json.loads((PREPARED/'review.json').read_text()),'Review/input drift'
    OUT.mkdir();record_build(OUT,contract)
    shutil.copytree(PARENT/'source',OUT/'source')
    (OUT/'source/tang/boards/neo/neo.cst').write_text(candidate)
    for name in ('console_neo.vg','font8x16.hex','rtl/video/font8x16.hex','rtl/usbhost/usb_hid_host_rom.hex','constraint_mapping.json'):
        dest=OUT/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(PARENT/name,dest)
    updated={str(p.relative_to(OUT/'source')):sha(p) for p in (OUT/'source').rglob('*') if p.is_file()}
    assert updated.keys()==original.keys() and {n for n in original if original[n]!=updated[n]}=={'tang/boards/neo/neo.cst'}
    assert sha(OUT/'console_neo.vg')==NETSHA
    (OUT/'sources.json').write_text(json.dumps(updated,indent=2)+'\n')
    settings=[line.replace(str(PARENT),str(OUT)) for line in (PARENT/'build.tcl').read_text().splitlines()
        if line.startswith(('set_device ','set_option '))]
    (OUT/'build.tcl').write_text('\n'.join(settings+[f'add_file {{{OUT/"console_neo.vg"}}}',
        f'add_file {{{OUT/"source/tang/boards/neo/neo.cst"}}}',f'add_file {{{OUT/"source/tang/boards/neo/neo.sdc"}}}','run pnr','']))
    (OUT/'route.json').write_text(json.dumps(record,indent=2)+'\n')
    (OUT/'constraints.diff').write_text(record['constraints_diff'])
    print('Routing '+str(OUT),flush=True)
    with (OUT/'build.log').open('x') as log:
        done=subprocess.run([str(IDE/'bin/gw_sh'),'build.tcl'],cwd=OUT,env=environment(),stdout=log,stderr=log)
    text=(OUT/'build.log').read_text()
    failed=bool(done.returncode or re.search(r'^ERROR',text,re.M) or 'Bitstream generation completed' not in text)
    (OUT/'route_result.json').write_text(json.dumps(dict(status='ROUTING_FAILED' if failed else 'ROUTED_NOT_QUALIFIED',
        returncode=done.returncode,hardware_access=False),indent=2)+'\n')
    if failed:raise SystemExit('Route failed')
    with (OUT/'qualification_automatic.log').open('x') as log:
        checked=subprocess.run([sys.executable,str(ROOT/'tools/check_neo_timing.py'),str(OUT)],cwd=ROOT,stdout=log,stderr=log,timeout=600)
    routes=global_nets(OUT)
    unexpected={n:routes[n] for n in record['local_controls'] if n in routes}
    observer.OUT=OUT
    observed=observer.audit()
    observed['sha256'][str(Path(__file__).resolve())]=sha(Path(__file__))
    (OUT/'scan_observer_audit.json').write_text(json.dumps(observed,indent=2)+'\n')
    result=dict(qualification_returncode=checked.returncode,unexpected_global_controls=unexpected,
        strict_observer_audit_passed=observed['passed'],hardware_access=False,
        passed=checked.returncode==0 and not unexpected and observed['passed'],
        note='Full reset-driver/load comparison and review of any new global controls still required before hardware trial.')
    (OUT/'automatic_checks.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2),flush=True)
    if not result['passed']:raise SystemExit('Qualification or observer/control audit failed')


if __name__=='__main__':main()
