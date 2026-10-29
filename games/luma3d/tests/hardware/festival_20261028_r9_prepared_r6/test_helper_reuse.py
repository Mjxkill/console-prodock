#!/usr/bin/env python3
"""Reject stale/mismatched helper proofs; verify real prepare transfers only delta."""
import copy,json,types,unittest
from pathlib import Path
from unittest.mock import patch
import festival_trial as t
from test_trial import review
HERE=Path(__file__).resolve().parent
class Tests(unittest.TestCase):
    def test_frozen_proof_and_root_attestation(self):
        m=t.preflight(HERE);sha=t.digest(HERE/'manifest.json')['sha256'];r=review(m);t.check_review(r,m,sha,t.LOCAL_HOSTNAME)
        for change in (None,{},dict(r['helper_reuse'],continuity_confirmed=False),dict(r['helper_reuse'],proof_sha256='0'*64),dict(r['helper_reuse'],path='/tmp/f9f-helper')):
            rr=dict(r,helper_reuse=change)
            with self.assertRaisesRegex(RuntimeError,'continuity'):t.check_review(rr,m,sha,t.LOCAL_HOSTNAME)
    def test_failed_or_foreign_readback_proof(self):
        m=json.loads((HERE/'manifest.json').read_text());original=t.json.loads
        for key,value in [('passed',False),('board','neo'),('identity',{'pid':2925,'start_ticks':1}),('save_sha256','0'*64),('game_signals_sent',True),('fpga_writes',1),('available_kib',0),('display_before',{})]:
            def changed(raw):
                v=original(raw)
                if isinstance(v,dict) and 'deleted' in v:v[key]=value
                return v
            with patch.object(t.json,'loads',side_effect=changed):
                with self.assertRaises(RuntimeError,msg=key):t.check_helper_proof(HERE,m)
    def test_changed_bytes_fail(self):
        m=json.loads((HERE/'manifest.json').read_text());original=t.digest
        for name in ('mc1-helper','helper_reuse_verified.bin','helper_reuse_result.json'):
            def changed(p):
                v=original(p)
                if Path(p).name==name:v['sha256']='0'*64
                return v
            with patch.object(t,'digest',side_effect=changed):
                with self.assertRaises(RuntimeError,msg=name):t.check_helper_proof(HERE,m)
    def test_actual_prepare_only_delta_and_crc_before_transfer(self):
        m=t.preflight(HERE);calls=[]
        class TX:
            def run(self,label,cmd,*args):
                calls.append(('run',label,cmd))
                if label.startswith('space_'):return b'tmpfs 186556 100000 86556 54% /tmp\n'
                if label=='install_candidate':return f'LUMA3D_UNPACK_OK bytes={m["game"]["bytes"]} crc32={m["game"]["crc32"]}'.encode()
                return b''
            def transfer(self,path,name,expected):calls.append(('transfer',name));return {'name':name}
        def readback(tx,label,path,*args):calls.append(('readback',label,path))
        def raw_verify(tx,helper,label,path,record):calls.append(('raw',label,path));self.assertEqual(helper,'mc1-helper')
        b=object.__new__(t.Hardware);b.bundle=HERE;b.m=m;b.tx=TX();b.signals=t.DeferredSignals();b.mods={'prodock_valley_benchmark':types.SimpleNamespace(readback=readback),'prodock_transport':types.SimpleNamespace(RECEIVER_SHA='x')};b.arcade=types.SimpleNamespace(raw_verify=raw_verify)
        self.assertEqual(b.prepare(),[{'name':'festival-r9f.delta.lz4'}]);self.assertEqual([x for x in calls if x[0]=='readback'],[('readback','receiver_readback','/tmp/luma-rx')]);self.assertEqual([x for x in calls if x[0]=='transfer'],[('transfer','festival-r9f.delta.lz4')])
        self.assertLess(calls.index(('raw','retained_helper_runtime','/tmp/mc1-helper')),calls.index(('transfer','festival-r9f.delta.lz4')))
        self.assertFalse(any(x[0]=='run' and ('chmod 700 /tmp/mc1-helper' in x[2] or 'od -b -v /tmp/mc1-helper' in x[2]) for x in calls))
        calls.clear()
        def corrupted(*a):raise RuntimeError('Injected runtime CRC mismatch')
        b.arcade=types.SimpleNamespace(raw_verify=corrupted)
        with self.assertRaises(RuntimeError):b.prepare()
        self.assertFalse(any(x[0]=='transfer' for x in calls))
if __name__=='__main__':
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    (HERE/'helper_reuse_tests.json').write_text(json.dumps(dict(passed=r.wasSuccessful(),hardware=False,tests=r.testsRun,manifest_sha256=t.digest(HERE/'manifest.json')['sha256'],controller_sha256=t.digest(HERE/'festival_trial.py')['sha256'],test_sha256=t.digest(Path(__file__))['sha256']),indent=2)+'\n')
    raise SystemExit(not r.wasSuccessful())
