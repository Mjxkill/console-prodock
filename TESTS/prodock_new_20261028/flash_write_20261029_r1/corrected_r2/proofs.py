#!/usr/bin/env python3
"""Evidence validation, pinned reference loading and plan helpers.

Scope
-----
This module holds every *offline* decision of the flash write coordinator:

* it loads the pinned reference snapshots of ``refs/`` and refuses to use a
  file whose SHA-256 differs from ``refs_manifest.json``;
* it validates the request JSON, the read-only detection evidence, the two
  read-only backups, the SRAM candidate result and the explicit root
  acceptance attestation;
* it runs the two pinned native offline tools (``export_fs`` and
  ``raw_route_check``) with a bounded duration and checks their exit code,
  their printed counters and the bytes they produced;
* it writes and re-reads the plan and its manifest.

No hardware is touched here.  The module never opens a device, never talks
to a serial port and never reads the CPU.  The only subprocesses it starts
are the two pinned offline binaries, and they are executed from a private
temporary copy whose SHA-256 is verified against the pinned snapshot (the
snapshots themselves are mode 0400 and are never modified).

Identity
--------
One single target is accepted: FTDI 0403:6010 serial 2025071717, board
tangmega138k, physical FPGA id 0x1081b, on host michael-AX15.  The old
2023112818 dock, UART 7.3 and every J-Link stay forbidden and are never
referenced by this file.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# --------------------------------------------------------------------------
# Pinned production identities (never inferred from the running host).
# --------------------------------------------------------------------------
ROOT = Path('/home/michael/console-validation-20261001')
BASE = Path(__file__).resolve().parent
MANIFEST_NAME = 'refs_manifest.json'

SERIAL = '2025071717'
VENDOR = '0403'
PRODUCT = '6010'
BOARD = 'tangmega138k'
PHYSICAL_IDCODE = '1081b'
HOST_REQUIRED = 'michael-AX15'

TOOL_SHA = '1c0c245f4bcad2c537b5fbaf77d055c5eccf6b3b17835a24c79be631cd218066'
RUNTIME_SHA = '101c3c17456644f08217c3b11103aa78f8ab4debf4d2d133831c9c91c6d6d873'
LOADER_SHA = 'f8387d5a0fa31ba2c832ebb5ed88e0c98594dbb75ad9df9a3321cc9574a970b4'
GUARD_SHA = '47c4e095d6dab667f8c7d30ecf8c581e9f6bcdf278080242e92ba68616eaff5c'

SECTOR_BYTES = 65536
MIN_CAPACITY = 65536
MAX_CAPACITY = 64 * 1024 * 1024

NATIVE_TIMEOUT = 60
MIN_TIMEOUT = 1
MAX_TIMEOUT = 1800

# Pinned reference locations (relative to the directory of this file).
OFFLINE_REF = 'refs/review/offline.py'
EXPORT_REF = 'refs/review/export_fs'
RAW_REF = 'refs/review/raw_route_check'
FLASH_READONLY_REF = 'refs/readonly/flash_readonly.py'
PROCESS_GUARD_REF = 'refs/readonly/process_guard.py'
TARGET_GUARD_REF = 'refs/readonly/reference/target_guard.py'
LOAD_FPGA_REF = 'refs/readonly/reference/load_fpga.py'
SRAM_REF = 'refs/readonly/reference/load_sd_candidate.py'

#: Every reference this coordinator depends on, in the manifest order.
DEPENDENCIES = (OFFLINE_REF, EXPORT_REF, RAW_REF, FLASH_READONLY_REF,
                 PROCESS_GUARD_REF, TARGET_GUARD_REF, LOAD_FPGA_REF, SRAM_REF)

SHA64_RE = re.compile(r'^[0-9a-f]{64}$')
HEX6_RE = re.compile(r'^[0-9a-f]{6}$')
HEX_IDCODE_RE = re.compile(r'^[0-9a-f]{4,8}$')


class ProofError(ValueError, RuntimeError, OSError):
    """Refusal of a proof, of a schema or of the offline preparation.

    It derives from ValueError, RuntimeError and OSError so that a caller
    may catch whichever of those it expects for a rejected input.
    """


@contextlib.contextmanager
def pinned_errors(what):
    """Turn a refusal of a pinned reference into a single ``ProofError``.

    The pinned modules raise their own ``FlashError`` (a ValueError, a
    RuntimeError and an OSError).  The caller of this coordinator must see
    one single refusal type, whatever the pinned reference did.
    """
    try:
        yield
    except ProofError:
        raise
    except (ValueError, RuntimeError, OSError) as error:
        raise ProofError('%s: %r' % (what, error))


# --------------------------------------------------------------------------
# Small helpers.
# --------------------------------------------------------------------------
def sha256_file(path):
    """SHA-256 of a regular file, read in chunks."""
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def file_size(path):
    """Size in bytes of a regular file."""
    return os.lstat(path).st_size


def _now():
    return time.time()


def _require_regular(path, what):
    """Refuse symlinks and non regular files; return the lstat result."""
    try:
        info = os.lstat(path)
    except OSError as error:
        raise ProofError('%s is not accessible: %r' % (what, error))
    if stat.S_ISLNK(info.st_mode):
        raise ProofError('%s is a symlink: %s' % (what, path))
    if not stat.S_ISREG(info.st_mode):
        raise ProofError('%s is not a regular file: %s' % (what, path))
    return info


def _no_symlink_components(path):
    """Refuse a symlinked parent component of an absolute path."""
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise ProofError('refusing the symlinked path component %s' % current)


def require_file(path, what, *, base=None, must_exist=True):
    """Return an absolute, regular, non symlink file path.

    The path may not contain "..", may not have a symlinked parent component
    and may not leave `base` when one is given.
    """
    if not isinstance(path, (str, os.PathLike)):
        raise ProofError('%s must be a path' % what)
    target = Path(path)
    if not target.is_absolute():
        raise ProofError('%s must be an absolute path: %s' % (what, target))
    if '..' in target.parts:
        raise ProofError('%s must not contain ".." components: %s' % (what, target))
    if base is not None and not target.is_relative_to(Path(base)):
        raise ProofError('%s must live under %s: %s' % (what, base, target))
    _no_symlink_components(target)
    if must_exist:
        _require_regular(target, what)
    return target


def require_sha256(value, what):
    """Return a 64 character lowercase hexadecimal SHA-256."""
    if not isinstance(value, str) or not SHA64_RE.match(value):
        raise ProofError('%s must be a 64 character lowercase hex SHA-256' % what)
    return value


def check_sha256(path, expected, what):
    """Compare the actual bytes of `path` with the expected digest."""
    actual = sha256_file(path)
    if actual != str(expected).strip().lower():
        raise ProofError('%s SHA mismatch: %s != %s' % (what, actual, expected))
    return actual


def normalise_idcode(value, what):
    """Accept 0001081b or 1081b and return the canonical 1081b."""
    if not isinstance(value, str) or not HEX_IDCODE_RE.match(value.strip().lower()):
        raise ProofError('%s must be a hexadecimal physical idcode' % what)
    text = value.strip().lower()
    if int(text, 16) != int(PHYSICAL_IDCODE, 16):
        raise ProofError('%s is %r, expected %s' % (what, value, PHYSICAL_IDCODE))
    return PHYSICAL_IDCODE


# --------------------------------------------------------------------------
# Pinned reference loading.
# --------------------------------------------------------------------------
_MODULES = {}


def manifest():
    """Return the pinned manifest mapping (relative path -> SHA-256)."""
    path = BASE / MANIFEST_NAME
    _require_regular(path, 'reference manifest')
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise ProofError('the reference manifest is not readable JSON: %r' % error)
    if not isinstance(data, dict):
        raise ProofError('the reference manifest is not a JSON object')
    return data


def verify_ref(relative):
    """Return the absolute path of a pinned reference after checking its SHA."""
    pins = manifest()
    if relative not in pins:
        raise ProofError('the reference %s is not pinned in %s'
                         % (relative, MANIFEST_NAME))
    path = BASE / relative
    _require_regular(path, 'pinned reference %s' % relative)
    actual = sha256_file(path)
    if actual != pins[relative]:
        raise ProofError('the reference %s has SHA %s, expected %s'
                         % (relative, actual, pins[relative]))
    return path


def _import_pinned(relative, name):
    """Import a pinned reference from its exact location."""
    path = verify_ref(relative)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def process_guard():
    """Return the pinned process_guard module (the only process path)."""
    module = _MODULES.get(PROCESS_GUARD_REF)
    if module is None:
        module = _import_pinned(PROCESS_GUARD_REF, 'pinned_process_guard')
        existing = sys.modules.get('process_guard')
        if existing is None:
            sys.modules['process_guard'] = module
        else:
            origin = getattr(existing, '__file__', None)
            if origin is None or Path(origin).resolve() != verify_ref(PROCESS_GUARD_REF).resolve():
                raise ProofError('an unpinned process_guard is already imported: %r'
                                 % origin)
        _MODULES[PROCESS_GUARD_REF] = module
    return module


def flash_readonly():
    """Return the pinned read-only coordinator module."""
    module = _MODULES.get(FLASH_READONLY_REF)
    if module is None:
        # The pinned coordinator imports "process_guard" by name; make sure
        # that name can only ever resolve to the pinned snapshot.
        process_guard()
        readonly_dir = str((BASE / 'refs' / 'readonly').resolve())
        if readonly_dir not in sys.path:
            sys.path.insert(0, readonly_dir)
        module = _import_pinned(FLASH_READONLY_REF, 'pinned_flash_readonly')
        _MODULES[FLASH_READONLY_REF] = module
    return module


def target_guard():
    """Return the pinned hardware guard module."""
    module = _MODULES.get(TARGET_GUARD_REF)
    if module is None:
        verify_ref(TARGET_GUARD_REF)
        module = flash_readonly().load_target_guard()
        _MODULES[TARGET_GUARD_REF] = module
    return module


def offline():
    """Return the pinned offline preparation module."""
    module = _MODULES.get(OFFLINE_REF)
    if module is None:
        module = _import_pinned(OFFLINE_REF, 'pinned_offline')
        _MODULES[OFFLINE_REF] = module
    return module


def dependency_digests():
    """Return the pinned SHA-256 of every reference used by this coordinator."""
    pins = manifest()
    result = {}
    for relative in DEPENDENCIES:
        if relative not in pins:
            raise ProofError('the reference %s is not pinned' % relative)
        result[relative] = pins[relative]
    result['tool'] = TOOL_SHA
    result['runtime'] = RUNTIME_SHA
    result['loader'] = LOADER_SHA
    result['guard'] = GUARD_SHA
    return result


def verify_dependencies():
    """Re-check every pinned reference; raise when one of them changed."""
    for relative in DEPENDENCIES:
        verify_ref(relative)
    return dependency_digests()


# --------------------------------------------------------------------------
# Request schema.
# --------------------------------------------------------------------------
_FILE_FIELDS = ('bitstream', 'sram_result', 'detection', 'backups', 'acceptance')


def _file_entry(data, name):
    """Validate one {"path", "sha256"} entry of the request."""
    if name not in data:
        raise ProofError('the request lacks the %r section' % name)
    entry = data[name]
    if not isinstance(entry, dict):
        raise ProofError('the request section %r must be an object' % name)
    if 'path' not in entry or 'sha256' not in entry:
        raise ProofError('the request section %r needs a path and a sha256' % name)
    path = entry['path']
    if not isinstance(path, str) or not path:
        raise ProofError('the request section %r has an invalid path' % name)
    digest = require_sha256(entry['sha256'], 'the request section %r sha256' % name)
    return {'path': path, 'sha256': digest}


def validate_request(data):
    """Validate the request JSON object and return its normalised form."""
    if not isinstance(data, dict):
        raise ProofError('the request must be a JSON object')
    version = data.get('version')
    if version != 1 or isinstance(version, bool):
        raise ProofError('the request version must be 1')
    serial = data.get('target_serial')
    if serial != SERIAL:
        raise ProofError('the request targets serial %r, expected %s'
                         % (serial, SERIAL))
    idcode = normalise_idcode(data.get('physical_idcode'), 'the request physical_idcode')
    jedec = data.get('jedec')
    if not isinstance(jedec, str) or not HEX6_RE.match(jedec):
        raise ProofError('the request jedec must be 6 lowercase hexadecimal digits')
    capacity = data.get('capacity')
    if isinstance(capacity, bool) or not isinstance(capacity, int):
        raise ProofError('the request capacity must be an integer number of bytes')
    if not MIN_CAPACITY <= capacity <= MAX_CAPACITY:
        raise ProofError('the request capacity %d is out of the supported range'
                         % capacity)
    if capacity % SECTOR_BYTES:
        raise ProofError('the request capacity %d is not a multiple of %d bytes'
                         % (capacity, SECTOR_BYTES))
    request = {'version': 1, 'target_serial': serial, 'physical_idcode': idcode,
               'jedec': jedec, 'capacity': capacity}
    for name in _FILE_FIELDS:
        request[name] = _file_entry(data, name)
    return request


def load_request(request_path, request_sha, root):
    """Read the request file, check its digest and validate its schema."""
    path = require_file(request_path, 'the request file', base=root / 'TESTS')
    expected = require_sha256(str(request_sha).strip().lower(), 'the request sha256')
    check_sha256(path, expected, 'the request file')
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise ProofError('the request file is not readable JSON: %r' % error)
    request = validate_request(data)
    request['path'] = str(path)
    request['sha256'] = expected
    request['bytes'] = file_size(path)
    scope_request(request, root)
    return request


def scope_request(request, root):
    """Check that every referenced path stays inside the approved scope."""
    root = Path(root)
    for name in _FILE_FIELDS:
        base = root if name == 'bitstream' else root / 'TESTS'
        path = require_file(request[name]['path'], 'the request %s file' % name,
                            base=base)
        request[name]['path'] = str(path)
        check_sha256(path, request[name]['sha256'], 'the request %s file' % name)
    return request


# --------------------------------------------------------------------------
# Evidence: the read-only detection.
# --------------------------------------------------------------------------
def validate_detection(root, detection_path, detection_sha, jedec, capacity):
    """Validate the read-only detection evidence with the pinned coordinator.

    The pinned ``Coordinator.validate_detection`` re-parses the referenced
    detect log and checks the recorded geometry, the target identity and the
    pinned tool/runtime/loader digests.  The extra checks below cover the
    recorded phase, mode, command and the error/timeout consistency.
    """
    readonly = flash_readonly()
    path = require_file(detection_path, 'the detection file', base=Path(root) / 'TESTS')
    expected = require_sha256(str(detection_sha).strip().lower(), 'the detection sha256')
    check_sha256(path, expected, 'the detection file')
    coordinator = readonly.Coordinator(
        phase='dump', out_dir=Path(root) / 'TESTS', root=Path(root),
        detection=path, detection_sha=expected, jedec=jedec, capacity=capacity)
    with pinned_errors('the detection evidence'):
        evidence = coordinator.validate_detection()
    data = json.loads(path.read_text())
    if data.get('mode') != 'run':
        raise ProofError('the detection evidence mode is %r, expected "run"'
                         % data.get('mode'))
    if data.get('error') is not None:
        raise ProofError('the detection evidence carries an error: %r'
                         % data.get('error'))
    if data.get('programmer_attempted') is not True:
        raise ProofError('the detection evidence did not attempt the detect pass')
    run = data.get('run')
    if not isinstance(run, dict):
        raise ProofError('the detection evidence does not describe its command')
    if run.get('returncode') != 0:
        raise ProofError('the detection command exited with %r' % run.get('returncode'))
    if run.get('timeout') is not False:
        raise ProofError('the detection command timed out')
    if run.get('error') is not None:
        raise ProofError('the detection command failed: %r' % run.get('error'))
    tool = Path(root) / 'bin' / 'openFPGALoader'
    with pinned_errors('the reviewed detect command'):
        expected_command = readonly.build_command('detect', tool)
    if [str(item) for item in run.get('command') or []] != expected_command:
        raise ProofError('the detection command differs from the reviewed detect argv')
    log_path = require_file(run.get('log'), 'the detection log',
                             base=Path(root) / 'TESTS')
    if str(log_path) != data.get('log') or run.get('log_sha256') != data.get('log_sha256'):
        raise ProofError('Detection command/log provenance is contradictory')
    summary = evidence['summary']
    summary['mode'] = data.get('mode')
    summary['returncode'] = run.get('returncode')
    summary['tool_sha256'] = data.get('tool_sha256')
    summary['runtime_sha256'] = data.get('runtime_sha256')
    summary['loader_sha256'] = data.get('loader_sha256')
    summary['log_path'] = str(log_path)
    return {'parsed': evidence['parsed'], 'summary': summary, 'data': data}


# --------------------------------------------------------------------------
# Evidence: the two read-only backups.
# --------------------------------------------------------------------------
def validate_backups(root, backups_path, backups_sha, detection, jedec, sectors,
                     capacity):
    """Validate the read-only dump evidence and the two independent backups."""
    readonly = flash_readonly()
    root = Path(root)
    path = require_file(backups_path, 'the backups file', base=root / 'TESTS')
    expected = require_sha256(str(backups_sha).strip().lower(), 'the backups sha256')
    check_sha256(path, expected, 'the backups file')
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ProofError('the backups file is not a JSON object')
    if data.get('phase') != 'dump':
        raise ProofError('the backups file phase is %r, expected "dump"'
                         % data.get('phase'))
    if data.get('mode') != 'run':
        raise ProofError('the backups file mode is %r, expected "run"'
                         % data.get('mode'))
    if data.get('passed') is not True:
        raise ProofError('the read-only backup pass is not marked as passed')
    if data.get('flash_writes') != 0:
        raise ProofError('the read-only backup pass records flash writes')
    if data.get('error') is not None:
        raise ProofError('the backups file carries an error: %r' % data.get('error'))
    if data.get('tool_sha256') != TOOL_SHA:
        raise ProofError('the backups file tool SHA is not the pinned wrapper SHA')
    if data.get('runtime_sha256') != RUNTIME_SHA:
        raise ProofError('the backups file runtime SHA is not the pinned runtime SHA')
    if data.get('loader_sha256') != LOADER_SHA:
        raise ProofError('the backups file loader SHA is not the pinned loader SHA')
    with pinned_errors('the recorded target identity'):
        readonly.Coordinator._check_target(data.get('target'))
    recorded_detection = data.get('detection')
    if not isinstance(recorded_detection, dict):
        raise ProofError('the backups file does not reference its detection')
    if recorded_detection.get('path') != detection['summary']['path']:
        raise ProofError('the backups file points at another detection file')
    if recorded_detection.get('sha256') != detection['summary']['sha256']:
        raise ProofError('the backups file points at another detection digest')
    if data.get('jedec') != jedec:
        raise ProofError('the backups file JEDEC differs from the request')
    if data.get('capacity') != capacity:
        raise ProofError('the backups file capacity differs from the request')
    if data.get('sectors') != sectors:
        raise ProofError('the backups file sector count differs from the request')
    dumps = data.get('dumps')
    if not isinstance(dumps, dict) or set(dumps) != {'a', 'b'}:
        raise ProofError('the backups file must describe exactly the dumps a and b')
    tool = root / 'bin' / 'openFPGALoader'
    files = {}
    for name in ('a', 'b'):
        files[name] = _validate_one_dump(root, dumps[name], tool, jedec, sectors,
                                         capacity, name)
    if Path(files['a']['log']).samefile(files['b']['log']):
        raise ProofError('Two independent dump logs are required')
    if any(files[n]['detected']['model'] != detection['parsed']['model'] for n in ('a', 'b')):
        raise ProofError('Dump flash model differs from detection')
    first = files['a']['file']
    second = files['b']['file']
    if first == second:
        raise ProofError('both dumps reference the same file')
    with pinned_errors('the backup comparison'):
        comparison = readonly.compare_backups(first, second, capacity)
    recorded = data.get('comparison')
    if not isinstance(recorded, dict):
        raise ProofError('the backups file does not record its comparison')
    if recorded.get('matching') is not True:
        raise ProofError('the backups file does not record a matching comparison')
    if recorded.get('sha256') != comparison['sha256']:
        raise ProofError('the recorded comparison digest differs from the recomputed one')
    if recorded.get('sha256_b') != comparison['sha256_b']:
        raise ProofError('Second recorded comparison digest contradicts the file')
    if recorded.get('bytes') != comparison['bytes']:
        raise ProofError('the recorded comparison size differs from the recomputed one')
    if recorded.get('same_inode') is not False:
        raise ProofError('the recorded comparison claims one shared inode')
    return {'path': str(path), 'sha256': expected, 'dumps': files,
            'comparison': comparison, 'data': data}


def _validate_one_dump(root, info, tool, jedec, sectors, capacity, name):
    """Validate one of the two read-only dump records and its files."""
    readonly = flash_readonly()
    if not isinstance(info, dict):
        raise ProofError('the dump %r record is not an object' % name)
    for field in ('command', 'log', 'file'):
        if not info.get(field):
            raise ProofError('the dump %r record lacks its %s' % (name, field))
    if info.get('returncode') != 0:
        raise ProofError('the dump %r exited with %r' % (name, info.get('returncode')))
    if info.get('timeout') is not False:
        raise ProofError('the dump %r timed out' % name)
    if info.get('error') is not None:
        raise ProofError('the dump %r failed: %r' % (name, info.get('error')))
    dump_file = require_file(info['file'], 'the dump %r file' % name,
                              base=Path(root) / 'TESTS')
    log_file = require_file(info['log'], 'the dump %r log' % name,
                            base=Path(root) / 'TESTS')
    with pinned_errors('the reviewed dump command'):
        expected_command = readonly.build_command('dump', tool, output=dump_file,
                                                   size=capacity)
    if [str(item) for item in info['command']] != expected_command:
        raise ProofError('the dump %r command differs from the reviewed dump argv' % name)
    log_sha = info.get('log_sha256')
    if not log_sha:
        raise ProofError('the dump %r record does not reference its log digest' % name)
    check_sha256(log_file, log_sha, 'the dump %r log' % name)
    with pinned_errors('the dump log'):
        parsed = readonly.parse_dump_log(log_file.read_bytes(), jedec=jedec,
                                          sectors=sectors)
    recorded = info.get('detected')
    if not isinstance(recorded, dict):
        raise ProofError('Dump lacks its parsed identification record')
    if isinstance(recorded, dict):
        for key in ('jedec', 'model', 'sectors', 'capacity'):
            if recorded.get(key) != parsed[key]:
                raise ProofError('the dump %r recorded %s contradicts its log'
                                 % (name, key))
    with pinned_errors('the dump file'):
        summary = readonly.backup_summary(dump_file, capacity)
    require_sha256(info.get('sha256'), 'recorded dump SHA')
    if info.get('sha256') != summary['sha256']:
        raise ProofError('the dump %r recorded digest differs from the file' % name)
    if isinstance(info.get('bytes'), bool) or info.get('bytes') != summary['bytes']:
        raise ProofError('the dump %r recorded size differs from the file' % name)
    return {'file': str(dump_file), 'sha256': summary['sha256'],
            'bytes': summary['bytes'], 'log': str(log_file),
            'log_sha256': log_sha, 'detected': parsed, 'command': expected_command}


# --------------------------------------------------------------------------
# Evidence: the SRAM candidate result.
# --------------------------------------------------------------------------
def validate_sram_result(root, path, sha, bitstream_path, bitstream_sha):
    """Validate the final SRAM result of the exact candidate."""
    root = Path(root)
    file_path = require_file(path, 'the SRAM result file', base=root / 'TESTS')
    expected = require_sha256(str(sha).strip().lower(), 'the SRAM result sha256')
    check_sha256(file_path, expected, 'the SRAM result file')
    data = json.loads(file_path.read_text())
    if not isinstance(data, dict):
        raise ProofError('the SRAM result is not a JSON object')
    if data.get('target_serial') != SERIAL:
        raise ProofError('the SRAM result targets serial %r, expected %s'
                         % (data.get('target_serial'), SERIAL))
    if data.get('bitstream_sha256') != bitstream_sha:
        raise ProofError('the SRAM result was produced for another bitstream')
    recorded_path = data.get('bitstream')
    if recorded_path and Path(recorded_path) != Path(bitstream_path):
        raise ProofError('the SRAM result was produced for another bitstream path')
    if data.get('configuration_completed') is not True:
        raise ProofError('the SRAM configuration was not completed')
    if data.get('flash_writes') != 0:
        raise ProofError('the SRAM trial wrote to the flash')
    if data.get('physical_idcodes') != [PHYSICAL_IDCODE]:
        raise ProofError('the SRAM result physical idcodes are %r'
                         % (data.get('physical_idcodes'),))
    if data.get('programmer_reaped') is not True:
        raise ProofError('the SRAM programmer was not reaped')
    if data.get('passed') is not True:
        raise ProofError('the SRAM trial is not marked as passed')
    if data.get('log_checks_passed') is not True:
        raise ProofError('the SRAM log checks did not pass')
    if data.get('game_launch_observed') is not True:
        raise ProofError('the SRAM trial did not observe the game launch')
    for field in ('error', 'programmer_cleanup_error', 'uart_cleanup_error'):
        if data.get(field) is not None:
            raise ProofError('the SRAM result carries %s: %r' % (field, data.get(field)))
    for field, pinned in (('tool_sha256', TOOL_SHA), ('runtime_sha256', RUNTIME_SHA),
                          ('loader_sha256', LOADER_SHA)):
        if field in data and data[field] != pinned:
            raise ProofError('the SRAM result %s is not the pinned digest' % field)
    return {'path': str(file_path), 'sha256': expected, 'bytes': file_size(file_path),
            'data': data}


# --------------------------------------------------------------------------
# Evidence: the explicit root acceptance attestation.
# --------------------------------------------------------------------------
def validate_acceptance(root, path, sha, *, bitstream_sha, sram_sha, dump_sha):
    """Validate the explicit root acceptance artifact.

    This artifact is a human attestation by root, not a sensor measurement:
    it binds the target, the physical id, the exact bitstream, the SRAM
    result digest and the dump result digest, and it states that the flash
    did not change since the backups were taken.
    """
    root = Path(root)
    file_path = require_file(path, 'the acceptance file', base=root / 'TESTS')
    expected = require_sha256(str(sha).strip().lower(), 'the acceptance sha256')
    check_sha256(file_path, expected, 'the acceptance file')
    data = json.loads(file_path.read_text())
    if not isinstance(data, dict):
        raise ProofError('the acceptance artifact is not a JSON object')
    if data.get('target_serial') != SERIAL:
        raise ProofError('the acceptance targets serial %r, expected %s'
                         % (data.get('target_serial'), SERIAL))
    normalise_idcode(data.get('physical_idcode'), 'the acceptance physical_idcode')
    if data.get('bitstream_sha256') != bitstream_sha:
        raise ProofError('the acceptance binds another bitstream')
    if data.get('sram_result_sha256') != sram_sha:
        raise ProofError('the acceptance binds another SRAM result')
    if data.get('dump_result_sha256') != dump_sha:
        raise ProofError('the acceptance binds another dump result')
    for field in ('sram_boot_accepted', 'permission_to_program',
                  'flash_unchanged_since_backup'):
        if data.get(field) is not True:
            raise ProofError('the acceptance does not state %s' % field)
    for field in ('error', 'cleanup_error'):
        if data.get(field) is not None:
            raise ProofError('the acceptance carries %s: %r' % (field, data.get(field)))
    return {'path': str(file_path), 'sha256': expected, 'bytes': file_size(file_path),
            'data': data}


# --------------------------------------------------------------------------
# The pinned native offline tools.
# --------------------------------------------------------------------------
def run_native(relative, arguments, *, timeout=NATIVE_TIMEOUT):
    """Run a pinned native offline tool from a verified temporary copy.

    The snapshots are mode 0400; the copy is made executable and its digest
    is compared with the pinned one before it is started.  The run is bounded
    and the temporary directory is always removed.
    """
    source = verify_ref(relative)
    expected = sha256_file(source)
    work = Path(tempfile.mkdtemp(prefix='flash-write-native-'))
    try:
        executable = work / source.name
        shutil.copyfile(source, executable)
        os.chmod(executable, 0o700)
        if sha256_file(executable) != expected:
            raise ProofError('the copied %s differs from the pinned bytes' % relative)
        argv = [str(executable)] + [str(item) for item in arguments]
        record = {'tool': relative, 'argv': [str(item) for item in argv],
                  'returncode': None, 'stdout': '', 'stderr': '', 'timeout': False,
                  'error': None}
        try:
            completed = subprocess.run(argv, capture_output=True, text=True,
                                       timeout=timeout)
        except subprocess.TimeoutExpired as error:
            record['timeout'] = True
            record['error'] = 'timeout after %ss' % timeout
            record['stdout'] = _as_text(error.stdout)
            record['stderr'] = _as_text(error.stderr)
            return record
        except OSError as error:
            record['error'] = repr(error)
            return record
        record['returncode'] = completed.returncode
        record['stdout'] = completed.stdout or ''
        record['stderr'] = completed.stderr or ''
        return record
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _as_text(value):
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode('utf-8', errors='replace')
    return value or ''


def export_payload(bitstream, output_path):
    """Export the .fs candidate with the pinned FsParser(false) tool."""
    record = run_native(EXPORT_REF, [str(bitstream), str(output_path)])
    if record['timeout']:
        raise ProofError('export_fs did not finish within %ss' % NATIVE_TIMEOUT)
    if record['error']:
        raise ProofError('export_fs failed: %s' % record['error'])
    if record['returncode'] != 0:
        raise ProofError('export_fs exited with %s: %s'
                         % (record['returncode'], (record['stdout'] or '').strip()))
    match = re.search(r'FLASH_PAYLOAD_BYTES=(\d+)', record['stdout'])
    if not match:
        raise ProofError('export_fs did not report the payload size')
    count = int(match.group(1))
    path = require_file(output_path, 'the exported payload')
    size = file_size(path)
    if size != count:
        raise ProofError('export_fs reported %d payload bytes but produced %d'
                         % (count, size))
    if count <= 0:
        raise ProofError('export_fs produced an empty payload')
    record['payload_bytes'] = count
    record['payload_sha256'] = sha256_file(path)
    record['payload_path'] = str(path)
    return record


def check_raw_route(bitstream, program_path):
    """Compare the FsParser and the RawParser routes with the pinned tool."""
    record = run_native(RAW_REF, [str(bitstream), str(program_path)])
    if record['timeout']:
        raise ProofError('raw_route_check did not finish within %ss' % NATIVE_TIMEOUT)
    if record['error']:
        raise ProofError('raw_route_check failed: %s' % record['error'])
    if record['returncode'] != 0:
        raise ProofError('raw_route_check exited with %s: %s'
                         % (record['returncode'], (record['stdout'] or '').strip()))
    match = re.search(r'RAW_ROUTE_IDENTICAL\s+payload=(\d+)\s+total=(\d+)',
                      record['stdout'])
    if not match:
        raise ProofError('raw_route_check did not report the identical routes')
    payload = int(match.group(1))
    total = int(match.group(2))
    size = file_size(program_path)
    if total != size:
        raise ProofError('raw_route_check saw %d bytes but the image holds %d'
                         % (total, size))
    record['route_payload_bytes'] = payload
    record['route_total_bytes'] = total
    return record


# --------------------------------------------------------------------------
# Plan and manifest.
# --------------------------------------------------------------------------
def write_json(path, payload):
    """Write a JSON document; a failed write may never keep a success."""
    try:
        with open(path, 'x') as handle:
            handle.write(json.dumps(payload, indent=2, sort_keys=True) + '\n')
    except FileExistsError:
        raise ProofError('refusing to overwrite the existing file %s' % path)
    except (OSError, TypeError, ValueError) as error:
        raise ProofError('cannot write %s: %r' % (path, error))


def file_entry(path):
    """Return {path, sha256, bytes} for an existing regular file."""
    target = require_file(path, 'the file')
    return {'path': str(target), 'sha256': sha256_file(target),
            'bytes': file_size(target)}


def manifest_entries(plan):
    """Return the {name: entry} mapping of every hashed artefact."""
    entries = {}
    for name, entry in (plan.get('inputs') or {}).items():
        entries['input:' + name] = entry
    for name, entry in (plan.get('proof_logs') or {}).items():
        entries['proof_log:' + name] = entry
    for name in ('image', 'payload', 'offline_report'):
        if plan.get(name):
            entries[name] = plan[name]
    return entries


def write_manifest(out_dir, plan):
    """Write the manifest: hashes of all inputs, proof logs, image, deps."""
    entries = manifest_entries(plan)
    payload = {
        'version': 1,
        'kind': 'flash-write-manifest',
        'created_unix': _now(),
        'root': plan.get('root'),
        'files': entries,
        'dependencies': plan.get('dependencies') or {},
        'plan_sha256': plan.get('plan_sha256'),
    }
    write_json(Path(out_dir) / 'manifest.json', payload)
    return payload


def revalidate_plan(plan, plan_path, root):
    """Re-check the plan, every input, every proof log and the image."""
    if not isinstance(plan, dict):
        raise ProofError('the plan is not a JSON object')
    if isinstance(plan.get('version'), bool) or plan.get('version') != 1:
        raise ProofError('the plan version must be 1')
    if plan.get('kind') != 'flash-write-plan':
        raise ProofError('the plan kind is not "flash-write-plan"')
    if plan.get('dependencies') != verify_dependencies():
        raise ProofError('Plan dependencies differ from the pinned runtime')
    required = {'request','bitstream','sram_result','detection','backups','acceptance','backup_a','backup_b'}
    if not isinstance(plan.get('inputs'), dict) or set(plan['inputs']) != required:
        raise ProofError('Plan must bind all required inputs')
    if not isinstance(plan.get('proof_logs'), dict) or set(plan['proof_logs']) != {'detection','dump_a','dump_b'}:
        raise ProofError('Plan must bind each proof log')
    root = Path(root)
    if Path(plan.get('root', '')) != root:
        raise ProofError('the plan was prepared for another root')
    for name, entry in (plan.get('inputs') or {}).items():
        path = require_file(entry.get('path'), 'the plan input %r' % name, base=root if name == 'bitstream' else root / 'TESTS')
        check_sha256(path, entry.get('sha256'), 'the plan input %r' % name)
        if entry.get('bytes') is not None and file_size(path) != entry['bytes']:
            raise ProofError('the plan input %r changed its size' % name)
    for name, entry in (plan.get('proof_logs') or {}).items():
        path = require_file(entry.get('path'), 'the plan proof log %r' % name, base=root / 'TESTS')
        check_sha256(path, entry.get('sha256'), 'the plan proof log %r' % name)
    image = plan.get('image')
    if not isinstance(image, dict):
        raise ProofError('the plan does not reference its image')
    image_path = require_file(image.get('path'), 'the plan image', base=root / 'TESTS')
    check_sha256(image_path, image.get('sha256'), 'the plan image')
    if image.get('bytes') is not None and file_size(image_path) != image['bytes']:
        raise ProofError('the plan image changed its size')
    for name in ('offline_report', 'payload'):
        entry = plan.get(name)
        if not isinstance(entry, dict):
            raise ProofError('Plan lacks ' + name)
        artifact = require_file(entry.get('path'), 'plan ' + name, base=root / 'TESTS')
        check_sha256(artifact, entry.get('sha256'), 'plan ' + name)
        if entry.get('bytes') != file_size(artifact):
            raise ProofError('Plan artifact size differs: ' + name)
    expected = plan.get('expected_full_sha256')
    require_sha256(str(expected or ''), 'the plan expected_full_sha256')
    return image_path


def make_output_dir(root, out_dir):
    """Create the exclusive output directory under ROOT/TESTS."""
    root = Path(root)
    out = Path(out_dir)
    if not out.is_absolute():
        raise ProofError('the output directory must be an absolute path')
    if '..' in out.parts:
        raise ProofError('the output directory must not contain ".." components')
    tests = root / 'TESTS'
    if not out.is_relative_to(tests) or out == tests:
        raise ProofError('the output directory must live under %s' % tests)
    current = root
    for part in out.relative_to(root).parts:
        current = current / part
        if current.is_symlink():
            raise ProofError('refusing the symlinked output component %s' % current)
    if out.exists() or out.is_symlink():
        raise ProofError('the output directory already exists: %s' % out)
    try:
        out.mkdir(parents=True, exist_ok=False)
    except OSError as error:
        raise ProofError('cannot create the output directory %s: %r' % (out, error))
    return out
