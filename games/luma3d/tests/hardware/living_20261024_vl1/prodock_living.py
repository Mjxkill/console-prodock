#!/usr/bin/env python3
"""One frozen living-valley trial; RAM only, current R3 preserved until ready."""
import argparse
import fcntl
import json
import re
import signal
import time
from pathlib import Path
import serial
from prodock_transport import Transport, RECEIVER_SHA
from prodock_valley_ab import process, stop, launch, progress, PORT, RELEASE
from prodock_valley_trial import sha, display, game_counters
from prodock_valley_benchmark import readback, supervisor, wait_exit, fields

R3_SHA = '131ff6d7ca404e0188bb7e0ff68c25bd2db29b52ae27c561e019f6c53dfcc270'
R3 = 'luma3d-b3v2'
LIVE = '/tmp/luma3d-live.pid'


def preflight(bundle):
    m = json.loads((bundle/'manifest.json').read_text())
    assert m['candidate'] and m['baseline']['sha256'] == R3_SHA
    assert re.fullmatch(r'luma3d-vl[0-9]+', m['program'])
    assert re.fullmatch(r'vl[0-9]+', m['tag'])
    assert m['helper'] == m['tag']+'-helper'
    for name, record in m['files'].items():
        assert re.fullmatch(r'[A-Za-z0-9_.-]+', name)
        p = bundle/name
        assert p.stat().st_size == record['bytes'] and sha(p) == record['sha256'], name
    for name in ('prodock_living.py', 'prodock_transport.py', 'prodock_valley_ab.py',
                 'prodock_valley_trial.py', 'prodock_valley_benchmark.py', 'check_linux.py', 'check_gpu_reloads.py'):
        assert sha(Path(__file__).with_name(name)) == m['files'][name]['sha256'], name
    frozen = json.loads((bundle/'game_manifest.json').read_text())
    assert frozen['riscv'] == m['game']
    d = m['delta']
    assert d['old_sha256'] == R3_SHA and d['new_sha256'] == m['game']['sha256']
    assert d['new_bytes'] == m['game']['bytes'] and d['new_crc32'] == m['game']['crc32']
    assert m['validation']['passed'] and not m['validation']['hardware']
    assert len(m['scenes']) == 7 and m['scenes'][0]['variant'] == 'r3'
    assert [s['pose'] for s in m['scenes'][1:]] == [0,90,1450,2330,3200,3800]
    for scene in m['scenes']:
        assert scene['pixels']['bytes'] == 192000
        assert scene['pixels']['sha256'] == scene['oracle']['image_sha256']
        if scene['variant'] == 'new':
            assert scene['hud']['bytes'] % 800 == 0 and 0 < scene['hud']['bytes'] <= 240000
    return m


def identity(tx, label):
    assert process(tx, label+'_alive', R3, LIVE)
    raw = tx.run(label+'_identity', 'p=`cat '+LIVE+'`; cat /proc/$p/stat; cat /proc/$p/cmdline; echo')
    line = re.search(rb'^(\d+) \('+R3.encode()+rb'\) ([^\r\n]+)', raw, re.M)
    assert line, 'Missing exact R3 stat identity'
    rest = line[2].split()
    assert rest[0] not in (b'Z', b'X') and len(rest) >= 20
    assert re.search(rb'^/tmp/'+R3.encode()+rb'(?:\x00|\r?$)', raw, re.M)
    return dict(pid=int(line[1]), start_ticks=int(rest[19]))


def parse(log, scene):
    assert fields(log,'LUMA3D_BENCHMARK') == dict(pose=scene['pose'],warmup=3,measured_frames=30,fixed_pose=1,hardware=1)
    r = fields(log,'LUMA3D_RESULT')
    assert r['frames'] == 30 and r['warmup'] == 3 and r['benchmark'] == r['hardware'] == 1 and r['elapsed'] > 0
    c = game_counters(log)
    assert c['frames'] == 33
    measured = fields(log,'LUMA3D_BENCHMARK_COUNTERS')
    for k in ('vertices','slivers'):
        assert c[k] == scene['oracle'][k]*33, (k,c[k],scene['oracle'][k])
        assert measured[k] == scene['oracle'][k]*30
    assert measured['raster_triangles'] == scene['oracle']['triangles']*30
    assert measured['cycles'] > 0
    if scene['variant'] == 'new':
        for k in ('commands','batches','draws_last','triangles_last'):
            assert r[k] == scene['host_benchmark'][k], (k,r[k],scene['host_benchmark'][k])
    return dict(result=r,measured=measured,counters=c,scope='30 fixed-pose frames after 3 warmup; no percentile or renderer-only A/B claim')


def verify_pixels(tx, helper, tag, ref):
    log = tx.run(tag+'_pixels',f'/tmp/{helper} pixels /tmp/{ref["file"]} page0 192000 {ref["crc32"]}',60)
    assert f'LUMA3D_PIXELS pixels=96000 mismatch=0 actual_crc={ref["crc32"]} expected_crc={ref["crc32"]}'.encode() in log


def verify_hud(tx, helper, tag, ref):
    for bank in (20,21):
        log = tx.run(tag+'_hud_'+str(bank),f'/tmp/{helper} hud /tmp/{ref["file"]} bank{bank} {ref["bytes"]} {ref["crc32"]}',60)
        assert f'LUMA3D_HUD bank={bank} bytes={ref["bytes"]} mismatch=0 actual_crc={ref["crc32"]} expected_crc={ref["crc32"]}'.encode() in log


def recover(tx, m, current, ever):
    if current:
        # An unpublished PID remains ambiguous: stop() raises rather than
        # starting a second process against the same GPU.
        stop(tx,current[0],'cleanup_candidate',current[1])
    if not ever and process(tx,'r3_still_alive',R3,LIVE):
        one=display(tx.run('preserved_display1','prodockctl display'));time.sleep(3)
        two=display(tx.run('preserved_display2','prodockctl display'))
        assert (two['presents']-one['presents'])&0xffffffff
        return two
    tag=m['tag']+'_restore';pidfile='/tmp/'+tag+'.pid'
    launch(tx,R3,tag+'.log','restore_r3',pidfile)
    result=progress(tx,R3,tag+'.log','restored_r3',pidfile)
    tx.run('publish_restored_pid','cp '+pidfile+' '+LIVE)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();m=preflight(a.bundle);a.out.mkdir(parents=True,exist_ok=False)
    from check_linux import command
    r=dict(passed=False,manifest_sha256=sha(a.bundle/'manifest.json'),game=m['game'],
           fpga='G22r0 continuity; G3D1 signature checked by renderer open, no JTAG/write',kernel=RELEASE.decode(),
           fpga_writes=0,kernel_writes=0,sd_writes=0,flash_writes=0,transfers=[],scenes=[])
    def interrupted(n,frame):raise KeyboardInterrupt('Signal '+str(n))
    signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGHUP,interrupted)
    with open('/tmp/prodock-diagnostic.lock','a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with serial.Serial(PORT,115200,timeout=.1,exclusive=True) as uart:
            tx=Transport(uart,command,a.out);stopped=False;current=None;ever=False
            try:
                uart.write(b'\n');time.sleep(.2);uart.read(16000)
                before=tx.run('before','uname -r; prodockctl info; prodockctl geometry; prodockctl display; cat /proc/mounts')
                assert re.search(rb'^'+RELEASE+rb'\r?$',before,re.M)
                assert b'GPU ABI=1 caps=000001ff DDR=00800000+90177536 ' in before
                assert b'GEOMETRY board=0 width=800 height=480 ' in before
                assert b'tmpfs /tmp tmpfs ' in before and not re.search(rb'^/dev/mmc\S* ',before,re.M)
                r['before']=display(before);r['initial_identity']=identity(tx,'initial_r3')
                tags=[m['tag']+'_'+str(i) for i in range(len(m['scenes']))]+[m['tag']+'_'+s for s in ('endurance','live','restore')]
                tx.run('fresh_names',' && '.join('test ! -f /tmp/'+t+'.pid' for t in tags)+f' && test ! -f /tmp/{m["program"]}')
                readback(tx,'receiver_readback','/tmp/luma-rx',1464,RECEIVER_SHA)
                for name in m['transfer_files']:
                    r['transfers'].append(tx.transfer(a.bundle/name,name))
                helper=m['helper'];tx.run('helper_mode','chmod 700 /tmp/'+helper)
                d=m['delta']
                installed=tx.run('install',f'/tmp/{helper} patch /tmp/{d["file"]} /tmp/{m["program"]} {d["patch_bytes"]} {d["patch_crc32"]} /tmp/{R3}',90)
                assert f'LUMA3D_UNPACK_OK bytes={m["game"]["bytes"]} crc32={m["game"]["crc32"]}'.encode() in installed
                tx.run('candidate_mode','chmod 700 /tmp/'+m['program'])
                for i,s in enumerate(m['scenes']):
                    for kind in ('pixels','hud') if s['variant']=='new' else ('pixels',):
                        ref=s[kind]
                        raw=tx.run(f'verify_{i}_{kind}',f'/tmp/{helper} verify /tmp/{ref["file"]} unused {ref["bytes"]} {ref["crc32"]}')
                        assert f'LUMA3D_VERIFY_OK bytes={ref["bytes"]} crc32={ref["crc32"]}'.encode() in raw
                assert identity(tx,'r3_before_switch')==r['initial_identity']
                print('LIVING_READY: transfer checked; first new valley will appear after baseline and a 10 second announcement',flush=True)
                stopped=True;stop(tx,R3,'stop_r3')
                r['released']=display(tx.run('released','prodockctl display'))
                for i,scene in enumerate(m['scenes']):
                    program=R3 if scene['variant']=='r3' else m['program'];tag=tags[i]
                    if i==1:
                        print('LIVING_FIRST_APPEARANCE_IN_10_SECONDS',flush=True);time.sleep(10)
                    current=(program,'/tmp/'+tag+'.pid');ever=True
                    initial=tx.run(tag+'_launch',supervisor(program,tag,scene['pose']))
                    code=wait_exit(uart,a.out,tag,initial=initial)
                    assert code==0,(tag,code)
                    log=tx.run(tag+'_log','cat /tmp/'+tag+'.log');current=None
                    record=parse(log,scene);record.update(pose=scene['pose'],variant=scene['variant'])
                    verify_pixels(tx,helper,tag,scene['pixels'])
                    if scene['variant']=='new':verify_hud(tx,helper,tag,scene['hud'])
                    record['display']=display(tx.run(tag+'_display','prodockctl display'))
                    r['scenes'].append(record)
                    print(f'{tag} pose={scene["pose"]}: pixels/HUD PASS, {record["result"]["fps"]} FPS',flush=True)
                tag=m['tag']+'_endurance';current=(m['program'],'/tmp/'+tag+'.pid')
                launch(tx,m['program'],tag+'.log','endurance_launch',current[1])
                r['warm_display']=progress(tx,m['program'],tag+'.log','warm',current[1])
                begin=time.monotonic();print('LIVING_ENDURANCE: 120 seconds, no UART writes',flush=True)
                while time.monotonic()-begin<120:time.sleep(min(5,max(0,120-(time.monotonic()-begin))))
                assert process(tx,'endurance_alive',m['program'],current[1])
                stop(tx,m['program'],'endurance_stop',current[1]);current=None
                log=tx.run('endurance_log','cat /tmp/'+tag+'.log')
                r['endurance']=fields(log,'LUMA3D_RESULT');r['story']=fields(log,'LUMA3D_STORY')
                assert r['endurance']['elapsed']>=120 and r['endurance']['frames']>1
                assert all(r['story'][k]==v for k,v in dict(phase=4,relay=3,discovered=1,collected=4,complete=1,auto=1).items())
                assert r['story']['sim']>=61.8
                r['endurance_counters']=game_counters(log)
                verify_hud(tx,helper,'completion',m['completion_hud'])
                r['after_endurance']=display(tx.run('after_endurance','prodockctl display'))
                tag=m['tag']+'_live';current=(m['program'],'/tmp/'+tag+'.pid')
                launch(tx,m['program'],tag+'.log','live_launch',current[1])
                r['live_display']=progress(tx,m['program'],tag+'.log','live',current[1])
                tx.run('publish_live_pid','cp '+current[1]+' '+LIVE)
                r['live_identity']=tx.run('live_identity','p=`cat '+LIVE+'`; cat /proc/$p/stat').decode(errors='replace')
                r['passed']=True;r['left_running']=m['program']+' automatic adventure; R3 executable preserved; no NEBULA'
            except BaseException as error:
                r['error']=repr(error)
                if stopped:
                    try:
                        uart.write(b'\x03');uart.flush();time.sleep(.3);uart.read(16000)
                        r['restored_display']=recover(tx,m,current,ever);r['restored_r3']=True
                    except BaseException as cleanup:r['cleanup_error']=repr(cleanup)
                raise
            finally:
                (a.out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)


if __name__=='__main__':main()
