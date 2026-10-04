from pathlib import Path
import hashlib,json,re,subprocess,sys,time
import serial
root=Path('/home/michael/console-validation-20261001')
sys.path.insert(0,str(root/'tools'))
from check_gpu_reloads import target_busdev,console_snapshot,wait_console
stage=root/'tang/impl/gpu_l12_usb_hs33_cdc_r4'
fs=stage/'impl/pnr/console_gpu_l12_usb_hs33_cdc_r4.fs'
expected='28a83d1048e5ec80ed6c1b8c0b5c0c9894b8846a19124216a80fe6a1ff1f3f8d'
assert hashlib.sha256(fs.read_bytes()).hexdigest()==expected
out=root/'TESTS/gpu_l12_usb_hs33_cdc_r4_ddr_boot'
out.mkdir(exist_ok=False)
before=console_snapshot();target=target_busdev()
with (out/'loader.log').open('w') as f:
 subprocess.run([str(root/'bin/openFPGALoader'),'--busdev-num',target,'-b','tangmega138k','-m',str(fs)],stdout=f,stderr=subprocess.STDOUT,check=True,timeout=120)
port,device=wait_console(before)
assert device['speed_mbps']==480
(out/'device.json').write_text(json.dumps(dict(device=device,sha256=expected,target=target),indent=2))
with serial.Serial(port,115200,timeout=.1,write_timeout=2,exclusive=True) as d, (out/'uart.bin').open('wb') as f:
 d.reset_input_buffer();d.write(b'D')
 deadline=time.monotonic()+90;raw=bytearray()
 while time.monotonic()<deadline:
  chunk=d.read(min(4096,d.in_waiting) or 1)
  if chunk:
   raw+=chunk;f.write(chunk);f.flush();print(chunk.decode('ascii',errors='replace'),end='',flush=True)
   if b'DDR END' in raw and raw.endswith(b'\n'):break
 d.write(b'?');end=time.monotonic()+2
 while time.monotonic()<end:
  chunk=d.read(512)
  if chunk:raw+=chunk;f.write(chunk);print(chunk.decode('ascii',errors='replace'),end='',flush=True)
 result=dict(completed=b'DDR END errors=0' in raw,cpu_answers_after=b'MegaPro GPU' in raw,sha256=expected)
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(result,flush=True)
