#!/usr/bin/env python3
"""Local-only tests: no sysfs, USB device or hardware lock is accessed."""
import ctypes
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('ep0', HERE / 'read_ep0_startup.py')
ep0 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ep0)


def reply(nibble=15):
    return struct.pack('<8I', 1, 2, 3, 0x00050004, (nibble << 28) | 0x01234567,
                       0xd1123456, 6, 7)


class TestReader(unittest.TestCase):
    def test_decode_all_bit_combinations(self):
        for nibble in range(16):
            decoded = ep0.decode(reply(nibble))
            self.assertEqual(decoded['board_status_nibble'], nibble)
            for bit, name in enumerate(('ae350_por_hw_rstn', 'pll_ddr_filtered_lock',
                                       'ddr3_stop_enclk2', 'pll_ae350_filtered_lock')):
                self.assertEqual(decoded[name], (nibble >> bit) & 1)

    def test_refuse_signature_and_lengths(self):
        for n in (0, 7, 31, 33, 64):
            with self.assertRaises(ValueError):
                ep0.decode(bytes(n))
        bad = bytearray(reply()); bad[23] = 0
        with self.assertRaises(ValueError):
            ep0.decode(bad)

    def test_only_in_request_and_short_timeout(self):
        calls = []
        def fake(fd, number, data):
            req = ep0.Control.from_buffer_copy(data)
            calls.append((fd, number, req.request_type, req.request, req.value,
                          req.index, req.length, req.timeout))
            ctypes.memmove(req.data, reply(9), 32)
            return 32
        self.assertEqual(ep0.read_once(99, ioctl=fake)['board_status_nibble'], 9)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][2:], (0xa0, 0x21, 0xd1a6, 0, 32, 1000))
        with self.assertRaises(ValueError):
            ep0.read_once(99, ioctl=lambda *args: 31)

    def test_exact_port_identity_and_debugger(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def put(name, values):
                target = root / name; target.mkdir()
                for key, value in values.items():
                    (target / key).write_text(value)
            put('3-4.3', dict(ep0.IDENTITY, busnum='3', devnum='42'))
            put('3-4.1', dict(idVendor='0403', idProduct='6010', serial='2025041420',
                             product='USB Debugger', busnum='3', devnum='28'))
            self.assertEqual(ep0.select_device('3-4.3', '3:42', root)['serial'], 'NEO00001')
            with self.assertRaises(ValueError):
                ep0.select_device('3-4.3', '3:43', root)
            (root/'3-4.3'/'serial').write_text('11252024')
            with self.assertRaises(ValueError):
                ep0.select_device('3-4.3', '3:42', root)
            (root/'3-4.3'/'serial').write_text('NEO00001')
            put('3-5', dict(ep0.IDENTITY, busnum='3', devnum='43'))
            with self.assertRaises(ValueError):
                ep0.select_device('3-4.3', '3:42', root)
            with self.assertRaises(ValueError):
                ep0.select_device('../3-4.3', '3:42', root)

    def test_check_only_does_not_discover_or_open_hardware(self):
        with (patch.object(ep0, 'select_device', side_effect=AssertionError('hardware discovery')),
             patch.object(ep0, 'collect', side_effect=AssertionError('USB access')),
             patch.object(ep0, 'local_preflight', return_value={'proof': 'mock'})):
            self.assertEqual(ep0.main(['--check-only']), 0)


if __name__ == '__main__':
    unittest.main()
