"""A stopped hardware probe must retain earlier evidence and report failure."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools/neo'))
import probe_memory


class ProbeEvidenceTests(unittest.TestCase):
    def run_probe(self, failure):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        previous = root/'previous'
        previous.mkdir()
        (previous/'result.json').write_text('{"passed": false}')
        out = root/'probe'

        def captured_openocd(command, **kwargs):
            self.assertEqual(command[0], '/usr/local/bin/openocd')
            if failure == 'guard':
                raise subprocess.CalledProcessError(1, command)
            expected = (out/'pattern.bin').read_bytes()
            first = bytearray(expected)
            if failure in ('gpu','gpu_step'):
                first[9] ^= 0x40
            (out/'read1.bin').write_bytes(first)
            (out/'read2.bin').write_bytes(expected)
            (out/'ilm_read.bin').write_bytes(expected)
            if failure == 'gpu_step':
                script=(out/'probe.tcl').read_text()
                self.assertEqual(script.count('write_memory 0xe9001010 32'),8)
                self.assertNotIn('gpu_ffff.bin',script)
                kwargs['stdout'].write('NEO_GPU_WORD_0 0x1 0x0 0x0\nNEO_GPU_WORD_7 0x0 0x0 0x0\n')
            if failure in ('gpu','gpu_step'):
                kwargs['stdout'].write('GPU command did not complete\n')
                raise subprocess.CalledProcessError(1, command)
            return subprocess.CompletedProcess(command, 0)

        argv = ['probe_memory.py', '--failed-load', str(previous), '--out', str(out)]
        if failure in ('gpu','gpu_step'):
            argv.append('--gpu')
        if failure == 'gpu_step':
            argv.append('--gpu-step')
        with patch.object(sys, 'argv', argv), \
             patch.object(probe_memory, 'recovery_commands', return_value=['halt', 'a', 'b', 'c']), \
             patch.object(probe_memory.subprocess, 'run', side_effect=captured_openocd), \
             redirect_stdout(io.StringIO()):
            if failure:
                with self.assertRaises(SystemExit):
                    probe_memory.main()
            else:
                probe_memory.main()
        return json.loads((out/'result.json').read_text())

    def test_gpu_stop_preserves_memory_errors_and_control(self):
        result = self.run_probe('gpu')
        self.assertFalse(result['passed'])
        self.assertIsNotNone(result['transport_error'])
        self.assertEqual(result['read1.bin']['error_bytes'], 1)
        self.assertEqual(result['read1.bin']['bits'], {'14': 1})
        self.assertEqual(result['ilm_read.bin']['error_bytes'], 0)
        self.assertIn('error', result['gpu_ffff.bin'])

    def test_early_guard_failure_is_not_an_empty_success(self):
        result = self.run_probe('guard')
        self.assertFalse(result['passed'])
        self.assertIn('error', result['read1.bin'])
        self.assertNotIn('repeated_reads_identical', result)

    def test_word_steps_retain_status_and_never_schedule_a_fill(self):
        result=self.run_probe('gpu_step')
        self.assertFalse(result['passed'])
        self.assertEqual(result['gpu_word_status'],{'0':[1,0,0],'7':[0,0,0]})
        self.assertNotIn('gpu_ffff.bin',result)
        self.assertIn('GPU TARGET only, no DMA',result['writes'])

    def test_exact_readbacks_pass(self):
        result = self.run_probe(None)
        self.assertTrue(result['passed'])
        self.assertIsNone(result['transport_error'])
        self.assertTrue(result['repeated_reads_identical'])
        self.assertEqual(result['read1.bin']['error_bytes'], 0)

    def test_regions_span_the_address_space_with_distinct_signatures(self):
        regions=probe_memory.region_patterns()
        self.assertEqual(len(regions),32)
        self.assertEqual(len({name for name,address,data in regions}),32)
        self.assertEqual(len({data for name,address,data in regions}),32)
        self.assertEqual({address>>26 for name,address,data in regions},set(range(16)))
        for name,address,data in regions:
            self.assertEqual(address%4096,0)
            self.assertEqual(len(data),4096)
            self.assertGreaterEqual(address,0)
            self.assertLessEqual(address+len(data),0x40000000)


if __name__ == '__main__':
    unittest.main()
