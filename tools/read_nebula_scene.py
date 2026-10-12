#!/usr/bin/env python3
"""Read a fixed NEBULA scene via CDC, accepting only a complete matching CRC.

Runs the game briefly, writes a snapshot only to target /tmp, reads it with
BusyBox od. Repeated reads of the same immutable file tolerate rejected serial
lines; no bytes are repaired and a target-generated CRC is mandatory.
"""
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import re
import serial
import zlib
from check_linux import command
from check_gpu_reloads import wait_console


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--pose',type=int,default=700)
    p.add_argument('--boss',action='store_true')
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    assert 0<a.pose<=100000
    port,usb=wait_console();assert usb['speed_mbps']==480
    with serial.Serial(port,115200,timeout=.1,exclusive=True) as uart:
        def run(name,text):
            status,data=command(uart,text,80);(a.out/(name+'.log')).write_bytes(data)
            assert status==0,(status,data[-1000:])
            return data
        run('pose',f'nebula --demo {"--boss" if a.boss else ""} --pose {a.pose} --frames 3 --snapshot /tmp/nebula.scene > /tmp/nebula-snapshot.log')
        crcs=Counter()
        for i in range(8):
            data=run(f'crc{i}','grep NEBULA_SCENE_CRC32 /tmp/nebula-snapshot.log')
            m=re.search(rb'^NEBULA_SCENE_CRC32 crc=([0-9a-f]{8}) bytes=1568\r?$',data,re.M)
            if m:crcs[int(m[1],16)]+=1
            if crcs and crcs.most_common(1)[0][1]>=2:break
        assert crcs and len(crcs)==1 and crcs.most_common(1)[0][1]>=2,crcs
        expected=next(iter(crcs));chunks=defaultdict(Counter)
        for trial in range(10):
            data=run(f'od{trial}','od -v -b /tmp/nebula.scene')
            for line in data.replace(b'\r',b'').splitlines():
                if not re.fullmatch(rb'[0-7]{7}( +[0-7]{3}){16}',line):continue
                fields=line.split();offset=int(fields[0],8)
                if offset%16 or not 0<=offset<1568:continue
                chunk=bytes(int(b,8) for b in fields[1:]);chunks[offset][chunk]+=1
            agreed={offset:c.most_common(1)[0][0] for offset,c in chunks.items() if len(c)==1 and c.most_common(1)[0][1]>=2}
            print(f'Scene read {trial}: {len(agreed)}/98 blocks with two identical observations',flush=True)
            if len(agreed)!=98:continue
            blob=b''.join(agreed[offset] for offset in range(0,1568,16))
            assert zlib.crc32(blob)==expected,'Snapshot CRC mismatch'
            (a.out/'actual.scene').write_bytes(blob)
            (a.out/'result.json').write_text(json.dumps(dict(passed=True,pose=a.pose,boss=a.boss,bytes=len(blob),crc32=f'{expected:08x}',reads=trial+1,usb=usb),indent=2)+'\n')
            return
        raise RuntimeError('Could not obtain a complete CRC-checked snapshot')


if __name__=='__main__':main()
