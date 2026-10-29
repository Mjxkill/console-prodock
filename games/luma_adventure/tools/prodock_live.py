#!/usr/bin/env python3
"""Leave the already tested LUMA game visible, per the user's live-demo request.
No transfer, FPGA, kernel or SD access. Successful starts deliberately keep LUMA.
"""
import argparse,fcntl,hashlib,json,re,sys,time
from pathlib import Path
import serial
REFERENCE='fbbea9c357d0c4d5b33c3c4a7e54f9ed0ff8e31cc3fad1ac9dc1771f8e8cba5f'
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('/home/michael/console-validation-20261001'));p.add_argument('--proof',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--world',type=int,required=True);p.add_argument('--previous',choices=['nebula','luma'],default='nebula');a=p.parse_args();assert 0<=a.world<36;a.out.mkdir(parents=True,exist_ok=False)
 proof=json.loads(a.proof.read_text());assert proof['passed'] and proof['reference_fpga_sha256']==REFERENCE
 entries={e['name']:e for e in proof['transfers']};required=['luma-riscv','luma.lz4',f'world_{a.world:02d}.lz4'];assert all(n in entries for n in required)
 assert entries['luma-riscv']['sha256']=='23f096f081d81d958a81f911a9b30441d51f27f0e377f10682f0bd7024ad7218'
 assert hashlib.sha256((a.root/'tang/impl/gpu_geometry_g22r0/impl/pnr/console_gpu_geometry_g22r0.fs').read_bytes()).hexdigest()==REFERENCE
 lock=open('/tmp/prodock-diagnostic.lock','a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 sys.path.insert(0,str(a.root/'tools'));from check_linux import command
 report={'passed':False,'world':a.world,'mode':'existing --demo: automatic movement and archery, no progression injection','saving':False,'fpga_kernel_sd_writes':0,'proof_sha256':hashlib.sha256(a.proof.read_bytes()).hexdigest(),'resources':{n:entries[n] for n in required},'user_preference':'leave LUMA running after a successful demonstration; do not restore NEBULA'}
 with serial.Serial('/dev/serial/by-id/usb-Electrosens_MegaPro_Console_11252024-if00',115200,timeout=.1,exclusive=True) as uart:
  def run(name,cmd):
   rc,data=command(uart,cmd,45);(a.out/(name+'.log')).write_bytes(data)
   if rc:raise RuntimeError((name,rc,data[-1000:]))
   return data
  try:
   uart.write(b'\n');time.sleep(.2);uart.read(16000)
   before=run('before','uname -a; prodockctl display; ps; cat /proc/mounts');assert b'6.12.112-prodock' in before and b'tmpfs /tmp tmpfs ' in before
   run('resource_presence',' && '.join('test -s /tmp/'+n for n in required))
   report['reuse']='Files unchanged since R9b CRC-verified transfer. The game revalidates pack lengths/CRCs on load; no new target SHA readback.'
   pidfile='/tmp/nebula.pid' if a.previous=='nebula' else '/tmp/luma-live.pid';comm='nebula' if a.previous=='nebula' else 'luma-riscv'
   run('stop_previous','p=`cat '+pidfile+'`; test "`cat /proc/$p/comm`" = '+comm+' && kill -TERM "$p" && sleep 1 && test ! -d /proc/$p')
   info=run('gpu_before','prodockctl info; prodockctl display');assert b'GPU ABI=1 caps=000001ff DDR=00800000+90177536 ' in info
   run('launch','/tmp/luma-riscv --demo --no-save --world '+str(a.world)+' > /tmp/luma-live.log 2>&1 & echo $! > /tmp/luma-live.pid; echo '+str(a.world)+' > /tmp/luma-live.world')
   for attempt in range(6):
    time.sleep(5);data=run('startup_'+str(attempt),'p=`cat /tmp/luma-live.pid`; test "`cat /proc/$p/comm`" = luma-riscv && cat /tmp/luma-live.log && prodockctl display')
    if b'LUMA_START worlds=36 mode=benchmark board=800x480 ' in data:break
   else:raise RuntimeError('LUMA startup not confirmed')
   assert ('LUMA_LOAD file=/tmp/world_%02d.lz4'%a.world).encode() in data
   time.sleep(5);final=run('verify_live','p=`cat /tmp/luma-live.pid`; test "`cat /proc/$p/comm`" = luma-riscv && cat /tmp/luma-live.pid && prodockctl display')
   line=re.findall(rb'^DISPLAY [^\r\n]+',final,re.M);assert len(line)==1
   counters={k.decode():int(v) for k,v in re.findall(rb'\b(errors|uf|invalid|sprites|fault)=(\d+)\b',line[0])};assert len(counters)==5 and not any(counters.values()),counters
   report['display']=counters;report['pid']=int(re.search(rb'^([0-9]+)\r?$',final,re.M)[1]);report['passed']=True;report['left_running']='LUMA';report['serial_lock_released_on_exit']=True
  finally:(a.out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':main()
