#!/usr/bin/env python3
"""Wait for this one R17 build and audit outputs only; never load a board."""
import json
from pathlib import Path
import subprocess
import time
from prepare_opcode_probe import HERE,OUT,sha


def main():
    out=HERE/'opcode_route_watch_01'
    out.mkdir(exist_ok=False)
    launch=OUT/'route_launch.json'
    expected=sha(launch)
    data=json.loads(launch.read_text())
    assert data['candidate']==str(OUT)
    audit=HERE/'audit_opcode_probe.py'
    audit_sha=sha(audit)
    r=dict(started_unix=time.time(),status='WAITING',pid=data['pid'],
        launch_sha256=expected,audit_sha256=audit_sha,hardware_loading=False,
        timeout_seconds=21600,qualification='PENDING')
    def save(): (out/'result.json').write_text(json.dumps(r,indent=2)+'\n')
    save()
    try:
        while time.time()-r['started_unix']<r['timeout_seconds']:
            assert sha(launch)==expected, 'Build identity changed'
            if (OUT/'route_result.json').exists():break
            time.sleep(5)
        else:
            r['status']='WAIT_EXPIRED_COMPILER_UNTOUCHED'
            return
        route=json.loads((OUT/'route_result.json').read_text())
        r['route']=route
        r['route_result_sha256']=sha(OUT/'route_result.json')
        if route['status']!='ROUTED_NOT_QUALIFIED' or route['returncode']!=0:
            r.update(status='ROUTING_FAILED',qualification='FAIL')
            return
        assert sha(audit)==audit_sha
        r['status']='AUDITING';save()
        with (out/'audit.log').open('x') as log:
            done=subprocess.run(['/usr/bin/python3',str(audit)],cwd=HERE.parents[2],
                                stdout=log,stderr=log,timeout=600)
        r['audit_returncode']=done.returncode
        r['audit_log_sha256']=sha(out/'audit.log')
        proof=HERE/'opcode_probe_postroute_01/result.json'
        if proof.exists():
            result=json.loads(proof.read_text())
            r['audit_result_sha256']=sha(proof)
            r['qualification']=result['qualification_status']
        else:r['qualification']='FAIL'
        r['status']='AUDIT_COMPLETE' if done.returncode==0 else 'AUDIT_FAILED'
    except BaseException as error:
        r.update(status='WATCH_ERROR',error=repr(error))
        raise
    finally:
        r['finished_unix']=time.time()
        save()
        print(json.dumps(r),flush=True)


if __name__=='__main__':main()
