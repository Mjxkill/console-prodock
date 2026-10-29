#!/usr/bin/env python3
"""Protected launcher; actual reader baseline plus independent adversarial suite."""
from pathlib import Path
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parent
result = subprocess.run(['/usr/bin/python3', '-B', 'readback_r1/test_readback.py'],
                        cwd=HERE, capture_output=True, text=True, timeout=5)
print(result.stdout + result.stderr)
if result.returncode:
    raise SystemExit(result.returncode)
print('FULL_CHAIN_COMPILE_PASS BASELINE_PASS: exact compiled reader executed by bounded RV32 interpreter')
sys.path.insert(0, str(HERE/'readback_r1'))
suite = unittest.defaultTestLoader.discover(str(HERE), pattern='adversarial.py')
result = unittest.TextTestRunner(verbosity=2).run(suite)
if result.testsRun < 10 or result.skipped:
    print('Need at least ten genuinely executed independent cases, no skip')
    raise SystemExit(1)
raise SystemExit(0 if result.wasSuccessful() else 1)
