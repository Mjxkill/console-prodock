#!/usr/bin/env python3
"""Diagnostic recovery after recorded OpenSBI AMOSWAP stall; RAM only."""
import sys,subprocess,time
from pathlib import Path
import serial
sys.path.insert(0,str(Path.cwd()/'tools'))
from check_gpu_reloads import target_busdev,wait_console
out=Path('TESTS/linux_atomic_20261009_r1');out.mkdir(exist_ok=False)
print('Target',target_busdev(),flush=True)
port,usb=wait_console()
if usb['speed_mbps']!=480:raise RuntimeError(usb)
with serial.Serial(port,115200,timeout=.2,exclusive=True) as uart:
 cmd=['exec InhibitConnectRetries = 1','exec DisableFlashDL','exec DisableFlashBPs','exec SetAllowFlashCache = 0',
      'connect','h','regs','speed 1000','loadfile /tmp/console_linux_atomic.bin 0xa0000000 noreset',
      'verifybin /tmp/console_linux_atomic.bin 0xa0000000','SetPC 0xa000000c','g','q']
 (out/'load.jlink').write_text('\n'.join(cmd)+'\n')
 with (out/'jlink.log').open('w') as log:
  subprocess.run(['JLinkExe','-SelectEmuBySN','506005083','-Device','A25','-If','JTAG','-Speed','100',
    '-JTAGConf','-1,-1','-NoGui','1','-ExitOnError','1','-CommanderScript',str(out/'load.jlink')],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=60)
 data=bytearray();deadline=time.monotonic()+20
 while time.monotonic()<deadline:
  data.extend(uart.read(4096))
  if b'PRODOCK PREFLIGHT READY' in data:break
 (out/'console.log').write_bytes(data);print(data.decode(errors='replace'))
