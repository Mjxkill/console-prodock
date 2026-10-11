import sys,time,serial,json
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'tools'))
from check_gpu_reloads import wait_console
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
port,snap=wait_console();report={'passed':False,'physical_sd_writes':0,'usb':snap}
with serial.Serial(port,115200,timeout=.1,exclusive=True) as uart:
 try:
  for name,cmd in [('list','fatls mmc 0:0'),('read','fatload mmc 0:0 10000000 CONSOLE.TST'),('crc','crc32 10000000 40000')]:
   uart.reset_input_buffer();uart.write((cmd+'\n').encode());uart.flush();data=bytearray();start=time.monotonic()
   while time.monotonic()-start<45:
    data.extend(uart.read(4096))
    if data.endswith(b'PRODOCK => '):break
   (out/(name+'.log')).write_bytes(data);print(data.decode(errors='replace'),flush=True)
   if not data.endswith(b'PRODOCK => '):raise RuntimeError(name+' timeout')
   if name=='list' and b'console.tst' not in data.lower():raise RuntimeError('SD file absent')
   if name=='read' and b'262144 bytes read' not in data:raise RuntimeError('SD read failed')
   if name=='crc' and b'==>' not in data:raise RuntimeError('CRC unavailable')
   report[name+'_seconds']=time.monotonic()-start
  report['passed']=True
 finally:(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
