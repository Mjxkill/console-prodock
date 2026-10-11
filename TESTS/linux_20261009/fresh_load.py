import sys,usb.core,usb.util
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'tools'))
import load_ilm
original=load_ilm.wait_console
def wait(*args):
 port,snap=original(*args)
 if snap['speed_mbps']!=480:raise RuntimeError(snap)
 dev=usb.core.find(idVendor=0x359f,idProduct=0x2011,bus=snap['bus'],address=snap['address'])
 if dev.serial_number!='11252024':raise RuntimeError('Wrong console')
 if dev.is_kernel_driver_active(2):dev.detach_kernel_driver(2)
 usb.util.dispose_resources(dev)
 print('MSC detached for volatile Linux test',snap,flush=True)
 return port,snap
load_ilm.wait_console=wait
load_ilm.main()
