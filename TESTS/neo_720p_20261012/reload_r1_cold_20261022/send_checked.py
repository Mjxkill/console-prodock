#!/usr/bin/env python3
"""Send one Neo shell line slowly and require its exact echo before Enter."""
import argparse
import fcntl
import json
from pathlib import Path
import sys
import time

import serial

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'tools/neo'))
from console import UART

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--command', required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--seconds', type=float, default=10)
a = p.parse_args()
if len(a.command)>256 or not all(32<=ord(c)<127 for c in a.command):
    p.error('One bounded ASCII command required')
a.out.mkdir(exist_ok=False)
report = dict(executed=False, echo_verified=False, command=a.command,
              uart_route='preserved', sd_written=False, flash_written=False)
with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
    with serial.Serial(UART,2000000,timeout=.05,exclusive=True) as port, (a.out/'serial.log').open('wb',buffering=0) as log:
        def collect(seconds):
            result=bytearray(); deadline=time.monotonic()+seconds
            while time.monotonic()<deadline:
                data=port.read(port.in_waiting or 1)
                result.extend(data);log.write(data)
            return bytes(result)
        port.write(b'\x03');collect(.5)
        port.write(b'\x15');collect(.2)
        port.write(b'\r');initial=collect(.8)
        if b'prodock# ' not in initial:
            raise RuntimeError('No idle shell prompt')
        echo=bytearray()
        for byte in a.command.encode():
            port.write(bytes([byte]))
            returned=collect(.04)
            echo.extend(returned)
            if returned!=bytes([byte]):
                report['mismatch']=dict(expected=byte,received=returned.hex())
                port.write(b'\x15');collect(.2)
                (a.out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
                raise RuntimeError('Echo differs; line cancelled before Enter')
        report['echo_verified']=bytes(echo)==a.command.encode()
        port.write(b'\r');report['executed']=True
        output=collect(a.seconds)
        report['output']=output.decode(errors='replace')
        (a.out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        print(report['output'])
