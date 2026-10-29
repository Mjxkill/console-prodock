#!/usr/bin/env python3
"""Fault injection for the warm-boot controller; never opens real hardware."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import types
import time
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import prodock_warm_boot as boot


def counters(presents):
    return f'DISPLAY mode=1 presents={presents} errors=0 uf=0 invalid=0 sprites=0 fault=0\n'.encode()


class Tests(unittest.TestCase):
    def test_loader_group_stops_grandchild_before_returning(self):
        for injected in ('timeout','interrupt'):
            with self.subTest(injected=injected),tempfile.TemporaryDirectory() as name:
                root=Path(name);pidfile=root/'writer.pid';ticks=root/'ticks'
                writer="import os,time,pathlib;pathlib.Path(%r).write_text(str(os.getpid()));f=open(%r,'wb',buffering=0)\nwhile True:f.write(b'x');time.sleep(.02)"%(str(pidfile),str(ticks))
                loader="import subprocess,sys;subprocess.Popen([sys.executable,'-c',%r]).wait()"%writer
                original=boot.subprocess.Popen.wait;pending=[True]
                def interrupted_wait(child,timeout=None):
                    if pending[0]:
                        pending[0]=False;until=time.monotonic()+3
                        while not ticks.exists() and time.monotonic()<until:time.sleep(.01)
                        self.assertTrue(ticks.exists())
                        raise KeyboardInterrupt('Injected while grandchild writes')
                    return original(child,timeout=timeout)
                with tempfile.TemporaryFile() as log,tempfile.TemporaryFile() as lock:
                    ctx=patch.object(boot.subprocess.Popen,'wait',interrupted_wait) if injected=='interrupt' else contextlib.nullcontext()
                    with ctx,self.assertRaises(KeyboardInterrupt if injected=='interrupt' else subprocess.TimeoutExpired):
                        boot.run_loader([sys.executable,'-c',loader],root,log,lock.fileno(),timeout=1)
                self.assertTrue(pidfile.exists());pid=int(pidfile.read_text())
                state=Path('/proc')/str(pid)/'stat'
                if state.exists():self.assertIn(state.read_text().split()[2],('Z','X'))
                size=ticks.stat().st_size;time.sleep(.1)
                self.assertEqual(ticks.stat().st_size,size,'Grandchild kept writing after recovery became possible')

    def test_alive_is_not_just_comm(self):
        for letter,result in [('S','alive'),('R','alive'),('Z','dead'),('X','dead')]:
            tx=types.SimpleNamespace(run=lambda *a:b'luma-riscv\nState:\t'+letter.encode()+b' (state)\n')
            self.assertEqual(boot.luma_state(tx,'test'),result)
        tx=types.SimpleNamespace(run=lambda *a:b'STOPPED\n')
        self.assertEqual(boot.luma_state(tx,'test'),'absent')
        tx=types.SimpleNamespace(run=lambda *a:b'other-app\nState:\tR (running)\n')
        with self.assertRaises(AssertionError):
            boot.luma_state(tx,'test')

    def test_living_but_stalled_is_not_restored(self):
        def run(name,*args):
            return b'luma-riscv\nState:\tS (sleeping)\n' if 'process' in name else counters(200)
        with patch.object(boot.time,'sleep',lambda n:None):
            with self.assertRaisesRegex(AssertionError,'not presenting'):
                boot.live_luma(types.SimpleNamespace(run=run),'test')

    def test_resume_requires_actual_warm_identity_before_payload(self):
        for accept in (True,False):
            with self.subTest(accept=accept),tempfile.TemporaryDirectory() as name:
                root=Path(name); files={'kernel':{},'warm':{}}
                prepared=root/'prepared.json';prepared.write_text(json.dumps(files))
                prior=root/'old';(prior/'recovery/r17').mkdir(parents=True)
                (prior/'result.json').write_text(json.dumps({'passed':False,'fpga_sha256':boot.FPGA_SHA,'identities':files}))
                (prior/'recovery/r17/loader.log').write_text('Expected one Pro Dock FTDI 2023112818, found []')
                calls=[]; phases=[]
                class UART:
                    def __enter__(self):return self
                    def __exit__(self,*args):return False
                    def write(self,data):calls.append(('uart',data))
                    def read(self,size):return b''
                    def reset_input_buffer(self):pass
                    def flush(self):pass
                class TX:
                    def __init__(self,*args):pass
                    def marker(self,wanted):
                        self_marker=b'MegaPro GPU LUMA3D WARM PARK R1\r\n'
                        assert wanted==self_marker
                        if not accept:raise TimeoutError('Unknown board state')
                        return self_marker
                    def run(self,label,command,*args):
                        calls.append((label,command))
                        if label=='candidate_system':return boot.RELEASE.encode()+b'\ntmpfs /tmp tmpfs rw 0 0\n'+counters(1)
                        if label=='raster_oracle':return b'PRODOCK_GPU_PIXELS_OK pixels=384000\n'
                        if label=='raster_display':return counters(2)
                        raise AssertionError('Unexpected Linux command before boot: '+label)
                argv=['boot','--root',str(root),'--pack',str(root/'candidate'),'--rollback-pack',str(root/'r17'),
                      '--rollback-bundle',str(root/'r9b'),'--warm-bin',str(root/'warm'),'--setup',str(root/'setup'),
                      '--out',str(root/'result'),'--prepared',str(prepared),'--resume-from',str(prior/'result.json')]
                with contextlib.ExitStack() as stack:
                    stack.enter_context(patch.object(sys,'argv',argv))
                    stack.enter_context(patch.object(boot,'identities',lambda a:files))
                    stack.enter_context(patch.object(boot,'open',lambda *a,**k:tempfile.TemporaryFile(),create=True))
                    stack.enter_context(patch.object(boot.fcntl,'flock',lambda *a:None))
                    stack.enter_context(patch.object(boot.signal,'signal',lambda *a:None))
                    stack.enter_context(patch.object(boot.time,'sleep',lambda n:None))
                    stack.enter_context(patch.object(boot.serial,'Serial',lambda *a,**k:UART()))
                    stack.enter_context(patch.object(boot,'Transport',TX))
                    stack.enter_context(patch.object(boot,'warm_and_boot',lambda a,p,o:phases.append(p.name)))
                    stack.enter_context(patch.dict(sys.modules,{'check_linux':types.SimpleNamespace(command=None)}))
                    stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                    if accept:boot.main()
                    else:
                        with self.assertRaises(TimeoutError):boot.main()
                report=json.loads((root/'result/result.json').read_text())
                self.assertEqual(report['passed'],accept)
                self.assertEqual(phases,['candidate'] if accept else [])
                self.assertFalse(any(k in ('before','identify_game','stop_game') for k,_ in calls))

    def test_failure_and_ctrl_c_restore_kernel_and_luma(self):
        for error in (RuntimeError('Injected boot failure'),KeyboardInterrupt('Injected Ctrl-C')):
            with self.subTest(error=type(error).__name__),tempfile.TemporaryDirectory() as name:
                root=Path(name); prepared=root/'prepared.json'; prepared.write_text('{}')
                calls=[]; phases=[]
                class UART:
                    def __enter__(self):return self
                    def __exit__(self,*args):return False
                    def write(self,data):pass
                    def read(self,size):return b''
                class TX:
                    def __init__(self,*args):pass
                    def run(self,label,command,*args):
                        calls.append((label,command))
                        if label=='before':
                            return b'6.12.112-prodock\ntmpfs /tmp tmpfs rw 0 0\n'+counters(1)
                        if label=='gpu_released':
                            return b'GPU ABI=1 caps=000001ff DDR=00800000+90177536 \n'+counters(2)
                        if label=='r17_system':return b'6.12.112-prodock\n'
                        if label=='luma_start_0':return b'LUMA_START worlds=36 mode=benchmark board=800x480 \n'
                        if 'process' in label:return b'luma-riscv\nState:\tS (sleeping)\n'
                        if label.endswith('_first'):return counters(10)
                        if label.endswith('_second'):return counters(50)
                        return b''
                    def bootstrap(self,p):calls.append(('bootstrap',p.name))
                    def transfer(self,p,n):calls.append(('transfer',n));return {'name':n}
                def warm(a,pack,out):
                    phases.append(pack.name)
                    if pack.name=='candidate':raise error
                argv=['boot','--root',str(root),'--pack',str(root/'candidate'),
                      '--rollback-pack',str(root/'r17'),'--rollback-bundle',str(root/'r9b'),
                      '--warm-bin',str(root/'warm'),'--setup',str(root/'setup'),
                      '--out',str(root/'result'),'--prepared',str(prepared)]
                with contextlib.ExitStack() as stack:
                    stack.enter_context(patch.object(sys,'argv',argv))
                    stack.enter_context(patch.object(boot,'identities',lambda a:{}))
                    stack.enter_context(patch.object(boot,'open',lambda *a,**k:tempfile.TemporaryFile(),create=True))
                    stack.enter_context(patch.object(boot.fcntl,'flock',lambda *a:None))
                    stack.enter_context(patch.object(boot.signal,'signal',lambda *a:None))
                    stack.enter_context(patch.object(boot.time,'sleep',lambda n:None))
                    stack.enter_context(patch.object(boot.serial,'Serial',lambda *a,**k:UART()))
                    stack.enter_context(patch.object(boot,'Transport',TX))
                    stack.enter_context(patch.object(boot,'warm_and_boot',warm))
                    stack.enter_context(patch.dict(sys.modules,{'check_linux':types.SimpleNamespace(command=None)}))
                    stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                    with self.assertRaises(type(error)):
                        boot.main()
                report=json.loads((root/'result/result.json').read_text())
                self.assertFalse(report['passed']);self.assertTrue(report['restored_luma'])
                self.assertEqual(phases,['candidate','r17'])
                self.assertEqual([n for k,n in calls if k=='transfer'],['luma-riscv','luma.lz4','world_02.lz4'])
                self.assertTrue(any(k=='luma_launch' for k,_ in calls))
                self.assertLess([k for k,_ in calls].index('restored_executable_mode'),[k for k,_ in calls].index('luma_launch'))
                self.assertFalse(any('/bin/nebula' in str(v) for _,v in calls))


if __name__=='__main__':unittest.main()
