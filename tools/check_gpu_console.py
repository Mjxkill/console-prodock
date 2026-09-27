#!/usr/bin/env python3
"""Exercise G0/G1 diagnostic firmware over the MegaPro USB CDC port."""
import argparse
import re
import struct
import time

import serial
from serial.tools import list_ports


def response(dev, prefix, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = dev.read_until(b'\n\r').strip()
        if not line:
            continue
        print(line.decode('ascii', errors='replace'), flush=True)
        if b'FAIL' in line or b'TRAP' in line:
            raise SystemExit('GPU diagnostic failed')
        if line.startswith(prefix):
            return line
    raise SystemExit(f'Timeout waiting for {prefix!r}')


def test_gpu(dev):
    dev.write(b'V')
    line = response(dev, b'GPU READY')
    sums = [int(v, 16) for v in re.findall(rb'sum[01]=([0-9a-fA-F]+)', line)]
    if len(sums) != 2:
        raise SystemExit('Invalid checksum response')
    previous_frames = None
    for page in (0, 1, 0, 1, 0):
        if previous_frames is not None:
            dev.write(b'F')
            if response(dev, b'GPU FLIP') != f'GPU FLIP page={page}'.encode():
                raise SystemExit('Wrong page acknowledgement')
        time.sleep(.12)  # let the new page traverse two complete frames
        dev.write(b'M')  # CPU reads/writes a separate 1 MiB region while GPU scans
        if response(dev, b'SHARED END', timeout=90) != b'SHARED END errors=0':
            raise SystemExit('Concurrent CPU DDR test failed')
        dev.write(b'S')
        line = response(dev, b'GPU base=')
        fields = dict(re.findall(rb'(\w+)=([0-9a-fA-F]+)', line))
        expected_base = 0x800000 if page == 0 else 0x900000
        if (int(fields[b'base'], 16) != expected_base or fields[b'enable'] != b'1'
                or fields[b'busy'] != b'0' or fields[b'underflows'] != b'0'
                or int(fields[b'sum'], 16) != sums[page]):
            raise SystemExit('Framebuffer status/checksum mismatch')
        frames = int(fields[b'frames'])
        if previous_frames is not None and frames <= previous_frames:
            raise SystemExit('LCD frame counter stopped')
        previous_frames = frames
    print('G1 PASS: DDR framebuffer, palette, 4 page flips, concurrent CPU DDR, zero underflows', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wait', type=float, default=15)
    args = parser.parse_args()
    deadline = time.monotonic() + args.wait
    while True:
        ports = [p for p in list_ports.comports() if (p.vid, p.pid) == (0x359f, 0x2011)]
        if len(ports) == 1:
            break
        if len(ports) > 1 or time.monotonic() > deadline:
            raise SystemExit(f'Expected one MegaPro USB CDC port, found {ports}')
        time.sleep(.2)
    with serial.Serial(ports[0].device, 115200, timeout=.2, write_timeout=2) as dev:
        print(f'PORT {ports[0].device}', flush=True)
        time.sleep(.3)
        dev.reset_input_buffer()
        dev.write(b'?')
        identity = dev.read_until(b'\n\r')  # BSP appends CR after each LF.
        print(identity.decode('ascii', errors='replace').strip(), flush=True)
        if b'MegaPro GPU G' not in identity or b'core=800MHz' not in identity:
            raise SystemExit('Wrong firmware or no response')
        for n in (1, 64, 256, 1024, 4096):
            data = bytes((i * 73 + 19) & 255 for i in range(n))
            dev.write(b'E' + struct.pack('<H', n) + data)
            received = bytearray()
            deadline = time.monotonic() + 5
            while len(received) < n and time.monotonic() < deadline:
                received.extend(dev.read(n - len(received)))
            if received != data:
                raise SystemExit(f'Echo mismatch: {len(received)}/{n} bytes')
            print(f'ECHO {n} PASS', flush=True)
        dev.write(b'D')
        deadline = time.monotonic() + 90
        pending = bytearray()
        failures = False
        while time.monotonic() < deadline:
            pending.extend(dev.read(256))
            while b'\n' in pending:
                line, _, pending = pending.partition(b'\n')
                line = line.strip(b'\r')
                print(line.decode('ascii', errors='replace'), flush=True)
                failures |= line.startswith(b'FAIL')
                if b'TRAP' in line or b'Unhandled Trap' in line:
                    raise SystemExit('CPU exception during DDR test')
                if line.startswith(b'DDR END '):
                    if line != b'DDR END errors=0' or failures:
                        raise SystemExit('DDR verification failed')
                    print('G0 PASS', flush=True)
                    if b'GPU G1 ' in identity:
                        test_gpu(dev)
                    return
        raise SystemExit(f'DDR timeout; pending={pending!r}')


if __name__ == '__main__':
    main()
