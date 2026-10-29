#!/usr/bin/env python3
"""Delete two attributed obsolete benchmarks; root-reviewed, prepare-only default.

No game signal, launch, receiver, SD, FPGA or broad deletion. Runtime transport
is reused from the immutable FC1 stage bundle through an explicit --runtime.
An uncertain shell permits no further query or automatic recovery command.
"""
import argparse
import fcntl
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import signal
import socket
import stat
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
RUNTIME_SHA = '0fe854aa271743c1ad838feaa63fa0984fa326da75471ea73d8c5bd7785a6afd'
TARGETS = {
    '/tmp/gm1-baseline': (8619636, '028214fd64380ced18558658c3c20641c945df00505b9443c41ddb8f865d886f', '80db0d69'),
    '/tmp/gm1-candidate': (10029328, '349ff11131b3b97d1787b0815725dff367c99e75b637e59853bf2c25b3f1b0cb', '1accf6e5'),
}


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_runtime(runtime):
    """Pin every reusable module before importing; no dependency is rewritten."""
    need(not runtime.is_symlink() and sha(runtime/'plan.json') == RUNTIME_SHA, 'Wrong runtime')
    plan = json.loads((runtime/'plan.json').read_text())
    for name, record in plan['files'].items():
        need(re.fullmatch(r'[A-Za-z0-9_.-]+', name), 'Unsafe runtime member')
        path = runtime/name
        need(not path.is_symlink() and sha(path) == record['sha256'], 'Runtime changed '+name)
    sys.path.insert(0, str(runtime))
    module = importlib.import_module('transfer')
    need(Path(module.__file__).resolve() == runtime/'transfer.py', 'Wrong imported runtime')
    module.preflight()
    return module


def preflight(runtime):
    plan = json.loads((HERE/'plan.json').read_text())
    need(__debug__ and plan['runtime_plan_sha256'] == RUNTIME_SHA, 'Invalid mode/runtime')
    need(plan['archives_verified'] is True and plan['inventory']['passed'] is True and plan['inventory']['identity'] == dict(pid=3940,start_ticks=35705238), 'Missing archived/live provenance')
    actual = {r['remote']:(r['bytes'],r['sha256'],r['crc32']) for r in plan['targets']}
    need(actual == TARGETS and len(plan['targets']) == 2, 'Deletion allowlist changed')
    need(set(plan['files']) == {p.name for p in HERE.glob('*.py')}, 'Unpinned executable code')
    for name,digest in plan['files'].items():
        need(not (HERE/name).is_symlink() and sha(HERE/name) == digest, 'Cleanup code changed')
    return plan,sha(HERE/'plan.json'),load_runtime(runtime)


def review_check(review, digest, runtime, host, now):
    need(host == runtime.policy.HOST and review.get('host') == host and review.get('port') == runtime.policy.PORT, 'Wrong host/port')
    need(review.get('plan_sha256') == digest and review.get('runtime_plan_sha256') == RUNTIME_SHA and review.get('anchor') == runtime.ANCHOR, 'Wrong review anchors')
    need(review.get('targets') == list(TARGETS), 'Wrong deletion targets')
    for key in ('root_authorized_two_obsolete_files_only','archives_verified_and_preserved','same_fm4a_since_inventory','same_g22r0_since_inventory','helper_unchanged_since_full_readback','ordinary_shell_confirmed','no_other_console_session'):
        need(review.get(key) is True, 'Missing review '+key)
    need(type(review.get('reviewed_unix')) in (int,float) and 0 <= now-review['reviewed_unix'] <= 1800, 'Expired review')


def size_check(raw, path):
    size = TARGETS[path][0]
    rows = re.findall(rb'^-[^\r\n]* '+re.escape(path.encode())+rb'\r?$', raw, re.M)
    need(len(rows) == 1, 'Missing/duplicate regular-file row')
    fields = rows[0].split()
    need(len(fields) >= 4 and fields[-2].isdigit() and int(fields[-2]) == size, 'Wrong file size')
    return size


def scan_command(path=None):
    """A missing exe is allowed only for a vanished process, zombie or kthread.

    /proc/kernel-thread/exe can be a symlink with no target. test -L alone is
    insufficient on this BusyBox. PF_KTHREAD is Linux bit0x00200000; after the
    final ') ' in stat, flags is field7. Every other unreadable exe is refused.
    """
    forbidden = list(TARGETS) if path is None else [path]
    need(all(name in TARGETS for name in forbidden), 'Unexpected scan target')
    pattern = '|'.join(' *" -> '+name+'"|*" -> '+name+' (deleted)"' for name in forbidden)
    return (
        'fcseen=0; for fcdir in /proc/[0-9]*; do '
        'if test -e "$fcdir/exe"; then fclink=`ls -l "$fcdir/exe"` || exit 31; '
        'printf "%s\\n" "$fclink"; '
        f'case "$fclink" in{pattern}) exit 32;; esac; '
        'case "$fclink" in *" /proc/3940/exe -> /tmp/luma3d-fm4a") fcseen=1;; esac; '
        'else if test -d "$fcdir"; then fcstat=`cat "$fcdir/stat"` || exit 33; '
        'fctail=${fcstat##*) }; set -- $fctail; test "$#" -ge 7 || exit 34; '
        'if test "$1" != Z && test "$1" != X; then shift 6; test "$(( $1 & 2097152 ))" -ne 0 || exit 35; fi; '
        'printf "FC1_NO_USER_EXE %s\\n" "$fcdir"; fi; fi; done; '
        'test "$fcseen" = 1 || exit 36; '
    )


def delete_command(path):
    """One literal allowlisted path; fresh CRC, size, active-exe and PID gates."""
    need(path in TARGETS, 'Not an authorized obsolete benchmark')
    size,_,crc = TARGETS[path]
    return (
        f'( test -f {path} && test ! -L {path} || exit 20; '
        f'/tmp/mc1-helper raw {path} unused {size} {crc} || exit 21; '
        f'fcls=`ls -ln {path}` || exit 22; set -- $fcls; '
        'while test "$#" -gt 2; do shift; done; '
        f'test "$1" = {size} && test "$2" = {path} || exit 23; '
        + scan_command(path) +
        'test "`cat /tmp/fm4live1.pid`" = 3940 || exit 37; '
        'set -- `cat /proc/3940/stat`; test "$1" = 3940 && test "$2" = "(luma3d-fm4a)" && test "$3" != Z && test "$3" != X || exit 38; '
        'shift 21; test "$1" = 35705238 || exit 39; '
        f'test -f {path} && test ! -L {path} || exit 40; '
        f'rm {path} && test ! -e {path} && test ! -L {path} || exit 41; '
        f'printf "FC1_REMOVED {path} {size} {crc}\\n" )'
    )


def execute(channel, runtime, result):
    result['before'] = runtime.health(channel, 'before')
    raw = channel.run('kernel_tmpfs', 'uname -r && cat /proc/mounts')
    need(re.search(rb'^'+runtime.policy.KERNEL.encode()+rb'\r?$', raw, re.M) and b'tmpfs /tmp tmpfs ' in raw, 'Kernel/tmpfs changed')
    channel.run('helper_permissions', 'test -f /tmp/mc1-helper && test -x /tmp/mc1-helper && test ! -L /tmp/mc1-helper')
    runtime.raw_check(channel, 'helper_crc', '/tmp/mc1-helper', runtime.policy.HELPER)
    channel.run('active_executables', '( '+scan_command()+'printf "FC1_SCAN_OK\\n" )')
    for index,path in enumerate(TARGETS):
        raw = channel.run('size_'+str(index), f'test -f {path} && test ! -L {path} && ls -ln {path}')
        size_check(raw,path)
        # Repeat full process identity/GPU health immediately before each deletion.
        result.setdefault('per_target_before',[]).append(runtime.health(channel,'predelete_'+str(index)))
        raw = channel.run('remove_'+str(index), delete_command(path), 180)
        size,_,crc = TARGETS[path]
        marker = f'FC1_REMOVED {path} {size} {crc}'.encode()
        need(re.findall(rb'^'+re.escape(marker)+rb'\r?$',raw,re.M) == [marker], 'Deletion not confirmed')
        result['removed'].append(dict(path=path,bytes=size,crc32=crc))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',type=Path,required=True)
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--expected-plan')
    parser.add_argument('--review',type=Path)
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    _,digest,runtime=preflight(args.runtime.resolve())
    if not args.run:
        print(json.dumps(dict(prepared=True,hardware=False,plan_sha256=digest,targets=list(TARGETS))))
        return 0
    need(args.expected_plan == digest and args.review and args.out, 'Explicit plan/review/new output required')
    review_check(json.loads(args.review.read_text()),digest,runtime,socket.gethostname().split('.')[0],time.time())
    args.out.mkdir(parents=True,exist_ok=False)
    result=dict(passed=False,hardware=True,plan_sha256=digest,review_sha256=sha(args.review),removed=[],game_stopped=False,game_launched=False,fpga_writes=0,sd_writes=0,save_writes=0)
    uart=channel=None;cleanup=False
    def interrupted(sig,_frame):
        if not cleanup:raise InterruptedError('Signal '+str(sig))
    previous={sig:signal.signal(sig,interrupted) for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP)}
    try:
        with open(runtime.transport.LOCK,'a+') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            need(stat.S_ISCHR(os.stat(runtime.policy.PORT).st_mode),'Wrong port')
            owner=subprocess.run(['fuser',runtime.policy.PORT],capture_output=True)
            need(owner.returncode == 1 and not owner.stdout.strip() and not owner.stderr.strip(),'Port busy')
            try:
                uart=runtime.transport.UART(runtime.policy.PORT)
                channel=runtime.transport.Channel(uart,args.out);channel.initial_shell()
                execute(channel,runtime,result);result['passed']=True
            except BaseException as error:result['error']=repr(error)
            finally:
                cleanup=True
                if channel:
                    try:
                        need(channel.shell and channel.current is None,'Shell unconfirmed; no recovery command allowed')
                        result['after']=runtime.health(channel,'after')
                        delta=(result['after']['gpu']['presents']-result['before']['gpu']['presents'])&0xffffffff
                        need(0<delta<1000000,'No GPU progression')
                        result.update(preserved=True,presents_delta=delta)
                    except BaseException as error:result.update(passed=False,cleanup_error=repr(error),manual_review_required=True)
                    channel.close()
                if uart:uart.close()
    except BaseException as error:result.update(passed=False,error=repr(error))
    finally:
        for sig,handler in previous.items():signal.signal(sig,handler)
        (args.out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=result['passed'],output=str(args.out))))
    return not result['passed']


if __name__=='__main__':raise SystemExit(main())
