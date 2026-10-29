#!/usr/bin/env python3
"""Compare GAO's child library environment during read-only cable discovery."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(HERE.parent))
from gowin_toolchain import environment
from probe_route9_led_compare import usb_identity

out = HERE / 'programmer_env_probe'
assert not out.exists()
with (ROOT / 'TESTS/neo_board.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    active = subprocess.run(['ps', '-C', 'jtagserver', '-C', 'gao_analyzer', '-C', 'gao_sh',
        '-C', 'openocd', '-C', 'openFPGALoader', '-o', 'pid=,args='], capture_output=True, text=True)
    assert active.returncode == 1 and not active.stdout.strip()
    out.mkdir()
    records = dict(usb=usb_identity(), fpga_programmed=False, probes=[])
    for name, env in [('normal', dict(os.environ)), ('gao_libraries', environment())]:
        command = ['/home/michael/gowin/Programmer/bin/programmer_cli', '--scan-cables', 'L']
        result = subprocess.run(command, env=env, cwd=out, capture_output=True, text=True, timeout=15)
        (out / (name + '.log')).write_text(result.stdout + result.stderr)
        records['probes'].append(dict(name=name, returncode=result.returncode))
        print(name, result.returncode, result.stdout, result.stderr, flush=True)
    (out / 'result.json').write_text(json.dumps(records, indent=2) + '\n')
