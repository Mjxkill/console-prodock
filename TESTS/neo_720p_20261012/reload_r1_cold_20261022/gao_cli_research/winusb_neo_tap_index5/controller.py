#!/usr/bin/env python3
"""Read the FPGA TAP identity through the vendor libusb cable selection."""
import fcntl
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent))
from probe_route9_led_compare import run_child, usb_identity

out = HERE / 'winusb_neo_tap_index5'
assert not out.exists()
with (ROOT / 'TESTS/neo_board.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    active = subprocess.run(['ps', '-C', 'jtagserver', '-C', 'gao_analyzer', '-C', 'gao_sh',
        '-C', 'openocd', '-C', 'openFPGALoader', '-o', 'pid=,args='], capture_output=True, text=True)
    assert active.returncode == 1 and not active.stdout.strip()
    identity = usb_identity()
    assert identity['neo']['path'].endswith('/3-4.4.1')
    assert identity['esp']['path'].endswith('/3-4.4.2')
    out.mkdir()
    (out / 'identity.json').write_text(json.dumps(dict(usb=identity,
        candidate_location=13377, candidate_cable_index=5,
        selection_not_confirmed_until_fpga_id=True, fpga_programmed=False,
        instruction='Vendor --scan only: no operation or bitstream'), indent=2) + '\n')
    command = ['/home/michael/gowin/Programmer/bin/programmer_cli', '--scan',
               '--cable-index', '5', '--location', '13377', '--frequency', '2.5MHz']
    try:
        run_child(command, out / 'scan.log', 20)
    finally:
        print((out / 'scan.log').read_text())
