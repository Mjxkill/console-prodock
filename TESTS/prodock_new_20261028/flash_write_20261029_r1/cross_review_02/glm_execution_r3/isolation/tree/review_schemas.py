#!/usr/bin/env python3
"""Cross-review suites for the producer orchestration and writer evidence.

This module answers CONTRACT.md questions A, B and E by exercising real code:

* Question A - the unmodified producer ``load_sd_candidate.run_session`` is
  driven with fake boundaries (clock, child, guard, collector, loader) and its
  result file is fed through the writer's ``proofs.validate_sram_result``.
* Question B - the real ``flash_readonly.Coordinator`` detect/dump passes
  produce detect.json / dump.json which are fed to ``flash_write.prepare``;
  contradictory mutations (with internally consistent digests) must then be
  refused.
* Question E - single fields of the produced SRAM record are mutated after
  the fact, to see exactly which fields the writer re-derives from evidence
  and which it only trusts.

Every produced artifact is synthetic and labelled so; everything lives in a
TemporaryDirectory that is removed again.  No hardware, no network, no writes
into the project tree.
"""
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

REVIEW = Path(__file__).resolve().parent
PROJECT = REVIEW.parent

SERIAL = '2025071717'
BOARD = 'tangmega138k'
IDCODE = '1081b'
JEDEC = 'ef4018'
SECTOR = 65536

#: The exact code under review. A substitution or mid-review edit of any of
#: these files fails this module at import time instead of silently reviewing
#: different bytes.
REQUIRED_DIGESTS = {
    'producer/load_sd_candidate.py':
        '18a6c2af3b24703f66cf2df2cbf39ecf6589fb633c1d1ce5c6c74f14dcaca52e',
    'producer/program_sram_sample.log':
        '0225c2f7aa135a278da97dd57d6e9cb17476f5264cebe4d016b7aaccfe025195',
    'writer/flash_write.py':
        '4593bb8e26db3caea47927df73dad80ab30ca1e165c16be9b1084e3ed56f6f34',
    'writer/program_log.py':
        '1e8bf1585d72af69582c9be2610c863ef1e16ed1e3556dbe22ad4615fcbce6a3',
    'writer/proofs.py':
        '61b4ac16a01956001d03e5b17994b447c47d1627e3b4773c803290995d4026d8',
    'writer/refs/review/offline.py':
        '3ee29df91dc50799bb4bcc2fca43d632d61bd26733f9317500281971628c9277',
    'writer/refs/readonly/flash_readonly.py':
        'e55e186c4090b6c5cfd72f49fc402c7a41e545c08628465a06b6dd1233c5350d',
}

OBSERVATIONS = []


def note(key, text):
    OBSERVATIONS.append('%s: %s' % (key, text))


def digest_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_project_pins():
    """Check every reviewed target against its recorded digest."""
    problems = []
    for rel, expected in sorted(REQUIRED_DIGESTS.items()):
        actual = digest_file(PROJECT / rel)
        if actual != expected:
            problems.append('%s: sha256 %s != %s' % (rel, actual, expected))
    source_hashes = json.loads((PROJECT / 'SOURCE_HASHES.json').read_bytes())
    for rel, expected in sorted(REQUIRED_DIGESTS.items()):
        recorded = source_hashes.get(rel)
        if recorded is not None and recorded != expected:
            problems.append('%s: SOURCE_HASHES.json records %s'
                            % (rel, recorded))
    if problems:
        raise AssertionError('pinned review inputs changed:\n'
                             + '\n'.join(problems))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


verify_project_pins()
PROOFS = _load('proofs', PROJECT / 'writer' / 'proofs.py')
FLASH_WRITE = _load('review_flash_write', PROJECT / 'writer' / 'flash_write.py')
PRODUCER = _load('review_sd_candidate',
                 PROJECT / 'producer' / 'load_sd_candidate.py')
READONLY = PROOFS.flash_readonly()
TARGET_GUARD = PROOFS.target_guard()
ProofError = PROOFS.ProofError

FIXTURE_FS = PROJECT / 'writer' / 'fixture.fs'
SAMPLE_LOG = PROJECT / 'producer' / 'program_sram_sample.log'
SAMPLE_LOG_BYTES = SAMPLE_LOG.read_bytes()
FIXTURE_FS_BYTES = FIXTURE_FS.read_bytes()


def sha_entry(path):
    path = Path(path)
    return {'path': str(path.resolve()), 'sha256': digest_file(path),
            'bytes': path.stat().st_size}


# --------------------------------------------------------------------------
# Fake boundaries for the producer's run_session. Only the injected OS,
# process and UART surfaces are fake; the orchestration itself is the real
# unmodified code.
# --------------------------------------------------------------------------
class FakeClock:
    """Deterministic monotonic clock; every call advances a tiny step."""

    def __init__(self, start=1000.0, step=0.05):
        self.value = float(start)
        self.step = float(step)

    def __call__(self):
        self.value += self.step
        return self.value


class StubSubprocess:
    """The reviewed producer only calls subprocess.run for ps/fuser."""

    STDOUT = subprocess.STDOUT
    TimeoutExpired = subprocess.TimeoutExpired

    @staticmethod
    def run(argv, **kwargs):
        assert argv and argv[0] in ('ps', 'fuser'), argv
        return SimpleNamespace(returncode=0, stdout='', stderr='')


class FakeChild:
    """Popen stand-in: silent until one poll past its exit counter."""

    def __init__(self, argv, stdout, log_path, exit_after, log_body, rc,
                 wait_fails=False):
        self.args = list(argv)
        self.pid = 424242
        self.returncode = None
        self.stdout = stdout
        self.stderr = None
        self._log_path = Path(log_path)
        self._exit_after = int(exit_after)
        self._log_body = log_body
        self._rc = int(rc)
        self._calls = 0
        self._wait_fails = bool(wait_fails)

    def poll(self):
        self._calls += 1
        if self.returncode is None and self._calls >= self._exit_after:
            self.returncode = self._rc
            if self._log_body is not None and not self._log_path.exists():
                self._log_path.write_bytes(self._log_body)
        return self.returncode

    def wait(self, timeout=None):
        if self._wait_fails:
            raise subprocess.TimeoutExpired(self.args, timeout)
        code = self.poll()
        if code is None:
            raise subprocess.TimeoutExpired(self.args, timeout)
        return code

    def kill(self):
        self.returncode = -9


class FakeGuard:
    """Producer guard: diagnostic lock plus an USB console identity."""

    PORT = Path('/dev/ttyUSB0')

    def __init__(self):
        self.snapshots = 0
        self.locked = False
        self.uart = None

    @contextmanager
    def diagnostic_lock(self):
        assert not self.locked
        self.locked = True
        try:
            yield
        finally:
            self.locked = False

    def snapshot(self):
        self.snapshots += 1
        if self.snapshots == 1:
            raise FileNotFoundError('/dev/bus/usb re-enumeration pending')
        return {'busnum': 2, 'devnum': 77}

    def quiet_owner(self, result):
        return None

    def set_uart(self, uart):
        self.uart = uart
        return uart

    class PassiveUART:
        def __init__(self):
            self.opened = False
            self.closed = False

        def open(self, timeout=5):
            self.opened = True
            return {'busnum': '002', 'devnum': '077', 'serial': SERIAL}

        def read(self, size, timeout):
            return b''

        def connected(self):
            return False

        def close(self):
            self.closed = True


class FakeCollector:
    """Synthetic capture module; its result says so explicitly."""

    @staticmethod
    def capture(io, out, remaining, clock, sleep):
        deadline = clock() + max(0.0, float(remaining))
        attempts = 0
        while True:
            try:
                io.open(timeout=0.5)
                break
            except FileNotFoundError:
                attempts += 1
                if clock() >= deadline:
                    raise RuntimeError('fake collector: device never appeared')
                sleep(0.05)
        delivered = 0
        for _ in range(4):
            chunk = io.read(4096, 1.0)
            if not chunk:
                break
            delivered += len(chunk)
        return {'game_launch_observed': True, 'log_checks_passed': True,
                'segments': [], 'bytes': delivered, 'capture_completed': True,
                'synthetic': True, 'attempts_before_open': attempts,
                'synthetic_note': 'review harness replaces the pinned collector'}

    @staticmethod
    def preflight(manifest):
        return None


class FakeLoader:
    @staticmethod
    def devices():
        return [{'idVendor': '0403', 'idProduct': '6010', 'serial': SERIAL,
                 'busnum': 2, 'devnum': 77, 'board': BOARD}]


FAIL_LOG_BYTES = (b'write to ram\nfound 1 devices\nindex 0:\n'
                  b' idcode 0x1081b\nJEDEC ID: 0xef4018\n\n')


def replay(out_dir, bit, digest, seconds=15.0, *, rc=0, log_body=None,
           exit_after=6, wait_fails=False):
    """Run the real run_session with fake boundaries and return the report."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if log_body is None:
        log_body = SAMPLE_LOG_BYTES
    original = PRODUCER.subprocess
    PRODUCER.subprocess = StubSubprocess
    try:
        def spawn(argv, stdout=None, stderr=None, start_new_session=True,
                  preexec_fn=None):
            return FakeChild(argv, stdout, out_dir / 'program.log', exit_after,
                             log_body, rc, wait_fails)

        clock = FakeClock()
        return PRODUCER.run_session(out_dir, Path(bit), digest, seconds,
                                    FakeGuard(), FakeCollector(), FakeLoader(),
                                    spawn=spawn, clock=clock,
                                    sleep=lambda *_a: None,
                                    stop_group=lambda child, sig: None,
                                    check_permissions=lambda *_a, **_k: True)
    finally:
        PRODUCER.subprocess = original


# --------------------------------------------------------------------------
# Real readonly Coordinator with fake runner/guard boundaries.
# --------------------------------------------------------------------------
IDENT = b'found 1 devices\nindex 0:\n idcode 0x1081b\n'


def flash_line(sectors):
    size_mb = (sectors * SECTOR + 0xFFFF) // (1 << 20)
    return (b'JEDEC ID: 0xef4018\nDetected: winbond W25Q128 '
            b'%d sectors size: %dMb\n' % (sectors, size_mb))


def detect_log_bytes(sectors):
    return IDENT + b'Detect flash:\n' + flash_line(sectors) + b'Done\n'


DUMP_BODY = (b'dump flash (May take time)\nOpen dump file DONE\n'
             b'Read flash 100.00%\nDone\n')


def dump_log_bytes(sectors):
    return IDENT + flash_line(sectors) + DUMP_BODY


PROGRAM_BODY = (b'Writing: [==================================================]'
                b' 100.00%\nDone\nVerifying write (May take time)\n'
                b'Reading: [==================================================]'
                b' 100.00%\nDone\n')


def program_log_bytes(sectors):
    line = flash_line(sectors)
    return IDENT + line + line + PROGRAM_BODY


def backup_bytes(sectors):
    """Deterministic read-only dump; a marker sits at the very end."""
    data = bytearray()
    while len(data) < sectors * SECTOR:
        data.extend(bytes(((i * 31 + 7) & 0xFF) for i in range(SECTOR)))
    data[sectors * SECTOR - 20:sectors * SECTOR] = b'FLASH-END-MARKER-028'
    return bytes(data[:sectors * SECTOR])


class ReadonlyRunner:
    """Fake openFPGALoader for the real readonly Coordinator."""

    def __init__(self, sectors, backup=None):
        self.detect = detect_log_bytes(sectors)
        self.dump = dump_log_bytes(sectors)
        self.backup = backup_bytes(sectors) if backup is None else backup
        self.dump_bytes = self.backup
        self.calls = []

    def __call__(self, argv, stdout, timeout):
        assert timeout is None or timeout > 0
        argv = [str(item) for item in argv]
        self.calls.append(argv)
        if '--detect' in argv:
            stdout.write(self.detect)
            return 0
        if '--dump-flash' in argv:
            stdout.write(self.dump)
            Path(argv[-1]).write_bytes(self.backup)
            return 0
        if '--write-flash' in argv:
            assert '--verify' in argv
            stdout.write(program_log_bytes(256))
            return 0
        raise AssertionError('unexpected programme argv: %r' % (argv,))


@contextmanager
def readonly_guard_ctx():
    yield {'target_serial': SERIAL, 'board': BOARD,
           'target': {'serial': SERIAL, 'idVendor': '0403',
                      'idProduct': '6010', 'busnum': 3, 'devnum': 12}}


def readonly_guard_factory():
    return readonly_guard_ctx()


def writer_guard_factory(root):
    @contextmanager
    def ctx():
        yield {'target_serial': SERIAL, 'board': BOARD,
               'target': {'serial': SERIAL, 'idVendor': '0403',
                          'idProduct': '6010', 'busnum': 3, 'devnum': 12}}
    return ctx()


# --------------------------------------------------------------------------
# Full synthetic evidence chain: SRAM run + detect + dump + request.json.
# --------------------------------------------------------------------------
class Chain:
    def __init__(self, root, sectors, sram_dir, bitstream, digest,
                 detect_json, dump_json, backup, tests, request, acceptance):
        self.root = root
        self.sectors = sectors
        self.capacity = sectors * SECTOR
        self.sram_dir = sram_dir
        self.bitstream = bitstream
        self.digest = digest
        self.detect_json = detect_json
        self.dump_json = dump_json
        self.backup = backup
        self.tests = tests
        self.request = request
        self.acceptance = acceptance

    @property
    def result_path(self):
        return self.sram_dir / 'result.json'

    @property
    def sram_log_path(self):
        return self.sram_dir / 'program.log'


def build_chain(basedir, sectors=256, *, sram_rc=0, sram_wait_fails=False):
    """Run the real producer + real readonly Coordinator and write request.json."""
    root = Path(basedir) / 'root'
    tests = root / 'TESTS'
    tests.mkdir(parents=True, exist_ok=True)
    bitstream = tests / 'candidate.fs'
    bitstream.write_bytes(FIXTURE_FS_BYTES)
    digest = digest_file(bitstream)
    # A. real SRAM candidate rehearsal: the actual run_session is reused.
    sram_dir = tests / 'sram_run'
    report = replay(sram_dir, bitstream, digest, rc=sram_rc,
                    wait_fails=sram_wait_fails)
    if not sram_rc and not sram_wait_fails:
        assert report['passed'], dict(report)
        assert report['configuration_completed'], dict(report)
        assert report['physical_idcodes'] == [IDCODE], dict(report)
    result_path = sram_dir / 'result.json'
    result_json = json.loads(result_path.read_text())
    assert result_json['passed'] == report['passed'], dict(report)
    # B. real detection phase.
    detect_dir = tests / 'detect_run'
    runner = ReadonlyRunner(sectors)
    detect = READONLY.Coordinator(phase='detect', out_dir=detect_dir,
                                  root=root, runner=runner,
                                  guard_factory=readonly_guard_factory).execute()
    assert detect['passed'], dict(detect)
    assert detect['jedec'] == JEDEC and detect['sectors'] == sectors, dict(detect)
    detect_json = detect_dir / 'detect.json'
    # B. two independent dumps bound to that detection.
    dump_dir = tests / 'dump_run'
    dump = READONLY.Coordinator(phase='dump', out_dir=dump_dir, root=root,
                                runner=runner,
                                guard_factory=readonly_guard_factory,
                                detection=detect_json,
                                detection_sha=digest_file(detect_json),
                                jedec=JEDEC,
                                capacity=sectors * SECTOR).execute()
    assert dump['passed'], dict(dump)
    dump_json = dump_dir / 'dump.json'
    # acceptance bound to the synthetic but internally consistent digests.
    acceptance = {
        'version': 1, 'target_serial': SERIAL, 'physical_idcode': IDCODE,
        'bitstream_sha256': digest,
        'sram_result_sha256': digest_file(result_path),
        'dump_result_sha256': digest_file(dump_json),
        'sram_boot_accepted': True, 'permission_to_program': True,
        'flash_unchanged_since_backup': True, 'error': None,
        'cleanup_error': None, 'synthetic': True,
        'note': 'review acceptance for synthetic runs inside a temp dir'}
    acceptance_path = tests / 'acceptance.json'
    acceptance_path.write_text(json.dumps(acceptance, indent=2,
                                          sort_keys=True) + '\n')
    request = {
        'version': 1, 'target_serial': SERIAL, 'physical_idcode': IDCODE,
        'jedec': JEDEC, 'capacity': sectors * SECTOR,
        'bitstream': sha_entry(bitstream),
        'sram_result': sha_entry(result_path),
        'detection': sha_entry(detect_json),
        'backups': sha_entry(dump_json),
        'acceptance': sha_entry(acceptance_path)}
    request_path = tests / 'request.json'
    request_path.write_text(json.dumps(request, indent=2,
                                       sort_keys=True) + '\n')
    return Chain(root, sectors, sram_dir, bitstream, digest, detect_json,
                 dump_json, None, tests, request_path, acceptance_path)


def sign_request(path):
    """Recalculate the request sha256 after its content changed."""
    return digest_file(path)


def run_producer_replay(out_dir, bitstream, digest):
    return replay(out_dir, bitstream, digest)


def mutate_evidence(path, mutate):
    """Mutate a JSON evidence file in place and keep it well formed."""
    data = json.loads(path.read_text())
    mutate(data)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def resign_request_entries(request_path, **updates):
    """Fix entry digests inside request.json (name -> evidence path)."""
    request = json.loads(request_path.read_text())
    for name, evidence in updates.items():
        request[name] = sha_entry(evidence)
    request_path.write_text(json.dumps(request, indent=2,
                                       sort_keys=True) + '\n')


def prepare_chain(chain, out_name):
    return FLASH_WRITE.prepare(chain.request, sign_request(chain.request),
                               chain.tests / out_name, root=chain.root)


def copy_chain_result(chain, name, mutate=None, mutate_log=None):
    """A private copy of the SRAM result plus its log, under TESTS."""
    run_dir = chain.sram_dir
    target_dir = chain.tests / name
    target_dir.mkdir(parents=True, exist_ok=True)
    result = target_dir / 'result.json'
    log = target_dir / 'program.log'
    shutil.copyfile(chain.result_path, result)
    shutil.copyfile(chain.sram_log_path, log)
    if mutate is not None:
        data = json.loads(result.read_text())
        mutate(data)
        result.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')
    if mutate_log is not None:
        body = log.read_bytes()
        replacement = mutate_log(body)
        if replacement is None:
            body = (b'write to ram\nfound 1 devices\nindex 0:\n'
                    b' idcode 0x1081b\nJEDEC ID: 0xef4018\n\n')
        else:
            body = replacement
        log.write_bytes(body)
    return result


def validate_result_in(chain, result_path, bitstream=None):
    sha = digest_file(result_path)
    return FLASH_WRITE.proofs.validate_sram_result(
        chain.root, str(result_path), sha,
        str(chain.bitstream if bitstream is None else bitstream),
        digest_file(chain.bitstream if bitstream is None else bitstream))


# --------------------------------------------------------------------------
# Question A - the genuine producer output passes the writer schemas.
# --------------------------------------------------------------------------
class ProducerContractSuite(unittest.TestCase):
    """A: run_session orchestration and its writer-validated report."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix='review_sram_')
        cls.tmp = Path(cls._tmp.name)
        cls.chain = build_chain(cls.tmp, sectors=256)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_a01_real_run_session_report_shape(self):
        report = json.loads(self.chain.result_path.read_text())
        self.assertTrue(report['passed'])
        self.assertTrue(report['configuration_completed'])
        self.assertEqual(report['physical_idcodes'], [IDCODE])
        self.assertTrue(report['programmer_reaped'])
        self.assertTrue(report['fresh_console_observed'])
        self.assertTrue(report['fresh_console_identity'])
        self.assertIsNone(report['initial_console'])
        self.assertTrue(report['saw_absent'])
        self.assertTrue(report['log_checks_passed'])
        self.assertNotIn('uart_cleanup_error', report)
        self.assertIsNone(report.get('programmer_cleanup_error'))
        self.assertTrue(report['game_launch_observed'])
        self.assertEqual(report['target_serial'], SERIAL)
        self.assertEqual(report['flash_writes'], 0)
        self.assertEqual(report['sd_writes'], 0)
        self.assertFalse(report['cpu_jtag_access'])
        self.assertEqual(report['uart_tx_bytes'], 0)
        self.assertEqual(report['seconds_budget'], 15.0)
        self.assertIn('programmer_pid', report)
        self.assertIn('returncode', report)
        self.assertEqual(report['returncode'], 0)

    def test_a02_writer_validate_sram_result_accepts(self):
        # The produced result file is accepted untouched (question A).
        validate_result_in(self.chain, self.chain.result_path)

    def test_a03_writer_accepts_absent_cleanup_key(self):
        # E4: the writer must tolerate a missing uart_cleanup_error key.
        data = json.loads(self.chain.result_path.read_text())
        self.assertNotIn('uart_cleanup_error', data)
        self.assertNotIn('programmer_cleanup_error', data)
        validate_result_in(self.chain, self.chain.result_path)


# --------------------------------------------------------------------------
# Questions A2 and E - single-field contradictions of the SRAM records.
# --------------------------------------------------------------------------
class ProducerRefusalSuite(unittest.TestCase):
    """A2/E: mutated records are refused (or documented as writer trust)."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix='review_ref_')
        cls.tmp = Path(cls._tmp.name)
        cls.chain = build_chain(cls.tmp, sectors=256)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def refuser(self, name, mutate=None, mutate_log=None, bitstream=None):
        target = copy_chain_result(self.chain, name, mutate=mutate,
                                   mutate_log=mutate_log)
        with self.assertRaises(ProofError) as caught:
            validate_result_in(self.chain, target, bitstream=bitstream)
        return str(caught.exception)

    def test_a10_passed_flag_flip_refused(self):
        def mutate(data):
            data['passed'] = False

        text = self.refuser('passed_flip', mutate)
        note('A2 passed=false with consistent digests',
             'refused: %s' % text)

    def test_a11_configuration_completed_flip_refused(self):
        def mutate(data):
            data['configuration_completed'] = False

        text = self.refuser('config_flip', mutate)
        note('A2 configuration_completed=false',
             'refused: %s' % text)

    def test_a12_idcode_contradiction_refused(self):
        def mutate(data):
            data['physical_idcodes'] = ['1081c']

        text = self.refuser('idcode_flip', mutate)
        note('A2 physical_idcodes=1081c', 'refused: %s' % text)

    def test_a13_corrupt_program_log_refused(self):
        def bad_log(body):
            return b'write to ram\nfound 1 devices\nindex 0:\n'

        text = self.refuser('corrupt_log', mutate_log=bad_log)
        note('A2 truncated program.log beside a success record',
             'refused: %s' % text)

    def test_a14_bitstream_digest_contradiction_refused(self):
        def mutate(data):
            data['bitstream_sha256'] = 'ab' * 32

        text = self.refuser('bitstream_sha', mutate)
        note('A2 bitstream_sha256 differs from the request bitstream',
             'refused: %s' % text)

    def test_e1_returncode_one_with_completed_flag(self):
        # E1: does the writer re-derive returncode from the SRAM log or does
        # it trust the recorded boolean bundle?
        def mutate(data):
            data['returncode'] = 1

        try:
            validate_result_in(self.chain, copy_chain_result(
                self.chain, 'e1_rc1', mutate=mutate))
            note('E1 writer accepts returncode=1 while the log shows a '
                 'completed configuration', 'ACCEPTED - reported in REPORT.md')
            print('E1: writer accepted the contradictory returncode flag')
        except ProofError as refusal:
            note('E1 writer accepts returncode=1 while the log shows a '
                 'completed configuration', 'refused: %s' % refusal)
            print('E1: writer refused the contradictory returncode flag')

    def test_e2_uart_cleanup_error_present_refused(self):
        def mutate(data):
            data['uart_cleanup_error'] = 'synthetic-e2-uart-cleanup'

        text = self.refuser('e2_uart_cleanup', mutate)
        note('E2 uart_cleanup_error set in an otherwise happy record',
             'refused: %s' % text)

    def test_e3_real_reap_failure_is_refused(self):
        # E3: genuine producer failure path (wait raises), then the writer.
        run_dir = self.chain.tests / 'e3_reap_fail'
        report = replay(run_dir, self.chain.bitstream, self.chain.digest,
                        wait_fails=True)
        self.assertFalse(report['passed'])
        self.assertFalse(report['programmer_reaped'])
        self.assertIn('programmer_cleanup_error', report)
        self.assertFalse(report['log_checks_passed'])
        result_path = run_dir / 'result.json'
        with self.assertRaises(ProofError) as caught:
            validate_result_in(self.chain, result_path)
        note('E3 genuine reap failure (real run_session path)',
             'refused: %s' % caught.exception)


# --------------------------------------------------------------------------
# Question B - real readonly detection/dump evidence and its refusals.
# --------------------------------------------------------------------------
def mutate_detect(data, **fields):
    data.update(fields)


def chain_variant(basedir, sectors=4):
    """A fresh, small evidence chain; cheap enough for every variant."""
    return build_chain(basedir, sectors=sectors)


def detect_json_path(chain):
    return chain.detect_json


class ReadonlyEvidenceSuite(unittest.TestCase):
    """B: the writer accepts real detection/dump evidence and refuses lies."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix='review_readonly_')
        cls.tmp = Path(cls._tmp.name)
        cls.chain = build_chain(cls.tmp, sectors=256)
        cls.plan = prepare_chain(cls.chain, 'write_prep')
        cls.plan_path = cls.chain.tests / 'write_prep' / 'plan.json'

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_b01_real_detect_dump_produce_writer_plan(self):
        plan = self.plan
        self.assertEqual(plan.get('version'), 1)
        self.assertEqual(plan.get('kind'), 'flash-write-plan')
        self.assertEqual(Path(plan.get('root', '')), self.chain.root)
        self.assertEqual(set(plan.get('inputs', {})),
                         {'sram_result', 'detection', 'backups', 'bitstream',
                          'request', 'acceptance', 'backup_a', 'backup_b'})
        flash = plan.get('flash') or {}
        self.assertEqual(flash.get('jedec'), JEDEC)
        self.assertEqual(flash.get('sectors'), 256)
        self.assertEqual(flash.get('bytes'), 256 * SECTOR)
        image_path = Path(plan['image']['path'])
        image = image_path.read_bytes()
        self.assertEqual(len(image), SECTOR)
        # the plan binds exactly the offline image: payload + backup tail
        payload = Path(plan['payload']['path']).read_bytes()
        self.assertEqual(payload[:20], image[:20])
        offline_plan = json.loads(self.chain.tests.joinpath(
            'write_prep', 'prepared', 'plan.json').read_text())
        self.assertEqual(plan['image']['sha256'], digest_file(image_path))
        self.assertEqual(digest_file(image_path),
                         offline_plan['image_sha256'])
        self.assertEqual(plan['expected_full_sha256'],
                         offline_plan['expected_full_sha256'])
        manifest_path = self.chain.tests / 'write_prep' / 'manifest.json'
        self.assertTrue(manifest_path.exists())
        self.assertEqual(offline_plan['raw_route']['payload_bytes'], 20)

    def test_b02_detect_passed_false_refused(self):
        chain = chain_variant(self.tmp / 'b02')
        mutate_evidence(chain.detect_json, lambda data:
                        update_detect(data, passed=False))
        mutate_detect(chain, data=None)
        resign(chain)
        with self.assertRaises(ProofError) as caught:
            prepare_chain(chain, 'write_prep_b02')
        note('B detection passed=false with consistent digests',
             'refused: %s' % caught.exception)

    def test_b03_detect_returncode_one_refused(self):
        chain = chain_variant(self.tmp / 'b03')
        mutate_evidence(chain.detect_json, lambda data:
                        update_detect(data, returncode=1))
        resign(chain)
        with self.assertRaises(ProofError) as caught:
            prepare_chain(chain, 'write_prep_b03')
        note('B detection returncode=1', 'refused: %s' % caught.exception)

    def test_b04_backup_corrupted_consistently_refused(self):
        chain = chain_variant(self.tmp / 'b04')
        backup_a = Path(json.loads(chain.dump_json.read_text())
                        ['dumps']['a']['file'])
        original = backup_a.read_bytes()
        corrupted = bytearray(original)
        corrupted[SECTOR * 2 + 5] ^= 0x01
        backup_a.write_bytes(bytes(corrupted))
        mutate_evidence(chain.dump_json, lambda data:
                        update_backup_digests(data, chain))
        resign(chain)
        with self.assertRaises(ProofError) as caught:
            prepare_chain(chain, 'write_prep_b04')
        note('B backup_a corrupted with all record digests recomputed',
             'refused: %s' % caught.exception)

    def test_b05_dump_b_log_alias(self):
        chain = chain_variant(self.tmp / 'b05')
        dumps = json.loads(chain.dump_json.read_text())['dumps']
        self.assertNotEqual(dumps['a']['log'], dumps['b']['log'])
        mutate_evidence(chain.dump_json, alias_b_log)
        resign(chain)
        try:
            prepare_chain(chain, 'write_prep_b05_alias')
            note('B backups with log_b aliased onto log_a',
                 'ACCEPTED (recorded digests are consistent; the writer '
                 'accepted the alias - provenance observation)')
        except ProofError as refusal:
            note('B backups with log_b aliased onto log_a',
                 'refused: %s' % refusal)


def update_detect(data, **fields):
    data.update(fields)
    return data


def alias_b_log(data):
    dumps = data['dumps']
    dumps['b']['log'] = dumps['a']['log']


def update_backup_digests(data, chain):
    """Recompute file digests inside dump.json so records stay consistent."""
    dumps = data['dumps']
    for name in ('a', 'b'):
        info = dumps[name]
        info['sha256'] = digest_file(info['file'])
        info['bytes'] = Path(info['file']).stat().st_size
        log_info = Path(info['log'])
        info['log_sha256'] = digest_file(log_info)
        data['comparison'] = None


def resign(chain):
    """Recalculate every request entry after a chain file was mutated."""
    resign_request_entries(chain.request,
                           detection=chain.detect_json,
                           backups=chain.dump_json)
    mutate_evidence(chain.acceptance, lambda data: data.update(
        {'dump_result_sha256': digest_file(chain.dump_json)}))
    resign_request_entries(chain.request, acceptance=chain.acceptance)


# --------------------------------------------------------------------------
# Frozen digests, visible as a test (the import-time check is the true guard).
# --------------------------------------------------------------------------
class FrozenPinsSuite(unittest.TestCase):
    """F: the review binds itself to the exact unmodified source files."""

    def test_f01_pinned_digests_match_source_hashes(self):
        verify_project_pins()

    def test_f02_source_hashes_cover_the_review_targets(self):
        source_hashes = json.loads(
            (PROJECT / 'SOURCE_HASHES.json').read_bytes())
        missing = [rel for rel in REQUIRED_DIGESTS
                   if rel not in source_hashes]
        self.assertEqual(missing, [],
                         'SOURCE_HASHES.json lacks: %r' % (missing,))


def tearDownModule():
    for line in OBSERVATIONS:
        print('OBSERVATION %s' % line)


if __name__ == '__main__':
    unittest.main()