#!/usr/bin/env python3
"""Root-only flash pre-read coordinator (detect + double read-only backup).

Scope
-----
* One single target: the FTDI 0403:6010 programmer, serial 2025071717, board
  tangmega138k, on host michael-AX15. The 2023112818 dock, UART7.3 and every
  J-Link are forbidden and are never referenced by this file.
* The coordinator only *reads* the SPI flash: one --detect pass and two
  independent --dump-flash passes. It never writes, erases, unprotects or
  bulk-erases the flash. The single --write-flash occurrence is the documented
  non-writing --detect mode, issued without any positional input file.
* Default mode is "prepare": the plan, the pinned identities and the SRAM
  consequence are printed, and no hardware resource, lock or output file is
  opened. "--run" performs the reviewed steps.

Consequence that must stay explicit
-----------------------------------
Preparing a flash access erases the SRAM FPGA configuration of the GW5AST
(reference/src/gowin.cpp:1220). Detect *and* both dumps therefore interrupt
the new SRAM candidate and the Linux it currently runs; afterwards the FPGA
may reload the program already stored in flash. This coordinator never
reloads, restores or re-programs the FPGA and never retries automatically.

Pinned identities
-----------------
wrapper  SHA-256 1c0c245f4bcad2c537b5fbaf77d055c5eccf6b3b17835a24c79be631cd218066
runtime  SHA-256 101c3c17456644f08217c3b11103aa78f8ab4debf4d2d133831c9c91c6d6d873
loader   SHA-256 f8387d5a0fa31ba2c832ebb5ed88e0c98594dbb75ad9df9a3321cc9574a970b4
         (ROOT/TESTS/prodock_new_20261028/load_fpga.py, reused through the
         reviewed target_guard context; its main() is never called)

Runner protocol
---------------
A runner is any callable ``runner(argv, stdout, timeout) -> int`` that writes
the tool output into the already opened binary ``stdout`` file and returns the
process return code (a negative value means death by signal). The default
runner is subprocess.run with a bounded timeout; the integration tests inject
a fake runner at exactly this level, so the whole coordinator stays real.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import signal
import socket
import stat
import subprocess
import sys
import time
from pathlib import Path

# --------------------------------------------------------------------------
# Pinned identities and constants (never inferred from the running host).
# --------------------------------------------------------------------------
ROOT = Path('/home/michael/console-validation-20261001')
TOOL_SHA = '1c0c245f4bcad2c537b5fbaf77d055c5eccf6b3b17835a24c79be631cd218066'
RUNTIME_SHA = '101c3c17456644f08217c3b11103aa78f8ab4debf4d2d133831c9c91c6d6d873'
LOADER_SHA = 'f8387d5a0fa31ba2c832ebb5ed88e0c98594dbb75ad9df9a3321cc9574a970b4'

SERIAL = '2025071717'
VENDOR = '0403'
PRODUCT = '6010'
BOARD = 'tangmega138k'
EXPECTED_IDCODE = '1081b'          # GW5AST-138 physical ID of tangmega138k
HOST_REQUIRED = 'michael-AX15'

SECTOR_BYTES = 65536               # capacity = sectors * 65536
DETECT_TIMEOUT = 120               # seconds, default detect timeout
DUMP_TIMEOUT = 900                 # seconds, default timeout of each dump
MIN_TIMEOUT = 1
MAX_TIMEOUT = 1800

JEDEC_RE = re.compile(r'^[ \t]*JEDEC ID:[ \t]*0x([0-9a-fA-F]{6})[ \t]*$', re.MULTILINE)
JEDEC_ANY_RE = re.compile(r'^[ \t]*JEDEC[ \t]+ID[ \t]*:[ \t]*(\S*)[ \t]*$',
                           re.MULTILINE | re.IGNORECASE)
DETECTED_RE = re.compile(
    r'^(?P<model>.+?)[ \t]+(?P<sectors>\d+)[ \t]+sectors[ \t]+size:[ \t]*'
    r'(?P<size>\d+(?:\.\d+)?)[ \t]*Mb(?:its)?[ \t]*$', re.IGNORECASE)
FOUND_RE = re.compile(r'^[ \t]*found[ \t]+(\d+)[ \t]+devices[ \t]*$', re.MULTILINE)
INDEX_RE = re.compile(r'^[ \t]*index[ \t]+(\d+)[ \t]*:[ \t]*$', re.MULTILINE)
IDCODE_RE = re.compile(r'^[ \t]*idcode[ \t]+0x([0-9a-fA-F]+)[ \t]*$', re.MULTILINE)
DETECT_MARK_RE = re.compile(r'^[ \t]*Detect flash:[ \t]*$', re.MULTILINE)
DETECTED_LINE_RE = re.compile(r'^[ \t]*Detected:[ \t]*(.*)$', re.MULTILINE)

# Records that describe the device or the flash; nothing like them may follow
# the completion line.
SIGNIFICANT_RES = (FOUND_RE, INDEX_RE, IDCODE_RE, DETECT_MARK_RE,
                   JEDEC_ANY_RE, DETECTED_LINE_RE)

# A display error makes the pass a failure. Whole words, case insensitive.
ERROR_PATTERN = re.compile(r'\b(?:fail|failed|failure|error|errors)\b', re.IGNORECASE)
# Historical flag text of an earlier trial: not an error of this pass.
HISTORICAL_FLAG = re.compile(r'auto_boot_1st_fail', re.IGNORECASE)

DUMP_MARKERS = (
    (re.compile(r'dump flash\s*\(\s*may take time\s*\)', re.IGNORECASE),
     'dump flash (May take time)'),
    (re.compile(r'open dump file\s+done', re.IGNORECASE), 'Open dump file DONE'),
    (re.compile(r'read flash', re.IGNORECASE), 'Read flash'),
    (re.compile(r'100\.00\s*%'), '100.00%'),
)
WRITE_TO_FLASH_RE = re.compile(r'write to flash', re.IGNORECASE)

CONSEQUENCES = (
    'Flash access erases the SRAM FPGA configuration on GW5AST-138 '
    '(reference/src/gowin.cpp:1220): the new SRAM candidate and the Linux it '
    'currently runs stop during the detect step and during both dumps.',
    'After that interruption the FPGA may reload the program currently stored '
    'in flash; this coordinator never reloads, restores or re-programs it.',
    'No flash write, erase, unprotect or bulk-erase command is issued. The only '
    '--write-flash flag used is the documented non-writing --detect mode, '
    'without any positional input file.',
    'Root cleanup of partial logs and partial dumps stays a separate root '
    'decision: every artifact is kept and nothing is deleted or restored here.',
)


class FlashError(ValueError, RuntimeError, OSError):
    """Refusal of the pure API or of the coordinator.

    It derives from ValueError, RuntimeError and OSError so that a caller may
    catch whichever of those it expects for a rejected input.
    """


class _Abort(BaseException):
    """Raised from a signal handler so the finally block still writes JSON."""


# --------------------------------------------------------------------------
# Small helpers.
# --------------------------------------------------------------------------
def _as_text(raw):
    if isinstance(raw, (bytes, bytearray, memoryview)):
        return bytes(raw).decode('utf-8', errors='replace')
    return str(raw)


def sha256_file(path):
    """SHA-256 of a regular file, read in chunks."""
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _error_context(text):
    """Return the offending snippet of an error word, or None."""
    cleaned = HISTORICAL_FLAG.sub(' ', text)
    match = ERROR_PATTERN.search(cleaned)
    if not match:
        return None
    start = max(0, match.start() - 40)
    return cleaned[start:match.end() + 40].strip()


def _require_regular(path, what):
    """Refuse symlinks and non regular files; return the lstat result."""
    try:
        info = os.lstat(path)
    except OSError as error:
        raise FlashError('%s is not accessible: %r' % (what, error))
    if stat.S_ISLNK(info.st_mode):
        raise FlashError('%s is a symlink: %s' % (what, path))
    if not stat.S_ISREG(info.st_mode):
        raise FlashError('%s is not a regular file: %s' % (what, path))
    return info


def _is_significant(line):
    """True when a line carries a device or a flash record."""
    return any(pattern.search(line) for pattern in SIGNIFICANT_RES)


def _check_done(lines, what):
    """Require the single "Done" completion line; only annotations may follow."""
    done = [index for index, line in enumerate(lines) if line.strip() == 'Done']
    if not done:
        raise FlashError('%s: missing final "Done" line' % what)
    if len(done) != 1:
        raise FlashError('%s: repeated "Done" line' % what)
    for line in lines[done[0] + 1:]:
        if not line.strip():
            continue
        if _is_significant(line):
            raise FlashError('%s: a device or flash record follows the "Done" line'
                             % what)


def _check_idcode(text, what):
    """One physical ID, and it must be the GW5AST-138 of tangmega138k."""
    codes = IDCODE_RE.findall(text)
    if len(codes) != 1:
        raise FlashError('%s: expected exactly one physical idcode, got %d'
                         % (what, len(codes)))
    code = codes[0].lower()
    if code != EXPECTED_IDCODE:
        raise FlashError('%s: unexpected physical idcode 0x%s (expected 0x%s)'
                         % (what, code, EXPECTED_IDCODE))
    return code


def _parse_detected(line, what):
    """Parse one "Detected: <model> <n> sectors size: <x>Mb" record."""
    match = DETECTED_RE.match(line.strip())
    if not match:
        raise FlashError('%s: unreadable flash geometry record: %r' % (what, line))
    model = match.group('model').strip()
    if not model:
        raise FlashError('%s: empty flash model text' % what)
    sectors = int(match.group('sectors'))
    if sectors <= 0:
        raise FlashError('%s: invalid sector count %d' % (what, sectors))
    size = float(match.group('size'))
    if abs(size - sectors / 2.0) > 1e-9:
        raise FlashError('%s: sector count %d disagrees with displayed size %sMb'
                         % (what, sectors, match.group('size')))
    return model, sectors, size


# --------------------------------------------------------------------------
# Pure API required by the protected tests.
# --------------------------------------------------------------------------
def parse_detection(raw):
    """Parse a detect log into {jedec, model, sectors, capacity}.

    Raises FlashError (ValueError/RuntimeError/OSError) for an unknown chip, an
    ambiguous or repeated record, a wrong or multiple physical ID, a geometry
    mismatch or any error word in the log.
    """
    text = _as_text(raw)
    lines = text.splitlines()
    what = 'detect log'

    context = _error_context(text)
    if context:
        raise FlashError('%s reports an error status: %r' % (what, context))

    found = FOUND_RE.findall(text)
    if len(found) != 1:
        raise FlashError('%s: expected exactly one "found N devices" header' % what)
    if int(found[0]) != 1:
        raise FlashError('%s: exactly one physical device expected, got %s'
                         % (what, found[0]))
    indexes = INDEX_RE.findall(text)
    if len(indexes) != 1 or indexes[0] != '0':
        raise FlashError('%s: expected exactly one "index 0:" record' % what)
    _check_idcode(text, what)

    if len(DETECT_MARK_RE.findall(text)) != 1:
        raise FlashError('%s: missing or repeated "Detect flash:" marker' % what)

    jedec_any = JEDEC_ANY_RE.findall(text)
    if len(jedec_any) != 1:
        raise FlashError('%s: expected exactly one JEDEC ID record' % what)
    jedec_match = JEDEC_RE.findall(text)
    if len(jedec_match) != 1:
        raise FlashError('%s: unsupported flash identification %r'
                         % (what, jedec_any[0]))
    jedec = jedec_match[0].lower()

    detected = DETECTED_LINE_RE.findall(text)
    if len(detected) != 1:
        raise FlashError('%s: expected exactly one "Detected:" flash record' % what)
    model, sectors, _size = _parse_detected(detected[0], what)

    _check_done(lines, what)

    return {'jedec': jedec, 'model': model, 'sectors': sectors,
            'capacity': sectors * SECTOR_BYTES}


def parse_dump_log(raw, jedec=None, sectors=None):
    """Check a dump log: no error, physical ID, JEDEC, geometry, completion."""
    text = _as_text(raw)
    lines = text.splitlines()
    what = 'dump log'

    context = _error_context(text)
    if context:
        raise FlashError('%s reports an error status: %r' % (what, context))
    if WRITE_TO_FLASH_RE.search(text):
        raise FlashError('%s mentions a flash write: refusing a read-only dump' % what)

    _check_idcode(text, what)

    jedec_any = JEDEC_ANY_RE.findall(text)
    if len(jedec_any) > 1:
        raise FlashError('%s: repeated JEDEC ID record' % what)
    if jedec_any:
        match = JEDEC_RE.findall(text)
        if len(match) != 1:
            raise FlashError('%s: unsupported flash identification %r'
                             % (what, jedec_any[0]))
        observed = match[0].lower()
        if jedec is not None and observed != str(jedec).lower():
            raise FlashError('%s: JEDEC %s differs from the detected %s'
                             % (what, observed, jedec))

    detected = DETECTED_LINE_RE.findall(text)
    if len(detected) > 1:
        raise FlashError('%s: repeated "Detected:" flash record' % what)
    if detected:
        _model, observed_sectors, _size = _parse_detected(detected[0], what)
        if sectors is not None and observed_sectors != int(sectors):
            raise FlashError('%s: %d sectors differ from the detected %d'
                             % (what, observed_sectors, sectors))

    for pattern, label in DUMP_MARKERS:
        if not pattern.search(text):
            raise FlashError('%s: missing completion marker %r' % (what, label))

    _check_done(lines, what)
    return {'jedec': str(jedec).lower() if jedec else None, 'sectors': sectors}


def backup_summary(path, capacity):
    """Return {bytes, sha256} for a regular, non symlink dump of `capacity`."""
    if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity <= 0:
        raise FlashError('invalid capacity: %r' % (capacity,))
    target = Path(path)
    info = _require_regular(target, 'dump file')
    if info.st_size != capacity:
        raise FlashError('dump file %s holds %d bytes, expected %d'
                         % (target, info.st_size, capacity))
    digest = hashlib.sha256()
    read = 0
    with open(target, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
            read += len(chunk)
    if read != capacity:
        raise FlashError('dump file %s yielded %d bytes, expected %d'
                         % (target, read, capacity))
    return {'bytes': read, 'sha256': digest.hexdigest()}


def compare_backups(a, b, capacity):
    """Compare two independent dumps; raise unless they are truly equal."""
    first = backup_summary(a, capacity)
    second = backup_summary(b, capacity)
    left = os.stat(a)
    right = os.stat(b)
    if left.st_dev == right.st_dev and left.st_ino == right.st_ino:
        raise FlashError('both paths share one inode (%d): not two independent dumps'
                         % left.st_ino)
    if first['sha256'] != second['sha256']:
        raise FlashError('backup contents differ (%s != %s)'
                         % (first['sha256'], second['sha256']))
    if Path(a).read_bytes() != Path(b).read_bytes():
        raise FlashError('backup bytes differ although the digests match')
    return {'matching': True, 'bytes': first['bytes'], 'sha256': first['sha256'],
            'sha256_b': second['sha256'], 'same_inode': False}


# --------------------------------------------------------------------------
# Reviewed command construction and hardware guard.
# --------------------------------------------------------------------------
def _load_target_guard():
    """Import the immutable reviewed guard (no I/O at import time)."""
    try:
        import target_guard  # type: ignore
        return target_guard
    except ImportError:
        pass
    here = Path(__file__).resolve().parent
    for candidate in (here / 'target_guard.py', here / 'reference' / 'target_guard.py'):
        if candidate.is_file():
            spec = importlib.util.spec_from_file_location('reviewed_target_guard', candidate)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise FlashError('reviewed target_guard.py not found next to the coordinator')


def _local_command(action, tool, output=None, size=None):
    """The allowlisted argv, built locally."""
    base = [str(tool), '--usb-serial-num', SERIAL, '-b', BOARD, '--verbose']
    if action == 'detect':
        return base + ['--write-flash', '--detect']
    if action == 'dump' and output is not None and isinstance(size, int) and size > 0:
        return base + ['--dump-flash', '--file-size', str(size), str(output)]
    raise FlashError('invalid operation or arguments')


def build_command(action, tool, output=None, size=None):
    """Return the reviewed argv, cross checked against the reviewed helper."""
    local = _local_command(action, tool, output=output, size=size)
    try:
        guard = _load_target_guard()
    except FlashError:
        return local
    if action == 'detect':
        shared = guard.command(tool, 'detect')
    else:
        shared = guard.command(tool, 'dump', output=output, size=size)
    shared = [str(item) for item in shared]
    if shared != local:
        raise FlashError('the reviewed helper command differs from the allowlisted argv')
    return shared


def default_guard_factory(root):
    """Hold the reviewed global lock around the reviewed steps."""
    root = Path(root)
    tool = root / 'bin' / 'openFPGALoader'
    runtime = root / 'bin' / 'runtime' / 'openFPGALoader'
    loader = root / 'TESTS' / 'prodock_new_20261028' / 'load_fpga.py'
    guard = _load_target_guard()
    return guard.guarded_target(tool, TOOL_SHA, loader, LOADER_SHA,
                                runtime=runtime, runtime_sha=RUNTIME_SHA)


def default_runner(argv, stdout, timeout):
    """Run the reviewed argv; stdout and stderr are merged into stdout."""
    completed = subprocess.run(list(argv), stdout=stdout, stderr=subprocess.STDOUT,
                               timeout=timeout)
    return completed.returncode


# --------------------------------------------------------------------------
# Coordinator.
# --------------------------------------------------------------------------
class Coordinator:
    """Detect pass, or two read-only dumps bound to a validated detection."""

    def __init__(self, *, phase, out_dir, root=ROOT, timeout=None, runner=None,
                 guard_factory=None, detection=None, detection_sha=None,
                 jedec=None, capacity=None):
        if phase not in ('detect', 'dump'):
            raise FlashError('phase must be detect or dump')
        if timeout is not None and not (MIN_TIMEOUT <= timeout <= MAX_TIMEOUT):
            raise FlashError('timeout must be between %d and %d seconds'
                             % (MIN_TIMEOUT, MAX_TIMEOUT))
        self.phase = phase
        self.root = Path(root)
        self.out_dir = Path(out_dir)
        self.timeout = timeout
        self.runner = runner or default_runner
        self.guard_factory = guard_factory
        self.detection = detection
        self.detection_sha = detection_sha
        self.jedec = jedec
        self.capacity = capacity

    # -- paths ------------------------------------------------------------
    @property
    def tool(self):
        return self.root / 'bin' / 'openFPGALoader'

    @property
    def runtime(self):
        return self.root / 'bin' / 'runtime' / 'openFPGALoader'

    @property
    def loader(self):
        return self.root / 'TESTS' / 'prodock_new_20261028' / 'load_fpga.py'

    def _timeout_for(self, phase):
        if self.timeout is not None:
            return self.timeout
        return DETECT_TIMEOUT if phase == 'detect' else DUMP_TIMEOUT

    def _checked_out_dir(self):
        base = (self.root / 'TESTS').resolve()
        out = self.out_dir.resolve()
        if out == base or not out.is_relative_to(base):
            raise FlashError('the output directory must live under %s' % base)
        return out

    # -- prepare ----------------------------------------------------------
    def prepare(self):
        """Describe the reviewed steps. No hardware, lock or file is opened."""
        out = self._checked_out_dir()
        plan = {
            'phase': self.phase,
            'mode': 'prepare',
            'will_run': False,
            'root': str(self.root),
            'out_dir': str(out),
            'tool': str(self.tool),
            'tool_sha256': TOOL_SHA,
            'runtime': str(self.runtime),
            'runtime_sha256': RUNTIME_SHA,
            'loader': str(self.loader),
            'loader_sha256': LOADER_SHA,
            'target_serial': SERIAL,
            'host_required': HOST_REQUIRED,
            'host_observed': socket.gethostname(),
            'timeouts': {'detect': self._timeout_for('detect'),
                         'dump': self._timeout_for('dump')},
            'flash_writes': 0,
            'sram_interrupted': True,
            'boot': False,
            'gpu': False,
            'powercycle': False,
            'consequences': list(CONSEQUENCES),
            'notes': [
                'The prepare step opens no resource and starts no process.',
                '--run is required for any hardware access.',
                'Every command is built by the reviewed target_guard helper.',
            ],
        }
        if socket.gethostname().split('.')[0] != HOST_REQUIRED:
            plan['notes'].append('The observed host is not %s; the reviewed '
                                 'guard will refuse the run.' % HOST_REQUIRED)
        if self.phase == 'detect':
            plan['commands'] = [build_command('detect', self.tool)]
            plan['outputs'] = ['detect.log', 'detect.json']
        else:
            evidence = self.validate_detection()
            plan['detection'] = evidence['summary']
            plan['commands'] = [
                build_command('dump', self.tool, output=out / 'backup_a.bin',
                              size=evidence['capacity']),
                build_command('dump', self.tool, output=out / 'backup_b.bin',
                              size=evidence['capacity']),
            ]
            plan['outputs'] = ['backup_a.bin', 'backup_a.log', 'backup_b.bin',
                               'backup_b.log', 'dump.json']
            plan['notes'].append('Both dumps run inside one single global lock.')
        return plan

    # -- evidence ---------------------------------------------------------
    def validate_detection(self):
        """Validate the detection JSON, its log SHA and reparse the log."""
        if self.detection is None or self.detection_sha is None:
            raise FlashError('the dump phase requires --detection and --detection-sha')
        if self.jedec is None or self.capacity is None:
            raise FlashError('the dump phase requires --jedec and --capacity')
        path = Path(self.detection)
        _require_regular(path, 'detection file')
        actual = sha256_file(path)
        if actual != str(self.detection_sha).strip().lower():
            raise FlashError('detection file SHA mismatch: %s != %s'
                             % (actual, self.detection_sha))
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError) as error:
            raise FlashError('detection file is not readable JSON: %r' % error)
        if not isinstance(data, dict):
            raise FlashError('detection file is not a JSON object')
        if data.get('phase') != 'detect':
            raise FlashError('detection file phase is %r, expected "detect"'
                             % data.get('phase'))
        if data.get('passed') is not True:
            raise FlashError('the detection pass is not marked as passed')
        self._check_target(data.get('target'))
        if data.get('tool_sha256') != TOOL_SHA:
            raise FlashError('detection tool SHA is not the pinned wrapper SHA')
        if data.get('runtime_sha256') != RUNTIME_SHA:
            raise FlashError('detection runtime SHA is not the pinned runtime SHA')
        log_path = data.get('log')
        log_sha = data.get('log_sha256')
        if not log_path or not log_sha:
            raise FlashError('the detection file does not reference its log')
        log_file = Path(log_path)
        _require_regular(log_file, 'detection log')
        if sha256_file(log_file) != str(log_sha).strip().lower():
            raise FlashError('the referenced detection log SHA does not match')
        parsed = parse_detection(log_file.read_bytes())
        if parsed['jedec'] != str(self.jedec).strip().lower():
            raise FlashError('JEDEC %s differs from the detected %s'
                             % (self.jedec, parsed['jedec']))
        if parsed['capacity'] != int(self.capacity):
            raise FlashError('capacity %s differs from the sector derived %d'
                             % (self.capacity, parsed['capacity']))
        summary = {'path': str(path), 'sha256': actual, 'log': str(log_file),
                   'log_sha256': str(log_sha).strip().lower(),
                   'jedec': parsed['jedec'], 'model': parsed['model'],
                   'sectors': parsed['sectors'], 'capacity': parsed['capacity']}
        return {'parsed': parsed, 'summary': summary}

    @staticmethod
    def _check_target(target):
        if not isinstance(target, dict):
            raise FlashError('the detection file does not carry the target identity')

        def pick(*names):
            for name in names:
                if target.get(name) not in (None, ''):
                    return str(target[name])
            return None

        serial = pick('serial', 'target_serial', 'targetSerial')
        vendor = pick('idVendor', 'vendor', 'id_vendor')
        product = pick('idProduct', 'product', 'id_product')
        if serial != SERIAL:
            raise FlashError('the detection targets serial %r, expected %s'
                             % (serial, SERIAL))
        if vendor != VENDOR or product != PRODUCT:
            raise FlashError('the detection targets %s:%s, expected %s:%s'
                             % (vendor, product, VENDOR, PRODUCT))

    # -- execution --------------------------------------------------------
    def _base_result(self):
        return {'phase': self.phase, 'mode': 'run', 'passed': False,
                'root': str(self.root), 'out_dir': str(self.out_dir),
                'target_serial': SERIAL, 'tool': str(self.tool),
                'tool_sha256': TOOL_SHA, 'runtime': str(self.runtime),
                'runtime_sha256': RUNTIME_SHA, 'loader': str(self.loader),
                'loader_sha256': LOADER_SHA, 'returncode': None,
                'flash_writes': 0, 'sram_interrupted': True, 'boot': False,
                'gpu': False, 'powercycle': False, 'started_unix': time.time()}

    def _open_guard(self):
        if self.guard_factory is not None:
            return self.guard_factory()
        return default_guard_factory(self.root)

    def _make_out_dir(self, out):
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            out.mkdir(exist_ok=False)
        except FileExistsError:
            raise FlashError('the output directory already exists: %s' % out)

    def _run_logged(self, argv, log_path, timeout):
        """Run one reviewed command, keeping the full log and partial output."""
        info = {'command': list(argv), 'log': str(log_path), 'returncode': None,
                'timeout': False, 'error': None}
        with open(log_path, 'xb') as log:
            try:
                info['returncode'] = int(self.runner(list(argv), log, timeout))
            except subprocess.TimeoutExpired:
                info['timeout'] = True
                info['error'] = 'timeout after %ss' % timeout
            log.flush()
        return info

    def _write_result(self, result):
        name = 'detect.json' if self.phase == 'detect' else 'dump.json'
        try:
            if self.out_dir.is_dir():
                path = self.out_dir / name
                path.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
                result['result_json'] = str(path)
        except OSError as error:
            result['result_json_error'] = repr(error)

    def execute(self):
        """Run the phase; the result JSON is always finished in a finally."""
        if self.phase == 'detect':
            return self._execute_detect()
        return self._execute_dump()

    def _execute_detect(self):
        result = self._base_result()
        try:
            out = self._checked_out_dir()
            self._make_out_dir(out)
            with self._open_guard() as identity:
                result['target'] = _identity(identity)
                argv = build_command('detect', self.tool)
                log = out / 'detect.log'
                info = self._run_logged(argv, log, self._timeout_for('detect'))
                result['run'] = info
                result['returncode'] = info['returncode']
                result['log'] = str(log)
                result['log_sha256'] = sha256_file(log)
                if info['error']:
                    raise FlashError('detect: %s' % info['error'])
                if info['returncode'] != 0:
                    raise FlashError('detect exited with %s' % info['returncode'])
                parsed = parse_detection(log.read_bytes())
                result['jedec'] = parsed['jedec']
                result['model'] = parsed['model']
                result['sectors'] = parsed['sectors']
                result['capacity'] = parsed['capacity']
                result['passed'] = True
        except BaseException as error:
            result['error'] = repr(error)
            result['passed'] = False
        finally:
            result['finished_unix'] = time.time()
            self._write_result(result)
        return result

    def _execute_dump(self):
        result = self._base_result()
        try:
            evidence = self.validate_detection()
            result['detection'] = evidence['summary']
            out = self._checked_out_dir()
            self._make_out_dir(out)
            result['dumps'] = {}
            with self._open_guard() as identity:
                result['target'] = _identity(identity)
                for name in ('a', 'b'):
                    self._one_dump(name, evidence, out, result)
                comparison = compare_backups(out / 'backup_a.bin',
                                             out / 'backup_b.bin',
                                             evidence['parsed']['capacity'])
                result['comparison'] = comparison
                result['passed'] = True
        except BaseException as error:
            result['error'] = repr(error)
            result['passed'] = False
        finally:
            result['finished_unix'] = time.time()
            self._write_result(result)
        return result

    def _one_dump(self, name, evidence, out, result):
        capacity = evidence['parsed']['capacity']
        target_file = out / ('backup_%s.bin' % name)
        log_file = out / ('backup_%s.log' % name)
        if target_file.exists() or target_file.is_symlink():
            raise FlashError('refusing to overwrite the existing dump %s' % target_file)
        argv = build_command('dump', self.tool, output=target_file, size=capacity)
        info = self._run_logged(argv, log_file, self._timeout_for('dump'))
        info['file'] = str(target_file)
        if log_file.exists():
            info['log_sha256'] = sha256_file(log_file)
        result['dumps'][name] = info
        if info['error']:
            raise FlashError('dump %s: %s' % (name, info['error']))
        if info['returncode'] != 0:
            raise FlashError('dump %s exited with %s' % (name, info['returncode']))
        parse_dump_log(log_file.read_bytes(), jedec=evidence['parsed']['jedec'],
                       sectors=evidence['parsed']['sectors'])
        info.update(backup_summary(target_file, capacity))


def _identity(identity):
    """Normalize the reviewed guard identity into the recorded target."""
    identity = dict(identity or {})
    target = dict(identity.get('target') or {})
    return {'serial': target.get('serial') or identity.get('target_serial'),
            'idVendor': target.get('idVendor'), 'idProduct': target.get('idProduct'),
            'busnum': target.get('busnum'), 'devnum': target.get('devnum'),
            'path': target.get('path')}


# --------------------------------------------------------------------------
# Command line.
# --------------------------------------------------------------------------
def _install_signal_handlers():
    previous = {}

    def handler(signum, _frame):
        raise _Abort('signal %d' % signum)

    for number in (signal.SIGINT, signal.SIGTERM):
        try:
            previous[number] = signal.signal(number, handler)
        except (ValueError, OSError):
            pass
    return previous


def _restore_signal_handlers(previous):
    for number, old in previous.items():
        try:
            signal.signal(number, old)
        except (ValueError, OSError):
            pass


def build_parser():
    parser = argparse.ArgumentParser(
        prog='flash_readonly.py',
        description='Root-only flash detect and double read-only backup coordinator.')
    parser.add_argument('--phase', choices=('detect', 'dump'), default='detect')
    parser.add_argument('--out', type=Path, required=True,
                        help='exclusive output directory, ROOT/TESTS/NEW')
    parser.add_argument('--run', action='store_true',
                        help='execute the reviewed steps (default: prepare only)')
    parser.add_argument('--timeout', type=int, default=None,
                        help='seconds per command, %d..%d' % (MIN_TIMEOUT, MAX_TIMEOUT))
    parser.add_argument('--detection', type=Path, default=None,
                        help='detection JSON of the detect phase')
    parser.add_argument('--detection-sha', default=None,
                        help='exact SHA-256 of the detection JSON')
    parser.add_argument('--jedec', default=None, help='JEDEC ID observed by root')
    parser.add_argument('--capacity', type=int, default=None,
                        help='capacity in bytes observed by root')
    parser.add_argument('--root', type=Path,
                        default=Path(os.environ.get('PRODOCK_ROOT', str(ROOT))),
                        help='validation root holding bin/ and TESTS/')
    return parser


def main(argv=None, runner=None, guard_factory=None):
    """Entry point. Returns 0 on success, 1 on a failed phase, 2 on a refusal."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.timeout is not None and not (MIN_TIMEOUT <= args.timeout <= MAX_TIMEOUT):
        print(json.dumps({'error': 'timeout must be between %d and %d seconds'
                                  % (MIN_TIMEOUT, MAX_TIMEOUT)}, indent=2))
        return 2
    try:
        coordinator = Coordinator(
            phase=args.phase, out_dir=args.out, root=args.root, timeout=args.timeout,
            runner=runner, guard_factory=guard_factory, detection=args.detection,
            detection_sha=args.detection_sha, jedec=args.jedec, capacity=args.capacity)
    except FlashError as error:
        print(json.dumps({'error': repr(error)}, indent=2))
        return 2

    if not args.run:
        try:
            plan = coordinator.prepare()
        except FlashError as error:
            print(json.dumps({'phase': args.phase, 'mode': 'prepare',
                              'error': repr(error)}, indent=2, sort_keys=True))
            return 2
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0

    previous = _install_signal_handlers()
    try:
        result = coordinator.execute()
    except _Abort as error:
        print(json.dumps({'error': repr(error)}, indent=2))
        return 130
    finally:
        _restore_signal_handlers(previous)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get('passed') else 1


if __name__ == '__main__':
    sys.exit(main())
