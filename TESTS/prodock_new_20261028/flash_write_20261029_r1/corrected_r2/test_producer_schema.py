"""Feed actual load_sd_candidate.run_session output into the writer.

Only guard, subprocess/child, UART and collector I/O are fake. The producer's
report construction, program-log parser and cleanup accounting are real.
This proves schema compatibility, not any boot or physical card behavior.
"""
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import flash_write as writer
from fixture_factory import Fixture, sha, store

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('actual_sram_producer', HERE/'refs/readonly/reference/load_sd_candidate.py')
producer=importlib.util.module_from_spec(spec);spec.loader.exec_module(producer)
PROGRAM=b'write to ram\nfound 1 devices\nindex 0:\n idcode 0x1081b\nafter program sram: displayReadReg 00002000\n'


class Guard:
    PORT=Path('/dev/serial/by-path/pci-0000:00:14.0-usb-0:7.1:1.0')
    def __init__(self):self.locked=False;self.first=True;self.closed=False
    @contextmanager
    def diagnostic_lock(self):
        self.locked=True
        try:yield
        finally:self.locked=False
    def snapshot(self):
        if self.first:self.first=False;raise FileNotFoundError
        return {'busnum':'3','devnum':'22','port':str(self.PORT)}
    def quiet_owner(self,result):assert result.returncode==1
    def PassiveUART(self):return self
    def open(self,timeout):assert self.locked;return self.snapshot()
    def close(self):self.closed=True


class ActualSchema(unittest.TestCase):
    def test_real_sram_report_and_readonly_report_are_consumable(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Fixture(tmp,HERE);g=Guard();out=f.tests/'real_sram';out.mkdir()
            def spawn(argv,stdout,**kw):
                assert g.locked and argv[argv.index('--usb-serial-num')+1]=='2025071717'
                stdout.write(PROGRAM)
                return SimpleNamespace(pid=123,poll=lambda:0,wait=lambda timeout:0)
            def run(argv,**kw):
                assert argv[0] in ('ps','fuser')
                return SimpleNamespace(returncode=1,stdout='',stderr='')
            def capture(io,out,seconds,clock,sleep):
                io.open(.1)  # Real FreshPassive.poll uses real program-log parser.
                return {'game_launch_observed':True,'log_checks_passed':True}
            target={'idVendor':'0403','idProduct':'6010','serial':'2025071717','busnum':'3','devnum':'22'}
            with patch.object(producer.subprocess,'run',side_effect=run):
                result=producer.run_session(out,f.fs,sha(f.fs),3,g,
                    SimpleNamespace(capture=capture),SimpleNamespace(devices=lambda:[target]),
                    spawn=spawn,check_permissions=lambda *a:True)
            self.assertTrue(result['passed'],result)
            self.assertTrue(result['programmer_reaped'])
            self.assertEqual(result['returncode'],0)
            self.assertTrue(g.closed)
            self.assertFalse(g.locked)
            self.assertEqual(json.loads((out/'result.json').read_text()),result)
            f.req['sram_result']={'path':str(out/'result.json'),'sha256':sha(out/'result.json')}
            acc=json.loads(f.acceptance.read_text());acc['sram_result_sha256']=sha(out/'result.json')
            f.req['acceptance']=store(f.acceptance,acc);f.sync()
            plan=writer.prepare(f.request,sha(f.request),f.tests/'writer_plan',root=f.root)
            self.assertTrue(plan['image_contract']['verified'])
            self.assertEqual(plan['inputs']['sram_result']['sha256'],sha(out/'result.json'))
            self.assertFalse(f.calls)


if __name__=='__main__':unittest.main()
