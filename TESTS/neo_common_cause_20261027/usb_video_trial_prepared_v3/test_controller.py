"""Offline restoration state-machine checks; all IO mocked."""
from pathlib import Path
import json,hashlib,sys
from unittest.mock import patch
import probe_usb_video as ctl
HERE=Path(__file__).parent
class IO:
 def __init__(self,r,fail,journal):self.r=r;self.events=[];self.fail=fail;self.journal=journal;self.current='';self.save=self.write_report
 def write_report(self):
  if self.journal and self.current==self.journal[0]:raise self.journal[1]('injected journal failure')
 def event(self,name):
  self.current=name;self.events.append(name)
  if name in self.fail:raise RuntimeError('injected '+name)
 def observe(self,name,code,marker):self.event(name);return marker
 def camera(self,name):self.event(name);self.save()
 def program(self,name,path,digest):
  self.event(name);self.save();self.r['last_programmed_sha256']=digest;self.r['left_startup_verified']=False;self.save()
def case(name,fail=(),journal=None,expected_error=False,expect_restore=True,expect_verified=True):
 r={'candidate_sha256':'candidate','left_startup_verified':False};io=IO(r,set(fail),journal);error=None
 with patch.object(ctl.signal,'signal'):
  try:ctl.execute(io,r,io.write_report,Path('candidate.fs'),'code')
  except BaseException as e:error=repr(e)
 count=io.events.count('restore_r19')
 assert count==(1 if expect_restore else 0),(name,io.events)
 assert bool(error)==expected_error,(name,error)
 assert bool(r.get('left_startup_verified'))==expect_verified,(name,r)
 if expect_verified:assert r['last_programmed_sha256']==ctl.base.prior.t.R19_SHA
 return {'name':name,'passed':True,'events':io.events,'error':error,'report':r}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 if sys.flags.optimize:raise SystemExit('assertions disabled: refusing to run')
 cases=[case('success'),case('initial_guard_fail',('r19_initial_guard',),expected_error=True,expect_restore=False,expect_verified=False),case('baseline_observer_fail',('r19_usb_video',),expected_error=True),case('candidate_program_fail',('program_coupled',),expected_error=True),case('candidate_observer_fail',('coupled_usb_video',),expected_error=True),case('candidate_photo_fail',('coupled_after_observation',),expected_error=True),case('restore_program_fail',('restore_r19',),expected_error=True,expect_verified=False),case('restore_guard_fail',('restored_guard',),expected_error=True,expect_verified=False),case('double_failure_once',('coupled_usb_video','restore_r19'),expected_error=True,expect_verified=False),case('journal_oserror',('coupled_usb_video',),journal=('coupled_usb_video',OSError),expected_error=True),case('journal_interrupt',('coupled_usb_video',),journal=('coupled_usb_video',KeyboardInterrupt),expected_error=True),case('cleanup_journal_oserror',journal=('restore_r19',OSError)),case('cleanup_journal_interrupt',journal=('restore_r19',KeyboardInterrupt))]
 result={'passed':True,'hardware_access':False,'tool_sha256':sha(Path(__file__)),'controller_sha256':sha(HERE/'probe_usb_video.py'),'cases':cases}
 (HERE/'controller_tests_result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'passed':True,'cases':len(cases)}))
if __name__=='__main__':main()
