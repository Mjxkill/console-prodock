import json,serial,struct,time,sys
port='/dev/serial/by-id/usb-Electrosens_MegaPro_Console_11252024-if00'
with serial.Serial(port,115200,timeout=.1,exclusive=True) as s:
 def cmd(b):
  s.write(b);s.flush();a=bytearray();end=time.monotonic()+4
  while time.monotonic()<end:
   a.extend(s.read(4096))
   if a.endswith((b'\n',b'\r')):break
  if not a:raise RuntimeError('No response')
  print(a.decode(errors='replace').strip(),flush=True)
 cmd(b'P')
 for t in [100,700,1200,2200,4300,5250,5700,6100,7560,7980,8650,9500,11200,12700,13500,14200,14400,15000,16000]:cmd(b'T'+struct.pack('<H',t))
 cmd(b'R')
