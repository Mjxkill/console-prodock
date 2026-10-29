"""Freeze an offline-only review packet. This never enables board access."""
import json,sys
from pathlib import Path
if sys.flags.optimize:raise SystemExit('assertions disabled: refusing to run')
import probe_snapshot as c
HERE=Path(__file__).resolve().parent
for result,tool in [('tests_result.json','test_snapshot.py'),('signals_result.json','test_signals.py')]:
 t=json.loads((HERE/result).read_text())
 c.require(t['passed'] and not t['hardware_access'],'Offline tests failed')
 c.require(t['controller_sha256']==c.sha(HERE/'probe_snapshot.py') and t['tool_sha256']==c.sha(HERE/tool),'Stale tests')
c.require(json.loads((HERE/'tests_result.json').read_text())['tcl_sha256']==c.sha(HERE/'snapshot.tcl'),'Stale Tcl proof')
files=set(c.dependencies())|{Path(__file__).resolve(),Path('/usr/bin/tclsh'),HERE/'README.md'}
review=dict(board='neo',scope='R19_snapshot_individual_block_restore',hardware_ready=False,qualification_status='FAIL',
            controller_sha256=c.sha(HERE/'probe_snapshot.py'),anchor_sha256=c.ANCHOR_SHA,r19_sha256=c.R19_SHA,
            observer_commands=[2],observer_write_address='0xe900200c',restore='R19 exact SRAM image only',
            observe_timeout_seconds=30,program_timeout_seconds=120,proof_files={str(p.resolve()):c.sha(p) for p in sorted(files)},
            limits=['No R21r2, no new FPGA build. Identity of current R19 relies on the recorded restoration and continuity.',
                    'Capturing data is not passing its contract: every header must be ID/version1/command2.',
                    'The CPU is halted during guards; restoration restarts ROM, then verifies parked CPU.',
                    'Interrupted trials preserve signals and errors while attempting exact R19 restoration once.'])
temporary=HERE/'tests/guard_review.json';records=[]
def reject(name,bad,ready=False):
 temporary.write_text(json.dumps(bad))
 try:c.local_checks(temporary,ready)
 except (RuntimeError,KeyError) as exc:records.append(dict(name=name,passed=True,error=str(exc)))
 else:raise RuntimeError('Bad review accepted: '+name)
for name,key,value in [('scope','scope','wrong'),('readiness','hardware_ready',False),('controller','controller_sha256','0'*64),('anchor','anchor_sha256','0'*64),('r19','r19_sha256','0'*64)]:
 bad=dict(review);bad[key]=value;reject(name,bad,name=='readiness')
for name in ('missing_dependency','changed_dependency'):
 bad=dict(review);bad['proof_files']=dict(review['proof_files']);key=str(Path('/usr/local/bin/openocd'))
 if name=='missing_dependency':bad['proof_files'].pop(key)
 else:bad['proof_files'][key]='0'*64
 reject(name,bad)
valid={'neo':{'serial':'2025041420','path':'/sys/3-4.4.1'},'esp':{'path':'/sys/3-4.4.2'}}
c.ro.check_identity(valid)
for key in ('serial','neo_path','esp_path'):
 bad=json.loads(json.dumps(valid))
 if key=='serial':bad['neo']['serial']='wrong'
 elif key=='neo_path':bad['neo']['path']='/wrong'
 else:bad['esp']['path']='/wrong'
 try:c.ro.check_identity(bad)
 except RuntimeError as exc:records.append(dict(name=key,passed=True,error=str(exc)))
 else:raise RuntimeError('Bad identity accepted: '+key)
(HERE/'guard_tests_result.json').write_text(json.dumps(dict(passed=True,hardware_access=False,cases=records),indent=2)+'\n')
files|={HERE/'guard_tests_result.json'}|{p.resolve() for p in (HERE/'tests').iterdir() if p.is_file()}
review['proof_files']={str(p.resolve()):c.sha(p) for p in sorted(files)}
target=HERE/'review_prepared.json';target.write_text(json.dumps(review,indent=2)+'\n')
c.local_checks(target,False)
print(json.dumps(dict(controller_sha256=review['controller_sha256'],tcl_sha256=c.sha(HERE/'snapshot.tcl'),review_sha256=c.sha(target),hardware_ready=False,guard_tests=len(records))))
