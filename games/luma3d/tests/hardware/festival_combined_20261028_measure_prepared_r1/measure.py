#!/usr/bin/env python3
"""Seven bounded FC1 windows then restore the exact FM4A demo and its saves.

No transfer or receiver execution. The existing persistent controller supplies
process identity, stop, progress and write-aware launch tracking. Every launch
must resolve its exact PID/start/argv before cleanup; ambiguity fails closed.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import socket
import stat
import subprocess
import time

import identity_policy as policy
import persistent_base as base
import probe_channel as transport
import read_metrics

HERE = Path(__file__).resolve().parent
STAGE_SHA = '0fe854aa271743c1ad838feaa63fa0984fa326da75471ea73d8c5bd7785a6afd'
ANCHOR = dict(pid=3940, start_ticks=35705238)
PROGRAM = 'luma3d-fc1'
TAG = 'fc1measure1'
BASE_PROGRAM = 'luma3d-fm4a'
BASE_PIDFILE = '/tmp/fm4live1.pid'
BASE_ARGS = ['--festival', '--festival-save', '/tmp/fm4live1.festival.save', '--memory-save', '/tmp/fm4live1.memory.save']
TARGET_SHA = '950ced706963b9f7591f45c067b80ee515dcae084a061c78274fe0f00f3871f7'
need = policy.need


def preflight():
    manifest = json.loads((HERE / 'manifest.json').read_text())
    need(__debug__, 'Python -O disallowed')
    for name, digest in manifest['files'].items():
        need(re.fullmatch(r'[A-Za-z0-9_.-]+', name) and not (HERE / name).is_symlink(), 'Unsafe input')
        need(policy.sha(HERE / name) == digest, 'Changed input ' + name)
    need(all(path.name in manifest['files'] for path in HERE.glob('*.py')), 'Unpinned code')
    stage = json.loads((HERE / 'stage_plan.json').read_text())
    need(policy.sha(HERE / 'stage_plan.json') == STAGE_SHA and manifest['stage_plan_sha256'] == STAGE_SHA, 'Stage changed')
    for field in ('target', 'base', 'helper', 'windows', 'anchor', 'baseline_args'):
        need(manifest[field] == stage[field], 'Contract changed ' + field)
    need(manifest['program'] == PROGRAM and manifest['tag'] == TAG and manifest['anchor'] == ANCHOR and manifest['target']['sha256'] == TARGET_SHA, 'Identity changed')
    need(manifest['host'] == policy.HOST and manifest['port'] == policy.PORT and manifest['lock'] == transport.LOCK, 'Transport changed')
    return manifest, policy.sha(HERE / 'manifest.json')


def stage_check(proof):
    need(proof.get('passed') is True and proof.get('preserved') is True and proof.get('hardware') is True and proof.get('plan_sha256') == STAGE_SHA, 'Stage failed or differs')
    need(not proof['game_stopped'] and not proof['game_executed'] and proof['after']['identity'] == ANCHOR, 'Stage changed live demo')
    need(proof['after']['protected_save']['sha256'] == policy.SAVE_SHA, 'Protected save changed')
    need(proof['staged'] == dict(path='/tmp/' + PROGRAM, expected_sha256=TARGET_SHA, runtime_crc32='ad06b5da', runtime_sha256_measured=False, game_executed=False), 'Target not verified')
    need(not any(k in proof for k in ('error', 'cleanup_error', 'manual_review_required')), 'Stage has unresolved error')


def review_check(review, digest, proof_sha, host, now):
    need(host == policy.HOST and review.get('host') == policy.HOST and review.get('port') == policy.PORT, 'Wrong host')
    need(review.get('manifest_sha256') == digest and review.get('stage_result_sha256') == proof_sha and review.get('anchor') == ANCHOR, 'Review identity differs')
    need(review.get('fpga_sha256') == policy.FPGA_SHA and review.get('target_sha256') == TARGET_SHA, 'Review target/FPGA differs')
    for key in ('root_authorized_seven_windows_and_restore_fm4a', 'same_fm4a_since_stage', 'same_g22r0_since_stage', 'same_helper_target_since_stage', 'ordinary_shell_confirmed', 'no_other_console_session'):
        need(review.get(key) is True, 'Missing review ' + key)
    need(type(review.get('reviewed_unix')) in (int, float) and 0 <= now - review['reviewed_unix'] <= 1800, 'Expired review')


def diagnostic(log):
    rows = re.findall(rb'^LUMA3D_SUBMIT_DIAG (.+)\r?$', log, re.M)
    need(len(rows) == 1, 'Missing/duplicate diagnostic summary')
    fields = rows[0].strip().split()
    need(all(re.fullmatch(rb'[a-z_]+=[0-9]+', x) for x in fields), 'Invalid diagnostic fields')
    pairs = [x.decode().split('=') for x in fields]
    need(len({k for k, v in pairs}) == len(pairs), 'Duplicate diagnostic field')
    value = {k: int(v) for k, v in pairs}
    required = {'hardware','batches','commands','geometry_commands','draws','failed_batches','sampled_batches','invalid_samples','wall_ns','feed_us','wait_us','cache_us','cycles','vertices','triangles'}
    need(set(value) == required and value['hardware'] == 1 and value['batches'] > 0 and value['sampled_batches'] == value['batches'], 'Incomplete hardware samples')
    need(value['failed_batches'] == value['invalid_samples'] == 0 and value['wall_ns'] > 0, 'Invalid diagnostic window')
    return value


def parse_window(log, row):
    need(b'LUMA3D_SAVE ' not in log, 'Unexpected save action')
    parsed = read_metrics.parse(log.decode(), hardware=True, mode=row['mode'],
                                memory_actions=row.get('memory_actions'), table_actions=row.get('table_actions'))
    counters = re.findall(rb'^LUMA3D_COUNTERS (.+)\r?$', log, re.M)
    need(len(counters) == 1, 'Missing counters')
    values = dict(x.split('=') for x in counters[0].decode().split())
    need(all(int(values[k], 0) == 0 for k in ('errors', 'underflows', 'fault', 'geometry_errors')), 'GPU error')
    need(int(values['frames'], 0) == parsed['frames'], 'Frame mismatch')
    if row.get('environment'):
        need(row['environment'] == {'LUMA_SUBMIT_DIAG':'1'}, 'Unexpected environment')
        diag = diagnostic(log)
    else:
        need(b'LUMA3D_SUBMIT_DIAG ' not in log, 'Diagnostic contaminates comparison window')
        diag = None
    return dict(measurement=parsed, counters=values, submission_diagnostic=diag)


def launch_command(tag, row):
    args = row['args']
    need(re.fullmatch(r'[a-z0-9_]+', tag) and all(re.fullmatch(r'[A-Za-z0-9_./-]+', arg) for arg in args), 'Unsafe argv')
    need(not any('save' in arg for arg in args), 'Measurement must not save')
    env = 'LUMA_SUBMIT_DIAG=1 ' if row.get('environment') else 'LUMA_SUBMIT_DIAG=0 '
    return (f'( {env}/tmp/{PROGRAM} {" ".join(args)} < /dev/null > /tmp/{tag}.log 2>&1 & p=$!; '
            f'printf "%s\\n" "$p" > /tmp/{tag}.pid.tmp && mv /tmp/{tag}.pid.tmp /tmp/{tag}.pid; '
            f'wait "$p"; rc=$?; printf "%s\\n" "$rc" > /tmp/{tag}.exit; '
            f'printf "\\nL3_EXIT_{tag}:%s\\n" "$rc" ) & echo WINDOW_LAUNCHED')


class Hardware(base.Hardware):
    def __init__(self, channel, manifest):
        super().__init__(channel, ANCHOR)
        self.m = manifest
        self.current = None
        self.save_snapshot = None

    def prepare(self):
        raw = self.c.run('environment', 'uname -r && cat /proc/mounts && LC_ALL=C df -Pk /tmp')
        need(re.search(rb'^' + policy.KERNEL.encode() + rb'\r?$', raw, re.M) and b'tmpfs /tmp tmpfs ' in raw, 'Wrong kernel/tmpfs')
        rows = [x.split() for x in raw.splitlines() if x.split() and x.split()[-1] == b'/tmp']
        need(len(rows) == 1 and len(rows[0]) == 6 and rows[0][3].isdigit() and int(rows[0][3]) >= 1024, 'Need1MiB logs reserve')
        need(self.identity('live', BASE_PROGRAM, BASE_ARGS, BASE_PIDFILE) == ANCHOR, 'Live baseline changed')
        names = [TAG + '_' + str(i) + suffix for i in range(7) for suffix in ('.pid','.pid.tmp','.log','.exit')]
        names += [TAG + '_restore' + suffix for suffix in ('.pid','.pid.tmp','.exit','.publish')]
        self.c.run('fresh_names', ' && '.join('test ! -e /tmp/' + n + ' && test ! -L /tmp/' + n for n in names))
        self.c.run('permissions', ' && '.join(f'test -f {p} && test -x {p} && test ! -L {p}' for p in ('/tmp/mc1-helper','/tmp/'+PROGRAM,'/tmp/'+BASE_PROGRAM)))
        for label, path, expected in [('helper','/tmp/mc1-helper',self.m['helper']),('baseline','/tmp/'+BASE_PROGRAM,self.m['base']),('running','/proc/3940/exe',self.m['base']),('target','/tmp/'+PROGRAM,self.m['target'])]:
            self.raw_verify(label + '_crc', path, expected)
        return dict(identity=ANCHOR, save=self.saved('protected_before'), progress=self.progress(ANCHOR, BASE_PROGRAM, BASE_ARGS, BASE_PIDFILE))

    def demo_saves(self, label):
        result = {}
        for index, path in enumerate((BASE_ARGS[2], BASE_ARGS[4])):
            raw = self.c.run(label + str(index), f'test -f {path} && test ! -L {path} && od -b -v {path}')
            data = transport.octets(raw, 65536)
            result[path] = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        return result

    def stop_baseline(self):
        self.stopping = True
        self.stop('baseline', ANCHOR, BASE_PROGRAM, BASE_ARGS, BASE_PIDFILE)
        self.save_snapshot = self.demo_saves('baseline_stopped_save_')

    def window(self, index, row):
        tag = TAG + '_' + str(index)
        self.current = (tag, row)
        self.c.launch_attempted = False
        self.c.arming = True
        try:
            first = self.c.run(tag + '_launch', launch_command(tag, row))
        finally:
            self.c.arming = False
        pattern = re.compile(rb'^L3_EXIT_' + tag.encode() + rb':(\d+)\r?\n', re.M)
        data = bytearray(first)
        deadline = time.monotonic() + row['timeout_seconds']
        try:
            while not pattern.search(data):
                need(time.monotonic() < deadline and len(data) < 1048576, 'Window deadline/output limit')
                data.extend(self.c.read(.05))
            found = pattern.findall(data)
            need(found == [b'0'], 'Window failure/duplicate exit')
        finally:
            (self.c.out / (tag + '_wait.log')).write_bytes(data)
        log = self.c.run(tag + '_log', 'cat /tmp/' + tag + '.log', 120)
        result = parse_window(log, row)
        self.current = None
        return dict(window=row, display=self.display(tag + '_gpu'), **result)

    def recover(self):
        # No receiver is invoked here. Cancel only a possible shell command.
        if not self.c.shell:
            self.c.write(b'\x03\x15\n')
            self.c.collect(5, transport.resync_valid)
            self.c.shell = True
        if self.current and self.c.launch_attempted:
            tag, row = self.current
            active = self.identity('cleanup_window', PROGRAM, row['args'], '/tmp/' + tag + '.pid')
            if active:
                self.stop('cleanup_window', active, PROGRAM, row['args'], '/tmp/' + tag + '.pid')
        alive = self.identity('cleanup_baseline', BASE_PROGRAM, BASE_ARGS, BASE_PIDFILE)
        if alive:
            need(alive == ANCHOR, 'Different baseline appeared')
            return dict(identity=alive, preserved=True, save=self.saved('protected_preserved'))
        if self.save_snapshot is not None:
            need(self.demo_saves('unchanged_save_') == self.save_snapshot, 'Demo save changed while stopped')
        need(not self.restore_attempted, 'Restore already attempted')
        self.raw_verify('restore_crc', '/tmp/' + BASE_PROGRAM, self.m['base'])
        self.restore_attempted = True
        tag = TAG + '_restore'
        self.c.run('restore_fm4a', policy.launch_command(BASE_PROGRAM, tag, BASE_ARGS))
        restored = self.identity('restored', BASE_PROGRAM, BASE_ARGS, '/tmp/' + tag + '.pid')
        need(restored is not None, 'Restored demo exited')
        self.restore_anchor = restored
        progress = self.progress(restored, BASE_PROGRAM, BASE_ARGS, '/tmp/' + tag + '.pid')
        self.c.run('publish_restored_pid', f'test ! -e /tmp/{tag}.publish && test ! -L /tmp/{tag}.publish && cp /tmp/{tag}.pid /tmp/{tag}.publish && mv /tmp/{tag}.publish {BASE_PIDFILE}')
        need(self.identity('published', BASE_PROGRAM, BASE_ARGS, BASE_PIDFILE) == restored, 'Restored canonical identity changed')
        return dict(identity=restored, restored_fm4a=True, save=self.saved('protected_restored'), progress=progress, saved_state_before_restore=self.save_snapshot)


def execute(hw, manifest):
    result = dict(passed=False, hardware=True, windows=[], fpga_writes=0, sd_writes=0, baseline_save_writes_by_controller=0)
    try:
        result['before'] = hw.prepare()
        hw.stop_baseline()
        for index, row in enumerate(manifest['windows']):
            result['windows'].append(hw.window(index, row))
        result['functional_passed'] = True
    except BaseException as error:
        result['error'] = repr(error)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--expected-manifest')
    parser.add_argument('--stage-result', type=Path)
    parser.add_argument('--review', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    manifest, digest = preflight()
    if not args.run:
        print(json.dumps(dict(prepared=True, hardware=False, manifest_sha256=digest, windows=7)))
        return 0
    need(args.expected_manifest == digest and args.stage_result and args.review and args.out, 'Explicit proof/review/output required')
    proof = json.loads(args.stage_result.read_text());stage_check(proof)
    review_check(json.loads(args.review.read_text()), digest, policy.sha(args.stage_result), socket.gethostname().split('.')[0], time.time())
    args.out.mkdir(parents=True, exist_ok=False)
    result = dict(passed=False, hardware=True, manifest_sha256=digest, stage_result_sha256=policy.sha(args.stage_result))
    uart = channel = hw = None
    cleanup = False

    def interrupted(signum, _frame):
        if not cleanup:
            raise InterruptedError('Signal ' + str(signum))

    old = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP)}
    try:
        with open(transport.LOCK, 'a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            need(stat.S_ISCHR(os.stat(policy.PORT).st_mode), 'Wrong port')
            owner = subprocess.run(['fuser',policy.PORT],capture_output=True)
            need(owner.returncode == 1 and not owner.stdout.strip() and not owner.stderr.strip(), 'Port busy')
            try:
                uart = transport.UART(policy.PORT);channel = base.Channel(uart, args.out)
                channel.initial_shell();hw = Hardware(channel, manifest)
                result.update(execute(hw, manifest))
            finally:
                cleanup = True
                if hw and hw.stopping:
                    try:
                        result['recovery'] = hw.recover()
                        result['passed'] = result.get('functional_passed') is True
                    except BaseException as error:
                        result.update(passed=False, cleanup_error=repr(error), manual_review_required=True)
                        if hw.restore_anchor:
                            result['known_fallback_identity'] = hw.restore_anchor
                if channel:channel.close()
                if uart:uart.close()
    except BaseException as error:
        result.update(passed=False,error=repr(error))
    finally:
        for sig, handler in old.items():signal.signal(sig,handler)
        (args.out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=result['passed'],output=str(args.out))))
    return not result['passed']


if __name__ == '__main__':
    raise SystemExit(main())
