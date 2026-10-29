#!/usr/bin/env python3
"""Prepared UTW1 collector. No launch until exact bitstream and timing review exist."""
import argparse,fcntl,hashlib,importlib.util,json,re,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
ACT=ROOT/'TESTS/neo_common_cause_20261027/utna_activity_prepared_01'
DEC=HERE.parent/'reply_witness_candidate_01'
BIND=HERE.parent/'offline_binding_r22r1_01'
ANCHOR=ACT/'activity_20261028_000942/result.json'
ANCHOR_SHA='1c39884c0dab5fca3a1217eef887cbd1ac7e8fca21f250174070ce85bfdf342d'
PINS={ACT/'probe_activity.py':'1a20d30efa0f8fc41cc3d50dc5ad5a969ff777c2bef759f3f11b37df5045b3d9',
 DEC/'offline_capture.py':'668f4dc7d14e1491f0bc97a4a14e2ee7e589eceab450273c6aff8e22b83708ae',
 DEC/'CONTRACT.md':'5a7e0020e33e2a5af25e13c9d6cb8aaf49b3925a37a53e72cafe36bb6154e6ed',
 BIND/'offline_capture.py':'bd04d5087a5907ca2e306e390bdc1f497db100b9d7cb2f48e4fe567b40b60e65',
 BIND/'decoder_bound.py':'a9273f681cf4d34443edd6e507f00551abb8cd062078974a5773b29617279802',
 BIND/'binding.json':'338cac2441e5c7e05bb6b1e1843c1bdc27ce5682eebf50b5c0a6c52d6cea164c'}
SEQUENCE=(('ARM',1,1),('DISARM',6,2),('STOPPED',2,3),('STABLE',2,4))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def need(ok,message):
 if not ok:raise RuntimeError(message)
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
for _p,_h in PINS.items():need(sha(_p)==_h,'Changed pinned dependency '+str(_p))
activity=module('utw_activity_parent',ACT/'probe_activity.py')
decoder=module('utw_strict_decoder',BIND/'offline_capture.py')
prior=activity.prior;StopRequest=activity.StopRequest;R19=activity.R19;R19_SHA=activity.R19_SHA

def code():return prior.base.prior.check_code(0)+(HERE/'capture_body.tcl').read_text()
def parse(raw,bitstream_sha256,origin='hardware_capture'):
 need(type(raw) is str and len(raw.encode())<=262144,'Capture log too large')
 rawlines=raw.splitlines();need(rawlines.count('WARM_CHECK_0')==1 and rawlines.index('WARM_CHECK_0')<next((i for i,s in enumerate(rawlines) if s.startswith('UTW1_')),len(rawlines)),'Parked CPU/GPU guard missing or misplaced')
 lines=[s.rstrip('\r') for s in raw.splitlines() if s.startswith('UTW1_')];at=0
 def take():
  nonlocal at
  need(at<len(lines),'Partial acquisition');line=lines[at];at+=1;return line
 def control(label,n):
  line=take();prefix='UTW1_CONTROL '+label+' ';need(line.startswith(prefix),'Control ordering '+label)
  words=[int(s,0) for s in line[len(prefix):].split()];need(words==[decoder.ID,0,n],'Control value '+label)
 control('INITIAL',0)
 line=take();prefix='UTW1_INITIAL_EXT ';need(line.startswith(prefix),'Initial witness missing')
 initial=[int(x,0) for x in line[len(prefix):].split()];need(initial==[0x55545731,0x10001]+[0]*14,'Initial witness not reset')
 captures=[]
 for label,command,n in SEQUENCE:
  control(label+'_PRE',n-1);need(take()==f'UTW1_WRITE {label} {command} {n}','Write ordering');control(label+'_ACK',n)
  log=[]
  for phase in decoder.PHASES:
   for offset in decoder.EXPECTED_OFFSETS[phase]:
    line=take();prefix='UTW1_READ '+label+' ';need(line.startswith(prefix),'Unexpected image label/order')
    item=decoder.strict_json(line[len(prefix):]);need(type(item) is dict,'Invalid read record');need(item.get('phase')==phase and decoder.u32(item.get('address'))==decoder.BASE+offset,'Unexpected phase/address')
    log.append(line[len(prefix):])
  need(take()=='UTW1_CAPTURE_COMPLETE '+label,'Missing completion')
  packet=decoder.collect_jsonl('\n'.join(log),expected_sequence=n,expected_command=command,origin=origin,bitstream_sha256=bitstream_sha256 if origin=='hardware_capture' else None)
  result=decoder.decode(packet,trusted_bitstream_sha256=bitstream_sha256 if origin=='hardware_capture' else None)
  captures.append(dict(label=label,packet=packet,decode=result,jsonl='\n'.join(log)+'\n'))
 need(take()=='UTW1_READS_DONE' and at==len(lines),'Missing/extra acquisition record')
 # Activity relation comes from the existing ARM/DISARM/SNAPSHOT contract.
 banks=[[decoder.u32(row['value']) for row in c['packet']['reads']['image_a'][:32]] for c in captures]
 a,d,s,h=banks;errors=[]
 if a[3]!=0 or a[31]&0x400:errors.append('ARM must observe fresh pre-clear state')
 if d[3]==0 or not d[31]&0x400:errors.append('DISARM lacks armed activity')
 if s[31]&0x400 or h[31]&0x400:errors.append('Observer did not remain disarmed')
 if s[3]!=(d[3]+1)&0xffffffff:errors.append('DISARM final tick relation')
 if h[3]!=s[3]:errors.append('Stopped ticks changed')
 return dict(capture_complete=True,captures=captures,activity_errors=errors,
  coherent=all(c['decode']['coherent'] for c in captures),protocol_passed=not errors and all(c['decode']['passed'] for c in captures),
  qualification_status='FAIL',hardware_qualified=False,
  limits=['Loaded identity is externally declared, not physically attested.','Alias CC/D4 shares storage.','Valid version1 does not identify a cause; version0 remains FAIL.'])

def dependencies():
 return sorted(set(activity.dependencies()+list(PINS)+[ROOT/name for name in decoder.FILES]+[ANCHOR,Path(__file__),HERE/'capture_body.tcl',HERE/'capture.tcl',HERE/'test_collector.py',HERE/'tests_result.json']))
def local_checks(path,ready=False):
 decoder.provenance()
 review=decoder.strict_json(path.read_text())
 need(review['board']=='neo' and review['scope']=='UTW1_candidate_collect_restore_R19','Wrong scope')
 need(review['qualification_status']=='FAIL','Diagnostic must not qualify FPGA')
 need(review['controller_sha256']==sha(Path(__file__)),'Controller changed')
 need(review['anchor_sha256']==ANCHOR_SHA==sha(ANCHOR),'Anchor changed')
 anchor=json.loads(ANCHOR.read_text());need(anchor.get('finished_unix') and anchor['left_startup_verified'] and not anchor['signals_received'] and anchor['restore_attempted'] and not anchor.get('restore_error'),'Invalid restored anchor')
 need(anchor['last_programmed_sha256']==anchor['r19_sha256']==review['r19_sha256']==R19_SHA==sha(R19),'Wrong R19')
 for name,digest in anchor['files'].items():need(sha(ANCHOR.parent/name)==digest,'Anchor evidence changed '+name)
 need('RESTORED_UTNA_FRESH' in (ANCHOR.parent/'restored_guard.log').read_text(),'Restored guard missing')
 need(set(str(p.resolve()) for p in dependencies())<=set(review['proof_files']),'Missing dependency')
 for name,digest in review['proof_files'].items():need(sha(Path(name))==digest,'Changed dependency '+name)
 need((HERE/'capture.tcl').read_text()==code(),'Changed Tcl')
 need(re.findall(r'write_memory\s+(0x[0-9a-f]+)',code())==['0xe900200c'],'Unexpected write')
 need(re.findall(r'^utw_capture (\w+) (\d+) (\d+)$',code(),re.M)==[(a,str(b),str(c)) for a,b,c in SEQUENCE],'Wrong sequence')
 proof=json.loads((HERE/'tests_result.json').read_text());need(proof['passed'] and not proof['hardware_access'] and proof['controller_sha256']==sha(Path(__file__)) and proof['test_sha256']==sha(HERE/'test_collector.py') and proof['tcl_sha256']==sha(HERE/'capture.tcl'),'Tests stale/missing')
 if ready:
  need(review['hardware_ready'] is True,'Root review pending: prepare-only')
  candidate=review['candidate'];need(type(candidate) is dict,'Candidate bitstream SHA not yet reviewed')
  need(candidate['netlist_sha256']==decoder.NET_SHA,'Wrong witness input netlist')
  digest=candidate['bitstream_sha256'];need(type(digest) is str and re.fullmatch('[0-9a-f]{64}',digest) and digest!='0'*64,'Unknown bitstream SHA')
  original=ROOT/candidate['path'];p=original.resolve();need(p.is_relative_to(ROOT) and p.is_file() and not original.is_symlink() and sha(p)==digest,'Candidate file changed')
  audit=review['timing_audit'];need(type(audit) is dict and audit['reviewed'] is True,'Timing audit not reviewed')
  original=ROOT/audit['path'];ap=original.resolve();need(ap.is_relative_to(ROOT) and ap.is_file() and not original.is_symlink() and sha(ap)==audit['sha256'],'Timing audit changed')
  a=json.loads(ap.read_text());need(a.get('reviewer')=='root' and a.get('decision')=='diagnostic_trial_allowed' and a.get('bitstream_sha256')==digest and a.get('input_netlist_sha256')==decoder.NET_SHA,'Timing review not tied to exact bitstream/netlist')
 return review,code()

def execute(io,report,save,text,candidate,stop=None):
 stop=stop if stop is not None else StopRequest();report['signals_received']=stop.received;touched=False
 try:
  stop.checkpoint();io.observe('r19_initial_guard',prior.restoration_guard(),'RESTORED_UTNA_FRESH');stop.checkpoint();report['baseline_verified']=True;save();stop.checkpoint()
  touched=True;stop.checkpoint()
  io.program('candidate_utw1',ROOT/candidate['path'],candidate['bitstream_sha256']);stop.checkpoint()
  raw=io.observe('candidate_utw1_capture',text,'UTW1_READS_DONE');stop.checkpoint()
  report['observation']=parse(raw,candidate['bitstream_sha256']);report['observations_collected']=True;save()
  need(report['observation']['protocol_passed'],'UTW1 diagnostic contract failed; retain captured evidence')
  report['observations_completed']=True;save();stop.checkpoint()
 except BaseException as exc:
  report['error']=repr(exc)
  try:save()
  except BaseException as log_error:report.setdefault('error_log_errors',[]).append(repr(log_error))
  raise
 finally:
  if touched:
   def cleanup_save():
    try:save()
    except BaseException as exc:report.setdefault('cleanup_log_errors',[]).append(repr(exc))
   if hasattr(io,'save'):io.save=cleanup_save
   report['restore_attempted']=True;cleanup_save()
   try:
    io.program('restore_r19',R19,R19_SHA);io.observe('restored_guard',prior.restoration_guard(),'RESTORED_UTNA_FRESH')
    report.update(left_startup_verified=True,left_state='Exact R19 restored, CPU parked, fresh GPU/NCP/UTNA, internal bars');cleanup_save()
   except BaseException as exc:report['restore_error']=repr(exc);cleanup_save();raise
 try:stop.checkpoint()
 except KeyboardInterrupt as exc:
  report['error']=repr(exc)
  try:save()
  except BaseException as log_error:report.setdefault('error_log_errors',[]).append(repr(log_error))
  raise

def prepare(path):
 need(not path.exists(),'Review already exists');(HERE/'capture.tcl').write_text(code())
 review=dict(board='neo',scope='UTW1_candidate_collect_restore_R19',qualification_status='FAIL',hardware_ready=False,
  controller_sha256=sha(Path(__file__)),anchor_sha256=ANCHOR_SHA,r19_sha256=R19_SHA,candidate=None,timing_audit=None,
  proof_files={str(p.resolve()):sha(p) for p in dependencies()},required_before_launch=['Root supplies exact bitstream SHA and input netlist binding.','Root writes a separately hashed timing audit with decision diagnostic_trial_allowed.','Root reviews all proof files and sets hardware_ready in a new review.'])
 path.write_text(json.dumps(review,indent=2)+'\n');return review

def main():
 if sys.flags.optimize:raise SystemExit('assertions disabled: refusing to run')
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--review',type=Path,required=True);mode=ap.add_mutually_exclusive_group(required=True);mode.add_argument('--prepare',action='store_true');mode.add_argument('--check-only',action='store_true');mode.add_argument('--run',action='store_true');args=ap.parse_args()
 path=args.review.resolve();need(path.is_relative_to(HERE),'Review must be in prepared folder')
 if args.prepare:prepare(path);print(json.dumps(dict(prepared=True,hardware_ready=False,hardware_access=False)));return
 review,text=local_checks(path,ready=args.run)
 if args.check_only:print(json.dumps(dict(preflight_passed=True,hardware_ready=review['hardware_ready'],hardware_access=False)));return
 stop=StopRequest();stop.install();stop.checkpoint()
 with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  ps=subprocess.run(['ps','-C','openocd','-C','openFPGALoader','-C','gao_sh','-C','gao_analyzer','-C','jtagserver','-o','pid=,comm='],capture_output=True,text=True,timeout=5)
  need(ps.returncode==1 and not ps.stdout.strip(),'Another diagnostic tool is active');stop.checkpoint()
  identity=prior.base.prior.hw.usb_identity();activity.ro.check_identity(identity);stop.checkpoint();review,text=local_checks(path,ready=True)
  out=HERE/('capture_'+time.strftime('%Y%m%d_%H%M%S'));out.mkdir(exist_ok=False)
  report=dict(board='neo',qualification_status='FAIL',hardware_review_sha256=sha(path),candidate=review['candidate'],r19_sha256=R19_SHA,initial_reference_declared_sha256=R19_SHA,last_programmed_sha256=None,left_startup_verified=False,observations_completed=False,identity=identity,started_unix=time.time(),observer_commands=[1,6,2,2],observer_write_address=0xe900200c)
  def save():(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
  save();(out/'controller_used.py').write_bytes(Path(__file__).read_bytes())
  try:execute(prior.base.prior.IO(out,report,save),report,save,text,review['candidate'],stop)
  finally:
   report['finished_unix']=time.time();report['files']={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='result.json'};save();print(json.dumps(dict(output=str(out),qualification_status='FAIL',left_startup_verified=report['left_startup_verified'])))
if __name__=='__main__':main()
