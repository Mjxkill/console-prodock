#!/usr/bin/env python3
"""Separate phase2: six bounded GPU windows, then exact GM1 restoration.

No transfer path. Frozen R6 launch-state and process guards are reused. Device
access only in --run, root-reviewed against a successful phase1 result.
"""
import argparse,fcntl,json,os,re,socket,stat,subprocess,time
from pathlib import Path
import festival_trial as legacy
import probe_channel as p
import read_metrics
HERE=Path(__file__).resolve().parent
STAGE_SHA='fce932922910e876040f8d09012fe207c723f9162adaefa5d3a0ed3deddc09d1'
TARGET_SHA='6b8d3eeb273e03be38eb73a2ff6fee60dad16678316bfdacb52b4db308fec3f7'
def preflight(expected=None):
 m=json.loads((HERE/'manifest.json').read_text());h=p.sha(HERE/'manifest.json')
 if expected:p.need(h==expected,'Manifest changed')
 p.need(__debug__,'Python -O disallowed')
 p.need(m['board']=='prodock' and m['host']==p.HOST and m['port']==p.PORT and m['lock']==p.LOCK and m['expected_identity']==p.ANCHOR and m['kernel']==p.KERNEL and m['fpga_sha256']==p.FPGA and m['save_sha256']==p.SAVE,'Wrong board/anchor')
 p.need(set(legacy.DEPS).issubset(m['files']) and all(x.name in m['files'] for x in HERE.glob('*.py')),'Missing executable input')
 for name,d in m['files'].items():
  p.need(re.fullmatch(r'[A-Za-z0-9_.-]+',name) is not None,'Unsafe input name')
  p.need(legacy.digest(HERE/name)==d and not(HERE/name).is_symlink(),'Input changed '+name)
 stage=json.loads((HERE/'stage_plan.json').read_text());p.need(p.sha(HERE/'stage_plan.json')==STAGE_SHA and m['game']==stage['target'] and m['game']['sha256']==TARGET_SHA and m['windows']==stage['windows'] and m['baseline']==stage['base'] and m['helper_record']==stage['helper'],'Wrong target/windows')
 p.need(m['program']=='luma3d-fm4a' and m['tag']=='fm4measured' and m['helper']=='mc1-helper','Unexpected names')
 p.need(json.loads((HERE/'fpga_reference.json').read_text())['bitstream_sha256']==p.FPGA,'External FPGA identity changed')
 return m,h
def stage_result_check(r):
 p.need(r.get('passed') and r.get('hardware') and r.get('preserved') and r.get('plan_sha256')==STAGE_SHA,'Stage did not pass')
 p.need(r['after']['identity']==p.ANCHOR and r['after']['save']['sha256']==p.SAVE and not r['stop_gm1'] and not r['game_executed'],'Stage changed GM1')
 s=r['staged'];p.need(s['elf']=='/tmp/luma3d-fm4a' and s['expected_sha256']==TARGET_SHA and s['runtime_crc32']=='fa358bf4' and s['game_executed'] is False,'Stage target changed')
def review_check(r,h,stage_sha,host,now):
 p.need(host==p.HOST and r.get('host')==p.HOST and r.get('port')==p.PORT and r.get('manifest_sha256')==h and r.get('stage_result_sha256')==stage_sha,'Review identity mismatch')
 p.need(r.get('anchor')==p.ANCHOR and r.get('fpga_sha256')==p.FPGA and r.get('save_sha256')==p.SAVE and r.get('target_sha256')==TARGET_SHA,'Review anchors changed')
 for k in ['root_authorized_six_windows_and_restore','same_gm1_since_stage','same_g22r0_since_stage','helper_unchanged_since_full_readback','ordinary_shell_confirmed','no_other_console_session']:p.need(r.get(k) is True,'Missing review '+k)
 p.need(type(r.get('reviewed_unix')) in (int,float) and 0<=now-r['reviewed_unix']<=1800,'Review expired')
def log_capacity(raw):
 rows=[x.split() for x in raw.splitlines() if x.split() and x.split()[-1]==b'/tmp']
 p.need(len(rows)==1 and len(rows[0])==6 and rows[0][0]==b'tmpfs' and all(x.isdigit() for x in rows[0][1:4]),'Invalid tmpfs capacity')
 total,used,free=map(int,rows[0][1:4]);p.need(0<total and 0<=used<=total and 1024<=free<=total and used+free<=total,'Need 1 MiB log reserve')
 return free
def measurement(log,row):
 p.need(b'LUMA3D_SAVE ' not in log,'Unexpected save action')
 parsed=read_metrics.parse(log.decode(),hardware=True,mode=row['mode'],memory_actions=row.get('memory_actions'),table_actions=row.get('table_actions'))
 counters=legacy.fields(log,'LUMA3D_COUNTERS');p.need(all(counters[k]==0 for k in ['errors','underflows','fault','geometry_errors']) and counters['frames']==parsed['frames'],'GPU error/present mismatch')
 return dict(measurement=parsed,counters=counters)
class UARTAdapter:
 """Preserve raw host settings and no DTR transition; legacy API shape only."""
 def __init__(self,uart):self.uart=uart;self.timeout=.1
 def read(self,n):return self.uart.read(n,self.timeout)
 def write(self,b):n=self.uart.write(b);p.need(n==len(b),'Partial shell write');return n
 def flush(self):pass # write uses finite nonblocking syscall; no tcdrain hang.
class Hardware(legacy.Hardware):
 def initial(self):
  # No receiver exists in phase2. Root attests ordinary shell continuity.
  self.uart.write(b'\n');time.sleep(.2);self.uart.read(16000)
  raw=self.tx.run('before','uname -r; prodockctl display; cat /proc/mounts')
  p.need(re.search(rb'^'+p.KERNEL.encode()+rb'\r?$',raw,re.M) and b'tmpfs /tmp tmpfs ' in raw and not re.search(rb'^/dev/mmc\S* ',raw,re.M),'Kernel/tmpfs changed')
  anchor=self.identity('initial_gm1');saved=self.save('save_initial');first=self.display(raw);time.sleep(3);second=self.display(self.tx.run('progress_before','prodockctl display'));delta=(second['presents']-first['presents'])&0xffffffff;p.need(0<delta<100000,'GPU progression invalid')
  names=[self.m['tag']+'_'+str(i)+'.'+ext for i in range(6) for ext in ('pid','pid.tmp','log','exit')]+[self.m['tag']+'_restore.'+ext for ext in ('pid','log')]
  self.tx.run('fresh_names',' && '.join('test ! -e /tmp/'+n+' && test ! -L /tmp/'+n for n in names),60)
  free=log_capacity(self.tx.run('space_logs','LC_ALL=C df -Pk /tmp'))
  return dict(identity=anchor,save=saved,display=second,kernel=p.KERNEL,tmp_available_kib=free)
 def prepare(self):
  self.tx.run('permissions','test -f /tmp/mc1-helper && test -x /tmp/mc1-helper && test ! -L /tmp/mc1-helper && test -f /tmp/luma3d-fm4a && test -x /tmp/luma3d-fm4a && test ! -L /tmp/luma3d-fm4a')
  for label,path,record in [('helper','/tmp/mc1-helper',self.m['helper_record']),('baseline','/tmp/luma3d-gm1',self.m['baseline']),('running','/proc/3158/exe',self.m['baseline']),('target','/tmp/luma3d-fm4a',self.m['game'])]:self.arcade.raw_verify(self.tx,self.m['helper'],label+'_runtime',path,record)
  return []
 def window(self,row,tag,launch):
  raw=self.tx.run(tag+'_launch',legacy.launch_command(self.m['program'],tag,' '.join(row['args'])),launch=launch)
  data=bytearray(raw);deadline=time.monotonic()+row['timeout_seconds'];pattern=re.compile(rb'^L3_EXIT_'+tag.encode()+rb':(\d+)\r?\n',re.M)
  try:
   while True:
    launch.observe(data);self.signals.checkpoint();found=pattern.search(data)
    if found:p.need(int(found[1])==0,'Candidate nonzero exit');break
    p.need(time.monotonic()<deadline and len(data)<1048576,'Window time/output bound');data.extend(self.uart.read(4096))
  finally:(self.out/(tag+'_wait.log')).write_bytes(data)
  log=self.tx.run(tag+'_log','cat /tmp/'+tag+'.log',120);value=measurement(log,row)
  display=self.display(self.tx.run(tag+'_display','prodockctl display'));return dict(window=row,display=display,**value)
 def abort_transfer(self):p.need(self.tx.receiver_state=='idle','Phase2 has no receiver or transfer')
 def recover(self,current,ever,recovery):
  p.need(current is None or current[0]==self.m['program'],'Cleanup target is not our candidate')
  return super().recover(current,ever,recovery)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--run',action='store_true');ap.add_argument('--expected-manifest');ap.add_argument('--stage-result',type=Path);ap.add_argument('--review',type=Path);ap.add_argument('--out',type=Path);a=ap.parse_args();m,h=preflight(a.expected_manifest)
 if not a.run:print(json.dumps({'prepared':True,'hardware':False,'manifest_sha256':h,'windows':6}));return 0
 p.need(a.expected_manifest and a.stage_result and a.review and a.out,'Explicit manifest/stage-result/review/output required');sr=json.loads(a.stage_result.read_text());stage_result_check(sr);r=json.loads(a.review.read_text());review_check(r,h,p.sha(a.stage_result),socket.gethostname().split('.')[0],time.time());a.out.mkdir(parents=True,exist_ok=False)
 modules=legacy.dependencies(HERE,m);result=dict(passed=False,hardware=True,manifest_sha256=h,stage_result_sha256=p.sha(a.stage_result));uart=None
 try:
  with open(p.LOCK,'a+') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);p.need(stat.S_ISCHR(os.stat(p.PORT).st_mode),'Wrong port');owner=subprocess.run(['fuser',p.PORT],capture_output=True);p.need(owner.returncode==1 and not owner.stdout.strip() and not owner.stderr.strip(),'Port busy')
   try:
    uart=p.UART(p.PORT)
    with legacy.DeferredSignals() as signals:
     hardware=Hardware(HERE,a.out,m,UARTAdapter(uart),signals,modules);result.update(legacy.Session(hardware,m,signals).run())
   finally:
    if uart:uart.close();uart=None
 except BaseException as e:result['error']=repr(e);result['passed']=False
 finally:(a.out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'passed':result['passed'],'output':str(a.out)}));return not result['passed']
if __name__=='__main__':raise SystemExit(main())
