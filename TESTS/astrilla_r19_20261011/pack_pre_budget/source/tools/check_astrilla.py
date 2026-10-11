#!/usr/bin/env python3
"""Check exact autonomous scene poses and endurance, leave ASTRILLA running."""
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
    for k,v in re.findall(r'(\w+)=(\w+)',line):result[k]=int(v,16 if k in ('hash','lcd','crc','crc565','hud_crc') else 10)
    if 'gpu_cmd_total' in result:result['gpu_cmd_total'] |= result.get('gpu_cmd_hi',0)<<32
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--expected',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--seconds',type=int,default=305,help='the clock-driven loop lasts exactly 300 s');p.add_argument('--min-fps',type=float,default=54.5,help='LCD refresh is 55.04 Hz; diagnostic echoes cost a few frames');p.add_argument('--max-cycles',type=int,default=13700000,help='800 MHz cycles per frame; one LCD period is 14.53 M');p.add_argument('--sample-seconds',type=float,default=3,help='Delay between UART probes; longer status lines need a larger interval to limit their rendering cost');p.add_argument('--show-poses',action='store_true',help='Display diagnostic poses; default keeps LOADING visible and checks RGB565 offscreen');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    require(a.seconds > 0 and a.min_fps > 0 and a.max_cycles > 0 and 0<a.sample_seconds<=10, 'Paramètres de mesure invalides')
    poses=json.loads(a.expected.read_text());require(isinstance(poses,list) and poses, 'Aucune pose de référence')
    pack=Path(__file__).resolve().parents[1]/'assets/astrilla/packed'
    manifest=json.loads((pack/'manifest.json').read_text());raw=(pack/'astrilla.bin').read_bytes()
    regions=manifest['regions'];palette=struct.unpack_from('<256I',raw,regions['palette']['offset'])
    label=raw[regions['loading']['offset']:regions['loading']['offset']+640*128]
    loading_sum=800*480*4+sum(palette[p]-4 for p in label if p)
    progress=raw[regions['progress']['offset']]
    def loading_lcd(frame):
        return (loading_sum+(1200+(frame*600//16500)*2)*(palette[progress]-4))&0xffffffff
    port,snapshot=wait_console();require(snapshot['speed_mbps']==480, snapshot)
    uart=serial.Serial(port,115200,timeout=.1,exclusive=True);transcript=bytearray()
    def cmd(data,marker=b'ASTRILLA ',timeout=3):
        uart.write(data);uart.flush();answer=bytearray();limit=time.monotonic()+timeout
        while time.monotonic()<limit:
            answer.extend(uart.read(4096))
            if marker in answer and answer.endswith((b'\n',b'\r')):break
        transcript.extend(answer)
        if marker not in answer:raise RuntimeError(f'Missing response to {data!r}: {answer!r}')
        return answer.decode(errors='replace')
    records=[]
    try:
        uart.reset_input_buffer();require('ASTRILLA R' in cmd(b'?'), 'Identité ASTRILLA absente')
        # Start a fresh measurement window before exact poses.
        if a.show_poses:
            cmd(b'R',b'ASTRILLA AUTO')
            cmd(b'P',b'ASTRILLA PAUSED')
        else:cmd(b'L',b'ASTRILLA LOADING')
        for pose in poses:
            line=cmd(b'T'+struct.pack('<H',pose['frame']),b'ASTRILLA frame=');d=status(line)
            field='lcd' if pose.get('mode')=='rgb565' else 'hash'
            if a.show_poses:require(d[field]==int(pose[field],16),(pose,d))
            else:
                require(field=='lcd' and d.get('loading')==1, ('Hidden RGB565 test required',d))
                require(d['lcd']==loading_lcd(pose['frame']), ('LOADING display mismatch',pose['frame'],d))
            if field=='lcd':require(d['crc565']==int(pose['crc565'],16),(pose,d))
            if pose.get('hardware_geometry'):
                for counter, expected in [('vertices','vertices'),('triangles','triangles'),('clipped','intersections'),('slivers','slivers')]:
                    require(d.get('geom_'+counter)==pose[expected], ('Hardware geometry counter mismatch',counter,pose,d))
            if 'scene_commands' in pose:
                require(d['gpu_cmd_frame']==pose['commands'], ('GPU command count mismatch',pose,d))
                if 'hud_crc' in pose:
                    require(d['hud_crc']==int(pose['hud_crc'],16), ('HUD pixel mismatch',pose,d))
                    require(d['layers']==pose['layers'] and d['sprites']==pose['sprites'], ('Native descriptor count mismatch',pose,d))
                    require(d['live_fps_x10']==0 and d['gpu_cmds_s']==0, ('Paused rates must be zero',d))
            require(d['frame']==pose['frame'],d);healthy(d,a.max_cycles)
            records.append(d);print('POSE PASS',pose['frame'],pose.get('crc565',pose[field]),'scene LCD' if a.show_poses else 'LOADING LCD',flush=True)
        cmd(b'R',b'ASTRILLA AUTO')
        # La fenêtre englobe les deux interrogations : son débit est prudent,
        # même si la lecture série ou l'ordonnanceur du PC tarde à reprendre.
        start=time.monotonic();initial=status(cmd(b'S',b'ASTRILLA frame='));healthy(initial)
        echo_bytes=0;samples=[];elapsed=0.0
        while time.monotonic()-start<a.seconds:
            time.sleep(a.sample_seconds)
            # Short exact binary echoes while animation continues. <=64 bytes
            # avoids forcing a long blocked UART interval into a video benchmark.
            payload=bytes(((echo_bytes+i)*73+17)&255 for i in range(32))
            uart.write(b'E'+struct.pack('<H',len(payload))+payload);uart.flush();received=bytearray();deadline=time.monotonic()+2
            while len(received)<len(payload) and time.monotonic()<deadline:received.extend(uart.read(len(payload)-len(received)))
            require(bytes(received)==payload,(bytes(received),payload))
            echo_bytes+=len(payload)
            d=status(cmd(b'S',b'ASTRILLA frame='));samples.append(d)
            healthy(d,a.max_cycles)
            previous=samples[-2] if len(samples)>1 else initial
            require(d['run']==1 and d.get('loading',0)==0 and d['submitted']>previous['submitted'], ('Animation arrêtée ou mesure figée',d))
            require(d['uf_total']==initial['uf_total'], ('Sous-débordement pendant la mesure',d))
            if 'gpu_cmd_total' in d:
                sent=d['gpu_cmd_total']-previous['gpu_cmd_total']
                require(sent>0 and (sent&65535)==((d['gpu_done']-previous['gpu_done'])&65535), ('Issued/completed command mismatch',previous,d))
                require(400<=d['live_fps_x10']<=570 and d['gpu_cmds_s']>0, ('Invalid live throughput',d))
                require(2<=d['layers']<=16 and 0<=d['sprites']<=64, ('Invalid native counters',d))
            elapsed=time.monotonic()-start
            print('AUTO',round(elapsed,1),d,flush=True)
        require(samples and elapsed>=a.seconds, 'Fenêtre de mesure incomplète')
        frames=samples[-1]['submitted']-initial['submitted'];fps=frames/elapsed
        if a.seconds>=300:
            require(samples[-1]['loops']>=1, 'No complete 300-second loop')
            require(set(d['chapter'] for d in samples)==set(range(10)), 'Missing chapter in endurance')
        for sample in samples:
            expected_tick=(sample['elapsed_ms']*55)//1000
            measured_tick=sample['loops']*16500+sample['frame']
            require(-12<=measured_tick-expected_tick<=1, ('Timeline drift',sample))
        require(fps>=a.min_fps, f'Débit insuffisant : {frames} images / {elapsed:.6f} s = {fps:.3f} fps < {a.min_fps}')
        # Do not leave a PASS artifact if restoring autoplay failed. Capture
        # its acknowledgement in the transcript before closing the UART.
        cmd(b'R',b'ASTRILLA AUTO')
        result=dict(status='PASS',sample_seconds=a.sample_seconds,lcd_reference_checked=a.show_poses,hidden_pose_checks=not a.show_poses,usb=snapshot,poses=records,samples=samples,seconds=elapsed,frames=frames,fps=fps,initial=initial,echo_bytes=echo_bytes,autoplay_restored=True)
        (a.out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    finally:
        (a.out/'usb.txt').write_bytes(transcript)
        uart.close()
if __name__=='__main__':main()
