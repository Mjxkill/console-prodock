#!/usr/bin/env python3
"""One bounded native G3D oracle on the already booted candidate; RAM only."""
import argparse,fcntl,hashlib,json,re,sys,time
from pathlib import Path
import serial
from prodock_transport import Transport,RECEIVER_SHA
RELEASE=b'6.12.112-prodock-luma3d-g3d1-r1'
PROBE_SHA='199228183cab92fa532ddddc7fc5193048fd2b97ec6cb56baf596da8ccd72fdc'
PORT='/dev/serial/by-id/usb-Electrosens_MegaPro_Console_11252024-if00'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def display(data):
    lines=re.findall(rb'^DISPLAY [^\r\n]+',data,re.M);assert len(lines)==1
    values={k.decode():int(v) for k,v in re.findall(rb'\b(errors|uf|invalid|sprites|fault)=(\d+)\b',lines[0])}
    assert set(values)=={'errors','uf','invalid','sprites','fault'} and not any(values.values()),values
    return values
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--bundle',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    assert sha(a.bundle/'geometry-probe')==PROBE_SHA and sha(a.bundle/'uart-receiver')==RECEIVER_SHA
    a.out.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(a.root/'tools'));from check_linux import command
    report={'passed':False,'probe_sha256':PROBE_SHA,'controller_sha256':sha(Path(__file__)),
            'fpga':'G22r0 continuity; unchanged since warm_boot trial_resume_r2',
            'fpga_writes':0,'sd_writes':0,'flash_writes':0,'scope':'Two deterministic geometry fixtures, not gameplay or FPS'}
    with open('/tmp/prodock-diagnostic.lock','a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            with serial.Serial(PORT,115200,timeout=.1,exclusive=True) as uart:
                uart.write(b'\n');time.sleep(.2);uart.read(16000);tx=Transport(uart,command,a.out)
                before=tx.run('before','uname -r; prodockctl info; prodockctl display; cat /proc/mounts')
                assert re.search(rb'^'+RELEASE+rb'\r?$',before,re.M)
                assert b'tmpfs /tmp tmpfs ' in before and not re.search(rb'^/dev/mmc\S* ',before,re.M)
                assert b'GPU ABI=1 caps=000001ff DDR=00800000+90177536 ' in before
                report['before']=display(before)
                tx.bootstrap(a.bundle/'uart-receiver')
                report['transfer']=tx.transfer(a.bundle/'geometry-probe','luma3d-probe')
                result=tx.run('probe','chmod 700 /tmp/luma3d-probe && /tmp/luma3d-probe',60)
                assert b'LUMA3D_GEOMETRY_OK phases=2 pixels=294 vertices=24 triangles=8 culled=4 errors=0 uf=0 invalid=0 sprites=0 fault=0' in result
                assert b'phase=0 pixels=147 depth=49150 commands=22' in result
                assert b'phase=1 pixels=147 depth=57342 commands=22' in result
                report['after']=display(tx.run('after','prodockctl display; prodockctl info'))
                report['passed']=True
        except BaseException as error:
            report['error']=repr(error);raise
        finally:
            (a.out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
