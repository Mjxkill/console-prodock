"""Offline mocks of exact Tcl, negative contracts, guards and rollback."""
import ast,json,re,subprocess,sys
from pathlib import Path
import probe_snapshot as c
HERE=Path(__file__).resolve().parent
HARNESS=r'''
set fault [lindex $argv 0]
set writes 0
proc init {} {}
proc halt {} {}
proc riscv {args} {}
proc echo {message} {puts $message}
proc sleep {n} {}
proc get_reg {args} {
 global fault
 return [dict create pc [expr {$fault eq "cpu"?0x80010000:0x80000004}] priv 3 satp 0]
}
proc write_memory {address width words} {
 global writes
 if {$address!=0xe900200c || $width!=32 || $words ne "2" || $writes!=0} {error "Unexpected write"}
 incr writes
}
proc read_memory {address bits count} {
 global fault writes
 if {$bits!=32} {error "bad width"}
 if {$address==0x80000000 && $count==2} {return {0x10500073 0xffdff06f}}
 if {$address==0xe9005080 && $count==7} {return {0x4e435031 4 0 0 0 0 0}}
 if {$address==0xe9005088 && $count==2} {return {0 0}}
 if {$address==0xe9002040 && $count>1} {
   set result [lrepeat $count 0]
   lset result 0 0x55544e41;lset result 1 1;lset result 2 2
   if {$fault eq "bulk_alias" || $fault eq "all_alias"} {lset result 1 0;lset result 2 1}
   if {$fault eq "bulk3" && $count==3} {lset result 2 3}
   if {$fault eq "short"} {set result [lrange $result 0 end-1]}
   return $result
 }
 if {$count!=1} {error "Unexpected bulk read"}
 switch -- [format %x $address] {
  e9000000 {return 0x47505531}
  e9000070 {return 0x02d00500}
  e9000008 - e900000c - e9005088 - e900508c - e9001004 - e9001034 {return 0}
  e9001008 {return [expr {$fault eq "gpu"?1:0}]}
  e9000060 {return 0x1ff8f800}
  e9005080 {return 0x4e435031}
  e9002000 {return [expr {$fault eq "id"?0:0x55544e41}]}
  e9002004 {return [expr {$writes&&$fault eq "reject"?2:($fault eq "busy"?1:0)}]}
  e9002008 {return [expr {$writes?($fault eq "timeout"?0:($fault eq "sequence"?2:1)):0}]}
  e9002040 {return [expr {$writes?0x55544e41:0}]}
  e9002044 {return [expr {$writes?($fault eq "individual"||$fault eq "all_alias"?0:1):0}]}
  e9002048 {return [expr {$writes?($fault eq "all_alias"?1:2):0}]}
  default {error "Unexpected address $address"}
 }
}
source [lindex $argv 1]
if {$writes!=1} {error "Expected exactly one write"}
'''

def main():
 if sys.flags.optimize:raise SystemExit('assertions disabled: refusing to run')
 (HERE/'snapshot.tcl').write_text(c.code());out=HERE/'tests';out.mkdir(exist_ok=False)
 harness=out/'mock.tcl';harness.write_text(HARNESS);records=[]
 for fault in ('none','bulk_alias','all_alias','individual','bulk3','cpu','gpu','id','busy','reject','timeout','sequence','short'):
  result=subprocess.run(['/usr/bin/tclsh',str(harness),fault,str(HERE/'snapshot.tcl')],capture_output=True,text=True,timeout=5)
  (out/(fault+'.log')).write_text(result.stdout+result.stderr)
  if fault in ('none','bulk_alias','all_alias','individual','bulk3'):
   assert result.returncode==0,(fault,result.stderr)
   parsed=c.parse(result.stdout);assert parsed['protocol_passed']==(fault=='none'),(fault,parsed)
   assert len(parsed['headers'])==8
  else:assert result.returncode!=0 and 'SNAPSHOT_READS_DONE' not in result.stdout,(fault,result.stdout)
  records.append(dict(name='tcl_'+fault,passed=True))
 valid=(out/'none.log').read_text()
 for name,bad in [('missing',valid.replace('SNAPSHOT_ACK 1','NO_ACK')),('duplicate',valid+'SNAPSHOT_WRITE 2\n'),('order',valid.replace('SNAPSHOT_READ 0 pre','SNAPSHOT_READ 1 pre',1))]:
  try:c.parse(bad)
  except RuntimeError:pass
  else:raise AssertionError('accepted '+name)
  records.append(dict(name='parser_'+name,passed=True))
 # No real IO in controller tests. All rollback paths target exactly R19.
 class IO:
  def __init__(self,fault):self.events=[];self.fault=fault;self.save=lambda:None
  def observe(self,name,code,marker):
   self.events.append(name)
   if self.fault==name:raise RuntimeError(name)
   return valid if name=='r19_snapshot' else marker
  def program(self,name,path,digest):
   assert name=='restore_r19' and path==c.R19 and digest==c.R19_SHA
   self.events.append(name)
   if self.fault==name:raise RuntimeError(name)
 for fault in ('none','r19_initial_guard','r19_snapshot','restore_r19','restored_guard','bad_header'):
  io=IO(fault);report={};old=c.parse
  if fault=='bad_header':c.parse=lambda raw:dict(protocol_passed=False,protocol_errors=['injected'])
  try:
   try:c.execute(io,report,lambda:None,c.code())
   except RuntimeError:assert fault!='none'
   else:assert fault=='none'
  finally:c.parse=old
  assert io.events.count('restore_r19')==(0 if fault=='r19_initial_guard' else 1),(fault,io.events)
  if fault=='bad_header':assert not report.get('observations_completed') and report['observation']['protocol_errors']
  if fault=='none':assert report['left_startup_verified'] and report['observations_completed']
  records.append(dict(name='cleanup_'+fault,passed=True))
 tree=ast.parse((HERE/'probe_snapshot.py').read_text());calls=[n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
 assert calls.count('program')==1 and not any(x in calls for x in ('camera','send'))
 assert re.findall(r'write_memory\s+(0x[0-9a-f]+)\s+32\s+\{([^}]+)\}',c.code())==[('0xe900200c','2')]
 records.append(dict(name='one_snapshot_only_R19_rollback',passed=True))
 # Optimize must refuse before an IO attempt, including helper scripts.
 for option in ('-O','-OO'):
  r=subprocess.run([sys.executable,option,str(HERE/'probe_snapshot.py'),'--review','nonexistent'],capture_output=True,text=True,timeout=5)
  assert r.returncode!=0 and 'assertions disabled' in r.stderr
  records.append(dict(name='optimize_'+option,passed=True))
 (HERE/'tests_result.json').write_text(json.dumps(dict(passed=True,hardware_access=False,controller_sha256=c.sha(HERE/'probe_snapshot.py'),tcl_sha256=c.sha(HERE/'snapshot.tcl'),tool_sha256=c.sha(Path(__file__)),cases=records),indent=2)+'\n')
 print(json.dumps(dict(passed=True,hardware_access=False,cases=len(records))))
if __name__=='__main__':main()
