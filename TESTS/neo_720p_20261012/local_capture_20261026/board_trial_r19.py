#!/usr/bin/env python3
"""Nine configuration-only captures on exact Neo R19; SRAM fallback to R18r1."""
import argparse
import fcntl
import json
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time
from board_trial import HERE,ROOT,BASE_GUARD,CAPTURE,DISABLED,hw,sha,decode
from route_local_ce import evidence,NET,SRC,DEST

BIT_SHA='1056917bf942ea2eaf9541b9abbb3997a8ad45eb78fc09e9432f73f3e209917c'
OLD_SHA='f713c85b2dbd8c3d2010e1f34c1af2c88a6cb9f1880ee91c8e706c5f2abf46e1'

def preflight():
    anchor=evidence()
    proof=HERE/'r19_capture_paths_01.json';review=json.loads(proof.read_text())
    assert review['passed'] and review['script_sha256']==sha(HERE/'audit_capture_paths_r19.py')
    path=HERE/'r19_postroute_01/result.json';assert sha(path)==review['route_audit_sha256']
    audit=json.loads(path.read_text())
    for p,h in audit['input_sha256'].items():assert sha(Path(p))==h,p
    assert not any(audit[k] for k in ('missing_parent_cells','changed_parent_cells','changed_parent_parameters','added_cells','missing_primary'))
    assert BIT_SHA==review['bitstream_sha256']==audit['bitstream_sha256']==sha(DEST/'impl/pnr/console_neo.fs')
    assert OLD_SHA==sha(SRC/'impl/pnr/console_neo.fs')
    assert review['sample_setup_lower_bound_ns']>5 and review['held_shadow_max_ns']<3
    assert not any(n==NET for n,_,_ in audit['global_routes'])
    assert audit['qualification_status']=='FAIL'
    return dict(route_audit_sha256=sha(path),capture_paths_sha256=sha(proof),anchor_sha256=sha(anchor),timing=audit['timing'])

def make_probe():
    cases=[];code=BASE_GUARD
    code+='''if {[lindex [read_memory 0xe9005080 32 1] 0]!=0x4e435031 || [lindex [read_memory 0xe9005088 32 1] 0]!=0 || [lindex [read_memory 0xe900508c 32 1] 0]!=0} {error "Fresh R19 observer differs"}
'''
    for i in range(9):
        op=0x16 if i==0 or i%2==1 else 0x1e
        words=[0x16000000,0x12000000,0x12010000,0x00800010,0x01000100,0,0,0] if op==0x16 else [0x1e000000]+[0]*7
        cases.append(dict(index=i,opcode=op,words=words))
        c=CAPTURE.replace('[lindex $gpu 2]!=0','[lindex $gpu 2]!='+str(i))
        if i:c=c.replace('foreach index {3 7 9 13 19}','foreach index {3 7 9 19}')
        c=c.replace('0x16000000 0x12000000 0x12010000 0x00800010 0x01000100 0 0 0',' '.join(hex(w) for w in words))
        c=c.replace('[lindex $gpu 2]==1','[lindex $gpu 2]=='+str(i+1))
        code+='echo CASE_BEGIN_'+str(i)+'\n'+c+'echo CASE_END_'+str(i)+'\n'
    return cases,code+DISABLED+'echo R19_CAPTURE_COMPLETE\n'

def parse(text,cases):
    result=[]
    for case in cases:
        i=case['index'];m=re.search(r'^CASE_BEGIN_'+str(i)+r'\n(.*?)^CASE_END_'+str(i)+r'$',text,re.M|re.S);assert m
        block=m[1];epoch=int(re.search(r'^ARMED ([01]) ',block,re.M)[1])
        rows=[[int(w,0) for w in s.split()] for _,s in re.findall(r'^NCP_(\d) (.+)$',block,re.M)]
        assert len(rows)==3 and all(len(v)==7 for v in rows)
        assert rows[0][:6]==rows[1][:6]==rows[2][:6]
        assert rows[0][0]==0x4e435031 and rows[0][2]==rows[0][3]==i+1
        assert (rows[0][1]&0x4f)==12 and ((rows[0][1]>>5)&1)==epoch and rows[0][6]!=rows[-1][6]
        gpu={n:[int(w,0) for w in s.split()] for n,s in re.findall(r'^GPU_(\w+) (.+)$',block,re.M)}
        assert len(gpu['BEFORE'])==len(gpu['AFTER'])==26
        deltas={name:(gpu['AFTER'][j]-gpu['BEFORE'][j])&0xffffffff for name,j in
            [('transport',3),('queue_lost',7),('raster',9),('pixels_v1',13),('geometry',19)]}
        result.append(dict(case=case,epoch=epoch,rows=rows,gpu=gpu,error_deltas=deltas,
            capture=decode(rows[0][4]|rows[0][5]<<32,case['opcode'],epoch)))
    assert 'R19_CAPTURE_COMPLETE' in text
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check-only',action='store_true');a=p.parse_args()
    proof=preflight();cases,code=make_probe();out=HERE/'r19_board_trial_01';assert not out.exists()
    if a.check_only:
        print(json.dumps(dict(ready=True,hardware=False,bitstream_sha256=BIT_SHA,cases=len(cases),**proof)));return
    r=dict(candidate=True,qualification='FAIL',bitstream_sha256=BIT_SHA,**proof,
        programming_attempted=False,configured=False,restored_r18r1=False,measurement_complete=False,
        cpu_execution_requested=False,DDR_write_requested=False,SD_write_requested=False,flash_write_requested=False)
    def save():(out/'result.json').write_text(json.dumps(r,indent=2)+'\n')
    def run(name,content,timeout=55):
        cfg=out/(name+'.tcl');cfg.write_text(content+'\nshutdown\n');log=out/(name+'.log')
        hw.run_child(['/usr/local/bin/openocd','-f',str(ROOT/'tools/neo/ae350_espprog.cfg'),
            '-c','adapter speed 1000; gdb_port disabled; tcl_port disabled; telnet_port disabled','-f',str(cfg)],log,timeout)
        return log.read_text()
    def interrupt(sig,frame):raise KeyboardInterrupt('Signal '+str(sig))
    for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,interrupt)
    with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        active=subprocess.run(['ps','-C','openocd','-C','openFPGALoader','-C','gao_sh','-C','gao_analyzer','-C','jtagserver','-o','pid=,comm='],capture_output=True,text=True)
        assert active.returncode==1 and not active.stdout.strip(),active.stdout
        r['identity']=hw.usb_identity()
        assert r['identity']['neo']['path'].endswith('/3-4.4.1') and r['identity']['esp']['path'].endswith('/3-4.4.2')
        out.mkdir();shutil.copy2(Path(__file__),out/'controller.py');r['started_unix']=time.time();save()
        board=hw.Hardware(out,r)
        try:
            run('guard_r18r1',BASE_GUARD+'''foreach {address expected} {0xe9005080 0x4e435031 0xe9005088 9 0xe900508c 9 0xe9001004 0 0xe9001008 9 0xe9001034 9} {
    if {[lindex [read_memory $address 32 1] 0]!=$expected} {error "R18r1 anchor changed; do not reconfigure"}
}
echo R18R1_ANCHOR_CONFIRMED
''')
            r['programming_attempted']=True;save()
            board.program('program_r19',DEST/'impl/pnr/console_neo.fs',BIT_SHA)
            r['configured']=True;save();print('R19_CONFIGURED '+BIT_SHA,flush=True)
            r['results']=parse(run('captures',code),cases);r['measurement_complete']=True
            r['all_opcodes_captured']=all(v['capture']['finding']=='OPCODE_CAPTURE_CONSISTENT' for v in r['results'])
            r['all_configuration_commands_accepted']=all(not any(v['error_deltas'].values()) for v in r['results'])
            r['mire_parked']=True;r['left_configured']='R19, halted CPU, internal bars; full GPU unqualified';save()
            try:
                hw.run_child(['/usr/bin/ffmpeg','-hide_banner','-loglevel','warning','-f','v4l2','-input_format','mjpeg',
                    '-video_size','1920x1080','-i','/dev/video0','-vf','select=gte(n\\,15)','-frames:v','1',
                    '-update','1','-n',str(out/'camera.jpg')],out/'camera.log',15)
            except Exception as exc:r['camera_error']=repr(exc)
        except BaseException as exc:
            r['error']=repr(exc);save()
            if r['programming_attempted']:
                for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,signal.SIG_IGN)
                try:
                    board.program('restore_r18r1',SRC/'impl/pnr/console_neo.fs',OLD_SHA);r['restored_r18r1']=True
                    run('restored_guard',BASE_GUARD);r['restored_mire_parked']=True
                except Exception as fallback:r['fallback_error']=repr(fallback)
            raise
        finally:
            r['finished_unix']=time.time();r['files']={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='result.json'}
            save();print(json.dumps({k:r[k] for k in ('configured','restored_r18r1','measurement_complete',
                'all_opcodes_captured','all_configuration_commands_accepted','error') if k in r}),flush=True)

if __name__=='__main__':main()
