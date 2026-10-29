#!/usr/bin/env python3
"""Prepare-only persistent Festival handoff; root alone owns the UART.

No receiver, transfer, FPGA, SD or kernel operation. On a verified success the
new demo remains alive. Failure/interruption before handoff restores GM1 when
the candidate's state can be established; an unpublished launch fails closed.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import socket
import stat
import subprocess
import time

import identity_policy as p
import probe_channel as transport

HERE = Path(__file__).resolve().parent
LOCK = '/tmp/prodock-diagnostic.lock'


def atomic_json(path, value):
    temporary = path.with_suffix('.json.tmp')
    with temporary.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def preflight(expected=None):
    manifest = json.loads((HERE/'manifest.json').read_text())
    digest = p.sha(HERE/'manifest.json')
    p.need(not expected or expected == digest, 'Manifest changed')
    for name, record in manifest['files'].items():
        path = HERE/name
        p.need(re.fullmatch(r'[A-Za-z0-9_.-]+', name) and not path.is_symlink() and path.stat().st_size == record['bytes'] and p.sha(path) == record['sha256'], 'Changed input '+name)
    p.need(manifest['target'] == p.TARGET and manifest['baseline'] == p.BASE and manifest['helper'] == p.HELPER, 'ELF identity mismatch')
    external = json.loads((HERE/'measurement_manifest.json').read_text())
    p.need(p.sha(HERE/'measurement_manifest.json') == p.MEASURE_SHA and external['game'] == p.TARGET and external['baseline'] == p.BASE and external['helper_record'] == p.HELPER and external['fpga_sha256'] == p.FPGA_SHA, 'External anchor mismatch')
    p.need(manifest['argv'] == p.ARGS and manifest['program'] == p.PROGRAM and manifest['tag'] == p.TAG, 'Launch contract changed')
    return manifest, digest


class Channel(transport.Channel):
    def __init__(self, *args):
        super().__init__(*args)
        self.arming = False
        self.launch_attempted = False

    def write(self, data):
        if self.arming:
            self.launch_attempted = True
        return super().write(data)


class Hardware:
    def __init__(self, channel, baseline):
        self.c = channel
        self.baseline = baseline
        self.stopping = False
        self.candidate = None
        self.restore_attempted = False
        self.restore_anchor = None

    def identity(self, label, program, argv, pidfile):
        raw = self.c.run(label+'_pid', f'if test -f {pidfile} && test ! -L {pidfile}; then cat {pidfile}; else echo MISSING; fi')
        pids = re.findall(rb'^(\d+)\r?$', raw, re.M)
        p.need(len(pids) == 1 and int(pids[0]) > 1, 'Unpublished or invalid PID '+pidfile)
        pid = int(pids[0])
        raw = self.c.run(label+'_state', f'if test -d /proc/{pid}; then cat /proc/{pid}/stat; else echo GONE; fi')
        if re.search(rb'^GONE\r?$', raw, re.M):
            return None
        match = re.search(rb'^'+str(pid).encode()+rb' \('+program.encode()+rb'\) ([^\r\n]+)', raw, re.M)
        p.need(match is not None and len(match[1].split()) >= 20, 'PID belongs to another process')
        fields = match[1].split()
        first = dict(pid=pid, start_ticks=int(fields[19]))
        if fields[0] in (b'Z', b'X'):
            return None
        data = self.c.run(label+'_argv', f'cat /proc/{pid}/stat && od -b -v /proc/{pid}/cmdline && ls -l /proc/{pid}/exe')
        second = p.parse_identity(data, program, argv)
        p.need(second == first, 'Process identity changed between reads')
        return second

    def display(self, label):
        return transport.gpu(self.c.run(label, 'prodockctl display'))

    def saved(self, label):
        return transport.save(self.c.run(label, 'od -b -v /tmp/op2-live.save'))

    def raw_verify(self, label, path, record):
        raw = self.c.run(label, f'/tmp/mc1-helper raw {path} unused {record["bytes"]} {record["crc32"]}', 180)
        expected = f'LUMA3D_RAW_OK bytes={record["bytes"]} crc32={record["crc32"]}'.encode()
        p.need(re.search(rb'^'+expected+rb'\r?$', raw, re.M), 'Runtime CRC mismatch '+path)

    def initial(self, restore=False):
        raw = self.c.run('environment', 'uname -r && cat /proc/mounts && LC_ALL=C df -Pk /tmp && cat /proc/meminfo')
        p.need(re.search(rb'^'+p.KERNEL.encode()+rb'\r?$', raw, re.M) and b'tmpfs /tmp tmpfs ' in raw, 'Wrong kernel/tmpfs')
        rows = [line.split() for line in raw.splitlines() if line.split() and line.split()[0] == b'tmpfs' and line.split()[-1] == b'/tmp' and len(line.split()) == 6]
        p.need(len(rows) == 1 and rows[0][3].isdigit() and int(rows[0][3]) >= 1024, 'Need one MiB for isolated saves and metadata')
        available = re.findall(rb'^MemAvailable:\s+(\d+) kB\r?$', raw, re.M)
        p.need(len(available) == 1 and int(available[0]) >= 65536, 'Insufficient available memory')
        self.c.run('elf_permissions', 'test -f /tmp/mc1-helper && test -x /tmp/mc1-helper && test ! -L /tmp/mc1-helper && test -f /tmp/'+p.PROGRAM+' && test -x /tmp/'+p.PROGRAM+' && test ! -L /tmp/'+p.PROGRAM)
        self.raw_verify('helper_crc', '/tmp/mc1-helper', p.HELPER)
        self.raw_verify('candidate_crc', '/tmp/'+p.PROGRAM, p.TARGET)
        self.raw_verify('fallback_crc', '/tmp/luma3d-gm1', p.BASE)
        saved = self.saved('initial_protected_save')
        before = self.display('initial_display')
        if not restore:
            got = self.identity('initial_gm1', 'luma3d-gm1', ['--showcase'], '/tmp/luma3d-live.pid')
            p.need(got == self.baseline, 'Restored baseline changed since measurement')
            names = [p.TAG+suffix for suffix in ('.pid', '.pid.tmp', '.exit', '.festival.save', '.memory.save', '_restore.pid', '_restore.pid.tmp', '_restore.exit', '_restore.publish')]
            self.c.run('fresh_names', ' && '.join('test ! -e /tmp/'+name+' && test ! -L /tmp/'+name for name in names))
        return dict(save=saved, display=before, tmp_available_kib=int(rows[0][3]), mem_available_kib=int(available[0]))

    def stop(self, label, identity, program, argv, pidfile):
        p.need(self.identity(label+'_recheck', program, argv, pidfile) == identity, 'Stop identity changed')
        self.c.run(label+'_term', p.term_command(identity, program, pidfile))
        for index in range(8):
            raw = self.c.run(label+'_wait_'+str(index), f'if test -d /proc/{identity["pid"]}; then cat /proc/{identity["pid"]}/stat; else echo GONE; fi')
            if re.search(rb'^GONE\r?$', raw, re.M):
                return
            match = re.search(rb'^'+str(identity['pid']).encode()+rb' \('+program.encode()+rb'\) ([^\r\n]+)', raw, re.M)
            p.need(match is not None and len(match[1].split()) >= 20, 'PID reused while stopping')
            fields = match[1].split()
            p.need(int(fields[19]) == identity['start_ticks'], 'Start time changed while stopping')
            if fields[0] in (b'Z', b'X'):
                return
            time.sleep(1)
        raise RuntimeError('Process did not stop')

    def stop_baseline(self):
        self.stopping = True
        self.stop('baseline', self.baseline, 'luma3d-gm1', ['--showcase'], '/tmp/luma3d-live.pid')

    def launch(self):
        self.c.arming = True
        try:
            self.c.run('launch_festival', p.launch_command(p.PROGRAM, p.TAG, p.ARGS))
        finally:
            self.c.arming = False
        for index in range(3):
            try:
                self.candidate = self.identity('candidate_'+str(index), p.PROGRAM, p.ARGS, '/tmp/'+p.TAG+'.pid')
                p.need(self.candidate is not None, 'Candidate exited at startup')
                return self.candidate
            except ValueError:
                if index == 2:
                    raise
                time.sleep(1)

    def progress(self, identity, program, argv, pidfile):
        samples = []
        for index in range(4):
            p.need(self.identity('progress_'+str(index), program, argv, pidfile) == identity, 'Live process changed')
            samples.append(self.display('progress_display_'+str(index)))
            if index != 3:
                time.sleep(3)
        delta = (samples[-1]['presents']-samples[0]['presents']) & 0xffffffff
        p.need(0 < delta < 1000000, 'No verified GPU presentation progress')
        return dict(samples=samples, presents_delta=delta)

    def recover(self):
        # No receiver is ever invoked by this controller: cancel only a possible
        # partial shell command, then resolve exact process identities.
        if not self.c.shell:
            self.c.write(b'\x03\x15\n')
            self.c.collect(5, transport.resync_valid)
            self.c.shell = True
        if self.c.launch_attempted:
            current = self.identity('cleanup_candidate', p.PROGRAM, p.ARGS, '/tmp/'+p.TAG+'.pid')
            if current:
                if self.candidate:
                    p.need(current == self.candidate, 'Candidate PID changed during recovery')
                self.stop('cleanup_candidate', current, p.PROGRAM, p.ARGS, '/tmp/'+p.TAG+'.pid')
        alive = self.identity('cleanup_baseline', 'luma3d-gm1', ['--showcase'], '/tmp/luma3d-live.pid')
        if alive:
            p.need(alive == self.baseline, 'Cannot adopt a different baseline')
            return dict(identity=alive, save=self.saved('preserved_save'), progress=self.progress(alive, 'luma3d-gm1', ['--showcase'], '/tmp/luma3d-live.pid'))
        p.need(not self.restore_attempted, 'Fallback launch was already attempted')
        self.raw_verify('fallback_before_restore', '/tmp/luma3d-gm1', p.BASE)
        self.restore_attempted = True
        tag = p.TAG+'_restore'
        self.c.run('restore_gm1', p.launch_command('luma3d-gm1', tag, ['--showcase']))
        restored = self.identity('restored_gm1', 'luma3d-gm1', ['--showcase'], '/tmp/'+tag+'.pid')
        p.need(restored is not None, 'Fallback not alive')
        self.restore_anchor = restored
        progress = self.progress(restored, 'luma3d-gm1', ['--showcase'], '/tmp/'+tag+'.pid')
        self.c.run('publish_gm1', f'test ! -e /tmp/{tag}.publish && test ! -L /tmp/{tag}.publish && cp /tmp/{tag}.pid /tmp/{tag}.publish && mv /tmp/{tag}.publish /tmp/luma3d-live.pid')
        p.need(self.identity('published_gm1', 'luma3d-gm1', ['--showcase'], '/tmp/luma3d-live.pid') == restored, 'Canonical fallback identity differs')
        return dict(identity=restored, save=self.saved('restored_save'), progress=progress)


def execute(hw, baseline, terminal_phase=lambda: None):
    result = dict(passed=False, hardware=True, left_running=False, baseline_before=baseline, fpga_writes=0, sd_writes=0, baseline_save_writes=0)
    try:
        result['initial'] = hw.initial()
        hw.stop_baseline()
        result['identity'] = hw.launch()
        result['progress'] = hw.progress(result['identity'], p.PROGRAM, p.ARGS, '/tmp/'+p.TAG+'.pid')
        result['save_after'] = hw.saved('handoff_protected_save')
        result.update(passed=True, left_running=True, program=p.PROGRAM, argv=p.ARGS, pidfile='/tmp/'+p.TAG+'.pid', save_paths=[p.ARGS[2], p.ARGS[4]])
        terminal_phase()
    except BaseException as error:
        result.update(passed=False, left_running=False)
        result['error'] = repr(error)
        terminal_phase()
        if hw.stopping:
            try:
                result['recovery'] = hw.recover()
            except BaseException as cleanup:
                result['cleanup_error'] = repr(cleanup)
                result['manual_review_required'] = True
                if getattr(hw, 'restore_anchor', None):
                    result['known_fallback_identity'] = hw.restore_anchor
        else:
            result['no_game_switch_attempted'] = True
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--expected-manifest')
    parser.add_argument('--measure-result', type=Path)
    parser.add_argument('--review', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    manifest, digest = preflight(args.expected_manifest)
    if not args.run:
        print(json.dumps(dict(prepared=True, hardware=False, manifest_sha256=digest, argv=p.ARGS)))
        return 0
    p.need(args.expected_manifest and args.measure_result and args.review and args.out, 'Explicit proof/review/output required')
    proof = json.loads(args.measure_result.read_text())
    baseline = p.measurement_proof(proof)
    review = json.loads(args.review.read_text())
    p.review_check(review, digest, p.sha(args.measure_result), baseline, socket.gethostname().split('.')[0])
    args.out.mkdir(parents=True, exist_ok=False)
    result = dict(passed=False, hardware=True)
    uart = channel = None
    cleanup = False
    received_signals = []
    def terminal_phase():
        nonlocal cleanup
        cleanup = True
    def interrupted(number, unused):
        received_signals.append(number)
        if not cleanup:
            raise InterruptedError('Controller interrupted '+str(number))
    handlers = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    try:
        descriptor = os.open(LOCK, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, 'r+') as lock:
            p.need(stat.S_ISREG(os.fstat(lock.fileno()).st_mode), 'Diagnostic lock is not regular')
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            p.need(stat.S_ISCHR(os.stat(p.PORT).st_mode), 'Wrong port type')
            owner = subprocess.run(['fuser', p.PORT], capture_output=True)
            p.need(owner.returncode == 1 and not owner.stdout.strip() and not owner.stderr.strip(), 'Console is in use')
            uart = transport.UART(p.PORT)
            channel = Channel(uart, args.out)
            channel.initial_shell()
            result = execute(Hardware(channel, baseline), baseline, terminal_phase)
            cleanup = True
    except BaseException as error:
        result['error'] = repr(error)
    finally:
        cleanup = True
        if channel:
            channel.close()
        if uart:
            uart.close()
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
        result.update(manifest_sha256=digest, measure_result_sha256=p.sha(args.measure_result), review_sha256=p.sha(args.review), signals=received_signals)
        atomic_json(args.out/'result.json', result)
    print(json.dumps(dict(passed=result['passed'], left_running=result.get('left_running', False), output=str(args.out))))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
