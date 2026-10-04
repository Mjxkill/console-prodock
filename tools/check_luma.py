#!/usr/bin/env python3
"""Check exact autonomous scene poses and endurance, leave Luma running."""
import argparse,json,re,struct,time
from pathlib import Path
import serial
from check_gpu_reloads import wait_console

def status(line):
    result={}
    for k,v in re.findall(r'(\w+)=(\w+)',line):result[k]=int(v,16 if k in ('hash','lcd','crc','crc565') else 10)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--expected',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--seconds',type=int,default=315);p.add_argument('--start',type=int,default=5120);p.add_argument('--min-fps',type=int,default=50);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    port,snapshot=wait_console();assert snapshot['speed_mbps']==480
    uart=serial.Serial(port,115200,timeout=.1,exclusive=True);transcript=bytearray()
    def cmd(data,marker=b'LUMA ',timeout=3):
        uart.write(data);uart.flush();answer=bytearray();limit=time.monotonic()+timeout
        while time.monotonic()<limit:
            answer.extend(uart.read(4096))
            if marker in answer and answer.endswith((b'\n',b'\r')):break
        transcript.extend(answer)
        if marker not in answer:raise RuntimeError(f'Missing response to {data!r}: {answer!r}')
        return answer.decode(errors='replace')
    records=[];passed=False
    try:
        uart.reset_input_buffer();assert 'LUMA R' in cmd(b'?')
        cmd(b'P')
        for pose in json.loads(a.expected.read_text()):
            line=cmd(b'T'+struct.pack('<H',pose['frame']),b'LUMA frame=');d=status(line)
            field='lcd' if pose.get('mode')=='rgb565' else 'hash'
            assert d[field]==int(pose[field],16),(pose,d)
            if field=='lcd':assert d['crc565']==int(pose['crc565'],16),(pose,d)
            assert d['frame']==pose['frame'] and d['errors']==0 and d['uf']==0 and d['invalid']==0 and d['badsprite']==0,d
            assert d['line']<2556,d
            assert d.get('rejected',0)==0,d
            records.append(d);print('POSE PASS',pose['frame'],pose[field],flush=True)
        cmd(b'T'+struct.pack('<H',a.start),b'LUMA frame=');cmd(b'G');start=time.monotonic();echo_bytes=0;samples=[]
        while time.monotonic()-start<a.seconds:
            time.sleep(5)
            # Short exact binary echoes while animation continues. <=64 bytes
            # avoids forcing a long blocked UART interval into a video benchmark.
            payload=bytes(((echo_bytes+i)*73+17)&255 for i in range(32))
            uart.write(b'E'+struct.pack('<H',len(payload))+payload);uart.flush();received=bytearray();deadline=time.monotonic()+2
            while len(received)<len(payload) and time.monotonic()<deadline:received.extend(uart.read(len(payload)-len(received)))
            assert bytes(received)==payload,(bytes(received),payload)
            echo_bytes+=len(payload)
            d=status(cmd(b'S',b'LUMA frame='));samples.append(d)
            assert d['errors']==0 and d['uf']==0 and d['invalid']==0 and d['badsprite']==0 and d['line']<2556,d
            print('AUTO',round(time.monotonic()-start,1),d,flush=True)
        assert samples and samples[-1]['submitted']>a.seconds*a.min_fps,samples[-1] if samples else 'no samples'
        passed=True
        result=dict(status='PASS',usb=snapshot,poses=records,samples=samples,seconds=time.monotonic()-start,echo_bytes=echo_bytes)
        (a.out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    finally:
        (a.out/'usb.txt').write_bytes(transcript)
        if passed:cmd(b'G')
        uart.close()
if __name__=='__main__':main()
