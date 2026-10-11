#!/usr/bin/env python3
"""Transfert Linux vers la DDR USB volatile de C37, jamais vers la SD.

USBDISK R4/C4b doit être chargé et la console en HS. Détache uniquement
l'interface MSC, exige MEDIA=DDR/SERVING=1 et la capacité exacte avant WRITE.
La relecture intégrale et le CRC du lanceur protègent deux étapes distinctes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
import serial
import usb.core
import usb.util
from check_gpu_reloads import target_busdev, wait_console
from check_usb_disk import Disk, command, VID, PID
from check_usb_disk_faults import require_ddr
from load_ilm import require, quiesce_console


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pack', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--chunk-bytes', type=int, choices=(4096, 16384, 65536), default=65536)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((a.pack / 'manifest.json').read_text())
    name = 'opensbi/platform/generic/firmware/fw_payload.bin'
    data = (a.pack / name).read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    require(0 < len(data) == manifest['files'][name]['bytes'] <= 0x2000000, 'Taille staging incorrecte')
    require(sha == manifest['files'][name]['sha256'], 'SHA incorrect')
    require(manifest['load'] == 0x07c00000 and manifest['launcher_usb']['stage'] == 0x08000000, 'Adresses incorrectes')
    print('Pro Dock', target_busdev(), flush=True)
    port, snapshot = wait_console()
    require(snapshot['speed_mbps'] == 480, snapshot)
    dev = usb.core.find(idVendor=VID, idProduct=PID, bus=snapshot['bus'], address=snapshot['address'])
    require(dev is not None, 'USB absent')
    detached = claimed = False
    report = dict(passed=False, physical_sd_writes=0, usb=snapshot, sha256=sha,
                  chunk_bytes=a.chunk_bytes, cleanup_errors=[])
    try:
        if dev.is_kernel_driver_active(2):
            dev.detach_kernel_driver(2); detached = True
        usb.util.claim_interface(dev, 2); claimed = True
        with serial.Serial(port, 115200, timeout=.05, exclusive=True) as uart:
            identity = command(uart, '?', 'USBDISK R')
            require('R4 ' in identity and 'BOT_GUARD=1' in identity, 'USBDISK R4 requis')
            try:
                command(uart, 'd', 'USBDISK MEDIA=DDR')
                disk = Disk(dev)
                require_ddr(uart, disk)  # No WRITE may precede this media/capacity check.
                padded = data + bytes((-len(data)) % 512)
                start = time.monotonic()
                for off in range(0, len(padded), a.chunk_bytes):
                    require(disk.write(off // 512, padded[off:off + a.chunk_bytes]) == (0, 0), 'WRITE DDR refusé')
                report['write_seconds'] = time.monotonic() - start
                start = time.monotonic(); back = bytearray()
                for off in range(0, len(padded), a.chunk_bytes):
                    length = min(a.chunk_bytes, len(padded) - off)
                    status, residue, chunk = disk.read(off // 512, length // 512)
                    require(not status and not residue and len(chunk) == length, 'READ DDR incomplet')
                    back.extend(chunk)
                report['read_seconds'] = time.monotonic() - start
                require(bytes(back) == padded, 'Relecture DDR différente')
                report['passed'] = True
            finally:
                (a.out / 'released.txt').write_bytes(quiesce_console(uart, b'q'))
    except Exception as error:
        report['passed'] = False; report['error'] = str(error)
        raise
    finally:
        actions = []
        if claimed: actions.append(lambda: usb.util.release_interface(dev, 2))
        # Linux has no firmware MSC server. Keep interface 2 detached after
        # a successful handoff, otherwise host storage probes/reset recovery
        # may disturb CDC while the CPU is entering Linux. On failure restore
        # the original binding; no Linux handoff has been authorized by success.
        report['msc_detached_for_linux'] = report['passed']
        if detached and not report['passed']:
            actions.append(lambda: dev.attach_kernel_driver(2))
        actions.append(lambda: usb.util.dispose_resources(dev))
        for action in actions:
            try: action()
            except Exception as error:
                report['cleanup_errors'].append(str(error)); report['passed'] = False
        (a.out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    require(report['passed'], report)
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__': main()
