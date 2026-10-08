#!/usr/bin/env python3
"""Identification du firmware derrière les journaux USB encore en attente."""
import itertools
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from load_ilm import identify_console, quiesce_console, require


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
    def test_checks_survive_optimization(self):
        require(True,'witness')
        with self.assertRaisesRegex(RuntimeError,'rejected'):require(False,'rejected')

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

    def test_pause_acknowledgements(self):
        for pause, ack in ((b'P', b'ORBITAL PAUSED'), (b'P', b'LUMA PAUSED'),
                           (b'c', b'RASTER PAUSED'),
                           (b'q', b'USBDISK MEDIA=DDR SERVING=0 ONLINE=1')):
            with self.subTest(pause=pause,ack=ack):
                uart=SerialQueue(b'old log\n'+ack+b'\r\n')
                self.assertIn(ack,quiesce_console(uart,pause))
                self.assertEqual(uart.writes[0],pause)

    def test_ae350_crlfcr_pause_acknowledgement(self):
        for pause,ack in ((b'q',b'USBDISK MEDIA=DDR SERVING=0 ONLINE=1'),
                          (b'P',b'ORBITAL PAUSED'), (b'c',b'RASTER PAUSED')):
            with self.subTest(pause=pause):
                uart=SerialQueue(b'previous line\r\n\r'+ack+b'\r\n\r')
                self.assertIn(ack,quiesce_console(uart,pause))

    def test_missing_or_partial_ack_refused(self):
        for pause, data in ((b'P', b'ORBITAL PAUSED'), (b'P', b'ORBITAL frame=10 run=1\n'),
                            (b'q', b'USBDISK MEDIA=DDR SERVING=1\n'),
                            (b'q', b'USBDISK MEDIA=DDR SERVING=01\n'),
                            (b'q', b'noise USBDISK MEDIA=DDR SERVING=0\n'),
                            (b'q', b'SERVING=0\n'), (b'c', b'')):
            with self.subTest(pause=pause,data=data):
                with patch('load_ilm.time.monotonic', side_effect=itertools.count()):
                    with self.assertRaisesRegex(RuntimeError,'Arrêt non acquitté'):
                        quiesce_console(SerialQueue(data),pause)


if __name__ == '__main__':
    unittest.main()
