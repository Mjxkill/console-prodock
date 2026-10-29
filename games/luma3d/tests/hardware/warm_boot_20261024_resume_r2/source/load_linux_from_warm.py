#!/usr/bin/env python3
"""Packed Linux boot ONLY from the verified Pro Dock warm parking program.

Derived from tools/load_linux.py SHA2cd0414c1f0dc92cebf81ce95396d5dcb7db1230c33e01597a3daab417beabc0.
The FPGA programmer is not used: bind CDC11252024 and J-Link506005083,
require the known parking identity and verify its ILM bytes before any DDR
write. The parent must pass its held diagnostic-lock descriptor. All payload
hash, size, launcher verification and on-board CRC checks remain mandatory.
No FPGA reset/configuration, SD or flash access.
"""
import argparse
import fcntl
import os
import sys
import hashlib
import json
from pathlib import Path
import subprocess
import time
import serial
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT / "tools"))
from check_gpu_reloads import wait_console
from load_ilm import identify_console, quiesce_console, require

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack', type=Path, default=ROOT / 'linux/build')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=180)
    parser.add_argument('--staged', action='store_true', help='Payload already verified in USB DDR staging at 0x08000000')
    parser.add_argument('--packed', action='store_true', help='Load zero-run packed payload by JTAG into 0x10000000')
    parser.add_argument('--jtag-speed', type=int, choices=(1000, 2000, 4000), default=1000,
                        help='JTAG download clock in kHz; payload CRC remains mandatory')
    parser.add_argument('--lock-fd', type=int, required=True)
    parser.add_argument('--warm-bin', type=Path, required=True)
    args = parser.parse_args()
    require(args.packed and not args.staged, 'This loader only supports packed warm boot')
    held = os.fstat(args.lock_fd); expected_lock = os.stat('/tmp/prodock-diagnostic.lock')
    require((held.st_dev,held.st_ino)==(expected_lock.st_dev,expected_lock.st_ino), 'Wrong diagnostic lock descriptor')
    fcntl.flock(args.lock_fd,fcntl.LOCK_EX | fcntl.LOCK_NB)
    warm = args.warm_bin.resolve()
    require(warm.stat().st_size==446 and hashlib.sha256(warm.read_bytes()).hexdigest()=='95b37af2dd390dc57333aba16318b95b11fcf7ccf9e8e36e2c726049e0c6c044', 'Wrong warm parking program')
    out = args.out.resolve(); out.mkdir(parents=True, exist_ok=False)
    pack = args.pack.resolve(); manifest = json.loads((pack / 'manifest.json').read_text())
    payload = pack / 'opensbi/platform/generic/firmware/fw_payload.bin'
    require(not (args.staged and args.packed), 'Choose USB staged OR packed JTAG')
    launch = pack / ('launch_usb.bin' if args.staged else 'launch_packed.bin' if args.packed else 'launch.bin')
    expected = manifest['files']['opensbi/platform/generic/firmware/fw_payload.bin']
    require(manifest['board'] == 'Tang Mega 138K Pro Dock' and manifest['abi'] == 1, 'Wrong board/ABI')
    require(manifest['load'] == manifest['entry'] == 0x07c00000 and manifest['kernel'] == 0x08000000, 'Wrong RAM layout')
    require(0 < payload.stat().st_size == expected['bytes'] <= 0x02000000, 'Bad payload size')
    require(hashlib.sha256(payload.read_bytes()).hexdigest() == expected['sha256'], 'Payload SHA mismatch')
    meta = manifest['launcher_usb' if args.staged else 'launcher_packed' if args.packed else 'launcher']
    download = payload
    address = 0x07c00000
    if args.packed:
        download = pack / 'payload.rle.bin'; address = 0x10000000
        compressed = manifest['files']['payload.rle.bin']
        require(meta['stage'] == address and 0 < download.stat().st_size == compressed['bytes'] <= 0x02000000,
                'Invalid compact staging')
        require(hashlib.sha256(download.read_bytes()).hexdigest() == compressed['sha256'], 'Packed SHA mismatch')
    if args.staged:
        require(meta['stage'] == 0x08000000 and expected['bytes'] <= 0x02000000, 'Bad USB staging layout')
    require(meta['load'] == 0xa0000000 and meta['entry'] == 0xa000000c and
            12 < launch.stat().st_size == meta['bytes'] <= 65536, 'Bad launcher')
    require(hashlib.sha256(launch.read_bytes()).hexdigest() == meta['sha256'], 'Launcher SHA mismatch')
    print('Target Pro Dock: CDC11252024 + J-Link506005083; no FPGA programmer needed', flush=True)
    port, usb = wait_console(); require(usb['speed_mbps'] == 480, usb)
    (out / 'usb.json').write_text(json.dumps(usb, indent=2) + '\n')
    with serial.Serial(port, 115200, timeout=.2, exclusive=True) as uart:
        identity, pause = identify_console(uart)
        require(b'MegaPro GPU LUMA3D WARM PARK R1' in identity and pause==b'c', 'Not the verified M-mode parking program')
        (out / 'before.txt').write_bytes(identity)
        (out / 'paused.txt').write_bytes(quiesce_console(uart, pause))
        commands = ['exec InhibitConnectRetries = 1', 'exec DisableFlashDL', 'exec DisableFlashBPs',
                    'exec SetAllowFlashCache = 0', 'connect', 'h', f'speed {args.jtag_speed}',
                    f'verifybin {warm} 0xa000f000',
                    *([] if args.staged else [f'loadfile {download} 0x{address:08x} noreset']),
                    f'loadfile {launch} 0xa0000000 noreset', f'verifybin {launch} 0xa0000000',
                    'SetPC 0xa000000c', 'g', 'q']
        script = out / 'load.jlink'; script.write_text('\n'.join(commands) + '\n')
        start = time.monotonic(); print('Linux payload download into DDR...', flush=True)
        with (out / 'jlink.log').open('w') as log:
            r = subprocess.run(['JLinkExe', '-SelectEmuBySN', '506005083', '-Device', 'A25',
                '-If', 'JTAG', '-Speed', '100', '-JTAGConf', '-1,-1', '-NoGui', '1', '-ExitOnError', '1',
                '-CommanderScript', str(script)], stdout=log, stderr=subprocess.STDOUT, timeout=1200)
        content = (out / 'jlink.log').read_text()
        require(r.returncode == 0 and 'Verify successful.' in content and 'Error:' not in content, content[-3000:])
        print('Download done:', round(time.monotonic() - start, 1), 's; waiting for Linux', flush=True)
        deadline = time.monotonic() + args.seconds; received = bytearray()
        with (out / 'console.log').open('wb', buffering=0) as log:
            while time.monotonic() < deadline:
                chunk = uart.read(4096)
                if chunk:
                    received.extend(chunk); log.write(chunk); print(chunk.decode(errors='replace'), end='', flush=True)
                if b'PRODOCK_LINUX_READY - SD non montee; prodockctl info\n' in received.replace(b'\r', b''): break
                if b'LINUX FAIL' in received or b'Kernel panic' in received: break
        ok = (b'PRODOCK_LINUX_READY - SD non montee; prodockctl info\n' in received.replace(b'\r', b'')
              and b'Linux version' in received and b'CRC OK' in received)
        (out / 'result.json').write_text(json.dumps({'passed': ok, 'usb': usb, 'manifest': manifest,
            'seconds': time.monotonic() - start, 'boot_only': True,
            'binding': 'CDC11252024 and verified ILM parking through J-Link506005083',
            'fpga_programmer_used': False}, indent=2) + '\n')
        require(ok, 'Linux boot not confirmed; see console.log and jlink.log')
if __name__ == '__main__': main()
