#!/usr/bin/env python3
"""Offline flash preparation and exact readback checks; no device access.

Only ordinary flash bytes are backed up, not OTP/security/status registers.
A 64 KiB-aligned image preserves the remainder of the last erased sector.
Full-capacity readback also checks all bytes beyond the programmed region.
"""
import argparse
import hashlib
import json
import stat
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_regular(path, expected_size=None):
    path = Path(path)
    mode = path.lstat().st_mode
    if not stat.S_ISREG(mode):
        raise ValueError(f"Not a regular non-symlink file: {path}")
    data = path.read_bytes()
    if expected_size is not None and len(data) != expected_size:
        raise ValueError(f"Wrong length for {path}: {len(data)} != {expected_size}")
    return data


def prepare(payload_path, backup_a, backup_b, capacity, output):
    """Require two exact, independent full dumps before generating an image.

    Caller must retain each dump's separate hardware log. Equality alone does
    not attest that a file was read from the intended chip; this is offline.
    """
    if not 65536 <= capacity <= 64 * 1024 * 1024 or capacity % 65536:
        raise ValueError("Capacity must come from identified flash geometry")
    if Path(backup_a).resolve() == Path(backup_b).resolve():
        raise ValueError("Two distinct backup files are required")
    if Path(backup_a).samefile(backup_b):
        raise ValueError("Backups cannot be hard links to one file")
    a = read_regular(backup_a, capacity)
    b = read_regular(backup_b, capacity)
    if a != b:
        raise ValueError("Independent backups disagree")
    payload = read_regular(payload_path)
    if not 0 < len(payload) <= capacity:
        raise ValueError("Payload does not fit")
    end = (len(payload) + 65535) & ~65535
    image = payload + a[len(payload):end]
    expected = payload + a[len(payload):]
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'program.bin').write_bytes(image)
    # Only a hash is needed for the full expected image: no duplicate backup.
    report = dict(schema=1, hardware_access=False, capacity=capacity,
                  backup_sha256=digest(a), payload_sha256=digest(payload),
                  payload_bytes=len(payload), program_bytes=len(image),
                  program_sha256=digest(image), expected_full_sha256=digest(expected),
                  preserved_last_sector_bytes=end-len(payload),
                  preserved_tail_bytes=capacity-len(payload))
    (output / 'plan.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def verify(plan_path, dump_path):
    plan = json.loads(read_regular(plan_path))
    dump = read_regular(dump_path, plan['capacity'])
    actual = digest(dump)
    if actual != plan['expected_full_sha256']:
        raise ValueError("Full flash readback differs from intended bytes")
    return dict(full_readback_matches=True, bytes=len(dump), sha256=actual,
                hardware_boot_tested=False, powercycle_tested=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='action', required=True)
    prep = subs.add_parser('prepare')
    for name in ('payload', 'backup-a', 'backup-b', 'out'):
        prep.add_argument('--' + name, type=Path, required=True)
    prep.add_argument('--capacity', type=int, required=True)
    check = subs.add_parser('verify')
    check.add_argument('--plan', type=Path, required=True)
    check.add_argument('--dump', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'prepare':
        result = prepare(args.payload, args.backup_a, args.backup_b, args.capacity, args.out)
    else:
        result = verify(args.plan, args.dump)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
