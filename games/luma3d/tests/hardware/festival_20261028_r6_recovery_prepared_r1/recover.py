#!/usr/bin/env python3
"""Prepare-only by default. Root may execute the reviewed one-shot R6 recovery.

No imports or default CLI paths open a device. No FPGA/SD/JTAG/reset/process
signal/transfer retry. Unknown receiver state permits only the reviewed 2064
bytes once; no shell query before its exact fresh terminal marker and resync.
"""
import argparse,fcntl,hashlib,json,os,re,select,signal,socket,stat,struct,subprocess,termios,time,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
HOST='michael-AX15';SSH_ALIAS='ax15'
PORT='/dev/serial/by-id/usb-Electrosens_MegaPro_Console_11252024-if00'
LOCK='/tmp/prodock-diagnostic.lock'
CLAIM='/tmp/prodock-r6-recovery-66e113ea17517cbf.claim'
R6_SHA='66e113ea17517cbf53b847138b1e33b3201323faa13d0bef4133d7c35a66e316'
R6_REVIEW_SHA='abf02a51dd4342f30a63cb50c7d7eb3761f6c9524e4c94351782ef77a2fd3cf0'
FPGA_SHA='fbbea9c357d0c4d5b33c3c4a7e54f9ed0ff8e31cc3fad1ac9dc1771f8e8cba5f'
BASE_SHA='df529a3463d6f3138895eeefb6ac70d149d7a714f51be74fb79a73079054e29b'
SAVE_SHA='2138ac0ad21a4707aad2dc0613381e3bde131acfa783dbb29a43f4d6a4c08cc6'
ANCHOR={'pid':3158,'start_ticks':27508908}
KERNEL='6.12.112-prodock-luma3d-g3d1-r1'
NAME='festival-r9f.delta.lz4'
MAGIC=b'LMA1';RECOVERY=bytes(2048)+struct.pack('<4sIII',MAGIC,0,0,0)
MARKER=b'\nLMA_RX_EXIT_'+NAME.encode()+b':1\n'
PROMPT=b'prodock# '
class Refused(RuntimeError):pass
def need(condition,message):
 if not condition:raise Refused(message)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def preflight(bundle,expected=None):
 raw=bundle/'manifest.json';m=json.loads(raw.read_text());digest=sha(raw)
 if expected:need(digest==expected,'Manifest digest mismatch')
 need(m['r6_manifest_sha256']==R6_SHA and m['r6_review_sha256']==R6_REVIEW_SHA,'Not exact R6')
 need(m['host']==HOST and m['ssh_alias']==SSH_ALIAS and m['port']==PORT and m['lock']==LOCK,'Wrong host/transport')
 need(m['expected_identity']==ANCHOR and m['fpga_sha256']==FPGA_SHA and m['baseline_sha256']==BASE_SHA and m['save_sha256']==SAVE_SHA,'Wrong anchor')
 need(m['recovery_hex']==RECOVERY.hex() and len(RECOVERY)==2064 and set(RECOVERY)<=set(b'\0LMA1'),'Unexpected recovery bytes')
 for name,d in m['files'].items():
  need(re.fullmatch(r'[A-Za-z0-9_.-]+',name) is not None,'Unsafe bundle name');p=bundle/name
  need(not p.is_symlink() and p.stat().st_size==d['bytes'] and sha(p)==d['sha256'],'Bundle changed: '+name)
 need(sha(bundle/'r6_manifest.json')==R6_SHA,'Retained R6 manifest is not exact')
 incident=json.loads((bundle/'r6_result.json').read_text());transport=json.loads((bundle/'r6_transport.json').read_text())
 need(incident['manifest_sha256']==R6_SHA and incident['review_sha256']==R6_REVIEW_SHA and not incident['passed'] and not incident['windows'],'Wrong incident')
 need(incident['manual_recovery_required'] and incident['initial']['identity']==ANCHOR and incident['initial']['save']['sha256']==SAVE_SHA,'Wrong incident anchor')
 need(transport['receiver_state']=='unknown','Receiver was not unknown')
 records=[x for x in transport['trace'] if x.get('phase')=='data'];need(len(records)==117,'Unexpected transfer history')
 for seq,row in enumerate(records[:-1]):need(row==dict(phase='data',seq=seq,raw=(b'A'+struct.pack('<I',seq)).hex()),'ACK history changed')
 need(records[-1]==dict(phase='data',seq=116,raw=''),'Not silent seq116')
 reference=json.loads((bundle/'fpga_reference.json').read_text());need(reference['bitstream_sha256']==FPGA_SHA,'External FPGA anchor differs')
 proof=json.loads((bundle/'nul_qemu_result.json').read_text());need(proof['passed'] and not proof['hardware'] and len(proof['cases'])==28,'Missing bounded QEMU proof')
 need(proof['inputs']['games/luma_adventure/tests/hardware/trial_20261024_r9b/uart-receiver']=='5964389b8244dc73b58bf916a7856da3cc3aba2c2efa58779d1f755bb8410ae4','Wrong receiver proof')
 return m,digest
def check_review(review,digest,host,now):
 need(host==HOST,'Execution host must be michael-AX15, not merely SSH alias ax15')
 need(review.get('manifest_sha256')==digest and review.get('r6_manifest_sha256')==R6_SHA and review.get('r6_review_sha256')==R6_REVIEW_SHA,'Review digest mismatch')
 need(review.get('expected_identity')==ANCHOR and review.get('fpga_sha256')==FPGA_SHA and review.get('save_sha256')==SAVE_SHA and review.get('baseline_sha256')==BASE_SHA,'Review anchor mismatch')
 need(review.get('host')==HOST and review.get('ssh_alias')==SSH_ALIAS and review.get('port')==PORT,'Review transport mismatch')
 for key in ('root_authorized_one_shot','r6_state_unchanged_since_incident','no_other_console_session','receiver_or_ordinary_shell_only','not_in_quote_heredoc_or_other_program','no_reconfiguration_since_g22r0'):
  need(review.get(key) is True,'Missing root confirmation: '+key)
 stamp=review.get('reviewed_unix');need(type(stamp) in (int,float) and 0<=now-stamp<=1800,'Review is not fresh (30 minute bound)')
def terminal(data):
 """A bounded, whole transcript parser. No substring-only terminal match."""
 need(len(data)<=16384,'Receiver transcript exceeds bound')
 if data.endswith(b'\r'):return None # CRLF can be fragmented between reads.
 raw=data.replace(b'\r\n',b'\n')
 # Binary ACK fields can contain 0x0d/0x0a in general; here whitelisted values
 # are below 60417 and their little-endian bytes never contain CRLF.
 at=raw.find(b'\nLMA_RX_EXIT_')
 if at<0:
  # Before a marker, permit only a small number of exact protocol ACKs and
  # a partial prefix of the expected marker. Any unrelated output refuses.
  prefix=raw;acks=[]
 else:prefix=raw[:at];acks=[]
 while len(prefix)>=5 and prefix[:1] in (b'A',b'N',b'F'):
  code=prefix[0];value=struct.unpack('<I',prefix[1:5])[0]
  need((code==65 and value==116) or (code==78 and value in (116,117)) or (code==70 and 59392<=value<=60416),'Unexpected ACK value')
  acks.append((code,value));need(len(acks)<=3,'Too many ACKs');prefix=prefix[5:]
 if at<0:
  if not prefix:return None
  if len(prefix)<5 and prefix[:1] in (b'A',b'N',b'F'):return None
  need(MARKER.startswith(prefix),'Unexpected output while receiver unresolved');return None
 need(not prefix,'Unexpected bytes before marker')
 end=at+len(MARKER)
 if len(raw)<end:need(MARKER.startswith(raw[at:]),'Wrong return marker');return None
 need(raw[at:end]==MARKER,'Wrong receiver/code or malformed marker')
 tail=raw[end:]
 # Echo after return may contain only the recovery suffix or NUL echo from
 # the known ordinary shell line. Unknown diagnostics/extra markers refuse.
 while tail:
  token=next((x for x in (PROMPT,b'LMA1',b'^@',b'\0',b'\n',b'\r') if tail.startswith(x)),None)
  if token:tail=tail[len(token):];continue
  if any(x.startswith(tail) for x in (PROMPT,b'LMA1',b'^@')):return None
  raise Refused('Unexpected bytes after return marker')
 return {'receiver_exit':1,'acks':[{'code':chr(c),'value':v} for c,v in acks]}
def resync_valid(data):
 # BusyBox line editor may erase each character or redraw its line. Permit
 # erasure and prompt tokens only, never a diagnostic or echoed command word.
 need(len(data)<=16384,'Resync transcript exceeds bound');raw=data;prompts=0
 while raw:
  if raw.startswith(PROMPT):prompts+=1;raw=raw[len(PROMPT):];continue
  if raw[:1] in (b'\b',b'\r',b'\n',b' '):raw=raw[1:];continue
  m=re.match(rb'\x1b\[[0-9;]*[JKGH]',raw)
  if m:raw=raw[m.end():];continue
  if PROMPT.startswith(raw) or re.fullmatch(rb'\x1b(?:\[[0-9;]*)?',raw):return False
  raise Refused('Unexpected output during shell line cancellation')
 return prompts>0
class Recovery:
 def __init__(self,uart,out,clock=time.monotonic,sleep=time.sleep,claim=None):self.uart,self.out,self.clock,self.sleep=uart,out,clock,sleep;self.claim=claim;self.state='unknown';self.attempted=False;self.record={'bytes_sent':0,'receiver_return_confirmed':False,'shell_confirmed':False}
 def listen(self,seconds,name,validator=None,quiet=.5):
  deadline=self.clock()+seconds;last=self.clock();data=bytearray();verdict=None
  try:
   while self.clock()<deadline:
    new=self.uart.read(4096,.05)
    if new:
     data.extend(new);last=self.clock();need(len(data)<=16384,'Read bound exceeded')
     if validator is None:raise Refused('Passive listener saw data; no recovery emitted')
     verdict=validator(bytes(data))
    if verdict and self.clock()-last>=quiet:return verdict
   if validator is None:return None
   raise Refused('Expected return or prompt not confirmed before deadline')
  finally:(self.out/name).write_bytes(data)
 def run(self):
  need(self.state=='unknown' and not self.attempted,'Recovery is single-use')
  self.listen(15,'passive.bin')
  need(self.claim is not None,'No durable one-shot claim configured');self.claim()
  self.attempted=True;self.state='sending_once'
  # Pacing matches the known transport. A short/failed write is uncertain;
  # never resend its remainder or retry the 2064-byte recovery sequence.
  for start in range(0,len(RECOVERY),16):
   block=RECOVERY[start:start+16];n=self.uart.write(block);self.record['bytes_sent']+=max(0,n or 0);need(n==len(block),'Partial recovery write; no retry');self.sleep(.002)
  self.state='waiting_return';verdict=self.listen(15,'return.bin',terminal);self.record.update(verdict,receiver_return_confirmed=True)
  self.state='return_confirmed'
  need(self.uart.write(b'\x15\n')==2,'Partial line cancellation; no query allowed')
  self.listen(10,'resync.bin',resync_valid);self.state='shell_confirmed';self.record['shell_confirmed']=True
  return self.record
class UART:
 """No flush, baud change, DTR/RTS transition, or termios mutation."""
 def __init__(self,port):
  self.fd=os.open(port,os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)
  try:
   fcntl.ioctl(self.fd,termios.TIOCEXCL)
   attrs=termios.tcgetattr(self.fd)
   need(attrs[4]==attrs[5]==termios.B115200,'Host UART speed changed')
   need(not(attrs[3]&(termios.ICANON|termios.ECHO|termios.ISIG)),'Host UART is not raw')
   need(not(attrs[0]&(termios.IGNCR|termios.ICRNL|termios.INLCR|termios.IXON|termios.IXOFF|termios.ISTRIP)) and not(attrs[1]&termios.OPOST),'Host UART would translate/control bytes')
   need((attrs[2]&termios.CSIZE)==termios.CS8 and not(attrs[2]&(termios.PARENB|termios.CSTOPB)),'Host UART is not 8N1')
  except BaseException:os.close(self.fd);raise
 def read(self,n,timeout):
  ready,_,_=select.select([self.fd],[],[],timeout)
  if not ready:return b''
  try:return os.read(self.fd,n)
  except BlockingIOError:return b''
 def write(self,data):
  _,ready,_=select.select([],[self.fd],[],2);need(ready,'UART write timeout');return os.write(self.fd,data)
 def close(self):os.close(self.fd)
def octets(data,limit):
 blob=bytearray();end=None
 for row in data.replace(b'\r',b'').splitlines():
  if re.fullmatch(rb'[0-7]{7,}(?: +[0-7]{3}){1,16}',row):
   parts=row.split();need(end is None and int(parts[0],8)==len(blob),'Bad octal order');blob.extend(int(x,8) for x in parts[1:]);need(len(blob)<=limit,'Octal overflow')
  elif re.fullmatch(rb'[0-7]{7,}',row):need(end is None,'Duplicate octal end');end=int(row,8)
 need(end==len(blob),'Incomplete octal dump');return bytes(blob)
def identity(raw):
 lines=re.findall(rb'^(3158) \(luma3d-gm1\) ([^\r\n]+)',raw,re.M);need(len(lines)==1,'Wrong GM1 process')
 fields=lines[0][1].split();need(len(fields)>=20 and fields[0] not in (b'Z',b'X') and int(fields[19])==ANCHOR['start_ticks'],'GM1 starttime/state changed')
 need(octets(raw,512)==b'/tmp/luma3d-gm1\0--showcase\0','GM1 argv changed');need(re.search(rb'^3158\r?$',raw,re.M),'Published PID changed')
 need(re.search(rb'^/tmp/luma3d-gm1\r?$',raw,re.M),'GM1 executable path changed');return ANCHOR.copy()
def save(raw):
 blob=octets(raw,5292);need(len(blob)==5292 and hashlib.sha256(blob).hexdigest()==SAVE_SHA,'GM1 save changed');return {'bytes':len(blob),'sha256':SAVE_SHA}
def gpu(raw):
 lines=re.findall(rb'^DISPLAY [^\r\n]+',raw,re.M);need(len(lines)==1,'Missing GPU display status');line=lines[0];d={k.decode():int(v) for k,v in re.findall(rb'\b(errors|uf|invalid|sprites|fault|presents)=(\d+)\b',line)}
 need(set(d)=={'errors','uf','invalid','sprites','fault','presents'} and not any(d[k] for k in d if k!='presents'),'GPU error counters nonzero');return d
QUERIES={
 'identity':"cat /tmp/luma3d-live.pid && cat /proc/3158/stat && od -b -v /proc/3158/cmdline && readlink /proc/3158/exe",
 'save':'od -b -v /tmp/op2-live.save',
 'system':'uname -r && cat /proc/mounts',
 'gpu':'prodockctl display',
 'space':'LC_ALL=C df -Pk /tmp',
 'partial':'wc -c /tmp/festival-r9f.delta.lz4',
}
class Queries:
 def __init__(self,recovery,token):self.r=recovery;self.token=token;self.serial=0
 def run(self,name,key):
  need(self.r.state=='shell_confirmed','No shell permission');need(key in QUERIES,'Query not on fixed read-only list');self.serial+=1
  marker=f'__REC_{self.token}_{self.serial}:';cmd=QUERIES[key]+f'; printf "\\n{marker}%s__\\n" "$?"\n';data=bytearray()
  try:
   for ch in cmd.encode():need(self.r.uart.write(bytes([ch]))==1,'Partial query write');self.r.sleep(.025);data.extend(self.r.uart.read(4096,.002));need(len(data)<65536,'Query overflow')
   deadline=self.r.clock()+90;pattern=re.compile(rb'^'+marker.encode()+rb'([0-9]+)__\r?\n',re.M)
   while self.r.clock()<deadline:
    match=pattern.findall(data)
    if match:need(match==[b'0'],'Query failed or duplicate return');return bytes(data)
    data.extend(self.r.uart.read(4096,.05));need(len(data)<65536,'Query overflow')
   raise Refused('Read-only query timed out')
  finally:(self.r.out/(name+'.log')).write_bytes(data)
def claim_once(path,record):
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'w') as f:json.dump(record,f);f.write('\n');f.flush();os.fsync(f.fileno())
def inspect(recovery):
 q=Queries(recovery,os.urandom(8).hex());result={}
 result['identity_before']=identity(q.run('identity_before','identity'));system=q.run('system','system')
 need(re.search(rb'^'+KERNEL.encode()+rb'\r?$',system,re.M),'Kernel changed');need(b'tmpfs /tmp tmpfs ' in system,'Unexpected /tmp filesystem');result['kernel']=KERNEL
 result['save_before']=save(q.run('save_before','save'));first=gpu(q.run('gpu_before','gpu'));recovery.sleep(3);second=gpu(q.run('gpu_after','gpu'));delta=(second['presents']-first['presents'])&0xffffffff;need(0<delta<100000,'No bounded GPU progression');result['gpu']={'before':first,'after':second,'presents_delta':delta}
 raw=q.run('space','space');rows=[x.split() for x in raw.replace(b'\r',b'').splitlines() if x.split() and x.split()[-1]==b'/tmp'];need(len(rows)==1 and len(rows[0])==6 and all(x.isdigit() for x in rows[0][1:4]),'Unexpected df');result['tmp_available_kib']=int(rows[0][3])
 raw=q.run('partial','partial');matches=re.findall(rb'^\s*(\d+) /tmp/festival-r9f\.delta\.lz4\r?$',raw,re.M);need(len(matches)==1,'Partial delta size unavailable');result['failed_delta_bytes']=int(matches[0]);result['failed_delta_reusable']=False
 result['identity_after']=identity(q.run('identity_after','identity'));result['save_after']=save(q.run('save_after','save'));return result
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--run',action='store_true');ap.add_argument('--expected-manifest');ap.add_argument('--review',type=Path);ap.add_argument('--out',type=Path);a=ap.parse_args();m,digest=preflight(HERE,a.expected_manifest)
 if not a.run:print(json.dumps({'prepared':True,'hardware':False,'manifest_sha256':digest}));return 0
 need(a.expected_manifest and a.review and a.out,'Run needs explicit manifest/review/new output');review=json.loads(a.review.read_text());check_review(review,digest,socket.gethostname().split('.')[0],time.time());a.out.mkdir(parents=True,exist_ok=False)
 result={'passed':False,'hardware':True,'manifest_sha256':digest,'review_sha256':sha(a.review),'stop_gm1':False,'relaunch_gm1':False,'fpga_writes':0,'sd_writes':0,'save_writes':0,'failed_delta_reusable':False};uart=None;recovery=None
 def interrupted(number,frame):raise InterruptedError('Signal '+str(number))
 for number in (signal.SIGTERM,signal.SIGHUP,signal.SIGINT):signal.signal(number,interrupted)
 try:
  with open(LOCK,'a+') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   st=os.stat(PORT);need(stat.S_ISCHR(st.st_mode),'Port is not a character device')
   owner=subprocess.run(['fuser',PORT],capture_output=True);need(owner.returncode==1 and not owner.stdout.strip() and not owner.stderr.strip(),'UART busy or ownership query failed')
   try:
    uart=UART(PORT);recovery=Recovery(uart,a.out,claim=lambda:claim_once(CLAIM,{'manifest_sha256':digest,'review_sha256':sha(a.review),'attempt_unix':time.time(),'r6_manifest_sha256':R6_SHA}));result['recovery']=recovery.record;recovery.run();result['preservation']=inspect(recovery);result['passed']=True
   finally:
    if uart:uart.close();uart=None # Close while diagnostic lock is still held.
 except BaseException as error:result['error']=repr(error);result['manual_review_required']=True
 finally:
  if recovery:result['state']=recovery.state;result['recovery']=recovery.record
  if uart:uart.close()
  (a.out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'passed':result['passed'],'output':str(a.out)}));return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
