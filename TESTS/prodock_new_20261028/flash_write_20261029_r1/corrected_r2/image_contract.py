"""Bind actual flash-image bytes to accepted FS, original backups and report.

The same check runs before publishing an offline plan and inside the hardware
lock before the program runner. A valid set of independent file hashes is not
sufficient: these artifacts must describe one internally consistent image.
No hardware is accessed here. The native route checker is pinned and offline.
"""
import hashlib
import json
from pathlib import Path

import proofs


def digest(data):
    return hashlib.sha256(data).hexdigest()


def _file(entry, what, root, *, bitstream=False):
    if not isinstance(entry, dict):
        raise proofs.ProofError('Image contract lacks ' + what)
    path = proofs.require_file(entry.get('path'), what,
                               base=root if bitstream else root / 'TESTS')
    expected = proofs.require_sha256(entry.get('sha256'), what + ' SHA')
    data = path.read_bytes()
    if digest(data) != expected or entry.get('bytes') != len(data):
        raise proofs.ProofError('Image contract file changed: ' + what)
    return path, data


def _equal(report, expected):
    for name, value in expected.items():
        observed = report.get(name)
        if type(observed) is not type(value) or observed != value:
            raise proofs.ProofError('Offline image report contradicts actual bytes: ' + name)


def validate(plan, root):
    """Recompute all byte relations, then re-check the native FS/raw route.

    The report, payload and image are independently hashed and cross-checked.
    The preserved sector and untouched tail are derived from the two accepted
    backups. Checks after native execution catch input changes during that
    check. An unrelated process changing files after the final check is still
    outside this single-owner workflow; no claim of hostile-host resistance.
    """
    root = Path(root)
    capacity = plan.get('flash', {}).get('capacity')
    if type(capacity) is not int or not 65536 <= capacity <= 64 * 1024 * 1024 or capacity % 65536:
        raise proofs.ProofError('Image contract has an invalid flash capacity')
    inputs = plan.get('inputs', {})
    fs, _ = _file(inputs.get('bitstream'), 'accepted bitstream', root, bitstream=True)
    a_path, a = _file(inputs.get('backup_a'), 'backup A', root)
    b_path, b = _file(inputs.get('backup_b'), 'backup B', root)
    if a_path.samefile(b_path) or len(a) != capacity or len(b) != capacity or a != b:
        raise proofs.ProofError('Image contract requires independent equal full backups')
    payload_path, payload = _file(plan.get('payload'), 'payload', root)
    image_path, image = _file(plan.get('image'), 'program image', root)
    report_path, report_bytes = _file(plan.get('offline_report'), 'offline report', root)
    if not 0 < len(payload) <= capacity:
        raise proofs.ProofError('Image contract payload does not fit')
    try:
        report = json.loads(report_bytes)
    except (ValueError, UnicodeDecodeError) as error:
        raise proofs.ProofError('Offline image report is invalid JSON') from error
    if not isinstance(report, dict):
        raise proofs.ProofError('Offline image report is not an object')
    end = (len(payload) + 65535) & ~65535
    if image != payload + a[len(payload):end]:
        raise proofs.ProofError('Program bytes do not preserve the original sector tail')
    full = hashlib.sha256(payload)
    full.update(memoryview(a)[len(payload):])
    expected = dict(schema=1, hardware_access=False, capacity=capacity,
        backup_sha256=digest(a), payload_sha256=digest(payload), payload_bytes=len(payload),
        program_bytes=end, program_sha256=digest(image), expected_full_sha256=full.hexdigest(),
        preserved_last_sector_bytes=end-len(payload), preserved_tail_bytes=capacity-len(payload))
    _equal(report, expected)
    for name in ('payload_sha256', 'expected_full_sha256',
                 'preserved_last_sector_bytes', 'preserved_tail_bytes'):
        if type(plan.get(name)) is not type(expected[name]) or plan[name] != expected[name]:
            raise proofs.ProofError('Plan contradicts image contract: ' + name)
    route = proofs.check_raw_route(fs, image_path)
    if (route['route_payload_bytes'], route['route_total_bytes']) != (len(payload), end):
        raise proofs.ProofError('Native route lengths contradict image contract')
    # Each byte relation above was computed from a definite snapshot. Native
    # parsing must not silently allow a later version of one of those files.
    for entry, name in ((inputs['bitstream'], 'bitstream'), (inputs['backup_a'], 'backup A'),
                        (inputs['backup_b'], 'backup B'), (plan['payload'], 'payload'),
                        (plan['image'], 'image'), (plan['offline_report'], 'report')):
        proofs.check_sha256(Path(entry['path']), entry['sha256'], name + ' after route check')
    return dict(verified=True, hardware_access=False, payload_bytes=len(payload),
                program_bytes=end, capacity=capacity, program_sha256=expected['program_sha256'],
                payload_sha256=expected['payload_sha256'],
                expected_full_sha256=expected['expected_full_sha256'],
                preserved_last_sector_bytes=expected['preserved_last_sector_bytes'],
                preserved_tail_bytes=expected['preserved_tail_bytes'])
