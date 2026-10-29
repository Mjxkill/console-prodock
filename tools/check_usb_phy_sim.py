#!/usr/bin/env python3
"""Run the original Gowin USB2 PHY model with independent serial USB clocks.

Requires Icarus Verilog and the separately installed Sipeed/Gowin model/library.
No synthesis, board access, internal force or edits to vendor files are involved.
"""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from gowin_toolchain import PRIMITIVES

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = Path('/home/michael/gowin/ref/TangMega-138KPro-example/usb2_soft/usb_uart_loopback/src')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iverilog', default='iverilog')
    parser.add_argument('--vvp', default='vvp')
    parser.add_argument('--ivl-root', type=Path)
    parser.add_argument('--reference', type=Path, default=REFERENCE)
    parser.add_argument('--primitives', type=Path, default=PRIMITIVES)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--jobs', type=int, choices=(1, 2), default=1)
    parser.add_argument('--direction', choices=('rx', 'tx'), default='rx')
    parser.add_argument('--quick', action='store_true', help='nominal and opposite ppm corners at one phase')
    args = parser.parse_args()
    phy = args.reference / 'usb2_0_softphy/usb2_0_softphy.vo'
    encrypted = args.reference / 'usb2_0_softphy/usb2_0_softphy.v'
    project_phy = ROOT / 'tang/rtl/usb/usb2_0_softphy.v'
    top = 'usb_phy_drift_tb' if args.direction == 'rx' else 'usb_phy_tx_drift_tb'
    marker = ('PASS USB PHY independent serial clock' if args.direction == 'rx'
              else 'PASS USB PHY TX independent host CDR')
    tb = ROOT / f'TESTS/rtl/{top}.sv'
    if sha(encrypted) != sha(project_phy):
        parser.error('Reference synthesis netlist differs from the project PHY')
    hashes = {str(p): sha(p) for p in (phy, encrypted, project_phy, args.primitives, tb)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        'scope': f'Digital HS {args.direction} path through original PHY; no SDF or analog model',
        'limits': ['Does not prove metastability immunity or physical timing',
                   'Does not simulate enumeration or controller ACK retirement',
                   'UTMI HS mode selected by testbench; reset/lock applied at PHY inputs'],
        'sha256': hashes,
        'cases': [],
    }
    # Both transmitters can be +/-500 ppm. The opposite corners give ~1000 ppm
    # relative error. The two same-sign corners test absolute clock scaling too.
    cases = [(host, card, phase)
             for host, card in ((0, 0), (500, -500), (-500, 500), (500, 500), (-500, -500))
             for phase in (0.0, 0.137, 0.317, 0.521, 0.937, 1.271, 1.683, 2.001)]
    if args.quick:
        cases = [(host, card, 0.317) for host, card in ((0, 0), (500, -500), (-500, 500))]
    with tempfile.TemporaryDirectory(prefix='console-usb-phy-') as tmp:
        executable = Path(tmp) / 'phy.vvp'
        compile_cmd = [args.iverilog]
        if args.ivl_root:
            compile_cmd += ['-B', str(args.ivl_root)]
        compile_cmd += ['-g2012', '-s', top, '-o', str(executable),
                        str(tb), str(phy), str(args.primitives)]
        compiled = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=60)
        report['compile'] = {'command': compile_cmd, 'returncode': compiled.returncode,
                             'stdout': compiled.stdout, 'stderr': compiled.stderr}
        if compiled.returncode:
            args.output.write_text(json.dumps(report, indent=2) + '\n')
            raise SystemExit(compiled.stderr)

        def run(case):
            host, card, phase = case
            cmd = [args.vvp, str(executable), f'+HOST_PPM={host}',
                   f'+CARD_PPM={card}', f'+PHASE_NS={phase}']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            return {'host_ppm': host, 'card_ppm': card, 'phase_ns': phase,
                    'returncode': result.returncode, 'stdout': result.stdout,
                    'stderr': result.stderr,
                    'pass': result.returncode == 0 and
                            marker in result.stdout}

        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            for result in pool.map(run, cases):
                report['cases'].append(result)
                args.output.write_text(json.dumps(report, indent=2) + '\n')
                print(('PASS' if result['pass'] else 'FAIL') +
                      f" host={result['host_ppm']:+} ppm card={result['card_ppm']:+} ppm"
                      f" phase={result['phase_ns']:.3f} ns", flush=True)
    report['pass'] = all(c['pass'] for c in report['cases'])
    report['sources_unchanged'] = all(sha(Path(p)) == h for p, h in hashes.items())
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(f"{sum(c['pass'] for c in report['cases'])}/{len(cases)} passed; {args.output}")
    return 0 if report['pass'] and report['sources_unchanged'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
