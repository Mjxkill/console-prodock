#!/usr/bin/env python3
"""Read-only build monitor; compare ROM only after the owned R4 tool has exited.

Does not start/stop Gowin or access a device. New report paths are exclusive.
The fixed known checker and firmware hashes are required before comparison.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
STAGE = ROOT / 'tang/impl/prodock_sd_boot_20261029_r4'
CHECKER = Path(__file__).with_name('rom_check.py')
CHECK_SHA = 'cb39392bfd6bbabd58139535f25d8b651d4709333c7d49a6d230d25a940283fb'
BIN_SHA = 'd8ab75277c4cb4eb2a4123fbdf269d96fa8a5cd44cb84eaa11c8e3fdf66d8ae8'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    start = time.monotonic()
    result_path = STAGE / 'build_result.json'
    previous = None
    while time.monotonic() - start < 7200:
        if result_path.exists():
            result = json.loads(result_path.read_text())
            if result.get('tool_returncode') != 0 or result.get('tool_error') is not False:
                raise RuntimeError('R4 did not finish successfully: ' + repr(result))
            break
        log = STAGE / 'build.log'
        lines = log.read_text(errors='replace').splitlines()
        last = lines[-1] if lines else '(empty log)'
        if last != previous:
            print(json.dumps({'stage': last, 'elapsed_seconds': round(time.monotonic()-start, 1)}), flush=True)
            previous = last
        time.sleep(30)
    else:
        raise TimeoutError('Build monitor bounded to two hours; Gowin left untouched')
    vo = STAGE / ('impl/pnr/console_' + STAGE.name + '.vo')
    binary = STAGE / 'source/boot_firmware/sd_boot.bin'
    assert sha(CHECKER) == CHECK_SHA, 'Checker changed; root review required'
    assert sha(binary) == BIN_SHA, 'Firmware changed; root review required'
    stamp = (vo.stat().st_size, vo.stat().st_mtime_ns)
    time.sleep(2)
    assert stamp == (vo.stat().st_size, vo.stat().st_mtime_ns), 'VO is still changing'
    out = STAGE / 'rom_verification'
    if out.exists():
        print(json.dumps({'existing_report_requires_review': str(out)}), flush=True)
        return 2
    run = subprocess.run([sys.executable, '-B', str(CHECKER), '--vo', str(vo),
                          '--binary', str(binary), '--out', str(out)], timeout=120)
    print(json.dumps({'rom_check_returncode': run.returncode, 'report': str(out / 'result.json'),
                      'hardware_validated': False}), flush=True)
    return run.returncode


if __name__ == '__main__':
    raise SystemExit(main())
