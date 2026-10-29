#!/usr/bin/env python3
"""Identify the sole connected console after a cable reconnect, without a load.

The CDC iSerial is firmware-defined and does not identify either programmer.
Record USB topology separately; never infer an FPGA/JTAG association from it.
Unlike an uninterrupted RX2 transfer, this reconnect probe must explicitly set
115200/raw on its held descriptor. It does not flush bytes or toggle DTR/RTS.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import termios
import tty

PORT = Path('/dev/serial/by-path/pci-0000:00:14.0-usb-0:7.3:1.0')
USB = Path('/sys/bus/usb/devices/3-7.3')
TRANSPORT = Path('/tmp/festival_persistent_20261028_prepared_r1')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert socket.gethostname().split('.')[0] == 'michael-AX15'
    args.out.mkdir(parents=True, exist_ok=False)
    report = {'passed': False, 'target_programmer_association': None,
              'fpga_writes': 0, 'sd_writes': 0, 'game_stopped': False}
    sys.path.insert(0, str(TRANSPORT))
    import probe_channel as transport

    class ReconnectedUART(transport.UART):
        def __init__(self):
            self.fd = os.open(PORT, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
            try:
                fcntl.ioctl(self.fd, termios.TIOCEXCL)
                report['termios_before'] = repr(termios.tcgetattr(self.fd))
                tty.setraw(self.fd, termios.TCSANOW)
                attrs = termios.tcgetattr(self.fd)
                attrs[2] &= ~(termios.PARENB | termios.CSTOPB | termios.CSIZE | termios.CRTSCTS)
                attrs[2] |= termios.CS8 | termios.CLOCAL | termios.CREAD
                attrs[4] = attrs[5] = termios.B115200
                termios.tcsetattr(self.fd, termios.TCSANOW, attrs)
                assert termios.tcgetattr(self.fd)[4:6] == [termios.B115200] * 2
            except BaseException:
                os.close(self.fd)
                raise

    try:
        identity = {k: (USB / k).read_text().strip() for k in
                    ('idVendor', 'idProduct', 'serial', 'product', 'busnum', 'devnum', 'speed')}
        assert (identity['idVendor'], identity['idProduct'], identity['serial']) == ('359f', '2011', '11252024')
        report['usb'] = identity
        lock_fd = os.open('/tmp/prodock-diagnostic.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(lock_fd, 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            owner = subprocess.run(['fuser', str(PORT)], capture_output=True)
            assert owner.returncode == 1 and not owner.stdout.strip() and not owner.stderr.strip()
            uart = ReconnectedUART()
            channel = transport.Channel(uart, args.out)
            try:
                channel.initial_shell()
                channel.run('identity', 'uname -r && prodockctl display && ps && cat /proc/mounts')
                channel.run('executables', 'ls -l /proc/[0-9]*/exe')
                report['passed'] = True
            finally:
                channel.close()
                uart.close()
    except BaseException as error:
        report['error'] = repr(error)
    (args.out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
