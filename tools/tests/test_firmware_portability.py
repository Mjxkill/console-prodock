#!/usr/bin/env python3
"""Offline contracts for portable firmware support; no SDK or target required.

The optional historical generator comparison uses an explicitly supplied local
path, never a sibling repository hidden in the test or production build.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "fw_console/support/itcm_init.py"
REFERENCE = None
SIZES = (0, 1, 2, 3, 4, 5, 255, 65535, 65536)


def run(args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, **kwargs)


class FirmwareSupport(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="console-fw-test-")
        self.addCleanup(self.directory.cleanup)
        self.tmp = Path(self.directory.name)

    def generate(self, size):
        data = bytes((i * 19 + 7) & 255 for i in range(size))
        source = self.tmp / "input.bin"
        source.write_bytes(data)
        output = self.tmp / "lanes"
        result = run([sys.executable, str(GENERATOR), str(source), str(output)])
        return data, source, output, result

    def test_lane_bytes_padding_and_crlf(self):
        for size in SIZES:
            with self.subTest(size=size):
                data, _, output, result = self.generate(size)
                self.assertEqual(result.returncode, 0, result.stderr)
                lanes = [(output / f"itcm{i}").read_bytes() for i in range(4)]
                expected_words = (size + 3) // 4
                self.assertTrue(all(len(x) == expected_words * 4 for x in lanes))
                decoded = []
                for lane in lanes:
                    lines = lane.split(b"\r\n")
                    self.assertEqual(lines[-1], b"")
                    self.assertTrue(all(len(x) == 2 for x in lines[:-1]))
                    decoded.append([int(x, 16) for x in lines[:-1]])
                restored = bytes(decoded[lane][word]
                                 for word in range(expected_words) for lane in range(4))
                self.assertEqual(restored[:size], data)
                self.assertEqual(restored[size:], b"\0" * (-size % 4))

    def test_oversize_preserves_existing_output(self):
        output = self.tmp / "lanes"
        output.mkdir()
        for lane in range(4):
            (output / f"itcm{lane}").write_bytes(b"unchanged")
        _, _, _, result = self.generate(65537)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exceeds 64 KiB", result.stderr)
        self.assertTrue(all((output / f"itcm{i}").read_bytes() == b"unchanged"
                            for i in range(4)))

    def test_missing_input_fails(self):
        result = run([sys.executable, str(GENERATOR), str(self.tmp / "absent"),
                      str(self.tmp / "lanes")])
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.tmp / "lanes").exists())

    def cloned_make(self, *args, sdk=True):
        clone = self.tmp / "independent-checkout/fw_console"
        clone.mkdir(parents=True, exist_ok=True)
        for name in ("Makefile", "toolchain.mk"):
            shutil.copy2(ROOT / "fw_console" / name, clone / name)
        fake = self.tmp / "sdk"
        if sdk:
            (fake / "bsp/ae350").mkdir(parents=True, exist_ok=True)
            (fake / "bsp/ae350/start.S").touch()
        # An empty HOME proves no installed neighbouring project is required.
        env = dict(os.environ, HOME=str(self.tmp / "empty-home"))
        env.pop("TC", None)
        env.pop("CROSS_COMPILE", None)
        return run(["make", "--no-print-directory", "-s", "-C", str(clone),
                    f"AE350_SDK={fake}", *args], env=env)

    def test_print_nm_prefix_contract(self):
        for args, expected in [([], "riscv-none-elf-nm"),
                               (["CROSS_COMPILE=/opt/rv/bin/rv-"], "/opt/rv/bin/rv-nm"),
                               (["CROSS_COMPILE=ignored-", "TC=/opt/legacy-"],
                                "/opt/legacy-nm")]:
            with self.subTest(args=args):
                result = self.cloned_make("print-nm", *args, sdk=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), expected)

    def test_missing_sdk_is_actionable(self):
        result = self.cloned_make("check-config", sdk=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Set AE350_SDK", result.stderr)

    def test_missing_toolchain_is_actionable(self):
        result = self.cloned_make("check-config", "CROSS_COMPILE=not-a-toolchain-")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Set CROSS_COMPILE (or TC)", result.stderr)

    def test_four_lanes_are_grouped_outputs(self):
        fw = self.tmp / "fw"
        fw.mkdir()
        shutil.copy2(ROOT / "fw_console/Makefile", fw / "Makefile")
        shutil.copy2(ROOT / "fw_console/toolchain.mk", fw / "toolchain.mk")
        shutil.copytree(ROOT / "fw_console/support", fw / "support")
        out = fw / "build"
        out.mkdir()
        (out / "console_test.bin").write_bytes(bytes(range(16)))
        # Stop make before firmware compilation: the image is already an input.
        cmd = ["make", "-s", "-C", str(fw), "-o", "build/console_test.bin",
               "build/itcm/itcm1"]
        result = run(cmd)
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = (out / "itcm/itcm1").read_bytes()
        (out / "itcm/itcm1").unlink()
        result = run(cmd)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((out / "itcm/itcm1").read_bytes(), expected)

    def test_historical_generator_exact(self):
        if REFERENCE is None:
            self.skipTest("optional --reference-generator not provided")
        for size in SIZES:
            with self.subTest(size=size):
                _, source, output, result = self.generate(size)
                refout = self.tmp / "reference"
                ref = run([sys.executable, str(REFERENCE), str(source), str(refout)])
                self.assertEqual((result.returncode, ref.returncode), (0, 0))
                for lane in range(4):
                    self.assertEqual((output / f"itcm{lane}").read_bytes(),
                                     (refout / f"itcm{lane}").read_bytes())


def main():
    global REFERENCE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-generator", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    REFERENCE = args.reference_generator
    started = time.monotonic()
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(FirmwareSupport))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({
            "passed": result.wasSuccessful(), "tests_run": result.testsRun,
            "failures": len(result.failures), "errors": len(result.errors),
            "skipped": len(result.skipped), "duration_seconds": time.monotonic() - started,
            "generator_sha256": hashlib.sha256(GENERATOR.read_bytes()).hexdigest(),
            "historical_generator_sha256": hashlib.sha256(REFERENCE.read_bytes()).hexdigest()
            if REFERENCE else None}, indent=2) + "\n")
    raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
