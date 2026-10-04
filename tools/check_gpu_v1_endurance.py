#!/usr/bin/env python3
"""Observe the three V1 GPU scenes with one CDC owner; fail on stalls/errors/re-enumeration."""
import argparse,json,re,time,hashlib,random,struct
from pathlib import Path
import serial
from serial.tools import list_ports
from check_gpu_console import response,test_v1
from check_gpu_reloads import console_snapshot

def echo_active(dev,payload):
    # The diagnostic CPU polls UART between frames. Four initial bytes fit its
    # RX FIFO; the first echoed byte proves it has entered the streaming loop.
    # Sending a whole block before that point could overflow the CPU UART while
    # it is waiting for a GPU frame, independently of USB packet correctness.
    dev.write(b'E'+struct.pack('<H',len(payload))+payload[:1])
    received=bytearray();deadline=time.monotonic()+5
    while not received and time.monotonic()<deadline:received.extend(dev.read(1))
    if received!=payload[:1]:return received
    dev.write(payload[1:])
    while len(received)<len(payload) and time.monotonic()<deadline:
        received.extend(dev.read(len(payload)-len(received)))
    return received

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--seconds',type=int,default=1800);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if not 30<=a.seconds<=7200:p.error('seconds must be 30..7200')
    ports=[p for p in list_ports.comports() if (p.vid,p.pid,p.serial_number)==(0x359f,0x2011,'11252024')]
    if len(ports)!=1:raise SystemExit('Expected exactly one Pro Dock console 11252024')
    usb=console_snapshot()
    if not usb or usb['speed_mbps']!=480:raise SystemExit('HS 480 Mbit/s required')
    a.out.mkdir(parents=True,exist_ok=False);results=[];start=None;rng=random.Random(0x5631)
    summary=dict(status='running',requested_seconds=a.seconds,port=ports[0].device,serial=ports[0].serial_number,
        usb=usb,usb_echo_bytes=0,tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),samples=results)
    (a.out/'test_tool.py').write_bytes(Path(__file__).read_bytes())
    summary['helper_sha256']={}
    for name in ('check_gpu_console.py','check_gpu_reloads.py'):
        source=(Path(__file__).parent/name).read_bytes()
        (a.out/name).write_bytes(source);summary['helper_sha256'][name]=hashlib.sha256(source).hexdigest()
    try:
        with serial.Serial(ports[0].device,115200,timeout=.2,exclusive=True) as dev:
            dev.write(b'c');response(dev,b'RASTER PAUSED');dev.write(b'?');identity=response(dev,b'MegaPro GPU')
            if b' V1 ' not in identity:raise RuntimeError('Wrong firmware')
            # Verify all deterministic poses before and after the endurance window.
            test_v1(dev);start=time.monotonic();last_scenes={};total_frames=0
            while time.monotonic()-start<a.seconds:
                line=response(dev,b'V1 BENCH',timeout=30)
                fields={k.decode():int(v) for k,v in re.findall(rb'(\w+)=(\d+)',line)}
                if fields['underflows'] or fields['rejected'] or fields['frames']!=120 or fields['line']>=2556:
                    raise RuntimeError('GPU error/load counter')
                # Echo handling intentionally occupies the diagnostic CPU loop.
                # Measure actual presentation intervals, but bound GPU drawing separately.
                if fields['gpu_max']>32000000:raise RuntimeError('GPU drawing exceeds 40 ms')
                if console_snapshot()!=usb:raise RuntimeError('USB identity/configuration changed during endurance')
                if len(results)%4==0:
                    size=(64,512,4096)[(len(results)//4)%3];payload=rng.randbytes(size)
                    received=echo_active(dev,payload)
                    if received!=payload:
                        (a.out/'echo_expected.bin').write_bytes(payload);(a.out/'echo_received.bin').write_bytes(received)
                        raise RuntimeError('USB binary echo mismatch while graphics active')
                    summary['usb_echo_bytes']+=size
                fields['elapsed']=round(time.monotonic()-start,3);results.append(fields)
                last_scenes[fields['scene']]=fields['elapsed'];total_frames+=fields['frames']
                if fields['elapsed']>40 and (set(last_scenes)!={0,1,2} or any(fields['elapsed']-t>40 for t in last_scenes.values())):
                    raise RuntimeError('Scene rotation stopped')
                (a.out/'result.json').write_text(json.dumps(summary,indent=2)+'\n')
            dev.write(b'c');response(dev,b'RASTER PAUSED');summary['elapsed_seconds']=time.monotonic()-start
            summary['total_frames']=total_frames;test_v1(dev)
            summary['status']='pass'
    except BaseException as e:
        summary['status']='fail';summary['error']=str(e);raise
    finally:(a.out/'result.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='samples'},indent=2))
if __name__=='__main__':main()
