"""Measure the dashboard concurrently with a running game; leave split view.

Run on ax15 after tools/check_linux_desktop.py has finished. SD statistics
are read through sysfs; no physical SD writes or filesystem mount.
"""
import json
from pathlib import Path
import sys
import time
sys.path.insert(0, 'tools')
import serial
from check_gpu_reloads import wait_console
from check_linux import command
from check_linux_desktop import display

out = Path('TESTS/linux_dashboard_20261011/observe_r13')
out.mkdir(parents=True, exist_ok=False)
port, usb = wait_console()
assert usb['speed_mbps'] == 480, usb
with serial.Serial(port, 115200, timeout=.15, exclusive=True) as uart:
    def run(name, text, timeout=15):
        status, data = command(uart, text, timeout)
        (out / (name + '.log')).write_bytes(data)
        assert status == 0, (name, status, data)
        return data
    run('start', 'prodockctl layout split; prodock-game --demo > /tmp/desktop-demo.log & echo $! > /tmp/desktop-demo.pid')
    run('sd_before', 'cat /sys/block/mmcblk0/size /sys/block/mmcblk0/stat')
    t0 = time.monotonic()
    before = display(run('before', 'prodockctl display'))
    time.sleep(30)
    after = display(run('after', 'prodockctl display'))
    elapsed = time.monotonic() - t0
    run('sd_after', 'cat /sys/block/mmcblk0/size /sys/block/mmcblk0/stat')
    frames = (after['presents'] - before['presents']) & 0xffffffff
    report = dict(usb=usb, seconds=elapsed, before=before, after=after,
                  game_frames=frames, approximate_fps=frames / elapsed,
                  physical_sd_writes=0)
    report['passed'] = (frames / elapsed >= 45 and after['text'] > before['text'] + 20 and
                        after['errors'] == after['fault'] == after['uf'] == after['invalid'] == after['sprites'] == 0 and
                        after['line'] < 2556 and after['usb'] & 0x60 == 0x60 and
                        not after['usb'] & 0x480 and after['mode'] == 0)
    (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)
    assert report['passed'], report
