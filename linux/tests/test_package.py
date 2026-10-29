#!/usr/bin/env python3
import hashlib
import json
import os
from pathlib import Path
p = Path(__file__).resolve().parents[1] / ('build-neo' if os.environ.get('CONSOLE_BOARD')=='neo' else 'build')
m = json.loads((p / 'manifest.json').read_text())
if m['load'] != 0x07c00000 or m['kernel'] != 0x08000000:
    raise SystemExit('Wrong Pro Dock load addresses')
for name, expected in m['files'].items():
    data = (p / name).read_bytes()
    if len(data) != expected['bytes'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
        raise SystemExit('Artifact mismatch: ' + name)
for key, name in [('launcher', 'launch.bin'), ('launcher_usb', 'launch_usb.bin'),
                  ('launcher_packed', 'launch_packed.bin')]:
    expected = m[key]
    data = (p / name).read_bytes()
    if (expected['load'] != 0xa0000000 or expected['entry'] != 0xa000000c or
        not 12 < len(data) == expected['bytes'] <= 65536 or
        hashlib.sha256(data).hexdigest() != expected['sha256']):
        raise SystemExit('Launcher mismatch: ' + name)
if m['launcher_usb']['stage'] != 0x08000000:
    raise SystemExit('Wrong USB staging address')
if m['launcher_packed']['stage'] != 0x10000000:
    raise SystemExit('Wrong compact JTAG staging address')
print('PASS: Pro Dock Linux payload addresses, sizes and hashes')
