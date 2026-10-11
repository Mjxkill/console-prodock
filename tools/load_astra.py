#!/usr/bin/env python3
"""ASTRA loader for ax15: HS -> volatile DDR, verified ILM -> J-Link, never SD.

Full asset loading requires USBDISK R4/C4b already running on C37. For later
program iterations use --firmware-only. No FPGA reset/rebuild/flash operation.
"""
import argparse,hashlib,json,struct,subprocess,time,zlib
from pathlib import Path
import serial
import usb.core,usb.util
from check_gpu_reloads import target_busdev,wait_console
from check_usb_disk import Disk,command,VID,PID
from check_usb_disk_faults import require_ddr
from load_ilm import identify_console,quiesce_console,require
ROOT=Path(__file__).resolve().parents[1]
C37='6f47a8cdab5857a0b652f791ff61fbed9a26c3c7ba7f4f30de01da95f0c076e2'
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--firmware-only',action='store_true');p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);pack=ROOT/'assets/astra/packed'
 meta=json.loads((pack/'firmware.json').read_text());assets=(pack/'astra.bin').read_bytes();fw=pack/'astra_fw.bin'
 require(hashlib.sha256(assets).hexdigest()==meta['assets_sha256'] and hashlib.sha256(fw.read_bytes()).hexdigest()==meta['sha256'],'Pack SHA mismatch')
 require(meta['fpga_sha256']==C37,'C37 ABI reference required')
 require(meta['load']==0xa0000000<=meta['entry']<meta['load']+fw.stat().st_size<=0xa0010000,'Invalid ILM image')
 magic,version,size,crc=struct.unpack_from('<4I',assets)
 require(magic==0x41535452 and version==1 and size==len(assets)<=0x2000000 and zlib.crc32(assets[1024:])==crc,'Invalid asset header/CRC')
 print('Target Pro Dock',target_busdev(),flush=True);port,snap=wait_console();require(snap['speed_mbps']==480,snap)
 report=dict(status='FAIL',usb=snap,physical_sd_writes=0,fpga_reloaded=False,firmware=meta,cleanup_errors=[])
 dev=None;claimed=False;uart=None
 try:
  dev=usb.core.find(idVendor=VID,idProduct=PID,bus=snap['bus'],address=snap['address']);require(dev is not None,'USB vanished')
  # Refuse to detach any MSC interface with a mounted block device. The USB
  # sysfs branch names the exact console bus/port, not another attached disk.
  for device in Path('/sys/bus/usb/devices').glob('*'):
   try:
    if int((device/'busnum').read_text())!=snap['bus'] or int((device/'devnum').read_text())!=snap['address']:continue
   except (OSError,ValueError):continue
   branch=device.resolve()
   mounted={line.split()[0] for line in Path('/proc/mounts').read_text().splitlines()}
   for block in Path('/sys/class/block').iterdir():
    if branch in block.resolve().parents:require('/dev/'+block.name not in mounted,'Mounted console SD: '+block.name)
  if dev.is_kernel_driver_active(2):dev.detach_kernel_driver(2)
  uart=serial.Serial(port,115200,timeout=.1,exclusive=True)
  identity,pause=identify_console(uart);(out/'identity.txt').write_bytes(identity)
  if not a.firmware_only:
   require(b'USBDISK R4 ' in identity and b'BOT_GUARD=1' in identity,'Load USBDISK R4/C4b before staging')
   usb.util.claim_interface(dev,2);claimed=True
   try:
    command(uart,'d','USBDISK MEDIA=DDR');disk=Disk(dev);require_ddr(uart,disk)
    padded=assets+bytes((-len(assets))%512);start=time.monotonic()
    for off in range(0,len(padded),65536):require(disk.write(off//512,padded[off:off+65536])==(0,0),'DDR write failed')
    report['write_seconds']=time.monotonic()-start;back=bytearray();start=time.monotonic()
    for off in range(0,len(padded),65536):
     length=min(65536,len(padded)-off);status,residue,data=disk.read(off//512,length//512)
     require(status==0 and residue==0 and len(data)==length,'DDR read failed');back.extend(data)
    require(bytes(back)==padded,'DDR readback mismatch');report['read_seconds']=time.monotonic()-start
    print('Assets staged and read back:',len(assets),'bytes',flush=True)
   finally:(out/'paused.txt').write_bytes(quiesce_console(uart,b'q'))
   usb.util.release_interface(dev,2);claimed=False
  else:(out/'paused.txt').write_bytes(quiesce_console(uart,pause))
  script=out/'load.jlink'
  script.write_text('\n'.join(['exec InhibitConnectRetries = 1','exec DisableFlashDL','exec DisableFlashBPs','exec SetAllowFlashCache = 0','connect','h','speed 1000',
    f'loadfile {fw} 0xa0000000 noreset',f'verifybin {fw} 0xa0000000',f'SetPC 0x{meta["entry"]:08x}','g','q'])+'\n')
  with (out/'jlink.log').open('w') as log:
   result=subprocess.run(['JLinkExe','-SelectEmuBySN','506005083','-Device','A25','-If','JTAG','-Speed','100','-JTAGConf','-1,-1','-NoGui','1','-ExitOnError','1','-CommanderScript',str(script)],stdout=log,stderr=subprocess.STDOUT,timeout=180)
  content=(out/'jlink.log').read_text();require(result.returncode==0 and 'Verify successful.' in content and 'Error:' not in content,content[-3000:])
  response=bytearray();limit=time.monotonic()+45
  while time.monotonic()<limit:
   response.extend(uart.read(4096))
   if b'ASTRA READY R1 ' in response:break
   require(b' FAIL' not in response and b' TRAP ' not in response,response)
  (out/'startup.txt').write_bytes(response);require(b'ASTRA READY R1 ' in response,response)
  print(response.decode(errors='replace'),flush=True);report['status']='PASS'
 except Exception as e:report['error']=str(e);raise
 finally:
  if uart is not None:uart.close()
  if dev is not None:
   try:
    if claimed:usb.util.release_interface(dev,2)
    # Bare-metal demo has no MSC server; keep the host interface detached.
    usb.util.dispose_resources(dev)
   except Exception as e:report['cleanup_errors'].append(str(e));report['status']='FAIL'
  (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 require(report['status']=='PASS',report)
if __name__=='__main__':main()
