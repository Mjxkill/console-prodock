#!/usr/bin/env python3
"""Reprise Bulk-Only pendant des lectures SD/DDR, sans écrire sur le support.

Application USBDISK requise sur ax15. Seule l'interface MSC est détachée du
pilote ; le CDC reste ouvert pour vérifier resets, pertes et délais. Le
test interrompt READ10, applique BOT Reset + Clear Halt, puis compare une
nouvelle lecture au contenu relevé avant les interruptions.
"""
import argparse
import json
import re
import struct
import time
import zlib
from pathlib import Path

import serial
from serial.tools import list_ports
import usb.core
import usb.util
from check_usb_disk import Disk, Fail, command, VID, PID
from check_gpu_reloads import console_snapshot


def counters(port):
    return dict(re.findall(r'(\w+)=(\w+)', command(port, 's', 'USBDISK MEDIA=')))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--rounds', type=int, default=12)
    args = parser.parse_args()
    if not 1 <= args.rounds <= 1000:
        parser.error('rounds : 1..1000')
    args.out.mkdir(parents=True, exist_ok=False)
    report = dict(passed=False, read_only=True, rounds=[], cleanup_errors=[])
    dev = None
    detached = claimed = False
    try:
        snapshot = console_snapshot()  # Vérifie également la série 11252024.
        report['usb'] = snapshot
        if snapshot is None:
            raise Fail('Console 11252024 absente')
        dev = usb.core.find(idVendor=VID, idProduct=PID,
                            bus=snapshot['bus'], address=snapshot['address'])
        if dev is None or dev.speed != 3:
            raise Fail('Console USB High Speed absente')
        ports = [p.device for p in list_ports.comports()
                 if (p.vid, p.pid, p.serial_number) == (VID, PID, '11252024')]
        if len(ports) != 1:
            raise Fail(f'Port CDC ambigu : {ports}')
        if dev.is_kernel_driver_active(2):
            dev.detach_kernel_driver(2)
            detached = True
        usb.util.claim_interface(dev, 2)
        claimed = True
        with serial.Serial(ports[0], 115200, timeout=.05, exclusive=True) as port:
            command(port, '?', 'USBDISK ')
            disk = Disk(dev)
            for _ in range(3):
                if disk.transfer(bytes(6))[0] == 0:
                    break
                disk.sense()
            status, residue, reference = disk.read(0, 8)
            if status or residue or len(reference) != 4096:
                raise Fail('Lecture de référence refusée')
            report['initial'] = counters(port)
            for n in range(args.rounds):
                before = counters(port)
                disk.tag += 1
                cdb = struct.pack('>BBIBHB', 0x28, 0, 0, 0, 128, 0)
                cbw = struct.pack('<IIIBBB', 0x43425355, disk.tag, 65536, 0x80, 0, 10) + cdb.ljust(16, b'\0')
                if dev.write(0x01, cbw, 5000) != 31:
                    raise Fail('CBW incomplet')
                received = 0
                for _ in range((n % 3) + 1):
                    part = bytes(dev.read(0x81, 512, 5000))
                    if len(part) != 512:
                        raise Fail('READ10 court avant reset')
                    received += len(part)
                dev.ctrl_transfer(0x21, 0xff, 0, 2, None, timeout=3000)
                dev.clear_halt(0x01)
                dev.clear_halt(0x81)
                limit = time.monotonic() + 3
                while True:
                    after = counters(port)
                    if int(after['RESETS']) > int(before['RESETS']):
                        break
                    if time.monotonic() >= limit:
                        raise Fail('Reset non traité par le firmware')
                status, residue, data = disk.read(0, 8)
                if status or residue or data != reference:
                    raise Fail('Lecture différente après reprise')
                row = dict(round=n, interrupted_after_bytes=received,
                           resets=int(after['RESETS']), crc32=f'{zlib.crc32(data):08x}')
                report['rounds'].append(row)
                print('PASS', row, flush=True)
            report['final'] = counters(port)
            for key in ('TIMEOUTS', 'LOSSES', 'RESYNCS'):
                if report['final'][key] != report['initial'][key]:
                    raise Fail(f'Compteur {key} augmenté')
            report['passed'] = True
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        cleanup = []
        if claimed:
            cleanup.append(lambda: usb.util.release_interface(dev, 2))
        if detached:
            cleanup.append(lambda: dev.attach_kernel_driver(2))
        if dev is not None:
            cleanup.append(lambda: usb.util.dispose_resources(dev))
        for action in cleanup:
            try:
                action()
            except Exception as error:
                report['cleanup_errors'].append(str(error))
                report['passed'] = False
        (args.out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    if not report['passed']:
        raise Fail('Nettoyage incomplet : ' + '; '.join(report['cleanup_errors']))


if __name__ == '__main__':
    main()
