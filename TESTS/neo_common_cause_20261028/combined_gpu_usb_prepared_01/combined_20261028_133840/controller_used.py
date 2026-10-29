#!/usr/bin/env python3
"""Prepared combined R22r1 witness/GPU/video/USB diagnostic; root launches after review."""
import argparse,fcntl,hashlib,importlib.util,inspect,json,re,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
PARENT=HERE.parent/'utw1_collector_prepared_01'
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
parent=module('combined_parent_collector',PARENT/'collector.py')
activity,prior,StopRequest,R19,R19_SHA,decoder=(parent.activity,parent.prior,parent.StopRequest,parent.R19,parent.R19_SHA,parent.decoder)
sha,need=parent.sha,parent.need
ANCHOR=PARENT/'capture_20261028_124454/result.json'
ANCHOR_SHA='bb05c3936dcdc82e8cb13e8cf7620bdb4d0c9fb65027a553b4e85e1a590d9720'
PARENT_SHA='61439428fd262ed24165bcbb79c1acc6dc07e2527999dbba6d7c711e31952ae2'
CANDIDATE=dict(path='tang/impl/console_neo_n56r22r1_utw1_reports/impl/pnr/console_neo.fs',bitstream_sha256='55601256120915adbb08279c0b6bd42caabf8deff261bf87b8a7b8d8cbf9c8aa',netlist_sha256=decoder.NET_SHA)
SPLIT='\n# COMBINED_SPLIT_NEXT_OPENOCD_SESSION\n'

def parts():
 gpu=(HERE/'gpu_video.tcl').read_text();defs=gpu.split('foreach label {T0 T100 T200 T1200}')[0]
 u=(PARENT/'capture_body.tcl').read_text();udefs=u.split('utw_idle INITIAL 0')[0]
 begin=prior.base.prior.check_code(0)+gpu+u.split('utw_capture ARM 1 1\n')[0]+'''utw_capture ARM 1 1
set g [cv_snapshot 0xe9005000 GPU_BEFORE]
set s [cv_snapshot 0xe9006000 SCAN_BEFORE]
if {$g && $s} {cv_matrix} else {echo "COMBINED_GPU_FAIL MATRIX skipped_snapshot_failure"}
cv_snapshot 0xe9005000 GPU_AFTER_MATRIX
cv_video AFTER_MATRIX
echo COMBINED_BEGIN_DONE
'''
 finish=prior.base.prior.t.BASE_GUARD+defs+udefs+'''utw_idle HOST_RETURN 1
utw_capture DISARM 6 2
sleep 100
utw_capture STOPPED 2 3
sleep 100
utw_capture STABLE 2 4
echo UTW1_READS_DONE
cv_snapshot 0xe9005000 GPU_FINAL
cv_snapshot 0xe9006000 SCAN_FINAL
cv_video FINAL
echo COMBINED_DONE
'''
 return begin,finish

def code():return SPLIT.join(parts())

def parse(raw,bitstream_sha256,origin='hardware_capture'):
 # HOST_RETURN is an additional strict continuity guard between OpenOCD sessions.
 matches=re.findall(r'^UTW1_CONTROL HOST_RETURN (.+)$',raw,re.M)
 need(len(matches)==1 and [int(x,0) for x in matches[0].split()]==[decoder.ID,0,1],'Observer continuity across host sampling')
 clean=re.sub(r'^UTW1_CONTROL HOST_RETURN .+\n','',raw,flags=re.M)
 result=parent.parse(clean,bitstream_sha256,origin);errors=[]
 def rows(tag,count):
  found=re.findall(r'^'+tag+r' (\w+) (.+)$',raw,re.M);out={}
  for label,data in found:
   need(label not in out,'Duplicate '+tag+' '+label);v=[int(x,0) for x in data.split()]
   need(len(v)==count and all(0<=x<=0xffffffff for x in v),'Malformed '+tag);out[label]=v
  return out
 scan,gpu,ncp=rows('COMBINED_SCAN',30),rows('COMBINED_GPU',26),rows('COMBINED_NCP',7)
 labels=['T0','T100','T200','T1200','AFTER_MATRIX','FINAL']
 need(list(scan)==list(gpu)==list(ncp)==labels,'Incomplete video sampling')
 for label in labels:
  if scan[label][0]!=0x47505531 or scan[label][28]!=0x02d00500 or gpu[label][0]!=0x424c5432:errors.append(label+' wrong GPU/video identity')
  if scan[label][2]!=0:errors.append(label+' framebuffer enabled unexpectedly')
  if ncp[label][0]!=0x4e435031 or ncp[label][2:4]!=[0,0]:errors.append(label+' NCP changed')
 if (scan['T1200'][6]-scan['T0'][6])&0xffffffff==0:errors.append('No video frame progression')
 snapshots=rows('COMBINED_SNAPSHOT',17)
 for label in ['GPU_BEFORE','SCAN_BEFORE','GPU_AFTER_MATRIX','GPU_FINAL','SCAN_FINAL']:
  if label not in snapshots:errors.append('Missing coherent snapshot '+label)
  elif snapshots[label][0]!=0x4e474442 or snapshots[label][1]!=6:errors.append('Wrong snapshot '+label)
 failures=re.findall(r'^COMBINED_GPU_FAIL (.+)$',raw,re.M);errors.extend(failures)
 matrix={}
 for label in ('BEFORE','AFTER'):
  found=re.findall(r'^COMBINED_MATRIX_'+label+r' (.+)$',raw,re.M)
  if len(found)!=1:errors.append('Missing matrix '+label);continue
  values=[int(x,0) for x in found[0].split()];need(len(values)==5,'Bad matrix record');matrix[label]=values
 if len(matrix)==2:
  b,a=matrix['BEFORE'],matrix['AFTER']
  if a[:3]!=[(b[0]+8)&0xffffffff,(b[1]+8)&0xffffffff,(b[2]+1)&65535] or a[3:]!=b[3:]:errors.append('Matrix counters failed')
 need(raw.splitlines().count('COMBINED_BEGIN_DONE')==1 and raw.splitlines().count('COMBINED_DONE')==1,'Missing phase completion')
 hostlines=re.findall(r'^COMBINED_HOST (.+)$',raw,re.M);need(len(hostlines)==1,'Host sample missing')
 host=decoder.strict_json(hostlines[0]);need(type(host) is dict and 'devices' in host and 'usb_io_attempted' in host,'Bad host sample')
 if host.get('diag_status') in ('TRANSFER_FAILED','AMBIGUOUS'):errors.append('Host USB '+host['diag_status'])
 result.update(combined_errors=errors,video_scan=scan,gpu_registers=gpu,ncp=ncp,snapshots=snapshots,matrix=matrix,host_usb=host,
  video_frame_delta_mod32=(scan['T1200'][6]-scan['T0'][6])&0xffffffff,
  usb_hs_observed=host.get('hs_present') is True,USB_functional_qualified=False,GPU_rendering_qualified=False)
 result['protocol_passed']=result['protocol_passed'] and not errors
 return result

class CombinedIO(prior.base.prior.IO):
 def __init__(self,out,report,save,stop,allowed_usb_path=None):
  super().__init__(out,report,save);self.stop=stop;self.allowed_usb_path=allowed_usb_path
 def observe(self,name,text,marker):
  if name!='candidate_utw1_capture':return super().observe(name,text,marker)
  need(text==code(),'Combined script mismatch');begin,finish=parts();self.stop.checkpoint()
  first=super().observe('combined_begin',begin,'COMBINED_BEGIN_DONE');self.stop.checkpoint()
  log=self.out/'host_usb.log';cmd=[sys.executable,str(HERE/'host_usb.py')]
  if self.allowed_usb_path is not None:cmd+=['--allowed-path',self.allowed_usb_path]
  prior.base.prior.hw.run_child(cmd,log,5);self.stop.checkpoint()
  host=decoder.strict_json(log.read_text());self.r['host_usb']=host;self.save();self.stop.checkpoint()
  last=super().observe('combined_finish',finish,'COMBINED_DONE');self.stop.checkpoint()
  raw=first+'\nCOMBINED_HOST '+json.dumps(host)+'\n'+last
  (self.out/'candidate_utw1_capture.log').write_text(raw)
  return raw

# Execute is copied exactly from the already tested collector; only parse resolves
# to this module's stricter combined decoder. Its rollback/checkpoints are unchanged.
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

def dependencies():
 return sorted(set(parent.dependencies()+[Path(__file__),HERE/'gpu_video.tcl',HERE/'host_usb.py',HERE/'combined.tcl',
  HERE/'test_combined.py',HERE/'test_signals_combined.py',HERE/'tests_result.json',HERE/'signals_result.json',ANCHOR,PARENT/'collector.py']))

def local_checks(path,ready=False):
 decoder.provenance();r=decoder.strict_json(path.read_text());need(r['scope']=='R22r1_combined_diag_restore_R19' and r['board']=='neo','Wrong scope')
 need(r['qualification_status']=='FAIL' and r['controller_sha256']==sha(Path(__file__)),'Wrong controller/qualification')
 need(not ready or r['hardware_ready'] is True,'Root review pending')
 need(sha(PARENT/'collector.py')==PARENT_SHA,'Parent controller changed')
 need(sha(ANCHOR)==r['anchor_sha256']==ANCHOR_SHA,'Anchor changed');a=json.loads(ANCHOR.read_text())
 need(a.get('finished_unix') and a['left_startup_verified'] and a['last_programmed_sha256']==R19_SHA and not a.get('restore_error') and not a['signals_received'],'Anchor not fresh/restored')
 for name,digest in a['files'].items():need(sha(ANCHOR.parent/name)==digest,'Anchor evidence changed')
 need(sha(R19)==R19_SHA and r['candidate']==CANDIDATE and sha(ROOT/CANDIDATE['path'])==CANDIDATE['bitstream_sha256'],'Build identity changed')
 need((HERE/'combined.tcl').read_text()==code(),'Prepared scripts changed')
 need(set(re.findall(r'write_memory\s+(0x[0-9a-f]+)',code()))=={'0xe900200c','0xe9005004','0xe9006004','0xe9001010'},'Unexpected write address')
 commands='\n'.join(line for line in code().splitlines() if not line.lstrip().startswith('#'))
 need(not re.search(r'\b(load_image|dump_image|mww|mwh|mwb|resume|irscan|drscan)\b',commands),'Forbidden operation')
 need('foreach word {0x1f000000 0 65536 0 0 0 0 0}' in code(),'Matrix command changed')
 need(r.get('usb_ep0_allowed_path') is None or re.fullmatch(r'/sys/bus/usb/devices/[0-9]+-[0-9]+(?:\.[0-9]+)*',r['usb_ep0_allowed_path']),'Unsafe USB binding')
 need(set(str(x.resolve()) for x in dependencies())<=set(r['proof_files']),'Missing proof')
 for name,digest in r['proof_files'].items():need(sha(Path(name))==digest,'Dependency changed '+name)
 for name in ('tests_result.json','signals_result.json'):
  proof=json.loads((HERE/name).read_text());need(proof['passed'] and not proof['hardware_access'] and proof['controller_sha256']==sha(Path(__file__)),'Tests incomplete/stale')
  for item,digest in proof.get('inputs',{}).items():need(sha(Path(item))==digest,'Test input stale '+item)
 audit=r['timing_audit'];ap=ROOT/audit['path'];need(audit['reviewed'] and sha(ap)==audit['sha256'],'Timing review changed')
 t=json.loads(ap.read_text());need(t['reviewer']=='root' and t['decision']=='diagnostic_trial_allowed' and t['bitstream_sha256']==CANDIDATE['bitstream_sha256'],'Timing approval wrong')
 return r,code()

def prepare(path):
 need(not path.exists(),'Review exists');(HERE/'combined.tcl').write_text(code())
 (HERE/'begin.tcl').write_text(parts()[0]);(HERE/'finish.tcl').write_text(parts()[1])
 parentreview=json.loads((PARENT/'root_hardware_review_r22r1_01.json').read_text())
 r=dict(board='neo',scope='R22r1_combined_diag_restore_R19',qualification_status='FAIL',hardware_ready=False,
  controller_sha256=sha(Path(__file__)),anchor_sha256=ANCHOR_SHA,candidate=CANDIDATE,r19_sha256=R19_SHA,
  timing_audit=parentreview['timing_audit'],usb_ep0_allowed_path=None,
  proof_files={str(x.resolve()):sha(x) for x in dependencies()},
  allowed_writes={'0xe900200c':'1,6,2,2 observer commands','0xe9005004':'snapshot request1','0xe9006004':'snapshot request1','0xe9001010':'one matrix_row0 eight-word packet'},
  no_DDR_writes=True,no_Linux=True,no_USB_port_reset=True,required_before_hardware=['Root reviews exact controller/proofs and USB binding (None sends no USB traffic).'])
 path.write_text(json.dumps(r,indent=2)+'\n')

def main():
 if sys.flags.optimize:raise SystemExit('assertions disabled: refusing')
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--review',type=Path,required=True);g=ap.add_mutually_exclusive_group(required=True)
 g.add_argument('--prepare',action='store_true');g.add_argument('--check-only',action='store_true');g.add_argument('--run',action='store_true');args=ap.parse_args()
 path=args.review.resolve();need(path.is_relative_to(HERE),'Review outside prepared folder')
 if args.prepare:prepare(path);print('PREPARED_NO_HARDWARE');return
 review,text=local_checks(path,ready=args.run)
 if args.check_only:print(json.dumps(dict(preflight_passed=True,hardware_access=False,hardware_ready=review['hardware_ready'])));return
 stop=StopRequest();stop.install();stop.checkpoint()
 with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  ps=subprocess.run(['ps','-C','openocd','-C','openFPGALoader','-C','gao_sh','-C','gao_analyzer','-C','jtagserver','-o','pid=,comm='],capture_output=True,text=True,timeout=5)
  need(ps.returncode==1 and not ps.stdout.strip(),'Other diagnostic active');stop.checkpoint()
  identity=prior.base.prior.hw.usb_identity();activity.ro.check_identity(identity);stop.checkpoint();review,text=local_checks(path,ready=True)
  out=HERE/('combined_'+time.strftime('%Y%m%d_%H%M%S'));out.mkdir(exist_ok=False)
  report=dict(board='neo',qualification_status='FAIL',hardware_review_sha256=sha(path),candidate=review['candidate'],r19_sha256=R19_SHA,
   last_programmed_sha256=None,left_startup_verified=False,observations_completed=False,identity=identity,started_unix=time.time(),DDR_written=False,Linux_loaded=False,GPU_command='matrix_row0 register-only',USB_port_reset=False)
  def save():(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
  save();(out/'controller_used.py').write_bytes(Path(__file__).read_bytes())
  try:execute(CombinedIO(out,report,save,stop,review['usb_ep0_allowed_path']),report,save,text,review['candidate'],stop)
  finally:
   report['finished_unix']=time.time();report['files']={x.name:sha(x) for x in out.iterdir() if x.is_file() and x.name!='result.json'};save();print(json.dumps(dict(output=str(out),left_startup_verified=report['left_startup_verified'],qualification_status='FAIL')))
if __name__=='__main__':main()
