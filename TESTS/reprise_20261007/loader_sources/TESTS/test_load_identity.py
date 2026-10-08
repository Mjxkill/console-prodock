#!/usr/bin/env python3
"""Identification du firmware derrière les journaux USB encore en attente."""
import itertools
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from load_ilm import identify_console


class SerialQueue:
    def __init__(self, data):
        self.data = data
        self.writes = []

    def reset_input_buffer(self):
        # Les octets encore dans le FPGA survivent à la purge du tampon PC.
        pass

    def flush(self):
        pass

    def write(self, data):
        self.writes.append(data)

    def read(self, size):
        data, self.data = self.data[:size], self.data[size:]
        return data


class IdentityTests(unittest.TestCase):
    def test_banner_after_large_queue(self):
        logs = b'V1 BENCH scene=0 frames=120 underflows=0\r\n' * 400
        uart = SerialQueue(logs + b'MegaPro GPU V1\r\n')
        answer, pause = identify_console(uart)
        self.assertEqual(pause, b'c')
        self.assertTrue(answer.endswith(b'MegaPro GPU V1\r\n'))
        self.assertEqual(uart.writes, [b'?'])

    def test_application_pause_commands(self):
        for banner, expected in ((b'USBDISK R1 CDC + MSC', b'q'),
                                 (b'LUMA R4', b'P'), (b'ORBITAL R6', b'P')):
            with self.subTest(banner=banner):
                self.assertEqual(identify_console(SerialQueue(banner+b'\r\n'))[1], expected)

    def test_unknown_or_incomplete_banner_never_guesses(self):
        for data in (b'V1 BENCH underflows=0\n', b'MegaPro GPU'):
            uart = SerialQueue(data)
            with patch('load_ilm.time.monotonic', side_effect=itertools.count()):
                with self.assertRaises(RuntimeError):
                    identify_console(uart)
            self.assertEqual(uart.writes, [b'?'])


if __name__ == '__main__':
    unittest.main()
