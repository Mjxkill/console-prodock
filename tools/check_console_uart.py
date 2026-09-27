#!/usr/bin/env python3
"""Test de l'écho firmware E2 sur le CDC MegaPro (359f:2011), sans index tty fixe."""
import argparse
import hashlib
import time

import serial
from serial.tools import list_ports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wait', type=float, default=15, help='attente énumération, secondes')
    args = parser.parse_args()
    deadline = time.monotonic() + args.wait
    while True:
        ports = [p for p in list_ports.comports() if (p.vid, p.pid) == (0x359F, 0x2011)]
        if len(ports) == 1:
            break
        if len(ports) > 1:
            raise SystemExit('Plusieurs consoles MegaPro : identification ambiguë, aucun test envoyé.')
        if time.monotonic() >= deadline:
            raise SystemExit('Aucun CDC MegaPro 359f:2011 détecté.')
        time.sleep(0.1)
    port = ports[0]
    print(f'CDC : {port.device}, {port.product}, série {port.serial_number}', flush=True)
    with serial.Serial(port.device, 115200, timeout=0.2, write_timeout=5) as uart:
        time.sleep(0.2)
        startup = uart.read(uart.in_waiting)
        if startup:
            print(f'Démarrage : {startup!r}', flush=True)
        for size in (1, 64, 256, 1024, 4096):
            payload = bytes((n * 73 + size) & 255 for n in range(size))
            started = time.monotonic()
            uart.write(payload)
            received = bytearray()
            deadline = started + max(3, size * 10 / 115200 * 4)
            while len(received) < size and time.monotonic() < deadline:
                received.extend(uart.read(size - len(received)))
            if received != payload:
                mismatch = next((n for n, (a, b) in enumerate(zip(payload, received)) if a != b), None)
                raise SystemExit(f'ECHEC : {len(received)}/{size} octets, première différence {mismatch}; '
                                 f'début reçu {received[:64].hex()}')
            print(f'PASS {size} octets, {time.monotonic()-started:.3f} s, '
                  f'SHA256 {hashlib.sha256(received).hexdigest()}', flush=True)
        extra = uart.read(64)
        if extra:
            raise SystemExit(f'ECHEC : octets supplémentaires {extra.hex()}')
    print('PASS : écho AE350 exact, 5441 octets, aucune perte ni duplication.', flush=True)


if __name__ == '__main__':
    main()
