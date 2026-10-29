#!/usr/bin/env python3
"""Offline POSIX rollback tests: real execute/CombinedIO, inert transport doubles only."""
import importlib.util,inspect,json,os,re,signal,subprocess,sys,tempfile
from pathlib import Path
import controller as c
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('inherited_signal_tests',c.PARENT/'test_collector.py')
legacy=importlib.util.module_from_spec(spec);sys.modules['collector']=c;spec.loader.exec_module(legacy);legacy.c=c
BOUNDARIES=['finally_entry','cleanup_definition','cleanup_attempt','cleanup_first_save','cleanup_save','after_cleanup','experiment_error','double_error','restore_error','log_error','cleanup_log_error','error_finally']+['event:'+n for n in ('r19_initial_guard','candidate_utw1','candidate_utw1_capture','restore_r19','restored_guard')]
STAGES=['combined_begin_before','combined_begin_after','host_before','host_after','host_save','combined_finish_before','combined_finish_after','merge_write']

def stage_child(case,number,fixture):
 raw=Path(fixture).read_text();before,hostrow,after=re.split(r'^COMBINED_HOST (.+)\n',raw,flags=re.M)
 stop=c.StopRequest();stop.install();events=[];report={};fired=False;delivered=[]
 error=None;real_write=Path.write_text
 def event(name):
  nonlocal fired
  events.append(name)
  if name!=case:return
  fired=True
  if number:
   delivered.append(number);os.kill(os.getpid(),number)
  else:raise RuntimeError('injected '+name)
 base=c.CombinedIO.__bases__[0]
 def program(self,name,path,digest):
  assert (name,path,digest) in [('candidate_utw1',c.ROOT/legacy.CANDIDATE['path'],legacy.CANDIDATE['bitstream_sha256']),('restore_r19',c.R19,c.R19_SHA)]
  event(name);report['last_programmed_sha256']=digest;self.save()
 def observe(self,name,code,marker):
  if name in ('combined_begin','combined_finish'):
   event(name+'_before');value=before if name=='combined_begin' else after;assert marker in value
   event(name+'_after');return value
  assert name in ('r19_initial_guard','restored_guard');event(name);return marker
 def run(cmd,log,seconds):
  assert cmd==[sys.executable,str(HERE/'host_usb.py')] and seconds==5
  event('host_before');real_write(log,hostrow);event('host_after')
 def write(path,*args,**kwargs):
  if path.name=='candidate_utw1_capture.log':event('merge_write')
  return real_write(path,*args,**kwargs)
 def save():
  if report.get('host_usb') and not report.get('restore_attempted'):event('host_save')
 base.program=program;base.observe=observe;c.prior.base.prior.hw.run_child=run;Path.write_text=write
 with tempfile.TemporaryDirectory(prefix='combined-signal-') as directory:
  io=c.CombinedIO(Path(directory),report,save,stop)
  try:c.execute(io,report,save,c.code(),legacy.CANDIDATE,stop)
  except BaseException as exc:error=repr(exc)
 assert fired,(case,events)
 assert events.count('restore_r19')==1 and events[-1]=='restored_guard',(case,events)
 assert report['left_startup_verified'] and report['last_programmed_sha256']==c.R19_SHA
 assert report['signals_received']==delivered
 assert error is not None
 if number:assert 'KeyboardInterrupt' in error,(case,error)
 else:assert error=="RuntimeError('injected "+case+"')",(case,error)
 if case.startswith('combined_begin'):
  assert 'host_before' not in events and 'combined_finish_before' not in events
 if case.startswith('host_'):assert 'combined_finish_before' not in events
 print(json.dumps(dict(passed=True,case=case,signal=number,events=events,error=error,report=report,hardware_access=False)))

def main():
 if sys.flags.optimize:raise SystemExit('assertions required')
 if len(sys.argv)==5:
  kind,case,n,fixture=sys.argv[1:]
  if kind=='--legacy':legacy.signal_child(case,int(n),fixture)
  elif kind=='--stage':stage_child(case,int(n),fixture)
  else:raise ValueError(kind)
  return
 out=Path(sys.argv[1]).resolve();assert out.is_relative_to(HERE);out.mkdir(exist_ok=False)
 fixture=HERE/'tests_local_01/good.log';assert c.parse(fixture.read_text(),'a'*64,origin='synthetic')['protocol_passed']
 assert inspect.getsource(c.execute)==inspect.getsource(c.parent.execute)
 records=[]
 cases=[('--legacy',case,int(n)) for case in BOUNDARIES for n in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP)]+[('--legacy','all_cleanup',int(signal.SIGINT))]
 cases += [('--stage',case,int(n)) for case in STAGES for n in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP,0)]
 for kind,case,n in cases:
  r=subprocess.run([sys.executable,str(Path(__file__).resolve()),kind,case,str(n),str(fixture)],capture_output=True,text=True,timeout=15)
  log=out/(kind[2:]+'_'+case.replace(':','_')+'_'+str(n)+'.json')
  assert r.returncode==0,(kind,case,n,r.stdout[-3000:],r.stderr[-3000:])
  result=json.loads(r.stdout);log.write_text(json.dumps(result,indent=2)+'\n');records.append(dict(kind=kind,case=case,signal=n,passed=True,evidence=log.name,sha256=c.sha(log)))
 result=dict(passed=True,hardware_access=False,controller_sha256=c.sha(HERE/'controller.py'),test_sha256=c.sha(Path(__file__)),inherited_test_sha256=c.sha(c.PARENT/'test_collector.py'),fixture_sha256=c.sha(fixture),inherited_posix_cases=52,combined_posix_cases=24,combined_exception_cases=8,
  scope='Real execute, CombinedIO and strict combined decoder. Only board IO and bounded host subprocess replaced with inert doubles; no hardware. Actual SIGINT/SIGTERM/SIGHUP delivered to child processes.',cases=records)
 (HERE/'signals_result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='cases'}))
if __name__=='__main__':main()
