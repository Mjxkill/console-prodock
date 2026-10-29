#!/usr/bin/env python3
"""Frozen valley: native first-frame oracle, two-minute run, then live display."""
import argparse,fcntl,hashlib,json,re,signal,sys,time
from pathlib import Path
import serial
from prodock_transport import Transport,RECEIVER_SHA
PORT='/dev/serial/by-id/usb-Electrosens_MegaPro_Console_11252024-if00'
RELEASE=b'6.12.112-prodock-luma3d-g3d1-r1'
GAME_SHA='216623767b298d0c13e3b35bfccdc088ca042c97d1ebc33beece415cea525951'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def display(data):
    lines=re.findall(rb'^DISPLAY [^\r\n]+',data,re.M);assert len(lines)==1
    values={k.decode():int(v) for k,v in re.findall(rb'\b(errors|uf|invalid|sprites|fault)=(\d+)\b',lines[0])}
    assert set(values)=={'errors','uf','invalid','sprites','fault'} and not any(values.values()),values
    values['presents']=int(re.search(rb'\bpresents=(\d+)',lines[0])[1]);return values
def process(tx,label):
    data=tx.run(label,'p=`cat /tmp/luma3d-live.pid`; if test -d /proc/$p; then cat /proc/$p/comm; cat /proc/$p/status; else echo STOPPED; fi')
    if re.search(rb'^STOPPED\r?$',data,re.M):return False
    assert re.search(rb'^luma3d-r1\r?$',data,re.M),'PID belongs to another program'
    state=re.search(rb'^State:\s+([A-Z])\s',data,re.M);assert state
    return state[1] not in (b'Z',b'X')
def stop(tx):
    if not process(tx,'process_before_stop'):return
    tx.run('stop','p=`cat /tmp/luma3d-live.pid`; test "`cat /proc/$p/comm`" = luma3d-r1 && kill -TERM "$p" && sleep 1')
    for i in range(8):
        if not process(tx,'process_stopped_'+str(i)):return
        time.sleep(1)
    raise RuntimeError('LUMA3D did not stop after TERM')
def game_counters(log):
    lines=re.findall(rb'^LUMA3D_COUNTERS [^\r\n]+',log,re.M);assert len(lines)==1
    d={k.decode():int(v) for k,v in re.findall(rb'(\w+)=(\d+)',lines[0])}
    assert all(d[k]==0 for k in ['errors','underflows','fault','geometry_errors']),d
    return d
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--bundle',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    m=json.loads((a.bundle/'manifest.json').read_text())
    for name,record in m['files'].items():
        source=a.bundle/name;assert source.stat().st_size==record['bytes'] and sha(source)==record['sha256'],name
    assert m['outputs']['luma3d.lz4']['sha256']==GAME_SHA
    assert m['outputs']['frame0.lz4']['sha256']=='e9449de1c075c23fa37e090c8edf1ce3eb728ea109d7f7b069e6b7fba9988fb4'
    assert sha(a.bundle/'uart-receiver')==RECEIVER_SHA
    assert sha(Path(__file__))==m['files']['prodock_valley_trial.py']['sha256']
    a.out.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(a.root/'tools'));from check_linux import command
    r={'passed':False,'game_sha256':GAME_SHA,'manifest_sha256':sha(a.bundle/'manifest.json'),
       'fpga':'G22r0 continuity from successful geometry_20261024_r1',
       'fpga_writes':0,'sd_writes':0,'flash_writes':0,'transfers':[],
       'scope':'First-frame pixel oracle + 120 seconds wall-clock auto traversal; no frame-time percentile claim'}
    def interrupted(signum,frame):raise KeyboardInterrupt('Signal '+str(signum))
    signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGHUP,interrupted)
    with open('/tmp/prodock-diagnostic.lock','a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        started=False
        with serial.Serial(PORT,115200,timeout=.1,exclusive=True) as uart:
            tx=Transport(uart,command,a.out)
            try:
                uart.write(b'\n');time.sleep(.2);uart.read(16000)
                before=tx.run('before','uname -r; prodockctl info; prodockctl display; cat /proc/mounts; ps')
                assert re.search(rb'^'+RELEASE+rb'\r?$',before,re.M)
                assert b'tmpfs /tmp tmpfs ' in before and not re.search(rb'^/dev/mmc\S* ',before,re.M)
                assert b'GPU ABI=1 caps=000001ff DDR=00800000+90177536 ' in before
                assert not re.search(rb'^\s*\d+[^\r\n]*\bluma3d-r1\b',before,re.M)
                r['before']=display(before);tx.bootstrap(a.bundle/'uart-receiver')
                for name in ['runtime-helper','luma3d.lz4']:
                    r['transfers'].append(tx.transfer(a.bundle/name,name))
                output=m['outputs']['luma3d.lz4']
                data=tx.run('unpack',f'chmod 700 /tmp/runtime-helper && /tmp/runtime-helper unpack /tmp/luma3d.lz4 /tmp/luma3d-r1 {output["bytes"]} {output["crc32"]}',60)
                assert f'LUMA3D_UNPACK_OK bytes={output["bytes"]} crc32={output["crc32"]}'.encode() in data
                tx.run('executable_mode','chmod 700 /tmp/luma3d-r1')
                started=True
                # The background supervisor records the real game's PID and exit.
                # The console shell stays available for bounded cleanup.
                tx.run('first_launch','( /tmp/luma3d-r1 --frames 1 --advance 0 < /dev/null > /tmp/luma3d-first.log 2>&1 & p=$!; echo "$p" > /tmp/luma3d-live.pid; wait "$p"; echo "$?" > /tmp/luma3d-first.exit ) < /dev/null > /tmp/luma3d-first-wrapper.log 2>&1 & echo FIRST_SUPERVISOR_LAUNCHED')
                deadline=time.monotonic()+120
                while time.monotonic()<deadline:
                    time.sleep(2)
                    state=tx.run('first_status','if test -f /tmp/luma3d-first.exit; then cat /tmp/luma3d-first.exit; else echo RUNNING; fi')
                    if re.search(rb'^RUNNING\r?$',state,re.M):continue
                    assert re.search(rb'^0\r?$',state,re.M),'First frame process failed'
                    break
                else:raise RuntimeError('First frame did not exit within 120 seconds')
                first=tx.run('first_frame','cat /tmp/luma3d-first.log')
                started=False
                assert b'LUMA3D_RESULT frames=1 ' in first;r['first_frame_counters']=game_counters(first)
                print('FIRST_FRAME visible; transferring independent pixel oracle',flush=True)
                r['transfers'].append(tx.transfer(a.bundle/'frame0.lz4','frame0.lz4'))
                output=m['outputs']['frame0.lz4']
                pixels=tx.run('pixels',f'/tmp/runtime-helper pixels /tmp/frame0.lz4 page0 {output["bytes"]} {output["crc32"]}',60)
                assert f'LUMA3D_PIXELS pixels=96000 mismatch=0 actual_crc={output["crc32"]} expected_crc={output["crc32"]}'.encode() in pixels
                r['after_pixels']=display(tx.run('after_pixels','prodockctl display'))
                started=True
                tx.run('endurance_launch','/tmp/luma3d-r1 < /dev/null > /tmp/luma3d-endurance.log 2>&1 & echo $! > /tmp/luma3d-live.pid')
                for i in range(12):
                    time.sleep(5)
                    assert process(tx,'endurance_warm_process_'+str(i)),'Endurance game exited during initialization'
                    log=tx.run('endurance_warm_log_'+str(i),'cat /tmp/luma3d-endurance.log')
                    if b'LUMA3D_PERF ' in log:break
                else:raise RuntimeError('No render progress before endurance window')
                begin=time.monotonic();print('ENDURANCE started; no UART commands for 120 seconds',flush=True)
                while time.monotonic()-begin<120:
                    time.sleep(max(0,min(10,120-(time.monotonic()-begin))))
                assert process(tx,'endurance_alive_at_deadline'),'Game exited before the endurance window ended'
                stop(tx);started=False
                log=tx.run('endurance_log','cat /tmp/luma3d-endurance.log')
                r['endurance_counters']=game_counters(log)
                result=re.search(rb'^LUMA3D_RESULT frames=(\d+) elapsed=([\d.]+) fps=([\d.]+) [^\r\n]+',log,re.M);assert result
                r['endurance']={'frames':int(result[1]),'elapsed':float(result[2]),'fps':float(result[3])}
                assert r['endurance']['frames']>1 and r['endurance']['elapsed']>=120
                r['performance_windows']=[{k.decode():float(v) for k,v in re.findall(rb'(\w+)=([\d.]+)',line)} for line in re.findall(rb'^LUMA3D_PERF [^\r\n]+',log,re.M)]
                r['after_endurance']=display(tx.run('after_endurance','prodockctl display'))
                started=True
                tx.run('live_launch','/tmp/luma3d-r1 < /dev/null > /tmp/luma3d-live.log 2>&1 & echo $! > /tmp/luma3d-live.pid')
                for i in range(12):
                    time.sleep(5)
                    assert process(tx,'live_process_'+str(i)),'Live game exited'
                    status=tx.run('live_log_'+str(i),'cat /tmp/luma3d-live.log')
                    if b'LUMA3D_PERF ' in status:break
                else:raise RuntimeError('No live render progress')
                one=display(tx.run('live_display_1','prodockctl display'));time.sleep(5)
                assert process(tx,'live_process_final')
                two=display(tx.run('live_display_2','prodockctl display'))
                assert (two['presents']-one['presents'])&0xffffffff
                r['live_display']=two;r['passed']=True;r['left_running']='LUMA3D real-time automatic traversal, fullscreen; no NEBULA'
            except BaseException as error:
                r['error']=repr(error)
                if started:
                    try:stop(tx);r['failed_game_stopped']=True
                    except BaseException as cleanup:r['cleanup_error']=repr(cleanup)
                raise
            finally:
                (a.out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)
if __name__=='__main__':main()
