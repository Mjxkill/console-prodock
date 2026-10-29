"""Exact selected helpers from frozen R6 recovery; no entry point."""
import os,fcntl,termios,select,re,hashlib
SAVE_SHA="2138ac0ad21a4707aad2dc0613381e3bde131acfa783dbb29a43f4d6a4c08cc6"
PROMPT=b"prodock# "
class Refused(RuntimeError):pass
def need(condition,message):
 if not condition:raise Refused(message)
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
def save(raw):
 blob=octets(raw,5292);need(len(blob)==5292 and hashlib.sha256(blob).hexdigest()==SAVE_SHA,'GM1 save changed');return {'bytes':len(blob),'sha256':SAVE_SHA}
def gpu(raw):
 lines=re.findall(rb'^DISPLAY [^\r\n]+',raw,re.M);need(len(lines)==1,'Missing GPU display status');line=lines[0];d={k.decode():int(v) for k,v in re.findall(rb'\b(errors|uf|invalid|sprites|fault|presents)=(\d+)\b',line)}
 need(set(d)=={'errors','uf','invalid','sprites','fault','presents'} and not any(d[k] for k in d if k!='presents'),'GPU error counters nonzero');return d
