"""Exact Tcl mocks plus identity/hash gates; never invokes hardware APIs."""
import ast,json,os,re,subprocess,sys
from pathlib import Path
import read_utna as c
HERE=Path(__file__).resolve().parent
HARNESS=r'''
set fault [lindex $argv 0]
proc init {} {}
proc halt {} {}
proc riscv {args} {}
proc echo {message} {puts $message}
proc shutdown {} {}
proc get_reg {args} {
 global fault
 return [dict create pc [expr {$fault eq "cpu"?0x80010000:0x80000004}] priv 3 satp 0]
}
proc write_memory {args} {error "FORBIDDEN WRITE"}
proc read_memory {address bits count} {
 global fault
 if {$bits!=32} {error "bad width"}
 if {$address==0x80000000 && $count==2} {return {0x10500073 0xffdff06f}}
 if {$address==0xe9005080 && $count==7} {return {0x4e435031 4 0 0 0 0 0}}
 if {$address==0xe9005088 && $count==2} {return {0 0}}
 if {$count!=1} {error "Unexpected bulk read"}
 switch -- [format %x $address] {
  e9000000 {return 0x47505531}
  e9000070 {return 0x02d00500}
  e9000008 - e900000c - e9005088 - e900508c - e9001004 - e9001034 {return 0}
  e9001008 {return [expr {$fault eq "gpu"?1:0}]}
  e9000060 {return 0x1ff8f800}
  e9005080 {return 0x4e435031}
  e9002000 {return [expr {$fault eq "id"?0:0x55544e41}]}
  e9002004 {return [expr {$fault eq "busy"?1:0}]}
  e9002008 {return [expr {$fault eq "sequence"?1:0}]}
  e9002040 {return [expr {$fault eq "alias"?0x55544e41:0}]}
  e9002044 {if {$fault eq "short"} {return {}};return 0}
  e9002048 - e9002080 - e9002084 {return 0}
  default {error "Unexpected address $address"}
 }
}
source [lindex $argv 1]
'''
def main():
 if sys.flags.optimize:raise SystemExit('assertions disabled: refusing to run')
 (HERE/'read_utna.tcl').write_text(c.code());out=HERE/'tests';out.mkdir(exist_ok=False)
 harness=out/'mock.tcl';harness.write_text(HARNESS);records=[]
 for fault in ('none','alias','cpu','gpu','id','busy','sequence','short'):
  result=subprocess.run(['/usr/bin/tclsh',str(harness),fault,str(HERE/'read_utna.tcl')],capture_output=True,text=True,timeout=5)
  (out/(fault+'.log')).write_text(result.stdout+result.stderr)
  if fault in ('none','alias'):
   assert result.returncode==0,(fault,result.stderr)
   parsed=c.parse(result.stdout);assert parsed['initial_bank_all_zero']==(fault=='none')
  else:assert result.returncode!=0 and 'UTNA_READONLY_DONE' not in result.stdout
  records.append(dict(name='tcl_'+fault,passed=True))
 def reject(name,fn):
  try:fn()
  except (RuntimeError,KeyError) as e:records.append(dict(name=name,passed=True,error=str(e)))
  else:raise AssertionError('accepted '+name)
 valid={'neo':{'serial':'2025041420','path':'/sys/3-4.4.1'},'esp':{'path':'/sys/3-4.4.2'}};c.check_identity(valid)
 for key in ('serial','neo_path','esp_path'):
  bad=json.loads(json.dumps(valid))
  if key=='serial':bad['neo']['serial']='wrong'
  elif key=='neo_path':bad['neo']['path']='/wrong'
  else:bad['esp']['path']='/wrong'
  reject(key,lambda:c.check_identity(bad))
 report=HERE/'tests_result.json';report.write_text('{"passed":false}\n')
 base={'board':'neo','scope':'fresh_R19_UTNA_readonly','hardware_ready':False,'controller_sha256':c.sha(HERE/'read_utna.py'),'anchor_sha256':c.ANCHOR_SHA,'r19_sha256':c.prior.base.prior.t.R19_SHA,'proof_files':{str(p.resolve()):c.sha(p) for p in c.dependencies()}}
 review=out/'fake_review.json'
 def check_changed(name,key,value,ready=False):
  bad=json.loads(json.dumps(base));bad[key]=value;review.write_text(json.dumps(bad));reject(name,lambda:c.local_checks(review,ready))
 check_changed('readiness','hardware_ready',False,True)
 check_changed('controller_hash','controller_sha256','0'*64)
 check_changed('anchor_hash','anchor_sha256','0'*64)
 broken=dict(base['proof_files']);broken[str(Path('/usr/local/bin/openocd'))]='0'*64
 check_changed('dependency_hash','proof_files',broken)
 missing=dict(base['proof_files']);missing.pop(str(Path('/usr/local/bin/openocd')))
 check_changed('missing_dependency','proof_files',missing)
 require_no_write=not re.search(r'\b(write_memory|load_image|dump_image|mww|mwh|mwb|resume|irscan|drscan|reset)\b',c.code());assert require_no_write
 tree=ast.parse((HERE/'read_utna.py').read_text());calls=[n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
 assert calls.count('run_child')==1 and not any(n in calls for n in ('program','camera','send','observe'))
 records.append(dict(name='zero_write_no_programming_API',passed=True))
 report.write_text(json.dumps({'passed':True,'hardware_access':False,'controller_sha256':c.sha(HERE/'read_utna.py'),'tcl_sha256':c.sha(HERE/'read_utna.tcl'),'tool_sha256':c.sha(Path(__file__)),'cases':records},indent=2)+'\n')
 print(json.dumps({'passed':True,'hardware_access':False,'cases':len(records)}))
if __name__=='__main__':main()
