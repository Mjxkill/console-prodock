"""Pure guards and stage-command transcript; no UART/device/network access."""
import copy
import json
import tempfile
from pathlib import Path
from unittest import mock

import transfer as t


def rejects(function, *args):
    try:
        function(*args)
    except ValueError:
        return
    raise AssertionError('Unsafe input accepted')


def review(digest):
    result = dict(host=t.policy.HOST, port=t.policy.PORT, plan_sha256=digest,
                  anchor=t.ANCHOR, target_sha256=t.TARGET['sha256'], fpga_sha256=t.policy.FPGA_SHA,
                  protected_save_sha256=t.policy.SAVE_SHA, reviewed_unix=1000)
    for key in ('root_authorized_stage_only', 'same_fm4a_since_live_anchor', 'same_g22r0_since_live_anchor',
                'helper_unchanged_since_full_readback', 'receiver_unchanged_since_full_readback',
                'ordinary_shell_confirmed', 'no_other_console_session', 'allow_known_g22r0_link_instability'):
        result[key] = True
    return result


class Transcript:
    def __init__(self, directory, plan, free=30000):
        self.out, self.plan, self.free = directory, plan, free
        self.commands = []

    def run(self, label, command, timeout=90):
        self.commands.append((label, command))
        if label == 'environment':
            return (t.policy.KERNEL + '\ntmpfs /tmp tmpfs rw 0 0\nMemAvailable: 100000 kB\n').encode()
        if label.startswith('space_'):
            return f'tmpfs 186556 {186556-self.free} {self.free} 10% /tmp\n'.encode()
        if label.endswith('_crc'):
            words = command.split()
            return f'LUMA3D_RAW_OK bytes={words[-2]} crc32={words[-1]}\n'.encode()
        if label == 'reconstruction':
            return f'LUMA3D_UNPACK_OK bytes={t.TARGET["bytes"]} crc32={t.TARGET["crc32"]}\n'.encode()
        return b''


def main():
    plan, digest = t.preflight()
    good = review(digest)
    t.review_check(good, digest, t.policy.HOST, 1001)
    count = 1
    for key, value in [('host', 'ax15'), ('anchor', {'pid':3158,'start_ticks':27508908}),
                       ('target_sha256', '0'*64), ('reviewed_unix', 0),
                       ('ordinary_shell_confirmed', False), ('allow_known_g22r0_link_instability', False)]:
        bad = copy.deepcopy(good);bad[key] = value
        rejects(t.review_check, bad, digest, t.policy.HOST, 2000)
        count += 1
    rejects(t.review_check, good, digest, 'wrong-host', 1001);count += 1
    assert t.free_kib(b'tmpfs 100 25 75 25% /tmp\n') == 75
    for raw in (b'/dev/mmc0 100 25 75 25% /tmp\n', b'tmpfs 100 25 200 25% /tmp\n', b''):
        rejects(t.free_kib, raw);count += 1
    with tempfile.TemporaryDirectory(prefix='combined-prepare-') as temporary:
        directory = Path(temporary)
        channel = Transcript(directory, plan)
        row = dict(complete=True, offset=118315, retries=2)
        with mock.patch.object(t.stage, 'segment', return_value=row) as segment:
            result = t.stage_files(channel, plan, [])
            assert result['runtime_sha256_measured'] is False and result['game_executed'] is False
            assert segment.call_args.kwargs == dict(resume=False, expected_offset=0)
        assert all('kill ' not in command and 'rm ' not in command and '/tmp/luma3d-fc1 --' not in command for _, command in channel.commands)
        assert any('/proc/3940/exe' in command for _, command in channel.commands)
        assert not any('/proc/3158/' in command or '/proc/3880/' in command for _, command in channel.commands)
        low = Transcript(directory, plan, free=14504)
        with mock.patch.object(t.stage, 'segment', side_effect=AssertionError('Transfer before space guard')):
            rejects(t.stage_files, low, plan, [])
        count += 2
    output = dict(passed=True, hardware=False, checks=count, plan_sha256=digest,
                  limitations='Transcript validates wrapper guards/commands only; existing RX2 protocol proofs and exact QEMU helper proof remain separate.')
    print(json.dumps(output))


if __name__ == '__main__':
    main()
