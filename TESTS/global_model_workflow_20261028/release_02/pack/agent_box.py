"""Trusted tool implementation inside the isolated PID/filesystem/network namespace."""
import ctypes
import json
import os
from pathlib import Path
import resource
import selectors
import signal
import socket
import subprocess
import sys
import time


def protect():
    # Tools must not reopen the MCP server's stdio through /proc/1/fd or ptrace.
    libc=ctypes.CDLL(None,use_errno=True)
    if libc.prctl(4,0,0,0,0)!=0:raise OSError(ctypes.get_errno(),'PR_SET_DUMPABLE')
    signal.signal(signal.SIGTERM,lambda *_:sys.exit(143))


def limits():
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
    resource.setrlimit(resource.RLIMIT_FSIZE,(64*1024**2,64*1024**2))


def execute(argv,timeout):
    if not isinstance(argv,list) or not argv or len(argv)>128 or any(
            not isinstance(a,str) or not a or '\0' in a or len(a)>16384 for a in argv):
        raise ValueError('Invalid argv')
    start=time.monotonic();data=bytearray();over=False;expired=False
    proc=subprocess.Popen(argv,cwd='/work',stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,start_new_session=True,close_fds=True,preexec_fn=limits,
        env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','HOME':'/tmp',
             'PYTHONNOUSERSITE':'1','PYTHONDONTWRITEBYTECODE':'1'})
    selector=selectors.DefaultSelector();selector.register(proc.stdout,selectors.EVENT_READ)
    try:
        while selector.get_map():
            if time.monotonic()-start>timeout:expired=True;break
            for key,_ in selector.select(.1):
                chunk=os.read(key.fd,8192)
                if not chunk:selector.unregister(key.fileobj);continue
                data.extend(chunk)
                if len(data)>131072:over=True;break
            if over:break
        if not over and not expired:
            try:proc.wait(timeout=max(.001,timeout-(time.monotonic()-start)))
            except subprocess.TimeoutExpired:expired=True
    finally:
        # Even a successful shell must not leave background children in its
        # session. The namespace is torn down when the trusted server exits.
        try:os.killpg(proc.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        proc.wait();selector.close();proc.stdout.close()
    return dict(returncode=proc.returncode,timeout=expired,output_limited=over,
                elapsed_seconds=time.monotonic()-start,stdout=data[:131072].decode(errors='replace'))


def tests(policy):
    records=[execute(command,policy['timeout_seconds']) for command in policy['tests']]
    return dict(test_results=records,test_runs=len(records),
                test_failures=sum(r['returncode']!=0 for r in records),
                passed=all(r['returncode']==0 and not r['timeout'] and not r['output_limited'] for r in records))


def preflight():
    checks={}
    checks['pid1']=os.getpid()==1
    checks['private_root']=not Path('/home/michael').exists() and not Path('/sys').exists()
    checks['no_credentials']=not any(k in os.environ for k in ('OLLAMA_API_KEY','AWS_SECRET_ACCESS_KEY','SSH_AUTH_SOCK'))
    checks['minimal_devices']=not Path('/dev/bus/usb').exists() and not Path('/dev/ttyUSB0').exists()
    try:
        sock=socket.create_connection(('192.0.2.1',9),timeout=.2);sock.close();checks['network_unreachable']=False
    except OSError:checks['network_unreachable']=True
    probe=execute(['/usr/bin/python3','-c',
        'import os;\ntry: os.open("/proc/1/fd/1",os.O_WRONLY); raise SystemExit(1)\nexcept PermissionError: pass'],2)
    checks['parent_stdio_protected']=probe['returncode']==0
    return dict(passed=all(checks.values()),checks=checks)


if __name__=='__main__':
    protect()
    policy=json.loads(Path('/control/policy.json').read_text())
    print(json.dumps(preflight() if sys.argv[1]=='preflight' else tests(policy)))
