#!/usr/bin/env python3
"""Small adversarial tests, all local files/mocks; never access USB or JTAG."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import offline
import target_guard

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
G22 = ROOT / 'tang/impl/gpu_geometry_g22r0/impl/pnr/console_gpu_geometry_g22r0.fs'
G22_SHA = 'fbbea9c357d0c4d5b33c3c4a7e54f9ed0ff8e31cc3fad1ac9dc1771f8e8cba5f'


class OfflineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Path(self.tmp.name)
        self.cap = 3 * 65536
        self.backup = bytes(range(256)) * (self.cap // 256)
        self.payload = b'new!' * 16385
        for name, data in [('a', self.backup), ('b', self.backup), ('payload', self.payload)]:
            (self.p / name).write_bytes(data)

    def prepare(self):
        return offline.prepare(self.p/'payload', self.p/'a', self.p/'b', self.cap, self.p/'prepared')

    def test_exact_preservation_and_full_readback(self):
        report = self.prepare()
        image = (self.p/'prepared/program.bin').read_bytes()
        self.assertEqual(len(image), 131072)
        self.assertEqual(image[:len(self.payload)], self.payload)
        self.assertEqual(image[len(self.payload):], self.backup[len(self.payload):131072])
        expected = self.payload + self.backup[len(self.payload):]
        (self.p/'after').write_bytes(expected)
        result = offline.verify(self.p/'prepared/plan.json', self.p/'after')
        self.assertTrue(result['full_readback_matches'])
        self.assertFalse(result['hardware_boot_tested'])
        self.assertEqual(report['expected_full_sha256'], hashlib.sha256(expected).hexdigest())

    def test_corruption_outside_programmed_region_rejected(self):
        self.prepare()
        after = bytearray(self.payload + self.backup[len(self.payload):])
        after[-1] ^= 1
        (self.p/'after').write_bytes(after)
        with self.assertRaises(ValueError):
            offline.verify(self.p/'prepared/plan.json', self.p/'after')

    def test_short_or_inconsistent_backup(self):
        for value in (self.backup[:-1], b'', b'x' * self.cap):
            (self.p/'b').write_bytes(value)
            with self.assertRaises(ValueError): self.prepare()
        self.assertFalse((self.p/'prepared').exists())

    def test_hardlink_is_not_independent_dump(self):
        (self.p/'b').unlink()
        (self.p/'b').hardlink_to(self.p/'a')
        with self.assertRaises(ValueError): self.prepare()

    def test_symlink_rejected(self):
        (self.p/'b').unlink()
        (self.p/'b').symlink_to(self.p/'a')
        with self.assertRaises(ValueError): self.prepare()

    def test_capacity_and_payload_bounds(self):
        for capacity in (0, 65537, 65*1024*1024):
            with self.assertRaises(ValueError):
                offline.prepare(self.p/'payload', self.p/'a', self.p/'b', capacity, self.p/'prepared')
        (self.p/'payload').write_bytes(b'x' * (self.cap+1))
        with self.assertRaises(ValueError): self.prepare()

    def test_no_overwrite(self):
        self.prepare()
        before = (self.p/'prepared/program.bin').read_bytes()
        with self.assertRaises(FileExistsError): self.prepare()
        self.assertEqual(before, (self.p/'prepared/program.bin').read_bytes())

    def test_serial_and_commands_always_new_board(self):
        old = dict(idVendor='0403', idProduct='6010', serial='2023112818')
        new = dict(old, serial='2025071717')
        self.assertIs(target_guard.select_target([old, new]), new)
        for devices in ([old], [new,new], []):
            with self.assertRaises(ValueError): target_guard.select_target(devices)
        for action, kwargs in [('detect', {}), ('dump', dict(output='new.bin', size=131072)),
                               ('program', dict(image='program.bin'))]:
            cmd = target_guard.command('/reviewed/tool', action, **kwargs)
            self.assertEqual(cmd[1:3], ['--usb-serial-num', '2025071717'])
            self.assertNotIn('2023112818', cmd)
            self.assertNotIn('--bulk-erase', cmd)
            self.assertNotIn('--unprotect-flash', cmd)
        with self.assertRaises(ValueError): target_guard.command('tool', 'dump', output='x', size=0)

    def test_wrong_host_guard_before_hardware(self):
        with patch.object(target_guard.socket, 'gethostname', return_value='elsewhere'), \
             patch.object(target_guard.subprocess, 'run', side_effect=AssertionError('must not run')):
            with self.assertRaises(ValueError):
                with target_guard.guarded_target('x', 'y', 'z', 's', runtime='r', runtime_sha='h'):
                    self.fail('Guard should reject')

    def test_upstream_exporter_exact_g22_and_exclusive_output(self):
        text = G22.read_bytes()
        self.assertEqual(hashlib.sha256(text).hexdigest(), G22_SHA)
        # Independent lexical conversion checks every upstream-emitted byte.
        raw = bytearray()
        for line in text.decode('ascii').splitlines():
            if not line or line.startswith('/'): continue
            self.assertEqual(set(line) - set('01'), set())
            self.assertEqual(len(line) % 8, 0)
            raw.extend(int(line[i:i+8], 2) for i in range(0, len(line), 8))
        out = self.p/'g22.bin'
        proc = subprocess.run([str(HERE/'export_fs'), str(G22), str(out)], capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out.read_bytes(), raw)
        # The exact RawParser(false) used by programExtFlash must preserve
        # every byte, including the suffix retained from the old sector.
        program = self.p/'program.bin'
        program.write_bytes(raw + bytes(range(256)))
        check = subprocess.run([str(HERE/'raw_route_check'), str(G22), str(program)],
                               capture_output=True)
        self.assertEqual(check.returncode, 0, check.stderr)
        damaged = bytearray(program.read_bytes()); damaged[19] ^= 1
        program.write_bytes(damaged)
        check = subprocess.run([str(HERE/'raw_route_check'), str(G22), str(program)],
                               capture_output=True)
        self.assertNotEqual(check.returncode, 0)
        proc = subprocess.run([str(HERE/'export_fs'), str(G22), str(out)], capture_output=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(out.read_bytes(), raw)

    def test_invalid_fs_not_silently_parsed_as_zero(self):
        (self.p/'bad.fs').write_text('0000x000\n')
        proc = subprocess.run([str(HERE/'export_fs'), str(self.p/'bad.fs'), str(self.p/'bad.bin')],
                              capture_output=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse((self.p/'bad.bin').exists())


if __name__ == '__main__':
    unittest.main()
