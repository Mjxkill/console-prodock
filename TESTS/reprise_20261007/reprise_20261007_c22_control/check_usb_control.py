#!/usr/bin/env python3
"""Vérifie les réponses EP0 de la console HS, sans ouvrir le port série.

Alterner CDC7 et les deux pages diagnostic32 exerce les changements de réponse.
Aucun reset, détachement de pilote ou acquittement perdu artificiellement :
les reprises de bas niveau restent gérées par le contrôleur USB du PC.
"""
import argparse
import ctypes
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import time

from check_gpu_reloads import console_snapshot
from usb_control_probe import Control


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rounds', type=int, default=100)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.rounds <= 1000:
        parser.error('rounds: 1..1000')
    device = console_snapshot()
    if (not device or device['speed_mbps'] != 480 or
            device['configuration'] != '1' or device['interfaces'] not in (2, 3)):
        raise SystemExit(f'Console HS configurée requise : {device}')
    path = Path('/sys/bus/usb/devices') / device['topology']
    ports = list((path / (path.name + ':1.0')).glob('tty/ttyACM*'))
    if len(ports) != 1:
        raise SystemExit('Un seul port CDC attendu')
    port = '/dev/' + ports[0].name
    owner = subprocess.run(['fuser', port], capture_output=True, text=True)
    if owner.returncode != 1 or owner.stdout.strip() or owner.stderr.strip():
        raise SystemExit(f'Port série occupé ou contrôle impossible : {owner.stdout} {owner.stderr}')
    node = '/dev/bus/usb/%03d/%03d' % (device['bus'], device['address'])
    args.out.mkdir(parents=True, exist_ok=False)
    result = dict(status='running', device=device, port=port, requests=[],
                  scope='EP0 CDC7 exact et longueur des snapshots32 ; aucun ACK perdu injecté')
    sources = {}
    for name in ('check_usb_control.py', 'check_gpu_reloads.py', 'usb_control_probe.py'):
        source = Path(__file__).with_name(name).read_bytes()
        (args.out / name).write_bytes(source)
        sources[name] = hashlib.sha256(source).hexdigest()
    result['tool_sources_sha256'] = sources
    ioctl = 0xc0005500 | (ctypes.sizeof(Control) << 16)
    line_coding = None
    try:
        with open(node, 'r+b', buffering=0) as fd:
            for index in range(args.rounds * 3):
                value, length = ((0, 7), (0xd1a6, 32), (0xd1a7, 32))[index % 3]
                buf = ctypes.create_string_buffer(length)
                req = Control(0xa0, 0x21, value, 0, length, 1000, ctypes.addressof(buf))
                sample = dict(index=index, value=value, expected_length=length)
                result['requests'].append(sample)
                start = time.monotonic()
                try:
                    received = fcntl.ioctl(fd, ioctl, bytearray(bytes(req)))
                except OSError as error:
                    sample.update(errno=error.errno, error=str(error))
                    raise
                finally:
                    sample['elapsed_ms'] = (time.monotonic() - start) * 1000
                raw = buf.raw[:received]
                sample.update(received_length=received, data=raw.hex())
                if received != length:
                    raise RuntimeError(f'Réponse courte : {received}/{length}')
                if value == 0:
                    if line_coding is None:
                        line_coding = raw
                        if raw != bytes.fromhex('00c20100000008'):
                            raise RuntimeError(f'Configuration CDC initiale inattendue : {raw.hex()}')
                    if raw != line_coding:
                        raise RuntimeError('Réponse CDC modifiée ou périmée')
        result['status'] = 'pass'
        print(f'PASS: {args.rounds * 3} requêtes EP0, CDC7 exact et snapshots32 complets à 480 Mbit/s')
    except Exception as error:
        result.update(status='fail', error=str(error))
        print(f'FAIL: {len(result["requests"])} requêtes tentées : {error}')
    finally:
        result['device_after'] = console_snapshot()
        (args.out / 'result.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    return int(result['status'] != 'pass')


if __name__ == '__main__':
    raise SystemExit(main())
