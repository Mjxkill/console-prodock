#!/usr/bin/env python3
"""Prepare only Michael's explicitly identified, erasable 32 GB SD.

The default is a read-only probe. --apply formats a FAT32 superfloppy (the
same layout as the tested file image), installs the pinned package as the
ordinary user, verifies after unmount/remount, and leaves the card unmounted.
No programmer, J-Link, FPGA or other disk is accessed.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
MEDIA = Path('/dev/disk/by-id/usb-Generic_STORAGE_DEVICE_000000001532-0:0')
OLD_MOUNT = '/media/michael/63c2d96d-938f-467d-a02f-58e7680691c6'
LOT = ROOT / 'games/luma3d/candidates/sd_install_20261028_r1'
PACKAGE = LOT / 'final_package_cm1_r1/package'
INSTALLER = LOT / 'minimax_execution_r2/isolation/tree/owned/install.py'
MANIFEST_SHA = '10b0ee5d77919f492bef371427d5849010ead80e9be7ded10089772d55b05b43'
INSTALLER_SHA = '0b21a2d5515e43a4a042193c9dedfe331cfdc9563d4bd39293e7a10e992dfda8'
EXPECTED = dict(serial='000000001532', diskseq='159', bytes=31267487744,
                major=8, minor=32, usb_path='3-4.4.4', removable='1')
NAMES = {'UBOOT.BIN', 'LINUX.BIN', 'LUMA.BIN', 'LUMA.DAT', 'ORBITAL.BIN',
         'ORBITAL.DAT', 'LUMA3D.ELF', 'GAME.SHA'}


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def check_identity(observed):
    for key, value in EXPECTED.items():
        if observed.get(key) != value:
            raise RuntimeError(f'SD identity changed: {key}')


def identify():
    node = MEDIA.resolve(strict=True)
    info = node.stat()
    if not stat.S_ISBLK(info.st_mode):
        raise RuntimeError('Target is not a block device')
    props = subprocess.check_output(['udevadm', 'info', '--query=property',
                                     '--name=' + str(node)], text=True)
    fields = dict(line.split('=', 1) for line in props.splitlines() if '=' in line)
    system = Path('/sys/class/block') / node.name
    result = dict(node=str(node), serial=fields.get('ID_SERIAL_SHORT'),
                  diskseq=(system / 'diskseq').read_text().strip(),
                  bytes=int((system / 'size').read_text()) * 512,
                  major=os.major(info.st_rdev), minor=os.minor(info.st_rdev),
                  removable=(system / 'removable').read_text().strip(),
                  usb_path=next((p.name for p in system.resolve().parents
                                 if (p / 'idVendor').is_file()), None))
    check_identity(result)
    return result


def mounts():
    data = json.loads(subprocess.check_output(
        ['findmnt', '--json', '--list', '-o', 'SOURCE,TARGET,MAJ:MIN'], text=True))
    return [item for item in data['filesystems'] if item.get('maj:min') == '8:32']


def verify_package():
    if sha(INSTALLER) != INSTALLER_SHA or sha(PACKAGE / 'manifest.json') != MANIFEST_SHA:
        raise RuntimeError('Installer or package manifest changed')
    manifest = json.loads((PACKAGE / 'manifest.json').read_text())
    if set(manifest['files']) != NAMES:
        raise RuntimeError('Unexpected file list')
    for name, entry in manifest['files'].items():
        path = PACKAGE / 'PRODOCK' / name
        if path.is_symlink() or path.stat().st_size != entry['bytes'] or sha(path) != entry['sha256']:
            raise RuntimeError('Package file changed: ' + name)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise RuntimeError('Root required for block-device identity and formatting')
    manifest = verify_package()
    identity = identify()
    if not args.apply:
        print(json.dumps(dict(identity=identity, mounts=mounts(), package_verified=True,
                              erase_authorized=True, format='FAT32 superfloppy')))
        return
    out = args.out.resolve()
    if not out.is_relative_to(HERE) or out.exists():
        raise RuntimeError('A new report directory inside the task is required')
    out.mkdir()
    report = dict(started=time.time(), identity=identity, package_sha256=MANIFEST_SHA,
                  user_authorization='non efface tout', formatted=False, installed=False,
                  readback_verified=False, left_unmounted=False)

    def save():
        (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')

    def run(name, command, timeout=120):
        report['last_action'] = name
        save()
        with (out / (name + '.log')).open('x') as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                           timeout=timeout, check=True)

    target = out / 'mnt'
    target.mkdir()
    (out / 'controller_used.py').write_bytes(Path(__file__).read_bytes())
    save()
    with (HERE / 'sd_media.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            active = mounts()
            if any(item['target'] != OLD_MOUNT for item in active) or len(active) > 1:
                raise RuntimeError('Unexpected SD mount; refusing to unmount it')
            if active:
                run('unmount_old', ['umount', OLD_MOUNT])
            identify()
            if mounts():
                raise RuntimeError('SD is still mounted')
            # This is the only destructive operation, authorized explicitly.
            run('erase_signatures', ['wipefs', '--all', str(MEDIA)])
            identify()
            run('format_fat32', ['mkfs.vfat', '-I', '-F', '32', '-n', 'PRODOCK', str(MEDIA)])
            report['formatted'] = True
            identify()
            if mounts():
                raise RuntimeError('Another process mounted the new filesystem')
            run('mount_install', ['mount', '-t', 'vfat', '-o',
                                 'uid=1000,gid=1000,umask=077,nosuid,nodev,noexec',
                                 str(MEDIA), str(target)])
            # The reviewed installer runs unprivileged and only handles files.
            run('install_package', ['runuser', '-u', 'michael', '--', '/usr/bin/python3',
                str(INSTALLER), '--package', str(PACKAGE), '--target', str(target),
                '--manifest-sha256', MANIFEST_SHA, '--apply'])
            report['installed'] = True
            run('sync', ['sync', '-f', str(target)])
            run('unmount_installed', ['umount', str(target)])
            identify()
            run('flush_buffers', ['blockdev', '--flushbufs', str(MEDIA)])
            run('check_fat', ['fsck.fat', '-n', str(MEDIA)])
            run('mount_readback', ['mount', '-t', 'vfat', '-o', 'ro,nosuid,nodev,noexec',
                                  str(MEDIA), str(target)])
            readback = {}
            for name, expected in manifest['files'].items():
                file = target / 'PRODOCK' / name
                readback[name] = dict(bytes=file.stat().st_size, sha256=sha(file))
                if any(readback[name][key] != expected[key] for key in ('bytes', 'sha256')):
                    raise RuntimeError('Physical SD readback mismatch: ' + name)
            report.update(readback=readback, readback_verified=True)
            run('unmount_verified', ['umount', str(target)])
            report['left_unmounted'] = not mounts()
        except BaseException as error:
            report['error'] = repr(error)
            # Do not unmount another actor's mount or retry any destructive step.
            if any(item['target'] == str(target) for item in mounts()):
                try:
                    run('cleanup_unmount', ['umount', str(target)])
                except Exception as cleanup:
                    report['cleanup_error'] = repr(cleanup)
            save()
            raise
        finally:
            report['finished'] = time.time()
            save()
    print(json.dumps({key: report[key] for key in
                     ('formatted', 'installed', 'readback_verified', 'left_unmounted')}))


if __name__ == '__main__':
    main()
