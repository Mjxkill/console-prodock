#!/usr/bin/env python3
"""Await exact reviewed route completion, then run read-only audits sequentially."""
from pathlib import Path
import fcntl,hashlib,json,subprocess,time,sys
HERE=Path(__file__).resolve().parent;ROOT=Path('/home/michael/console')
BUILD=ROOT/'tang/impl/console_neo_n56r21r2_resetqual_coupled'
OUT=HERE/'postroute_01'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def save(p,data):
    tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(data,indent=2)+'\n');tmp.replace(p)

def main():
    launch=json.loads((BUILD/'route_launch.json').read_text());assert launch['netlist_sha256']=='4eace9a4feabe65a1a47e726500b23dd256b4edc3ea4f037b36a9d4d14e08ae4'
    assert launch['assembly_sha256']=='6a0015a5c155d98bea8b98142f0e6153850a5915b5db81551c16231a1b4c1333'
    scripts={n:sha(HERE/n) for n in ['audit_global.py','audit_routed.py','audit_observer.py']}
    OUT.mkdir(exist_ok=False)
    state=dict(status='WAITING_FOR_FINAL_ROUTE',hardware_access=False,route_pid=launch['pid'],started_unix=time.time(),scripts=scripts,watcher_sha256=sha(Path(__file__)))
    save(OUT/'watch_status.json',state)
    with (OUT/'watch.lock').open('x') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        last=''
        while not (BUILD/'route_result.json').is_file():
            if time.time()-state['started_unix']>36000:
                state.update(status='WAIT_TIMEOUT_NO_PROCESS_STOPPED');save(OUT/'watch_status.json',state);return
            log=(BUILD/'build.log').read_text()
            progress=[l for l in log.splitlines() if 'completed' in l or l.startswith(('ERROR','WARN'))]
            if progress and progress[-1]!=last:
                last=progress[-1];state['last_progress']=last;save(OUT/'watch_status.json',state);print(last,flush=True)
            time.sleep(30)
        route=json.loads((BUILD/'route_result.json').read_text())
        if route['status']!='ROUTED_NOT_QUALIFIED' or route['returncode']!=0:
            state.update(status='ROUTING_FAILED_NO_FINAL_AUDIT',route_result=route);save(OUT/'watch_status.json',state);return
        assert route['netlist_sha256']==launch['netlist_sha256']
        assert sha(BUILD/'build.log')==route['log_sha256']
        files=[BUILD/'impl/pnr'/('console_neo'+ext) for ext in ['.vo','.sdf','.tr','.fs','.rpt.txt']]
        stable={str(p):sha(p) for p in files};time.sleep(5)
        assert all(sha(Path(p))==h for p,h in stable.items())
        state.update(status='FINAL_OUTPUTS_CONFIRMED',final_files=stable);save(OUT/'watch_status.json',state)
        runs=[]
        for script,output in [('audit_global.py','global.json'),('audit_routed.py','reset.json'),('audit_observer.py',None)]:
            assert sha(HERE/script)==scripts[script],script
            cmd=[sys.executable,str(HERE/script)]+(['--out',str(OUT/output)] if output else [])
            state.update(status='RUNNING_'+script,runs=runs);save(OUT/'watch_status.json',state)
            start=time.time();entry=dict(script=script,started_unix=start)
            try:
                with (OUT/(script+'.log')).open('x') as log:
                    r=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=log,timeout=900)
                entry['returncode']=r.returncode
            except Exception as exc:entry.update(returncode=None,error=repr(exc))
            entry.update(finished_unix=time.time(),log_sha256=sha(OUT/(script+'.log')))
            runs.append(entry);print(json.dumps(entry),flush=True)
        reports={}
        for name,path in [('global',OUT/'global.json'),('reset',OUT/'reset.json'),('observer',OUT/'observer/result.json')]:
            if path.exists():reports[name]=dict(path=str(path),sha256=sha(path))
        assert all(sha(Path(p))==h for p,h in stable.items())
        state.update(status='AUDITS_FINISHED_REVIEW_REQUIRED',runs=runs,reports=reports,finished_unix=time.time(),all_scripts_returned_zero=all(r['returncode']==0 for r in runs))
        save(OUT/'watch_status.json',state);print(json.dumps(state,indent=2),flush=True)
if __name__=='__main__':main()
