"""Bind exact read-only code, tests and latest restored R19; never authorize IO."""
import json,sys
from pathlib import Path
if sys.flags.optimize:raise SystemExit('assertions disabled: refusing to run')
import read_utna as c
HERE=Path(__file__).resolve().parent
t=json.loads((HERE/'tests_result.json').read_text())
c.require(t['passed'] and not t['hardware_access'],'Tests failed')
c.require(t['controller_sha256']==c.sha(HERE/'read_utna.py') and t['tcl_sha256']==c.sha(HERE/'read_utna.tcl'),'Tests stale')
c.require(t['tool_sha256']==c.sha(HERE/'test_readonly.py'),'Test runner changed')
files=set(c.dependencies())|{Path(__file__).resolve(),Path('/usr/bin/tclsh')}
files|={p.resolve() for p in (HERE/'tests').iterdir() if p.is_file()}
review={'board':'neo','scope':'fresh_R19_UTNA_readonly','hardware_ready':False,'qualification_status':'FAIL','controller_sha256':c.sha(HERE/'read_utna.py'),'anchor_sha256':c.ANCHOR_SHA,'r19_sha256':c.prior.base.prior.t.R19_SHA,'MMIO_writes':0,'FPGA_writes':0,'timeout_seconds':30,'proof_files':{str(p.resolve()):c.sha(p) for p in sorted(files)},'limits':['R19 identity relies on exact latest programming anchor plus continuity and runtime guards; no configuration readback.','Existing parked-CPU guard issues halt; no CPU resume, no MMIO write, no command to observer.','Diagnostic completion does not require the observed bank to be zero; values are reported without declaring USB/video qualification.']}
(HERE/'review_prepared.json').write_text(json.dumps(review,indent=2)+'\n')
c.local_checks(HERE/'review_prepared.json',False)
print(json.dumps({'controller_sha256':review['controller_sha256'],'tcl_sha256':c.sha(HERE/'read_utna.tcl'),'review_sha256':c.sha(HERE/'review_prepared.json'),'hardware_ready':False}))
