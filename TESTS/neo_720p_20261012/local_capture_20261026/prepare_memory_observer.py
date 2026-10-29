#!/usr/bin/env python3
"""R20: rewire existing coherent snapshot DATA; leave application logic intact."""
import argparse
import fcntl
import json
from pathlib import Path
import re
import shutil
import subprocess
import time
from board_trial_r19 import HERE, ROOT, DEST as PARENT, BIT_SHA, preflight, sha
from build_capture import add_ports, add_child_ports, extra_before_end, block, pins, once, manifest, save
from build_capture import before_build, record_build, environment, IDE

OUT=ROOT/'tang/impl/console_neo_n56r20_memory_observer'
PIXEL_EXPR='{bad_clear,clear_flags[1:0],n1617_5,native_valid_8,native_issue,state[57:0]}'
HANDSHAKES=['native_valid','native_write','v1_select','v1_pending','v1_accepted','b_grant',
    'v1_tx_write','fetch_valid','v1_tx_addr_27_9','n249_5','n4432_3','v1_tx_addr_27_12',
    'copy_valid','cache_valid','legacy_valid','v1_done']

def prepare():
    preflight();contract=before_build('neo',candidate=True)
    anchor=HERE/'r19_clear_isolate_01/result.json';prior=json.loads(anchor.read_text())
    assert prior['measurements_complete'] and prior['bitstream_sha256']==BIT_SHA
    for name,h in prior['files'].items():assert sha(anchor.parent/name)==h,name
    assert [c['completed'] for c in prior['cases']]==[True]*4+[False]
    assert prior['cases'][1]['legacy']['expected_matches'] and prior['cases'][-1]['color']['unchanged']
    original=(PARENT/'console_neo.vg').read_text();changes={}
    pixel=block(original,'gpu_v1')
    assert pins(pixel,'native_valid_s1')==dict(Q='native_valid',D='native_issue',CLK='gpu_clk',RESET='n1617_5',CE='native_valid_8')
    assert pins(pixel,'state_37_s0')['Q']=='state[37]'
    accel=block(original,'gpu_accel')
    assert pins(accel,'v1_pending_s2')==dict(Q='v1_pending',D='v1_tx_addr_27_9',CLK='gpu_clk',RESET='n249_5',CE='VCC')
    assert pins(accel,'v1_accepted_s0')['D']=='n4432_3'
    assert pins(accel,'v1_tx_write_s0')['CE']=='v1_tx_addr_27_12'
    for name,child in [('gpu_v1',None),('gpu_geometry','u_pixels'),('gpu_accel','u_v1')]:
        old=block(original,name);ports={'diag_pixels':('output','[63:0] ')}
        if name=='gpu_accel':ports['diag_handshake']=('output','[15:0] ')
        new=add_ports(old,name,ports)
        if child:new=add_child_ports(new,child,{'diag_pixels':'diag_pixels[63:0]'})
        else:new=extra_before_end(new,'assign diag_pixels='+PIXEL_EXPR+';')
        if name=='gpu_accel':new=extra_before_end(new,'assign diag_handshake={'+','.join(reversed(HANDSHAKES))+'};')
        changes[name]=(old,new)
    old=block(original,'console_neo')
    new=once(old,'wire clk_d;','wire [63:0] diag_pixels;\nwire [15:0] diag_handshake;\nwire clk_d;')
    new=add_child_ports(new,'u_accel',{'diag_pixels':'diag_pixels[63:0]','diag_handshake':'diag_handshake[15:0]'})
    oldpins=pins(old,'u_gpu_debug');rewires={}
    for i in range(32):
        rewires['gpu_debug_state_'+str(64+i)]=f'diag_handshake[{i}]' if i<16 else ('VCC' if (0x4d20>>(i-16))&1 else 'GND')
        rewires['gpu_debug_state_'+str(192+i)]=f'v1_tx_addr[{i}]' if i<28 else ('VCC' if (0xa>>(i-28))&1 else 'GND')
    for i in range(64):rewires['gpu_debug_state_'+str(128+i)]=f'diag_pixels[{i}]'
    inst=re.search(r'  neo_gpu_debug_0 u_gpu_debug \(.*?\n\);',new,re.S)
    assert inst;replacement=inst[0]
    for port,value in rewires.items():replacement=once(replacement,'.'+port+'('+oldpins[port]+')','.'+port+'('+value+')')
    new=once(new,inst[0],replacement);changes['console_neo']=(old,new)
    merged=original
    for old,new in changes.values():merged=once(merged,old,new)
    undone=merged
    for old,new in changes.values():undone=once(undone,new,old)
    assert undone==original
    assert block(merged,'neo_gpu_debug_0')==block(original,'neo_gpu_debug_0')
    OUT.mkdir(exist_ok=False);shutil.copytree(PARENT/'source',OUT/'source')
    for name in ('font8x16.hex','rtl/video/font8x16.hex','rtl/usbhost/usb_hid_host_rom.hex'):
        (OUT/name).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(PARENT/name,OUT/name)
    (OUT/'console_neo.vg').write_text(merged)
    (OUT/'build.tcl').write_text((PARENT/'build.tcl').read_text().replace(str(PARENT),str(OUT)))
    assert manifest(OUT/'source')==json.loads((PARENT/'sources.json').read_text())
    shutil.copy2(PARENT/'sources.json',OUT/'sources.json')
    shutil.copy2(Path(__file__),OUT/'prepare_memory_observer.py')
    save(OUT/'observation.json',dict(candidate=True,qualification='PENDING',hardware_loaded=False,parent=str(PARENT),
        parent_bitstream_sha256=BIT_SHA,anchor=str(anchor),anchor_sha256=sha(anchor),
        builder_sha256=sha(Path(__file__)),common_sources_changed=False,source_RTL_changed=False,
        authoritative_logic='R19 mapped netlist plus reversible observation-only wiring ECO; source RTL remains R19 snapshot',
        added_primitives=0,changed_modules=list(changes),recovered_parent_byte_identical=True,
        same_CST=True,same_SDC=True,same_PNR_options=True,same_DDR_PLL_reset=True,
        snapshot_layout={'word0':'unchanged done','word1':'unchanged reset/queue flags',
            'word2':'0x4d20 signature in bits31:16; handshake names LSB first below',
            'word3':'unchanged blitter pointers/opcode',
            'word4_word5':'bits57:0 pixel FSM; bit58 native_valid.D, 59 native_valid.CE, 60 pixel reset, 61..62 clear_flags, 63 bad_clear',
            'word6':'0xa signature in bits31:28; bits27:0 pending DDR word address',
            'word7':'unchanged extended header'},
        handshakes_lsb_first=HANDSHAKES,pixel_expression=PIXEL_EXPR,debug_port_rewires=rewires,
        inputs={n:sha(OUT/n) for n in ('console_neo.vg','sources.json','build.tcl','source/tang/boards/neo/neo.cst','source/tang/boards/neo/neo.sdc')},
        limits=['Global routing can change with observation fanout; reproduce R19 stall before interpreting.',
                'Snapshot is a single coherent edge, not a historical trace or event counter.',
                'Postroute application-cell audit, snapshot timing audit and hardware comparison pending.']))
    record_build(OUT,contract);print('R20 snapshot wiring prepared; no synthesis/route started',flush=True)

def route(proof):
    preflight();contract=before_build('neo',candidate=True)
    r=json.loads((OUT/'observation.json').read_text())
    assert sha(Path(__file__))==r['builder_sha256']
    for name,h in r['inputs'].items():assert sha(OUT/name)==h,name
    assert manifest(OUT/'source')==json.loads((OUT/'sources.json').read_text())
    q=json.loads(proof.read_text());assert q['passed'] and q['netlist_sha256']==sha(OUT/'console_neo.vg')
    for name,h in q['inputs'].items():assert sha(Path(name))==h,name
    tool=ROOT/'tang/impl/console_neo_n56r15_reset50ms/public_license_runtime/bin/gw_sh'
    assert sha(tool)==sha(IDE/'bin/gw_sh')
    with (OUT/'route.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);assert not (OUT/'route_launch.json').exists()
        record_build(OUT,contract);started=time.time()
        with (OUT/'build.log').open('x') as log:
            p=subprocess.Popen([str(tool),'build.tcl'],cwd=OUT,env=environment(),stdout=log,stderr=log)
            save(OUT/'route_launch.json',dict(pid=p.pid,started_unix=started,tool=str(tool),loaded=False,
                local_proof=str(proof),local_proof_sha256=sha(proof)))
            print('R20_MEMORY_OBSERVER_ROUTE_STARTED pid='+str(p.pid),flush=True);rc=p.wait()
        log=(OUT/'build.log').read_text();ok=rc==0 and not re.search(r'^ERROR',log,re.M) and 'Bitstream generation completed' in log
        save(OUT/'route_result.json',dict(returncode=rc,status='ROUTED_NOT_QUALIFIED' if ok else 'ROUTING_FAILED',started_unix=started,finished_unix=time.time(),loaded=False))
        if not ok:raise SystemExit('R20 route failed; evidence retained')
        print('R20 routed, postroute review required',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--route',type=Path);a=p.parse_args()
    route(a.route.resolve()) if a.route else prepare()
