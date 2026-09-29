#!/usr/bin/env python3
"""Test répété de l'écho binaire CDC, avec conservation des octets en défaut."""
import argparse
import difflib
from pathlib import Path
import random
import re
import struct
import time

import serial
from serial.tools import list_ports

from check_gpu_console import response


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rounds', type=int, default=20)
    parser.add_argument('--sizes', type=int, nargs='+', default=[1, 64, 256, 1024, 4096])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--tiles', action='store_true', help='Compose L11 tiles on the LCD throughout the echo test')
    args = parser.parse_args()
    if args.rounds < 1 or any(not 1 <= n <= 65535 for n in args.sizes):
        parser.error('rounds >= 1; sizes entre 1 et 65535')
    args.out.mkdir(parents=True, exist_ok=True)
    ports = [p for p in list_ports.comports() if (p.vid, p.pid) == (0x359f, 0x2011)]
    if len(ports) != 1:
        raise SystemExit(f'Expected one MegaPro console, found {ports}')
    rng = random.Random(20260929)
    total = 0
    with serial.Serial(ports[0].device, 115200, timeout=.1, write_timeout=10, exclusive=True) as dev:
        dev.reset_input_buffer()
        dev.write(b'X?')
        identity = response(dev, b'MegaPro GPU')
        (args.out / 'identity.txt').write_bytes(identity + b'\n')
        first_frame = None
        if args.tiles:
            if b' TILES ' not in identity:
                raise SystemExit('Tile firmware required for --tiles')
            dev.write(b'U')
            response(dev, b'TILES READY', timeout=60)
            dev.write(b'S')
            first_status = response(dev, b'GPU base=')
            first_frame = int(dict(re.findall(rb'(\w+)=(\w+)', first_status))[b'frames'])
        for run in range(args.rounds):
            for n in args.sizes:
                expected = rng.randbytes(n)
                dev.write(b'E' + struct.pack('<H', n) + expected)
                got = bytearray()
                deadline = time.monotonic() + 3 + n * 10 / 115200
                while len(got) < n and time.monotonic() < deadline:
                    got.extend(dev.read(n - len(got)))
                if got != expected:
                    (args.out / 'expected.bin').write_bytes(expected)
                    (args.out / 'received.bin').write_bytes(got)
                    changes = [op for op in difflib.SequenceMatcher(None, expected, got, autojunk=False).get_opcodes()
                               if op[0] != 'equal']
                    print(f'FAIL round={run+1} received={len(got)}/{n} differences={changes[:20]}', flush=True)
                    # If the CPU completed E, a normal banner distinguishes a
                    # damaged return stream from a receiver still waiting for data.
                    dev.write(b'?')
                    answer = bytearray()
                    end = time.monotonic() + 1
                    while time.monotonic() < end:
                        answer.extend(dev.read(512))
                    (args.out / 'after_failure.bin').write_bytes(answer)
                    print(f'After failure: {bytes(answer)!r}', flush=True)
                    raise SystemExit(1)
                total += n
            dev.write(b'?')
            if response(dev, b'MegaPro GPU') != identity:
                raise SystemExit('Identity changed during the test')
            print(f'PASS round={run+1}/{args.rounds} bytes={total}', flush=True)
        if args.tiles:
            dev.write(b'S')
            line = response(dev, b'GPU base=')
            fields = dict(re.findall(rb'(\w+)=(\w+)', line))
            if (fields[b'enable'] != b'1' or fields[b'layers'] != b'1'
                    or fields[b'underflows'] != b'0' or fields[b'invalid'] != b'0'
                    or fields[b'invalid_sprites'] != b'0'
                    or int(fields[b'frames']) <= first_frame
                    or int(fields[b'max_cycles']) >= 2556):
                raise SystemExit('Tile scanout failed during USB stress')
            print('L11 composition active throughout USB stress: PASS', flush=True)
    print(f'USB STRESS PASS: {total} binary bytes exact, {args.rounds} rounds', flush=True)


if __name__ == '__main__':
    main()
