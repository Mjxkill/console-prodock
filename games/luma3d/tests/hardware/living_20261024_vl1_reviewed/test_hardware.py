#!/usr/bin/env python3
"""Fault injection only. No serial device or board is opened."""
import contextlib
import io
import json
import struct
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
ROOT=next(p for p in HERE.parents if (p/'games/luma3d/tools').is_dir())
sys.path[:0]=[str(HERE.parent),str(ROOT/'games/luma3d/tools')]
import prodock_living as t


def benchmark(scene):
    return (f'LUMA3D_BENCHMARK pose={scene["pose"]} warmup=3 measured_frames=30 fixed_pose=1 hardware=1\n'
        'LUMA3D_RESULT frames=30 elapsed=3.0 fps=10 commands=60 batches=30 draws_last=1 triangles_last=2 benchmark=1 hardware=1 warmup=3\n'
        'LUMA3D_COUNTERS errors=0 underflows=0 fault=0 geometry_errors=0 vertices=99 triangles=66 slivers=0 frames=33\n'
        'LUMA3D_BENCHMARK_COUNTERS cycles=10 vertices=90 raster_triangles=60 culled=0 intersections=0 slivers=0 feed_us=1 wait_us=1 cache_us=1 present_us=1\n').encode()


class Tests(unittest.TestCase):
    def test_receiver_abort_recovers_every_partial_packet_boundary(self):
        payload=bytearray();calls=[]
        uart=types.SimpleNamespace(write=lambda b:payload.extend(b),flush=lambda:None,read=lambda n:b'F\0\0\0\0')
        tx=types.SimpleNamespace(receiver_active=True,run=lambda *a:calls.append(a))
        with tempfile.TemporaryDirectory() as d,patch.object(t.time,'sleep',lambda *a:None):
            t.abort_receiver(tx,uart,Path(d))
        self.assertFalse(tx.receiver_active);self.assertEqual(calls[0][0],'receiver_shell_restored')
        packet=struct.pack('<4sIII',b'LMA1',17,512,0x12345678)+bytes(range(256))*2
        for cut in range(len(packet)+1):
            stream=packet[:cut]+payload[:-1];at=0;stopped=False
            # Match the receiver's magic/header/length consumption. CRC may
            # reject a partial data block, but it always resumes magic search.
            while True:
                at=stream.find(b'LMA1',at)
                if at<0:break
                self.assertGreaterEqual(len(stream)-at,16)
                seq,n,crc=struct.unpack_from('<III',stream,at+4);at+=16
                if n>1024:continue
                if n==0:stopped=True;break
                self.assertGreaterEqual(len(stream)-at,n);at+=n
            self.assertTrue(stopped,cut)

    def test_identity_accepts_fresh_pid_not_historical_anchor(self):
        for pid,state,good in [(424,'S',True),(501,'R',True),(424,'Z',False)]:
            commands=[]
            rest=[state]+['0']*18+['123456']
            raw=(str(pid)+' ('+t.R3+') '+' '.join(rest)+'\n/tmp/'+t.R3+'\x00\n').encode()
            def run(label,cmd):commands.append(cmd);return raw
            with patch.object(t,'process',return_value=True):
                if good:self.assertEqual(t.identity(types.SimpleNamespace(run=run),'probe'),dict(pid=pid,start_ticks=123456))
                else:
                    with self.assertRaises(AssertionError):t.identity(types.SimpleNamespace(run=run),'probe')
            self.assertTrue(all('kill' not in cmd and ' > ' not in cmd for cmd in commands))

    def test_ambiguous_pid_blocks_fallback(self):
        with patch.object(t,'stop',side_effect=RuntimeError('unpublished')),patch.object(t,'launch') as launch:
            with self.assertRaises(RuntimeError):t.recover(None,dict(tag='vl1'),('luma3d-vl1','/tmp/vl1.pid'),True)
            launch.assert_not_called()

    def test_benchmark_requires_all_frames_and_exact_commands(self):
        scene=dict(pose=90,variant='new',oracle=dict(vertices=3,triangles=2,slivers=0),host_benchmark=dict(commands=60,batches=30,draws_last=1,triangles_last=2))
        log=benchmark(scene);self.assertEqual(t.parse(log,scene)['result']['frames'],30)
        for before,after in [(b'frames=33',b'frames=32'),(b'commands=60',b'commands=61'),(b'vertices=90',b'vertices=89'),(b'underflows=0',b'underflows=1')]:
            with self.assertRaises(AssertionError):t.parse(log.replace(before,after),scene)

    def test_control_flow_errors_and_completion(self):
        for fail in (None,'install','vl1_1_launch','vl1_1_pixels','incomplete','dead_endurance'):
            with self.subTest(fail=fail),tempfile.TemporaryDirectory() as d:
                root=Path(d);(root/'manifest.json').write_text('{}');calls=[];alive=[t.R3];clock=[0];count=[0]
                def mono():clock[0]+=10;return clock[0]
                def status():count[0]+=1;return f'DISPLAY presents={count[0]} errors=0 uf=0 invalid=0 sprites=0 fault=0\n'.encode()
                ref=dict(file='ref.lz4',bytes=192000,crc32='11111111')
                scenes=[dict(pose=p,variant='r3' if i==0 else 'new',pixels=ref,hud=ref,
                    oracle=dict(vertices=3,triangles=2,slivers=0),host_benchmark=dict(commands=60,batches=30,draws_last=1,triangles_last=2)) for i,p in enumerate([0,0,90,1450,2330,3200,3800])]
                m=dict(game=dict(bytes=100,crc32='22222222'),tag='vl1',program='luma3d-vl1',helper='vl1-helper',transfer_files=[],
                    delta=dict(file='delta.lz4',patch_bytes=10,patch_crc32='33333333'),scenes=scenes,completion_hud=ref)
                class UART:
                    def __enter__(self):return self
                    def __exit__(self,*args):return False
                    def write(self,b):calls.append(('write',b))
                    def flush(self):pass
                    def read(self,n):return b''
                class TX:
                    def __init__(self,*a):pass
                    def run(self,label,cmd,*a):
                        calls.append((label,cmd))
                        if label==fail:
                            if label.endswith('_launch'):alive[0]=m['program'];raise KeyboardInterrupt('injected launch')
                            raise RuntimeError(label)
                        if label=='before':return t.RELEASE+b'\nGPU ABI=1 caps=000001ff DDR=00800000+90177536 \nGEOMETRY board=0 width=800 height=480 \ntmpfs /tmp tmpfs rw 0 0\n'+status()
                        if label=='install':return b'LUMA3D_UNPACK_OK bytes=100 crc32=22222222\n'
                        if label.startswith('verify_'):return b'LUMA3D_VERIFY_OK bytes=192000 crc32=11111111\n'
                        if label.endswith('_launch'):alive[0]=m['program'];return b''
                        if label.startswith('vl1_') and label.endswith('_log'):
                            alive[0]=None;return benchmark(scenes[int(label.split('_')[1])])
                        if label=='endurance_log':return (f'LUMA3D_RESULT frames=150 elapsed=130.0 fps=8\nLUMA3D_STORY phase={3 if fail=="incomplete" else 4} relay=3 discovered=1 collected=4 complete=1 sim=100.0 auto=1\nLUMA3D_COUNTERS errors=0 underflows=0 fault=0 geometry_errors=0 vertices=1 triangles=1 slivers=0 frames=150\n').encode()
                        if label.endswith('_pixels'):return b'LUMA3D_PIXELS pixels=96000 mismatch=0 actual_crc=11111111 expected_crc=11111111\n'
                        if '_hud_' in label:return f'LUMA3D_HUD bank={label[-2:]} bytes=192000 mismatch=0 actual_crc=11111111 expected_crc=11111111\n'.encode()
                        if 'prodockctl display' in cmd:return status()
                        return b''
                def proc(tx,label,name,pidfile=t.LIVE):return False if fail=='dead_endurance' and label=='endurance_alive' else alive[0]==name
                def stop(tx,name,label,pidfile=t.LIVE):calls.append((label,name));alive[0]=None
                def launch(tx,name,log,label,pidfile=t.LIVE):calls.append((label,name));alive[0]=name
                with contextlib.ExitStack() as s:
                    for name,val in [('preflight',lambda *a:m),('identity',lambda *a:dict(pid=501,start_ticks=123)),('Transport',TX),('readback',lambda *a:None),('wait_exit',lambda *a,**k:0),('process',proc),('stop',stop),('launch',launch),('progress',lambda *a:dict(presents=10))]:s.enter_context(patch.object(t,name,val))
                    s.enter_context(patch.object(t.serial,'Serial',lambda *a,**k:UART()))
                    s.enter_context(patch.object(t,'open',lambda *a,**k:tempfile.TemporaryFile(),create=True))
                    s.enter_context(patch.object(t.fcntl,'flock',lambda *a:None));s.enter_context(patch.object(t.signal,'signal',lambda *a:None))
                    s.enter_context(patch.object(t.time,'sleep',lambda *a:None));s.enter_context(patch.object(t.time,'monotonic',mono))
                    s.enter_context(patch.dict(sys.modules,{'check_linux':types.SimpleNamespace(command=None)}))
                    s.enter_context(patch.object(sys,'argv',['trial','--bundle',str(root),'--out',str(root/'out')]))
                    s.enter_context(contextlib.redirect_stdout(io.StringIO()))
                    if fail:
                        with self.assertRaises((AssertionError,RuntimeError,KeyboardInterrupt)):t.main()
                    else:t.main()
                result=json.loads((root/'out/result.json').read_text())
                self.assertNotIn('cleanup_error',result)
                self.assertEqual(alive[0],m['program'] if fail is None else t.R3)
                if fail is None:self.assertTrue(result['passed']);self.assertEqual(len(result['scenes']),7)
                elif fail=='install':self.assertFalse(any(x[0]=='stop_r3' for x in calls))
                else:self.assertTrue(result['restored_r3'])


if __name__=='__main__':unittest.main()
