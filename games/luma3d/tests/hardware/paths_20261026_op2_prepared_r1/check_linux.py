#!/usr/bin/env python3
"""Read-only system/SD checks and optional volatile GPU demo over Linux CDC."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import time
import serial
from check_gpu_reloads import wait_console


class CommandTimeout(TimeoutError):
    def __init__(self, data):
        self.data = bytes(data)
        super().__init__(repr(self.data[-4000:]))


def command(uart, text, seconds=20):
    # Marker must occupy its own complete line, not merely appear in echo.
    data = bytearray()
    previous_timeout = uart.timeout
    uart.timeout = .002
    try:
        for ch in (text + "; printf '\\n__PD_RC_%s__\\n' \"$?\"\n").encode():
            uart.write(bytes([ch])); uart.flush(); time.sleep(.025)
            data.extend(uart.read(4096))
    finally:
        uart.timeout = previous_timeout
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        data.extend(uart.read(4096))
        for line in bytes(data).replace(b'\r', b'').split(b'\n')[:-1]:
            if line.startswith(b'__PD_RC_') and line.endswith(b'__'):
                return int(line[8:-2]), bytes(data)
    raise CommandTimeout(data)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--demo',action='store_true')
    p.add_argument('--runtime',action='store_true')
    p.add_argument('--sd',action='store_true',help='Read SD sectors twice, dropping Linux caches; no writes')
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    port,snap=wait_console()
    if snap['speed_mbps']!=480:raise RuntimeError(snap)
    report={'passed':False,'usb':snap,'physical_sd_writes':0,'commands':[]}
    with serial.Serial(port,115200,timeout=.15,exclusive=True) as uart:
        uart.write(b'\n');time.sleep(.3)
        (a.out/'initial.log').write_bytes(uart.read(16000))
        commands=[('system','uname -a && cat /proc/interrupts && ls /dev/fb0 /dev/prodock-gpu && cat /proc/partitions'),
                  ('gpu','prodockctl info')]
        if a.runtime:commands.append(('runtime','prodock-runtime'))
        if a.demo:commands += [('demo','prodockctl demo'),('gpu_after','prodockctl info')]
        gpu_before=None
        try:
            for name,cmd in commands:
                status,data=command(uart,cmd,90 if name=='runtime' else 30)
                (a.out/(name+'.log')).write_bytes(data)
                print(data.decode(errors='replace'),flush=True)
                report['commands'].append({'name':name,'exit':status})
                if status:raise RuntimeError(f'{name}: exit {status}')
                marker={'runtime':b'PRODOCK_RUNTIME_OK threads=2 increments=20000 fork_mmap_mprotect=32',
                        'demo':b'PRODOCK_GPU_PIXELS_OK pixels=384000'}.get(name)
                if marker and marker not in data:raise RuntimeError(f'{name}: incomplete result')
                if name in ('gpu','gpu_after'):
                    match=re.search(rb'GPU ABI=1 caps=([0-9a-f]+) DDR=00800000\+90177536 done=(\d+) errors=0 uf=(\d+) frames=(\d+) crc=[0-9a-f]+ fault=0',data)
                    if not match:raise RuntimeError(f'{name}: missing/invalid GPU state')
                    if int(match[1],16)&0x1ff!=0x1ff:raise RuntimeError(f'{name}: missing GPU capabilities')
                    counters=[int(v) for v in match.groups()[1:]]
                    if name=='gpu':gpu_before=counters
                    elif ((counters[0]-gpu_before[0])&65535)!=2430 or counters[1]!=gpu_before[1]:
                        raise RuntimeError(f'GPU counters changed unexpectedly: {gpu_before} -> {counters}')
            if a.sd:
                status,data=command(uart,'test -b /dev/mmcblk0 && cat /sys/block/mmcblk0/size')
                (a.out/'sd_size.log').write_bytes(data)
                sizes=re.findall(rb'^([0-9]+)\r?$',data,re.M)
                if status or len(sizes)!=1:raise RuntimeError('SD size unavailable')
                size=int(sizes[0]);sectors=sorted({0,1,8191,size-1})
                if size<8192:raise RuntimeError('Unexpected SD size')
                report['sd']={'sectors':size,'reads':[]}
                for sector in sectors:
                    copies=[]
                    for trial in range(2):
                        status,data=command(uart,f'echo 3 > /proc/sys/vm/drop_caches && dd if=/dev/mmcblk0 of=/tmp/sd-sector bs=512 count=1 skip={sector} && od -v -b /tmp/sd-sector')
                        (a.out/f'sd_{sector}_{trial}.log').write_bytes(data)
                        lines=[line.split() for line in data.replace(b'\r',b'').splitlines()
                               if re.fullmatch(rb'[0-7]{7}( +[0-7]{3}){16}',line)]
                        if [int(line[0],8) for line in lines]!=list(range(0,512,16)):
                            raise RuntimeError(f'SD sector {sector}: incomplete/reordered dump')
                        raw=bytes(int(value,8) for line in lines for value in line[1:])
                        if status or len(raw)!=512:raise RuntimeError(f'SD sector {sector}: short/failed read')
                        copies.append(raw)
                    if copies[0]!=copies[1]:raise RuntimeError(f'SD sector {sector}: readback mismatch')
                    report['sd']['reads'].append({'sector':sector,'sha256':hashlib.sha256(copies[0]).hexdigest()})
            report['passed']=True
        except Exception as error:
            report['error']=str(error)
            if isinstance(error,CommandTimeout):(a.out/'timeout.log').write_bytes(error.data)
            raise
        finally:
            (a.out/'result.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
