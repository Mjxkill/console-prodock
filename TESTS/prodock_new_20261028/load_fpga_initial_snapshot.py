#!/usr/bin/env python3
"""Load exact G22r0 into the explicitly selected second Pro Dock SRAM.

FPGA programming and CPU/Linux loading are separate operations. Record USB
topology before/after to bind the next console session, since its iSerial is
identical on boards carrying the same bitstream. No SD or flash operation.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import time

ROOT = Path('/home/michael/console-validation-20261001')
OUT = ROOT / 'TESTS/prodock_2025071717_20261028/fpga_01'
BIT = ROOT / 'tang/impl/gpu_geometry_g22r0/impl/pnr/console_gpu_geometry_g22r0.fs'
SHA = 'fbbea9c357d0c4d5b33c3c4a7e54f9ed0ff8e31cc3fad1ac9dc1771f8e8cba5f'
SERIAL = '2025071717'


def devices():
    result = []
    for p in Path('/sys/bus/usb/devices').iterdir():
        if not (p / 'idVendor').exists():
            continue
        record = {k: (p / k).read_text().strip() for k in
                  ('idVendor', 'idProduct', 'serial', 'product', 'busnum', 'devnum', 'speed')
                  if (p / k).exists()}
        if record['idVendor'] in ('0403', '359f', '1366'):
            result.append(dict(record, path=str(p)))
    return sorted(result, key=lambda r: r['path'])


def main():
    assert __debug__ and socket.gethostname().split('.')[0] == 'michael-AX15'
    assert hashlib.sha256(BIT.read_bytes()).hexdigest() == SHA
    OUT.mkdir(parents=True, exist_ok=False)
    report = dict(target_serial=SERIAL, bitstream_sha256=SHA,
                  configuration_completed=False, linux_loaded=False,
                  flash_writes=0, sd_writes=0, started_unix=time.time())
    try:
        fd = os.open('/tmp/prodock-diagnostic.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            active = subprocess.run(['ps', '-C', 'openFPGALoader', '-C', 'JLinkExe', '-C', 'openocd',
                                     '-o', 'pid=,comm='], capture_output=True, text=True, timeout=5)
            assert not active.stdout.strip(), 'Another hardware client is running'
            report['before'] = devices()
            targets = [d for d in report['before'] if
                       (d['idVendor'], d['idProduct'], d.get('serial')) == ('0403', '6010', SERIAL)]
            assert len(targets) == 1
            target = targets[0]
            node = Path('/dev/bus/usb') / f"{int(target['busnum']):03}" / f"{int(target['devnum']):03}"
            assert os.access(node, os.R_OK | os.W_OK), 'Programmer permissions missing'
            command = [str(ROOT / 'bin/openFPGALoader'), '--usb-serial-num', SERIAL,
                       '-b', 'tangmega138k', '-m', '--verbose', str(BIT)]
            report['command'] = command
            (OUT / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
            with (OUT / 'program.log').open('x') as log:
                result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=180)
            report['returncode'] = result.returncode
            assert result.returncode == 0, 'FPGA programming failed; retain log'
            report['configuration_completed'] = True
            # A bounded observation, not an assumption that any CDC belongs to us.
            observations = []
            for _ in range(10):
                time.sleep(1)
                observations.append(devices())
            report['usb_observations'] = observations
    except BaseException as error:
        report['error'] = repr(error)
    finally:
        report['finished_unix'] = time.time()
        (OUT / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report.get(k) for k in
                      ('target_serial', 'configuration_completed', 'linux_loaded', 'error')}))


if __name__ == '__main__':
    main()
