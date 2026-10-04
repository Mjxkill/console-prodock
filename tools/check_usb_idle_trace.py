#!/usr/bin/env python3
"""Test the passive IN/NAK trace and its two-clock JTAG-accessible snapshot."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ['TESTS/rtl/usb_idle_trace_tb.sv', 'tang/rtl/usb/usb_idle_trace.v',
           'tang/rtl/board/ddr_dcfifo.v']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    result = dict(status='running', sources={s: hashlib.sha256((ROOT/s).read_bytes()).hexdigest()
                                            for s in SOURCES}, cases=[])
    try:
        with (out/'compile.log').open('w') as log:
            subprocess.run(['verilator', '--binary', '--timing', '-j', '2',
                            '--top-module', 'usb_idle_trace_tb', '--Mdir', str(out/'obj')]
                           + SOURCES, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                           timeout=180, check=True)
        for hp, up, phase in [(6.25, 8.333333, .317), (6.241, 8.342, 3.713),
                              (8.342, 6.241, 1.117), (4, 4.016064, .213)]:
            p = subprocess.run([str(out/'obj/Vusb_idle_trace_tb'), f'+hp={hp}',
                                f'+up={up}', f'+phase={phase}'], cwd=ROOT,
                               capture_output=True, text=True, timeout=30)
            passed = p.returncode == 0 and 'PASS IN/NAK' in p.stdout
            result['cases'].append(dict(hp=hp, up=up, phase=phase, passed=passed,
                                        stdout=p.stdout, stderr=p.stderr))
            print(p.stdout, end='', flush=True)
            if not passed:
                raise RuntimeError('Trace simulation failed')
        result['status'] = 'pass'
    finally:
        if result['status'] == 'running':
            result['status'] = 'fail'
        (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
