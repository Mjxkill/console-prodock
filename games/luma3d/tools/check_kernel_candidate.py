#!/usr/bin/env python3
"""Verify an isolated Linux candidate package and optionally boot it on QEMU.

No device access. QEMU virt checks actual RV32 kernel/KUnit/userspace execution;
it is not a simulation or qualification of the AE350, FPGA, DDR or GPU.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import tarfile
import zlib

ROOT = Path(__file__).resolve().parents[3]


def meta(data):
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack', type=Path, required=True)
    parser.add_argument('--qemu', action='store_true')
    args = parser.parse_args()
    pack = args.pack.resolve()
    assert pack.is_relative_to(ROOT / 'games/luma3d/build-kernel')
    manifest = json.loads((pack / 'manifest.json').read_text())
    assert manifest['board'] == 'Tang Mega 138K Pro Dock' and manifest['abi'] == 1
    assert manifest['candidate'] is True and manifest['release_qualified'] is False
    assert manifest['hardware_validation'] is False
    assert manifest['load'] == manifest['entry'] == 0x07c00000
    assert manifest['kernel'] == 0x08000000
    for name, expected in manifest['files'].items():
        assert meta((pack / name).read_bytes()) == expected, name
    for key, name in [('launcher', 'launch.bin'), ('launcher_usb', 'launch_usb.bin'),
                      ('launcher_packed', 'launch_packed.bin')]:
        expected = manifest[key]
        actual = meta((pack / name).read_bytes())
        assert all(actual[k] == expected[k] for k in actual)
        assert expected['load'] == 0xa0000000 and expected['entry'] == 0xa000000c
        assert 12 < actual['bytes'] <= 65536
    assert manifest['launcher_usb']['stage'] == 0x08000000
    assert manifest['launcher_packed']['stage'] == 0x10000000
    payload = (pack / 'opensbi/platform/generic/firmware/fw_payload.bin').read_bytes()
    image = (pack / 'kernel/arch/riscv/boot/Image').read_bytes()
    assert 0 < len(payload) <= 0x02000000
    assert payload[0x400000:0x400000 + len(image)] == image
    assert not any(payload[0x400000 + len(image):])
    prefix = (pack / 'provenance/opensbi_r17_prefix.bin').read_bytes()
    assert payload[:0x400000] == prefix
    assert (pack / 'prodock-linux.dtb').read_bytes() in prefix
    packed = (pack / 'payload.rle.bin').read_bytes()
    position, unpacked = 0, bytearray()
    while position < len(packed):
        word, = struct.unpack_from('<I', packed, position)
        position += 4
        size, literal = word & 0x7fffffff, word >> 31
        assert size > 0 and len(unpacked) + size <= len(payload)
        if literal:
            assert position + size <= len(packed)
            unpacked.extend(packed[position:position + size])
            position += size
        else:
            unpacked.extend(bytes(size))
    assert bytes(unpacked) == payload
    header = (pack / 'payload.h').read_text()
    for key, value in [('PAYLOAD_BYTES', len(payload)), ('PAYLOAD_CRC', zlib.crc32(payload)),
                       ('PAYLOAD_RLE_BYTES', len(packed)), ('PAYLOAD_RLE_CRC', zlib.crc32(packed))]:
        match = re.search(r'^#define ' + key + r' (\w+)U$', header, re.M)
        assert match and int(match[1], 0) == value, key
    config = (pack / 'kernel/.config').read_text()
    assert 'CONFIG_PRODOCK=y\n' in config and '# CONFIG_MODULES is not set\n' in config
    assert 'CONFIG_PRODOCK_KUNIT_TEST=y\n' in config
    recipe = json.loads((pack / 'provenance/recipe.json').read_text())
    assert meta((pack / 'provenance/recipe.json').read_bytes())['sha256'] == manifest['recipe_sha256']
    cpio = gzip.decompress((pack / 'r17-initramfs.cpio.gz').read_bytes())
    assert meta(cpio)['sha256'] == recipe['initramfs']['uncompressed_sha256']
    tests = pack / 'tests'
    tests.mkdir(exist_ok=True)
    report = {'passed': False, 'hardware_validation': False,
              'kernel_release': manifest['kernel_release'], 'manifest': meta((pack / 'manifest.json').read_bytes()),
              'payload_crc32': f'{zlib.crc32(payload):08x}', 'packed_crc32': f'{zlib.crc32(packed):08x}',
              'package_hashes': True, 'rle_roundtrip': True, 'r17_opensbi_dtb_initramfs': True,
              'verification_tool': meta(Path(__file__).read_bytes()),
              'builder': meta((pack / 'provenance/build_kernel_candidate.py').read_bytes())}
    (pack / 'provenance/check_kernel_candidate.py').write_bytes(Path(__file__).read_bytes())
    objdump = ROOT / 'linux/build/riscv32-ilp32d--musl--stable-2025.08-1/bin/riscv32-buildroot-linux-musl-objdump'
    disassembly = subprocess.check_output([objdump, '-d', pack / 'kernel/vmlinux'], text=True)
    for line in disassembly.splitlines():
        match = re.match(r'\s*([0-9a-f]+):\s+[0-9a-f]+\s+([\w.]+)\s*(.*)', line)
        assert not match or not (match[2].startswith('amo') or match[2].startswith('lr.w')), line
    report['kernel_no_native_cold_atomics'] = True
    if args.qemu:
        bios = ROOT / 'linux/build/opensbi-qemu-virt/platform/generic/firmware/fw_dynamic.bin'
        report['qemu_bios'] = meta(bios.read_bytes())
        report['qemu_version'] = subprocess.check_output(['qemu-system-riscv32', '--version'], text=True).splitlines()[0]
        command = ['qemu-system-riscv32', '-machine', 'virt', '-cpu', 'rv32', '-m', '256M',
                   '-smp', '1', '-nographic', '-monitor', 'none', '-no-reboot',
                   '-bios', str(bios),
                   '-kernel', str(pack / 'kernel/arch/riscv/boot/Image'),
                   '-append', 'console=ttyS0 earlycon=sbi panic=1 kunit.enable=1 prodock.selftest=1']
        (tests / 'qemu_command.json').write_text(json.dumps(command, indent=2) + '\n')
        try:
            result = subprocess.run(command, capture_output=True, timeout=90)
            log = result.stdout + result.stderr
        except subprocess.TimeoutExpired as error:
            (tests / 'qemu_boot.log').write_bytes((error.stdout or b'') + (error.stderr or b''))
            raise
        (tests / 'qemu_boot.log').write_bytes(log)
        required = [b'PRODOCK_USERSPACE_SELFTEST_OK', b'PRODOCK_LINUX_BOOT_OK', b'PRODOCK_RUNTIME_OK',
                    b'pass:11 fail:0 skip:0 total:11', manifest['kernel_release'].encode()]
        assert result.returncode == 0 and all(s in log for s in required), log[-6000:].decode(errors='replace')
        assert not any(s in log for s in [b'not ok', b'Kernel panic', b'BUG:'])
        report['qemu_rv32_kunit_11_userspace'] = True
        report['qemu_is_not_ae350_or_gpu_validation'] = True
    report['passed'] = True
    (tests / 'package_result.json').write_text(json.dumps(report, indent=2) + '\n')
    # Compact, portable handoff: binaries/provenance/tests, never the full source/build cache.
    members = set(manifest['files']) | {'manifest.json', 'launch.bin', 'launch_usb.bin', 'launch_packed.bin',
        'payload.h', 'board_contract.json', 'linux.config', 'kernel/.config', 'r17-initramfs.cpio.gz'}
    for folder in ('provenance', 'tests'):
        members.update(str(p.relative_to(pack)) for p in (pack / folder).rglob('*') if p.is_file())
    archive = pack / 'runtime.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        for name in sorted(members):
            tar.add(pack / name, arcname=name, recursive=False)
    report['runtime_archive'] = meta(archive.read_bytes())
    (pack / 'handoff.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
