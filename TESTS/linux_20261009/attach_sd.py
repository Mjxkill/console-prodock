import sys,time,serial,usb.core,usb.util
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'tools'))
from check_gpu_reloads import wait_console
from check_usb_disk import command,block_device
port,snap=wait_console()
if snap['speed_mbps']!=480:raise RuntimeError(snap)
with serial.Serial(port,115200,timeout=.1,exclusive=True) as s:
 print(command(s,'?','USBDISK R'),flush=True)
 status=command(s,'s','USBDISK MEDIA=')
 if not all(v in status for v in ('MEDIA=SD ','SERVING=1 ','HS=1 ')):raise RuntimeError(status)
 print(status,flush=True)
d=usb.core.find(idVendor=0x359f,idProduct=0x2011,bus=snap['bus'],address=snap['address'])
if d.serial_number!='11252024':raise RuntimeError('Wrong USB')
if not d.is_kernel_driver_active(2):d.attach_kernel_driver(2)
for _ in range(50):
 dev=block_device(d)
 if dev:print('BLOCK',dev,flush=True);break
 time.sleep(.2)
else:raise RuntimeError('No block device')
usb.util.dispose_resources(d)
