#!/usr/bin/env python3
"""Diagnostic L12 : échos d'un octet, trace UTMI seulement après une anomalie.

À lancer après l'arrêt du test USB ordinaire, firmware au repos dans sa boucle
de commandes. Ne remplace pas le test d'endurance. Ne recharge ni ne réinitialise
la carte. Le port reste ouvert pendant le délai supplémentaire après un défaut.
"""
import argparse
import contextlib
import io
import json
from pathlib import Path
import time

import serial
from serial.tools import list_ports

from usb_control_probe import control


def read_window(dev, duration):
    end = time.monotonic() + duration
    data = bytearray()
    while time.monotonic() < end:
        data.extend(dev.read(min(4096, dev.in_waiting) or 1))
    return bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rounds', type=int, default=1024)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--trace-each', action='store_true',
                        help='intrusive diagnostic: sample EP0 counters before each echo')
    args = parser.parse_args()
    if not 1 <= args.rounds <= 10000:
        parser.error('rounds doit être entre 1 et 10000')
    ports = [p for p in list_ports.comports()
             if (p.vid, p.pid, p.serial_number) == (0x359f, 0x2011, '11252024')]
    devices = []
    for path in Path('/sys/bus/usb/devices').glob('*'):
        try:
            if ((path/'idVendor').read_text().strip(),
                (path/'idProduct').read_text().strip(),
                (path/'serial').read_text().strip()) == ('359f', '2011', '11252024'):
                devices.append(path)
        except OSError:
            pass
    if len(ports) != 1 or len(devices) != 1:
        raise SystemExit('Expected exactly one Pro Dock console 359f:2011 / 11252024')
    path = devices[0]
    node = '/dev/bus/usb/%03d/%03d' % (int((path/'busnum').read_text()),
                                     int((path/'devnum').read_text()))
    args.out.mkdir(parents=True, exist_ok=False)
    result = dict(status='running', port=ports[0].device, topology=path.name,
                  serial='11252024', samples=[], trace_each=args.trace_each)
    try:
        with serial.Serial(ports[0].device, 115200, timeout=.01,
                           write_timeout=2, exclusive=True) as dev:
            initial = read_window(dev, .1)
            (args.out/'initial.bin').write_bytes(initial)
            if initial:
                raise RuntimeError('Data already arriving: pause the firmware before this diagnostic')
            for i in range(args.rounds):
                expected = bytes([(i*73+17) & 255])
                before = None
                if args.trace_each:
                    # A control request changes endpoint context. This mode
                    # measures UART/USB deltas, not ordinary CDC endurance.
                    trace = io.StringIO()
                    with open(node, 'r+b', buffering=0) as fd, contextlib.redirect_stdout(trace):
                        control(fd, True, False)
                    before = json.loads(trace.getvalue())
                start = time.monotonic()
                dev.write(b'E\x01\x00' + expected)
                got = bytearray()
                while not got and time.monotonic()-start < 1:
                    got.extend(dev.read(1))
                first_byte_ms = (time.monotonic()-start)*1000 if got else None
                got.extend(read_window(dev, .01))
                sample = dict(index=i, expected=expected.hex(), received=got.hex(),
                              first_byte_ms=first_byte_ms,
                              elapsed_ms=(time.monotonic()-start)*1000)
                if before is not None:
                    sample['counters_before'] = before
                result['samples'].append(sample)
                if got != expected:
                    # Same descriptor, no reopen/reset/flush and no private
                    # control request while waiting for a possibly late byte.
                    got.extend(read_window(dev, 1))
                    sample.update(received_after_grace=got.hex(), elapsed=time.monotonic()-start)
                    result['status'] = 'late' if got == expected else 'mismatch'
                    trace = io.StringIO()
                    try:
                        with open(node, 'r+b', buffering=0) as fd, contextlib.redirect_stdout(trace):
                            control(fd, True, True)
                            control(fd, True, False)
                    except Exception as error:
                        result['diagnostic_error'] = str(error)
                    (args.out/'diagnostic.txt').write_text(trace.getvalue())
                    print(json.dumps(sample), flush=True)
                    print(trace.getvalue(), end='', flush=True)
                    return 1
            result['status'] = 'pass'
            print(f'PASS: {args.rounds} isolated bytes exact (diagnostic only)', flush=True)
            return 0
    except Exception as error:
        result.update(status='error', error=str(error))
        raise
    finally:
        (args.out/'result.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    raise SystemExit(main())
