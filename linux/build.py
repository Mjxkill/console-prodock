#!/usr/bin/env python3
"""Pinned Linux/OpenSBI/rootfs build. Never formats, flashes or programs a board."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import tarfile
import sys

HERE = Path(__file__).resolve().parent
BOARD = os.environ.get('CONSOLE_BOARD', 'prodock')
if BOARD not in ('prodock', 'neo'): raise ValueError('Unknown CONSOLE_BOARD: ' + BOARD)
BUILD = HERE / ('build-neo' if BOARD == 'neo' else 'build')
TOOLS = HERE / 'build'
SOURCES = json.loads((HERE / 'sources.json').read_text())
DOWNLOADS = Path(os.environ.get('CONSOLE_DOWNLOADS', HERE / 'downloads')).expanduser().resolve()
EPOCH = '1791417600'
ENV = dict(os.environ, SOURCE_DATE_EPOCH=EPOCH, KBUILD_BUILD_TIMESTAMP='2026-10-08 00:00:00 UTC',
           KBUILD_BUILD_USER='prodock', KBUILD_BUILD_HOST='builder', KBUILD_BUILD_VERSION='1')
TC = TOOLS / SOURCES['toolchain']['directory'] / 'bin/riscv32-buildroot-linux-musl-'
JOBS = os.environ.get('JOBS', '4')
USER_TC = BUILD / 'userbin/riscv32-prodock-linux-'


def run(args, **kwargs):
    print('+', ' '.join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), check=True, env=ENV, **kwargs)


def src(name):
    return BUILD / 'src' / SOURCES[name]['directory']


def prepare():
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    for name, item in SOURCES.items():
        archive = DOWNLOADS / item['archive']
        if not archive.exists():
            run(['curl', '-fL', item['url'], '-o', archive])
        if hashlib.sha256(archive.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError(f'{name}: archive SHA-256 mismatch')
        parent = TOOLS if name == 'toolchain' else BUILD / 'src'
        parent.mkdir(parents=True, exist_ok=True)
        if not (parent / item['directory']).exists():
            with tarfile.open(archive) as tar:
                tar.extractall(parent, filter='data')
    sdk = TC.parent.parent
    if (sdk / 'relocate-sdk.sh').exists() and not (sdk / '.prodock-relocated').exists():
        run([sdk / 'relocate-sdk.sh'], cwd=sdk)
        (sdk / '.prodock-relocated').touch()
    for name in ['linux', 'opensbi']:
        overlay = HERE / 'overlay' / name
        if overlay.exists():
            shutil.copytree(overlay, src(name), dirs_exist_ok=True)
    for name in ['linux', 'opensbi', 'musl']:
        for patch in sorted((HERE / 'patches' / name).glob('*.patch')):
            # A changed patch must fail loudly, never silently reuse a stale tree.
            digest = hashlib.sha256(patch.read_bytes()).hexdigest()
            stamp = src(name) / ('.prodock-' + patch.name + '.sha256')
            if stamp.exists():
                if stamp.read_text().strip() != digest:
                    raise ValueError('Patch changed; extract a clean source tree: ' + str(patch))
                continue
            run(['patch', '--batch', '--fuzz=0', '-p1', '-i', patch], cwd=src(name))
            stamp.write_text(digest + '\n')
    if (HERE / 'drivers').exists():
        shutil.copytree(HERE / 'drivers', src('linux') / 'drivers/prodock', dirs_exist_ok=True)
        append_once(src('linux') / 'drivers/Makefile', '\nobj-$(CONFIG_PRODOCK) += prodock/\n')
        append_once(src('linux') / 'drivers/Kconfig', '\nsource "drivers/prodock/Kconfig"\n')
    if (HERE / 'overlay/opensbi/platform/generic/prodock.c').exists():
        shutil.copy2(HERE / 'configs/opensbi.config', src('opensbi') / 'platform/generic/configs/prodock_defconfig')
        append_once(src('opensbi') / 'platform/generic/Kconfig',
                    '\nconfig PLATFORM_PRODOCK\n\tbool "PRODOCK Tang Console"\n\tdefault n\n')
        append_once(src('opensbi') / 'platform/generic/objects.mk',
                    '\ncarray-platform_override_modules-$(CONFIG_PLATFORM_PRODOCK) += prodock\n'
                    'platform-objs-$(CONFIG_PLATFORM_PRODOCK) += prodock.o\n')


def append_once(path, text):
    original = path.read_text()
    if text not in original:
        path.write_text(original + text)


def rootfs():
    musl()
    out = BUILD / 'busybox'
    out.mkdir(exist_ok=True)
    args = ['make', '-C', src('busybox'), f'O={out}', 'ARCH=riscv', f'CROSS_COMPILE={USER_TC}']
    run(args + ['allnoconfig'])
    fragment = (HERE / 'configs/busybox.config').read_text()
    keys = {line.split('=')[0] for line in fragment.splitlines() if '=' in line}
    lines = [line for line in (out / '.config').read_text().splitlines()
             if line.split('=')[0] not in keys and
             not any(line == f'# {key} is not set' for key in keys)]
    (out / '.config').write_text('\n'.join(lines) + '\n' + fragment)
    run(args + ['oldconfig'], input=b'\n' * 2000)
    run(args + [f'-j{JOBS}'])
    root = BUILD / 'rootfs'
    run(args + [f'CONFIG_PREFIX={root}', 'install'])
    shutil.copytree(HERE / 'rootfs', root, dirs_exist_ok=True)
    (root / 'init').chmod(0o755)
    for path in ['dev', 'proc', 'sys', 'tmp', 'run', 'mnt', 'mnt/sd']:
        (root / path).mkdir(parents=True, exist_ok=True)
    if (HERE / 'userspace/prodockctl.c').exists():
        run([str(USER_TC) + 'gcc', '-O2', '-static', '-Wall', '-Wextra', '-Werror',
             '-I', HERE / 'drivers', HERE / 'userspace/prodockctl.c', '-lm', '-o', root / 'bin/prodockctl'])
    run([str(USER_TC) + 'gcc', '-O2', '-static', '-pthread', '-Wall', '-Wextra', '-Werror',
         HERE / 'userspace/prodock-runtime.c', '-o', root / 'bin/prodock-runtime'])
    run(['python3', HERE.parent / 'tools/build_nebula_assets.py'])
    (root / 'usr/share/nebula').mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE.parent / 'games/nebula/assets/packed/nebula.bin', root / 'usr/share/nebula/nebula.bin')
    for name in ['prodock-terminal', 'prodock-game', 'prodock-text-test', 'nebula']:
        application = (HERE.parent / 'games/nebula/src/nebula.c' if name == 'nebula'
                       else HERE / f'userspace/{name}.c')
        run([str(USER_TC) + 'gcc', '-O2', '-static', '-Wall', '-Wextra', '-Werror',
             '-I', HERE / 'drivers', '-I', HERE / 'userspace', application, '-lm', '-o', root / f'bin/{name}'])
    # gen_init_cpio describes device nodes without requiring mknod/root.
    listing = ['dir /dev 755 0 0', 'nod /dev/console 600 0 0 c 5 1',
               'nod /dev/null 666 0 0 c 1 3']
    for path in sorted(root.rglob('*')):
        rel = '/' + str(path.relative_to(root))
        if rel == '/dev':
            continue
        if path.is_symlink():
            listing.append(f'slink {rel} {os.readlink(path)} 777 0 0')
        elif path.is_dir():
            listing.append(f'dir {rel} 755 0 0')
        else:
            listing.append(f'file {rel} {path} {path.stat().st_mode & 0o777:o} 0 0')
    (BUILD / 'initramfs.list').write_text('\n'.join(listing) + '\n')


def musl():
    out, prefix = BUILD / 'musl', BUILD / 'musl-install'
    out.mkdir(exist_ok=True)
    run([src('musl') / 'configure', f'--prefix={prefix}', f'--syslibdir={prefix}/lib',
         '--target=riscv32', '--enable-wrapper=gcc', f'CC={TC}gcc', f'CROSS_COMPILE={TC}',
         'CFLAGS=-O2 -march=rv32imfdc_zicsr_zifencei -mabi=ilp32d'], cwd=out)
    run(['make', f'-j{JOBS}'], cwd=out)
    run(['make', 'install'], cwd=out)
    headers = TC.parent.parent / 'riscv32-buildroot-linux-musl/sysroot/usr/include'
    for name in ['linux', 'asm', 'asm-generic']:
        shutil.copytree(headers / name, prefix / 'include' / name, dirs_exist_ok=True)
    USER_TC.parent.mkdir(exist_ok=True)
    for program in TC.parent.glob(TC.name + '*'):
        dest = USER_TC.parent / program.name.replace(TC.name, USER_TC.name, 1)
        if program.name == TC.name + 'gcc':
            dest.write_text('#!/bin/sh\nexec ' + shlex.quote(str(program)) +
                ' -march=rv32imfdc_zicsr_zifencei -mabi=ilp32d -specs=' +
                shlex.quote(str(prefix / 'lib/musl-gcc.specs')) + ' "$@"\n')
            dest.chmod(0o755)
        elif not dest.exists():
            dest.symlink_to(program)


def kernel():
    out = BUILD / 'kernel'
    out.mkdir(exist_ok=True)
    fragment = (HERE / 'configs/linux.config').read_text().replace('@INITRAMFS@', str(BUILD / 'initramfs.list'))
    (BUILD / 'linux.config').write_text(fragment)
    args = ['make', '-C', src('linux'), f'O={out}', 'ARCH=riscv', f'CROSS_COMPILE={TC}']
    run(args + ['allnoconfig', f'KCONFIG_ALLCONFIG={BUILD / "linux.config"}'])
    run(args + [f'-j{JOBS}', 'Image'])


def opensbi():
    dtb = BUILD / 'prodock-linux.dtb'
    run(['dtc', '-I', 'dts', '-O', 'dtb', '-p', '4096', '-o', dtb, HERE / ('neo-linux.dts' if BOARD == 'neo' else 'prodock-linux.dts')])
    run(['make', '-C', src('opensbi'), f'O={BUILD / "opensbi"}', 'PLATFORM=generic',
         'PLATFORM_RISCV_XLEN=32', 'PLATFORM_RISCV_ISA=rv32imafdc_zicsr_zifencei',
         'PLATFORM_RISCV_ABI=ilp32d', f'CROSS_COMPILE={TC}',
         'PLATFORM_DEFCONFIG=prodock_defconfig', 'FW_TEXT_START=0x07c00000',
         'FW_PAYLOAD_OFFSET=0x00400000', 'FW_PAYLOAD_FDT_ADDR=0x07000000',
         f'FW_FDT_PATH={dtb}', 'FW_FDT_PADDING=4096',
         f'FW_PAYLOAD_PATH={BUILD / "kernel/arch/riscv/boot/Image"}', f'-j{JOBS}'])


def qemu_firmware():
    # Ubuntu ships only the RV64 BIOS. Build an RV32 dynamic firmware separately;
    # the board firmware must retain its low DDR address and embedded board DTB.
    run(['make', '-C', src('opensbi'), f'O={BUILD / "opensbi-qemu-virt"}', 'PLATFORM=generic',
         'PLATFORM_RISCV_XLEN=32', 'PLATFORM_RISCV_ISA=rv32imafdc_zicsr_zifencei',
         'PLATFORM_RISCV_ABI=ilp32d', f'CROSS_COMPILE={TC}',
         'PLATFORM_DEFCONFIG=defconfig', 'FW_TEXT_START=0x80000000', f'-j{JOBS}'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['all', 'prepare', 'rootfs', 'kernel', 'opensbi', 'package', 'test'])
    parser.add_argument('--candidate', action='store_true',
                        help='Explicit Pro Dock candidate; local checks do not replace hardware validation')
    args = parser.parse_args()
    stage = args.stage
    sys.path.insert(0, str(HERE.parent/'tools'))
    from board_contract import before_build, record_build
    contract = before_build(BOARD, candidate=args.candidate or BOARD == 'neo')
    BUILD.mkdir(parents=True, exist_ok=True)
    record_build(BUILD, contract)
    if stage in ['all', 'prepare', 'rootfs', 'kernel', 'opensbi', 'test']:
        prepare()
    for name, func in [('rootfs', rootfs), ('kernel', kernel), ('opensbi', opensbi)]:
        if stage in ['all', name]:
            func()
    if stage in ['all', 'package']:
        run(['python3', HERE / 'package.py', *(['--candidate'] if args.candidate else [])])
    if stage == 'test':
        qemu_firmware()
        run(['python3', HERE / 'tests/test_package.py'])
        run(['python3', HERE / 'tests/test_boot.py'])


if __name__ == '__main__':
    main()
