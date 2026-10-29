#!/usr/bin/env python3
"""Read-only qualification of the two regional-placement routes; no board operations."""
from pathlib import Path
import datetime,json,subprocess,sys,time
ROOT=Path('/home/michael/console')
sys.path.insert(0,str(ROOT/'tools/neo'))
from validate_pending import build_state
OUT=ROOT/'TESTS/neo_720p_20261012'
pending=['console_neo_n50r1','console_neo_n50r2']
state={'scope':__doc__,'results':{},'pending':pending.copy()}
deadline=time.monotonic()+7200
while pending and time.monotonic()<deadline:
    for name in pending.copy():
        build=ROOT/'tang/impl'/name
        status=build_state(build)
        if status=='waiting':continue
        if status=='build_failed':
            result={'status':'BUILD_FAILED'}
        else:
            with (OUT/(name+'_qualification.log')).open('w') as log:
                check=subprocess.run([sys.executable,str(ROOT/'tools/check_neo_timing.py'),str(build)],stdout=log,stderr=subprocess.STDOUT,cwd=ROOT)
            qpath=build/'qualification.json'
            if qpath.is_file():
                q=json.loads(qpath.read_text())
                result={k:q.get(k) for k in ('status','timing_checks_ns','minimum_pulse_slack_ns','bitstream_sha256','violated_endpoints','clock_mhz')}
                result['failed_audits']={k:v.get('errors',[]) for k,v in q.get('synthesis_audits',{}).items() if not v.get('passed')}
                result['qualification_returncode']=check.returncode
            else:result={'status':'QUALIFICATION_INCOMPLETE','qualification_returncode':check.returncode}
        result['observed_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        result['hardware_loaded']=False
        (OUT/(name+'_summary.json')).write_text(json.dumps(result,indent=2)+'\n')
        state['results'][name]=result;pending.remove(name)
        print(json.dumps({'build':name,**result}),flush=True)
    state['pending']=pending.copy();state['updated_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    (OUT/'n50_regions_route_observation.json').write_text(json.dumps(state,indent=2)+'\n')
    if pending:time.sleep(20)
if pending:raise SystemExit('Observation deadline expired: '+str(pending))
