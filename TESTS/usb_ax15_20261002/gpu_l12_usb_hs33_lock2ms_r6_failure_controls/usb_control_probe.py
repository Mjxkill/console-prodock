#!/usr/bin/env python3
"""Diagnostic temporaire L12 : compteurs USB via GET_LINE_CODING dédié.

Nécessite le build CONSOLE_USB_DIAG. Sélectionne uniquement la console
359f:2011, série 11252024 ; aucun reset ni détachement du pilote Linux.
Les requêtes de contrôle changent l'endpoint sélectionné : elles peuvent
modifier le comportement du défaut observé, sans réinitialiser les FIFO.
"""
import argparse
import ctypes
import fcntl
import json
import os
from pathlib import Path
import select
import struct
import sys
import threading
import time

import serial
from serial.tools import list_ports


class Control(ctypes.Structure):
    _fields_ = [('request_type', ctypes.c_uint8), ('request', ctypes.c_uint8),
                ('value', ctypes.c_uint16), ('index', ctypes.c_uint16),
                ('length', ctypes.c_uint16), ('timeout', ctypes.c_uint32),
                ('data', ctypes.c_void_p)]


def control(fd, diagnostic, packets=False):
    n = 32 if diagnostic else 7
    buf = ctypes.create_string_buffer(n)
    # Device recipient: the control interface belongs to cdc_acm. The FPGA
    # handler accepts this private device request without detaching cdc_acm.
    req = Control(0xa0, 0x21, (0xd1a7 if packets else 0xd1a6) if diagnostic else 0, 0, n, 1000,
                  ctypes.addressof(buf))
    ioctl = 0xc0005500 | (ctypes.sizeof(Control) << 16)
    received = fcntl.ioctl(fd, ioctl, bytearray(bytes(req)))
    raw = buf.raw[:received]
    if len(raw) != n:
        raise RuntimeError(f'Control reply {len(raw)}/{n}: {raw.hex()}')
    if not diagnostic:
        print('LINE_CODING', raw.hex(), flush=True)
        return
    if packets:
        records=[]
        for word in struct.unpack('<4Q',raw):
            if not word>>63:continue
            record=dict(pid=f'{word&255:02x}',last_two=f'{(word>>8)&65535:04x}',
                bytes=(word>>24)&65535,advertised=(word>>40)&4095,
                endpoint=(word>>52)&15,cork=(word>>56)&1,active=(word>>57)&1)
            if (word>>58)&1:
                record.update(previous_phy_ack_pid=('4b' if (word>>61)&1 else 'c3') if (word>>62)&1 else None,
                              previous_controller_ack_pid=('4b' if (word>>59)&1 else 'c3') if (word>>60)&1 else None)
            if (word>>39)&1:
                record.update(bytes=(word>>24)&1023,
                              phy_ack=bool((word>>38)&1),
                              controller_finish=bool((word>>37)&1),
                              rx_error_after_tx=bool((word>>36)&1),
                              fifo_pending_after_ack=bool((word>>34)&1) if (word>>35)&1 else None)
            records.append(record)
        print('TX_PACKETS',json.dumps(records),flush=True)
        return
    uart, out, delivered, counts, status, last, errors, packets = struct.unpack('<8I', raw)
    print(json.dumps(dict(uart=uart, usb_out=out, delivered=delivered,
        pop=counts & 65535, ack=counts >> 16, pending=(status >> 27) & 1,
        cork=(status >> 26) & 1, active=(status >> 25) & 1,
        advertised=(status >> 12) & 4095, available=status & 4095,
        last_uart=last & 255, last_out=(last >> 8) & 255,
        last_delivered=(last >> 16) & 255, signature=last >> 24,
        phy_errors=errors, out_packets=packets,
        board_status_nibble=(status >> 28) & 15)), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--standard-only', action='store_true')
    parser.add_argument('--no-diagnostics', action='store_true', help='Host trace with older firmware')
    parser.add_argument('--packets', action='store_true', help='Read optional UTMI packet history instead of counters')
    parser.add_argument('--seconds', type=float, default=2)
    parser.add_argument('--trace', type=Path, help='USBmon text, filtered to this console only')
    parser.add_argument('--log', type=Path, help='Save stdout and errors to a new log file')
    parser.add_argument('commands', nargs='*', default=['?', '?', 'X', '?'])
    args = parser.parse_args()
    if args.log:
        log=args.log.open('x')
        class Tee:
            def __init__(self,stream):self.stream=stream
            def write(self,text):self.stream.write(text);return log.write(text)
            def flush(self):self.stream.flush();log.flush()
        sys.stdout=Tee(sys.stdout)
        sys.stderr=Tee(sys.stderr)
    devices = []
    for path in Path('/sys/bus/usb/devices').glob('*'):
        try:
            if ((path/'idVendor').read_text().strip() == '359f'
                    and (path/'idProduct').read_text().strip() == '2011'
                    and (path/'serial').read_text().strip() == '11252024'):
                devices.append(path)
        except OSError:
            pass
    if len(devices) != 1:
        raise SystemExit(f'Expected one console; found {devices}')
    path = devices[0]
    node = '/dev/bus/usb/%03d/%03d' % (int((path/'busnum').read_text()),
                                      int((path/'devnum').read_text()))
    if args.trace:
        bus=int((path/'busnum').read_text());address=int((path/'devnum').read_text())
        monitor=os.open(f'/sys/kernel/debug/usb/usbmon/{bus}u',os.O_RDONLY|os.O_NONBLOCK)
        def trace():
            with args.trace.open('w') as out:
                while True:
                    if not select.select([monitor],[],[],.1)[0]:continue
                    try: chunk=os.read(monitor,65536).decode()
                    except BlockingIOError:
                        time.sleep(.01)
                        continue
                    for line in chunk.splitlines():
                        fields=line.split()
                        endpoint=fields[3].split(':') if len(fields)>3 else []
                        if len(endpoint)==4 and int(endpoint[1])==bus and int(endpoint[2])==address:
                            print(line,file=out,flush=True)
        threading.Thread(target=trace,daemon=True).start()
    with open(node, 'r+b', buffering=0) as fd:
        control(fd, False)
        if args.standard_only:
            return
        ports = [p for p in list_ports.comports() if (p.vid,p.pid)==(0x359f,0x2011)
                 and p.serial_number=='11252024']
        if len(ports)!=1:
            raise SystemExit('Ambiguous CDC port')
        with serial.Serial(ports[0].device,115200,timeout=.1,write_timeout=2,exclusive=True) as dev:
            if not args.no_diagnostics:control(fd, True, args.packets)
            for command in args.commands:
                print('SEND', repr(command), flush=True)
                dev.write(command.encode('ascii'))
                deadline=time.monotonic()+args.seconds
                while time.monotonic()<deadline:
                    # Return promptly when data arrives; a fixed 4096-byte
                    # read otherwise waits 100 ms even for a 1 ms probe.
                    data=dev.read(min(4096, dev.in_waiting) or 1)
                    if data: print('RECV',repr(data),flush=True)
                if not args.no_diagnostics:control(fd, True, args.packets)


if __name__ == '__main__':
    main()
