#!/usr/bin/env python3
"""Tests du validateur avec temps et UART simulés, également exécutables sous -O."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import check_orbital as target

class Clock:
    now=0.0
    def __init__(self,delay): self.delay=delay;self.now=0.0
    def monotonic(self): return self.now
    def sleep(self,seconds): self.now+=self.delay if seconds==5 else seconds

class UART:
    def __init__(self,clock,fault): self.clock=clock;self.fault=fault;self.output=bytearray();self.frame=0;self.closed=False;self.starts=0
    def reset_input_buffer(self): self.output.clear()
    def flush(self): pass
    def close(self): self.closed=True
    def write(self,data):
        if data==b'G':
            self.starts+=1
            if self.fault=='resume' and self.starts==2:return len(data)
        if data[:1]==b'E': self.output.extend(data[3:]);return len(data)
        if data[:1]==b'T': self.frame=int.from_bytes(data[1:3],'little')
        if data==b'?': line='ORBITAL R6 AUTOPLAY'
        elif data in (b'G',b'P'): line='ORBITAL AUTO' if data==b'G' else 'ORBITAL PAUSED'
        else:
            active=self.clock.now>0
            frames=300 if active else 0
            if self.fault=='frozen':frames=0
            line=(f'ORBITAL frame={self.frame} run={0 if self.fault=="stopped" and active else 1} '
                  f'submitted={frames} loops=0 hash=12345678 lcd=12345678 crc565=12345678 '
                  f'errors={1 if self.fault=="errors" else 0} uf=0 '
                  f'uf_total={1 if self.fault=="underflow" and active else 0} '
                  'invalid=0 badsprite=0 line=1000 rejected=0 fx_max=13000000')
        self.output.extend((line+'\r\n').encode());return len(data)
    def read(self,n):
        if not self.output:self.clock.now+=.01
        data=bytes(self.output[:n]);del self.output[:n];return data

class ValidatorTest(unittest.TestCase):
    def exercise(self,fault=None,delay=5,expected_error=None):
        clock=Clock(delay);uart=UART(clock,fault)
        with tempfile.TemporaryDirectory(prefix='console_validator_') as tmp:
            tmp=Path(tmp);poses=tmp/'poses.json';out=tmp/'out'
            poses.write_text(json.dumps([dict(frame=0,hash='12345678')]))
            args=['check_orbital.py','--expected',str(poses),'--out',str(out),'--seconds','5']
            with patch.object(target,'time',clock),patch.object(target,'serial',SimpleNamespace(Serial=lambda *a,**kw:uart)),patch.object(target,'wait_console',lambda:('MODEL',dict(speed_mbps=480))),patch.object(sys,'argv',args),contextlib.redirect_stdout(io.StringIO()):
                if expected_error:
                    with self.assertRaisesRegex(RuntimeError,expected_error):target.main()
                    self.assertFalse((out/'result.json').exists())
                else:
                    target.main();result=json.loads((out/'result.json').read_text())
                    self.assertEqual(result['status'],'PASS');self.assertEqual(result['fps'],60.)
                    self.assertEqual(result['frames'],300);self.assertEqual(result['seconds'],5.)
            self.assertTrue(uart.closed)
    def test_normal(self):self.exercise()
    def test_delayed_pc(self):self.exercise(delay=30,expected_error='Débit insuffisant')
    def test_stale_counter(self):self.exercise('frozen',expected_error='mesure figée')
    def test_stopped(self):self.exercise('stopped',expected_error='Animation arrêtée')
    def test_reported_error(self):self.exercise('errors',expected_error='errors')
    def test_underflow_counter(self):self.exercise('underflow',expected_error='Sous-débordement')
    def test_restore_failure(self):self.exercise('resume',expected_error='Missing response')

if __name__=='__main__':unittest.main()
