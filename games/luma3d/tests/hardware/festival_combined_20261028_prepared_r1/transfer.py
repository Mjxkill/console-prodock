#!/usr/bin/env python3
"""Reuse the verified RX2 transport to stage FC1 while FM4A keeps running.

Default is strictly offline. --run is root-only after a fresh written review.
This phase has no signal/launch command for any game, no file removal, and no
hardware bootstrap. A receiver with uncertain state permits only passive wait
for its own RETURN; the retained Channel enforces that transition.
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
import zlib

import identity_policy as policy
import probe_channel as transport
import stage

HERE = Path(__file__).resolve().parent
ANCHOR = {'pid': 3940, 'start_ticks': 35705238}
BASE = {'bytes': 16640496, 'sha256': '6b8d3eeb273e03be38eb73a2ff6fee60dad16678316bfdacb52b4db308fec3f7', 'crc32': 'fa358bf4'}
TARGET = {'bytes': 16644780, 'sha256': '950ced706963b9f7591f45c067b80ee515dcae084a061c78274fe0f00f3871f7', 'crc32': 'ad06b5da'}
ARGS = ['--festival', '--festival-save', '/tmp/fm4live1.festival.save', '--memory-save', '/tmp/fm4live1.memory.save']
need = policy.need


def record(path):
    data = path.read_bytes()
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), crc32=f'{zlib.crc32(data):08x}')


def preflight():
    plan = json.loads((HERE / 'plan.json').read_text())
    need(__debug__, 'Python -O disallowed')
    need(plan['anchor'] == ANCHOR and plan['base'] == BASE and plan['target'] == TARGET, 'Changed game identities')
    need(plan['host'] == policy.HOST and plan['ssh_alias'] == 'ax15' and plan['port'] == policy.PORT and plan['lock'] == transport.LOCK, 'Wrong transport')
    need(plan['baseline_program'] == 'luma3d-fm4a' and plan['baseline_pidfile'] == '/tmp/fm4live1.pid' and plan['baseline_args'] == ARGS, 'Changed active demo')
    expected = dict(base_remote='/tmp/luma3d-fm4a', target_remote='/tmp/luma3d-fc1', helper_remote='/tmp/mc1-helper', rx2_executable='/tmp/luma-rx2-buffer1', remote_payload='/tmp/rx2-fc1.delta.lz4.part', payload_file='combined.delta.lz4')
    need(all(plan[k] == v for k, v in expected.items()), 'Changed remote names')
    need(all(p.name in plan['files'] for p in HERE.glob('*.py')), 'Unpinned executable input')
    for name, expected_record in plan['files'].items():
        need(re.fullmatch(r'[A-Za-z0-9_.-]+', name) and not (HERE / name).is_symlink(), 'Unsafe input')
        need(record(HERE / name) == expected_record, 'Changed input ' + name)
    live = json.loads((HERE / 'live_anchor.json').read_text())
    need(live['passed'] and live['left_running'] and live['identity'] == ANCHOR and live['program'] == 'luma3d-fm4a' and live['argv'] == ARGS, 'External live anchor changed')
    delta = json.loads((HERE / 'delta.json').read_text())
    need(delta['old_sha256'] == BASE['sha256'] and delta['new_sha256'] == TARGET['sha256'] and delta['transport_sha256'] == record(HERE / plan['payload_file'])['sha256'], 'Wrong delta')
    need(plan['delta'] == dict(raw_bytes=delta['patch_bytes'], raw_crc32=delta['patch_crc32']), 'Wrong patch descriptor')
    need(plan['helper'] == policy.HELPER and plan['receiver']['sha256'] == 'c28b795a17922708a0f990eff4c0ef05dfd8aa2f7a20f036f4fbab51b67ad466', 'Unqualified helper/receiver')
    proof = json.loads((HERE / 'delta_qemu.json').read_text())
    need(proof['passed'] and proof['inputs_unchanged'] and not proof['hardware'] and proof['compared_bytes'] == TARGET['bytes'] and all(proof['cases'].values()), 'QEMU reconstruction not qualified')
    need({BASE['sha256'], TARGET['sha256'], policy.HELPER['sha256'], delta['transport_sha256']}.issubset(set(proof['inputs'].values())), 'QEMU tested different inputs')
    need(plan['target']['bytes'] <= 16 << 20 and plan['delta']['raw_bytes'] <= 16 << 20, 'Helper bounds exceeded')
    return plan, policy.sha(HERE / 'plan.json')


def review_check(review, digest, host, now):
    need(host == policy.HOST and review.get('host') == policy.HOST and review.get('port') == policy.PORT, 'Wrong review host/port')
    need(review.get('plan_sha256') == digest and review.get('anchor') == ANCHOR and review.get('target_sha256') == TARGET['sha256'], 'Wrong review identity')
    need(review.get('fpga_sha256') == policy.FPGA_SHA and review.get('protected_save_sha256') == policy.SAVE_SHA, 'Wrong immutable references')
    for key in ('root_authorized_stage_only', 'same_fm4a_since_live_anchor', 'same_g22r0_since_live_anchor', 'helper_unchanged_since_full_readback', 'receiver_unchanged_since_full_readback', 'ordinary_shell_confirmed', 'no_other_console_session', 'allow_known_g22r0_link_instability'):
        need(review.get(key) is True, 'Missing review ' + key)
    need(type(review.get('reviewed_unix')) in (int, float) and 0 <= now - review['reviewed_unix'] <= 1800, 'Review expired')


def free_kib(raw):
    rows = [x.split() for x in raw.splitlines() if x.split() and x.split()[-1] == b'/tmp']
    need(len(rows) == 1 and len(rows[0]) == 6 and rows[0][0] == b'tmpfs' and all(x.isdigit() for x in rows[0][1:4]), 'Unexpected tmpfs df')
    total, used, free = map(int, rows[0][1:4])
    need(0 < total and used + free <= total and 0 <= free <= total, 'Inconsistent df')
    return free


def identity(raw):
    got = policy.parse_identity(raw, 'luma3d-fm4a', ARGS)
    need(got == ANCHOR and re.findall(rb'^3940\r?$', raw, re.M) == [b'3940'], 'Active process/pidfile changed')
    return got


def health(channel, label):
    raw = channel.run(label + '_identity', 'cat /tmp/fm4live1.pid && cat /proc/3940/stat && od -b -v /proc/3940/cmdline && ls -l /proc/3940/exe')
    return dict(identity=identity(raw), protected_save=transport.save(channel.run(label + '_save', 'od -b -v /tmp/op2-live.save')),
                gpu=transport.gpu(channel.run(label + '_gpu', 'prodockctl display')),
                tmp_available_kib=free_kib(channel.run(label + '_space', 'LC_ALL=C df -Pk /tmp')))


def raw_check(channel, label, path, expected):
    raw = channel.run(label, f'/tmp/mc1-helper raw {path} unused {expected["bytes"]} {expected["crc32"]}', 180)
    need(re.search(rb'^LUMA3D_RAW_OK bytes=' + str(expected['bytes']).encode() + rb' crc32=' + expected['crc32'].encode() + rb'\r?$', raw, re.M), 'Runtime CRC mismatch ' + path)


def stage_files(channel, plan, segments):
    raw = channel.run('environment', 'uname -r && cat /proc/mounts && cat /proc/meminfo')
    need(re.search(rb'^' + policy.KERNEL.encode() + rb'\r?$', raw, re.M) and b'tmpfs /tmp tmpfs ' in raw, 'Kernel/tmpfs changed')
    available = re.findall(rb'^MemAvailable:\s+(\d+) kB\r?$', raw, re.M)
    need(len(available) == 1 and int(available[0]) * 1024 >= 64 << 20, 'Need 64MiB available memory')
    paths = [plan[k] for k in ('helper_remote', 'rx2_executable', 'base_remote')]
    channel.run('permissions', ' && '.join(f'test -f {p} && test -x {p} && test ! -L {p}' for p in paths))
    channel.run('fresh_names', ' && '.join(f'test ! -e {p} && test ! -L {p}' for p in (plan['target_remote'], plan['remote_payload'])))
    raw_check(channel, 'helper_crc', plan['helper_remote'], plan['helper'])
    raw_check(channel, 'receiver_crc', plan['rx2_executable'], plan['receiver'])
    raw_check(channel, 'base_crc', plan['base_remote'], plan['base'])
    raw_check(channel, 'running_crc', '/proc/3940/exe', plan['base'])
    stage.storage_check(free_kib(channel.run('space_transfer', 'LC_ALL=C df -Pk /tmp')), plan, payload_exists=False)
    # FC1 delta needs232 DATA blocks, below the existing512-block session cap.
    need(plan['files'][plan['payload_file']]['bytes'] <= 512 * 512, 'Single-session limit')
    row = stage.segment(channel, plan, HERE, resume=False, expected_offset=0)
    segments.append(row)
    (channel.out / 'segments.json').write_text(json.dumps(segments, indent=2) + '\n')
    need(row['complete'], 'Unexpected partial completion; no automatic restart')
    raw_check(channel, 'payload_crc', plan['remote_payload'], plan['files'][plan['payload_file']])
    stage.storage_check(free_kib(channel.run('space_reconstruction', 'LC_ALL=C df -Pk /tmp')), plan, payload_exists=True)
    d = plan['delta']
    raw = channel.run('reconstruction', f'/tmp/mc1-helper patch {plan["remote_payload"]} {plan["target_remote"]} {d["raw_bytes"]} {d["raw_crc32"]} {plan["base_remote"]}', 180)
    need(re.search(rb'^LUMA3D_UNPACK_OK bytes=' + str(TARGET['bytes']).encode() + rb' crc32=' + TARGET['crc32'].encode() + rb'\r?$', raw, re.M), 'Reconstruction failed')
    raw_check(channel, 'target_crc', plan['target_remote'], TARGET)
    channel.run('target_mode', 'chmod 700 ' + plan['target_remote'])
    return dict(path=plan['target_remote'], expected_sha256=TARGET['sha256'], runtime_crc32=TARGET['crc32'], runtime_sha256_measured=False, game_executed=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--expected-plan')
    parser.add_argument('--review', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, digest = preflight()
    if not args.run:
        print(json.dumps(dict(prepared=True, hardware=False, plan_sha256=digest, payload_bytes=plan['files'][plan['payload_file']]['bytes'])))
        return 0
    need(args.expected_plan == digest and args.review and args.out, 'Explicit plan/review/new output required')
    review = json.loads(args.review.read_text())
    review_check(review, digest, socket.gethostname().split('.')[0], time.time())
    args.out.mkdir(parents=True, exist_ok=False)
    result = dict(passed=False, hardware=True, plan_sha256=digest, review_sha256=policy.sha(args.review), game_stopped=False, game_executed=False, sd_writes=0, fpga_writes=0, save_writes=0, segments=[])
    uart = channel = None
    cleanup = False

    def interrupted(signum, _frame):
        if not cleanup:
            raise InterruptedError('Signal ' + str(signum))

    old = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    try:
        with open(transport.LOCK, 'a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            need(stat.S_ISCHR(os.stat(policy.PORT).st_mode), 'Not a character device')
            owners = subprocess.run(['fuser', policy.PORT], capture_output=True)
            need(owners.returncode == 1 and not owners.stdout.strip() and not owners.stderr.strip(), 'Port busy')
            try:
                uart = transport.UART(policy.PORT)
                channel = transport.Channel(uart, args.out)
                channel.initial_shell()
                result['before'] = health(channel, 'before')
                result['staged'] = stage_files(channel, plan, result['segments'])
                result['passed'] = True
            except BaseException as error:
                result['error'] = repr(error)
            finally:
                cleanup = True
                if channel:
                    try:
                        if channel.current:
                            channel.restore_shell(channel.current)
                        need(channel.shell, 'Shell return unconfirmed; no further command permitted')
                        result['after'] = health(channel, 'after')
                        delta = (result['after']['gpu']['presents'] - result['before']['gpu']['presents']) & 0xffffffff
                        need(0 < delta < 1000000, 'No GPU progression')
                        result.update(preserved=True, presents_delta=delta)
                    except BaseException as error:
                        result.update(passed=False, cleanup_error=repr(error), manual_review_required=True)
                    channel.close()
                if uart:
                    uart.close()
    except BaseException as error:
        result.update(passed=False, error=repr(error))
    finally:
        for sig, handler in old.items():
            signal.signal(sig, handler)
        (args.out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=result['passed'], output=str(args.out))))
    return not result['passed']


if __name__ == '__main__':
    raise SystemExit(main())
