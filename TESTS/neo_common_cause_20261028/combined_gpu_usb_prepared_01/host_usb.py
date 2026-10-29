#!/usr/bin/env python3
"""Bounded sysfs inventory; at most one EP0 diagnostic on an explicitly bound HS path."""
import argparse,ctypes,fcntl,json,os,re,struct,time
from pathlib import Path
class Control(ctypes.Structure):
 _fields_=[('request_type',ctypes.c_uint8),('request',ctypes.c_uint8),('value',ctypes.c_uint16),('index',ctypes.c_uint16),('length',ctypes.c_uint16),('timeout',ctypes.c_uint32),('data',ctypes.c_void_p)]

def inventory(root=Path('/sys/bus/usb/devices')):
 result=[]
 for path in sorted(root.iterdir()):
  try:
   if (path/'idVendor').read_text().strip()!='359f' or (path/'idProduct').read_text().strip()!='2011' or (path/'serial').read_text().strip()!='11252024':continue
   fields={name:(path/name).read_text().strip() for name in ['idVendor','idProduct','serial','speed','busnum','devnum']}
   fields['path']=str(path);result.append(fields)
  except OSError:continue
 return result

def sample(allowed_path=None,root=Path('/sys/bus/usb/devices'),opener=os.open,ioctl=fcntl.ioctl,closer=os.close):
 devices=inventory(root);result=dict(devices=devices,host_time_ns=time.time_ns(),usb_io_attempted=False,hs_present=any(x['speed']=='480' for x in devices),diag_status='NO_DEVICE' if not devices else 'NOT_ATTEMPTED',physical_identity_not_attested=True)
 if len(devices)!=1:
  if devices:result['diag_status']='AMBIGUOUS'
  return result
 d=devices[0]
 if d['speed']!='480':result['diag_status']='NON_HS_REFUSED';return result
 if allowed_path is None or d['path']!=allowed_path:result['diag_status']='PATH_NOT_AUTHORIZED';return result
 if not re.fullmatch(r'/sys/bus/usb/devices/[0-9]+-[0-9]+(?:\.[0-9]+)*',allowed_path):raise ValueError('Unsafe allowed USB path')
 # Recheck identity immediately before opening; never detach/reset a device.
 if inventory(root)!=devices:raise ValueError('USB identity changed before transfer')
 bus,dev=int(d['busnum']),int(d['devnum'])
 if not(1<=bus<=999 and 1<=dev<=127):raise ValueError('Invalid USB node')
 fd=None
 try:
  fd=opener('/dev/bus/usb/%03d/%03d'%(bus,dev),os.O_RDWR|os.O_CLOEXEC)
  buf=ctypes.create_string_buffer(32);req=Control(0xa0,0x21,0xd1a6,0,32,1000,ctypes.addressof(buf))
  result['usb_io_attempted']=True
  size=ioctl(fd,0xc0005500|(ctypes.sizeof(Control)<<16),bytearray(bytes(req)))
  if size!=32:raise ValueError('EP0 diagnostic size '+str(size))
  result.update(diag_status='READ_32_BYTES',diag_hex=buf.raw.hex(),board_status_nibble=(struct.unpack('<8I',buf.raw)[4]>>28)&15)
 except (OSError,ValueError) as exc:result.update(diag_status='TRANSFER_FAILED',error=repr(exc))
 finally:
  if fd is not None:closer(fd)
 return result

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--allowed-path');a=p.parse_args();print(json.dumps(sample(a.allowed_path)))
if __name__=='__main__':main()
