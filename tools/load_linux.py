#!/usr/bin/env python3
"""Volatile Linux boot on Pro Dock C37 via J-Link; no FPGA/SD/flash writes.

The resident demo must acknowledge pause (or disk release). OpenSBI is
loaded at 124 MiB, Linux at 128 MiB. The ILM launcher verifies the entire
payload CRC before jumping. The dedicated Linux RAM excludes game assets.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import serial
from check_gpu_reloads import target_busdev, wait_console
from load_ilm import identify_console, quiesce_console, require
ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack', type=Path, default=ROOT / 'linux/build')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=180)
    parser.add_argument('--staged', action='store_true', help='Payload already verified in USB DDR staging at 0x08000000')
    parser.add_argument('--packed', action='store_true', help='Load zero-run packed payload by JTAG into 0x10000000')
    parser.add_argument('--jtag-speed', type=int, choices=(1000, 2000, 4000), default=1000,
                        help='JTAG download clock in kHz; payload CRC remains mandatory')
    args = parser.parse_args()
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
    print('Target Pro Dock', target_busdev(), flush=True)
    port, usb = wait_console(); require(usb['speed_mbps'] == 480, usb)
    (out / 'usb.json').write_text(json.dumps(usb, indent=2) + '\n')
    with serial.Serial(port, 115200, timeout=.2, exclusive=True) as uart:
        identity, pause = identify_console(uart)
        (out / 'before.txt').write_bytes(identity)
        (out / 'paused.txt').write_bytes(quiesce_console(uart, pause))
        commands = ['exec InhibitConnectRetries = 1', 'exec DisableFlashDL', 'exec DisableFlashBPs',
                    'exec SetAllowFlashCache = 0', 'connect', 'h', f'speed {args.jtag_speed}',
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
            'seconds': time.monotonic() - start, 'boot_only': True}, indent=2) + '\n')
        require(ok, 'Linux boot not confirmed; see console.log and jlink.log')
if __name__ == '__main__': main()
