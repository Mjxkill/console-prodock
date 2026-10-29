#!/usr/bin/env python3
"""Prove CPU JTAG to UART association before any payload/launcher RAM write.

A cold-state guard first checks privilege, SATP, PC and MPRV. Then JTAG sends
a fresh nonce through UART2; only receipt on the selected physical USB path
accepts the association. This operation changes no DDR, ILM, flash or SD byte.
"""
import argparse
import fcntl
import json
from pathlib import Path
import subprocess
import time
import uuid
import serial

PROFILES = {'2023112818': '3', '2025071717': '1'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', choices=PROFILES, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    branch = PROFILES[args.target]
    port = f'/dev/serial/by-path/pci-0000:00:14.0-usb-0:7.{branch}:1.0'
    token = ('PD_CPU_BIND_' + uuid.uuid4().hex[:16]).encode()
    commands = ['exec InhibitConnectRetries = 1', 'exec DisableFlashDL',
                'exec DisableFlashBPs', 'exec SetAllowFlashCache = 0', 'connect', 'h']
    commands += [f'w4 0xf0300020 0x{b:02x}' for b in b'\r\n' + token + b'\r\n']
    commands += ['g', 'q']
    script = args.out / 'bind.jlink'
    script.write_text('\n'.join(commands) + '\n')
    report = dict(passed=False, target=args.target, port=port, token=token.decode(),
                  ddr_writes=0, ilm_writes=0, started_unix=time.time())
    try:
        with open('/tmp/prodock-diagnostic.lock', 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with serial.Serial(port, 115200, timeout=.1, exclusive=True) as uart:
                with (args.out / 'jlink.log').open('x') as log:
                    result = subprocess.run(['JLinkExe', '-SelectEmuBySN', '506005083',
                        '-Device', 'A25', '-If', 'JTAG', '-Speed', '100', '-JTAGConf', '-1,-1',
                        '-NoGui', '1', '-ExitOnError', '1', '-JLinkScriptFile',
                        '/tmp/cpu_cold_guard.JLinkScript', '-CommanderScript', str(script)],
                        stdout=log, stderr=subprocess.STDOUT, timeout=30)
                end = time.monotonic() + 5
                received = bytearray()
                while time.monotonic() < end:
                    received.extend(uart.read(4096))
                    if token + b'\r\n' in received:
                        break
                (args.out / 'uart.bin').write_bytes(received)
                raw = (args.out / 'jlink.log').read_text()
                assert result.returncode == 0 and 'COLD_CPU_GUARD_OK' in raw
                assert token + b'\r\n' in received, 'CPU nonce not received on selected console'
                report['passed'] = True
    except BaseException as error:
        report['error'] = repr(error)
    report['finished_unix'] = time.time()
    (args.out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
