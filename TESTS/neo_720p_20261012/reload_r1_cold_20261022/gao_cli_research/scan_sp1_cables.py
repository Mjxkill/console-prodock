#!/usr/bin/env python3
"""Read-only USB cable enumeration with the separately installed Programmer SP1."""
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent))
from probe_route9_led_compare import run_child, usb_identity

tool = Path('/home/michael/gowin/programmer1.9.12_SP1(2565).Linux.x86/Programmer/bin/programmer_cli')
out = HERE / 'sp1_cable_scan'
assert not out.exists()
with (ROOT / 'TESTS/neo_board.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    active = subprocess.run(['ps', '-C', 'jtagserver', '-C', 'gao_analyzer', '-C', 'gao_sh',
        '-C', 'openocd', '-C', 'openFPGALoader', '-o', 'pid=,args='], capture_output=True, text=True)
    assert active.returncode == 1 and not active.stdout.strip(), 'Another board operator exists'
    identity = usb_identity()
    out.mkdir()
    (out / 'identity.json').write_text(json.dumps(dict(usb=identity,
        programmer=str(tool), programmer_sha256=hashlib.sha256(tool.read_bytes()).hexdigest(),
        fpga_programmed=False, gao_capture_attempted=False), indent=2) + '\n')
    run_child([str(tool), '--scan-cables'], out / 'scan.log', 15)
    print((out / 'scan.log').read_text())
