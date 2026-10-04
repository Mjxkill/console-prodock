#!/usr/bin/env python3
"""Validate a timing-passed GPU build over repeated SRAM loads on the Pro Dock.

Stops at the first failure. Never resets a host controller or programs flash.
Uses only FTDI 2023112818 and console 359f:2011 / 11252024.
Requires a fresh USB address and complete configuration after every load.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

from serial.tools import list_ports

ROOT = Path(__file__).resolve().parents[1]


def target_busdev():
    targets = []
    for path in Path('/sys/bus/usb/devices').glob('*'):
        try:
            if ((path/'idVendor').read_text().strip() == '0403'
                    and (path/'idProduct').read_text().strip() == '6010'
                    and (path/'serial').read_text().strip() == '2023112818'):
                targets.append(f"{int((path/'busnum').read_text())}:{int((path/'devnum').read_text())}")
        except OSError:
            pass
    if len(targets) != 1:
        raise RuntimeError(f'Expected one Pro Dock FTDI 2023112818, found {targets}')
    return targets[0]


def console_snapshot():
    devices = []
    for path in Path('/sys/bus/usb/devices').glob('*'):
        try:
            if ((path/'idVendor').read_text().strip(),
                (path/'idProduct').read_text().strip(),
                (path/'serial').read_text().strip()) != ('359f', '2011', '11252024'):
                continue
            devices.append(dict(topology=path.name,
                bus=int((path/'busnum').read_text()), address=int((path/'devnum').read_text()),
                speed_mbps=int((path/'speed').read_text()),
                configuration=(path/'bConfigurationValue').read_text().strip(),
                interfaces=int((path/'bNumInterfaces').read_text(), 16),
                authorized=(path/'authorized').read_text().strip()))
        except (OSError, ValueError):
            pass  # Device may disappear while reconfiguration is in progress.
    if len(devices) > 1:
        raise RuntimeError(f'Ambiguous console devices: {devices}')
    return devices[0] if devices else None


def fresh_configuration(before, after):
    if not after or after['configuration'] != '1' or after['interfaces'] != 2 or after['authorized'] != '1':
        return False
    return before is None or (before['bus'], before['address']) != (after['bus'], after['address'])


def wait_console(before=None):
    deadline = time.monotonic()+25
    while time.monotonic() < deadline:
        ports = [p for p in list_ports.comports() if (p.vid, p.pid) == (0x359f, 0x2011)]
        if len(ports) > 1:
            raise RuntimeError(f'Ambiguous console: {ports}')
        if len(ports) == 1:
            if ports[0].serial_number != '11252024':
                raise RuntimeError('Wrong console serial number')
            device = console_snapshot()
            if fresh_configuration(before, device):
                return ports[0].device, device
        time.sleep(.2)
    raise RuntimeError(f'No fresh configured console within 25 seconds; before={before}, after={console_snapshot()}')


def run(command, log, timeout):
    with log.open('x') as stream:
        result = subprocess.run(command, cwd=ROOT, stdout=stream,
                                stderr=subprocess.STDOUT, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'Exit {result.returncode}: {command}; see {log}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--rounds', type=int, default=3)
    parser.add_argument('--usb-rounds', type=int, default=100)
    parser.add_argument('--usb-only', action='store_true',
                        help='run USB validation only; never claims a GPU pass')
    parser.add_argument('--load-only', action='store_true',
                        help='one verified SRAM load and enumeration, no USB traffic or GPU test')
    parser.add_argument('--expected-usb-speed', type=int, choices=(12, 480), default=480,
                        help='reject enumeration at a speed different from this diagnostic variant')
    args = parser.parse_args()
    if not 1 <= args.rounds <= 10 or not 1 <= args.usb_rounds <= 1000:
        parser.error('rounds 1..10, usb-rounds 1..1000')
    if args.load_only and args.rounds != 1:
        parser.error('--load-only requires --rounds 1')
    args.out = args.out.resolve()
    stage = args.stage.resolve(strict=True)
    if (stage/'usb_diagnostic.json').exists() and not (args.usb_only or args.load_only):
        parser.error('GPU-disabled diagnostic requires --usb-only')
    if not stage.is_relative_to(ROOT/'tang/impl'):
        parser.error('stage must be an immutable build under tang/impl')
    name = f'console_{stage.name}'
    bitstream = stage/f'impl/pnr/{name}.fs'
    digest = hashlib.sha256(bitstream.read_bytes()).hexdigest()
    if digest != (stage/'bitstream.sha256').read_text().split()[0]:
        raise RuntimeError('Bitstream hash mismatch')
    manifest = json.loads((stage/'sources.json').read_text())
    for source, expected in manifest.items():
        if hashlib.sha256((stage/'source'/source).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f'Frozen source mismatch: {source}')
    report = (stage/f'impl/pnr/{name}.tr').read_text()
    slacks = [float(s) for s in re.findall(r'^Slack\s*:\s*([-\d.]+)', report, re.M)]
    tns = re.findall(r'^\s*\S+\s+(?:setup|hold)\s+([-\d.]+)\s+(\d+)\s*$', report, re.M)
    if not slacks or not tns or min(slacks) < 0 or any(float(s) < 0 or int(n) for s, n in tns):
        raise RuntimeError('Timing gate failed; refusing to load')
    args.out.mkdir(parents=True, exist_ok=False)
    summary = dict(stage=str(stage), sha256=digest, sources=len(manifest),
                   minimum_slack_ns=min(slacks), status='running', runs=[],
                   scope='load_only' if args.load_only else ('usb_only' if args.usb_only else 'usb_and_gpu'))
    tool_source = Path(__file__).read_bytes()
    (args.out/'reload_test_tool.py').write_bytes(tool_source)
    summary['test_tool_sha256'] = hashlib.sha256(tool_source).hexdigest()
    try:
        for index in range(1, args.rounds+1):
            folder = args.out/f'load{index}'
            folder.mkdir()
            busdev = target_busdev()  # Re-identify before EVERY load.
            attempt = dict(load=index, busdev=busdev, target_serial='2023112818',
                           status='loading', usb_before=console_snapshot(),
                           load_started_unix=time.time())
            summary['runs'].append(attempt)
            print(f'LOAD {index}/{args.rounds}: Pro Dock 2023112818 at {busdev}', flush=True)
            run(['openFPGALoader', '--busdev-num', busdev, '-b', 'tangmega138k',
                 '-m', str(bitstream)], folder/'loader.log', 120)
            if not re.search(r'^DONE\s*$', (folder/'loader.log').read_text(), re.M):
                raise RuntimeError('Loader did not report DONE')
            attempt['load_completed_unix'] = time.time()
            attempt['status'] = 'enumerating'
            port, device = wait_console(attempt['usb_before'])
            attempt['usb_after'] = device
            attempt['fresh_enumeration'] = True
            speed = device['speed_mbps']
            attempt['usb_speed_mbps'] = speed
            if args.expected_usb_speed is not None and speed != args.expected_usb_speed:
                raise RuntimeError(f'USB speed {speed} Mbps, expected {args.expected_usb_speed}')
            if args.load_only:
                attempt.update(port=port, status='loaded')
                continue
            attempt.update(port=port, status='usb_testing', usb_rounds=args.usb_rounds)
            # No private control request primes the device before this test.
            run(['python3', 'tools/check_usb_stress.py', '--rounds', str(args.usb_rounds),
                 '--out', str(folder/'usb')], folder/'usb.log', 30+args.usb_rounds*15)
            attempt.update(status='pass', usb='pass')
            print(f'LOAD {index}: USB {args.usb_rounds} rounds PASS', flush=True)
        if args.load_only:
            summary['status'] = 'loaded'
            print('LOADED: fresh enumeration; USB traffic and GPU not tested', flush=True)
            return
        if args.usb_only:
            summary['status'] = 'pass'
            print('PASS: USB only; GPU not tested', flush=True)
            return
        run(['python3', 'tools/check_gpu_console.py', '--wait', '20'], args.out/'gpu.log', 900)
        summary['status'] = 'pass'
        print('PASS: repeated enumeration, exact USB stress and full GPU suite after final load', flush=True)
    except Exception as error:
        summary['status'] = 'fail'
        summary['error'] = str(error)
        raise
    finally:
        (args.out/'result.json').write_text(json.dumps(summary, indent=2)+'\n')


if __name__ == '__main__':
    main()
