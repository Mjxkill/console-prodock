#!/usr/bin/env python3
"""Bounded passive CDC collection; no serial write, flush, or termios change."""
import fcntl
import json
import os
from pathlib import Path
import select
import socket
import time

PORT = '/dev/serial/by-id/usb-Electrosens_MegaPro_Console_11252024-if00'
OUT = Path('/home/michael/festival_20261028_r6_passive_r1')

def main():
    if socket.gethostname() != 'michael-AX15':
        raise RuntimeError('Wrong host')
    OUT.mkdir(exist_ok=False)
    data = bytearray()
    result = dict(serial_writes=0, flushes=0, termios_changes=0)
    try:
        with open('/tmp/prodock-diagnostic.lock', 'a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fd = os.open(PORT, os.O_RDONLY | os.O_NOCTTY | os.O_NONBLOCK)
            try:
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline and len(data) < 65536:
                    if select.select([fd], [], [], .1)[0]:
                        try:
                            block = os.read(fd, 4096)
                        except BlockingIOError:
                            continue
                        if not block:
                            result['eof'] = True
                            break
                        data.extend(block)
            finally:
                os.close(fd)
        result['completed'] = True
    except BaseException as error:
        result['error'] = repr(error)
    finally:
        (OUT / 'received.bin').write_bytes(data)
        result['received_bytes'] = len(data)
        (OUT / 'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result), flush=True)

if __name__ == '__main__':
    main()
