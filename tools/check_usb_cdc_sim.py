#!/usr/bin/env python3
"""Verify the actual USB CDC FIFO and reset wiring with Icarus Verilog."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--iverilog', default='iverilog')
    p.add_argument('--vvp', default='vvp')
    p.add_argument('--ivl-root', type=Path)
    p.add_argument('--reference', type=Path, default=Path(
        '/home/michael/gowin/ref/TangMega-138KPro-example/usb2_soft/usb_uart_loopback/src/usb_device_controller'))
    p.add_argument('--primitives', type=Path, default=Path(
        '/home/michael/gowin/Gowin_V1.9.12_linux/IDE/simlib/gw5a/prim_sim.v'))
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--reset-only', action='store_true', help='run only the controller/FIFO reset regression')
    a = p.parse_args()
    fifo = ROOT / 'tang/rtl/usb/sync_fifo/usb_fifo.v'
    model = a.reference / 'usb_device_controller.vo'
    project_controller = ROOT / 'tang/rtl/usb/usb_device_controller.v'
    if project_controller.read_bytes() != (a.reference / 'usb_device_controller.v').read_bytes():
        p.error('Controller model does not correspond to the project synthesis netlist')
    paths = [fifo, model, project_controller, a.primitives,
             ROOT / 'TESTS/rtl/usb_cdc_fifo_tb.sv',
             ROOT / 'TESTS/rtl/usb_controller_reset_tb.sv',
             ROOT / 'tang/rtl/console_top.v']
    report = {'scope': 'Digital dual-clock FIFO and controller/application reset',
              'limits': 'No metastability, physical CDC routing or USB enumeration model',
              'sha256': {str(x): hashlib.sha256(x.read_bytes()).hexdigest() for x in paths},
              'cases': []}
    a.output.parent.mkdir(parents=True, exist_ok=True)

    def record(name, command, expected_failure=False):
        r = subprocess.run(command, capture_output=True, text=True, timeout=120)
        ok = (r.returncode != 0 and 'FIFO reset does not follow system reset asynchronously' in r.stdout
              if expected_failure else r.returncode == 0 and 'PASS' in r.stdout)
        report['cases'].append(dict(name=name, returncode=r.returncode, stdout=r.stdout,
                                    stderr=r.stderr, expected_failure=expected_failure, passed=ok))
        a.output.write_text(json.dumps(report, indent=2) + '\n')
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)
        return ok

    with tempfile.TemporaryDirectory(prefix='console-usb-cdc-') as tmp:
        def compile_tb(name, vendor=False, legacy=False):
            output = Path(tmp) / (name + ('_legacy' if legacy else '') + '.vvp')
            cmd = [a.iverilog]
            if a.ivl_root:
                cmd += ['-B', str(a.ivl_root)]
            cmd += ['-g2012', '-s', name, '-o', str(output)]
            if legacy:
                cmd += ['-DLEGACY_RESET']
            cmd += [str(ROOT / f'TESTS/rtl/{name}.sv'), str(fifo)]
            if vendor:
                cmd += [str(model), str(a.primitives)]
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=60)
            return str(output)

        if not a.reset_only:
            cdc = compile_tb('usb_cdc_fifo_tb')
            for wr, rd in ((125, 124.5), (124.5, 125), (60, 59.94), (60, 60), (80, 60), (60, 80)):
                for phase in (0, 0.317, 3.713):
                    record(f'FIFO {wr}/{rd} MHz phase {phase} ns',
                           [a.vvp, cdc, f'+WRITE_MHZ={wr}', f'+READ_MHZ={rd}', f'+PHASE_NS={phase}'])
        old = compile_tb('usb_controller_reset_tb', vendor=True, legacy=True)
        record('Legacy reset regression (must fail)', [a.vvp, old], expected_failure=True)
        new = compile_tb('usb_controller_reset_tb', vendor=True)
        record('Common reset with original controller model', [a.vvp, new])
    report['pass'] = all(x['passed'] for x in report['cases'])
    report['sources_unchanged'] = all(hashlib.sha256(Path(x).read_bytes()).hexdigest() == h
                                    for x, h in report['sha256'].items())
    a.output.write_text(json.dumps(report, indent=2) + '\n')
    return 0 if report['pass'] and report['sources_unchanged'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
