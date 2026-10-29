#!/usr/bin/env python3
"""Prepare-only by default. Small RX2 probes only; never stop or launch a game."""
import argparse,base64,fcntl,hashlib,json,os,re,signal,socket,stat,subprocess,time
from pathlib import Path
import bootstrap,sender
from support import UART,need,octets,save,gpu,resync_valid
HERE=Path(__file__).resolve().parent
HOST='michael-AX15';PORT='/dev/serial/by-id/usb-Electrosens_MegaPro_Console_11252024-if00';LOCK='/tmp/prodock-diagnostic.lock'
FPGA='fbbea9c357d0c4d5b33c3c4a7e54f9ed0ff8e31cc3fad1ac9dc1771f8e8cba5f'
ANCHOR={'pid':3158,'start_ticks':27508908};KERNEL='6.12.112-prodock-luma3d-g3d1-r1'
SAVE='2138ac0ad21a4707aad2dc0613381e3bde131acfa783dbb29a43f4d6a4c08cc6'
BASE='df529a3463d6f3138895eeefb6ac70d149d7a714f51be74fb79a73079054e29b'
EXECUTABLE='/tmp/luma-rx2-buffer1';PREFIX='/tmp/rx2-buffer3-';PROMPT=b'prodock# '
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def identity(raw):
 rows=re.findall(rb'^3158 \(luma3d-gm1\) ([^\r\n]+)',raw,re.M);need(len(rows)==1,'GM1 missing');f=rows[0].split();need(len(f)>19 and f[0] not in (b'Z',b'X') and int(f[19])==ANCHOR['start_ticks'],'GM1 PID reused/state changed')
 need(octets(raw,512)==b'/tmp/luma3d-gm1\0--showcase\0','GM1 argv changed');need(re.search(rb'^3158\r?$',raw,re.M),'GM1 pidfile differs')
 need(re.search(rb'^l[^\r\n]* /proc/3158/exe -> /tmp/luma3d-gm1\r?$',raw,re.M),'GM1 executable path differs');return ANCHOR.copy()
def space(raw):
 rows=[x.split() for x in raw.replace(b'\r',b'').splitlines() if x.split() and x.split()[-1]==b'/tmp'];need(len(rows)==1 and len(rows[0])==6 and rows[0][0]==b'tmpfs' and all(x.isdigit() for x in rows[0][1:4]),'Unexpected df');n=int(rows[0][3]);need(n>=1024,'Need 1 MiB free tmpfs for bounded receiver probes');return n
def preflight(bundle,expected=None):
 m=json.loads((bundle/'manifest.json').read_text());h=sha(bundle/'manifest.json')
 if expected:need(h==expected,'Manifest changed')
 for name,d in m['files'].items():
  need(re.fullmatch('[a-zA-Z0-9_.-]+',name),'Unsafe bundle name');p=bundle/name;need(not p.is_symlink() and p.stat().st_size==d['bytes'] and sha(p)==d['sha256'],'Changed file '+name)
 need(m['host']==HOST and m['port']==PORT and m['lock']==LOCK and m['ssh_alias']=='ax15','Wrong transport')
 need(m['anchor']==ANCHOR and m['fpga_sha256']==FPGA and m['save_sha256']==SAVE and m['baseline_sha256']==BASE,'Wrong anchors')
 need(json.loads((bundle/'fpga_reference.json').read_text())['bitstream_sha256']==FPGA,'External FPGA anchor differs')
 health=json.loads((bundle/'health.json').read_text());need(health['passed'] and health['preservation']['identity_after']==ANCHOR and health['preservation']['save_after']['sha256']==SAVE,'Wrong health proof')
 q=json.loads((bundle/'qemu_result.json').read_text());need(q['passed'] and not q['hardware'],'QEMU proof missing')
 need(q['inputs']['games/luma3d/candidates/uart_rx2_buffered_20261028_r1/build_r1/receiver']==sha(bundle/'receiver'),'QEMU tested different receiver')
 for name in ('sender.py','sender_base.py'):
  hashes=[v for k,v in q['host_sender_override'].items() if k.endswith('/uart_rx2_retry_20261028_r1/'+name)];need(hashes==[sha(bundle/name)],'QEMU tested different sender '+name)
 previous=json.loads((bundle/'previous_board_result.json').read_text());need(previous['hardware'] and previous['preserved'] and previous['manifest_sha256']==sha(bundle/'manifest_previous.json') and previous['bootstrap_verified']==dict(bytes=13132,sha256=sha(bundle/'receiver')),'Prior exact receiver verification missing')
 need(previous['after']['identity']==ANCHOR and previous['after']['save']['sha256']==SAVE and [x['name'] for x in previous['probes']]==['clean-0','clean-513'],'Prior probe identity/results differ')
 need(m['receiver_sha256']==sha(bundle/'receiver') and bootstrap.plan(bundle/'receiver',EXECUTABLE)==json.loads((bundle/'bootstrap.json').read_text()),'Bootstrap mismatch')
 return m,h
def review_check(r,h,host,now):
 need(host==HOST and r.get('host')==HOST and r.get('ssh_alias')=='ax15' and r.get('port')==PORT,'Wrong host/port')
 need(r.get('manifest_sha256')==h and r.get('anchor')==ANCHOR and r.get('fpga_sha256')==FPGA and r.get('save_sha256')==SAVE and r.get('previous_board_result_sha256')==sha(HERE/'previous_board_result.json'),'Review anchors differ')
 for k in ['root_authorized_probes','same_g22r0_since_health','same_gm1_since_health','ordinary_shell_confirmed','no_other_console_session','same_receiver_since_prior_probe'] :need(r.get(k) is True,'Missing review '+k)
 need(type(r.get('reviewed_unix')) in (int,float) and 0<=now-r['reviewed_unix']<=1800,'Review expired')
class Channel:
 def __init__(self,uart,out):self.uart=uart;self.out=out;self.shell=False;self.current=None;self.counter=0;self.token=os.urandom(8).hex();self.received=open(out/'uart_rx.bin','wb');self.sent=open(out/'uart_tx.bin','wb')
 def read(self,timeout):
  b=self.uart.read(4096,timeout);self.received.write(b);self.received.flush();return b
 def write(self,b):
  n=self.uart.write(b);self.sent.write(b[:max(0,n or 0)]);self.sent.flush();return n
 def collect(self,seconds,check,quiet=.2,bound=131072):
  end=time.monotonic()+seconds;last=time.monotonic();data=bytearray();value=None
  while time.monotonic()<end:
   b=self.read(.02)
   if b:data.extend(b);last=time.monotonic();need(len(data)<=bound,'Output bound exceeded');value=check(bytes(data))
   if value and time.monotonic()-last>=quiet:return bytes(data)
  raise RuntimeError('Expected bounded output absent')
 def initial_shell(self):
  # Root must attest a known ordinary shell; no recovery in this controller.
  data=bytearray();end=time.monotonic()+1
  while time.monotonic()<end:data.extend(self.read(.05))
  need(not data or resync_valid(bytes(data)),'Unexpected passive output')
  need(self.write(b'\n')==1,'Partial shell probe');self.collect(5,resync_valid);self.shell=True
 def text(self,command):
  deadline=time.monotonic()+10
  for ch in command:
   need(time.monotonic()<deadline,'Shell command transmit deadline');need(self.write(bytes([ch]))==1,'Partial shell command');time.sleep(.002)
 def run(self,name,command,timeout=90):
  need(self.shell and self.current is None,'Shell not confirmed');self.counter+=1;marker=f'RX2_QUERY_{self.token}_{self.counter}'
  cmd=f"{command}; rc=$?; printf '\\n{marker}:%s\\n' \"$rc\"\n".encode();self.shell=False;self.text(cmd)
  pat=re.compile(rb'^'+marker.encode()+rb':([0-9]+)\r?\n',re.M)
  def check(b):
   found=pat.findall(b)
   if found:self.shell=True;need(found==[b'0'],'Shell command failed/duplicate');return True
   return False
  data=self.collect(timeout,check);self.shell=True;(self.out/(name+'.log')).write_bytes(data);return data
 def restore_shell(self,s):
  # READ ONLY until a fresh RETURN, even after signal, CRC error or timeout.
  s.await_return()
  # Drain a bounded quiet suffix BEFORE cancellation so a stale prompt cannot
  # qualify the new shell response. No device flush is used.
  end=time.monotonic()+2;last=time.monotonic()
  while time.monotonic()<end:
   b=self.read(.05)
   if b:last=time.monotonic()
   elif time.monotonic()-last>=.2:break
  else:raise RuntimeError('No quiet return suffix')
  s.cancel_line();self.collect(5,resync_valid);self.shell=True;self.current=None
 def close(self):self.received.close();self.sent.close()
def inspect(c,label):
 ident=identity(c.run(label+'_identity','cat /tmp/luma3d-live.pid && cat /proc/3158/stat && od -b -v /proc/3158/cmdline && ls -l /proc/3158/exe'))
 system=c.run(label+'_system','uname -r && cat /proc/mounts');need(re.search(rb'^'+KERNEL.encode()+rb'\r?$',system,re.M) and b'tmpfs /tmp tmpfs ' in system,'Kernel/tmp mount changed')
 saved=save(c.run(label+'_save','od -b -v /tmp/op2-live.save'));counter=gpu(c.run(label+'_gpu','prodockctl display'));free=space(c.run(label+'_space','LC_ALL=C df -Pk /tmp'))
 return dict(identity=ident,kernel=KERNEL,save=saved,gpu=counter,tmp_available_kib=free)
def payload_readback(c,label,path,data):
 raw=c.run(label,'ls -ln '+path+" && printf '\\nRX2_PAYLOAD_BEGIN\\n' && od -b -v "+path+" && printf '\\nRX2_PAYLOAD_END\\n'")
 rows=re.findall(rb'^-[^\r\n]+ '+re.escape(path.encode())+rb'\r?$',raw,re.M);need(len(rows)==1,'Payload stat missing');fields=rows[0].split();need(len(fields)>=6 and fields[-2].isdigit() and int(fields[-2])==len(data),'Payload stat size differs')
 matches=re.findall(rb'\r?\nRX2_PAYLOAD_BEGIN\r?\n(.*?)\r?\nRX2_PAYLOAD_END\r?\n',raw,re.S);need(len(matches)==1,'Missing/duplicate payload boundaries');body=matches[0]
 # This BusyBox od emits no final offset for an empty file. The successful
 # regular-file ls and exact size zero distinguish that from a truncated dump.
 if not data:
  need(not body.strip(),'Nonempty dump for empty file');got=b''
 else:got=octets(body,len(data))
 need(got==data,'Probe payload changed');return {'bytes':len(got),'sha256':hashlib.sha256(got).hexdigest()}
class TimedSession(sender.Session):
 def __init__(self,*args,**kw):super().__init__(*args,**kw);self.send_seconds=0.;self.wait_seconds=0.
 def send(self,*args,**kw):
  start=time.monotonic()
  try:return super().send(*args,**kw)
  finally:self.send_seconds+=time.monotonic()-start
 def event(self,*args,**kw):
  start=time.monotonic()
  try:return super().event(*args,**kw)
  finally:self.wait_seconds+=time.monotonic()-start
 def reset_times(self):self.send_seconds=self.wait_seconds=0.
def probe(c,label,data,resume=False,stop=False,corrupt=False,path=None):
 path=path or PREFIX+label+'.part';s=TimedSession(c,os.urandom(16).hex(),data,idle_ms=5000,total_ms=120000)
 need(c.shell and c.current is None,'Shell not confirmed');c.shell=False;c.current=s
 c.text(s.command(EXECUTABLE,path,resume));ready=s.begin();s.reset_times();started=time.monotonic()
 def mutate(wire,attempt):
  if attempt:return wire
  raw=bytearray(base64.b64decode(wire[1:-1]));raw[-1]^=1;return b'\0'+base64.b64encode(raw)+b'\0'
 if stop:s.block();s.finish(stop=True)
 else:
  first=True
  while s.offset<len(data):s.block(mutate if corrupt and first else None);first=False
  s.finish()
 transfer_seconds=time.monotonic()-started
 c.restore_shell(s)
 need(not resume or ready.offset==512,'Wrong resume checkpoint')
 expected=data[:512] if stop else data
 check=payload_readback(c,label+'_readback',path,expected)
 need(not corrupt or (s.retries>=1 and s.nack_events>=1),'Injected bad frame rejection not observed')
 return {'name':label,'path':path,'ready_offset':ready.offset,'final_offset':s.offset,'returncode':s.returncode,'frames':s.sent_frames,'retries':s.retries,'nack_events':s.nack_events,'integrity_passed':True,'link_stability_passed':s.retries==(1 if corrupt else 0) and s.nack_events==(1 if corrupt else 0),'expected_retries':1 if corrupt else 0,'elapsed_seconds_including_readback':time.monotonic()-started,'transfer_seconds':transfer_seconds,'sender_seconds':s.send_seconds,'wait_seconds':s.wait_seconds,'readback':check,'replies':[r.__dict__ for r in s.replies]}
def main():
 p=argparse.ArgumentParser();p.add_argument('--run',action='store_true');p.add_argument('--prepare-only',action='store_true');p.add_argument('--expected-manifest');p.add_argument('--review',type=Path);p.add_argument('--out',type=Path);a=p.parse_args();m,h=preflight(HERE,a.expected_manifest)
 need(not(a.run and a.prepare_only),'Choose run OR prepare-only')
 if not a.run:print(json.dumps({'prepared':True,'hardware':False,'manifest_sha256':h}));return 0
 need(a.expected_manifest and a.review and a.out,'Explicit review/manifest/new output required');review=json.loads(a.review.read_text());review_check(review,h,socket.gethostname().split('.')[0],time.time());a.out.mkdir(parents=True,exist_ok=False)
 result={'passed':False,'integrity_passed':False,'link_stability_passed':False,'hardware':True,'manifest_sha256':h,'review_sha256':sha(a.review),'stop_gm1':False,'relaunch_gm1':False,'fpga_writes':0,'sd_writes':0,'save_writes':0,'probes':[]};uart=None;c=None;cleanup=False
 def interrupted(sig,frame):
  if not cleanup:raise InterruptedError('Signal '+str(sig))
 previous={sig:signal.signal(sig,interrupted) for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP)}
 try:
  with open(LOCK,'a+') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);need(stat.S_ISCHR(os.stat(PORT).st_mode),'Port not character device');owner=subprocess.run(['fuser',PORT],capture_output=True);need(owner.returncode==1 and not owner.stdout.strip() and not owner.stderr.strip(),'Port busy')
   try:
    uart=UART(PORT);c=Channel(uart,a.out);c.initial_shell();result['before']=inspect(c,'before')
    boot=json.loads((HERE/'bootstrap.json').read_text())
    result['receiver_reused']=True;result['receiver_written']=False
    raw=c.run('receiver_readback',boot['commands'][-1].rstrip('\n'));verified=bootstrap.validate_readback(boot,raw);need(hashlib.sha256(verified).hexdigest()==m['receiver_sha256'],'Receiver SHA mismatch')
    result['bootstrap_verified']=dict(bytes=len(verified),sha256=hashlib.sha256(verified).hexdigest())
    for n in (0,513,16384):result['probes'].append(probe(c,'clean-'+str(n),bytes((i*73+19)&255 for i in range(n))))
    data=bytes(range(256))*2+b'!';result['probes'].append(probe(c,'nack',data,corrupt=True))
    data=bytes(range(256))*4;result['probes'].append(probe(c,'stop',data,stop=True,path=PREFIX+'resume.part'));result['probes'].append(probe(c,'resume',data,resume=True,path=PREFIX+'resume.part'))
    result['integrity_passed']=all(x['integrity_passed'] for x in result['probes'])
    result['link_stability_passed']=all(x['link_stability_passed'] for x in result['probes'])
    result['passed']=result['integrity_passed'] and result['link_stability_passed']
    result['link_deviations']=[dict(name=x['name'],retries=x['retries'],nack_events=x['nack_events'],expected=x['expected_retries']) for x in result['probes'] if not x['link_stability_passed']]
   except BaseException as e:result['error']=repr(e)
   finally:
    cleanup=True
    if c:
     try:
      if c.current:c.restore_shell(c.current)
      if c.shell:
       result['after']=inspect(c,'after');delta=(result['after']['gpu']['presents']-result['before']['gpu']['presents'])&0xffffffff;need(0<delta<1000000,'GPU not progressing');result['presents_delta']=delta;result['preserved']=True
      else:result['passed']=False;result['manual_review_required']=True
     except BaseException as e:result['passed']=False;result['cleanup_error']=repr(e);result['manual_review_required']=True
     c.close()
    if uart:uart.close();uart=None
 except BaseException as e:result['passed']=False;result['error']=repr(e)
 finally:
  for sig,handler in previous.items():signal.signal(sig,handler)
  (a.out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'passed':result['passed'],'integrity_passed':result['integrity_passed'],'link_stability_passed':result['link_stability_passed'],'output':str(a.out)}));return not result['passed']
if __name__=='__main__':raise SystemExit(main())
