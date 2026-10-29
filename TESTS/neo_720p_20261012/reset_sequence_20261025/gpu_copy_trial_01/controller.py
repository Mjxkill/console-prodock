#!/usr/bin/env python3
"""R15 alternate DDR client: bounded clear/copy with guard bytes, CPU parked."""
import fcntl
import hashlib
import json
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time
from framebuffer_trial import HERE, ROOT, BIT_SHA, FRAME, FRAME_SHA, GUARD, DISABLED, CACHE, preflight, hw

BASE=0x12000000
SIZE=4096
PREFIX='riscv expose_csrs 1994,1996,2000\n'+GUARD+DISABLED+CACHE
QUEUE='''if {[lindex [read_memory 0xe9001000 32 1] 0]!=0x424c5432} {error "Wrong command ABI"}
proc packet {name words} {
    if {[llength $words]!=8} {error "Packet length"}
    if {[lindex [read_memory 0xe9001004 32 1] 0]!=0} {error "GPU busy before packet"}
    set before [read_memory 0xe9001008 32 2]
    set extra [list [lindex [read_memory 0xe900101c 32 1] 0] [lindex [read_memory 0xe9001024 32 1] 0]]
    set next [expr {([lindex $before 0]+1)&65535}]
    foreach w $words {write_memory 0xe9001010 32 [list $w]}
    set complete 0
    for {set i 0} {$i<100} {incr i} {
        set after [read_memory 0xe9001004 32 3]
        if {[lindex $after 0]==0 && ([lindex $after 1]&65535)==$next} {set complete 1; break}
        sleep 10
    }
    echo "PACKET_$name BEFORE $before AFTER $after"
    if {!$complete} {error "GPU fence timeout"}
    if {[lindex $after 2]!=[lindex $before 1]} {error "GPU error count changed"}
    set extra_after [list [lindex [read_memory 0xe900101c 32 1] 0] [lindex [read_memory 0xe9001024 32 1] 0]]
    if {$extra_after!=$extra} {error "GPU extra errors changed"}
}
'''

def packet(name, words):
    assert len(words)==8
    return 'packet '+name+' {'+' '.join(hex(w) for w in words)+'}\n'

def main():
    preflight()
    prev=json.loads((HERE/'resolution_matrix_01/result.json').read_text())
    assert prev['bitstream_sha256']==BIT_SHA and prev['restored_bars'] and not prev['fpga_reloaded']
    assert hw.p.sha(FRAME)==FRAME_SHA
    out=HERE/'gpu_copy_trial_01';out.mkdir(exist_ok=False)
    shutil.copy2(Path(__file__),out/'controller.py')
    report=dict(bitstream_sha256=BIT_SHA,qualification='FAIL',
        scope='CPU halted; 4160-byte guarded DDR target; GPU TARGET/CLEAR/COPY; no FPGA reload, Linux, SD or flash',
        script_sha256=hw.p.sha(Path(__file__)),previous_result_sha256=hw.p.sha(HERE/'resolution_matrix_01/result.json'),
        checks=[],passed=False,finished=False)
    seed=bytes((i*61+27)&255 for i in range(SIZE+64))
    (out/'seed.bin').write_bytes(seed)
    frame=FRAME.read_bytes()
    def save(): (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    def run(name,code,timeout=45):
        cfg=out/(name+'.tcl');cfg.write_text(code+'\nshutdown\n')
        log=out/(name+'.log')
        hw.run_child(['/usr/local/bin/openocd','-f',str(ROOT/'tools/neo/ae350_espprog.cfg'),
            '-c','adapter speed 1000; gdb_port disabled; tcl_port disabled; telnet_port disabled',
            '-f',str(cfg)],log,timeout)
        return log.read_text()
    def check(name,expected):
        got=(out/(name+'.bin')).read_bytes()
        wrong=[i for i,(a,b) in enumerate(zip(got,expected)) if a!=b]
        item=dict(name=name,bytes=len(got),expected_bytes=len(expected),wrong_bytes=len(wrong),
            first_wrong=wrong[:32],sha256=hashlib.sha256(got).hexdigest(),
            expected_sha256=hashlib.sha256(expected).hexdigest(),passed=len(got)==len(expected) and not wrong)
        report['checks'].append(item); save()
        assert item['passed'],name+' byte comparison failed'
        print(name.upper()+'_PASS',flush=True)
    def interrupt(sig,frame):raise KeyboardInterrupt(str(sig))
    for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,interrupt)
    with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        active=subprocess.run(['ps','-C','openocd','-C','openFPGALoader','-C','gao_sh',
            '-C','gao_analyzer','-C','jtagserver','-o','pid=,comm='],capture_output=True,text=True)
        assert active.returncode==1 and not active.stdout.strip()
        report['identity']=hw.usb_identity()
        assert report['identity']['neo']['path'].endswith('/3-4.4.1')
        assert report['identity']['esp']['path'].endswith('/3-4.4.2')
        report['started_unix']=time.time(); save()
        try:
            code=PREFIX+QUEUE
            code+=f'load_image {{{out/"seed.bin"}}} {BASE-32:#x} bin\nverify_image {{{out/"seed.bin"}}} {BASE-32:#x} bin\n'
            code+=packet('TARGET',[22<<24,BASE,BASE+0x10000,(128<<16)|16,(256<<16)|256,0,0,0])
            code+=packet('CLEAR',[28<<24,1,0x5aa5,0,0,(128<<16)|16,0,0])
            code+=f'dump_image {{{out/"clear.bin"}}} {BASE-32:#x} {SIZE+64}\necho CLEAR_COMPLETE\n'
            run('clear',code)
            check('clear',seed[:32]+b'\xa5\x5a'*(SIZE//2)+seed[-32:])
            for i,(sx,sy) in enumerate([(0,0),(17,37),(879,327)]):
                name=f'copy_{i}'
                # Check each contiguous source row independently, including nonzero coordinates.
                expected=b''.join(frame[(sy+y)*2560+sx*2:(sy+y)*2560+(sx+128)*2] for y in range(16))
                assert len(expected)==SIZE
                code=PREFIX+QUEUE
                for y in range(16):
                    row=out/f'{name}_source_{y:02d}.bin';row.write_bytes(expected[y*256:(y+1)*256])
                    code+=f'verify_image {{{row}}} {0x01700000+(sy+y)*2560+sx*2:#x} bin\n'
                code+=packet(name,[29<<24,0x01700000,(1024<<16)|512,2560,(sx<<16)|sy,0,(128<<16)|16,0])
                code+=f'dump_image {{{out/(name+".bin")}}} {BASE-32:#x} {SIZE+64}\necho COPY_COMPLETE\n'
                run(name,code,60)
                check(name,seed[:32]+expected+seed[-32:])
            report['passed']=True
        except BaseException as exc:
            report['error']=repr(exc)
        finally:
            try:
                log=run('final_state',GUARD+DISABLED+'echo "GPU_FINAL [read_memory 0xe9001000 32 10]"\necho MIRE_PARKED\n')
                report['mire_parked']='MIRE_PARKED' in log
                report['gpu_final']=[int(w,0) for w in re.search(r'^GPU_FINAL (.+)$',log,re.M).group(1).split()]
            except Exception as exc:report['final_state_error']=repr(exc)
            report['finished']=True;report['finished_unix']=time.time()
            report['logs']={p.name:hw.p.sha(p) for p in out.glob('*.log')}
            save();print(json.dumps({k:v for k,v in report.items() if k!='identity'}),flush=True)
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
