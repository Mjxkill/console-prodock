#!/usr/bin/env python3
"""Capture the Linux-variant console through the BL616 programmer UART."""
import argparse
from pathlib import Path
import re
import time

import serial

UART = '/dev/serial/by-id/usb-SIPEED_USB_Debugger_2025041420-if01-port0'


def select_relay(link, baud):
    """Select Sipeed's existing UART route after programming, without flashing."""
    transcript = bytearray()

    def receive(seconds):
        data = bytearray()
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            data.extend(link.read(4096))
        transcript.extend(data)
        return bytes(data)

    link.baudrate = 115200
    receive(.2)
    link.write(b'\x18')
    time.sleep(.2)
    link.write(b'\x03')
    time.sleep(.2)
    link.write(b'\r\n')
    prompt = receive(1.2)
    link.baudrate = baud
    if b'TangConsole' not in prompt or b'/>' not in prompt:
        raise RuntimeError('Sipeed debugger prompt missing; UART route not changed')
    receive(.2)
    link.write(b'uart_info\r\n')
    info = receive(.5)
    match = re.search(rb'dwDTERate:\s*(\d+)', info)
    if not match or abs(int(match[1]) - baud) > baud // 100:
        raise RuntimeError('Sipeed did not confirm the requested UART baud rate')
    link.write(b'choose uart\r\n')
    receive(.5)
    # Bytes used to enter the debugger at 115200 may have reached the
    # 2-Mbit/s FPGA receiver. Cancel that partial shell line before --send.
    link.write(b'\x03')
    receive(.3)
    return bytes(transcript)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--seconds', type=float, default=60)
    parser.add_argument('--baud', type=int, default=2000000,
                        help='Host serial setting (default: 2000000)')
    parser.add_argument('--select-relay', action='store_true',
                        help='Select the BL616 UART relay and clear the shell line with Ctrl-C (after programming)')
    send = parser.add_mutually_exclusive_group()
    send.add_argument('--send', help='Optional text sent once, followed by CR')
    send.add_argument('--send-file', type=Path,
                      help='Read the command from a UTF-8 file, followed by CR')
    args = parser.parse_args()
    if args.seconds <= 0 or args.baud <= 0 or args.output.exists():
        parser.error('Choose a new output file and a positive duration')
    command = args.send
    if args.send_file is not None:
        command = args.send_file.read_text().rstrip('\r\n')
        if any(c in command for c in '\x00\r\n'):
            parser.error('Command file must contain a single line')
    data = None if command is None else command.encode('utf-8') + b'\r'
    if data is not None and len(data) > 4096:
        parser.error('Input burst exceeds the console FIFO')
    # Open directly at the console rate. Preserve incoming boot messages and
    # prevent two host programs from issuing conflicting serial settings.
    with args.output.open('xb') as out, serial.Serial(
            UART, args.baud, timeout=0.1, exclusive=True) as link:
        if args.select_relay:
            out.write(select_relay(link, args.baud))
            out.flush()
        if data is not None:
            link.write(data)
        print(f'Console armed: {UART}, {args.baud} 8N1', flush=True)
        deadline = time.monotonic() + args.seconds
        total = 0
        while time.monotonic() < deadline:
            chunk = link.read(4096)
            if chunk:
                out.write(chunk)
                out.flush()
                total += len(chunk)
                print(chunk.decode('utf-8', errors='replace'), end='', flush=True)
        print(f'\nSaved {total} bytes to {args.output}', flush=True)


if __name__ == '__main__':
    main()
