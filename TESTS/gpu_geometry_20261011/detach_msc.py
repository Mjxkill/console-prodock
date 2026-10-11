#!/usr/bin/env python3
"""Detach only console MSC before starting USBDISK; keep CDC and JTAG live."""
import argparse
import json
from pathlib import Path
import sys
import usb.core
import usb.util

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from check_gpu_reloads import console_snapshot,target_busdev

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    target=target_busdev();snap=console_snapshot()
    if not snap or snap['speed_mbps']!=480 or snap['interfaces']!=3 or snap['configuration']!='1':
        raise RuntimeError(('Console HS composite absent',snap))
    branch=(Path('/sys/bus/usb/devices')/snap['topology']).resolve(strict=True)
    mounted={s.split()[2] for s in Path('/proc/self/mountinfo').read_text().splitlines()}
    blocks=[]
    for block in Path('/sys/class/block').iterdir():
        if branch in block.resolve().parents:
            number=(block/'dev').read_text().strip();blocks.append(dict(name=block.name,dev=number))
            if number in mounted:raise RuntimeError('Mounted console media: '+block.name)
    dev=usb.core.find(idVendor=0x359f,idProduct=0x2011,bus=snap['bus'],address=snap['address'])
    if dev is None or usb.util.get_string(dev,dev.iSerialNumber)!='11252024':
        raise RuntimeError('USB identity changed')
    try:
        config=dev.get_active_configuration()
        if config[(2,0)].bInterfaceClass!=8:raise RuntimeError('Interface 2 is not MSC')
        active=dev.is_kernel_driver_active(2)
        if active:dev.detach_kernel_driver(2)
        if dev.is_kernel_driver_active(2):raise RuntimeError('MSC detach failed')
        result=dict(status='PASS',console=snap,jtag_busdev=target,interface=2,was_active=active,
                    blocks=blocks,physical_sd_writes=0)
        a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    finally:usb.util.dispose_resources(dev)
if __name__=='__main__':main()
