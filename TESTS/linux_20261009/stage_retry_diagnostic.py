import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'tools'))
import stage_linux,check_usb_disk_faults
from check_usb_disk import command,Fail

def retry(port,text,expect,timeout=3.0):
    assert text in ('?','s','d')
    for attempt in range(5):
        try:return command(port,text,expect,timeout)
        except Fail as e:
            print('CDC_RETRY',attempt+1,repr(str(e)),flush=True)
    raise RuntimeError('No complete CDC acknowledgment')
stage_linux.command=retry
check_usb_disk_faults.command=retry
stage_linux.main()
