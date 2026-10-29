"""Exercise unattended pixel sequencing without accessing a board."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('finish_pixels',ROOT/'tools/neo/finish_pixels.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class PixelFollowerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.build=self.root/'tang/impl/console_neo_test'
        self.validation=self.root/'TESTS/validation';self.board=self.validation/self.build.name/'board'
        self.build.mkdir(parents=True);self.board.mkdir(parents=True)
        self.vectors=self.root/'vectors';self.vectors.mkdir()
        self.geometry=self.root/'geometry';self.geometry.mkdir()
        self.out=self.root/'TESTS/pixels';self.calls=[];self.fault=None
        self.entry=dict(build=str(self.build),out=str(self.board.parent),state='preflight_passed',
                        cpu_left_halted=True,bitstream_sha256='a'*64)
        self.status=dict(builds=[str(self.build)],state='preflight_passed',results=[self.entry])
        self.result=dict(bitstream_sha256='a'*64,passed=True,run_mode='preflight_only',
                         cpu_left_halted=True,sd_written=False,flash_written=False)
        self.save()

    def save(self):
        (self.validation/'status.json').write_text(json.dumps(self.status))
        (self.board/'result.json').write_text(json.dumps(self.result))
        (self.build/'qualification.json').write_text(json.dumps(dict(bitstream_sha256='a'*64)))

    def fake_probe(self,command,**kwargs):
        self.calls.append(command)
        dest=Path(command[command.index('--out')+1]);dest.mkdir()
        result=dict(self.result,transport_error=None)
        if self.fault=='pixel' and dest.name=='solid':result['passed']=False
        if self.fault=='transport' and dest.name=='solid':result['transport_error']='timeout'
        (dest/'result.json').write_text(json.dumps(result))
        return SimpleNamespace(returncode=0 if result['passed'] and not result['transport_error'] else 1)

    def run_follower(self):
        argv=['finish_pixels','--validation',str(self.validation),'--build',str(self.build),
              '--vectors',str(self.vectors),'--geometry',str(self.geometry),'--out',str(self.out)]
        with patch.object(module,'ROOT',self.root),patch('sys.argv',argv),\
                patch.object(module.subprocess,'run',side_effect=self.fake_probe):
            return module.main()

    def test_only_complete_preflight_admitted(self):
        self.assertEqual(module.accepted_board(self.validation,self.build),(self.board,'a'*64))
        for field,value in [('run_mode','linux'),('passed',False),('cpu_left_halted',False),
                            ('sd_written',True),('flash_written',True),('bitstream_sha256','b'*64)]:
            original=self.result[field];self.result[field]=value;self.save()
            with self.assertRaises(ValueError):module.accepted_board(self.validation,self.build)
            self.result[field]=original
        self.save()
        self.status['results'][0]['out']=str(self.root/'different');self.save()
        with self.assertRaises(ValueError):module.accepted_board(self.validation,self.build)

    def test_failed_preflight_never_probes(self):
        self.status['state']='no_candidate_passed';self.save()
        self.assertEqual(self.run_follower(),2);self.assertEqual(self.calls,[])

    def test_full_success_checks_geometry_with_full_windows(self):
        self.assertEqual(self.run_follower(),0);self.assertEqual(len(self.calls),7)
        self.assertNotIn('--window-bytes',self.calls[0])
        self.assertNotIn('--window-bytes',self.calls[-1])
        self.assertTrue(all('--window-bytes' in c for c in self.calls[1:-1]))
        self.assertEqual(json.loads((self.out/'status.json').read_text())['state'],'passed')

    def test_pixel_mismatch_collected_without_false_success(self):
        self.fault='pixel'
        self.assertEqual(self.run_follower(),1);self.assertEqual(len(self.calls),6)
        self.assertEqual(json.loads((self.out/'status.json').read_text())['state'],'pixel_mismatches')

    def test_transport_failure_stops_immediately(self):
        self.fault='transport'
        self.assertEqual(self.run_follower(),2);self.assertEqual(len(self.calls),2)
        self.assertEqual(json.loads((self.out/'status.json').read_text())['state'],'stopped')


if __name__=='__main__':unittest.main()
