#!/usr/bin/env python3
"""R19 activity capture with strict guards and recorded version0 failure; exact rollback."""
import argparse, fcntl, hashlib, json, re, subprocess, sys, time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
READONLY=HERE.parent/'utna_readonly_prepared_01'
sys.path.insert(0,str(READONLY))
import read_utna as ro
prior=ro.prior
sha=ro.sha
require=ro.require
StopRequest=prior.StopRequest
ANCHOR=HERE.parent/'utna_snapshot_prepared_01/snapshot_20261027_232521/result.json'
ANCHOR_SHA='c3f12030d68b66b25aec57a4c0c70d77909746c178598576307162fd624a79dc'
R19=prior.base.prior.t.R19/'impl/pnr/console_neo.fs'
R19_SHA=prior.base.prior.t.R19_SHA

def code():
    return prior.base.prior.check_code(0)+(HERE/'activity_body.tcl').read_text()

def dependencies():
    files={Path(__file__),HERE/'activity_body.tcl',HERE/'activity.tcl',HERE/'test_activity.py',
           HERE/'test_signals.py',HERE/'tests_result.json',HERE/'signals_result.json',ANCHOR,
           ro.ANCHOR,R19,ROOT/'tools/neo/ae350_espprog.cfg',Path('/usr/local/bin/openocd'),
           Path.home()/'.local/bin/openFPGALoader'}
    for module in tuple(sys.modules.values()):
        name=getattr(module,'__file__',None)
        if name:
            p=Path(name).resolve()
            if p.is_file() and p.suffix=='.py' and p.is_relative_to(ROOT) and not p.is_relative_to(HERE):files.add(p)
    return sorted(files)

def local_checks(path,ready=True):
    r=json.loads(path.read_text())
    require(r['board']=='neo' and r['scope']=='R19_activity_collect_version0_FAIL_restore','Wrong scope')
    require(r['qualification_status']=='FAIL','Diagnostic is not qualification')
    require(not ready or r['hardware_ready'] is True,'Root review pending')
    require(r['controller_sha256']==sha(Path(__file__)),'Controller changed')
    require(sha(ANCHOR)==ANCHOR_SHA==r['anchor_sha256'],'Read-only anchor changed')
    a=json.loads(ANCHOR.read_text())
    require('finished_unix' in a and a['left_startup_verified'] and not a['signals_received'],'Anchor incomplete')
    require(a['last_programmed_sha256']==a['r19_sha256']==R19_SHA==r['r19_sha256']==sha(R19),'Wrong R19')
    require(a['restore_attempted'] and 'restore_error' not in a,'Missing restoration')
    for name,digest in a['files'].items():require(sha(ANCHOR.parent/name)==digest,'Anchor evidence changed: '+name)
    require('RESTORED_UTNA_FRESH' in (ANCHOR.parent/'restored_guard.log').read_text(),'Missing restored guard')
    require(all(str(p.resolve()) in r['proof_files'] for p in dependencies()),'Missing dependency')
    for name,digest in r['proof_files'].items():require(sha(Path(name))==digest,'Dependency changed: '+name)
    text=(HERE/'activity.tcl').read_text();require(text==code(),'Tcl changed')
    require(re.findall(r'write_memory\s+(0x[0-9a-f]+)',text)==['0xe900200c'],'Unexpected observer write')
    require(re.findall(r'^capture (\w+) (\d+) (\d+)$',text,re.M)==[('ARM','1','1'),('DISARM','6','2'),('STOPPED','2','3'),('STABLE','2','4')],'Unexpected command sequence')
    require(not re.search(r'\b(load_image|dump_image|mww|mwh|mwb|resume|irscan|drscan|reset)\b',text),'Forbidden Tcl operation')
    for name in ('tests_result.json','signals_result.json'):
        t=json.loads((HERE/name).read_text());require(t['passed'] is True and not t['hardware_access'],'Missing offline proof')
    return r,text

def parse(raw):
    expected=[('ARM',1,1),('DISARM',6,2),('STOPPED',2,3),('STABLE',2,4)]
    writes=re.findall(r'^ACTIVITY_WRITE (\w+) (\d+) (\d+)\r?$',raw,re.M)
    require([(a,int(b),int(c)) for a,b,c in writes]==expected,'Wrong command sequence')
    blocks=[];errors=[]
    for phase,command,sequence,which,text in re.findall(r'^ACTIVITY_BANK (\w+) (\d+) (\d+) (first|repeat) (.+)\r?$',raw,re.M):
        words=[int(x,0) for x in text.split()]
        require(len(words)==32 and all(0<=x<=0xffffffff for x in words),'Invalid bank')
        require(words[0]==0x55544e41 and words[2]==int(command),'ID or command mismatch')
        require(words[1] in (0,1),'Unsupported version value')
        if words[1]==0:errors.append('Version0: '+phase+' '+which)
        blocks.append(dict(phase=phase,command=int(command),sequence=int(sequence),which=which,words=words))
    require([(b['phase'],b['command'],b['sequence'],b['which']) for b in blocks]==[(phase,cmd,seq,which) for phase,cmd,seq in expected for which in ('first','repeat')],'Incomplete/reordered banks')
    control=re.findall(r'^ACTIVITY_CONTROL (\w+) (.+)\r?$',raw,re.M)
    wants=[('INITIAL',0)]+[(phase+'_'+label,n) for phase,cmd,seq in expected for label,n in [('BEFORE',seq-1),('ACK',seq),('AFTER',seq)]]
    require(len(control)==len(wants),'Missing controls')
    for (label,text),(want,sequence) in zip(control,wants):
        require(label==want and [int(x,0) for x in text.split()]==[0x55544e41,0,sequence],'Control mismatch')
    require(re.search(r'^ACTIVITY_READS_DONE\r?$',raw,re.M),'Capture incomplete')
    for i in range(0,8,2):require(blocks[i]['words']==blocks[i+1]['words'],'Bank changed within phase')
    a,d,s,h=[blocks[i]['words'] for i in range(0,8,2)]
    activity=dict(arm_ticks=a[3],disarm_ticks=d[3],stopped_ticks=s[3],stable_ticks=h[3],armed=[bool(v[31]&0x400) for v in (a,d,s,h)])
    if a[3]!=0 or a[31]&0x400:errors.append('ARM is not fresh pre-clear state')
    if d[3]==0 or not d[31]&0x400:errors.append('DISARM lacks armed ticks')
    if s[31]&0x400 or h[31]&0x400:errors.append('Observer did not remain disarmed')
    if s[3]!=(d[3]+1)&0xffffffff:errors.append('Final disarm tick differs from RTL contract')
    if h[3]!=s[3]:errors.append('Stopped ticks changed')
    return dict(blocks=blocks,activity=activity,protocol_errors=errors,protocol_passed=not errors,capture_complete=True,
                qualification_status='FAIL',limits=['Captured counters do not establish physical frequency.','This sequence does not separate FIFO slot1 from bank slot1 or bank validity.'])

def execute(io,report,save,text,stop=None):
    stop=stop if stop is not None else StopRequest()
    report['signals_received']=stop.received
    touched=False
    try:
        stop.checkpoint()
        io.observe('r19_initial_guard',prior.restoration_guard(),'RESTORED_UTNA_FRESH')
        stop.checkpoint()
        report['baseline_verified']=True
        save()
        stop.checkpoint()
        touched=True
        stop.checkpoint()
        raw=io.observe('r19_activity',text,'ACTIVITY_READS_DONE')
        stop.checkpoint()
        report['observation']=parse(raw)
        report['observations_collected']=True
        save()
        require(report['observation']['protocol_passed'],'Activity data contract failed: '+repr(report['observation']['protocol_errors']))
        report['observations_completed']=True
        save()
        stop.checkpoint()
    except BaseException as exc:
        report['error']=repr(exc)
        try:save()
        except BaseException as log_error:report.setdefault('error_log_errors',[]).append(repr(log_error))
        raise
    finally:
        if touched:
            def cleanup_save():
                try:save()
                except BaseException as exc:report.setdefault('cleanup_log_errors',[]).append(repr(exc))
            if hasattr(io,'save'):io.save=cleanup_save
            report['restore_attempted']=True
            cleanup_save()
            try:
                io.program('restore_r19',R19,R19_SHA)
                io.observe('restored_guard',prior.restoration_guard(),'RESTORED_UTNA_FRESH')
                report.update(left_startup_verified=True,left_state='R19 restored, parked CPU, fresh GPU/NCP/UTNA, internal bars')
                cleanup_save()
            except BaseException as exc:
                report['restore_error']=repr(exc)
                cleanup_save()
                raise
    try:stop.checkpoint()
    except KeyboardInterrupt as exc:
        report['error']=repr(exc)
        try:save()
        except BaseException as log_error:report.setdefault('error_log_errors',[]).append(repr(log_error))
        raise

def main():
    if sys.flags.optimize:raise SystemExit('assertions disabled: refusing to run')
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--review',type=Path,required=True);p.add_argument('--check-only',action='store_true');args=p.parse_args()
    path=args.review.resolve();require(path.is_relative_to(HERE),'Review must be in prepared folder')
    review,text=local_checks(path,not args.check_only)
    if args.check_only:print(json.dumps(dict(preflight_passed=True,hardware_access=False,hardware_ready=review['hardware_ready'])));return
    stop=StopRequest();stop.install();stop.checkpoint()
    with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        active=subprocess.run(['ps','-C','openocd','-C','openFPGALoader','-C','gao_sh','-C','gao_analyzer','-C','jtagserver','-o','pid=,comm='],capture_output=True,text=True,timeout=5)
        require(active.returncode==1 and not active.stdout.strip(),'Another debug tool is active')
        stop.checkpoint();identity=prior.base.prior.hw.usb_identity();ro.check_identity(identity);stop.checkpoint()
        out=HERE/('activity_'+time.strftime('%Y%m%d_%H%M%S'));out.mkdir(exist_ok=False)
        (out/'controller_used.py').write_bytes(Path(__file__).read_bytes())
        report=dict(board='neo',qualification_status='FAIL',hardware_review_sha256=sha(path),anchor_sha256=ANCHOR_SHA,
                    r19_sha256=R19_SHA,last_programmed_sha256=R19_SHA,left_startup_verified=False,
                    observations_completed=False,observations_collected=False,identity=identity,started_unix=time.time(),observer_commands=[1,6,2,2],
                    observer_write_address=0xe900200c,observer_mutation=True,R21r2_programming=False,
                    UART_commands=False,DDR_written=False,GPU_commands=False,SD_written=False,flash_written=False,
                    Linux_loaded=False,CPU_resume_command=False,CPU_ROM_restart_possible=True)
        def save():(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        save()
        try:execute(prior.base.prior.IO(out,report,save),report,save,text,stop)
        finally:
            report['finished_unix']=time.time();report['files']={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='result.json'}
            save();print(json.dumps(dict(output=str(out),**report)),flush=True)
if __name__=='__main__':main()
