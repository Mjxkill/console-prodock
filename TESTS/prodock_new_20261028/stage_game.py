#!/usr/bin/env python3
"""Preload the recovery game's compressed bytes before Linux starts.

The 8 MiB window at physical 0x04000000 belongs to the reserved GPU pool,
outside Linux RAM and all boot images. It is later read through the GPU's
read-only mmap by a CRC-checking helper. No framebuffer uses this window.
"""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import serial

ROOT = Path('/home/michael/console-validation-20261001')
PORT = '/dev/serial/by-path/pci-0000:00:14.0-usb-0:7.3:1.0'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--binding', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert __debug__ and 0 < args.file.stat().st_size <= 8 * 1024 * 1024
    assert hashlib.sha256(args.file.read_bytes()).hexdigest() == args.sha256
    binding = json.loads(args.binding.read_text())
    assert binding['passed'] and binding['target'] == '2023112818' and binding['port'] == PORT
    args.out.mkdir(parents=True, exist_ok=False)
    report = dict(passed=False, file_sha256=args.sha256, bytes=args.file.stat().st_size,
                  physical_address='0x04000000', target='2023112818', sd_writes=0)
    try:
        with open('/tmp/prodock-diagnostic.lock', 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            sys.path.insert(0, str(ROOT / 'tools'))
            from load_ilm import identify_console, quiesce_console
            with serial.Serial(PORT, 115200, timeout=.2, exclusive=True) as uart:
                identity, pause = identify_console(uart)
                (args.out / 'identity.txt').write_bytes(identity)
                (args.out / 'paused.txt').write_bytes(quiesce_console(uart, pause))
                commands = ['exec InhibitConnectRetries = 1', 'exec DisableFlashDL',
                    'exec DisableFlashBPs', 'exec SetAllowFlashCache = 0', 'connect', 'h', 'speed 4000',
                    f'loadfile {args.file.resolve()} 0x04000000 noreset',
                    f'verifybin {args.file.resolve()} 0x04000000', 'g', 'q']
                script = args.out / 'stage.jlink'
                script.write_text('\n'.join(commands) + '\n')
                with (args.out / 'jlink.log').open('x') as log:
                    result = subprocess.run(['JLinkExe', '-SelectEmuBySN', '506005083',
                        '-Device', 'A25', '-If', 'JTAG', '-Speed', '100', '-JTAGConf', '-1,-1',
                        '-NoGui', '1', '-ExitOnError', '1', '-JLinkScriptFile',
                        '/tmp/cpu_cold_guard.JLinkScript', '-CommanderScript', str(script)],
                        stdout=log, stderr=subprocess.STDOUT, timeout=300)
                raw = (args.out / 'jlink.log').read_text()
                assert result.returncode == 0 and 'COLD_CPU_GUARD_OK' in raw
                assert 'Verify successful.' in raw and 'Error:' not in raw
                report['passed'] = True
    except BaseException as error:
        report['error'] = repr(error)
    (args.out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
