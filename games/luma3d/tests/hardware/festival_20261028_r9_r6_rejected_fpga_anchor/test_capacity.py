#!/usr/bin/env python3
"""Exercise the real preparation method, without a UART or filesystem deletion."""
import copy,json,types,unittest
from pathlib import Path
from unittest.mock import patch
import festival_trial as t
HERE=Path(__file__).resolve().parent
def df(available):return ('Filesystem 1024-blocks Used Available Capacity Mounted on\n'+'tmpfs 186556 '+str(186556-available)+' '+str(available)+' 80% /tmp\n').encode()
class TX:
    def __init__(self,free):self.free=iter(free);self.calls=[]
    def run(self,label,cmd,*args):
        self.calls.append(('run',label,cmd))
        if label.startswith('space_'):return df(next(self.free))
        if label=='install_candidate':return b'LUMA3D_UNPACK_OK bytes=123 crc32=456'
        return b''
    def transfer(self,path,name,expected):self.calls.append(('transfer',name));return {'name':name}
class Tests(unittest.TestCase):
    def test_exact_full_mount(self):
        with self.assertRaisesRegex(RuntimeError,'Insufficient'):t.tmp_capacity(df(0))
    def test_boundary_and_valid_echo_framing(self):
        for n in (32768,186556):self.assertEqual(t.tmp_capacity(b'cmd df -Pk /tmp\r\n'+df(n)+b'prodock#\r\n')['available_kib'],n)
        with self.assertRaises(RuntimeError):t.tmp_capacity(df(32767))
    def test_invalid_and_wrong_mount(self):
        for raw in (b'',df(50000).replace(b'/tmp',b'/root'),df(50000)*2,df(50000).replace(b'50000',b'-1'),df(50000).replace(b'186556',b'1'),df(50000).replace(b'80%',b'nan')):
            with self.assertRaises(RuntimeError,msg=raw):t.tmp_capacity(raw)
    def test_guard_is_frozen(self):
        original=json.loads((HERE/'manifest.json').read_text())
        for policy in (None,{},dict(mount='/tmp',minimum_available_kib=1,check='before_each_transfer_and_reconstruction')):
            m=copy.deepcopy(original);m['storage_guard']=policy
            with patch.object(t.json,'loads',return_value=m):
                with self.assertRaises(RuntimeError):t.preflight(HERE)
    def test_real_prepare_rechecks_before_every_write_phase(self):
        for free,expected_transfers,install in (([0],0,False),([32768,0],1,False),([32768]*2,1,True)):
            b=object.__new__(t.Hardware);b.bundle=HERE;b.signals=t.DeferredSignals();b.tx=TX(free)
            b.m=dict(transfer_files=['delta'],files={'helper':{'bytes':1,'sha256':'x'},'delta':{}},helper='helper',baseline={},delta={'file':'delta','patch_bytes':4,'patch_crc32':'5'},game={'bytes':123,'crc32':'456'},program='candidate')
            b.mods={'prodock_valley_benchmark':types.SimpleNamespace(readback=lambda *a:None),'prodock_transport':types.SimpleNamespace(RECEIVER_SHA='x')};b.arcade=types.SimpleNamespace(raw_verify=lambda *a:None)
            if install:self.assertEqual(len(b.prepare()),1)
            else:
                with self.assertRaisesRegex(RuntimeError,'Insufficient'):b.prepare()
            self.assertEqual(sum(c[0]=='transfer' for c in b.tx.calls),expected_transfers)
            self.assertEqual(any(c[:2]==('run','install_candidate') for c in b.tx.calls),install)
            for i,c in enumerate(b.tx.calls):
                if c[0]=='transfer':self.assertEqual(b.tx.calls[i-1][1],'space_before_transfer_'+c[1])
                if c[:2]==('run','install_candidate'):self.assertEqual(b.tx.calls[i-1][1],'space_before_reconstruction')
if __name__=='__main__':
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    (HERE/'capacity_tests.json').write_text(json.dumps(dict(passed=r.wasSuccessful(),hardware=False,tests=r.testsRun,manifest_sha256=t.digest(HERE/'manifest.json')['sha256'],controller_sha256=t.digest(HERE/'festival_trial.py')['sha256'],test_sha256=t.digest(Path(__file__))['sha256']),indent=2)+'\n')
    raise SystemExit(not r.wasSuccessful())
