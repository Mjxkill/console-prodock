#!/usr/bin/env python3
"""Exercise the real Neo Linux/GPU through its serial console; keep transcripts.

Run after tools/neo/load_linux.py. SD and flash are not written. Expected
NEBULA CRCs come from the independent 720p command/scanout reference.
"""
import argparse,json,re,time
from pathlib import Path
import serial
from console import UART
ROOT=Path(__file__).resolve().parents[2]
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--reference',type=Path,default=ROOT/'TESTS/neo_720p_20261012/nebula_n5')
    p.add_argument('--sd-reference',type=Path,
                   help='Optional old-Linux capture of sectors 0, 2048 and 65536')
    p.add_argument('--frames',type=int,default=1800);p.add_argument('--leave-demo',action='store_true')
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    if not 1<=a.frames<=100000:p.error('Frame count out of bounds')
    report={'passed':False,'steps':[]};result=out/'result.json'
    def record():result.write_text(json.dumps(report,indent=2)+'\n')
    record()
    with serial.Serial(UART,2000000,timeout=.1,exclusive=True) as port:
        port.write(b'\x03');time.sleep(.3);port.read_all()
        def command(name,cmd,seconds=40):
            index=len(report['steps']);token=f'NEO_STEP_{index}='
            step={'name':name,'command':cmd,'passed':False};report['steps'].append(step);record()
            port.write((cmd+'; echo '+token+'$?\r').encode())
            data=bytearray();deadline=time.monotonic()+seconds
            with (out/(name+'.log')).open('wb',buffering=0) as f:
                while time.monotonic()<deadline:
                    b=port.read(4096);data.extend(b);f.write(b)
                    hit=re.search(rb'(?:^|\n)'+token.encode()+rb'(\d+)\r?\n',data)
                    if hit:break
                else:raise RuntimeError('No completion marker for '+name)
            text=data.decode(errors='replace');step['returncode']=int(hit[1]);step['passed']=step['returncode']==0;record()
            print(text,flush=True)
            if not step['passed']:raise RuntimeError('Board test failed: '+name)
            return text
        geometry=command('geometry','prodockctl geometry')
        if not all(s in geometry for s in ['board=1','width=1280','height=720','line_budget=1663']):raise RuntimeError('Wrong physical target')
        command('runtime','prodock-runtime')
        if a.sd_reference:
            def sectors(text):
                data={int(n):bytes.fromhex(words) for n,words in re.findall(
                    r'^SECTOR=(\d+)\r?\n((?:[0-9a-f]{32}\r?\n){32})',text,re.M)}
                if set(data)!={0,2048,65536}:raise RuntimeError('Incomplete SD sector capture')
                return data
            before=sectors(a.sd_reference.read_text())
            storage=command('sd','test -b /dev/mmcblk0 && for n in 0 2048 65536; do '
                'echo SECTOR=$n; dd if=/dev/mmcblk0 bs=512 skip=$n count=1 2>/dev/null | '
                'hexdump -v -e \'16/1 "%02x" "\\n"\'; done')
            if sectors(storage)!=before:raise RuntimeError('SD sectors differ from previous Linux')
            report['sd_compared_bytes']=1536;record()
        command('info','prodockctl info')
        command('raster','prodockctl demo')
        text=command('text','prodock-text-test')
        if 'PRODOCK_TEXT_PIXELS_OK poses=4 pixels=3686400' not in text:raise RuntimeError('Missing independent text proof')
        command('game','prodock-game --demo --frames 300',60)
        for name,pose,boss in [('wave700',700,False),('boss310',310,True),('nova5740',5740,False)]:
            ref=json.loads((a.reference/(name+'.reference.json')).read_text())
            text=command(name,f'nebula --demo --pose {pose} --frames 3'+(' --boss' if boss else ''),60)
            expected=f"NEBULA_FRAME_CRC32 pose={pose} crc={ref['frame_crc32']} pixels=230400"
            if expected not in text:raise RuntimeError('Raster differs from independent reference: '+name)
        command('endurance',f'nebula --demo --split --frames {a.frames}',max(90,a.frames/10))
        status=command('status','prodockctl display')
        hit=re.search(r'DISPLAY mode=\d+[^\r\n]*',status)
        if not hit:raise RuntimeError('No final display counters')
        metrics={k:v for k,v in re.findall(r'(\w+)=([0-9a-f]+)',hit[0])}
        for key in ['errors','uf','invalid','sprites','fault']:
            if int(metrics[key],16 if key=='errors' else 10):raise RuntimeError('Nonzero display error '+key)
        report['display']=metrics;report['passed']=True;record()
        if a.leave_demo:
            port.write(b'nebula --demo --split\r')
            data=bytearray();deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                data.extend(port.read(4096))
                if b'NEBULA_START' in data:break
            (out/'running.log').write_bytes(data)
            report['demo_started']=b'NEBULA_START' in data;record()
            if not report['demo_started']:raise RuntimeError('Demo launch not acknowledged')
if __name__=='__main__':main()
