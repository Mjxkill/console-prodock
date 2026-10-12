from pathlib import Path
import sys,time,subprocess
sys.path.insert(0,'tools')
import serial
from check_gpu_reloads import wait_console
from check_linux import command
out=Path('TESTS/nebula_20261012')
out.mkdir(parents=True,exist_ok=True)
port,usb=wait_console()
assert usb['speed_mbps']==480
with serial.Serial(port,115200,timeout=.15,exclusive=True) as uart:
 uart.reset_input_buffer()
 for c in b'sync; poweroff -f\n':uart.write(bytes([c]));time.sleep(.035)
 received=b''; deadline=time.monotonic()+30
 while time.monotonic()<deadline:
  received+=uart.read(4096)
  if b'System halted' in received:break
 (out/'shutdown_r15.log').write_bytes(received)
 assert b'System halted' in received,repr(received[-2000:])
for name,args in [
 ('disk_r16',['python3','tools/load_linux_disk.py','--fs','tang/impl/gpu_geometry_g22r0/impl/pnr/console_gpu_geometry_g22r0.fs','--bin','linux/usbdisk_c4b.bin','--entry','0xa000000c','--expect','USBDISK READY R4','--out',str(out/'disk_r16')]),
 ('boot_r16',['python3','tools/load_linux.py','--pack','linux/nebula_r16','--packed','--jtag-speed','4000','--out',str(out/'boot_r16')])]:
 print(name,flush=True)
 with (out/(name+'_command.log')).open('w') as log:subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,check=True)
