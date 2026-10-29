"""Offline tests of exact Tcl and rollback controller; never opens any hardware."""
import ast,copy,inspect,json,os,re,signal,subprocess,sys,tempfile
from pathlib import Path
import collector as c
HERE=Path(__file__).resolve().parent
CANDIDATE=dict(path='TESTS/mock_candidate_never_opened.fs',bitstream_sha256='a'*64,netlist_sha256=c.decoder.NET_SHA)
HARNESS=r'''
set fault [lindex $argv 0]
set writes 0
set command 0
set bankreads 0
set extreads 0
set controls 0
proc init {} {}
proc halt {} {}
proc riscv {args} {}
proc echo {message} {puts $message}
proc sleep {n} {if {$n ni {2 100 200}} {error "unbounded sleep"}}
proc get_reg {args} {
 global fault
 return [dict create pc [expr {$fault eq "cpu"?0x80010000:0x80000004}] priv 3 satp 0]
}
proc write_memory {address width words} {
 global writes command bankreads extreads controls fault
 if {$address!=0xe900200c || $width!=32 || $words ne [lindex {1 6 2 2} $writes] || $writes>3} {error "Unexpected write"}
 incr writes;set command $words;set bankreads 0;set extreads 0;set controls 0
}
proc word {address} {
 global fault writes
 switch -- [format %x $address] {
  e9000000 {return 0x47505531}
  e9000070 {return 0x02d00500}
  e9000008 - e900000c - e9005088 - e900508c - e9001004 - e9001034 {return 0}
  e9001008 {return [expr {$fault eq "gpu"?1:0}]}
  e9000060 {return 0x1ff8f800}
  e9005080 {return 0x4e435031}
  e9002000 {return [expr {$fault eq "id"?0:0x55544e41}]}
  e9002004 {return [expr {$writes&&$fault eq "reject"?2:($fault eq "busy"?1:($writes&&$fault eq "flags"?4:0))}]}
  e9002008 {return [expr {$writes?($fault eq "timeout"?0:($fault eq "sequence"?7:$writes)):0}]}
  default {error "Unexpected address $address"}
 }
}
proc read_memory {address bits count} {
 global fault writes command bankreads extreads controls
 if {$bits!=32} {error "bad width"}
 if {$address==0x80000000 && $count==2} {return {0x10500073 0xffdff06f}}
 if {$address==0xe9005080 && $count==7} {return {0x4e435031 4 0 0 0 0 0}}
 if {$address==0xe9005088 && $count==2} {return {0 0}}
 if {$address==0xe9002000 && $count==3} {
  incr controls;set values [list [word $address] [word [expr {$address+4}]] [word [expr {$address+8}]]]
  if {$fault eq "changed_control" && $controls==2} {lset values 2 77}
  return $values
 }
 if {$address==0xe9002040 && $count==32} {
   incr bankreads
   set result [lrepeat 32 0]
   lset result 0 0x55544e41;lset result 1 1;lset result 2 $command
   lset result 3 [lindex {0 0 123 124 124} $writes]
   if {$writes==2} {lset result 31 0x400}
   if {$fault in {version0 raw0}} {lset result 1 0}
   if {$fault eq "version3"} {lset result 1 3}
   if {$fault eq "bank_id"} {lset result 0 0}
   if {$fault eq "command"} {lset result 2 7}
   if {$fault eq "ticks"} {lset result 3 0}
   if {$fault eq "armed"} {lset result 31 0}
   if {$fault eq "last_tick" && $writes>=3} {lset result 3 123}
   if {$fault eq "unstable" && $bankreads==2} {lset result 9 1}
   if {$fault eq "short"} {set result [lrange $result 0 end-1]}
   if {$fault eq "out_of_u32"} {lset result 9 0x100000000}
   return $result
 }
 if {$address==0xe90020c0 && $count==16} {
   set result [concat {0x55545731 0x10001} [lrepeat 14 0]]
   if {$fault eq "abi"} {lset result 1 3}
   if {$writes==0} {
    if {$fault eq "initial_dirty"} {lset result 4 1}
    return $result
   }
   incr extreads
   set raw [expr {$fault in {raw0 contradiction}?0:1}]
   lset result 2 0x55544e41;lset result 3 $raw;lset result 4 $command;lset result 5 $raw
   foreach i {6 7 8 10} {lset result $i $writes}
   lset result 9 [expr {32*$writes}]
   lset result 12 0x003f0007
   foreach i {13 14 15} {lset result $i [expr {$writes-1}]}
   if {$fault eq "alias"} {lset result 5 3}
   if {$fault eq "ec"} {lset result 11 1}
   if {$fault eq "tag"} {lset result 14 $writes}
   if {$fault eq "total"} {lset result 9 [expr {31*$writes}]}
   if {$fault eq "status"} {lset result 12 0x00370007}
   if {$fault eq "frame"} {lset result 7 0}
   if {$fault eq "rawid"} {lset result 2 0}
   if {$fault eq "rawcommand"} {lset result 4 0}
   if {$fault eq "unstable_ext" && $extreads==2} {lset result 15 99}
   if {$fault eq "short_ext"} {set result [lrange $result 0 end-1]}
   return $result
 }
 if {$count!=1} {error "Unexpected bulk read"}
 return [word $address]
}
source [lindex $argv 1]
if {$writes!=4} {error "Expected exactly four writes"}
'''

def rejected(fn):
 try:fn()
 except (RuntimeError,ValueError,KeyError,TypeError,OSError):return
 raise AssertionError('negative case accepted')

def signal_child(case,number,log):
 stop=c.StopRequest();stop.install();events=[];report={};fired=False;delivered=[]
 valid=Path(log).read_text()
 def deliver():
  nonlocal fired
  if fired:return
  fired=True
  for sig in ((signal.SIGINT,signal.SIGTERM,signal.SIGHUP) if case=='all_cleanup' else (number,)):
   delivered.append(int(sig));os.kill(os.getpid(),sig)
 class IO:
  current=''
  def __init__(self):self.save=self.write_report
  def write_report(self):
   if case=='cleanup_save' and report.get('restore_attempted'):deliver()
   if case=='log_error' and 'error' in report and not report.get('restore_attempted'):
    deliver();raise OSError('primary log failure')
   if case=='cleanup_log_error' and self.current=='restore_r19':
    deliver();raise OSError('cleanup log failure')
  def event(self,name):
   self.current=name;events.append(name)
   if case=='event:'+name:deliver()
   if case in ('all_cleanup','restore_error') and name=='restore_r19':deliver()
   if name=='candidate_utw1_capture' and case in ('experiment_error','double_error','log_error','error_finally'):raise RuntimeError('primary failure')
   if name=='restore_r19' and case in ('double_error','restore_error'):raise RuntimeError('restore failure')
  def observe(self,name,code,marker):self.event(name);return valid if name=='candidate_utw1_capture' else marker
  def program(self,name,path,digest):
   assert (name,path,digest) in (('candidate_utw1',c.ROOT/CANDIDATE['path'],CANDIDATE['bitstream_sha256']),('restore_r19',c.R19,c.R19_SHA))
   self.event(name);self.save();report['last_programmed_sha256']=digest;self.save()
 lines,start=inspect.getsourcelines(c.execute)
 tokens={'finally_entry':'if touched:','cleanup_definition':'def cleanup_save():',
         'cleanup_attempt':"report['restore_attempted']=True;cleanup_save()",'cleanup_first_save':"if hasattr(io,'save'):io.save=cleanup_save",
         'experiment_error':"report['error']=repr(exc)",'double_error':"report['error']=repr(exc)",
         'error_finally':'if touched:'}
 mapping={name:start+next(i for i,line in enumerate(lines) if line.strip()==token) for name,token in tokens.items()}
 mapping['after_cleanup']=start+next(i for i,line in enumerate(lines) if line.strip()=='try:stop.checkpoint()')
 def trace(frame,event,arg):
  if not fired and frame.f_code is c.execute.__code__ and event=='line' and frame.f_lineno==mapping.get(case):deliver()
  return trace
 io=IO();error=None;context=None;sys.settrace(trace)
 try:c.execute(io,report,io.write_report,c.code(),CANDIDATE,stop)
 except BaseException as exc:error=repr(exc);context=repr(exc.__context__) if exc.__context__ else None
 finally:sys.settrace(None)
 early=case=='event:r19_initial_guard'
 assert fired and report['signals_received']==delivered,(case,report)
 assert events.count('restore_r19')==(0 if early else 1),(case,events)
 assert error is not None,(case,report)
 if case in ('experiment_error','log_error','error_finally'):
  assert error==report['error']=="RuntimeError('primary failure')",(case,error,report)
 elif case=='double_error':
  assert report['error']=="RuntimeError('primary failure')"
  assert error==report['restore_error']=="RuntimeError('restore failure')" and context==report['error']
 elif case=='restore_error':assert error==report['restore_error']=="RuntimeError('restore failure')"
 else:assert 'KeyboardInterrupt' in error and report['error']==error,(case,error,report)
 if not early and case not in ('double_error','restore_error'):
  assert report['left_startup_verified'] and report['last_programmed_sha256']==c.R19_SHA
 if case=='log_error':assert report['error_log_errors']
 if case=='cleanup_log_error':assert report['cleanup_log_errors']
 print(json.dumps(dict(passed=True,case=case,signal=int(number),events=events,delivered=delivered,error=error,context=context,report=report,hardware_access=False)))

def main():
 if sys.flags.optimize:raise SystemExit('assertions disabled: refusing to run')
 if len(sys.argv)==5 and sys.argv[1]=='--signal':signal_child(sys.argv[2],int(sys.argv[3]),sys.argv[4]);return
 out=Path(sys.argv[1]).resolve();assert out.is_relative_to(HERE);out.mkdir(exist_ok=False)
 (HERE/'capture.tcl').write_text(c.code());harness=out/'mock.tcl';harness.write_text(HARNESS);records=[]
 def record(name):records.append(dict(name=name,passed=True))
 tcl_fail=('cpu','gpu','id','busy','reject','timeout','sequence','flags','short','out_of_u32','short_ext','abi','initial_dirty')
 data_fail=('version0','raw0','contradiction','version3','bank_id','command','ticks','armed','last_tick','unstable','alias','ec','tag','total','status','frame','rawid','rawcommand','unstable_ext','changed_control')
 for fault in ('none',)+tcl_fail+data_fail:
  result=subprocess.run(['/usr/bin/tclsh',str(harness),fault,str(HERE/'capture.tcl')],capture_output=True,text=True,timeout=5)
  (out/(fault+'.log')).write_text(result.stdout+result.stderr)
  if fault in tcl_fail:assert result.returncode!=0 and 'UTW1_READS_DONE' not in result.stdout,(fault,result.stdout)
  else:
   assert result.returncode==0,(fault,result.stderr)
   parsed=c.parse(result.stdout,'a'*64,origin='synthetic');assert parsed['protocol_passed']==(fault=='none'),(fault,parsed)
   assert len(parsed['captures'])==4 and all(len(s['packet']['reads']['image_a'])==48 for s in parsed['captures'])
   if fault in ('version0','raw0'):
    assert parsed['coherent'] and all(s['decode']['status']=='COHERENT_ANOMALY_VERSION_ZERO' for s in parsed['captures'])
   assert parsed['qualification_status']=='FAIL' and parsed['hardware_qualified'] is False
  record('tcl_'+fault)
 valid=(out/'none.log').read_text()
 mutations={
  'missing_done':valid.replace('UTW1_READS_DONE','NO_DONE'),
  'duplicate':valid+'UTW1_WRITE STABLE 2 4\n',
  'order':valid.replace('UTW1_READ ARM','UTW1_READ STABLE',1),
  'missing_guard':valid.replace('WARM_CHECK_0','NO_GUARD'),
  'duplicate_guard':valid+'WARM_CHECK_0\n',
  'partial':valid[:len(valid)//2],
  'badphase':valid.replace('"phase":"before"','"phase":"after"',1),
  'address':valid.replace('"address":"0xe9002000"','"address":"0xe9002004"',1),
  'duplicatekey':valid.replace('"phase":"before"','"phase":"before","phase":"before"',1),
  'boolword':valid.replace('"value":"0x55544e41"','"value":true',1),
  'wrong_initial':valid.replace('UTW1_INITIAL_EXT 0x55545731','UTW1_INITIAL_EXT 0x55545730',1),
  'oversize':valid+'x'*262144,
 }
 for name,bad in mutations.items():rejected(lambda:c.parse(bad,'a'*64,origin='synthetic'));record('parser_'+name)
 assert c.parse(valid,'a'*64)['protocol_passed'];record('hardware_origin_requires_sha')
 assert not c.parse(valid,None)['protocol_passed'];assert not c.parse(valid,'bad')['protocol_passed']
 class IO:
  def __init__(self,fault):self.events=[];self.fault=fault;self.save=lambda:None
  def observe(self,name,code,marker):
   self.events.append(name)
   if self.fault==name:raise RuntimeError(name)
   return (valid.replace('UTW1_READS_DONE','NO_DONE') if self.fault=='parse' else valid) if name=='candidate_utw1_capture' else marker
  def program(self,name,path,digest):
   assert (name,path,digest) in (('candidate_utw1',c.ROOT/CANDIDATE['path'],CANDIDATE['bitstream_sha256']),('restore_r19',c.R19,c.R19_SHA))
   self.events.append(name)
   if self.fault==name:raise RuntimeError(name)
 for fault in ('none','r19_initial_guard','candidate_utw1','candidate_utw1_capture','restore_r19','restored_guard','parse','save'):
  io=IO(fault);report={}
  def save():
   if fault=='save' and report.get('observations_collected'):raise OSError('log failure')
  try:c.execute(io,report,save,c.code(),CANDIDATE)
  except (RuntimeError,OSError):assert fault!='none'
  else:assert fault=='none'
  assert io.events.count('restore_r19')==(0 if fault=='r19_initial_guard' else 1),(fault,io.events)
  if fault=='none':assert report['left_startup_verified'] and report['observations_completed']
  if fault=='save':assert report['cleanup_log_errors'] and report['left_startup_verified']
  record('cleanup_'+fault)
 boundaries=['finally_entry','cleanup_definition','cleanup_attempt','cleanup_first_save','cleanup_save','after_cleanup','experiment_error','double_error','restore_error','log_error','cleanup_log_error','error_finally']
 boundaries+=['event:'+x for x in ('r19_initial_guard','candidate_utw1','candidate_utw1_capture','restore_r19','restored_guard')]
 for case,number in [(case,n) for case in boundaries for n in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP)]+[('all_cleanup',signal.SIGINT)]:
  r=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--signal',case,str(int(number)),str(out/'none.log')],capture_output=True,text=True,timeout=10)
  assert r.returncode==0,(case,number,r.stdout[-1500:],r.stderr[-1500:])
  result=json.loads(r.stdout);(out/(case.replace(':','_')+'_'+str(int(number))+'.json')).write_text(json.dumps(result,indent=2)+'\n')
  record('signal_'+case+'_'+str(int(number)))
 tree=ast.parse((HERE/'collector.py').read_text());calls=[n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
 assert calls.count('program')==2 and not any(x in calls for x in ('camera','send'))
 assert re.findall(r'write_memory\s+(0x[0-9a-f]+)',c.code())==['0xe900200c'];record('restricted_actions')
 for option in ('-O','-OO'):
  r=subprocess.run([sys.executable,option,str(HERE/'collector.py'),'--review','nonexistent','--run'],capture_output=True,text=True,timeout=5)
  assert r.returncode!=0 and 'assertions disabled' in r.stderr;record('optimize_'+option)
 # Local preflight is exercised on real pinned files; only readiness review is synthetic.
 # It never calls the hardware branch. The temporary review remains not-ready.
 def result():return dict(passed=True,hardware_access=False,controller_sha256=c.sha(HERE/'collector.py'),tcl_sha256=c.sha(HERE/'capture.tcl'),test_sha256=c.sha(Path(__file__)),cases=records)
 (HERE/'tests_result.json').write_text(json.dumps(result(),indent=2)+'\n')
 reviewpath=out/'review.json';review=c.prepare(reviewpath)
 assert c.local_checks(reviewpath)[0]['hardware_ready'] is False;record('preflight_prepare_only')
 extra=copy.deepcopy(review);extra['proof_files'][str(HERE/'README.md')]=c.sha(HERE/'README.md');reviewpath.write_text(json.dumps(extra))
 assert c.local_checks(reviewpath)[0]['hardware_ready'] is False;record('extra_real_pinned_proof_allowed')
 extra['proof_files'][str(out/'does_not_exist')]='0'*64;reviewpath.write_text(json.dumps(extra));rejected(lambda:c.local_checks(reviewpath));record('extra_fictitious_proof_rejected')
 reviewpath.write_text(json.dumps(review))
 rejected(lambda:c.local_checks(reviewpath,ready=True));record('gate_not_ready')
 # No valid bitstream can reach IO in these tests, even after a reviewed flag is forged.
 def checkreview(changes):
  candidate=copy.deepcopy(review);candidate.update(changes);reviewpath.write_text(json.dumps(candidate)+'\n');rejected(lambda:c.local_checks(reviewpath,ready=True))
 checkreview(dict(hardware_ready=True));record('gate_unknown_candidate')
 checkreview(dict(hardware_ready=True,candidate=CANDIDATE));record('gate_missing_bitstream')
 checkreview(dict(hardware_ready=True,candidate=dict(CANDIDATE,netlist_sha256='b'*64)));record('gate_wrong_netlist')
 checkreview(dict(hardware_ready=True,candidate=dict(CANDIDATE,bitstream_sha256='0'*64)));record('gate_unknown_sha')
 reviewpath.write_text(json.dumps(review)+'\n')
 r=subprocess.run([sys.executable,str(HERE/'collector.py'),'--review',str(reviewpath),'--run'],capture_output=True,text=True,timeout=5)
 assert r.returncode!=0 and 'Root review pending: prepare-only' in r.stderr;record('cli_refuses_before_hardware')
 # Readiness checks on an inert file in our temporary directory; still never enter main/IO.
 inert=out/'inert_not_a_bitstream.txt';inert.write_text('OFFLINE TEST ONLY')
 bit=dict(path=str(inert.relative_to(c.ROOT)),bitstream_sha256=c.sha(inert),netlist_sha256=c.decoder.NET_SHA)
 checkreview(dict(hardware_ready=True,candidate=bit));record('gate_missing_timing_review')
 audit=out/'inert_timing.json';audit.write_text(json.dumps(dict(reviewer='root',decision='diagnostic_trial_allowed',bitstream_sha256=bit['bitstream_sha256'],input_netlist_sha256=c.decoder.NET_SHA)))
 auditbinding=dict(path=str(audit.relative_to(c.ROOT)),sha256=c.sha(audit),reviewed=True)
 ok=copy.deepcopy(review);ok.update(hardware_ready=True,candidate=bit,timing_audit=auditbinding);reviewpath.write_text(json.dumps(ok))
 assert c.local_checks(reviewpath,ready=True)[0]['candidate']==bit;record('gate_complete_binding_only_no_launch')
 for key,val in (('reviewer','other'),('decision','pending'),('bitstream_sha256','0'*64),('input_netlist_sha256','b'*64)):
  a=json.loads(audit.read_text());a[key]=val;audit.write_text(json.dumps(a));binding=dict(auditbinding,sha256=c.sha(audit))
  checkreview(dict(hardware_ready=True,candidate=bit,timing_audit=binding));record('gate_audit_'+key)
  audit.write_text(json.dumps(dict(reviewer='root',decision='diagnostic_trial_allowed',bitstream_sha256=bit['bitstream_sha256'],input_netlist_sha256=c.decoder.NET_SHA)))
 # Never leave a ready-looking synthetic review on disk after the tests.
 reviewpath.write_text(json.dumps(review,indent=2)+'\n')
 proof=result();(HERE/'tests_result.json').write_text(json.dumps(proof,indent=2)+'\n');(out/'result.json').write_text(json.dumps(proof,indent=2)+'\n')
 print(json.dumps(dict(passed=True,hardware_access=False,cases=len(records),out=str(out))))
if __name__=='__main__':main()
