#!/usr/bin/env python3
"""Isolated Pro Dock R17 + G3D1 kernel/package. Never accesses hardware.

prepare snapshots inputs without compiling; build requires --candidate and the
complete, current dual-board regression gate. Neither stage writes linux/build.
The existing patched Linux tree is copied (no hard links), its Pro Dock overlay
is restored from the retained R17 commit, and only the G3D1 blocks are added.
"""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import zlib

ROOT = Path(__file__).resolve().parents[3]
REFERENCE = 'b2b1ba84904ca428b9971de23c9957c81b15dc72'
GOLDEN = ROOT / 'linux/build/golden_nebula_r17'
BASE = ROOT / 'linux/build/src/linux-6.12.112'
TC = ROOT / 'linux/build/riscv32-ilp32d--musl--stable-2025.08-1/bin/riscv32-buildroot-linux-musl-'
ENV = dict(os.environ, SOURCE_DATE_EPOCH='1791417600',
           KBUILD_BUILD_TIMESTAMP='2026-10-08 00:00:00 UTC',
           KBUILD_BUILD_USER='prodock', KBUILD_BUILD_HOST='builder', KBUILD_BUILD_VERSION='1')
LOCALVERSION = '-prodock-luma3d-g3d1-r1'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def metadata(path):
    data = path.read_bytes()
    return {'bytes': len(data), 'sha256': sha(data)}


def git_bytes(name):
    return subprocess.check_output(['git', 'show', REFERENCE + ':' + name], cwd=ROOT)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def section(text, begin, end):
    assert text.count(begin) == 1, begin
    first = text.index(begin)
    assert text[first:].count(end) == 1, end
    return text[first:text.index(end, first)]


def replace_once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new, 1)


def geometry_overlay():
    names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', REFERENCE,
                                     'linux/drivers/'], cwd=ROOT).decode().splitlines()
    original = {Path(n).name: git_bytes(n).decode() for n in names}
    result = dict(original)
    current = {n: (ROOT / 'linux/drivers' / n).read_text() for n in (
        'prodock-uapi.h', 'prodock-validate.h', 'prodock-gpu.c', 'prodock-kunit.c')}
    n = 'prodock-uapi.h'
    block = section(current[n], '/* Optional G3D1 frontend;', '/* Independent from exclusive')
    result[n] = replace_once(result[n], '/* Independent from exclusive', block + '/* Independent from exclusive')
    n = 'prodock-validate.h'
    block = section(current[n], '/* Exactly the G3D1 fixed-point', 'static inline int prodock_command(')
    result[n] = replace_once(result[n], 'static inline int prodock_command(', block + 'static inline int prodock_command(')
    result[n] = replace_once(result[n], '    if (!op || op > 30) return -EINVAL;',
        '    if (op >= PRODOCK_GEOM_MATRIX) return prodock_geometry_command(c);\n    if (!op) return -EINVAL;')
    n = 'prodock-gpu.c'
    begin, end = 'static int submit(', 'static int present_raw('
    result[n] = replace_once(result[n], section(result[n], begin, end), section(current[n], begin, end))
    block = section(current[n], '    if (cmd == PRODOCK_GEOMETRY_INFO)', '    switch (cmd) {')
    result[n] = replace_once(result[n], '    switch (cmd) {', block + '    switch (cmd) {')
    n = 'prodock-kunit.c'
    # This file currently differs from R17 only by the new G3D1 tests.
    result[n] = current[n]
    return original, result, {n: sha(t.encode()) for n, t in current.items()}


def golden_manifest():
    historical = json.loads((ROOT / 'TESTS/nebula_20261012/r17_manifest.json').read_text())
    assert json.loads((GOLDEN / 'manifest.json').read_text()) == historical
    for name, expected in historical['files'].items():
        assert metadata(GOLDEN / name) == expected, name
    for key, name in [('launcher', 'launch.bin'), ('launcher_usb', 'launch_usb.bin'),
                      ('launcher_packed', 'launch_packed.bin')]:
        actual = metadata(GOLDEN / name)
        assert all(actual[k] == historical[key][k] for k in actual), name
    return historical


def find_initramfs(image):
    found = []
    offset = 0
    while True:
        offset = image.find(b'\x1f\x8b\x08', offset)
        if offset < 0:
            break
        try:
            stream = zlib.decompressobj(31)
            raw = stream.decompress(image[offset:])
            count = len(image) - offset - len(stream.unused_data)
            if stream.eof and raw.startswith(b'070701'):
                found.append((offset, image[offset:offset + count], raw))
        except zlib.error:
            pass
        offset += 1
    assert len(found) == 1, 'Expected one R17 gzip/newc initramfs'
    return found[0]


def tree_hashes(path):
    result = {}
    for p in sorted(path.rglob('*')):
        if p.is_symlink():
            result[str(p.relative_to(path))] = {'symlink': os.readlink(p)}
        elif p.is_file():
            result[str(p.relative_to(path))] = metadata(p)
    return result


def run(out, name, command, **kwargs):
    print('+', ' '.join(map(str, command)), flush=True)
    with (out / (name + '.log')).open('w') as log:
        completed = subprocess.run(list(map(str, command)), stdout=log,
                                   stderr=subprocess.STDOUT, env=ENV, **kwargs)
    if completed.returncode:
        print((out / (name + '.log')).read_text()[-8000:])
        completed.check_returncode()


def prepare(out):
    from board_contract import reference_check
    reference_check(ROOT)
    golden = golden_manifest()
    original, drivers, current = geometry_overlay()
    assert not out.exists(), 'Use a new candidate directory'
    assert not (BASE / '.config').exists(), 'Expected clean out-of-tree kernel source'
    assert 'SUBLEVEL = 112' in (BASE / 'Makefile').read_text()
    patch = '0001-riscv-support-gowin-ae350.patch'
    expected_patch = sha(git_bytes('linux/patches/linux/' + patch))
    assert (BASE / ('.prodock-' + patch + '.sha256')).read_text().strip() == expected_patch
    out.mkdir(parents=True)
    provenance = out / 'provenance'
    provenance.mkdir()
    shutil.copy2(__file__, provenance / Path(__file__).name)
    write_json(provenance / 'golden_manifest.json', golden)
    write_json(provenance / 'live_g3d1_sources.json', current)
    source = out / 'source'
    # Reflinks if supported, ordinary copies otherwise; never hard links.
    run(out, 'source_copy', ['cp', '-a', '--reflink=auto', BASE, source])
    overlay = source / 'drivers/prodock'
    shutil.rmtree(overlay)  # Only inside the newly created private source copy.
    overlay.mkdir()
    for name, content in drivers.items():
        (overlay / name).write_text(content)
    delta = ''.join(''.join(difflib.unified_diff(original[n].splitlines(True), drivers[n].splitlines(True),
                    fromfile='R17/linux/drivers/' + n, tofile='candidate/linux/drivers/' + n))
                    for n in sorted(drivers) if drivers[n] != original[n])
    (provenance / 'g3d1-only.patch').write_text(delta)
    (provenance / patch).write_bytes(git_bytes('linux/patches/linux/' + patch))
    run(out, 'kernel_patch_verify', ['patch', '--dry-run', '--reverse', '--batch', '--fuzz=0', '-p1',
                                    '-i', provenance / patch], cwd=source)
    image = (GOLDEN / 'kernel/arch/riscv/boot/Image').read_bytes()
    payload = (GOLDEN / 'opensbi/platform/generic/firmware/fw_payload.bin').read_bytes()
    assert payload[0x400000:0x400000 + len(image)] == image
    assert not any(payload[0x400000 + len(image):]), 'Unexpected OpenSBI trailer'
    # R17 fw_next_addr points at the fixed 4 MiB offset; firmware data/BSS and
    # DTB precede it. No code references _payload_end/_fw_reloc_end (OpenSBI1.6).
    (provenance / 'opensbi_r17_prefix.bin').write_bytes(payload[:0x400000])
    offset, compressed, raw = find_initramfs(image)
    (out / 'r17-initramfs.cpio.gz').write_bytes(compressed)
    fragment = git_bytes('linux/configs/linux.config').decode().replace(
        '@INITRAMFS@', str(out / 'r17-initramfs.cpio.gz')).replace(
        'CONFIG_LOCALVERSION="-prodock"', f'CONFIG_LOCALVERSION="{LOCALVERSION}"')
    (out / 'linux.config').write_text(fragment)
    shutil.copy2(GOLDEN / 'prodock-linux.dtb', out / 'prodock-linux.dtb')
    # Launchers use the retained repository sources and their original SDK.
    launch_names = ['fw_console/Makefile', 'fw_console/gpu.c', 'fw_console/gpu.h',
                    'fw_console/gpu_v1.c', 'fw_console/gpu_v1.h', 'fw_console/orbital.ld',
                    'linux/boot/launch.c', 'linux/boot/unpack.h']
    for name in launch_names:
        destination = out / 'launcher-source' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(git_bytes(name))
    write_json(provenance / 'kernel_source_files.json', tree_hashes(source))
    write_json(provenance / 'recipe.json', {
        'schema': 1, 'candidate': True, 'release_qualified': False, 'board': 'prodock',
        'reference_commit': REFERENCE, 'kernel_source_origin': str(BASE),
        'kernel_source_inventory_sha256': metadata(provenance / 'kernel_source_files.json')['sha256'],
        'live_g3d1_sources': current, 'g3d1_patch': metadata(provenance / 'g3d1-only.patch'),
        'initramfs': {'image_offset': offset, 'compressed': metadata(out / 'r17-initramfs.cpio.gz'),
                      'uncompressed_sha256': sha(raw)},
        'opensbi_prefix': metadata(provenance / 'opensbi_r17_prefix.bin'),
        'localversion': LOCALVERSION, 'config_fragment': metadata(out / 'linux.config'),
        'launcher_sources': tree_hashes(out / 'launcher-source'),
        'compiler': metadata(Path(str(TC) + 'gcc')), 'hardware_validation': False,
        'changes': ['G3D1 driver/UAPI/KUnit only over R17 driver overlay',
                    'distinct kernel localversion; exact R17 initramfs/DTB/OpenSBI prefix retained'],
        'limitation': 'Existing patched Linux source snapshot; upstream archive is unavailable locally.'})
    print('PREPARED', out, flush=True)


def pack_zero_runs(data):
    blocks = []
    for offset in range(0, len(data), 4096):
        block = data[offset:offset + 4096]
        literal = any(block)
        if blocks and blocks[-1][0] == literal:
            blocks[-1][1].extend(block)
        else:
            blocks.append((literal, bytearray(block)))
    return b''.join(struct.pack('<I', len(block) | (0x80000000 if literal else 0)) +
                    (bytes(block) if literal else b'') for literal, block in blocks)


def build(out, jobs):
    from board_contract import before_build, record_build
    contract = before_build('prodock', candidate=True)
    recipe = json.loads((out / 'provenance/recipe.json').read_text())
    assert not (out / 'manifest.json').exists(), 'Completed candidates are immutable'
    assert tree_hashes(out / 'source') == json.loads((out / 'provenance/kernel_source_files.json').read_text())
    assert tree_hashes(out / 'launcher-source') == recipe['launcher_sources']
    assert metadata(out / 'linux.config') == recipe['config_fragment']
    assert metadata(out / 'r17-initramfs.cpio.gz') == recipe['initramfs']['compressed']
    assert metadata(out / 'provenance/opensbi_r17_prefix.bin') == recipe['opensbi_prefix']
    assert metadata(Path(str(TC) + 'gcc')) == recipe['compiler']
    for name, digest in recipe['live_g3d1_sources'].items():
        assert sha((ROOT / 'linux/drivers' / name).read_bytes()) == digest, name
    golden_manifest()
    record_build(out, contract)
    kernel = out / 'kernel'
    kernel.mkdir(exist_ok=True)
    command = ['make', '-C', out / 'source', f'O={kernel}', 'ARCH=riscv', f'CROSS_COMPILE={TC}']
    run(out, 'kernel_config', command + ['allnoconfig', f'KCONFIG_ALLCONFIG={out / "linux.config"}'])
    run(out, 'kernel_build', command + [f'-j{jobs}', 'Image'])
    image = (kernel / 'arch/riscv/boot/Image').read_bytes()
    _, compressed, raw = find_initramfs(image)
    assert sha(raw) == recipe['initramfs']['uncompressed_sha256']
    assert compressed == (out / 'r17-initramfs.cpio.gz').read_bytes()
    payload = (out / 'provenance/opensbi_r17_prefix.bin').read_bytes() + image
    payload += bytes((-len(payload)) % 8)
    assert len(payload) <= 0x02000000
    payload_path = out / 'opensbi/platform/generic/firmware/fw_payload.bin'
    payload_path.parent.mkdir(parents=True)
    payload_path.write_bytes(payload)
    packed = pack_zero_runs(payload)
    (out / 'payload.rle.bin').write_bytes(packed)
    (out / 'payload.h').write_text(
        f'#define PAYLOAD_LOAD 0x07c00000U\n#define PAYLOAD_BYTES {len(payload)}U\n'
        f'#define PAYLOAD_CRC 0x{zlib.crc32(payload):08x}U\n'
        f'#define PAYLOAD_RLE_BYTES {len(packed)}U\n#define PAYLOAD_RLE_CRC 0x{zlib.crc32(packed):08x}U\n')
    result = {'board': 'Tang Mega 138K Pro Dock', 'profile': 'prodock', 'abi': 1,
              'candidate': True, 'release_qualified': False, 'hardware_validation': False,
              'load': 0x07c00000, 'entry': 0x07c00000, 'kernel': 0x08000000,
              'gpu_memory': [0x00800000, 0x05800000], 'files': {},
              'kernel_release': (kernel / 'include/config/kernel.release').read_text().strip()}
    source = out / 'launcher-source/fw_console'
    for key, filename, define, stage in [
        ('launcher', 'launch.bin', '', None),
        ('launcher_usb', 'launch_usb.bin', '-DPAYLOAD_USB_STAGE ', 0x08000000),
        ('launcher_packed', 'launch_packed.bin', '-DPAYLOAD_RLE_STAGE ', 0x10000000)]:
        obj = out / key
        run(out, key, ['make', '-B', '-s', '-C', source, 'MAIN=../linux/boot/launch.c',
                       f'BUILD={obj}', f'LD={source / "orbital.ld"}',
                       'CFLAGS_EXTRA=' + define + '-I' + str(out)])
        shutil.copy2(obj / 'console_test.bin', out / filename)
        meta = metadata(out / filename)
        assert 12 < meta['bytes'] <= 65536
        result[key] = dict(meta, load=0xa0000000, entry=0xa000000c)
        if stage is not None:
            result[key]['stage'] = stage
    # Include unchanged reference userspace for the existing package validator.
    for name in json.loads((out / 'provenance/golden_manifest.json').read_text())['files']:
        if name.startswith('rootfs/'):
            (out / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(GOLDEN / name, out / name)
        result['files'][name] = metadata(out / name)
    result['recipe_sha256'] = metadata(out / 'provenance/recipe.json')['sha256']
    golden_manifest()  # Reference was read only throughout the build.
    write_json(out / 'manifest.json', result)
    print('CANDIDATE_BUILT', out, result['kernel_release'], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('prepare', 'build'))
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--candidate', action='store_true', required=True)
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    out = args.out.resolve()
    assert out.is_relative_to(ROOT / 'games/luma3d/build-kernel'), 'Candidate output must stay under games/luma3d/build-kernel'
    assert 1 <= args.jobs <= 8
    sys.path.insert(0, str(ROOT / 'tools'))
    if args.stage == 'prepare':
        prepare(out)
    else:
        build(out, args.jobs)


if __name__ == '__main__':
    main()
