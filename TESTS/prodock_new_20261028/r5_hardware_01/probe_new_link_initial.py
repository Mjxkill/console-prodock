#!/usr/bin/env python3
"""Probe only the new dock after the recorded G22 control load.

Standard device-descriptor reads test EP0. The sole UART byte '?' asks the
G22 diagnostic ROM to identify itself. No JTAG, memory or storage write.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import select
import socket
import subprocess
import termios
import time
import tty

ROOT = Path('/home/michael/console-validation-20261001')
BASE = ROOT / 'TESTS/prodock_sd_autoboot_r5_20261029'
USB = Path('/sys/bus/usb/devices/3-7.1')
PORT = Path('/dev/serial/by-path/pci-0000:00:14.0-usb-0:7.1:1.0')


def identity():
    return {k: (USB/k).read_text().strip() for k in
            ('idVendor', 'idProduct', 'serial', 'busnum', 'devnum', 'speed')}


def main():
    import usb.core
    assert socket.gethostname().split('.')[0] == 'michael-AX15'
    previous = json.loads((BASE/'g22_link_control_01/result.json').read_text())
    assert previous['target_serial'] == '2025071717'
    assert previous['configuration_completed'] and previous['fresh_console_observed']
    assert previous['bitstream_sha256'] == 'fbbea9c357d0c4d5b33c3c4a7e54f9ed0ff8e31cc3fad1ac9dc1771f8e8cba5f'
    out = BASE/'g22_communication_01'
    out.mkdir(exist_ok=False)
    record = dict(target_serial='2025071717', ep0_reads=0, uart_query_bytes=0,
                  uart_reply_observed=False, sd_writes=0, flash_writes=0)
    received = bytearray()
    try:
        lockfd = os.open('/tmp/prodock-diagnostic.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(lockfd, 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            now = identity()
            assert (now['idVendor'], now['idProduct'], now['serial'], now['speed']) == ('359f','2011','11252024','480')
            assert all(now[k] == previous['fresh_console_identity'][k] for k in now)
            record['usb'] = now
            dev = usb.core.find(bus=int(now['busnum']), address=int(now['devnum']), idVendor=0x359f, idProduct=0x2011)
            assert dev is not None
            for _ in range(10):
                raw = bytes(dev.ctrl_transfer(0x80, 6, 0x0100, 0, 18, timeout=1000))
                assert len(raw) == 18 and raw[:2] == b'\x12\x01'
                assert raw[8:12] == b'\x9f\x35\x11\x20'
                record['ep0_reads'] += 1
                record['device_descriptor_hex'] = raw.hex()
            owner = subprocess.run(['fuser', str(PORT)], capture_output=True, timeout=2)
            assert owner.returncode == 1 and not owner.stdout.strip()
            fd = os.open(PORT, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
            try:
                fcntl.ioctl(fd, termios.TIOCEXCL)
                tty.setraw(fd, termios.TCSANOW)
                attrs = termios.tcgetattr(fd)
                attrs[2] &= ~(termios.PARENB | termios.CSTOPB | termios.CSIZE | termios.CRTSCTS)
                attrs[2] |= termios.CS8 | termios.CLOCAL | termios.CREAD
                attrs[4] = attrs[5] = termios.B115200
                termios.tcsetattr(fd, termios.TCSANOW, attrs)
                assert os.write(fd, b'?') == 1
                record['uart_query_bytes'] = 1
                end = time.monotonic()+5
                while time.monotonic() < end and len(received) < 4096:
                    if select.select([fd], [], [], .1)[0]:
                        received.extend(os.read(fd, 4096-len(received)))
                record['uart_reply_observed'] = b'MegaPro GPU G6' in received
            finally:
                os.close(fd)
            assert identity() == now, 'Device changed during probe'
    except Exception as error:
        record['error'] = repr(error)
    (out/'uart.bin').write_bytes(received)
    record['uart_rx_bytes'] = len(received)
    record['uart_sha256'] = hashlib.sha256(received).hexdigest()
    (out/'result.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps(record), flush=True)


if __name__ == '__main__':
    main()
