#!/usr/bin/env python3
"""Local SDC-report-only checks, no Gowin and no hardware."""
import json
from pathlib import Path
import subprocess
import prepare_reports as p
HERE=Path(__file__).resolve().parent

def main():
 checked=p.check();expected=json.loads((p.OUT/'postroute_expected.json').read_text())
 old=(p.PARENT/'source'/p.SDC).read_text();suffix,endpoints=p.report_suffix(expected);new=old+suffix
 cases=[]
 def rejected(name,text):
  try:p.validate_sdc(old,text,expected)
  except RuntimeError:cases.append(dict(name=name,passed=True));return
  raise RuntimeError('invalid report accepted: '+name)
 rejected('modified original constraint',new.replace('create_clock','create_clock_BROKEN',1))
 rejected('appended constraint',new+'set_false_path -to [get_regs *]\n')
 rejected('missing last report','\n'.join(new.splitlines()[:-1])+'\n')
 rejected('wrong endpoint',new.replace(endpoints[0],endpoints[0]+'_BROKEN',1))
 rejected('changed path cap',new.replace('-max_paths 10000 -max_common_paths 3','-max_paths 1 -max_common_paths 3',1))
 # Use actual Tcl parser with strict inert stubs. No tool Tcl commands are loaded.
 tcl='''set count 0
proc get_pins {name} {return $name}
proc report_timing {mode to name max count common n} {
 if {$mode ni {-setup -hold} || $to ne "-to" || $max ne "-max_paths" || $count != 10000 || $common ne "-max_common_paths" || $n != 3} {error "bad report arguments"}
 if {![regexp {^u_usb_idle_trace/(utw_observer/utw_cell_[0-9]+|hrdata_[0-9]+_s0)/(D|CE|RESET)$} $name]} {error "bad endpoint"}
 incr ::count
}
'''
 tcl+='\n'.join(l for l in suffix.splitlines() if l and not l.startswith('//'))
 tcl+='\nif {$count != 2604} {error "bad report count"}\nputs "PASS TCL REPORTS $count"\n'
 result=subprocess.run(['tclsh'],input=tcl,text=True,capture_output=True,timeout=20)
 p.require(result.returncode==0 and result.stdout.strip()=='PASS TCL REPORTS 2604' and not result.stderr,'Tcl report parsing failed '+str(result))
 cases.append(dict(name='real Tcl syntax 2604 bounded inert report calls',passed=True,stdout=result.stdout))
 p.require(len(endpoints)==1302 and len(set(endpoints))==1302,'endpoint coverage duplicated')
 cases.append(dict(name='434 exact registers each D CE RESET and both analyses',passed=True))
 p.require(p.sha(p.OUT/'console_neo.vg')==p.sha(p.PARENT/'console_neo.vg'),'netlist bytes changed')
 cases.append(dict(name='exact netlist bytes and inherited logic proof preserved',passed=True))
 p.save(HERE/'tests.json',dict(passed=True,hardware_access=False,Gowin_executed=False,checks=checked,cases=cases,
  inputs={str(x):p.sha(x) for x in [Path(__file__),HERE/'prepare_reports.py',HERE/'launch_reports.py',p.OUT/'reports_assembly.json']},
  limitation='Tcl syntax and scope only, not Gowin endpoint resolution or timing closure.'))
 print(json.dumps(dict(passed=True,cases=len(cases),reports_assembly_sha256=p.sha(p.OUT/'reports_assembly.json'),launcher_sha256=p.sha(HERE/'launch_reports.py'),test_sha256=p.sha(HERE/'tests.json'))))
if __name__=='__main__':main()
