"""Board acceptance after check_linux_desktop; no SD/flash writes."""
from pathlib import Path
import json,re,sys,time
import serial
sys.path.insert(0,'tools')
from check_gpu_reloads import wait_console
from check_linux import command
from check_linux_desktop import display
out=Path('TESTS/linux_desktop_20261011/interactive_r12');out.mkdir()
port,usb=wait_console();assert usb['speed_mbps']==480
report={'passed':False,'usb':usb,'physical_sd_writes':0,'interactive':[],'samples':[]}
with serial.Serial(port,115200,timeout=.03,exclusive=True) as uart:
 def run(name,cmd,seconds=30):
  rc,data=command(uart,cmd,seconds);(out/(name+'.log')).write_bytes(data)
  print(data.decode(errors='replace'),flush=True)
  assert rc==0,(name,rc)
  return data
 try:
  for name,keys in [('keys',b'aD\x1b[C\x1b[Dq'),('sigint',b'\x03')]:
   data=bytearray();uart.reset_input_buffer()
   for c in b'prodock-game\n':
    uart.write(bytes([c]));time.sleep(.03);data.extend(uart.read(4096))
   until=time.monotonic()+10
   while b'PRODOCK_GAME_START' not in data and time.monotonic()<until:data.extend(uart.read(4096))
   assert b'PRODOCK_GAME_START' in data
   time.sleep(.5)
   for c in keys:uart.write(bytes([c]));time.sleep(.1);data.extend(uart.read(4096))
   until=time.monotonic()+10
   while not re.search(rb'PRODOCK_GAME_DONE frames=\d+ score=\d+ status=0',data) and time.monotonic()<until:data.extend(uart.read(4096))
   (out/(name+'.log')).write_bytes(data)
   assert re.search(rb'PRODOCK_GAME_DONE frames=[1-9]\d* score=\d+ status=0',data),repr(data[-1000:])
   run(name+'_shell','printf "INTERACTIVE_SHELL_RESTORED\\n"')
   report['interactive'].append(name)
  run('layout','prodockctl layout split')
  run('start_demo','prodock-game --demo > /tmp/desktop-demo.log & echo $! > /tmp/desktop-demo.pid')
  run('welcome','printf "\\nJEU GPU + TERMINAL LINUX + DIAGNOSTICS\\nprodockctl layout game / console / split\\n"')
  first=display(run('before','prodockctl display'));start=time.monotonic()
  print('DESKTOP_VISIBLE_ENDURANCE_STARTED',flush=True)
  for i in range(6):
   time.sleep(20)
   s=display(run('sample_'+str(i),'prodockctl display'));elapsed=time.monotonic()-start
   sample={'elapsed':elapsed,**s};report['samples'].append(sample)
   assert not(s['errors'] or s['fault'] or s['invalid'] or s['sprites'])
   assert s['uf']==first['uf'] and s['line']<2556
   assert s['usb']&0xe0==0x60
   assert ((s['done']-first['done'])&65535)==((s['sent']-first['sent'])&65535)
   assert s['text']>first['text'] and s['presents']>first['presents']
  report.update(before=first,final=s,seconds=elapsed,
   fps=(s['presents']-first['presents'])/elapsed,commands=s['sent']-first['sent'])
  assert report['fps']>=45,report
  report['passed']=True
 except Exception as error:
  report['error']=str(error)
  raise
 finally:
  (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2),flush=True)
