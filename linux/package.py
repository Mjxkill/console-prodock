#!/usr/bin/env python3
"""Manifest for the volatile Pro Dock Linux payload. No disk/flash writes."""
import os
import hashlib
import json
import subprocess
import zlib
import struct
import argparse
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
BOARD = os.environ.get('CONSOLE_BOARD', 'prodock')
if BOARD not in ('prodock', 'neo'): raise ValueError('Unknown CONSOLE_BOARD')
BUILD = ROOT / ('build-neo' if BOARD == 'neo' else 'build')
SUFFIX = '_neo' if BOARD == 'neo' else ''

def pack_zero_runs(data):
    blocks = []
    for off in range(0, len(data), 4096):
        block = data[off:off + 4096]
        literal = any(block)
        if blocks and blocks[-1][0] == literal:
            blocks[-1][1].extend(block)
        else:
            blocks.append((literal, bytearray(block)))
    return b''.join(struct.pack('<I', len(block) | (0x80000000 if literal else 0)) +
                    (bytes(block) if literal else b'') for literal, block in blocks)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', action='store_true')
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT.parent/'tools'))
    from board_contract import before_build, record_build
    contract = before_build(BOARD, candidate=args.candidate or BOARD == 'neo')
    record_build(BUILD, contract)
    paths = ['opensbi/platform/generic/firmware/fw_payload.bin',
             'kernel/arch/riscv/boot/Image', 'prodock-linux.dtb', 'rootfs/bin/prodockctl', 'rootfs/bin/prodock-terminal',
             'rootfs/bin/prodock-game', 'rootfs/bin/prodock-text-test',
             'rootfs/bin/nebula', 'rootfs/usr/share/nebula/nebula.bin']
    result = {'board': 'Tang Mega Neo Console 138K' if BOARD == 'neo' else 'Tang Mega 138K Pro Dock', 'profile': BOARD, 'abi': 1,
              'load': 0x07c00000, 'entry': 0x07c00000, 'kernel': 0x08000000,
              'gpu_memory': [0x00800000, 0x05800000], 'files': {}}
    for name in paths:
        data = (BUILD / name).read_bytes()
        result['files'][name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    if result['files'][paths[0]]['bytes'] > 0x02000000:
        raise ValueError('Linux payload exceeds the 32 MiB boot window')
    payload = (BUILD / paths[0]).read_bytes()
    packed = pack_zero_runs(payload)
    (BUILD / 'payload.rle.bin').write_bytes(packed)
    result['files']['payload.rle.bin'] = {'bytes': len(packed), 'sha256': hashlib.sha256(packed).hexdigest()}
    (BUILD / 'payload.h').write_text(
        f'#define PAYLOAD_LOAD 0x07c00000U\n#define PAYLOAD_BYTES {len(payload)}U\n'
        f'#define PAYLOAD_CRC 0x{zlib.crc32(payload):08x}U\n'
        f'#define PAYLOAD_RLE_BYTES {len(packed)}U\n#define PAYLOAD_RLE_CRC 0x{zlib.crc32(packed):08x}U\n')
    subprocess.run(['make', '-B', '-s', '-C', str(ROOT.parent / 'fw_console'),
                    'MAIN=../linux/boot/launch.c', 'BUILD=build/linux_launch' + SUFFIX,
                    'LD=' + str(ROOT.parent / 'games/orbital/src/orbital.ld'),
                    'CFLAGS_EXTRA=-I' + str(BUILD)], check=True)
    launch = (ROOT.parent / ('fw_console/build/linux_launch' + SUFFIX + '/console_test.bin')).read_bytes()
    if len(launch) > 65536:
        raise ValueError('Linux launcher exceeds ILM')
    (BUILD / 'launch.bin').write_bytes(launch)
    result['launcher'] = {'entry': 0xa000000c, 'load': 0xa0000000,
                          'bytes': len(launch), 'sha256': hashlib.sha256(launch).hexdigest()}
    subprocess.run(['make', '-B', '-s', '-C', str(ROOT.parent / 'fw_console'),
                    'MAIN=../linux/boot/launch.c', 'BUILD=build/linux_launch_usb' + SUFFIX,
                    'LD=' + str(ROOT.parent / 'games/orbital/src/orbital.ld'),
                    'CFLAGS_EXTRA=-DPAYLOAD_USB_STAGE -I' + str(BUILD)], check=True)
    launch = (ROOT.parent / ('fw_console/build/linux_launch_usb' + SUFFIX + '/console_test.bin')).read_bytes()
    if not 12 < len(launch) <= 65536:
        raise ValueError('USB launcher exceeds ILM')
    (BUILD / 'launch_usb.bin').write_bytes(launch)
    result['launcher_usb'] = {'entry': 0xa000000c, 'load': 0xa0000000,
        'stage': 0x08000000, 'bytes': len(launch), 'sha256': hashlib.sha256(launch).hexdigest()}
    subprocess.run(['make', '-B', '-s', '-C', str(ROOT.parent / 'fw_console'),
                    'MAIN=../linux/boot/launch.c', 'BUILD=build/linux_launch_packed' + SUFFIX,
                    'LD=' + str(ROOT.parent / 'games/orbital/src/orbital.ld'),
                    'CFLAGS_EXTRA=-DPAYLOAD_RLE_STAGE -I' + str(BUILD)], check=True)
    launch = (ROOT.parent / ('fw_console/build/linux_launch_packed' + SUFFIX + '/console_test.bin')).read_bytes()
    if not 12 < len(launch) <= 65536: raise ValueError('Packed launcher exceeds ILM')
    (BUILD / 'launch_packed.bin').write_bytes(launch)
    result['launcher_packed'] = {'entry': 0xa000000c, 'load': 0xa0000000,
        'stage': 0x10000000, 'bytes': len(launch), 'sha256': hashlib.sha256(launch).hexdigest()}
    (BUILD / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Pro Dock volatile Linux package ready')
if __name__ == '__main__': main()
