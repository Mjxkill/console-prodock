#!/usr/bin/env python3
"""Stage pinned upstream U-Boot and the PRODOCK board port; do not program anything."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

VERSION = '2025.10'
SHA256 = 'b4f032848e56cc8f213ad59f9132c084dbbb632bc29176d024e58220e0efdf4a'
HERE = Path(__file__).resolve().parent

def prepare(archive, destination):
    if not archive.exists():
        archive.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['curl', '-fLsS', 'https://ftp.denx.de/pub/u-boot/u-boot-' + VERSION + '.tar.bz2',
                        '-o', str(archive)], check=True)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise ValueError('Expected the official U-Boot 2025.10 archive; SHA-256 mismatch')
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive) as source:
            source.extractall(destination.parent, filter='data')
        (destination.parent / ('u-boot-' + VERSION)).rename(destination)
    shutil.copytree(HERE/'overlay', destination, dirs_exist_ok=True)
    # One maintained pump for Linux and U-Boot. This is a build snapshot,
    # not a second implementation to keep synchronized by hand.
    for suffix in ('h', 'c'):
        name = 'prodock-spi-pio.' + suffix
        shutil.copy2(HERE.parent/'drivers'/name, destination/'drivers/spi'/name)
    for patch in sorted((HERE / 'patches').glob('*.patch')):
        stamp = destination / ('.prodock-' + patch.name + '.sha256')
        digest = hashlib.sha256(patch.read_bytes()).hexdigest()
        if stamp.exists():
            if stamp.read_text().strip() != digest: raise ValueError('Changed U-Boot patch: ' + str(patch))
        else:
            subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(patch)], cwd=destination, check=True)
            stamp.write_text(digest + '\n')
    additions = {
        'arch/riscv/Kconfig': '\nsource "board/prodock/console/Kconfig"\n',
        'drivers/spi/Kconfig': '\nconfig PRODOCK_SPI\n\tbool "PRODOCK SD SPI byte engine"\n\tdepends on DM_SPI\n',
        'drivers/spi/Makefile': '\nobj-$(CONFIG_PRODOCK_SPI) += prodock_spi.o\n',
        'arch/riscv/dts/Makefile': '\ndtb-$(CONFIG_TARGET_PRODOCK_CONSOLE) += prodock-console.dtb\n',
    }
    kconfig = destination/'arch/riscv/Kconfig'
    target = 'config TARGET_PRODOCK_CONSOLE\n\tbool "PRODOCK Tang Console AE350"\n'
    if target not in kconfig.read_text():
        kconfig.write_text(kconfig.read_text().replace(
            'config TARGET_ANDES_AE350', target+'\nconfig TARGET_ANDES_AE350'))
    for name, addition in additions.items():
        path = destination/name
        original = path.read_text()
        if addition not in original:
            path.write_text(original+addition)

    path = destination/'drivers/spi/Makefile'
    common = ('\nobj-$(CONFIG_PRODOCK_SPI) += prodock-spi-pio.o\n'
              'CFLAGS_prodock-spi-pio.o += -DPRODOCK_SPI_UBOOT\n')
    original = path.read_text()
    if common not in original:
        path.write_text(original+common)

    board = destination / 'board/prodock/console'
    (board / 'image.h').write_text((HERE.parent / 'boot/image.h').read_text().replace(
        '#include <stdint.h>', '#include <linux/types.h>'))
    shutil.copy2(HERE.parent / 'boot/image.c', board / 'image.c')

if __name__ == '__main__':
    prepare(Path(sys.argv[1]), Path(sys.argv[2]))
