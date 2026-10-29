#!/usr/bin/env python3
"""Renderer-only R2 trial; preserve the live R1 until installation is verified."""
import argparse,fcntl,json,re,signal,sys,time
from pathlib import Path
import serial
from prodock_transport import Transport,RECEIVER_SHA
from prodock_valley_trial import sha,display,game_counters
PORT='/dev/serial/by-id/usb-Electrosens_MegaPro_Console_11252024-if00'
OLD_SHA='216623767b298d0c13e3b35bfccdc088ca042c97d1ebc33beece415cea525951'
NEW_SHA='05b64630c267e364fa2bda14b64406cfa2eb1ae8c78ba58bc2b9ed4e053053f5'
RELEASE=b'6.12.112-prodock-luma3d-g3d1-r1'
class UnpublishedPID(RuntimeError):pass
def process(tx,label,expected,pidfile='/tmp/luma3d-live.pid'):
    data=tx.run(label,'if test -f '+pidfile+'; then p=`cat '+pidfile+'`; if test -d /proc/$p; then cat /proc/$p/comm; cat /proc/$p/status; else echo STOPPED; fi; else echo UNPUBLISHED; fi')
    if re.search(rb'^UNPUBLISHED\r?$',data,re.M):raise UnpublishedPID(pidfile)
    if re.search(rb'^STOPPED\r?$',data,re.M):return False
    state=re.search(rb'^State:\s+([A-Z])\s',data,re.M);assert state
    if state[1] in (b'Z',b'X'):return False
    assert re.search(rb'^'+expected.encode()+rb'\r?$',data,re.M),'PID belongs to another application'
    return True
def stop(tx,expected,label,pidfile='/tmp/luma3d-live.pid'):
    for i in range(3):
        try:
            alive=process(tx,label+'_before_'+str(i),expected,pidfile);break
        except UnpublishedPID:
            if i==2:raise
            time.sleep(1)
    if not alive:return
    tx.run(label+'_term','p=`cat '+pidfile+'`; test "`cat /proc/$p/comm`" = '+expected+' && kill -TERM "$p" && sleep 1')
    for i in range(8):
        if not process(tx,label+'_after_'+str(i),expected,pidfile):return
        time.sleep(1)
    raise RuntimeError('Game did not stop: '+expected)
def launch(tx,program,log,label,pidfile='/tmp/luma3d-live.pid'):
    tx.run(label,f'/tmp/{program} < /dev/null > /tmp/{log} 2>&1 & echo $! > {pidfile}')
def progress(tx,program,log,label,pidfile='/tmp/luma3d-live.pid'):
    for i in range(12):
        time.sleep(5);assert process(tx,label+'_process_'+str(i),program,pidfile)
        data=tx.run(label+'_log_'+str(i),'cat /tmp/'+log)
        if b'LUMA3D_PERF ' in data:break
    else:raise RuntimeError('No rendering progress')
    one=display(tx.run(label+'_display_1','prodockctl display'));time.sleep(3)
    assert process(tx,label+'_process_final',program,pidfile)
    two=display(tx.run(label+'_display_2','prodockctl display'))
    assert (two['presents']-one['presents'])&0xffffffff
    return two
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--bundle',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    m=json.loads((a.bundle/'manifest.json').read_text());delta=m['delta']
    assert delta['old_sha256']==OLD_SHA and delta['new_sha256']==m['game']['sha256']==NEW_SHA
    assert m['reference']['sha256']=='e9449de1c075c23fa37e090c8edf1ce3eb728ea109d7f7b069e6b7fba9988fb4'
    for name,v in m['files'].items():
        f=a.bundle/name;assert f.stat().st_size==v['bytes'] and sha(f)==v['sha256'],name
    for name in ('check_linux.py','check_gpu_reloads.py'):
        assert sha(a.root/'tools'/name)==m['shared_tools'][name],name
    assert sha(Path(__file__))==m['files']['prodock_valley_ab.py']['sha256']
    a.out.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(a.root/'tools'));from check_linux import command
    r={'passed':False,'manifest_sha256':sha(a.bundle/'manifest.json'),'game':m['game'],'transfers':[],
       'fpga':'G22r0 unchanged','kernel':RELEASE.decode(),'fpga_writes':0,'sd_writes':0,'flash_writes':0,
       'scope':'R2 renderer only; unchanged world and first-frame reference; 30 seconds without UART after warmup'}
    def interrupted(signum,frame):raise KeyboardInterrupt('Signal '+str(signum))
    signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGHUP,interrupted)
    with open('/tmp/prodock-diagnostic.lock','a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        stopped_r1=False;r2_started=False;r2_ever=False;r2_pidfile=None
        with serial.Serial(PORT,115200,timeout=.1,exclusive=True) as uart:
            tx=Transport(uart,command,a.out)
            try:
                uart.write(b'\n');time.sleep(.2);uart.read(16000)
                before=tx.run('before','uname -r; prodockctl display; cat /proc/mounts')
                assert re.search(rb'^'+RELEASE+rb'\r?$',before,re.M)
                assert b'tmpfs /tmp tmpfs ' in before and not re.search(rb'^/dev/mmc\S* ',before,re.M)
                r['before']=display(before);assert process(tx,'r1_initial','luma3d-r1')
                tx.run('fresh_launch_files','test ! -f /tmp/luma3d-r2-first.pid && test ! -f /tmp/luma3d-r2-endurance.pid && test ! -f /tmp/luma3d-r2-live.pid')
                # Reuse only after exact readback of the receiver installed in R1.
                data=tx.run('receiver_readback','od -b -v /tmp/luma-rx');octets=[]
                for line in data.replace(b'\r',b'').splitlines():
                    if re.fullmatch(rb'[0-7]{7,} (?:[0-7]{3} ?){1,16}',line.strip()):octets.extend(int(x,8) for x in line.split()[1:])
                import hashlib
                assert len(octets)==1464 and hashlib.sha256(bytes(octets)).hexdigest()==RECEIVER_SHA
                for name in ['runtime-helper-r2','luma3d-r2.delta.lz4']:
                    r['transfers'].append(tx.transfer(a.bundle/name,name))
                tx.run('helper_mode','chmod 700 /tmp/runtime-helper-r2')
                verify=tx.run('retained_reference','/tmp/runtime-helper-r2 verify /tmp/frame0.lz4 unused 192000 b43a5e60')
                assert b'LUMA3D_VERIFY_OK bytes=192000 crc32=b43a5e60' in verify
                installed=tx.run('patch',f'/tmp/runtime-helper-r2 patch /tmp/luma3d-r2.delta.lz4 /tmp/luma3d-r2 {delta["patch_bytes"]} {delta["patch_crc32"]} /tmp/luma3d-r1',60)
                assert f'LUMA3D_UNPACK_OK bytes={delta["new_bytes"]} crc32={delta["new_crc32"]}'.encode() in installed
                tx.run('new_mode','chmod 700 /tmp/luma3d-r2')
                assert process(tx,'r1_preserved_until_ready','luma3d-r1')
                print('R2_READY_TO_SWITCH: transfer and reconstruction verified; first native R2 test follows',flush=True)
                # Brief announcement window, not an approval or benchmark delay.
                time.sleep(10)
                stopped_r1=True;stop(tx,'luma3d-r1','stop_r1')
                r['gpu_released']=display(tx.run('gpu_released','prodockctl info; prodockctl display'))
                r2_started=True;r2_ever=True;r2_pidfile='/tmp/luma3d-r2-first.pid'
                tx.run('first_launch','( /tmp/luma3d-r2 --frames 1 --advance 0 < /dev/null > /tmp/luma3d-r2-first.log 2>&1 & p=$!; echo "$p" > /tmp/luma3d-r2-first.pid; wait "$p"; echo "$?" > /tmp/luma3d-r2-first.exit ) < /dev/null > /tmp/luma3d-r2-first-wrapper.log 2>&1 & echo FIRST_SUPERVISOR_LAUNCHED')
                deadline=time.monotonic()+120
                while time.monotonic()<deadline:
                    time.sleep(2)
                    state=tx.run('first_status','if test -f /tmp/luma3d-r2-first.exit; then cat /tmp/luma3d-r2-first.exit; else echo RUNNING; fi')
                    if re.search(rb'^RUNNING\r?$',state,re.M):continue
                    assert re.search(rb'^0\r?$',state,re.M),'First frame failed';break
                else:raise RuntimeError('First frame timeout')
                first=tx.run('first_frame','cat /tmp/luma3d-r2-first.log');r2_started=False
                assert b'LUMA3D_RESULT frames=1 ' in first;r['first_counters']=game_counters(first)
                pixels=tx.run('pixels','/tmp/runtime-helper-r2 pixels /tmp/frame0.lz4 page0 192000 b43a5e60',60)
                assert b'LUMA3D_PIXELS pixels=96000 mismatch=0 actual_crc=b43a5e60 expected_crc=b43a5e60' in pixels
                print('R2 first-frame pixels PASS; starting automatic traversal',flush=True)
                r2_started=True;r2_pidfile='/tmp/luma3d-r2-endurance.pid';launch(tx,'luma3d-r2','luma3d-r2-endurance.log','endurance_launch',r2_pidfile)
                r['warm_display']=progress(tx,'luma3d-r2','luma3d-r2-endurance.log','warm',r2_pidfile)
                begin=time.monotonic();print('R2 quiet window: 30 seconds, no UART commands',flush=True)
                while time.monotonic()-begin<30:time.sleep(max(0,min(5,30-(time.monotonic()-begin))))
                assert process(tx,'alive_at_deadline','luma3d-r2',r2_pidfile)
                stop(tx,'luma3d-r2','stop_endurance',r2_pidfile);r2_started=False
                log=tx.run('endurance_log','cat /tmp/luma3d-r2-endurance.log')
                r['counters']=game_counters(log)
                result=re.search(rb'^LUMA3D_RESULT frames=(\d+) elapsed=([\d.]+) fps=([\d.]+) [^\r\n]+',log,re.M);assert result
                r['endurance']={'frames':int(result[1]),'elapsed':float(result[2]),'fps':float(result[3])}
                assert r['endurance']['frames']>1 and r['endurance']['elapsed']>=30
                r['performance_windows']=[{k.decode():float(v) for k,v in re.findall(rb'(\w+)=([\d.]+)',line)} for line in re.findall(rb'^LUMA3D_PERF [^\r\n]+',log,re.M)]
                r['gpu_windows']=[{k.decode():int(v) for k,v in re.findall(rb'(\w+)=(\d+)',line)} for line in re.findall(rb'^LUMA3D_WINDOW [^\r\n]+',log,re.M)]
                assert len(r['gpu_windows'])>=6 and len(r['gpu_windows'])==len(r['performance_windows'])
                assert sum(w['cycles'] for w in r['gpu_windows'])==r['gpu_windows'][-1]['cycles_accumulated']
                r['after']=display(tx.run('after','prodockctl display'))
                r2_started=True;r2_pidfile='/tmp/luma3d-r2-live.pid';launch(tx,'luma3d-r2','luma3d-r2-live.log','live_launch',r2_pidfile)
                r['live_display']=progress(tx,'luma3d-r2','luma3d-r2-live.log','live',r2_pidfile)
                tx.run('publish_live_pid','cp /tmp/luma3d-r2-live.pid /tmp/luma3d-live.pid')
                r['passed']=True;r['left_running']='R2 automatic real-time valley; R1 executable preserved; no NEBULA'
            except BaseException as error:
                r['error']=repr(error)
                if stopped_r1:
                    try:
                        # Cancel any partially transmitted shell line before PID queries.
                        uart.write(b'\x03');uart.flush();time.sleep(.3);uart.read(16000)
                        if r2_started:stop(tx,'luma3d-r2','stop_failed_r2',r2_pidfile)
                        # Before R2 was started, a failed R1 stop may leave it alive.
                        if not r2_ever and process(tx,'possible_r1','luma3d-r1'):
                            r['restored_display']=progress(tx,'luma3d-r1','luma3d-live.log','old_r1')
                        else:
                            launch(tx,'luma3d-r1','luma3d-r1-restored.log','restore_r1')
                            r['restored_display']=progress(tx,'luma3d-r1','luma3d-r1-restored.log','restored_r1')
                        r['restored_r1']=True
                    except BaseException as cleanup:r['cleanup_error']=repr(cleanup)
                raise
            finally:
                (a.out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)
if __name__=='__main__':main()
