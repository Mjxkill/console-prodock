#!/usr/bin/env python3
"""One bounded Neo SRAM trial: capture one TARGET, no DDR/SD/flash writes."""
import argparse
import fcntl
import json
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
from audit_route import HERE, ROOT, BUILD, sha
from decode_capture import decode

OLD=HERE.parent/'reset_sequence_20261025'
sys.path.insert(0,str(OLD))
from load_r15 import preflight as r15_preflight, BUILD as R15, BIT_SHA as R15_SHA, hw
from framebuffer_trial import GUARD, DISABLED

BIT_SHA='f713c85b2dbd8c3d2010e1f34c1af2c88a6cb9f1880ee91c8e706c5f2abf46e1'
BASE_GUARD=GUARD.replace('PARKED_R15','PARKED_CPU')+DISABLED
BEFORE='''set gpu [read_memory 0xe9001000 32 26]
if {[lindex $gpu 0]!=0x424c5432 || [lindex $gpu 1]!=0 || [lindex $gpu 2]!=2 || [lindex $gpu 13]!=2} {error "R15 diagnostic state changed; do not reconfigure"}
echo "R15_BEFORE $gpu"
'''
CAPTURE='''proc word {address} {return [lindex [read_memory $address 32 1] 0]}
set ready 0
for {set i 0} {$i<100} {incr i} {
    if {[word 0xe9005080]==0x4e435031 && ([word 0xe9005084]&7)==4} {set ready 1;break}
    sleep 10
}
if {!$ready} {error "NCP1 absent or not ready"}
set beat [word 0xe9005098]
sleep 10
if {[word 0xe9005098]==$beat} {error "GPU heartbeat stopped"}
set gpu [read_memory 0xe9001000 32 26]
echo "GPU_BEFORE $gpu"
if {[lindex $gpu 0]!=0x424c5432 || [lindex $gpu 1]!=0 || [lindex $gpu 2]!=0} {error "GPU already active before first TARGET"}
foreach index {3 7 9 13 19} {if {[lindex $gpu $index]!=0} {error "Initial GPU error"}}
if {[word 0xe9005000]!=0x4e474442} {error "Legacy observer signature changed"}
echo "RAW_BEFORE [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
set arm [word 0xe9005088]
set seq [word 0xe900508c]
set status [word 0xe9005084]
set epoch [expr {1-(($status>>5)&1)}]
if {$status&3} {error "Observer busy before arm"}
write_memory 0xe9005084 32 {1}
set armed 0
for {set i 0} {$i<100} {incr i} {
    set status [word 0xe9005084]
    if {($status&0x4f)==4 && (($status>>5)&1)==$epoch && [word 0xe9005088]==(($arm+1)&0xffffffff)} {set armed 1;break}
    sleep 10
}
if {!$armed} {error "Explicit arm handshake failed"}
echo "ARMED $epoch $status [word 0xe9005088]"
foreach w {0x16000000 0x12000000 0x12010000 0x00800010 0x01000100 0 0 0} {
    if {[word 0xe9001004]&2} {error "Unexpected full command FIFO"}
    write_memory 0xe9001010 32 [list $w]
}
set complete 0
for {set i 0} {$i<100} {incr i} {
    set gpu [read_memory 0xe9001000 32 26]
    if {[lindex $gpu 1]==0 && [lindex $gpu 2]==1} {set complete 1;break}
    sleep 10
}
echo "GPU_AFTER $gpu"
if {!$complete} {error "First TARGET did not finish"}
echo "RAW_AFTER [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
write_memory 0xe9005088 32 {1}
set snapped 0
for {set i 0} {$i<100} {incr i} {
    set status [word 0xe9005084]
    if {($status&0x4f)==12 && [word 0xe900508c]==(($seq+1)&0xffffffff)} {set snapped 1;break}
    sleep 10
}
if {!$snapped} {error "Snapshot handshake failed"}
for {set i 0} {$i<3} {incr i} {
    echo "NCP_${i} [read_memory 0xe9005080 32 7]"
    sleep 2
}
echo TARGET_CAPTURE_COMPLETE
'''

def preflight():
    r15_preflight()
    path=HERE/'capture_paths_01.json';review=json.loads(path.read_text())
    assert review['passed'] and review['qualification']=='FAIL'
    assert review['script_sha256']==sha(HERE/'audit_capture_paths.py')
    audit=HERE/'postroute_01/result.json';assert review['route_audit_sha256']==sha(audit)
    proof=json.loads(audit.read_text())
    assert BIT_SHA==review['bitstream_sha256']==proof['bitstream_sha256']==sha(BUILD/'impl/pnr/console_neo.fs')
    for p,h in proof['input_sha256'].items():assert sha(Path(p))==h,p
    assert proof['timing_summary']['violated_endpoints']==dict(setup=63,hold=0)
    assert review['sample_setup_lower_bound_ns']>5 and review['held_shadow_max_ns']<2
    assert not proof['missing_primary']
    for n in ('neo_capture_local','neo_capture_bus'):
        assert sha(HERE/(n+'.v'))==sha(BUILD/'source/tang/boards/neo'/(n+'.v'))
    prior=OLD/'warm_long_01/result.json'
    assert sha(prior)=='8a8ef8c3e9936d25a38097f93c6aada29ff1582df923ba50e53ffdee89d8d829'
    assert json.loads(prior.read_text())['mire_parked']
    return proof

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check-only',action='store_true');a=p.parse_args()
    proof=preflight();out=HERE/'board_trial_01';assert not out.exists()
    if a.check_only:
        print(json.dumps(dict(ready=True,hardware=False,bitstream_sha256=BIT_SHA,
                             qualification='FAIL',timing=proof['timing'])));return
    def interrupt(sig,frame):raise KeyboardInterrupt('Signal '+str(sig))
    for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,interrupt)
    r=dict(candidate=True,qualification='FAIL',timing=proof['timing'],bitstream_sha256=BIT_SHA,
           programming_attempted=False,configured=False,restored_r15=False,measurement_complete=False,
           cpu_execution_requested=False,DDR_write_requested=False,SD_write_requested=False,flash_write_requested=False,
           scope='One configuration-only TARGET on halted Neo CPU; GPU qualification remains pending')
    def save():(out/'result.json').write_text(json.dumps(r,indent=2)+'\n')
    def run(name,code):
        cfg=out/(name+'.tcl');cfg.write_text(code+'\nshutdown\n');log=out/(name+'.log')
        hw.run_child(['/usr/local/bin/openocd','-f',str(ROOT/'tools/neo/ae350_espprog.cfg'),
            '-c','adapter speed 1000; gdb_port disabled; tcl_port disabled; telnet_port disabled','-f',str(cfg)],log,40)
        return log.read_text()
    with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        active=subprocess.run(['ps','-C','openocd','-C','openFPGALoader','-C','gao_sh','-C','gao_analyzer',
                               '-C','jtagserver','-o','pid=,comm='],capture_output=True,text=True)
        assert active.returncode==1 and not active.stdout.strip(),active.stdout
        r['identity']=hw.usb_identity()
        assert r['identity']['neo']['path'].endswith('/3-4.4.1')
        assert r['identity']['esp']['path'].endswith('/3-4.4.2')
        out.mkdir();shutil.copy2(Path(__file__),out/'controller.py');r['started_unix']=time.time();save()
        board=hw.Hardware(out,r)
        try:
            run('guard_r15',BASE_GUARD+BEFORE)
            r['programming_attempted']=True;save()
            board.program('program_r18r1',BUILD/'impl/pnr/console_neo.fs',BIT_SHA)
            r['configured']=True;save();print('R18R1_CONFIGURED '+BIT_SHA,flush=True)
            text=run('first_target',BASE_GUARD+CAPTURE+DISABLED+'echo MIRE_PARKED\n')
            r['gpu']={n:[int(w,0) for w in s.split()] for n,s in re.findall(r'^GPU_(\w+) (.+)$',text,re.M)}
            r['raw']={n:[int(w,0) for w in s.split()] for n,s in re.findall(r'^RAW_(\w+) (.+)$',text,re.M)}
            rows=[[int(w,0) for w in s.split()] for _,s in re.findall(r'^NCP_(\d) (.+)$',text,re.M)]
            assert len(rows)==3 and all(len(v)==7 for v in rows)
            assert rows[0][:6]==rows[1][:6]==rows[2][:6]
            assert rows[0][0]==0x4e435031 and rows[-1][6]!=rows[0][6]
            epoch=int(re.search(r'^ARMED ([01]) ',text,re.M)[1]);status=rows[0][1]
            assert status&0x4f==12 and (status>>5)&1==epoch
            r['snapshot_rows']=rows;r['arm_epoch']=epoch
            r['capture']=decode(rows[0][4]|rows[0][5]<<32,0x16,epoch)
            before,after=r['gpu']['BEFORE'],r['gpu']['AFTER'];assert len(before)==len(after)==26
            r['error_deltas']={name:(after[i]-before[i])&0xffffffff for name,i in
                [('transport',3),('queue_lost',7),('raster',9),('pixels_v1',13),('geometry',19)]}
            r['r15_rejection_reproduced']=r['error_deltas']['pixels_v1']==1
            r['measurement_complete']='TARGET_CAPTURE_COMPLETE' in text
            r['mire_parked']='MIRE_PARKED' in text
            r['left_configured']='R18r1, CPU halted, internal bars; diagnostic only'
            save()
            try:
                hw.run_child(['/usr/bin/ffmpeg','-hide_banner','-loglevel','warning','-f','v4l2',
                    '-input_format','mjpeg','-video_size','1920x1080','-i','/dev/video0',
                    '-vf','select=gte(n\\,15)','-frames:v','1','-update','1','-n',str(out/'camera.jpg')],out/'camera.log',15)
            except Exception as exc:r['camera_error']=repr(exc)
        except BaseException as exc:
            r['error']=repr(exc);save()
            if r['programming_attempted']:
                for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,signal.SIG_IGN)
                try:
                    board.program('restore_r15',R15/'impl/pnr/ao_0.fs',R15_SHA);r['restored_r15']=True
                    run('restored_guard',BASE_GUARD);r['restored_mire_parked']=True
                except Exception as fallback:r['fallback_error']=repr(fallback)
            raise
        finally:
            r['finished_unix']=time.time()
            r['files']={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='result.json'}
            save();print(json.dumps({k:r[k] for k in ('configured','restored_r15','measurement_complete',
                'capture','error_deltas','error') if k in r}),flush=True)

if __name__=='__main__':main()
