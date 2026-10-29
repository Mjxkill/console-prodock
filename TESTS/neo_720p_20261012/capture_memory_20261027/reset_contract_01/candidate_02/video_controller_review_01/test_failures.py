#!/usr/bin/env python3
"""Failure injections only. No device/process/filesystem IO through the controller."""
from pathlib import Path
import hashlib,importlib,json,signal,sys
HERE=Path(__file__).resolve().parent
CTRL=HERE.parents[1]
sys.path.insert(0,str(CTRL))
import probe_coupled_video as c

class Fake:
    def __init__(self,r,phase):self.r,self.phase,self.calls=r,phase,[]
    def step(self,kind,name):
        self.calls.append((kind,name))
        if self.phase==name:raise RuntimeError(name)
        if self.phase==name+'_sigint':signal.raise_signal(signal.SIGINT)
    def observe(self,name,*a):self.step('observe',name)
    def camera(self,name,*a):self.step('camera',name)
    def program(self,name,path,digest):
        self.r.update(last_programmed_sha256=None,left_startup_verified=False)
        self.step('program',name)
        self.r['last_programmed_sha256']=digest

def case(phase):
    report=dict(candidate_sha256='candidate',left_startup_verified=False)
    io=Fake(report,phase);count=0;signals={s:signal.getsignal(s) for s in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP)}
    signal.signal(signal.SIGINT,signal.default_int_handler)
    def save():
        nonlocal count
        count+=1
        if phase=='cleanup_sigint' and count==3:signal.raise_signal(signal.SIGINT)
    error=None
    try:c.execute(io,report,save,Path('candidate.fs'),'read-only fixture')
    except BaseException as e:error=repr(e)
    finally:
        for s,h in signals.items():signal.signal(s,h)
    restores=sum(k=='program' and n=='restore_r19' for k,n in io.calls)
    should_restore=phase not in ('r19_initial_guard','r19_video_readonly','r19_before')
    checks={'restore_once':restores==int(should_restore),
            'restore_failure_not_verified':phase not in ('restore_r19','restored_guard') or not report['left_startup_verified'],
            'camera_before_candidate_read':not any(n=='video_readonly' for _,n in io.calls) or io.calls.index(('camera','coupled_before_dmi'))<io.calls.index(('observe','video_readonly'))}
    return dict(phase=phase,passed=all(checks.values()),checks=checks,calls=io.calls,report=report,error=error)

if __name__=='__main__':
    out=Path(sys.argv[1]);assert not out.exists()
    cases=[case(p) for p in ('success','r19_initial_guard','r19_video_readonly','r19_before','program_coupled','coupled_before_dmi_sigint','video_readonly_sigint','cleanup_sigint','restore_r19','restored_guard')]
    result=dict(passed=all(r['passed'] for r in cases),hardware_access=False,controller_sha256=hashlib.sha256(Path(c.__file__).read_bytes()).hexdigest(),test_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),cases=cases)
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=result['passed'],tests=len(cases),failed=[r['phase'] for r in cases if not r['passed']],out=str(out))))
    raise SystemExit(not result['passed'])
