"""Adversarial tests for protected RJC1 decoder and synthetic fixtures."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from rjc_decode import (
    InvalidCapture,
    MASK32,
    decode_capture,
    decode_record,
    load_strict,
)
from fixtures import capture, pair, mutate_pair

CHILD_FLAGS = 1 | 2 | 4 | 8 | 16 | 32 | 128 | 512 | 2048
CHILD_LIVE = (1 << 6) | (1 << 7)
KINDS = ("child", "header", "target", "manual", "parent_other", "child_other")


class TestAdversarial(unittest.TestCase):
    def test_all_six_fixture_kinds_pass(self):
        for kind in KINDS:
            result = decode_capture(capture(kind))
            self.assertTrue(result["coherent_record"], kind)
            self.assertEqual(result["format"], "RJC1")

    def test_stale_prime_not_discarded_rejected(self):
        bad = capture("child")
        bad["prime"]["discarded"] = False
        with self.assertRaises(InvalidCapture) as context:
            decode_capture(bad)
        self.assertIn("prime", str(context.exception))

    def test_stale_prime_wrong_sequence_rejected(self):
        bad = capture("child")
        bad["prime"]["gpu_sequence_after"] = 99
        with self.assertRaises(InvalidCapture) as context:
            decode_capture(bad)
        self.assertIn("prime", str(context.exception))

    def test_bank_tag_mismatch_rejected(self):
        banks = pair("child")
        bad = mutate_pair(banks, "tag1", 0)
        with self.assertRaises(InvalidCapture) as context:
            decode_record(bad[0], bad[1], expected_epoch=1)
        self.assertIn("bank tag", str(context.exception))

    def test_check_generation_mismatch_rejected(self):
        banks = pair("child")
        bad = mutate_pair(banks, "check_generation", 99)
        with self.assertRaises(InvalidCapture) as context:
            decode_record(bad[0], bad[1], expected_epoch=1)
        self.assertIn("CHECK belongs", str(context.exception))

    def test_command_generation_zero_rejected(self):
        banks = pair("child")
        bad = mutate_pair(banks, "command_generation", 0)
        with self.assertRaises(InvalidCapture) as context:
            decode_record(bad[0], bad[1], expected_epoch=1)
        self.assertIn("missing command generation", str(context.exception))

    def test_manual_stale_check_fields_rejected(self):
        banks = pair("manual")
        bad = mutate_pair(banks, "check_generation", 7)
        with self.assertRaises(InvalidCapture) as context:
            decode_record(bad[0], bad[1], expected_epoch=1)
        self.assertIn("stale CHECK fields", str(context.exception))

    def test_status_before_mismatch_rejected(self):
        bad = capture("child")
        bad["rounds"][0]["gpu"]["status_before"] = 7
        with self.assertRaises(InvalidCapture) as context:
            decode_capture(bad)
        self.assertIn("transport not ready", str(context.exception))

    def test_transport_sequence_mismatch_rejected(self):
        bad = capture("child")
        bad["rounds"][0]["gpu"]["sequence_before"] = 999
        with self.assertRaises(InvalidCapture) as context:
            decode_capture(bad)
        self.assertIn("transport sequence changed", str(context.exception))

    def test_round_payload_differs_rejected(self):
        good = capture("child")
        bad = copy.deepcopy(good)
        bad["rounds"][1]["gpu"]["words"][0] ^= 1
        with self.assertRaises(InvalidCapture) as context:
            decode_capture(bad)
        self.assertIn("two reads differ", str(context.exception))

    def test_unexpected_capture_key_rejected(self):
        bad = capture("child")
        bad["unexpected"] = 1
        with self.assertRaises(InvalidCapture) as context:
            decode_capture(bad)
        self.assertIn("schema: capture", str(context.exception))

    def test_unexpected_reading_key_rejected(self):
        bad = capture("child")
        bad["rounds"][0]["gpu"]["unexpected"] = 1
        with self.assertRaises(InvalidCapture) as context:
            decode_capture(bad)
        self.assertIn("schema: gpu round0", str(context.exception))

    def test_bool_integer_rejected(self):
        bad = capture("child")
        bad["arm_before"] = True
        with self.assertRaises(InvalidCapture) as context:
            decode_capture(bad)
        self.assertIn("invalid integer", str(context.exception))

    def test_arm_wrap_rejected(self):
        bad = capture("child")
        bad["arm_before"] = 65535
        with self.assertRaises(InvalidCapture) as context:
            decode_capture(bad)
        self.assertIn("ARM stale/wrapped", str(context.exception))

    def test_arm_after_mismatch_rejected(self):
        bad = capture("child")
        bad["arm_after"] = 9
        with self.assertRaises(InvalidCapture) as context:
            decode_capture(bad)
        self.assertIn("ARM stale/wrapped", str(context.exception))

    def test_counter_wrap_rejected(self):
        bad = capture("child")
        bad["sequences_before"]["gpu"] = MASK32 - 1
        with self.assertRaises(InvalidCapture) as context:
            decode_capture(bad)
        self.assertIn("transport sequence wrap", str(context.exception))

    def test_packet_provenance_child_copy(self):
        result = decode_capture(capture("child"))
        self.assertEqual(result["packet_provenance"], "COPY_AT_CHECK")
        self.assertTrue(result["flags"]["associated"])

    def test_packet_provenance_manual_parent(self):
        result = decode_capture(capture("manual"))
        self.assertEqual(result["packet_provenance"], "PARENT_AT_FREEZE")
        self.assertFalse(result["flags"]["associated"])

    def test_parent_header_mismatch_rejected(self):
        banks = pair("manual")
        bad = copy.deepcopy(banks)
        bad[0][9] ^= 1
        with self.assertRaises(InvalidCapture) as context:
            decode_record(bad[0], bad[1], expected_epoch=1)
        self.assertIn("parent packet/header mismatch", str(context.exception))

    def test_reset_seen_rejected(self):
        banks = pair("child")
        bad = mutate_pair(banks, "flags", CHILD_FLAGS | (1 << 8))
        with self.assertRaises(InvalidCapture) as context:
            decode_record(bad[0], bad[1], expected_epoch=1)
        self.assertIn("capture reset/anomaly/overflow/DQ error", str(context.exception))

    def test_anomaly_rejected(self):
        banks = pair("child")
        bad = mutate_pair(banks, "flags", CHILD_FLAGS | (1 << 10))
        with self.assertRaises(InvalidCapture) as context:
            decode_record(bad[0], bad[1], expected_epoch=1)
        self.assertIn("capture reset/anomaly/overflow/DQ error", str(context.exception))

    def test_dq_error_rejected(self):
        banks = pair("child")
        bad = mutate_pair(banks, "flags", CHILD_FLAGS | (1 << 12))
        with self.assertRaises(InvalidCapture) as context:
            decode_record(bad[0], bad[1], expected_epoch=1)
        self.assertIn("capture reset/anomaly/overflow/DQ error", str(context.exception))

    def test_freeze_pending_rejected(self):
        banks = pair("child")
        bad = mutate_pair(banks, "live", CHILD_LIVE | (1 << 11))
        with self.assertRaises(InvalidCapture) as context:
            decode_record(bad[0], bad[1], expected_epoch=1)
        self.assertIn("freeze pending", str(context.exception))

    def test_engine_reset_rejected(self):
        banks = pair("child")
        bad = mutate_pair(banks, "live", CHILD_LIVE | (1 << 8))
        with self.assertRaises(InvalidCapture) as context:
            decode_record(bad[0], bad[1], expected_epoch=1)
        self.assertIn("engine reset at decision", str(context.exception))

    def test_parent_state_not_one_hot_rejected(self):
        banks = pair("child")
        bad = mutate_pair(banks, "parent_state", 3)
        with self.assertRaises(InvalidCapture) as context:
            decode_record(bad[0], bad[1], expected_epoch=1)
        self.assertIn("parent state not one-hot", str(context.exception))

    def test_src_end_overflow_reported(self):
        banks = pair("child")
        bad = mutate_pair(banks, "src_end", 0x50000000)
        result = decode_record(bad[0], bad[1], expected_epoch=1)
        self.assertTrue(result["coherent_record"])
        overflow = result["predicates"]["conditions"][2]["source_end_overflow"]
        self.assertTrue(overflow)

    def test_reason_contradiction_rejected(self):
        banks = pair("child")
        bad = mutate_pair(banks, "reason", 4)
        with self.assertRaises(InvalidCapture) as context:
            decode_record(bad[0], bad[1], expected_epoch=1)
        self.assertIn("reason contradicts", str(context.exception))

    def test_header_priority_over_target_rejected(self):
        banks = pair("header")
        bad = mutate_pair(banks, "reason", 2)
        with self.assertRaises(InvalidCapture) as context:
            decode_record(bad[0], bad[1], expected_epoch=1)
        self.assertIn("reason contradicts", str(context.exception))

    def test_partial_descriptor_association_rejected(self):
        banks = pair("child")
        bad = mutate_pair(banks, "flags", CHILD_FLAGS & ~4)
        with self.assertRaises(InvalidCapture) as context:
            decode_record(bad[0], bad[1], expected_epoch=1)
        self.assertIn("partial CHECK association", str(context.exception))

    def test_predicate_mismatch_reported(self):
        banks = pair("child")
        bad = mutate_pair(banks, "descriptor_d", 5)
        bad = mutate_pair(bad, "descriptor_q", 5)
        result = decode_record(bad[0], bad[1], expected_epoch=1)
        self.assertTrue(result["coherent_record"])
        self.assertFalse(result["predicates"]["matches_actual_D"])
        self.assertFalse(result["physical_cause_established"])
        self.assertFalse(result["gpu_or_ddr_qualified"])

    def test_physical_cause_never_established(self):
        for kind in KINDS:
            result = decode_capture(capture(kind))
            self.assertFalse(result["physical_cause_established"], kind)
            self.assertFalse(result["gpu_or_ddr_qualified"], kind)

    def test_transcript_freshness_not_established(self):
        for kind in KINDS:
            result = decode_capture(capture(kind))
            self.assertTrue(result["transcript_freshness_checks_passed"], kind)
            self.assertFalse(result["freshness_established"], kind)

    def test_descriptor_flags_coherent_zero_accepted(self):
        result = decode_record(*pair("manual"), expected_epoch=1)
        self.assertFalse(result["flags"]["associated"])
        self.assertFalse(result["flags"]["packet_child"])

    def test_load_strict_duplicate_key_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.json"
            path.write_text('{"a": 1, "a": 2}')
            with self.assertRaises(InvalidCapture):
                load_strict(path)

    def test_load_strict_nonfinite_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.json"
            path.write_text('{"a": NaN}')
            with self.assertRaises(InvalidCapture):
                load_strict(path)


if __name__ == "__main__":
    unittest.main()
