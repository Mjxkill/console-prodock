#!/usr/bin/env python3
"""Stop only the autoplay left by this restoration's completed NEBULA test."""
import json
from pathlib import Path
import sys
import serial

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from check_gpu_reloads import wait_console
from check_linux import command

HERE = Path(__file__).resolve().parent
report = json.loads((HERE / 'nebula/result.json').read_text())
if not report.get('game_passed'):
    raise SystemExit('NEBULA acceptance did not complete; inspect its cleanup first')
if (HERE / 'stop_test_demo.json').exists():
    raise SystemExit('Stop already attempted; inspect evidence before another action')
port, usb = wait_console()
assert usb['speed_mbps'] == 480, usb
with serial.Serial(port, 115200, timeout=.1, exclusive=True) as uart:
    status, data = command(uart,
        'p=`cat /tmp/nebula-check.pid`; '
        'test "$p" = "`cat /tmp/nebula.pid`" && '
        'test "`cat /proc/$p/comm`" = nebula && '
        'kill -TERM "$p" && sleep 1 && test ! -d /proc/$p', 20)
    (HERE / 'stop_test_demo.log').write_bytes(data)
(HERE / 'stop_test_demo.json').write_text(json.dumps(
    dict(passed=status == 0, usb=usb, exit=status), indent=2) + '\n')
if status:
    raise SystemExit('Stop not confirmed; do not start another GPU application')
print('Restoration test demo stopped; serial port released')
