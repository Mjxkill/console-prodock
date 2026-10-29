#!/usr/bin/env python3
"""Guarded RGB565/Z clear and DDR COPY on the halted, already-loaded Neo R19."""
import fcntl
import hashlib
import json
from pathlib import Path
import random
import re
import shutil
import struct
import subprocess
import time
from board_trial_r19 import HERE,ROOT,BIT_SHA,BASE_GUARD,DISABLED,hw,sha,preflight
from framebuffer_trial import CACHE

BASE=0x12000000
ZBASE=BASE+0x10000
SOURCE=BASE+0x20000
SIZE=4096
QUEUE='''proc packet {name words} {
    if {[llength $words]!=8} {error "Command length"}
    set before [read_memory 0xe9001000 32 26]
    if {[lindex $before 1]!=0} {error "GPU busy before packet"}
    set next [expr {([lindex $before 2]+1)&65535}]
    foreach w $words {
        if {[lindex [read_memory 0xe9001004 32 1] 0]&2} {error "Unexpected FIFO full"}
        write_memory 0xe9001010 32 [list $w]
    }
    set complete 0
    for {set i 0} {$i<100} {incr i} {
        set after [read_memory 0xe9001000 32 26]
        if {[lindex $after 1]==0 && ([lindex $after 2]&65535)==$next} {set complete 1;break}
        sleep 10
    }
    echo "PACKET_$name $after"
    if {!$complete} {error "GPU completion timeout"}
    foreach j {3 7 9 13 19} {if {[lindex $after $j]!=[lindex $before $j]} {error "GPU error counter $j changed"}}
}
'''
def packet(name,words):
    assert len(words)==8
    return 'packet '+name+' {'+' '.join(hex(w) for w in words)+'}\n'

def main():
    preflight();anchor=HERE/'r19_board_trial_01/result.json';prior=json.loads(anchor.read_text())
    assert prior['configured'] and prior['measurement_complete'] and prior['all_configuration_commands_accepted']
    assert prior['bitstream_sha256']==BIT_SHA and not prior['restored_r18r1']
    for n,h in prior['files'].items():assert sha(anchor.parent/n)==h,n
    out=HERE/'r19_memory_01';assert not out.exists()
    rng=random.Random(0x138c19)
    make=lambda n:struct.pack('<'+str(n//4)+'I',*[rng.getrandbits(32) for _ in range(n//4)])
    seed=make(SIZE+64);zseed=make(SIZE+64);source=make(16384+64)
    r=dict(bitstream_sha256=BIT_SHA,qualification='FAIL',anchor_sha256=sha(anchor),
        passed=False,checks=[],fpga_reloaded=False,SD_written=False,flash_written=False,
        writes='Volatile DDR guarded color/Z targets and 16 KiB COPY source; CPU halted, display internal bars')
    prefix='riscv expose_csrs 1994,1996,2000\n'+BASE_GUARD+CACHE+QUEUE
    def save():(out/'result.json').write_text(json.dumps(r,indent=2)+'\n')
    def run(name,code):
        cfg=out/(name+'.tcl');cfg.write_text(code+'\nshutdown\n');log=out/(name+'.log')
        hw.run_child(['/usr/local/bin/openocd','-f',str(ROOT/'tools/neo/ae350_espprog.cfg'),
            '-c','adapter speed 1000; gdb_port disabled; tcl_port disabled; telnet_port disabled','-f',str(cfg)],log,55)
        return log.read_text()
    def compare(name,expected):
        got=(out/(name+'.bin')).read_bytes();wrong=[i for i,(a,b) in enumerate(zip(got,expected)) if a!=b]
        item=dict(name=name,bytes=len(got),expected_bytes=len(expected),wrong_bytes=len(wrong),first_wrong=wrong[:24],
                  passed=got==expected,sha256=hashlib.sha256(got).hexdigest(),expected_sha256=hashlib.sha256(expected).hexdigest())
        r['checks'].append(item);save();assert item['passed'],name+' comparison failed'
        print(name.upper()+'_PASS',flush=True)
    with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        active=subprocess.run(['ps','-C','openocd','-C','openFPGALoader','-C','gao_sh','-C','gao_analyzer','-C','jtagserver','-o','pid=,comm='],capture_output=True,text=True)
        assert active.returncode==1 and not active.stdout.strip(),active.stdout
        r['identity']=hw.usb_identity()
        assert r['identity']['neo']['path'].endswith('/3-4.4.1') and r['identity']['esp']['path'].endswith('/3-4.4.2')
        out.mkdir();shutil.copy2(Path(__file__),out/'controller.py')
        for n,data in [('seed',seed),('zseed',zseed),('source',source)]: (out/(n+'.bin')).write_bytes(data)
        r['started_unix']=time.time();save()
        try:
            code=prefix+'''foreach {addr expected} {0xe9005080 0x4e435031 0xe9005088 9 0xe900508c 9 0xe9001008 9 0xe9001034 0} {
    if {[lindex [read_memory $addr 32 1] 0]!=$expected} {error "R19 anchor changed"}
}
'''
            for n,addr in [('seed',BASE-32),('zseed',ZBASE-32),('source',SOURCE-32)]:
                code+=f'load_image {{{out/(n+".bin")}}} {addr:#x} bin\n'
            for n,addr in [('seed',BASE-32),('zseed',ZBASE-32),('source',SOURCE-32)]:
                code+=f'verify_image {{{out/(n+".bin")}}} {addr:#x} bin\n'
            code+='echo CPU_SEEDS_VERIFIED\n'
            code+=packet('TARGET',[22<<24,BASE,ZBASE,(128<<16)|16,(256<<16)|256,0,0,0])
            code+=packet('CLEAR',[28<<24,3,0x5aa5,0x7bde,0,(128<<16)|16,0,0])
            code+=f'dump_image {{{out/"clear_color.bin"}}} {BASE-32:#x} {SIZE+64}\n'
            code+=f'dump_image {{{out/"clear_depth.bin"}}} {ZBASE-32:#x} {SIZE+64}\necho CLEAR_COMPLETE\n'
            r['clear_log_complete']='CLEAR_COMPLETE' in run('clear',code)
            compare('clear_color',seed[:32]+struct.pack('<H',0x5aa5)*(SIZE//2)+seed[-32:])
            zexpected=zseed[:32]+struct.pack('<H',0x7bde)*(SIZE//2)+zseed[-32:]
            compare('clear_depth',zexpected)
            for i,(sx,sy) in enumerate([(0,0),(17,7),(127,16)]):
                code=prefix+packet('COPY_'+str(i),[29<<24,SOURCE,(256<<16)|32,512,(sx<<16)|sy,0,(128<<16)|16,0])
                name='copy_'+str(i)
                code+=f'dump_image {{{out/(name+".bin")}}} {BASE-32:#x} {SIZE+64}\necho COPY_COMPLETE\n'
                assert 'COPY_COMPLETE' in run(name,code)
                pixels=b''.join(source[32+(sy+y)*512+sx*2:32+(sy+y)*512+(sx+128)*2] for y in range(16))
                assert len(pixels)==SIZE;compare(name,seed[:32]+pixels+seed[-32:])
            code=prefix+f'dump_image {{{out/"source_after.bin"}}} {SOURCE-32:#x} {len(source)}\n'
            code+=f'dump_image {{{out/"depth_after.bin"}}} {ZBASE-32:#x} {SIZE+64}\n'
            code+='echo "GPU_FINAL [read_memory 0xe9001000 32 26]"\n'+DISABLED+'echo MEMORY_TRIAL_COMPLETE\n'
            text=run('final',code);compare('source_after',source);compare('depth_after',zexpected)
            r['gpu_final']=[int(w,0) for w in re.search(r'^GPU_FINAL (.+)$',text,re.M)[1].split()]
            assert r['gpu_final'][2]==14 and all(r['gpu_final'][i]==0 for i in (1,3,7,9,13,19))
            r['passed']='MEMORY_TRIAL_COMPLETE' in text;r['mire_parked']=True
        except BaseException as exc:r['error']=repr(exc);raise
        finally:
            r['finished_unix']=time.time();r['files']={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='result.json'}
            save();print(json.dumps({k:v for k,v in r.items() if k not in ('identity','files','checks')}),flush=True)

if __name__=='__main__':main()
