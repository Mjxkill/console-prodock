import fcntl,sys,time
from pathlib import Path
import serial
root=Path('/home/michael/console-validation-20261001')
sys.path.insert(0,str(root/'tools'))
from check_linux import command
out=root/'games/luma_adventure/trial_20261024_r2/restore_verified'
out.mkdir(exist_ok=False)
lock=open('/tmp/prodock-diagnostic.lock','a+')
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
with serial.Serial('/dev/serial/by-id/usb-Electrosens_MegaPro_Console_11252024-if00',115200,timeout=.1,exclusive=True) as uart:
 def run(name,cmd,timeout=30):
  rc,data=command(uart,cmd,timeout);(out/(name+'.log')).write_bytes(data);print(data.decode(errors='replace'),flush=True);assert rc==0,(name,rc)
 run('state','cat /tmp/luma-trial.log; cat /tmp/nebula.log; ps; prodockctl info; prodockctl display')
 run('restore','nebula --demo > /tmp/nebula.log 2>&1 & echo $! > /tmp/nebula.pid')
 time.sleep(5)
 run('verified','p=`cat /tmp/nebula.pid`; test "`cat /proc/$p/comm`" = nebula && cat /tmp/nebula.log && prodockctl display')
