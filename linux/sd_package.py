#!/usr/bin/env python3
"""Prépare les fichiers de démarrage ; n'accède à aucun disque physique."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import zlib
HERE = Path(__file__).resolve().parent
BUILD = HERE / 'build'
LAYOUT = {1: (0x06000000, 0x06000000, 0x800000),
          2: (0x07c00000, 0x07c00000, 0x2000000),
          3: (0xa0000000, 0xa000000c, 0x10000),
          4: (0xa0000000, 0xa000000c, 0x10000),
          5: (0x04000000, 0, 0x800000), 6: (0x05000000, 0, 0x800000)}


def wrap(data, kind):
    base, entry, maximum = LAYOUT[kind]
    if not data or len(data) > maximum or (entry and entry - base >= len(data)):
        raise ValueError('Image vide, trop grande ou entrée hors image')
    header = b'PDCKBOOT' + struct.pack('<7I', 1, kind, base, entry, len(data), zlib.crc32(data), 0x1ff)
    return header + struct.pack('<I', zlib.crc32(header)) + data


def main():
    out = BUILD / 'sd/PRODOCK'; out.mkdir(parents=True, exist_ok=True)
    items = [('UBOOT.BIN', 1, BUILD / 'uboot/out/u-boot.bin'),
             ('LINUX.BIN', 2, BUILD / 'opensbi/platform/generic/firmware/fw_payload.bin')]
    for game, code in [('luma', 3), ('orbital', 4)]:
        pack = HERE.parent / 'assets' / game / 'packed'
        meta = json.loads((pack / 'firmware.json').read_text())
        for suffix, kind, key, dest in [('_fw.bin', code, 'sha256', '.BIN'),
                                      ('.bin', code + 2, 'assets_sha256', '.DAT')]:
            path = pack / (game + suffix)
            if hashlib.sha256(path.read_bytes()).hexdigest() != meta[key]:
                raise ValueError('Ressource différente du manifeste : ' + str(path))
            items.append((game.upper() + dest, kind, path))
    manifest = {'board': 'Tang Mega 138K Pro Dock C37', 'format': 'PDCKBOOT v1', 'files': {}}
    for name, kind, path in items:
        data = wrap(path.read_bytes(), kind)
        (out / name).write_bytes(data)
        manifest['files'][name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                                   'kind': kind, 'load': LAYOUT[kind][0], 'entry': LAYOUT[kind][1]}
    (out.parent / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    # Separate volatile launcher for qualifying U-Boot before SD installation.
    raw = (BUILD / 'uboot/out/u-boot.bin').read_bytes()
    (BUILD / 'uboot_payload.h').write_text(
        f'#define UBOOT_BYTES {len(raw)}U\n#define UBOOT_CRC 0x{zlib.crc32(raw):08x}U\n')
    subprocess.run(['make', '-B', '-s', '-C', str(HERE.parent / 'fw_console'),
        'MAIN=../linux/boot/uboot_ram.c', 'BUILD=build/linux_uboot_ram',
        'LD=' + str(HERE.parent / 'fw_console/orbital.ld'),
        'EXTRA_SRCS=../linux/boot/image.c',
        f'CFLAGS_EXTRA=-I{HERE / "boot"} -I{BUILD}'], check=True)
    launcher = (HERE.parent / 'fw_console/build/linux_uboot_ram/console_test.bin').read_bytes()
    if not 12 < len(launcher) <= 65536:raise ValueError('U-Boot RAM launcher exceeds ILM')
    (out.parent / 'uboot_ram.bin').write_bytes(launcher)
    (out.parent / 'uboot_ram.json').write_text(json.dumps({
        'image_sha256':hashlib.sha256((out/'UBOOT.BIN').read_bytes()).hexdigest(),
        'launcher_sha256':hashlib.sha256(launcher).hexdigest()},indent=2)+'\n')
    print('Paquet SD prêt dans', out, '(aucune écriture physique)')


if __name__ == '__main__': main()
