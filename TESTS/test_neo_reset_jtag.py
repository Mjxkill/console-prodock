"""Reject stale, torn or incomplete diagnostic snapshots before interpretation."""
import sys
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/neo')]
from neo.run_reset_probe import decode_jtag


def frame(toggle=1,ready=1,ack=None,payload=None):
    if payload is None:payload=int('52510f0300000014000000000123456789abcdef',16)
    if ack is None:ack=toggle
    return (toggle<<162)|(ack<<161)|(ready<<160)|payload


class SnapshotTests(unittest.TestCase):
    def test_complete_alternating_observations(self):
        frames=decode_jtag(f'RESET_JTAG 0 {frame():x}\nRESET_JTAG 1 {frame(0):x}\n')
        self.assertEqual(len(frames),2)
        self.assertEqual(frames[0]['epoch'],20)
        self.assertEqual(frames[0]['copies'],15)

    def test_busy_or_wrong_ack_is_not_a_zero_error_result(self):
        for value in (frame(ready=0),frame(ack=0),frame()|(1<<163)):
            with self.assertRaises(ValueError):decode_jtag(f'RESET_JTAG 0 {value:x}\n')

    def test_old_frame_is_rejected(self):
        with self.assertRaises(ValueError):
            decode_jtag(f'RESET_JTAG 0 {frame():x}\nRESET_JTAG 1 {frame():x}\n')

    def test_wrong_magic_rejected_and_empty_not_pass(self):
        with self.assertRaises(ValueError):decode_jtag(f'RESET_JTAG 0 {frame(payload=0):x}\n')
        self.assertEqual(decode_jtag('JTAG scan failed\n'),[])


if __name__=='__main__':unittest.main()
