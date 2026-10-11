#!/usr/bin/env python3
"""Qualifie U-Boot en RAM, sans écrire la SD/flash ; firmware bare-metal au repos requis."""
import argparse,hashlib,json,struct,subprocess,time,zlib
from pathlib import Path
import serial
from check_gpu_reloads import target_busdev,wait_console
from load_ilm import identify_console,quiesce_console,require

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--pack',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
 a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
 pack=a.pack.resolve();im=(pack/'PRODOCK/UBOOT.BIN').read_bytes();launcher=pack/'uboot_ram.bin'
 meta=json.loads((pack/'uboot_ram.json').read_text())
 require(hashlib.sha256(im).hexdigest()==meta['image_sha256'],'U-Boot SHA mismatch')
 require(hashlib.sha256(launcher.read_bytes()).hexdigest()==meta['launcher_sha256'],'Launcher SHA mismatch')
 require(12<launcher.stat().st_size<=65536 and 40<len(im)<=40+0x800000,'Invalid size')
 fields=struct.unpack('<8I',im[8:40])
 require(im[:8]==b'PDCKBOOT' and fields[:4]==(1,1,0x6000000,0x6000000),'Invalid image target')
 require(fields[4]==len(im)-40 and fields[5]==zlib.crc32(im[40:]) and
         fields[6]==0x1ff and fields[7]==zlib.crc32(im[:36]),'Invalid image CRC/size/caps')
 raw=out/'u-boot.bin';raw.write_bytes(im[40:])
 print('Target Pro Dock',target_busdev(),flush=True)
 port,snap=wait_console();require(snap['speed_mbps']==480,snap)
 with serial.Serial(port,115200,timeout=.1,exclusive=True) as uart:
  identity,pause=identify_console(uart);(out/'before.log').write_bytes(identity)
  (out/'paused.log').write_bytes(quiesce_console(uart,pause))
  script=out/'load.jlink'
  script.write_text('\n'.join(['exec InhibitConnectRetries = 1','exec DisableFlashDL','exec DisableFlashBPs',
   'exec SetAllowFlashCache = 0','connect','h','speed 1000',f'loadfile {raw} 0x06000000 noreset',
   f'loadfile {launcher} 0xa0000000 noreset',f'verifybin {launcher} 0xa0000000','SetPC 0xa000000c','g','q'])+'\n')
  with (out/'jlink.log').open('w') as log:
   result=subprocess.run(['JLinkExe','-SelectEmuBySN','506005083','-Device','A25','-If','JTAG','-Speed','100',
    '-JTAGConf','-1,-1','-NoGui','1','-ExitOnError','1','-CommanderScript',str(script)],stdout=log,stderr=subprocess.STDOUT,timeout=180)
  log=(out/'jlink.log').read_text();require(result.returncode==0 and 'Verify successful.' in log and 'Error:' not in log,'J-Link failed')
  data=bytearray();end=time.monotonic()+45
  while time.monotonic()<end:
   part=uart.read(4096);data.extend(part)
   if part:print(part.decode(errors='replace'),end='',flush=True)
   if b'PRODOCK => ' in data:break
  (out/'console.log').write_bytes(data)
  passed=all(mark in data for mark in (b'PRODOCK UBOOT RAM: CRC OK',b'U-Boot 2025.10',b'PRODOCK => '))
  (out/'result.json').write_text(json.dumps({'passed':passed,'boot_only':True,'physical_sd_writes':0,'usb':snap,'image':meta},indent=2)+'\n')
  require(passed,'U-Boot boot not confirmed')
if __name__=='__main__':main()
