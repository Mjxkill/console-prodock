#!/usr/bin/env python3
"""Run on ax15: volatile files + userspace trial on the restored Pro Dock.

Never flashes, accesses JTAG, writes SD, or reloads FPGA/kernel. Acquires the
diagnostic lock and exclusive CDC. NEBULA is stopped only after all transfers
are verified, and restarted on any failure or after a bounded benchmark.
"""
import argparse,fcntl,hashlib,json,os,re,struct,sys,time,zlib
from pathlib import Path
import serial
REFERENCE='fbbea9c357d0c4d5b33c3c4a7e54f9ed0ff8e31cc3fad1ac9dc1771f8e8cba5f'
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('/home/michael/console-validation-20261001'));p.add_argument('--bundle',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--leave-running',action='store_true');p.add_argument('--reuse-bootstrap',action='store_true');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 lock=open('/tmp/prodock-diagnostic.lock','a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 sys.path.insert(0,str(a.root/'tools'));from check_linux import command
 fs=a.root/'tang/impl/gpu_geometry_g22r0/impl/pnr/console_gpu_geometry_g22r0.fs';assert hashlib.sha256(fs.read_bytes()).hexdigest()==REFERENCE
 report={'board':'Tang Mega 138K Pro Dock','serial':'11252024','reference_fpga_sha256':REFERENCE,'runtime_bitstream_identity':'continuity from documented G22r0 restoration; no runtime hash register','physical_sd_writes':0,'fpga_writes':0,'kernel_writes':0,'transfers':[],'passed':False}
 stopped=False;receiver_active=False
 with serial.Serial('/dev/serial/by-id/usb-Electrosens_MegaPro_Console_11252024-if00',115200,timeout=.1,exclusive=True) as uart:
  def run(name,cmd,timeout=60):
   rc,data=command(uart,cmd,timeout);(a.out/(name+'.log')).write_bytes(data)
   if rc:raise RuntimeError((name,rc,data[-2000:]))
   return data
  def sendline(cmd,delay=.002):
   for b in (cmd+'\n').encode():uart.write(bytes([b]));time.sleep(delay)
  def marker(marker,seconds=10):
   data=bytearray();deadline=time.monotonic()+seconds
   while time.monotonic()<deadline:
    data.extend(uart.read(4096))
    if marker in data:return bytes(data)
   raise TimeoutError(repr(data[-2000:]))
  def ack(seconds=.5):
   deadline=time.monotonic()+seconds;b=bytearray()
   while time.monotonic()<deadline:
    b.extend(uart.read(5-len(b)))
    if len(b)==5:return b[0],struct.unpack('<I',b[1:])[0]
   raise TimeoutError('Transport ack '+repr(b))
  try:
   uart.write(b'\n');time.sleep(.2);uart.read(16000)
   state=run('before','uname -a; prodockctl display; ps; cat /tmp/nebula.pid')
   assert b'6.12.112-prodock' in state and b'errors=0 uf=0' in state and b'fault=0' in state,state
   payload=(a.bundle/'uart-receiver').read_bytes()
   # Shell strings contain only octal escapes. The ELF is read back in full
   # before execution; corrupted text input cannot execute arbitrary payload.
   uart.reset_input_buffer()
   for i in ([] if a.reuse_bootstrap else range(0,len(payload),96)):
    part=payload[i:i+96];escaped=''.join('\\%03o'%c for c in part);sendline("printf '"+escaped+"' "+('>' if i==0 else '>>')+' /tmp/luma-rx; echo __RX_CHUNK__')
    marker(b'\r\n__RX_CHUNK__\r\n')
   data=run('bootstrap_readback','od -b -v /tmp/luma-rx')
   lines=data.replace(b'\r',b'').splitlines();octets=[]
   for line in lines:
    if re.fullmatch(rb'[0-7]{7,} (?:[0-7]{3} ?){1,16}',line.strip()):octets.extend(int(x,8) for x in line.split()[1:])
   assert bytes(octets)==payload,'Bootstrap readback mismatch; executable not launched'
   run('bootstrap_mode','chmod 700 /tmp/luma-rx')
   for name,target in [('luma-riscv','/tmp/luma-riscv'),('luma.lz4','/tmp/luma.lz4'),('world_00.lz4','/tmp/world_00.lz4')]:
    blob=(a.bundle/name).read_bytes();uart.reset_input_buffer();sendline('/tmp/luma-rx '+target);receiver_active=True;marker(b'R\0\0\0\0');start=time.monotonic();retries=0;seq=0
    for off in range(0,len(blob),512):
     block=blob[off:off+512];packet=struct.pack('<4sIII',b'LMA1',seq,len(block),zlib.crc32(block))+block
     for attempt in range(12):
      for off2 in range(0,len(packet),16):uart.write(packet[off2:off2+16]);uart.flush();time.sleep(.002)
      try:code,n=ack()
      except TimeoutError:code,n=0,0
      if code==ord('A') and n==seq:break
      retries+=1
     else:raise RuntimeError(('serial block rejected',name,seq,code,n))
     seq+=1
     if seq%256==0:print(f'{name}: {off+len(block)}/{len(blob)} bytes, retries={retries}',flush=True)
    uart.write(struct.pack('<4sIII',b'LMA1',seq,0,zlib.crc32(blob)));uart.flush();code,n=ack();assert code==ord('D') and n==len(blob),(code,n)
    receiver_active=False;time.sleep(.3);uart.read(4096);report['transfers'].append({'name':name,'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),'crc32':'%08x'%zlib.crc32(blob),'retries':retries,'seconds':time.monotonic()-start});print('TRANSFER',report['transfers'][-1],flush=True)
   run('stop_nebula','p=`cat /tmp/nebula.pid`; test "`cat /proc/$p/comm`" = nebula && kill -TERM "$p" && sleep 1 && test ! -d /proc/$p',20);stopped=True
   run('gpu_before','prodockctl info; prodockctl display')
   run('start_benchmark','/tmp/luma-riscv --demo --no-save --frames 600 > /tmp/luma-trial.log 2>&1 & echo $! > /tmp/luma-trial.pid')
   done=False
   for i in range(30):
    time.sleep(2);data=run('poll_%02d'%i,'cat /tmp/luma-trial.log; p=`cat /tmp/luma-trial.pid`; if test -d /proc/$p; then echo LUMA_RUNNING; else wait $p; echo LUMA_EXIT:$?; fi',20)
    if b'LUMA_RESULT' in data:done=True;break
    if re.search(rb'^LUMA_EXIT:\d+\r?$',data,re.M):raise RuntimeError(('LUMA exited before result',data))
    print('Waiting for LUMA resource upload / benchmark',i,flush=True)
   assert done,'LUMA benchmark did not finish'
   assert re.search(rb'LUMA_RESULT .* status=0\r?$',data,re.M),data
   rate=re.search(rb'LUMA_RATE frames=600 seconds=([0-9.]+) fps=([0-9.]+) updates=(\d+) commands=(\d+) max_sprites=(\d+)',data);assert rate,data
   report['benchmark']={'frames':600,'seconds':float(rate[1]),'fps':float(rate[2]),'updates':int(rate[3]),'commands':int(rate[4]),'max_sprites':int(rate[5])}
   after=run('gpu_after','prodockctl info; prodockctl display');assert b'errors=0 uf=0' in after and b'fault=0' in after,after
   if a.leave_running:
    run('leave_game','/tmp/luma-riscv --demo --no-save > /tmp/luma-live.log 2>&1 & echo $! > /tmp/luma-live.pid');stopped=False;report['left_running']='LUMA automatic benchmark movement; interactive console can be attached separately'
   else:
    run('restore_nebula','nebula --demo > /tmp/nebula.log 2>&1 & echo $! > /tmp/nebula.pid');time.sleep(5);run('verify_nebula','p=`cat /tmp/nebula.pid`; test "`cat /proc/$p/comm`" = nebula && cat /tmp/nebula.log && prodockctl display');stopped=False;report['left_running']='NEBULA reference demo, process verified after 5 seconds'
   report['passed']=True
  finally:
   if receiver_active:
    for ch in struct.pack('<4sIII',b'LMA1',0,0,0):uart.write(bytes([ch]));uart.flush();time.sleep(.025)
    time.sleep(.5);(a.out/'receiver_abort.log').write_bytes(uart.read(4096))
   if stopped:
    try:
     run('failure_stop','p=`cat /tmp/luma-trial.pid`; test "`cat /proc/$p/comm`" != luma-riscv || kill -TERM "$p"; n=0; while test -d /proc/$p && test $n -lt 30; do sleep 1; n=$((n+1)); done; test ! -d /proc/$p',50)
     run('failure_restore','nebula --demo > /tmp/nebula.log 2>&1 & echo $! > /tmp/nebula.pid',20);time.sleep(5);run('failure_verified','p=`cat /tmp/nebula.pid`; test "`cat /proc/$p/comm`" = nebula && cat /tmp/nebula.log && prodockctl display')
    except Exception as e:report['restore_error']=repr(e)
   (a.out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':main()
