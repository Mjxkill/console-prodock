#!/usr/bin/env python3
"""Exercise unchanged check_orbital with virtual time and serial, no hardware."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
spec = importlib.util.spec_from_file_location('review_orbital', ROOT / 'tools/check_orbital.py')
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

class Clock:
    def __init__(self, delay): self.now = 0.; self.delay = delay
    def monotonic(self): return self.now
    def sleep(self, seconds): self.now += self.delay if seconds == 5 else seconds

class UART:
    def __init__(self, *args, **kwargs): self.output = bytearray(); self.frame = 0
    def reset_input_buffer(self): self.output.clear()
    def flush(self): pass
    def close(self): pass
    def write(self, data):
        if data[:1] == b'E': self.output.extend(data[3:]); return len(data)
        if data[:1] == b'T': self.frame = int.from_bytes(data[1:3], 'little')
        if data == b'?': reply = 'ORBITAL R6 AUTOPLAY FPS R31 core=800MHz\r\n'
        elif data in (b'G', b'P'): reply = 'ORBITAL AUTO\r\n' if data == b'G' else 'ORBITAL PAUSED\r\n'
        else:
            reply = (f'ORBITAL frame={self.frame} run=1 submitted=300 loops=0 '
                     'hash=12345678 lcd=12345678 crc565=12345678 '
                     'errors=0 uf=0 uf_total=0 invalid=0 badsprite=0 '
                     'line=1000 rejected=0 fx_max=13000000\r\n')
        self.output.extend(reply.encode()); return len(data)
    def read(self, n):
        data = bytes(self.output[:n]); del self.output[:n]; return data

def case(name, delay):
    check.time = Clock(delay)
    check.serial = SimpleNamespace(Serial=UART)
    check.wait_console = lambda: ('SIMULATED', dict(speed_mbps=480))
    with tempfile.TemporaryDirectory(prefix='console_review_validator_') as tmp:
        tmp = Path(tmp); expected = tmp / 'poses.json'; out = tmp / 'result'
        expected.write_text(json.dumps([dict(frame=0, hash='12345678')]))
        sys.argv = ['check_orbital.py', '--expected', str(expected), '--out', str(out),
                    '--seconds', '5', '--min-fps', '54.5']
        transcript = io.StringIO()
        with contextlib.redirect_stdout(transcript): check.main()
        result = json.loads((out / 'result.json').read_text())
        actual_fps = result['samples'][-1]['submitted'] / result['seconds']
        return dict(case=name, validator_status=result['status'], requested_seconds=5,
                    elapsed_seconds=result['seconds'], frames=300, actual_fps=actual_fps,
                    required_fps=54.5, transcript=transcript.getvalue())

if __name__ == '__main__':
    cases = [case('control', 5), case('scheduler_delayed', 30)]
    if not (cases[0]['actual_fps'] >= 54.5 and cases[1]['actual_fps'] < 54.5
            and all(c['validator_status'] == 'PASS' for c in cases)):
        raise RuntimeError('Counterexample not reproduced')
    result = dict(reproduced=True, production_modified=False, cases=cases)
    Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
    for c in cases:
        print(f"{c['case']}: {c['validator_status']}, {c['frames']} frames / "
              f"{c['elapsed_seconds']} s = {c['actual_fps']} fps; required {c['required_fps']}")
