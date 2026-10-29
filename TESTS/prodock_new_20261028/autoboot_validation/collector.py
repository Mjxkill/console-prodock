#!/usr/bin/env python3
"""Prepare-only by default; capture at most120s on new Pro Dock USB7.1.

No command sent and no GPU test. USB reconnects begin a new independent log
segment; an older success cannot certify the newest boot attempt.
"""
import argparse
import errno
import hashlib
import json
from pathlib import Path
import signal
import socket
import time
import serial_guard as guard

HERE=Path(__file__).resolve().parent
LIMIT=4*1024*1024


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def preflight(expected=None):
    m=json.loads((HERE/'manifest.json').read_text());digest=sha(HERE/'manifest.json')
    guard.need(expected is None or digest==expected,'Manifest differs')
    for name,v in m['files'].items():
        guard.need(Path(name).name==name,'Non-flat bundle file')
        p=HERE/name;guard.need(not p.is_symlink() and p.stat().st_size==v['bytes'] and sha(p)==v['sha256'],'Changed bundle file '+name)
    guard.need(m['port']==str(guard.PORT) and m['programmer']==guard.PROGRAMMER,'Wrong bundle target')
    return m,digest


def capture(io,out,seconds,clock=time.monotonic,sleep=time.sleep):
    """Bounded state machine tested with fake clocks/ports; no writes exposed."""
    guard.need(type(seconds) in (int,float) and 0<seconds<=120,'Capture must be1..120seconds')
    from boot_log import parse_boot
    end=clock()+seconds;segments=[];current=None;total=0;last_check=0
    error=None
    try:
        while clock()<end:
            if current is None:
                try:identity=io.open(timeout=min(5,max(.001,end-clock())))
                except FileNotFoundError:
                    sleep(min(.1,max(0,end-clock())));continue
                current={'index':len(segments),'identity':identity,'raw':bytearray(),'start_elapsed':seconds-(end-clock()),'ended':False}
                segments.append(current);last_check=clock()
            try:
                data=io.read(4096,min(.1,max(0,end-clock())))
                guard.need(total+len(data)<=LIMIT,'Capture output limit exceeded')
                current['raw'].extend(data);total+=len(data)
                if clock()-last_check>=.5:
                    last_check=clock()
                    if not io.connected():raise OSError(errno.ENODEV,'USB disconnected')
            except OSError as exc:
                if exc.errno not in (errno.EIO,errno.ENODEV,errno.ENOENT):raise
                current['ended']=True;current['disconnect_errno']=exc.errno
                io.close();current=None
    except BaseException as exc:error=repr(exc)
    finally:
        active=current is not None
        io.close()
        for s in segments:
            raw=bytes(s.pop('raw'));path=out/('capture_%03d.bin'%s['index']);path.write_bytes(raw)
            s.update(file=path.name,bytes=len(raw),sha256=sha(path),classification=parse_boot(raw))
    newest=segments[-1]['classification'] if segments else parse_boot(b'')
    return {'capture_completed':error is None,'error':error,'segments':segments,'last_connection_active':active,'bytes':total,'uart_tx_bytes':0,'log_checks_passed':bool(error is None and active and newest['boot_log_checks_passed']),'game_launch_observed':newest['game_launch_observed'],'gpu_tested':False,'powercycle_validated':False,'kernel_sha_measured':False,'game_sha_measured':False,'elapsed_seconds':seconds-(end-clock())}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',action='store_true');p.add_argument('--expected-manifest');p.add_argument('--review',type=Path);p.add_argument('--out',type=Path);p.add_argument('--seconds',type=float,default=120)
    a=p.parse_args();m,digest=preflight(a.expected_manifest)
    guard.need(0<a.seconds<=120,'Invalid duration')
    if not a.run:
        print(json.dumps({'prepared':True,'hardware':False,'manifest_sha256':digest,'port':str(guard.PORT),'programmer':guard.PROGRAMMER,'uart_tx_bytes':0}));return 0
    guard.need(a.review and a.out and a.expected_manifest,'Review, manifest and new output required')
    review=json.loads(a.review.read_text())
    association=guard.validate_review(review,digest,socket.gethostname().split('.')[0],time.time())
    program=guard.verify_program_result(review)
    a.out.mkdir(parents=True,exist_ok=False)
    result={'hardware':True,'manifest_sha256':digest,'review_sha256':sha(a.review),'association':association,'program_result':program,'programmer':guard.PROGRAMMER,'port':str(guard.PORT),'expected_game_sha256':guard.GAME_SHA,'expected_package_manifest_sha256':guard.PACKAGE_SHA,'expected_kernel_manifest_sha256':guard.KERNEL_MANIFEST_SHA,'fpga_writes':0,'sd_writes':0,'jtag_access':False,'gpu_tested':False,'powercycle_validated':False,'uart_tx_bytes':0,'log_checks_passed':False}
    def stop(sig,frame):raise InterruptedError('Signal '+str(sig))
    previous={s:signal.signal(s,stop) for s in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP)}
    try:
        with guard.diagnostic_lock():
            io=guard.PassiveUART();result.update(capture(io,a.out,a.seconds))
    except BaseException as exc:result['error']=repr(exc)
    finally:
        for s,h in previous.items():signal.signal(s,h)
        (a.out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'log_checks_passed':result['log_checks_passed'],'output':str(a.out),'gpu_tested':False,'powercycle_validated':False}))
    return 0 if result['log_checks_passed'] else 1

if __name__=='__main__':raise SystemExit(main())
