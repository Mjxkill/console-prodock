#!/usr/bin/env python3
"""Finish named Neo experiments: qualify, test SRAM/DDR/GPU, stop at Linux boot.

Only the named, already-created build directories are considered. Every load
uses load_linux's saved-failure and live parking-loop guard. No SD/flash writes.
A failed load without a recognized recovery record ends the sequence.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]


def build_state(build):
    log=build/'build.log'
    if not log.is_file():
        return 'waiting'
    text=log.read_text(errors='replace')
    if re.search(r'^ERROR',text,re.M):
        return 'build_failed'
    report=build/'impl/pnr/console_neo.tr'
    if ('Bitstream generation completed' in text and
            f'Generate file "{report}" completed' in text):
        return 'ready'
    return 'waiting'


def recoverable(record):
    """Use exactly the loader's static recovery checks; live checks stay there."""
    from load_linux import recovery_commands
    try:
        recovery_commands(record)
        return True
    except (OSError,ValueError,KeyError,RuntimeError):
        return False


def run_logged(command,log):
    # Children have their own bounded hardware operations. Do not kill a
    # programmer halfway through a load because the build-wait deadline ends.
    with log.open('w') as output:
        return subprocess.run(command,cwd=ROOT,stdout=output,stderr=subprocess.STDOUT).returncode


def try_candidate(build,recovery,out,run=run_logged,can_recover=recoverable):
    out.mkdir(exist_ok=False)
    entry={'build':str(build),'out':str(out)}
    rc=run([sys.executable,str(ROOT/'tools/check_neo_timing.py'),str(build)],out/'qualification.log')
    if rc:
        return {**entry,'state':'qualification_failed'},recovery
    q=json.loads((build/'qualification.json').read_text())
    if q.get('status')!='PASS':
        return {**entry,'state':'qualification_failed'},recovery
    entry['bitstream_sha256']=q['bitstream_sha256']
    board=out/'board'
    rc=run([sys.executable,str(ROOT/'tools/neo/load_linux.py'),'--build',str(build),
            '--recover-failed-load',str(recovery),'--out',str(board)],out/'load.log')
    try:
        result=json.loads((board/'result.json').read_text())
    except (OSError,ValueError):
        return {**entry,'state':'needs_inspection','reason':'Loader produced no complete result'},recovery
    if result.get('bitstream_sha256')!=entry['bitstream_sha256']:
        return {**entry,'state':'needs_inspection','reason':'Board result hash mismatch'},recovery
    if result.get('sd_written') is not False or result.get('flash_written') is not False:
        return {**entry,'state':'needs_inspection','reason':'Unexpected write scope'},recovery
    if rc==0 and result.get('passed') is True:
        return {**entry,'state':'linux_booted'},board
    if not can_recover(board):
        return {**entry,'state':'needs_inspection','reason':'Failed load is not safely recoverable'},recovery
    entry['load_error']=result.get('load_error')
    # The boot preflight stops on its first mismatch. Capture CPU-vs-JTAG
    # DDR and a no-DMA GPU command before trying another qualified build.
    probe=out/'probe'
    rc=run([sys.executable,str(ROOT/'tools/neo/probe_memory.py'),
            '--failed-load',str(board),'--gpu-cpu','--out',str(probe)],out/'probe.log')
    entry['probe_returncode']=rc
    entry['probe_result']=str(probe/'result.json')
    return {**entry,'state':'board_failed'},board


def preflight_gate(build):
    """Use the loader's exact gate, including all non-setup timing checks."""
    from load_linux import check_fpga
    q=json.loads((build/'qualification.json').read_text())
    diagnostic=None if q.get('status')=='PASS' else q['bitstream_sha256']
    check_fpga(build,diagnostic_bitstream=diagnostic)
    return q,diagnostic


def try_preflight_candidate(build,recovery,out,run=run_logged,
                            can_recover=recoverable,gate=preflight_gate):
    """Exact-bitstream diagnostic, parked CPU, no Linux payload or boot.

    The only permitted timing exception is the loader's existing setup-only
    diagnostic. A complete qualification and its exact hashes remain required.
    TARGET and geometry/material configuration suites verify rejected commands
    as well as accepted commands; a fence alone is not a successful GPU test.
    """
    out.mkdir(exist_ok=False)
    entry={'build':str(build),'out':str(out),'mode':'diagnostic_preflight'}
    record=build/'qualification.json'
    prior=record.stat().st_mtime_ns if record.exists() else None
    rc=run([sys.executable,str(ROOT/'tools/check_neo_timing.py'),str(build)],out/'qualification.log')
    try:
        if not record.is_file() or record.stat().st_mtime_ns==prior:
            raise ValueError('Qualification did not produce a fresh result')
        q,diagnostic=gate(build)
        if rc and q.get('status')!='FAIL':
            raise ValueError('Qualification execution failed without a diagnostic result')
    except (OSError,ValueError,KeyError,RuntimeError) as error:
        return {**entry,'state':'qualification_failed','reason':str(error)},recovery
    entry.update(bitstream_sha256=q['bitstream_sha256'],qualification_status=q['status'],
                 timing_checks_ns=q.get('timing_checks_ns'),setup_diagnostic=diagnostic is not None)
    board=out/'board'
    command=[sys.executable,str(ROOT/'tools/neo/load_linux.py'),'--build',str(build),
             '--recover-failed-load',str(recovery),'--out',str(board),
             '--preflight-only','--jtag-frequency','6000000']
    if diagnostic is not None:command+=['--diagnostic-bitstream',diagnostic]
    rc=run(command,out/'load.log')
    try:
        result=json.loads((board/'result.json').read_text())
        if (result.get('bitstream_sha256')!=entry['bitstream_sha256'] or
                result.get('sd_written') is not False or result.get('flash_written') is not False or
                result.get('run_mode')!='preflight_only'):
            raise ValueError('Unexpected board result identity or write/execution scope')
    except (OSError,ValueError) as error:
        return {**entry,'state':'needs_inspection','reason':str(error)},recovery
    if not can_recover(board):
        return {**entry,'state':'needs_inspection','reason':'Loader did not prove a stopped CPU'},recovery
    if rc or result.get('passed') is not True:
        return {**entry,'state':'board_failed','load_error':result.get('load_error')},board
    entry['configuration_suites']=[]
    for name in ('target','control'):
        probe=out/(name+'_suite')
        rc=run([sys.executable,str(ROOT/'tools/neo/probe_gpu_debug.py'),
                '--failed-load',str(board),'--out',str(probe),'--'+name+'-suite'],out/(name+'.log'))
        try:
            tested=json.loads((probe/'result.json').read_text())
            if (tested.get('bitstream_sha256')!=entry['bitstream_sha256'] or
                    tested.get('sd_written') is not False or tested.get('flash_written') is not False or
                    tested.get('cpu_left_halted') is not True):
                raise ValueError('Unexpected probe identity, write scope or CPU state')
        except (OSError,ValueError) as error:
            return {**entry,'state':'needs_inspection','reason':str(error)},board
        passed=rc==0 and tested.get('passed') is True
        entry['configuration_suites'].append(dict(name=name,passed=passed,result=str(probe/'result.json')))
        if not passed:return {**entry,'state':'board_failed'},board
    return {**entry,'state':'preflight_passed','cpu_left_halted':True,
            'scope':'Targeted boot/DDR/GPU preflight and configuration tests only; no full-board qualification'},board


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',type=Path,action='append',required=True)
    p.add_argument('--recover-failed-load',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--wait-seconds',type=int,default=14400)
    p.add_argument('--poll-seconds',type=int,default=20)
    p.add_argument('--diagnostic-preflight',action='store_true',
                   help='Exact-SHA setup-only diagnostic if eligible, then GPU configuration tests; keep CPU parked, never boot Linux')
    a=p.parse_args()
    if not 1<=a.wait_seconds<=43200 or not 1<=a.poll_seconds<=60:
        p.error('Wait must be 1..43200 seconds and polling 1..60 seconds')
    builds=list(dict.fromkeys(b.resolve(strict=True) for b in a.build))
    for b in builds:
        if b.parent!=ROOT/'tang/impl' or not re.fullmatch(r'console_neo_[a-zA-Z0-9_]+',b.name):
            p.error('Only existing console Neo build directories are accepted')
    recovery=a.recover_failed_load.resolve(strict=True)
    if not recoverable(recovery):
        p.error('Initial failed load is not safely recoverable')
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    lock=(ROOT/'TESTS/neo_pending_validation.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    state={'state':'waiting','started_utc':datetime.now(timezone.utc).isoformat(),
           'builds':[str(b) for b in builds],'initial_recovery':str(recovery),
           'wait_seconds':a.wait_seconds,'results':[],
           'scope':'Neo only; existing guarded SRAM loader; no SD/flash writes'}
    state['mode']='diagnostic_preflight' if a.diagnostic_preflight else 'qualified_linux'
    def save():
        state['updated_utc']=datetime.now(timezone.utc).isoformat()
        pending=out/'status.tmp'
        pending.write_text(json.dumps(state,indent=2)+'\n')
        pending.replace(out/'status.json')
    save();deadline=time.monotonic()+a.wait_seconds
    try:
        while builds and time.monotonic()<deadline:
            for build in list(builds):
                status=build_state(build)
                if status=='waiting':
                    continue
                if status=='build_failed':
                    state['results'].append({'build':str(build),'state':status})
                else:
                    state.update(state='testing',active_build=str(build));save()
                    print('Testing '+build.name,flush=True)
                    attempt=try_preflight_candidate if a.diagnostic_preflight else try_candidate
                    entry,recovery=attempt(build,recovery,out/build.name)
                    state['results'].append(entry)
                    if entry['state'] in ('linux_booted','preflight_passed','needs_inspection'):
                        state['state']=entry['state'];save()
                        return 0 if entry['state'] in ('linux_booted','preflight_passed') else 2
                builds.remove(build)
                state.update(state='waiting',active_build=None);save()
            if builds:
                time.sleep(min(a.poll_seconds,max(0,deadline-time.monotonic())))
        state['state']='wait_expired' if builds else 'no_candidate_passed'
        save();return 1
    except Exception as error:
        state.update(state='needs_inspection',error=str(error));save()
        raise
    finally:
        lock.close()


if __name__=='__main__':
    raise SystemExit(main())
