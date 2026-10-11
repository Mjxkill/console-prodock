#!/usr/bin/env python3
"""Régression EP1/FIFO double horloge, phases décalées et purge horloge arrêtée.

Simulation numérique uniquement : ce banc ne valide ni le PHY ni le timing
physique. Les fréquences volontairement différentes éprouvent le CDC.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    'TESTS/rtl/usb_msc_port_tb.sv',
    'tang/rtl/usb/usb_msc_port.v', 'tang/rtl/usb/usb_msc_empty.v',
    'tang/rtl/usb/sync_fifo/usb_fifo.v',
    'tang/rtl/usb/sync_fifo/sync_tx_pkt_fifo.v',
    'tang/rtl/usb/sync_fifo/sync_rx_pkt_fifo.v',
    'tang/rtl/board/ddr_dcfifo.v', 'tang/rtl/board/cdc_word.v',
    'tang/rtl/video/video_bus_stage.v',
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--bus-stage', action='store_true')
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = dict(pass_all=False, bus_stage=args.bus_stage, cases=[], sha256={
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in SOURCES + ['TESTS/test_usb_msc_port.py']})
    try:
        for name, usb_half, bus_half, phase in [
            ('nominal', 8.333, 6.250, 0.0),
            ('usb_lent', 8.342, 6.242, 2.137),
            ('usb_rapide', 8.325, 6.258, 5.731),
        ]:
            stage = out / name
            stage.mkdir()
            result = dict(name=name, usb_half_ns=usb_half,
                          bus_half_ns=bus_half, phase_ns=phase, passed=False)
            report['cases'].append(result)
            command = [
                'verilator', '--binary', '-j', '4', '--timing', '-Wno-fatal',
                '--top-module', 'usb_msc_port_tb', '--Mdir', str(stage / 'obj'),
                f'-GUSB_HALF_NS={usb_half}', f'-GBUS_HALF_NS={bus_half}',
                f'-GBUS_PHASE_NS={phase}', f'-GBUS_STAGE={int(args.bus_stage)}', *[str(ROOT / s) for s in SOURCES],
            ]
            with (stage / 'build.log').open('w') as log:
                subprocess.run(command, stdout=log, stderr=log, check=True)
            with (stage / 'simulation.log').open('w') as log:
                subprocess.run([str(stage / 'obj/Vusb_msc_port_tb')],
                               stdout=log, stderr=log, check=True, timeout=120)
            text = (stage / 'simulation.log').read_text()
            if 'STOPPED CLOCK FLUSH PASS' not in text or 'PASS usb_msc_port:' not in text:
                raise RuntimeError(f'Résultat incomplet : {stage}')
            result['passed'] = True
            result['summary'] = [s for s in text.splitlines() if 'PASS' in s]
            print(name + ': ' + '; '.join(result['summary']), flush=True)
        report['pass_all'] = True
    finally:
        (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
