#!/usr/bin/env python3
"""Independent adversarial executable tests: real compiled reader + real journals.

Scope (CONTRACT.md, as refined by REVIEW_FINDINGS.md): concrete unittest cases against
  * the exact compiled reader bytes (readback_r1/build_01/readback.bin, 588B)
    executed by the bounded RV32 interpreter via readback_model.Reader,
  * the 256B readback journal decoder (readback_r1/decode.py),
  * the 512B MD12 journal decoders -- the protected original
    (microdma_r1/decode_journal.py) and the owned hardened candidate
    (microdma_decode_v2.py, imported by module path so its identical-ABI
    output can be compared side by side; importlib so neither 512B ABI can be
    confused with the new 256B reader ABI),
  * the real run02/run03 hardware artifacts (journal.bin, result.json, log).

This file owns nothing protected: every payload/decoder/log is read-only and
the real binary is always used (never a mock). No hardware, network or
physical CSR/cache/DDR/arbitration modeling is claimed anywhere.

Known outcome (updated after review): the reviewer CONFIRMED the useful
finding -- microdma_r1/decode_journal.py silently accepts a phase10/result1
completion claim whose words 24/25/26/27/31 contradict completion -- and
CORRECTED one of my inferences.  I had assumed command_words_remaining (word
24) would be 0 once all 8 command stores returned; actually microdma.S stores
the field immediately BEFORE each command word and never clears it, so the
final journaled value is 1.  The real run02/run03 journals carry 0x1 there
(direct evidence, read-only unpack).  The fixture below therefore uses
word24=1, and the payload was never edited to match my mistaken test.  The
bounded checks are implemented ONLY in the owned candidate microdma_decode_v2.py:
the last two test classes show the candidate rejecting every previously
unchecked-word mutation while the protected original keeps accepting them --
the original's laxity is preserved as an EXPECTED observation, not hidden.
All other reader/log/journal/provenance tests are unchanged and pass.
"""
import hashlib
import importlib.util
import json
import struct
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
RB = HERE / 'readback_r1'
MD12 = HERE / 'microdma_r1'

# test_reader.py already adds readback_r1 to sys.path; keep direct `python3
# adversarial.py` execution working too.
if str(RB) not in sys.path:
    sys.path.insert(0, str(RB))

from readback_model import Reader, JOURNAL, OLD, SCRATCH   # noqa: E402  (real-binary interpreter harness)
import decode as decode_mod                                # noqa: E402  (module: keeps NAMES)
from decode import decode as decode_256                    # noqa: E402  (256B reader journal decoder)

BINARY = (RB / 'build_01' / 'readback.bin').read_bytes()
BINARY_SHA = 'aa2a1a061c87de6cc47a567a217b6d4078df1d3c982242bfe2275ef7bcc50503'
VIDEO = 0xe9000000
GPU = 0xe9001000

RUN02 = HERE / 'run02'
RUN03 = HERE / 'run03'
RUN02_JOURNAL = (RUN02 / 'journal.bin').read_bytes()
RUN03_JOURNAL = (RUN03 / 'journal.bin').read_bytes()


def _load(name, path):
    """Import a protected module under a distinct name via importlib."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


decode_md12 = _load('adversarial_md12_decode_journal', MD12 / 'decode_journal.py').decode
# Owned hardened candidate; the ONLY place the reviewer-confirmed checks live.
decode_md12_v2 = _load('adversarial_md12_decode_v2', HERE / 'microdma_decode_v2.py').decode

SEED = [(0x12000000 + 4 * i) ^ 0xa5396c17 for i in range(32)]
CANARY = [0x6b4d6b4d] * 8
CLEAR_PATTERN = SEED[:8] + CANARY + SEED[16:]


def journal_words(cpu, count=64):
    """Reader journal words straight out of the model's ILM journal window."""
    return [cpu.word(JOURNAL + 4 * i) for i in range(count)]


def snapshot_old_journal(cpu):
    """Full 512B old journal as currently visible; call AFTER precondition changes."""
    return [cpu.word(OLD + 4 * i) for i in range(128)]


def signed(word):
    return word - 0x100000000 if word >= 0x80000000 else word


def unpack256(words):
    return struct.pack('<64I', *words[:64])


def footprint_ok(cpu):
    """No commands, no GPU writes; every store lands in the 256B journal window."""
    stores = [a for (write, a, _v) in cpu.accesses if write]
    return (cpu.commands == [] and cpu.gpu_writes == []
            and all(JOURNAL <= a < JOURNAL + 256 for a in stores))


# (word index, planted value) -> the single corruptions the reviewer's contract
# exercises on a completion claim; the candidate must refuse each one.
UNCHECKED_WORD_MUTATIONS = ((24, 0), (24, 2), (25, 0), (25, 0x12000080),
                            (26, 1), (27, 1), (31, 1))


def healthy_completed_claim():
    """run02/journal.bin repaired into the healthy completed payload.

    REVIEW CORRECTION: word 24 is 1, not 0.  microdma.S stores
    command_words_remaining immediately before each command word and never
    clears it, so all 8 stores returning still leave 1 journaled -- exactly
    what the protected artifacts already show in words[24:32]:
    [1, 0x1200007c, 0, 0, 32, 32, 0, 0].  word 25 is 0x1200007c, the last of
    the 32 compared DDR words.
    """
    words = list(struct.unpack('<128I', RUN02_JOURNAL))
    words[2] = 10                    # final phase
    words[3] = 1                     # result complete
    words[20] = 2                    # done_clear actually pulsed
    words[24] = 1                    # corrected: never cleared; was wrongly 0 in my first fixture
    words[25] = 0x1200007c           # last of the 32 compared DDR words
    words[30] = 32                   # clear compare did run
    words[96:128] = CLEAR_PATTERN    # clear image as a completed compare would leave it
    return words


class GuardRefusals(unittest.TestCase):
    """Every guard violation must refuse with result -1, phase 1, zero DDR reads.

    Refusal journals always leave the GPU identity word at 0 (the GPU CSRs are
    never reached), so decode_256 additionally reports 'gpu_identity' for them.
    """

    def _run_and_check_refusal(self, cpu, expect_issues):
        expected_old = snapshot_old_journal(cpu)          # AFTER deliberately changed preconditions
        words = cpu.run()
        self.assertEqual(signed(words[3]), -1)            # guard refusal, never a completion
        self.assertEqual(words[2], 1)                     # stuck in phase 1
        self.assertEqual(words[29], 0)                    # zero words read
        self.assertEqual(cpu.ddr_reads, [])               # refused BEFORE any DDR access
        self.assertEqual(words[32:64], [0] * 32)          # no image material recorded
        self.assertTrue(footprint_ok(cpu))
        self.assertEqual(snapshot_old_journal(cpu), expected_old)  # old journal never written
        self.assertEqual(cpu.csr[0x305], 0x80000000)      # reader restored mtvec on its way out
        decoded = decode_256(unpack256(words))
        self.assertFalse(decoded['readback_valid'])
        self.assertEqual(decoded['classification'], 'unobserved')
        self.assertEqual(decoded['issues'], expect_issues)

    def test_satp_nonzero_refuses_before_ddr(self):
        cpu = Reader(BINARY, 'cleared')
        cpu.csr[0x180] = 0xfffffc00                       # satp with a full ASID/ppn payload
        self._run_and_check_refusal(cpu, ['readback_incomplete', 'gpu_identity'])

    def test_mstatus_mie_refuses_before_ddr(self):
        cpu = Reader(BINARY, 'cleared')
        cpu.csr[0x300] |= 8                               # mstatus.MIE only, rest untouched
        self._run_and_check_refusal(
            cpu, ['readback_incomplete', 'cache_ilm_interrupt_guard', 'gpu_identity'])
        # The pre-guard value is journaled, which is what lets decode_256 flag it.
        self.assertEqual(cpu.word(JOURNAL + 4 * 8), 0x1808)

    def test_mie_nonzero_refuses_before_ddr(self):
        cpu = Reader(BINARY, 'cleared')
        cpu.csr[0x304] = 1
        self._run_and_check_refusal(
            cpu, ['readback_incomplete', 'cache_ilm_interrupt_guard', 'gpu_identity'])

    def test_old_journal_wrong_identity_refuses(self):
        # Reader's own magic instead of MD12's: the old journal must be the MD12 one.
        cpu = Reader(BINARY, 'cleared')
        cpu.put(OLD, 0x52423132)
        self._run_and_check_refusal(cpu, ['readback_incomplete', 'gpu_identity'])

    def test_old_journal_wrong_version_refuses(self):
        cpu = Reader(BINARY, 'cleared')
        cpu.put(OLD + 4, 2)
        self._run_and_check_refusal(cpu, ['readback_incomplete', 'gpu_identity'])

    def test_old_journal_wrong_phase_refuses(self):
        cpu = Reader(BINARY, 'cleared')
        cpu.put(OLD + 8, 9)                               # not the exact CLEAR phase 8
        self._run_and_check_refusal(cpu, ['readback_incomplete', 'gpu_identity'])

    def test_old_journal_wrong_result_refuses(self):
        cpu = Reader(BINARY, 'cleared')
        cpu.put(OLD + 12, 0xfffffffc)                     # -4, not the exact -5
        self._run_and_check_refusal(cpu, ['readback_incomplete', 'gpu_identity'])

    def test_old_journal_wrong_seed_count_refuses(self):
        cpu = Reader(BINARY, 'cleared')
        cpu.put(OLD + 112, 31)
        self._run_and_check_refusal(cpu, ['readback_incomplete', 'gpu_identity'])

    def test_old_journal_wrong_target_count_refuses(self):
        cpu = Reader(BINARY, 'cleared')
        cpu.put(OLD + 116, 31)
        self._run_and_check_refusal(cpu, ['readback_incomplete', 'gpu_identity'])

    def _framebuffer_case(self, offset):
        class FramebufferNonzero(Reader):
            """Narrow subclass: one AHB framebuffer CSR reads back nonzero."""
            def __init__(self, binary, off):
                self.off = off
                super().__init__(binary, 'cleared')

            def access(self, address, write=False, value=0):
                if address == VIDEO + self.off and not write:
                    self.accesses.append((False, address, 1))
                    return 1
                return super().access(address, write, value)

        self._run_and_check_refusal(
            FramebufferNonzero(BINARY, offset),
            ['readback_incomplete', 'gpu_identity'])

    def test_framebuffer_shadow_guard_refuses(self):
        self._framebuffer_case(8)

    def test_framebuffer_commit_guard_refuses(self):
        self._framebuffer_case(12)

    def test_framebuffer_active_guard_refuses(self):
        self._framebuffer_case(20)


class CompletedJournalConsistency(unittest.TestCase):
    """A completed journal with any single data/header/count/first-error mutation
    must never silently appear consistent. Journal words below are the 64-word
    slice cpu.run()[:64] that decode_256() consumes."""

    @classmethod
    def setUpClass(cls):
        cls.cleared = Reader(BINARY, 'cleared').run()[:64]     # result 1, phase 3, 32 words
        cls.unchanged = Reader(BINARY, 'unchanged').run()[:64] # result 1 with 8 recorded mismatches
        base = decode_256(unpack256(cls.cleared))
        assert base['readback_valid'] and base['classification'] == 'clear_exact_canaries_intact'

    def _flag(self, mutated, issue):
        decoded = decode_256(unpack256(mutated))
        self.assertFalse(decoded['readback_valid'], issue)
        self.assertIn(issue, decoded['issues'])
        self.assertEqual(decoded['classification'], 'unobserved')

    def test_single_data_mutation_flagged(self):
        for word_index in (32, 40, 63):                   # first, inside, last image word
            words = list(self.cleared)
            words[word_index] ^= 0x00000055
            self._flag(words, 'comparison_record_inconsistent')

    def test_count_mutation_flagged(self):
        words = list(self.cleared)
        words[16] = 1                                     # error_count claims a phantom error
        self._flag(words, 'comparison_record_inconsistent')
        words = list(self.cleared)
        words[29] = 31                                    # words_read no longer 32
        self._flag(words, 'readback_incomplete')

    def test_first_error_mutation_flagged(self):
        for word_index, label in ((13, 'first_bad_address'), (14, 'first_expected'),
                                  (15, 'first_actual'), (16, 'error_count')):
            words = list(self.unchanged)
            words[word_index] = 0x76543210
            self.assertIn(label, decode_mod.NAMES)
            self._flag(words, 'comparison_record_inconsistent')

    def test_completed_interrupt_guard_fields_flagged(self):
        words = list(self.cleared)
        words[8] |= 8                                     # old_mstatus.MIE set after the fact
        self._flag(words, 'cache_ilm_interrupt_guard')
        words = list(self.cleared)
        words[9] = 4                                      # old_mie nonzero
        self._flag(words, 'cache_ilm_interrupt_guard')

    def test_completed_cache_gpu_mutation_flagged(self):
        for word_index in (4, 5, 6):                      # cache_before/cache_after/milmb
            words = list(self.cleared)
            words[word_index] = 1
            self._flag(words, 'cache_ilm_interrupt_guard')
        words = list(self.cleared)
        words[17] = 0x424c5433                            # GPU identity corrupted
        self._flag(words, 'gpu_identity')

    def test_extent_and_reserved_mutation_flagged(self):
        """Positive control: the 256B decoder does enforce reserved-word discipline."""
        words = list(self.cleared)
        words[28] = 0x12000078                            # wrong last DDR address
        self._flag(words, 'extent_or_reserved')
        words = list(self.cleared)
        words[31] = 1                                     # reserved31 nonzero
        self._flag(words, 'extent_or_reserved')

    def test_wrong_size_magic_version_refused(self):
        raw = unpack256(self.cleared)
        for bad, match in ((raw[:255], 'Expected exact 256B journal'),
                           (raw + b'\x00', 'Expected exact 256B journal'),
                           (struct.pack('<64I', *([0x52423133] + list(self.cleared)[1:])),
                            'Wrong readback identity/version'),
                           (struct.pack('<64I', *([self.cleared[0], 2] + list(self.cleared)[2:])),
                            'Wrong readback identity/version')):
            with self.assertRaisesRegex(ValueError, match):
                decode_256(bad)

    def test_negative_or_zero_result_never_valid(self):
        for result in (0, 0xfffffff9, 0xfffffff7, 0xffffffff):   # 0, -7, -9, -1
            words = list(self.cleared)
            words[3] = result
            decoded = decode_256(unpack256(words))
            self.assertFalse(decoded['readback_valid'])
            self.assertIn('readback_incomplete', decoded['issues'])
        decoded = decode_256(unpack256(self.cleared))            # sanity: perfect journal stays valid
        self.assertTrue(decoded['readback_valid'])

    def test_completed_run_records_real_ddr_bytes(self):
        words = list(self.cleared)
        self.assertEqual(words[0], 0x52423132)
        self.assertEqual(words[1], 1)
        self.assertEqual(words[29], 32)
        self.assertEqual(words[32:64], CLEAR_PATTERN)     # 'cleared' DDR: seed, canary@8..15, seed

    def test_gpu_done_change_recorded_but_not_gating(self):
        """Result 1 means 32 CPU loads finished; GPU done stays 1 and is only recorded."""
        words = list(self.unchanged)
        self.assertEqual(words[18], 1)                    # done_before (GPU already done 1)
        self.assertEqual(words[19], 1)                    # done_after: recorded, still not gating
        decoded = decode_256(unpack256(words))
        self.assertTrue(decoded['readback_valid'])
        self.assertFalse(decoded['gpu_passed'])           # never promotes GPU success
        self.assertEqual(decoded['classification'], 'seed_unchanged')


class HangAndTrap(unittest.TestCase):
    """A CPU load that never completes must not yield a 'completed' journal."""

    def _hang_case(self, hang_at, expect_completed_loads, expect_ddr_reads):
        class LoadHang(Reader):
            """Narrow subclass: load number hang_at+1 never returns (AHB stall)."""
            def __init__(self, binary, at):
                self.at = at
                super().__init__(binary, 'cleared')

            def access(self, address, write=False, value=0):
                if SCRATCH <= address < SCRATCH + 128 and not write \
                        and len(self.ddr_reads) >= self.at:
                    raise AssertionError(f'AHB load hang at {address:#x}')
                return super().access(address, write, value)

        cpu = LoadHang(BINARY, hang_at)
        with self.assertRaisesRegex(AssertionError, 'AHB load hang'):
            cpu.run()                                     # interpreter aborts at the exception bound
        words = journal_words(cpu)
        self.assertEqual(words[2], 2)                     # stuck in phase 2
        self.assertEqual(words[3], 0)                     # result never written
        self.assertEqual(words[29], expect_completed_loads)
        self.assertEqual(len(cpu.ddr_reads), expect_ddr_reads)
        self.assertTrue(footprint_ok(cpu))
        decoded = decode_256(unpack256(words))
        self.assertFalse(decoded['readback_valid'])       # must NOT be labeled completed
        self.assertIn('readback_incomplete', decoded['issues'])
        self.assertEqual(decoded['classification'], 'unobserved')
        return words

    def test_load_hang_midstream_partial_journal(self):
        words = self._hang_case(10, expect_completed_loads=10, expect_ddr_reads=10)
        # 10 completed loads: seed words 0..7, then the 'cleared' canary in words 8..9.
        self.assertEqual(words[32:42], SEED[:8] + CANARY[:2])
        self.assertEqual(words[42:64], [0] * 22)                           # rest never filled
        self.assertEqual(words[28], 0x12000000 + 10 * 4)                   # hung load address journaled

    def test_load_hang_before_first_load(self):
        words = self._hang_case(0, expect_completed_loads=0, expect_ddr_reads=0)
        self.assertEqual(words[28], SCRATCH)              # last_ddr written before the stuck load
        self.assertEqual(words[32:64], [0] * 32)

    def test_trap_after_seven_loads_keeps_partial_evidence(self):
        cpu = Reader(BINARY, 'trap')
        words = cpu.run()
        self.assertEqual(len(cpu.ddr_reads), 7)
        self.assertEqual(cpu.ddr_reads, [SCRATCH + 4 * i for i in range(7)])
        self.assertEqual(signed(words[3]), -7)
        self.assertEqual(words[2], 2)                     # phase 2: not completed
        self.assertEqual(words[29], 7)
        self.assertEqual(words[28], 0x1200001c)           # the 8th load's address was journaled
        self.assertEqual(words[11], 0x1200001c)           # mtval: the trapping load address
        self.assertEqual(words[10], 5)                    # mcause: load access fault
        code_base = 0xa0005000
        self.assertTrue(code_base <= words[12] < code_base + len(BINARY))   # mepc inside payload
        self.assertEqual(words[32:39], SEED[:7])          # 7 real readback words preserved
        self.assertEqual(words[39:64], [0] * 25)
        self.assertTrue(footprint_ok(cpu))
        decoded = decode_256(unpack256(words))
        self.assertEqual(decoded['issues'], ['readback_incomplete', 'trap_recorded'])
        self.assertEqual(decoded['classification'], 'unobserved')


class RealHardwareJournals(unittest.TestCase):
    """run02/run03 artifacts: the original MD12 journal shows CLEAR never completed."""

    @classmethod
    def setUpClass(cls):
        cls.md12_words = list(struct.unpack('<128I', RUN02_JOURNAL))
        cls.decoded02 = decode_md12(RUN02_JOURNAL)
        cls.decoded03 = decode_md12(RUN03_JOURNAL)

    def test_run02_run03_declared_incomplete_clear(self):
        for run, decoded in (('run02', self.decoded02), ('run03', self.decoded03)):
            with self.subTest(run=run):
                self.assertFalse(decoded['passed'])
                self.assertEqual(decoded['header']['phase'], 8)
                self.assertEqual(decoded['header']['result'], -5)
                self.assertIn('clear_wait_or_error', decoded['issues'])
                self.assertIn('not_final_phase', decoded['issues'])
                self.assertIn('incomplete_cpu_images', decoded['issues'])
                self.assertIn('clear_image_mismatch', decoded['issues'])

    def test_zero_word_clear_image_is_not_a_measurement(self):
        """clear_compared_words==0 with an all-zero image: the clear compare never
        ran, so neither DDR clearing NOR corruption is measured by this journal."""
        for decoded in (self.decoded02, self.decoded03):
            header = decoded['header']
            self.assertEqual(header['seed_compared_words'], 32)
            self.assertEqual(header['target_compared_words'], 32)
            self.assertEqual(header['clear_compared_words'], 0)
            self.assertEqual(decoded['images']['clear'], [0] * 32)
            self.assertEqual(decoded['images']['seed'], SEED)   # those two compares DID run
            self.assertEqual(decoded['images']['target'], SEED)
            self.assertEqual(header['gpu_errors'], 0)           # GPU error counter, not a verdict

    def test_decoder_abis_stay_separate(self):
        """512B MD12 bytes must not pass the 256B decoder and vice versa."""
        new_journal = unpack256(Reader(BINARY, 'cleared').run())
        with self.assertRaisesRegex(ValueError, 'Expected exactly512bytes'):
            decode_md12(new_journal)
        with self.assertRaisesRegex(ValueError, 'Expected exact 256B journal'):
            decode_256(RUN02_JOURNAL)

    def test_result_files_agree_with_journal_bytes(self):
        for run_dir in (RUN02, RUN03):
            report = json.loads((run_dir / 'result.json').read_text())
            words = list(struct.unpack('<128I', (run_dir / 'journal.bin').read_bytes()))
            self.assertEqual(report['journal_words'], words)
            self.assertEqual(report['phase'], 8)
            self.assertEqual(report['cpu_result'], -5)
            self.assertFalse(report['diagnostic_passed'])
            self.assertTrue(report['hardware'])
            self.assertEqual(report['sd_writes'], 0)
            self.assertEqual(report['journal_bytes'], 512)
            self.assertEqual(report['scratch_address'], '0x12000000')

    def test_run02_run03_journals_byte_identical(self):
        self.assertEqual(hashlib.sha256(RUN02_JOURNAL).hexdigest(),
                         '17f453c398b2f5dcbad2769e7aa47c8ffda81827ce97c3f4a9d9e8368fc247e8')
        self.assertEqual(RUN02_JOURNAL, RUN03_JOURNAL)

    def test_microdma_logs_grounded_facts(self):
        for run_dir, markers in ((RUN02, ['nds.cpu', 'XLEN=32', 'MICRODMA_GPU 0x424c5432']),
                                 (RUN03, ['nds.cpu', 'XLEN=32', 'MICRODMA_GPU 0x424c5432',
                                          'MICRODMA_BEFORE_SNAPSHOT_A', 'MICRODMA_AFTER_GPU 0x424c5432'])):
            text = (run_dir / 'microdma.log').read_text()
            for marker in markers:
                self.assertIn(marker, text)
        # Raw, non-protocol taps observed in run03: opcode word 0x1c000000 twice. Clues
        # only; not treated as atomic GPU evidence anywhere in this suite.
        log03 = (RUN03 / 'microdma.log').read_text()
        self.assertIn('MICRODMA_AFTER_SNAPSHOT_A 0x10 0x0 0x1c000000 0x1c000000', log03)


class FootprintAndProvenance(unittest.TestCase):
    """Address allowlist and binary identity for the completed path too."""

    def test_completed_runs_allowlist(self):
        for scenario, expected_class in (('cleared', 'clear_exact_canaries_intact'),
                                         ('unchanged', 'seed_unchanged'),
                                         ('partial', 'other_or_partial_change'),
                                         ('canary', 'other_or_partial_change')):
            cpu = Reader(BINARY, scenario)
            words = cpu.run()
            with self.subTest(scenario=scenario):
                self.assertEqual(cpu.ddr_reads, list(range(SCRATCH, SCRATCH + 128, 4)))
                self.assertTrue(footprint_ok(cpu))
                decoded = decode_256(unpack256(words))
                self.assertEqual(decoded['classification'], expected_class)
                self.assertTrue(decoded['readback_valid'])

    def test_gpu_and_old_journal_reads_are_reads(self):
        cpu = Reader(BINARY, 'cleared')
        cpu.run()
        for write, address, _value in cpu.accesses:
            if write:
                self.assertTrue(JOURNAL <= address < JOURNAL + 256)

    def test_real_binary_and_deterministic_rerun(self):
        self.assertEqual(hashlib.sha256(BINARY).hexdigest(), BINARY_SHA)
        manifest = json.loads((RB / 'build_01' / 'manifest.json').read_text())
        self.assertEqual(manifest['code_bytes'], len(BINARY))
        self.assertEqual(manifest['gpu_commands'], 0)
        self.assertEqual(manifest['ddr_writes'], 0)
        first = Reader(BINARY, 'cleared').run()
        second = Reader(BINARY, 'cleared').run()
        self.assertEqual(first[:64], second[:64])


class CandidateHardenedDecoder(unittest.TestCase):
    """The owned hardened candidate microdma_decode_v2.decode -- the only place
    the reviewer-confirmed bounded checks are implemented; the protected
    original and all payloads stay read-only.

    Contract (protected test_md12_expected.py): a healthy completed payload
    carries word24=1 (microdma.S never clears command_words_remaining after the
    8 stores; my earlier fixture value 0 was a rejected inference), word25=0x1200007c
    (last of the 32 compared DDR words) and zero words 26/27/31; every single
    deviation must be refused on a completed phase10/result1 claim.
    """

    EXPECTED_ISSUE = {24: 'command_words_remaining_not_one',
                      25: 'last_ddr_address_wrong_extent',
                      26: 'reserved_words_nonzero',
                      27: 'reserved_words_nonzero',
                      31: 'reserved_words_nonzero'}

    def test_healthy_completed_claim_accepted(self):
        words = healthy_completed_claim()
        decoded = decode_md12_v2(struct.pack('<128I', *words))
        self.assertTrue(decoded['passed'],
                        f'healthy payload rejected: {decoded["issues"]}')
        self.assertEqual(decoded['issues'], [])
        self.assertEqual(decoded['header']['command_words_remaining'], 1)
        self.assertEqual(decoded['header']['last_ddr_address'], 0x1200007c)

    def test_every_previously_unchecked_word_mutation_rejected(self):
        for index, planted in UNCHECKED_WORD_MUTATIONS:
            with self.subTest(index=index, planted=planted):
                words = healthy_completed_claim()
                words[index] = planted
                decoded = decode_md12_v2(struct.pack('<128I', *words))
                self.assertFalse(decoded['passed'],
                                 f'completion claim with word[{index}]={planted:#x} must be refused')
                self.assertIn(self.EXPECTED_ISSUE[index], decoded['issues'])

    def test_single_bit_reserved_corruption_rejected(self):
        for index in (26, 27, 31):                        # one-bit real-world fault shape
            with self.subTest(index=index):
                words = healthy_completed_claim()
                words[index] ^= 1
                decoded = decode_md12_v2(struct.pack('<128I', *words))
                self.assertFalse(decoded['passed'],
                                 f'one flipped bit in reserved word[{index}] silently accepted')
                self.assertIn('reserved_words_nonzero', decoded['issues'])

    def test_real_incomplete_journals_unchanged_under_candidate(self):
        """run02/run03 stay genuinely incomplete under the candidate: the bounded
        checks add no invented issues (their words 24..31 already match the
        healthy format, and phase!=10/result!=1 keeps the completion gate off).
        The journal-format laxity did NOT cause the board failure."""
        for run, journal in (('run02', RUN02_JOURNAL), ('run03', RUN03_JOURNAL)):
            with self.subTest(run=run):
                words = list(struct.unpack('<128I', journal))
                self.assertEqual(words[24:32], [1, 0x1200007c, 0, 0, 32, 32, 0, 0])
                decoded = decode_md12_v2(journal)
                self.assertFalse(decoded['passed'])
                for issue in ('clear_wait_or_error', 'not_final_phase',
                              'incomplete_cpu_images', 'clear_image_mismatch'):
                    self.assertIn(issue, decoded['issues'])
                for added in ('reserved_words_nonzero', 'command_words_remaining_not_one',
                              'last_ddr_address_wrong_extent'):
                    self.assertNotIn(added, decoded['issues'])


class OriginalDecoderLaxityObservation(unittest.TestCase):
    """Preserved reproduction of the protected original decoder's confirmed
    laxity -- now as an EXPECTED observation rather than an intentionally red
    test.  REVIEW_FINDINGS.md confirmed microdma_r1/decode_journal.py ignores
    words 24/25/26/27/31; the original file and every payload are read-only, so
    the fix lives in owned microdma_decode_v2.py only.  Nothing is weakened or
    hidden: this class documents the exact defect behavior (original accepts
    each corrupted completion claim) while CandidateHardenedDecoder shows the
    candidate refusing the same claims."""

    def test_original_accepts_healthy_completed_claim(self):
        decoded = decode_md12(struct.pack('<128I', *healthy_completed_claim()))
        self.assertTrue(decoded['passed'])

    def test_original_silently_accepts_every_corrupted_word(self):
        """Expected observation: the protected original passes every mutation the
        candidate refuses.  If this ever flips, the protected file changed --
        re-run the review before trusting this suite."""
        for index, planted in UNCHECKED_WORD_MUTATIONS:
            with self.subTest(index=index, planted=planted):
                words = healthy_completed_claim()
                words[index] = planted
                decoded = decode_md12(struct.pack('<128I', *words))
                self.assertTrue(decoded['passed'],
                                'observation changed: protected decode_journal.py now reacts to '
                                f'word[{index}]={planted:#x}; update ANALYSIS.md first')

    def test_candidate_rejects_exactly_what_original_accepts(self):
        words = healthy_completed_claim()
        self.assertTrue(decode_md12(struct.pack('<128I', *words))['passed'])
        self.assertTrue(decode_md12_v2(struct.pack('<128I', *words))['passed'])
        for index, planted in ((24, 0), (24, 2), (25, 0x12000080), (26, 1),
                               (27, 1), (31, 1)):
            corrupted = list(words)
            corrupted[index] = planted
            original = decode_md12(struct.pack('<128I', *corrupted))
            candidate = decode_md12_v2(struct.pack('<128I', *corrupted))
            with self.subTest(index=index, planted=planted):
                self.assertTrue(original['passed'])       # confirmed laxity, still true
                self.assertFalse(candidate['passed'])     # bounded fix, owned candidate only


if __name__ == '__main__':
    unittest.main(verbosity=2)