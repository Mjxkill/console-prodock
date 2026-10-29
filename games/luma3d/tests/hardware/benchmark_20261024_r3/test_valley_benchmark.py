#!/usr/bin/env python3
"""Local benchmark protocol checks; no serial device or board access."""
import contextlib
import io
import json
import os
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import prodock_valley_benchmark as trial


def log():
    return (b'LUMA3D_BENCHMARK pose=0 warmup=3 measured_frames=30 fixed_pose=1 hardware=1\n'
            b'LUMA3D_RESULT frames=30 elapsed=10.000 fps=3.00 commands=300 batches=30 feed_seconds=8.000 present_seconds=1.000 draws_last=3 triangles_last=8 benchmark=1 hardware=1 warmup=3\n'
            b'LUMA3D_BENCHMARK_COUNTERS cycles=100 vertices=90 raster_triangles=60 culled=30 intersections=0 slivers=0 feed_us=50 wait_us=30 cache_us=10 present_us=20\n'
            b'LUMA3D_COUNTERS errors=0 underflows=0 fault=0 geometry_errors=0 vertices=99 triangles=66 slivers=0 frames=33\n')


class Tests(unittest.TestCase):
    def test_exact_supervisor_shell_exit_and_interruption(self):
        for killed in (False, True):
            with self.subTest(killed=killed), tempfile.TemporaryDirectory() as folder:
                out = Path(folder)
                program = out/'game'
                program.write_text('#!/bin/sh\n'+('exec sleep 10\n' if killed else 'sleep .05\nexit 0\n'))
                program.chmod(0o700)
                cmd = trial.supervisor('game', 'test', 0).replace('/tmp/', folder+'/')
                # Exact suffix used by tools/check_linux.py, including semicolon.
                cmd += "; printf '\\n__PD_RC_%s__\\n' \"$?\"\n"
                proc = subprocess.Popen(['/bin/sh', '-c', cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                deadline = time.monotonic()+2
                while not (out/'test.pid').exists() and time.monotonic() < deadline:
                    time.sleep(.01)
                pid = int((out/'test.pid').read_text())
                proc.wait(timeout=1)  # Interactive shell is available while child runs.
                if killed:
                    os.kill(pid, signal.SIGTERM)
                class ReadOnlyUART:
                    def read(self, size):
                        ready, _, _ = select.select([proc.stdout], [], [], .05)
                        return os.read(proc.stdout.fileno(), size) if ready else b''
                    def write(self, value):
                        raise AssertionError('UART write during measurement')
                code = trial.wait_exit(ReadOnlyUART(), out, 'test', timeout=2)
                proc.stdout.close()
                self.assertEqual(code == 0, not killed)
                self.assertEqual(code, int((out/'test.exit').read_text()))

    def test_exit_in_initial_response_and_echo_not_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            chunks = [b'printf "L3_EXIT_test:0"\r\n', b'\r\nL3_EXIT_test:7\r\n']
            uart = types.SimpleNamespace(read=lambda n: chunks.pop(0))
            self.assertEqual(trial.wait_exit(uart, Path(folder), 'test', timeout=1), 7)
            self.assertEqual(trial.wait_exit(types.SimpleNamespace(), Path(folder), 'test',
                                            initial=b'\r\nL3_EXIT_test:0\r\n'), 0)

    def test_parser_requires_measured_scope_and_all_error_counters(self):
        self.assertEqual(trial.parse_benchmark(log(), 0)['result']['frames'], 30)
        for before, after in [(b'frames=30 ', b'frames=29 '), (b'warmup=3', b'warmup=2'),
                              (b'hardware=1', b'hardware=0'), (b'errors=0', b'errors=1'),
                              (b'slivers=0', b'slivers=1'), (b'frames=33', b'frames=32'),
                              (b'cycles=100', b'cycles=0')]:
            with self.subTest(before=before), self.assertRaises(AssertionError):
                trial.parse_benchmark(log().replace(before, after), 0)

    def test_failure_before_stop_preserves_live_and_after_launch_restores(self):
        for failure in ('install_r3', 'l3v2_r2_0_launch', 'l3v2_r2_0_pixels'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as folder:
                root = Path(folder); bundle = root/'bundle'; bundle.mkdir(); (root/'tools').mkdir()
                names = ('prodock_valley_benchmark.py', 'prodock_transport.py', 'prodock_valley_ab.py', 'prodock_valley_trial.py')
                for name in names:
                    shutil.copy2(ROOT/'tools'/name, bundle/name)
                manifest = dict(live_sha256=trial.LIVE_SHA, shared_tools={}, helper=dict(bytes=1, sha256='fixture'),
                                files={name:dict(bytes=(bundle/name).stat().st_size, sha256=trial.sha(bundle/name)) for name in names}, programs={})
                for key, expected in trial.EXPECTED.items():
                    manifest['programs'][key] = dict(name='luma3d-b2v2' if key == 'r2' else 'luma3d-b3v2',
                        sha256=expected, bytes=200, crc32='22222222',
                        delta=dict(old_sha256=trial.LIVE_SHA, new_sha256=expected, new_bytes=200, new_crc32='22222222',
                                   file=key+'.delta', patch_bytes=100, patch_crc32='11111111'),
                        references={str(pose):dict(file=f'{key}_{pose}.lz4', bytes=192000, sha256='reference', crc32='33333333') for pose in trial.POSES})
                    (bundle/(key+'_game_manifest.json')).write_text(json.dumps(dict(riscv=dict(sha256=expected),
                        captures={f'frame_{pose}':dict(image_sha256='reference') for pose in trial.POSES})))
                (bundle/'manifest.json').write_text(json.dumps(manifest))
                active = ['luma3d-r2']; calls = []; count = [0]
                def display():
                    count[0] += 10
                    return f'DISPLAY presents={count[0]} errors=0 uf=0 invalid=0 sprites=0 fault=0\n'.encode()
                class UART:
                    def __enter__(self): return self
                    def __exit__(self, *args): return False
                    def write(self, value): pass
                    def flush(self): pass
                    def read(self, count): return b''
                class TX:
                    def __init__(self, *args): pass
                    def transfer(self, path, name): return dict(name=name)
                    def run(self, label, command, *args):
                        calls.append(label)
                        if label == failure:
                            if label.endswith('_launch'):
                                active[0] = 'luma3d-b2v2'
                                raise KeyboardInterrupt('injected after child launch')
                            raise RuntimeError('injected '+label)
                        if label == 'before': return trial.RELEASE+b'\ntmpfs /tmp tmpfs rw 0 0\n'+display()
                        if label.startswith('install_'): return b'LUMA3D_UNPACK_OK bytes=200 crc32=22222222\n'
                        if label.startswith('verify_'): return b'LUMA3D_VERIFY_OK bytes=192000 crc32=33333333\n'
                        if label.endswith('_term'): active[0] = None; return b''
                        if label.endswith('_launch'): active[0] = 'luma3d-b2v2'; return b''
                        if label == 'l3v2_r2_0_log': active[0] = None; return log()
                        if label == 'restore_r2': active[0] = 'luma3d-r2'; return b''
                        if 'cat /proc/$p/status' in command:
                            return active[0].encode()+b'\nState:\tR (running)\n' if active[0] else b'STOPPED\n'
                        if 'prodockctl display' in command: return display()
                        if command.startswith('cat /tmp/'): return b'LUMA3D_PERF fps=4.5\n'
                        return b''
                argv = ['benchmark', '--root', str(root), '--bundle', str(bundle), '--out', str(root/'result')]
                with contextlib.ExitStack() as stack:
                    for target, value in [('Transport', TX), ('readback', lambda *a: None), ('wait_exit', lambda *a, **k: 0)]:
                        stack.enter_context(patch.object(trial, target, value))
                    stack.enter_context(patch.object(sys, 'argv', argv))
                    stack.enter_context(patch.object(trial.serial, 'Serial', lambda *a, **k: UART()))
                    stack.enter_context(patch.object(trial, 'open', lambda *a, **k: tempfile.TemporaryFile(), create=True))
                    stack.enter_context(patch.object(trial.fcntl, 'flock', lambda *a: None))
                    stack.enter_context(patch.object(trial.signal, 'signal', lambda *a: None))
                    stack.enter_context(patch.object(trial.time, 'sleep', lambda *a: None))
                    stack.enter_context(patch.dict(sys.modules, {'check_linux': types.SimpleNamespace(command=None)}))
                    stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                    with self.assertRaises(KeyboardInterrupt if failure.endswith('_launch') else RuntimeError):
                        trial.main()
                result = json.loads((root/'result/result.json').read_text())
                self.assertFalse(result['passed']); self.assertEqual(active[0], 'luma3d-r2')
                self.assertNotIn('cleanup_error', result)
                if failure == 'install_r3':
                    self.assertNotIn('stop_live_r2_term', calls)
                    self.assertNotIn('restore_r2', calls)
                else:
                    self.assertTrue(result['restored_r2'])
                    self.assertIn('publish_restored_pid', calls)


if __name__ == '__main__':
    unittest.main()
