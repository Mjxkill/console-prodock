#!/usr/bin/env python3
"""Essai SRAM de la référence Sipeed intacte, boucle UART brute 115200.

Uniquement FTDI2023112818 et CDC359f:2010/11252024. Exige un manifeste
local de sources/bitstream/rapport et un timing non négatif avant chargement.
La référence n'a ni CPU ni GPU ; ce test n'en revendique aucune validation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def verify(stage):
    stage = stage.resolve(strict=True)
    if not stage.is_relative_to(ROOT/'tang/impl'):
        raise RuntimeError('Stage hors de tang/impl')
    manifest = json.loads((stage/'board_test_manifest.json').read_text())
    for name, digest in manifest['files'].items():
        path = (stage/name).resolve(strict=True)
        if not path.is_relative_to(stage):
            raise RuntimeError('Chemin du manifeste hors du stage')
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise RuntimeError(f'Empreinte incorrecte : {name}')
    if any(name not in manifest['files'] for name in (manifest['bitstream'], manifest['timing'])):
        raise RuntimeError('Bitstream ou timing non couvert par les empreintes')
    report = (stage/manifest['timing']).read_text()
    slacks = [float(x) for x in re.findall(r'^Slack\s*:\s*([-\d.]+)', report, re.M)]
    totals = re.findall(r'^\s*\S+\s+(?:setup|hold)\s+([-\d.]+)\s+(\d+)\s*$', report, re.M)
    if not slacks or not totals or min(slacks) < 0 or any(float(s) < 0 or int(n) for s, n in totals):
        raise RuntimeError('Timing négatif ou rapport incomplet ; chargement refusé')
    return stage, manifest, min(slacks)


def wait_reference():
    from serial.tools import list_ports
    deadline = time.monotonic()+25
    while time.monotonic() < deadline:
        ports = [p for p in list_ports.comports()
                 if (p.vid, p.pid, p.serial_number) == (0x359f, 0x2010, '11252024')]
        if len(ports) > 1:
            raise RuntimeError('Référence USB ambiguë')
        if ports:
            devices = []
            for path in Path('/sys/bus/usb/devices').glob('*'):
                try:
                    if tuple((path/k).read_text().strip() for k in ('idVendor','idProduct','serial')) == ('359f','2010','11252024'):
                        devices.append(dict(topology=path.name, speed=(path/'speed').read_text().strip()))
                except OSError:
                    pass
            if len(devices) != 1 or devices[0]['speed'] != '480':
                raise RuntimeError(f'Identification/vitesse incorrecte : {devices}')
            return ports[0].device, devices[0]
        time.sleep(.2)
    raise RuntimeError('Référence USB non énumérée en25s')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    stage, manifest, slack = verify(args.stage)
    if args.check_only:
        print(f'PASS : {len(manifest["files"])} empreintes, timing minimum {slack:.3f} ns ; aucun accès carte')
        return 0
    if args.out is None:
        parser.error('--out requis pour un essai matériel')
    import serial
    from check_gpu_reloads import target_busdev
    args.out.mkdir(parents=True, exist_ok=False)
    result = dict(stage=str(stage), minimum_slack_ns=slack,
                  bitstream_sha256=manifest['files'][manifest['bitstream']],
                  scope='Référence Sipeed USB seule, aucun test CPU/GPU',
                  status='loading', samples=[], target_serial='2023112818')
    deadline = None
    def read_window(dev, seconds):
        got = bytearray()
        until = time.monotonic()+seconds
        while time.monotonic() < until:
            got.extend(dev.read(min(dev.in_waiting,4096) or 1))
        return got
    try:
        busdev = target_busdev()
        result['busdev'] = busdev
        # Refuser un lecteur actif avant la reconfiguration de cette carte.
        from serial.tools import list_ports
        for p in list_ports.comports():
            if p.vid == 0x359f and p.serial_number == '11252024' and p.pid in (0x2010,0x2011):
                owner = subprocess.run(['fuser', p.device], capture_output=True, text=True)
                if owner.returncode != 1 or owner.stdout.strip() or owner.stderr.strip():
                    raise RuntimeError('Port CDC occupé ou impossible à vérifier')
        command = ['openFPGALoader','--busdev-num',busdev,'-b','tangmega138k','-m',str(stage/manifest['bitstream'])]
        result['load_command'] = command
        with (args.out/'loader.log').open('x') as stream:
            proc = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=120)
        if proc.returncode or not re.search(r'^DONE\s*$',(args.out/'loader.log').read_text(),re.M):
            raise RuntimeError('Chargement SRAM sans DONE')
        port, device = wait_reference()
        result.update(status='testing', port=port, device=device)
        with serial.Serial(port,115200,timeout=.01,write_timeout=2,exclusive=True) as dev:
            initial = read_window(dev,.1)
            if initial:
                raise RuntimeError(f'Données avant émission : {initial.hex()}')
            deadline = time.monotonic()+45
            rng = random.Random(20261002)
            payloads = [bytes([(i*73+17)&255]) for i in range(1000)]
            payloads += [rng.randbytes(n) for n in (64,256,1024)]
            for index, expected in enumerate(payloads):
                if time.monotonic() >= deadline:
                    raise RuntimeError('Limite utile45s atteinte')
                start = time.monotonic()
                dev.write(expected)
                got = bytearray()
                first = None
                until = min(deadline, start+1+len(expected)*10/115200)
                while len(got) < len(expected) and time.monotonic() < until:
                    chunk = dev.read(len(expected)-len(got))
                    if chunk and first is None:
                        first = (time.monotonic()-start)*1000
                    got.extend(chunk)
                got.extend(read_window(dev,.01))
                sample = dict(index=index, expected=expected.hex(), received=got.hex(),
                              first_byte_ms=first, elapsed_ms=(time.monotonic()-start)*1000)
                result['samples'].append(sample)
                if got != expected:
                    got.extend(read_window(dev,1))
                    sample['received_after_grace'] = got.hex()
                    result['status'] = 'mismatch'
                    print(json.dumps(sample),flush=True)
                    return 1
        result['status'] = 'pass'
        print('PASS : 1000 échos unitaires et blocs64/256/1024 exacts ; USB seul')
        return 0
    except Exception as error:
        result.update(status='error', error=str(error))
        print(str(error),flush=True)
        return 1
    finally:
        (args.out/'result.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')


if __name__ == '__main__':
    raise SystemExit(main())
