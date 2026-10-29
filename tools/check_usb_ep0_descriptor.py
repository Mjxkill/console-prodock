#!/usr/bin/env python3
"""A/B rxrdy EP0 : contrôleur FS3.2 exporté officiellement, UTMI idéal."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time
from gowin_toolchain import PRIMITIVES

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGE = ROOT/'tang/impl/gpu_usb_controller32_fs_model_r1'
TOOLS = Path('/tmp/console-usb-sim-tools/extracted/usr')


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage', type=Path, default=DEFAULT_STAGE)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--ready', type=int, choices=(0, 1), required=True)
    p.add_argument('--length', type=int, choices=(8, 18, 64), required=True)
    p.add_argument('--timeout', type=int, default=180)
    p.add_argument('--sipeed', action='store_true',
                   help='Comparer le modèle Sipeed original en repli FS, même ROM et mêmes ports')
    a = p.parse_args()
    if a.output.exists():
        p.error('Le rapport de sortie existe déjà')
    provenance = json.loads((a.stage/'provenance.json').read_text())
    for name, digest in provenance['export_inputs'].items():
        if sha(a.stage/name) != digest:
            p.error('Entrée export modifiée : '+name)
    if sha(Path(provenance['origin'])) != provenance['sha256']:
        p.error('Netlist r23 originale modifiée')
    model = a.stage/'wrapper_export/controller32_fs/impl/pnr/controller32_fs.vo'
    sources = [ROOT/'TESTS/rtl/usb_ep0_descriptor_tb.sv', model, PRIMITIVES]
    if a.sipeed:
        reference = Path('/home/michael/gowin/ref/TangMega-138KPro-example/usb2_soft/usb_uart_loopback/src/usb_device_controller')
        sources = [ROOT/'TESTS/rtl/usb_ep0_descriptor_tb.sv',
                   a.stage/'usb_ep0_controller_model.v', a.stage/'usb_descriptor.v',
                   reference/'usb_device_controller.vo', PRIMITIVES]
    files = sources + [a.stage/'provenance.json', a.stage/'generate_wrapper.log']
    files += [a.stage/name for name in provenance['export_inputs']]
    hashes = {str(x): sha(x) for x in files}
    report = dict(ready=a.ready, requested_length=a.length,
                  scope='FS3.2 GET_DESCRIPTOR avant/après SET_ADDRESS : SETUP, DATA et STATUS OUT',
                  limitations=['UTMI numérique idéal ; PHY FS non simulé.',
                               'Netlist r23 intacte exportée par Gowin avec ROM FS réelle.',
                               'Aucun SDF, aucune preuve de timing ni essai matériel.'],
                  sha256=hashes)
    report['controller'] = 'Sipeed original, repli FS' if a.sipeed else 'Gowin3.2 FSSUPPORT r23'
    if a.sipeed:
        report['limitations'][1] = 'Modèle Sipeed original ; descripteur et wrapper ouverts identiques au témoin FS.'
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='console-usb-ep0-') as tmp:
        exe = Path(tmp)/'ep0.vvp'
        command = [str(TOOLS/'bin/iverilog'), '-B', str(TOOLS/'lib/x86_64-linux-gnu/ivl'),
                   '-g2012', '-s', 'usb_ep0_descriptor_tb', '-o', str(exe)] + list(map(str, sources))
        built = subprocess.run(command, capture_output=True, text=True, timeout=60)
        report['compile'] = dict(command=command, returncode=built.returncode,
                                 stdout=built.stdout, stderr=built.stderr)
        if built.returncode:
            report['status'] = 'COMPILE_ERROR'
        else:
            command = [str(TOOLS/'bin/vvp'), str(exe), f'+READY={a.ready}', f'+LENGTH={a.length}']
            start = time.monotonic()
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=a.timeout)
                report['run'] = dict(command=command, returncode=result.returncode,
                                     stdout=result.stdout, stderr=result.stderr,
                                     elapsed_s=time.monotonic()-start)
                report['status'] = 'PASS' if result.returncode == 0 and 'PASS_EP0' in result.stdout else 'FAIL'
                report['data_passes'] = re.findall(r'DATA_PASS[^\n]*', result.stdout)
                report['completed_queries'] = re.findall(r'DESCRIPTOR_PASS[^\n]*', result.stdout)
                report['failure'] = next((line for line in result.stdout.splitlines() if 'FATAL:' in line), None)
            except subprocess.TimeoutExpired as exc:
                report['status'] = 'TIMEOUT'
                report['run'] = dict(stdout=(exc.stdout or b'').decode(errors='replace'),
                                     elapsed_s=time.monotonic()-start)
    report['sources_unchanged'] = all(sha(Path(name)) == digest for name, digest in hashes.items())
    a.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report.get(k) for k in ('status','ready','requested_length','failure','sources_unchanged')}, indent=2))
    if report['status'] in ('COMPILE_ERROR','TIMEOUT') or not report['sources_unchanged']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
