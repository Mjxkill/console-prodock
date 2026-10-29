#!/usr/bin/env python3
"""Same-content art3/terrain-order A/B; RAM only, art3 is the sole fallback."""
import argparse
import fcntl
import json
import re
import statistics
import signal
import struct
import time
from pathlib import Path
import serial
from prodock_transport import Transport, RECEIVER_SHA
from prodock_valley_ab import process, stop, launch, progress, PORT, RELEASE
from prodock_valley_trial import sha, display, game_counters
from prodock_valley_benchmark import readback, supervisor, wait_exit, fields

BASE_SHA = '7fa1062373664d977c26bf6df2a4a5075d64061b967fc3d6d9b831a841302882'
NEW_SHA = '8613a379771508cc07d6709a5b49f37a72fe0e241775374ccfc6be7d52d19117'
BASE = 'luma3d-vl2'
LIVE = '/tmp/luma3d-live.pid'


def schedule():
    result=[]
    for i,pose in enumerate((0,90,1450,2330,3200,3800)):
        result.extend((pose,v) for v in (('art3','new') if i%2==0 else ('new','art3')))
    return result+[(0,'art3')]


def decision(scenes, limits):
    assert [(s['pose'],s['variant']) for s in scenes] == schedule()
    pairs=[]
    for i in range(0,12,2):
        pair={s['variant']:s for s in scenes[i:i+2]}
        # Use unrounded elapsed/frame duration, not the printed 2-decimal FPS.
        base=pair['art3']['result'];new=pair['new']['result']
        assert base['frames']==new['frames']==30 and min(base['elapsed'],new['elapsed'])>0
        gain=base['elapsed']/new['elapsed']-1
        pairs.append(dict(pose=scenes[i]['pose'],gain=gain,art3_fps=30/base['elapsed'],candidate_fps=30/new['elapsed']))
    drift=scenes[0]['result']['elapsed']/scenes[-1]['result']['elapsed']-1
    median=statistics.median(p['gain'] for p in pairs)
    accepted=median>=limits['median_gain_min'] and min(p['gain'] for p in pairs)>=limits['pose_gain_min'] and abs(drift)<=limits['baseline_drift_max']
    return dict(accepted=accepted,median_gain=median,baseline_drift=drift,poses=pairs,limits=limits,
                scope='One prespecified 30-frame window per pair; terminal witness detects drift, no p95 or statistical confidence claim')


def preflight(bundle):
    m = json.loads((bundle/'manifest.json').read_text())
    assert m['candidate'] and m['baseline']['sha256'] == BASE_SHA and m['game']['sha256'] == NEW_SHA
    assert re.fullmatch(r'luma3d-to[0-9]+', m['program'])
    assert re.fullmatch(r'to[0-9]+', m['tag'])
    assert m['helper'] == m['tag']+'-helper'
    for name, record in m['files'].items():
        assert re.fullmatch(r'[A-Za-z0-9_.-]+', name)
        p = bundle/name
        assert p.stat().st_size == record['bytes'] and sha(p) == record['sha256'], name
    for name in ('prodock_order.py', 'prodock_transport.py', 'prodock_valley_ab.py',
                 'prodock_valley_trial.py', 'prodock_valley_benchmark.py', 'check_linux.py', 'check_gpu_reloads.py'):
        assert sha(Path(__file__).with_name(name)) == m['files'][name]['sha256'], name
    frozen = json.loads((bundle/'game_manifest.json').read_text())
    assert frozen['riscv'] == m['game']
    d = m['delta']
    assert d['old_sha256'] == BASE_SHA and d['new_sha256'] == m['game']['sha256']
    assert d['new_bytes'] == m['game']['bytes'] and d['new_crc32'] == m['game']['crc32']
    assert m['validation']['passed'] and not m['validation']['hardware']
    assert m['validation']['runtime'] == m['game']
    assert m['transfer_files'] == [m['helper'],m['delta']['file']]
    assert [(s['pose'],s['variant']) for s in m['scenes']] == schedule()
    assert m['acceptance'] == dict(median_gain_min=.05,pose_gain_min=-.03,baseline_drift_max=.03)
    assert m['path_validation']['exact'] and len(m['path_validation']['records'])==52
    for scene in m['scenes']:
        assert scene['pixels']['bytes'] == 192000
        assert scene['pixels']['sha256'] == scene['oracle']['image_sha256']
        assert scene['hud']['bytes'] % 800 == 0 and 0 < scene['hud']['bytes'] <= 240000
        for ref in (scene['pixels'],scene['hud']):
            assert ref['file'] in m['files']
    return m


def identity(tx, label):
    assert process(tx, label+'_alive', BASE, LIVE)
    raw = tx.run(label+'_identity', 'p=`cat '+LIVE+'`; cat /proc/$p/stat; cat /proc/$p/cmdline; echo')
    line = re.search(rb'^(\d+) \('+BASE.encode()+rb'\) ([^\r\n]+)', raw, re.M)
    assert line, 'Missing exact BASE stat identity'
    rest = line[2].split()
    assert rest[0] not in (b'Z', b'X') and len(rest) >= 20
    assert re.search(rb'^/tmp/'+BASE.encode()+rb'(?:\x00|\r?$)', raw, re.M)
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
    for k in ('commands','batches','draws_last','triangles_last'):
        assert r[k] == scene['host_benchmark'][k], (k,r[k],scene['host_benchmark'][k])
    return dict(result=r,measured=measured,counters=c,scope='30 fixed-pose frames after 3 warmup; same content/camera; no percentile claim')


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
    if not ever and process(tx,'art3_still_alive',BASE,LIVE):
        one=display(tx.run('preserved_display1','prodockctl display'));time.sleep(3)
        two=display(tx.run('preserved_display2','prodockctl display'))
        assert (two['presents']-one['presents'])&0xffffffff
        return two
    tag=m['tag']+'_restore';pidfile='/tmp/'+tag+'.pid'
    launch(tx,BASE,tag+'.log','restore_art3',pidfile)
    result=progress(tx,BASE,tag+'.log','restored_art3',pidfile)
    tx.run('publish_restored_pid','cp '+pidfile+' '+LIVE)
    return result


def abort_receiver(tx, uart, out):
    if not getattr(tx,'receiver_active',False):return
    # Fill any interrupted <=1024-byte block/header before a zero-length
    # protocol record. The receiver restores termios on either F or D.
    packet=bytes(1036)+struct.pack('<4sIII',b'LMA1',0,0,0)
    for offset in range(0,len(packet),16):
        uart.write(packet[offset:offset+16]);uart.flush();time.sleep(.002)
    data=bytearray();deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        data.extend(uart.read(4096))
        if re.search(rb'[FD].{4}',data,re.S):break
    else:
        # The send may have been interrupted before the receiver started, or
        # just after its D response. Cancel a possible partial shell command.
        uart.write(b'\x03');uart.flush();time.sleep(.2)
        (out/'receiver_abort_timeout.log').write_bytes(bytes(data)+uart.read(4096))
        raise RuntimeError('Receiver exit not confirmed; partial shell line cancelled')
    (out/'receiver_abort.log').write_bytes(data);tx.receiver_active=False
    uart.write(b'\x03');uart.flush();time.sleep(.2);uart.read(4096)
    tx.run('receiver_shell_restored','echo LUMA_RECEIVER_STOPPED')


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
                # The live game owns /dev/prodock-gpu exclusively. R17's
                # prodockctl also predates its later geometry subcommand.
                before=tx.run('before','uname -r; prodockctl display; cat /proc/mounts')
                assert re.search(rb'^'+RELEASE+rb'\r?$',before,re.M)
                assert b'tmpfs /tmp tmpfs ' in before and not re.search(rb'^/dev/mmc\S* ',before,re.M)
                r['before']=display(before);r['initial_identity']=identity(tx,'initial_art3')
                tags=[m['tag']+'_'+str(i) for i in range(len(m['scenes']))]+[m['tag']+'_'+s for s in ('endurance','live','restore')]
                names=[t+'.pid' for t in tags]+[m['program']]+m['transfer_files']
                tx.run('fresh_names',' && '.join('test ! -f /tmp/'+n for n in names))
                readback(tx,'receiver_readback','/tmp/luma-rx',1464,RECEIVER_SHA)
                for name in m['transfer_files']:
                    tx.receiver_active=True
                    r['transfers'].append(tx.transfer(a.bundle/name,name))
                helper=m['helper'];tx.run('helper_mode','chmod 700 /tmp/'+helper)
                d=m['delta']
                installed=tx.run('install',f'/tmp/{helper} patch /tmp/{d["file"]} /tmp/{m["program"]} {d["patch_bytes"]} {d["patch_crc32"]} /tmp/{BASE}',90)
                assert f'LUMA3D_UNPACK_OK bytes={m["game"]["bytes"]} crc32={m["game"]["crc32"]}'.encode() in installed
                tx.run('candidate_mode','chmod 700 /tmp/'+m['program'])
                seen=set()
                for i,s in enumerate(m['scenes']):
                    for kind in ('pixels','hud'):
                        ref=s[kind]
                        if ref['file'] in seen:continue
                        seen.add(ref['file'])
                        raw=tx.run(f'verify_{i}_{kind}',f'/tmp/{helper} verify /tmp/{ref["file"]} unused {ref["bytes"]} {ref["crc32"]}')
                        assert f'LUMA3D_VERIFY_OK bytes={ref["bytes"]} crc32={ref["crc32"]}'.encode() in raw
                ref=m['completion_hud']
                raw=tx.run('verify_completion',f'/tmp/{helper} verify /tmp/{ref["file"]} unused {ref["bytes"]} {ref["crc32"]}')
                assert f'LUMA3D_VERIFY_OK bytes={ref["bytes"]} crc32={ref["crc32"]}'.encode() in raw
                assert identity(tx,'art3_before_switch')==r['initial_identity']
                print('ORDER_READY: transfer checked; first candidate after baseline and a 10 second announcement',flush=True)
                stopped=True;stop(tx,BASE,'stop_art3')
                released=tx.run('released','prodockctl info; prodockctl display')
                assert b'GPU ABI=1 caps=000001ff DDR=00800000+90177536 ' in released
                r['released']=display(released)
                for i,scene in enumerate(m['scenes']):
                    program=BASE if scene['variant']=='art3' else m['program'];tag=tags[i]
                    if i==1:
                        print('ORDER_FIRST_APPEARANCE_IN_10_SECONDS',flush=True);time.sleep(10)
                    current=(program,'/tmp/'+tag+'.pid');ever=True
                    initial=tx.run(tag+'_launch',supervisor(program,tag,scene['pose']))
                    code=wait_exit(uart,a.out,tag,initial=initial)
                    assert code==0,(tag,code)
                    log=tx.run(tag+'_log','cat /tmp/'+tag+'.log');current=None
                    record=parse(log,scene);record.update(pose=scene['pose'],variant=scene['variant'])
                    verify_pixels(tx,helper,tag,scene['pixels'])
                    verify_hud(tx,helper,tag,scene['hud'])
                    record['display']=display(tx.run(tag+'_display','prodockctl display'))
                    r['scenes'].append(record)
                    print(f'{tag} pose={scene["pose"]}: pixels/HUD PASS, {record["result"]["fps"]} FPS',flush=True)
                r['comparison']=decision(r['scenes'],m['acceptance'])
                r['candidate_accepted']=r['comparison']['accepted']
                if not r['candidate_accepted']:
                    tag=m['tag']+'_restore';current=(BASE,'/tmp/'+tag+'.pid')
                    launch(tx,BASE,tag+'.log','restore_art3',current[1])
                    r['restored_display']=progress(tx,BASE,tag+'.log','restored_art3',current[1])
                    tx.run('publish_restored_pid','cp '+current[1]+' '+LIVE)
                    r['restored_art3']=True
                    r['live_identity']=tx.run('live_identity','p=`cat '+LIVE+'`; cat /proc/$p/stat').decode(errors='replace')
                    r['passed']=True;r['left_running']=BASE+' automatic adventure; candidate not promoted; no NEBULA'
                    return
                tag=m['tag']+'_endurance';current=(m['program'],'/tmp/'+tag+'.pid')
                launch(tx,m['program'],tag+'.log','endurance_launch',current[1])
                r['warm_display']=progress(tx,m['program'],tag+'.log','warm',current[1])
                begin=time.monotonic();print('ORDER_ENDURANCE: 120 seconds, no UART writes',flush=True)
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
                r['passed']=True;r['left_running']=m['program']+' automatic adventure; art3 executable preserved; no NEBULA'
            except BaseException as error:
                r['error']=repr(error)
                try:abort_receiver(tx,uart,a.out)
                except BaseException as abort:r['receiver_abort_error']=repr(abort)
                if stopped:
                    try:
                        uart.write(b'\x03');uart.flush();time.sleep(.3);uart.read(16000)
                        r['restored_display']=recover(tx,m,current,ever);r['restored_art3']=True
                    except BaseException as cleanup:r['cleanup_error']=repr(cleanup)
                raise
            finally:
                (a.out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)


if __name__=='__main__':main()
