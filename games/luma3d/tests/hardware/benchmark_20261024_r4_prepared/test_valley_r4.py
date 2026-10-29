#!/usr/bin/env python3
"""R4 acceptance and recovery checks. No board, serial port or device access."""
import contextlib
import io
import json
import re
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

GAME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GAME/'tools'))
import prodock_valley_r4 as trial


class Tests(unittest.TestCase):
    def test_initial_process_is_exact_and_read_only(self):
        for name, pid, state, good in [('luma3d-b3v2',302,'R',True), ('luma3d-r2',302,'R',False),
                                      ('luma3d-b3v2',303,'R',False), ('luma3d-b3v2',302,'Z',False)]:
            commands = []
            def run(label, command):
                commands.append(command)
                return f'{name}\nState:\t{state} (fixture)\nPid:\t{pid}\n'.encode()
            with self.subTest(name=name, pid=pid, state=state):
                if good:
                    self.assertEqual(trial.confirm_r3(types.SimpleNamespace(run=run)), 302)
                else:
                    with self.assertRaises(AssertionError): trial.confirm_r3(types.SimpleNamespace(run=run))
                self.assertTrue(all('kill' not in c and 'chmod' not in c and ' > ' not in c for c in commands))

    def test_gain_rule_is_not_execution_success(self):
        def records(ratios):
            return [dict(pose=p, variant=v, result=dict(elapsed=10 if v=='r3' else 10/ratios[i]))
                    for i,p in enumerate(trial.POSES) for v in ('r3','r4')]
        self.assertTrue(trial.improvement(records([1.25]*4))['accepted'])
        self.assertFalse(trial.improvement(records([1.05]*4))['accepted'])
        self.assertFalse(trial.improvement(records([2,2,2,.96]))['accepted'])

    def test_uncertain_candidate_pid_never_starts_a_second_game(self):
        with patch.object(trial, 'stop', side_effect=RuntimeError('PID unpublished')), patch.object(trial, 'launch') as launch:
            with self.assertRaises(RuntimeError):
                trial.restore_r3(None, (trial.R4_PROGRAM, '/tmp/specific.pid'), True)
            launch.assert_not_called()

    def test_full_control_flow_gain_no_gain_and_failures(self):
        for scenario in ('gain', 'no_gain', 'install_r4', 'l3r4_r4_0_launch', 'l3r4_r4_0_pixels'):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as directory:
                root=Path(directory); bundle=root/'bundle'; bundle.mkdir(); (root/'tools').mkdir()
                names=('prodock_valley_r4.py','prodock_valley_benchmark.py','prodock_transport.py','prodock_valley_ab.py','prodock_valley_trial.py')
                for name in names: shutil.copy2(GAME/'tools'/name,bundle/name)
                shutil.copy2(GAME/'tests/hardware/valley_20261024_r2/runtime-helper-r2',bundle/trial.HELPER)
                manifest=dict(live_sha256=trial.R3_SHA, shared_tools={}, programs={})
                for key, name, sha in (('r3',trial.R3_PROGRAM,trial.R3_SHA), ('r4',trial.R4_PROGRAM,trial.R4_SHA)):
                    references={str(p):dict(file=f'l3v2-r3-p{p}.lz4' if key=='r3' else f'l3r4-r4-p{p}.lz4',
                                           bytes=192000,sha256='reference',crc32='33333333') for p in trial.POSES}
                    manifest['programs'][key]=dict(name=name,sha256=sha,bytes=200,crc32='22222222',references=references)
                    (bundle/(key+'_game_manifest.json')).write_text(json.dumps(dict(riscv=dict(sha256=sha,bytes=200,crc32='22222222'),
                        captures={f'frame_{p}':dict(image_sha256='reference') for p in trial.POSES})))
                manifest['programs']['r4']['delta']=dict(file='l3r4.delta.lz4',old_sha256=trial.R3_SHA,new_sha256=trial.R4_SHA,
                    new_bytes=200,new_crc32='22222222',patch_bytes=100,patch_crc32='11111111')
                manifest['files']={p.name:dict(bytes=p.stat().st_size,sha256=trial.sha(p)) for p in bundle.iterdir()}
                (bundle/'manifest.json').write_text(json.dumps(manifest))
                active=[trial.R3_PROGRAM]; calls=[]; count=[0]; clock=[0]
                def monotonic(): clock[0]+=20; return clock[0]
                def display():
                    count[0]+=10
                    return f'DISPLAY presents={count[0]} errors=0 uf=0 invalid=0 sprites=0 fault=0\n'.encode()
                def status():
                    return f'{active[0]}\nState:\tR (fixture)\nPid:\t302\n'.encode() if active[0] else b'STOPPED\n'
                def benchmark(key,pose):
                    elapsed=10 if key=='r3' else 8 if scenario!='no_gain' else 10.5
                    return (f'LUMA3D_BENCHMARK pose={pose} warmup=3 measured_frames=30 fixed_pose=1 hardware=1\n'
                        f'LUMA3D_RESULT frames=30 elapsed={elapsed} fps={30/elapsed:.2f} commands=300 batches=30 benchmark=1 hardware=1 warmup=3\n'
                        'LUMA3D_BENCHMARK_COUNTERS cycles=100 vertices=90 raster_triangles=60 culled=30 intersections=0 slivers=0 feed_us=50 wait_us=30 cache_us=10 present_us=20\n'
                        'LUMA3D_COUNTERS errors=0 underflows=0 fault=0 geometry_errors=0 vertices=99 triangles=66 slivers=0 frames=33\n').encode()
                class UART:
                    def __enter__(self): return self
                    def __exit__(self,*args): return False
                    def write(self,data): pass
                    def flush(self): pass
                    def read(self,n): return b''
                class TX:
                    def __init__(self,*args): pass
                    def transfer(self,path,name): return dict(name=name)
                    def run(self,label,command,*args):
                        calls.append((label,command))
                        if label==scenario:
                            if label.endswith('_launch'):
                                active[0]=trial.R4_PROGRAM
                                raise KeyboardInterrupt('injected after R4 launch')
                            raise RuntimeError('injected '+scenario)
                        if label=='before': return trial.RELEASE+b'\ntmpfs /tmp tmpfs rw 0 0\n'+display()
                        if 'cat /proc/$p/status' in command: return status()
                        if label=='install_r4': return b'LUMA3D_UNPACK_OK bytes=200 crc32=22222222\n'
                        if label.startswith('verify_'): return b'LUMA3D_VERIFY_OK bytes=192000 crc32=33333333\n'
                        if label.endswith('_term'): active[0]=None; return b''
                        if label.endswith('_launch') or label=='restore_r3':
                            active[0]=trial.R4_PROGRAM if '/tmp/'+trial.R4_PROGRAM in command else trial.R3_PROGRAM
                            return b''
                        found=re.fullmatch(r'l3r4_(r3|r4)_(\d+)_log',label)
                        if found:
                            active[0]=None; return benchmark(found[1],int(found[2]))
                        if label.endswith('_pixels'):
                            return b'LUMA3D_PIXELS pixels=96000 mismatch=0 actual_crc=33333333 expected_crc=33333333\n'
                        if 'prodockctl display' in command: return display()
                        if label=='endurance_log':
                            return (b'LUMA3D_RESULT frames=100 elapsed=100.0 fps=1.00 benchmark=0 hardware=1 warmup=0\n'
                                    b'LUMA3D_COUNTERS errors=0 underflows=0 fault=0 geometry_errors=0 vertices=100 triangles=100 slivers=0 frames=100\n'
                                    b'LUMA3D_PERF fps=10 collected=4/4\n')
                        if command.startswith('cat /tmp/'): return b'LUMA3D_PERF fps=10 collected=4/4\n'
                        return b''
                argv=['r4','--root',str(root),'--bundle',str(bundle),'--out',str(root/'result')]
                with contextlib.ExitStack() as stack:
                    for name,value in [('Transport',TX),('readback',lambda *a:None),('wait_exit',lambda *a,**k:0)]:
                        stack.enter_context(patch.object(trial,name,value))
                    stack.enter_context(patch.object(sys,'argv',argv))
                    stack.enter_context(patch.object(trial.serial,'Serial',lambda *a,**k:UART()))
                    stack.enter_context(patch.object(trial,'open',lambda *a,**k:tempfile.TemporaryFile(),create=True))
                    stack.enter_context(patch.object(trial.fcntl,'flock',lambda *a:None))
                    stack.enter_context(patch.object(trial.signal,'signal',lambda *a:None))
                    stack.enter_context(patch.object(trial.time,'sleep',lambda *a:None))
                    stack.enter_context(patch.object(trial.time,'monotonic',monotonic))
                    stack.enter_context(patch.dict(sys.modules,{'check_linux':types.SimpleNamespace(command=None)}))
                    stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                    if scenario in ('gain','no_gain'): trial.main()
                    else:
                        with self.assertRaises(KeyboardInterrupt if scenario.endswith('_launch') else RuntimeError): trial.main()
                result=json.loads((root/'result/result.json').read_text())
                self.assertNotIn('cleanup_error',result)
                self.assertEqual(active[0],trial.R4_PROGRAM if scenario=='gain' else trial.R3_PROGRAM)
                if scenario in ('gain','no_gain'):
                    self.assertTrue(result['passed']); self.assertEqual(result['candidate_accepted'],scenario=='gain')
                    self.assertEqual(len(result['benchmarks']),8); self.assertTrue(result['endurance']['four_letters_observed'])
                else:
                    self.assertFalse(result['passed'])
                    if scenario=='install_r4': self.assertFalse(any(k=='stop_live_r3_term' for k,_ in calls))
                    else: self.assertTrue(result['restored_r3'])


if __name__=='__main__':
    unittest.main()
