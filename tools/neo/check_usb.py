#!/usr/bin/env python3
"""Check Neo's actual HS enumeration and Linux CDC round trips.

The FPGA/Linux must already be loaded and its shell available. This stops a
foreground demo with Ctrl-C. It never writes the SD or changes USB drivers.
Only serial NEO00001 (359f:2011) is accepted, not a Pro Dock or a debugger.
"""
import argparse
import json
import random
import re
import time
from pathlib import Path

import serial
from serial.tools import list_ports


def find_console():
    ports = [p for p in list_ports.comports()
             if p.vid == 0x359f and p.pid == 0x2011
             and p.serial_number == 'NEO00001']
    if len(ports) != 1:
        raise RuntimeError(f'Expected one Neo CDC interface, found {len(ports)}')
    tty = Path(ports[0].device).name
    node = (Path('/sys/class/tty') / tty / 'device').resolve(strict=True)
    for parent in (node, *node.parents):
        if (parent / 'idVendor').exists():
            values = {key: (parent / key).read_text().strip() for key in
                      ('idVendor', 'idProduct', 'serial', 'speed', 'busnum', 'devnum')}
            if (values['idVendor'], values['idProduct'], values['serial']) != (
                    '359f', '2011', 'NEO00001'):
                raise RuntimeError('Serial interface has an unexpected USB parent')
            if float(values['speed']) != 480:
                raise RuntimeError(f"Neo negotiated {values['speed']} Mbit/s instead of HS")
            return ports[0].device, parent, values
    raise RuntimeError('USB parent not found')


def result_line(data, prefix):
    """Match executed printf output, never the shell's echoed command line."""
    match = re.search(rb'(?:^|\n)' + re.escape(prefix) + rb':([^\r\n]*)\r?\n', data)
    return None if match is None else match[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--rounds', type=int, default=200)
    args = parser.parse_args()
    if not 1 <= args.rounds <= 10000:
        parser.error('rounds must be between 1 and 10000')
    args.out.mkdir(parents=True, exist_ok=False)
    report = dict(passed=False, rounds=0, payload_bytes=0)
    result = args.out / 'result.json'
    result.write_text(json.dumps(report, indent=2) + '\n')
    started = time.monotonic()
    try:
        device, usb_parent, values = find_console()
        report.update(device=device, usb_parent=str(usb_parent), usb=values)
        rng = random.Random(0x4e454f)
        sizes = [1, 63, 64, 65, 127, 255, 511, 512, 513, 1023]
        with serial.Serial(device, 115200, timeout=.05, write_timeout=5,
                           exclusive=True) as link, (args.out / 'serial.log').open('wb') as log:
            link.write(b'\x03')
            deadline = time.monotonic() + .5
            while time.monotonic() < deadline:
                log.write(link.read(4096))
            for index in range(args.rounds):
                size = sizes[index % len(sizes)]
                payload = ''.join(rng.choice('0123456789abcdef') for _ in range(size)).encode()
                prefix = f'NEO_CDC_{index:05d}'.encode()
                # Quoted alphanumeric arguments only; no shell metacharacters
                # from an external device or caller enter this command.
                command = b"printf '%s:%s\\n' '" + prefix + b"' '" + payload + b"'\r"
                offset = 0
                while offset < len(command):
                    count = min(len(command) - offset, rng.choice((1, 63, 64, 65, 512)))
                    sent = link.write(command[offset:offset + count])
                    if sent != count:
                        raise RuntimeError('Short serial write')
                    offset += sent
                received = bytearray()
                deadline = time.monotonic() + 4 + len(command) * 20 / 115200
                while time.monotonic() < deadline:
                    chunk = link.read(4096)
                    received.extend(chunk)
                    log.write(chunk)
                    found = result_line(received, prefix)
                    if found is not None:
                        if found != payload:
                            raise RuntimeError(f'Corrupted response in round {index}')
                        break
                    if len(received) > 32768:
                        raise RuntimeError('Unexpected unbounded console output')
                else:
                    raise RuntimeError(f'No exact response in round {index}')
                report['rounds'] += 1
                report['payload_bytes'] += len(payload)
                if index % 25 == 24:
                    print(f"HS CDC: {index + 1}/{args.rounds} exact round trips", flush=True)
            # A reconnect during the test must not count as uninterrupted HS.
            _, after_parent, after = find_console()
            if after_parent != usb_parent or after != values:
                raise RuntimeError('USB device changed or re-enumerated during the test')
        report['passed'] = True
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        report['seconds'] = time.monotonic() - started
        result.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
