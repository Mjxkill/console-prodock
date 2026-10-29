#!/usr/bin/env python3
"""Re-load the same R19; compare legacy, empty CLEAR, and one native burst."""
import fcntl
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import time
from board_trial_r19 import HERE, ROOT, BIT_SHA, BASE_GUARD, DISABLED, DEST, hw, sha, preflight
from board_trial import decode
from framebuffer_trial import CACHE
from observe_r19_clear import GUARD as STALLED_GUARD, SNAPSHOT

ARM='''proc word {addr} {return [lindex [read_memory $addr 32 1] 0]}
if {[word 0xe9005080]!=0x4e435031 || ([word 0xe9005084]&7)!=4} {error "Observer unavailable"}
set arm [word 0xe9005088]
set seq [word 0xe900508c]
set epoch [expr {1-(([word 0xe9005084]>>5)&1)}]
write_memory 0xe9005084 32 {1}
set ok 0
for {set i 0} {$i<100} {incr i} {
    set status [word 0xe9005084]
    if {($status&0x4f)==4 && (($status>>5)&1)==$epoch && [word 0xe9005088]==(($arm+1)&0xffffffff)} {set ok 1;break}
    sleep 1
}
if {!$ok} {error "Observer arm timeout"}
echo "ARM_EPOCH $epoch"
'''
CAPTURE='''write_memory 0xe9005088 32 {1}
set ok 0
for {set i 0} {$i<100} {incr i} {
    if {([word 0xe9005084]&0x4f)==12 && [word 0xe900508c]==(($seq+1)&0xffffffff)} {set ok 1;break}
    sleep 1
}
if {!$ok} {error "Observer snapshot timeout"}
set first [read_memory 0xe9005080 32 6]
set second [read_memory 0xe9005080 32 6]
if {$first ne $second} {error "Unstable capture"}
echo "NCP $first"
'''
PACKET='''proc packet {words} {
    set before [read_memory 0xe9001000 32 26]
    if {[lindex $before 1]!=0} {error "GPU busy before command"}
    set next [expr {([lindex $before 2]+1)&65535}]
    foreach w $words {
        if {[lindex [read_memory 0xe9001004 32 1] 0]&2} {error "FIFO full"}
        write_memory 0xe9001010 32 [list $w]
    }
    set completed 0
    for {set i 0} {$i<100} {incr i} {
        set after [read_memory 0xe9001000 32 26]
        if {[lindex $after 1]==0 && [lindex $after 2]==$next} {set completed 1;break}
        sleep 2
    }
    echo "GPU_BEFORE $before"
    echo "GPU_AFTER $after"
    echo "COMMAND_COMPLETE $completed"
}
'''

def main():
    preflight();anchor=HERE/'r19_clear_observe_01/result.json';old=json.loads(anchor.read_text())
    assert old['complete'] and old['bitstream_sha256']==BIT_SHA and old['gpu_final'][1:3]==[1,10]
    for name,digest in old['files'].items():assert sha(anchor.parent/name)==digest,name
    out=HERE/'r19_clear_isolate_01';assert not out.exists()
    r=dict(bitstream_sha256=BIT_SHA,qualification='FAIL',anchor_sha256=sha(anchor),
        scope='Same R19 SRAM reload; CPU halted; guarded volatile DDR; compare legacy and native CLEAR',
        fpga_reloaded=False,measurements_complete=False,SD_written=False,flash_written=False,cases=[])
    def save():(out/'result.json').write_text(json.dumps(r,indent=2)+'\n')
    def run(name,code):
        cfg=out/(name+'.tcl');cfg.write_text(code+'\nshutdown\n');log=out/(name+'.log')
        hw.run_child(['/usr/local/bin/openocd','-f',str(ROOT/'tools/neo/ae350_espprog.cfg'),
            '-c','adapter speed 1000; gdb_port disabled; tcl_port disabled; telnet_port disabled','-f',str(cfg)],log,40)
        return log.read_text()
    with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        active=subprocess.run(['ps','-C','openocd','-C','openFPGALoader','-C','gao_sh','-C','gao_analyzer','-C','jtagserver','-o','pid=,comm='],capture_output=True,text=True)
        assert active.returncode==1 and not active.stdout.strip(),active.stdout
        r['identity']=hw.usb_identity()
        assert r['identity']['neo']['path'].endswith('/3-4.4.1') and r['identity']['esp']['path'].endswith('/3-4.4.2')
        out.mkdir();shutil.copy2(Path(__file__),out/'controller.py');r['started_unix']=time.time();save()
        try:
            run('guard_stalled',STALLED_GUARD)
            hw.Hardware(out,r).program('reload_r19',DEST/'impl/pnr/console_neo.fs',BIT_SHA)
            r['fpga_reloaded']=True;save()
            prefix='riscv expose_csrs 1994,1996,2000\n'+BASE_GUARD+CACHE
            legacy=bytes((29*i+7)&255 for i in range(128))
            seed=bytes((i*37+19)&255 for i in range(4160))
            zseed=bytes((i*53+41)&255 for i in range(4160))
            for name,data in [('legacy_seed',legacy),('color_seed',seed),('depth_seed',zseed)]: (out/(name+'.bin')).write_bytes(data)
            code=prefix+'''foreach addr {0xe9001004 0xe9001008 0xe9001034 0xe9005088 0xe900508c} {
    if {[lindex [read_memory $addr 32 1] 0]!=0} {error "R19 fresh state mismatch"}
}
'''
            for name,addr in [('legacy_seed',0x800000),('color_seed',0x11ffffe0),('depth_seed',0x1200ffe0)]:
                code+=f'load_image {{{out/(name+".bin")}}} {addr:#x} bin\nverify_image {{{out/(name+".bin")}}} {addr:#x} bin\n'
            assert 'SEEDS_READY' in run('seeds',code+'echo SEEDS_READY\n')
            cases=[
                ('TARGET',[22<<24,0x12000000,0x12010000,(128<<16)|16,(256<<16)|256,0,0,0],True),
                ('LEGACY_32B',[0x0100a600,32<<16,(32<<16)|1,0,0,0,0,0],False),
                ('CLEAR_FLAGS_ZERO',[28<<24,0,0x5aa5,0x7bde,0,(16<<16)|1,0,0],True),
                ('CLEAR_EMPTY',[28<<24,3,0x5aa5,0x7bde,0,0,0,0],True),
                ('CLEAR_COLOR_16PX',[28<<24,1,0x5aa5,0x7bde,0,(16<<16)|1,0,0],True)]
            for name,words,capture in cases:
                code=prefix+PACKET+SNAPSHOT+(ARM if capture else '')
                code+='packet {'+' '.join(hex(w) for w in words)+'}\n'
                code+=(CAPTURE if capture else '')+'gpu_snapshot after\n'
                for region,addr,size in [('legacy',0x800000,128),('color',0x11ffffe0,4160),('depth',0x1200ffe0,4160)]:
                    code+=f'dump_image {{{out/(name+"_"+region+".bin")}}} {addr:#x} {size}\n'
                text=run(name,code+DISABLED+'echo CASE_OBSERVED\n')
                item=dict(name=name,words=words,completed=bool(int(re.search(r'^COMMAND_COMPLETE ([01])$',text,re.M)[1])))
                for key in ('BEFORE','AFTER'):item['gpu_'+key.lower()]=[int(w,0) for w in re.search(r'^GPU_'+key+r' (.+)$',text,re.M)[1].split()]
                item['error_deltas']={str(j):(item['gpu_after'][j]-item['gpu_before'][j])&0xffffffff for j in (3,7,9,13,19)}
                if capture:
                    raw=[int(w,0) for w in re.search(r'^NCP (.+)$',text,re.M)[1].split()]
                    epoch=int(re.search(r'^ARM_EPOCH ([01])$',text,re.M)[1]);item['capture_raw']=raw
                    item['capture']=decode(raw[4]|raw[5]<<32,words[0]>>24,epoch)
                expected_legacy=legacy if name=='TARGET' else legacy[:32]+bytes([0xa6])*32+legacy[64:]
                for region,before,expected in [('legacy',legacy,expected_legacy),('color',seed,seed),('depth',zseed,zseed)]:
                    got=(out/(name+'_'+region+'.bin')).read_bytes()
                    if name=='CLEAR_COLOR_16PX' and region=='color':expected=seed[:32]+struct.pack('<H',0x5aa5)*16+seed[64:]
                    item[region]=dict(bytes=len(got),unchanged=got==before,expected_matches=got==expected,
                        different_offsets=[i for i,(a,b) in enumerate(zip(got,expected)) if a!=b][:32],
                        guards_unchanged=got[:32]==before[:32] and got[-32:]==before[-32:])
                r['cases'].append(item);save();print(json.dumps(item),flush=True)
                if not item['completed'] or any(item['error_deltas'].values()):
                    r['stopped_on']=name;r['measurements_complete']=True;break
                assert all(item[k]['expected_matches'] for k in ('legacy','color','depth')),'DDR mismatch'
            else:r['measurements_complete']=True
        except BaseException as exc:r['error']=repr(exc);raise
        finally:
            r['finished_unix']=time.time();r['files']={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='result.json'}
            save();print(json.dumps({k:v for k,v in r.items() if k not in ('identity','files','cases')}),flush=True)

if __name__=='__main__':main()
