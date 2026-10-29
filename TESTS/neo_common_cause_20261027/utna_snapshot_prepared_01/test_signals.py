"""Actual POSIX signals at snapshot/rollback boundaries; fake board IO only."""
import inspect,json,os,signal,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
SIGNALS=(signal.SIGINT,signal.SIGTERM,signal.SIGHUP)

def child(case,number):
 import probe_snapshot as c
 stop=c.StopRequest();stop.install();events=[];report={};fired=False;delivered=[]
 valid=(HERE/'tests/none.log').read_text()
 def deliver():
  nonlocal fired
  if fired:return
  fired=True
  for sig in (SIGNALS if case=='all_cleanup' else (number,)):
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
   if case=='late_log_error' and report.get('restore_attempted') and 'error' in report:raise OSError('late log failure')
  def event(self,name):
   self.current=name;events.append(name)
   if case=='event:'+name:deliver()
   if case in ('all_cleanup','restore_error') and name=='restore_r19':deliver()
   if case=='late_log_error' and name=='restored_guard':deliver()
   if name=='r19_snapshot' and case in ('experiment_error','double_error','log_error','error_finally'):raise RuntimeError('primary failure')
   if name=='restore_r19' and case in ('double_error','restore_error'):raise RuntimeError('restore failure')
  def observe(self,name,code,marker):self.event(name);return valid if name=='r19_snapshot' else marker
  def program(self,name,path,digest):
   assert name=='restore_r19' and path==c.R19 and digest==c.R19_SHA
   self.event(name);self.save();report['last_programmed_sha256']=digest;self.save()
 lines,start=inspect.getsourcelines(c.execute)
 tokens={'finally_entry':'if touched:','cleanup_definition':'def cleanup_save():',
         'cleanup_attempt':"report['restore_attempted']=True",'cleanup_first_save':'cleanup_save()',
         'experiment_error':"report['error']=repr(exc)",'double_error':"report['error']=repr(exc)",
         'error_finally':'if touched:'}
 mapping={name:start+next(i for i,line in enumerate(lines) if line.strip()==token) for name,token in tokens.items()}
 mapping['after_cleanup']=start+next(i for i,line in enumerate(lines) if line.strip()=='try:stop.checkpoint()')
 def trace(frame,event,arg):
  if not fired and frame.f_code is c.execute.__code__ and event=='line' and frame.f_lineno==mapping.get(case):deliver()
  return trace
 io=IO();error=None;context=None;sys.settrace(trace)
 try:c.execute(io,report,io.write_report,c.code(),stop)
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
 if case in ('log_error','late_log_error'):assert report['error_log_errors']
 if case=='cleanup_log_error':assert report['cleanup_log_errors']
 print(json.dumps(dict(passed=True,case=case,signal=int(number),events=events,delivered=delivered,error=error,context=context,report=report,hardware_access=False)))

def main():
 if sys.flags.optimize:raise SystemExit('assertions disabled: refusing to run')
 if len(sys.argv)==4 and sys.argv[1]=='--child':child(sys.argv[2],int(sys.argv[3]));return
 import probe_snapshot as c
 boundaries=['finally_entry','cleanup_definition','cleanup_attempt','cleanup_first_save','cleanup_save','after_cleanup','experiment_error','double_error','restore_error','log_error','cleanup_log_error','late_log_error','error_finally']
 boundaries+=['event:'+x for x in ('r19_initial_guard','r19_snapshot','restore_r19','restored_guard')]
 records=[]
 for case,number in [(case,n) for case in boundaries for n in SIGNALS]+[('all_cleanup',signal.SIGINT)]:
  r=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--child',case,str(int(number))],capture_output=True,text=True,timeout=10)
  assert r.returncode==0,(case,number,r.stdout,r.stderr)
  records.append(json.loads(r.stdout))
 (HERE/'signals_result.json').write_text(json.dumps(dict(passed=True,hardware_access=False,controller_sha256=c.sha(HERE/'probe_snapshot.py'),tool_sha256=c.sha(Path(__file__)),signal_delivery='os.kill self in isolated subprocesses',cases=records),indent=2)+'\n')
 print(json.dumps(dict(passed=True,hardware_access=False,cases=len(records))))
if __name__=='__main__':main()
