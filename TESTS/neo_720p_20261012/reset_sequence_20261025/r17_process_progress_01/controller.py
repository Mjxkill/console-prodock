#!/usr/bin/env python3
"""Bounded progress inspection of one identified Gowin R17 process, no build/load."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BUILD = ROOT/'tang/impl/console_neo_n56r17_gao_opcode'
PID = 2794912
LAUNCH_SHA = '268ff046be021a3369267eb550da5c17945477369d71629d0d40bd9fd9276c8c'
GDB_SHA = '3832cc070ae1716e322105d3b39fb398695e5f031c9d39224cf227a8c2b889f6'


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def identify():
    launch=BUILD/'route_launch.json'
    assert sha(launch)==LAUNCH_SHA, 'Launch record changed'
    expected=json.loads(launch.read_text())
    assert expected['pid']==PID
    proc=Path('/proc')/str(PID)
    assert (proc/'cwd').resolve(strict=True)==BUILD.resolve(strict=True), 'Another working directory'
    cmd=(proc/'cmdline').read_bytes().rstrip(b'\0').split(b'\0')
    assert cmd==[os.fsencode(expected['tool']), b'build.tcl'], 'Another process command'
    assert sha(proc/'exe')==expected['tool_sha256'], 'Another executable'
    stat=(proc/'stat').read_text().rsplit(')',1)[1].split()
    ticks=int(stat[19])
    boot=int(next(s.split()[1] for s in Path('/proc/stat').read_text().splitlines() if s.startswith('btime ')))
    start=boot+ticks/os.sysconf('SC_CLK_TCK')
    assert abs(start-expected['started_unix'])<5, 'PID reused or unexpected start time'
    status=(proc/'status').read_text()
    tracer=int(next(s.split()[1] for s in status.splitlines() if s.startswith('TracerPid:')))
    assert tracer==0, 'Another debugger is already attached'
    return dict(pid=PID,start_ticks=ticks,state=stat[0],start_unix=start,
                io=(proc/'io').read_text(),status=status)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check-only',action='store_true')
    a=p.parse_args()
    def interrupted(sig,frame): raise KeyboardInterrupt('Signal '+str(sig))
    for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,interrupted)
    identity=identify()
    assert sha(Path('/usr/bin/gdb'))==GDB_SHA
    assert sha(Path('/home/michael/gowin/IDE/lib/libgowin.so'))=='7e7920244fbfa518c228e51a2e8143c67d8c19cfba535d1c4d3700b780f10b4d'
    assert sha(HERE/'read_r17_progress.py')=='3fc494e4552bd5065a62ee756a55d628904a80a4caed1ee078750eae10486404'
    if a.check_only:
        print(json.dumps(dict(identified=True,pid=PID,state=identity['state'],
            start_ticks=identity['start_ticks'],attached=False)))
        return
    assert os.geteuid()==0, 'Root authentication needed for ptrace; kernel policy is not changed'
    out=HERE/'r17_process_progress_01'
    out.mkdir(exist_ok=False)
    (out/'controller.py').write_text(Path(__file__).read_text())
    (out/'payload.py').write_text((HERE/'read_r17_progress.py').read_text())
    owner=HERE.stat()
    os.chown(out,owner.st_uid,owner.st_gid)
    for p in out.iterdir():os.chown(p,owner.st_uid,owner.st_gid)
    r=dict(started_unix=time.time(),identity=identity,script_sha256=sha(Path(__file__)),
        scope='Two bounded progress reads of PID 2794912; no FPGA access, reroute, kernel-policy or design change',
        samples=[],complete=False)
    command=['/usr/bin/gdb','--batch','--nx','--nh','--readnever',
        '-iex','set auto-load off','-iex','set debuginfod enabled off',
        '-ex','set pagination off','-ex','set print frame-arguments none',
        '-ex',f'attach {PID}','-ex','thread apply all bt 24',
        '-ex','source '+str(HERE/'read_r17_progress.py'),'-ex','detach']
    try:
        for i in range(2):
            now=identify()
            assert now['start_ticks']==identity['start_ticks']
            path=out/f'stack_{i}.log'
            with path.open('x') as log:
                os.fchown(log.fileno(),owner.st_uid,owner.st_gid)
                child=subprocess.Popen(command,stdout=log,stderr=log,start_new_session=True)
                timed_out=False
                try:
                    rc=child.wait(timeout=15)
                except BaseException:
                    timed_out=True
                    for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,signal.SIG_IGN)
                    os.killpg(child.pid,signal.SIGTERM)
                    try: rc=child.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid,signal.SIGKILL);rc=child.wait()
                    raise
                finally:
                    r['samples'].append(dict(index=i,returncode=child.returncode,
                        timed_out=timed_out,log_sha256=sha(path)))
            after=identify()
            r['samples'][-1]['after_state']=after['state']
            assert rc==0, 'GDB failed; no further attachment requested'
            assert 'detached' in path.read_text().lower(), 'Detach confirmation missing'
            if i==0:time.sleep(30)
        r['complete']=True
    except BaseException as error:
        r['error']=repr(error)
        raise
    finally:
        try:r['after']=identify()
        except Exception as error:r['final_identity_error']=repr(error)
        r['finished_unix']=time.time()
        with (out/'result.json').open('x') as f:
            os.fchown(f.fileno(),owner.st_uid,owner.st_gid)
            json.dump(r,f,indent=2);f.write('\n')
        print(json.dumps(dict(complete=r['complete'],output=str(out),error=r.get('error'))))


if __name__=='__main__':main()
