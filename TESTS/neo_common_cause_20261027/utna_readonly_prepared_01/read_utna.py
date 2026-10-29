#!/usr/bin/env python3
"""Bounded reads of fresh R19 UTNA windows. No MMIO write or programming API."""
import argparse,fcntl,hashlib,json,re,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PRIOR=HERE.parent/'usb_video_trial_prepared_v3'
sys.path.insert(0,str(PRIOR))
import probe_usb_video as prior
ANCHOR=PRIOR/'usb_video_20261027_223943/result.json'
ANCHOR_SHA='8ed6a4a7d0f5e1b0b10301b76c3822846c6b6fec85fa026d181165e9b98bdf10'
ADDRESSES=[0xe9002000,0xe9002004,0xe9002008,0xe9002040,0xe9002044,0xe9002048,0xe9002080,0xe9002084]
ORDERS={'forward':ADDRESSES,'reverse':list(reversed(ADDRESSES)),
 'interleaved':[0xe9002000,0xe9002040,0xe9002004,0xe9002044,0xe9002008,0xe9002048,0xe9002080,0xe9002084]}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(ok,message):
 if not ok:raise RuntimeError(message)
def code():
 guard=prior.base.prior.check_code(0)
 body='''
proc single {address} {
 set row [read_memory $address 32 1]
 if {[llength $row]!=1} {error "Single-word read length differs"}
 set value [lindex $row 0]
 if {$value<0 || $value>0xffffffff} {error "Read word out of range"}
 return $value
}
proc fresh {label} {
 set control [list [single 0xe9002000] [single 0xe9002004] [single 0xe9002008]]
 echo "UTNA_FRESH $label $control"
 if {[lindex $control 0]!=0x55544e41 || [lindex $control 1]!=0 || [lindex $control 2]!=0} {error "UTNA control not fresh"}
}
fresh BEFORE
'''
 for passage in range(2):
  for label,addresses in ORDERS.items():
   for index,address in enumerate(addresses):
    body+=f'echo "UTNA_READ {passage} {label} {index} {address:#x} [single {address:#x}]"\n'
  body+=f'fresh PASS{passage}\n'
 # Recheck the existing CPU/GPU/NCP guard without another init/halt.
 after=guard.removeprefix('\n').split('riscv set_enable_virt2phys off',1)[1]
 return guard+body+'\necho R19_AFTER_READS\nriscv set_enable_virt2phys off'+after+'\nfresh AFTER\necho UTNA_READONLY_DONE\nshutdown\n'
def dependencies():
 result={Path(__file__),HERE/'read_utna.tcl',HERE/'test_readonly.py',HERE/'tests_result.json',ANCHOR,
  ROOT/'tools/neo/ae350_espprog.cfg',Path('/usr/local/bin/openocd'),prior.base.prior.t.R19/'impl/pnr/console_neo.fs'}
 for module in tuple(sys.modules.values()):
  name=getattr(module,'__file__',None)
  if name:
   p=Path(name).resolve()
   if p.is_file() and p.suffix=='.py' and p.is_relative_to(ROOT) and not p.is_relative_to(HERE):result.add(p)
 return sorted(result)
def local_checks(path,ready=True):
 r=json.loads(path.read_text());require(r['board']=='neo' and r['scope']=='fresh_R19_UTNA_readonly','Wrong scope')
 require(not ready or r['hardware_ready'] is True,'Root review pending')
 require(r['controller_sha256']==sha(Path(__file__)),'Controller changed')
 require(sha(ANCHOR)==ANCHOR_SHA==r['anchor_sha256'],'Anchor changed')
 a=json.loads(ANCHOR.read_text());require('finished_unix' in a and a['left_startup_verified'],'Anchor incomplete')
 require(a['last_programmed_sha256']==prior.base.prior.t.R19_SHA==r['r19_sha256'],'Not restored R19')
 for name,digest in a['files'].items():require(sha(ANCHOR.parent/name)==digest,'Anchor evidence changed: '+name)
 require(all(str(p.resolve()) in r['proof_files'] for p in dependencies()),'Missing dependency')
 for name,digest in r['proof_files'].items():require(sha(Path(name))==digest,'Dependency changed: '+name)
 source=(HERE/'read_utna.tcl').read_text();require(source==code(),'Tcl changed')
 require(not re.search(r'\b(write_memory|load_image|dump_image|mww|mwh|mwb|resume|irscan|drscan|reset)\b',source),'Forbidden Tcl operation')
 require(json.loads((HERE/'tests_result.json').read_text())['passed'] is True,'Offline tests missing')
 return r,source
def check_identity(identity):
 require(identity['neo']['serial']=='2025041420' and identity['neo']['path'].endswith('/3-4.4.1'),'Wrong Neo identity')
 require(identity['esp']['path'].endswith('/3-4.4.2'),'Wrong AE350 adapter path')
def parse(raw):
 rows=re.findall(r'^UTNA_READ (\d+) (\w+) (\d+) (\S+) (\S+)\r?$',raw,re.M)
 expected=[(str(p),label,str(i),addr) for p in range(2) for label,addresses in ORDERS.items() for i,addr in enumerate(addresses)]
 require(len(rows)==len(expected)==48,'Incomplete read capture')
 values=[]
 for row,want in zip(rows,expected):
  require(row[:3]==want[:3] and int(row[3],0)==want[3],'Read order/address mismatch')
  value=int(row[4],0);require(0<=value<=0xffffffff,'Bad word');values.append(dict(passage=int(row[0]),order=row[1],index=int(row[2]),address=int(row[3],0),value=value))
 controls=re.findall(r'^UTNA_FRESH (\w+) (.+)\r?$',raw,re.M)
 require([x[0] for x in controls]==['BEFORE','PASS0','PASS1','AFTER'],'Missing control guards')
 require(all([int(v,0) for v in text.split()]==[0x55544e41,0,0] for _,text in controls),'Control changed')
 require(len(re.findall(r'^WARM_CHECK_0\r?$',raw,re.M))==2 and re.search(r'^UTNA_READONLY_DONE\r?$',raw,re.M),'Missing CPU/GPU/NCP guards')
 return dict(reads=values,control_fresh_before_after=True,initial_bank_all_zero=all(x['value']==0 for x in values if x['address']>=0xe9002040),capture_complete=True)
def main():
 if sys.flags.optimize:raise SystemExit('assertions disabled: refusing to run')
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--review',type=Path,required=True);p.add_argument('--check-only',action='store_true');a=p.parse_args()
 review,source=local_checks(a.review.resolve(),not a.check_only)
 if a.check_only:print(json.dumps(dict(preflight_passed=True,hardware_access=False,hardware_ready=review['hardware_ready'])));return
 stop=prior.StopRequest();stop.install();stop.checkpoint()
 with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  active=subprocess.run(['ps','-C','openocd','-C','openFPGALoader','-C','gao_sh','-C','gao_analyzer','-C','jtagserver','-o','pid=,comm='],capture_output=True,text=True,timeout=5)
  require(active.returncode==1 and not active.stdout.strip(),'Another debug tool is active')
  identity=prior.base.prior.hw.usb_identity();check_identity(identity);stop.checkpoint()
  out=HERE/('read_'+time.strftime('%Y%m%d_%H%M%S'));out.mkdir(exist_ok=False)
  script=out/'read_utna.tcl';script.write_text(source);log=out/'read_utna.log'
  report=dict(board='neo',started_unix=time.time(),qualification_status='FAIL',review_sha256=sha(a.review),anchor_sha256=ANCHOR_SHA,r19_sha256=review['r19_sha256'],identity=identity,signals_received=stop.received,MMIO_writes=0,FPGA_writes=0,DDR_writes=0,SD_writes=0,CPU_resume_commands=0,observations_completed=False)
  try:
   stop.checkpoint()
   prior.base.prior.hw.run_child(['/usr/local/bin/openocd','-f',str(ROOT/'tools/neo/ae350_espprog.cfg'),'-c','adapter speed 100; gdb_port disabled; tcl_port disabled; telnet_port disabled','-f',str(script)],log,30)
   stop.checkpoint();report['observation']=parse(log.read_text());report['observations_completed']=True
  except BaseException as error:report['error']=repr(error);raise
  finally:
   report['finished_unix']=time.time();report['files']={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='result.json'}
   (out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(output=str(out),**report)),flush=True)
if __name__=='__main__':main()
