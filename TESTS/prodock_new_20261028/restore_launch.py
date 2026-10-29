#!/usr/bin/env python3
"""Restore the exact FM4A demo after a verified cold Linux recovery.

Uses the topology-bound UART and existing process/launch policy. A launch is
attempted only once. An ambiguous reply never triggers another launch or a
blind kill; the report and UART transcript permit read-only investigation.
No J-Link, FPGA, flash, or SD operation is performed here.
"""
import argparse
import json
from pathlib import Path
import re
import signal
import sys
import time

import bootstrap_reader as link

POLICY_SHA = '8aa2da6da39c3dd355c006ae291c22e755d71573bbba9d28a2d95db139114908'
LINK_SHA = '7cc858ebff1b8cb135887b715d9951ce30c2b8003db297b20e7746f159242e64'
READER_R2_SHA = '00bf58fbcf032f1c4c95f7c64cc0b85bb47c03b8f00dfb689de6a9ebc29534a0'


def identity(channel, policy, name):
    raw = channel.run(name + '_pid', 'cat /tmp/fm4live1.pid')
    rows = re.findall(rb'^(\d+)\r?$', raw, re.M)
    assert len(rows) == 1 and int(rows[0]) > 1, 'No unique published PID'
    pid = int(rows[0])
    raw = channel.run(name + '_identity',
                      f'cat /proc/{pid}/stat && od -b -v /proc/{pid}/cmdline'
                      f' && ls -l /proc/{pid}/exe')
    return policy.parse_identity(raw, policy.PROGRAM, policy.ARGS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bootstrap-proof', type=Path, required=True)
    parser.add_argument('--linux-proof', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    assert __debug__ and link.sha(Path(link.__file__)) == LINK_SHA
    proof = json.loads(args.bootstrap_proof.read_text())
    assert proof['passed'] and proof['hardware'] and not proof['game_launched']
    assert proof['programmer'] == '2023112818' and proof['port'] == str(link.PORT)
    assert proof['game'] == '/tmp/luma3d-fm4a' and proof['game_crc32'] == 'fa358bf4'
    assert proof['game_bytes'] == 16640496
    assert proof['reader_full_readback_sha256'] == READER_R2_SHA
    linux = json.loads(args.linux_proof.read_text())
    assert linux['passed'] and linux['usb']['port'] == str(link.PORT)
    assert linux['manifest']['files']['opensbi/platform/generic/firmware/fw_payload.bin']['sha256'] == '0ff71bb9b7d44ce2f149ed6406d33c8497b45b8439c54b896621dedcd0c498b3'
    transport = link.imports()
    assert link.sha(link.TRANSPORT / 'policy.py') == POLICY_SHA
    import policy
    if not args.run:
        print(json.dumps({'prepared': True, 'target': link.PROGRAMMER, 'argv': policy.ARGS}))
        return 0
    args.out.mkdir(parents=True, exist_ok=False)
    result = dict(passed=False, target=link.PROGRAMMER, port=str(link.PORT),
                  launch_attempted=False, sd_writes=0, fpga_writes=0,
                  boot_proof_sha256=link.sha(args.linux_proof),
                  extraction_proof_sha256=link.sha(args.bootstrap_proof),
                  game_sha256_source=policy.TARGET['sha256'],
                  game_crc32_verified='fa358bf4',
                  ram_progress_recovered=False, started_unix=time.time())
    def interrupted(number, frame):
        raise InterruptedError('Signal ' + str(number))
    previous = {number: signal.signal(number, interrupted)
                for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    try:
        with link.open_channel(args.out) as channel:
            channel.initial_shell()
            raw = channel.run('environment', 'uname -r && cat /proc/mounts && ls -l /proc/[0-9]*/exe')
            assert re.search(rb'^' + link.KERNEL.encode() + rb'\r?$', raw, re.M)
            assert b'tmpfs /tmp tmpfs ' in raw
            assert not re.search(rb'^l[^\r\n]* /proc/[0-9]+/exe -> [^\r\n]*luma3d-', raw, re.M)
            fresh = ['/tmp/fm4live1' + suffix for suffix in
                     ('.pid', '.pid.tmp', '.exit', '.festival.save', '.memory.save')]
            channel.run('fresh_runtime', ' && '.join('test ! -e ' + path + ' && test ! -L ' + path for path in fresh)
                        + ' && test -f /tmp/luma3d-fm4a && test -x /tmp/luma3d-fm4a && test ! -L /tmp/luma3d-fm4a')
            result['before'] = transport.gpu(channel.run('before_display', 'prodockctl display'))
            result['launch_attempted'] = True
            channel.run('launch', policy.launch_command(policy.PROGRAM, policy.TAG, policy.ARGS))
            time.sleep(2)
            anchor = identity(channel, policy, 'started')
            result['identity'] = anchor
            result['samples'] = []
            for index in range(4):
                assert identity(channel, policy, 'sample_' + str(index)) == anchor
                status = transport.gpu(channel.run('display_' + str(index), 'prodockctl display'))
                result['samples'].append(status)
                if index != 3:
                    time.sleep(5)
            delta = (result['samples'][-1]['presents'] - result['samples'][0]['presents']) & 0xffffffff
            assert 0 < delta < 1000000, 'GPU presentation did not advance'
            result.update(passed=True, left_running=True, presents_delta=delta,
                          program=policy.PROGRAM, argv=policy.ARGS, pidfile='/tmp/fm4live1.pid')
    except BaseException as error:
        result['error'] = repr(error)
        result['automatic_retry'] = False
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)
        result['finished_unix'] = time.time()
        (args.out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
