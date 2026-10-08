#!/usr/bin/env python3
"""Check exact autonomous scene poses and endurance, leave Orbital running."""
import argparse,json,re,struct,time
from pathlib import Path
import serial
from check_gpu_reloads import wait_console

def require(condition, detail):
    if not condition:
        raise RuntimeError(str(detail))

def healthy(d, max_cycles=None):
    require(all(d[k] == 0 for k in ('errors', 'uf', 'invalid', 'badsprite', 'rejected')), d)
    require(d['line'] < 2556, d)
    if max_cycles is not None:
        require(d['fx_max'] <= max_cycles, d)

def status(line):
    result={}
    for k,v in re.findall(r'(\w+)=(\w+)',line):result[k]=int(v,16 if k in ('hash','lcd','crc','crc565') else 10)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--expected',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--seconds',type=int,default=520,help='the loop lasts 240 s');p.add_argument('--start',type=int,default=0);p.add_argument('--min-fps',type=float,default=54.5,help='LCD refresh is 55.04 Hz; diagnostic echoes cost a few frames');p.add_argument('--max-cycles',type=int,default=13700000,help='800 MHz cycles per frame; one LCD period is 14.53 M (R6 measures 13.17 M at worst)');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    require(a.seconds > 0 and a.min_fps > 0 and a.max_cycles > 0, 'Paramètres de mesure invalides')
    poses=json.loads(a.expected.read_text());require(isinstance(poses,list) and poses, 'Aucune pose de référence')
    port,snapshot=wait_console();require(snapshot['speed_mbps']==480, snapshot)
    uart=serial.Serial(port,115200,timeout=.1,exclusive=True);transcript=bytearray()
    def cmd(data,marker=b'ORBITAL ',timeout=3):
        uart.write(data);uart.flush();answer=bytearray();limit=time.monotonic()+timeout
        while time.monotonic()<limit:
            answer.extend(uart.read(4096))
            if marker in answer and answer.endswith((b'\n',b'\r')):break
        transcript.extend(answer)
        if marker not in answer:raise RuntimeError(f'Missing response to {data!r}: {answer!r}')
        return answer.decode(errors='replace')
    records=[]
    try:
        uart.reset_input_buffer();require('ORBITAL R' in cmd(b'?'), 'Identité ORBITAL absente')
        cmd(b'P',b'ORBITAL PAUSED')
        for pose in poses:
            line=cmd(b'T'+struct.pack('<H',pose['frame']),b'ORBITAL frame=');d=status(line)
            field='lcd' if pose.get('mode')=='rgb565' else 'hash'
            require(d[field]==int(pose[field],16),(pose,d))
            if field=='lcd':require(d['crc565']==int(pose['crc565'],16),(pose,d))
            require(d['frame']==pose['frame'],d);healthy(d)
            records.append(d);print('POSE PASS',pose['frame'],pose[field],flush=True)
        cmd(b'T'+struct.pack('<H',a.start),b'ORBITAL frame=');cmd(b'G',b'ORBITAL AUTO')
        # La fenêtre englobe les deux interrogations : son débit est prudent,
        # même si la lecture série ou l'ordonnanceur du PC tarde à reprendre.
        start=time.monotonic();initial=status(cmd(b'S',b'ORBITAL frame='));healthy(initial)
        echo_bytes=0;samples=[];elapsed=0.0
        while time.monotonic()-start<a.seconds:
            time.sleep(5)
            # Short exact binary echoes while animation continues. <=64 bytes
            # avoids forcing a long blocked UART interval into a video benchmark.
            payload=bytes(((echo_bytes+i)*73+17)&255 for i in range(32))
            uart.write(b'E'+struct.pack('<H',len(payload))+payload);uart.flush();received=bytearray();deadline=time.monotonic()+2
            while len(received)<len(payload) and time.monotonic()<deadline:received.extend(uart.read(len(payload)-len(received)))
            require(bytes(received)==payload,(bytes(received),payload))
            echo_bytes+=len(payload)
            d=status(cmd(b'S',b'ORBITAL frame='));samples.append(d)
            healthy(d,a.max_cycles)
            previous=samples[-2] if len(samples)>1 else initial
            require(d['run']==1 and d['submitted']>previous['submitted'], ('Animation arrêtée ou mesure figée',d))
            require(d['uf_total']==initial['uf_total'], ('Sous-débordement pendant la mesure',d))
            elapsed=time.monotonic()-start
            print('AUTO',round(elapsed,1),d,flush=True)
        require(samples and elapsed>=a.seconds, 'Fenêtre de mesure incomplète')
        frames=samples[-1]['submitted']-initial['submitted'];fps=frames/elapsed
        require(fps>=a.min_fps, f'Débit insuffisant : {frames} images / {elapsed:.6f} s = {fps:.3f} fps < {a.min_fps}')
        # Do not leave a PASS artifact if restoring autoplay failed. Capture
        # its acknowledgement in the transcript before closing the UART.
        cmd(b'G',b'ORBITAL AUTO')
        result=dict(status='PASS',usb=snapshot,poses=records,samples=samples,seconds=elapsed,frames=frames,fps=fps,initial=initial,echo_bytes=echo_bytes,autoplay_restored=True)
        (a.out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    finally:
        (a.out/'usb.txt').write_bytes(transcript)
        uart.close()
if __name__=='__main__':main()
