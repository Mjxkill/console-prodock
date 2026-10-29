#!/usr/bin/env python3
"""Reconstruct a rebuilt small helper from its verified previous ELF.

Only a fresh /tmp/stage_reader2 is written. Unchanged ranges are copied from
the previous file, changed bytes sent literally. Full readback MUST equal the
new host ELF before execution. No in-place patch, ambiguous append retry,
JTAG operation, or game launch is performed.
"""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import re
import signal

import bootstrap_reader as link

REMOTE = '/tmp/stage_reader2'


def plan(old, new):
    assert len(old) == len(new) == link.READER_BYTES
    assert hashlib.sha256(old).hexdigest() == link.READER_SHA
    # The compiler may shift instructions after a two-byte code insertion.
    # Reuse long equal spans regardless of offset; send short spans literally
    # to avoid hundreds of tiny shell commands. Full final readback is decisive.
    matches = [match for match in difflib.SequenceMatcher(None, old, new, autojunk=False).get_matching_blocks()
               if match.size >= 64]
    changed = len(new) - sum(match.size for match in matches)
    assert 0 < changed <= 4096, 'Not a small reviewed rebuild'
    commands = [f'(set -C; umask 077; : > {REMOTE})']
    pos = 0
    for match in [*matches, difflib.Match(len(old), len(new), 0)]:
        for start in range(pos, match.b, 96):
            value = ''.join('\\%03o' % byte for byte in new[start:min(start + 96, match.b)])
            commands.append(f"printf '{value}' >> {REMOTE}")
        if match.size:
            commands.append(f'dd if={link.REMOTE} bs=1 skip={match.a} count={match.size} >> {REMOTE}')
        pos = match.b + match.size
    return commands, changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old', type=Path, required=True)
    parser.add_argument('--new', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    old, new = args.old.read_bytes(), args.new.read_bytes()
    assert hashlib.sha256(new).hexdigest() == args.sha256
    commands, changed = plan(old, new)
    if not args.run:
        print(json.dumps({'prepared': True, 'changed_bytes': changed, 'commands': commands}))
        return
    args.out.mkdir(parents=True, exist_ok=False)
    result = dict(passed=False, hardware=True, programmer=link.PROGRAMMER,
                  port=str(link.PORT), game_launched=False, fpga_writes=0,
                  sd_writes=0, changed_bytes=changed, reader_bytes=len(new))
    def interrupted(number, frame):
        raise InterruptedError('Signal ' + str(number))
    previous = {n: signal.signal(n, interrupted) for n in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    try:
        transport = link.imports()
        with link.open_channel(args.out) as channel:
            channel.initial_shell()
            raw = channel.run('preflight', 'uname -r && test -f /tmp/stage_reader && test ! -L /tmp/stage_reader'
                              ' && test ! -e /tmp/luma3d-fm4a && test ! -L /tmp/luma3d-fm4a')
            assert re.search(rb'^' + link.KERNEL.encode() + rb'\r?$', raw, re.M)
            for index, command in enumerate(commands):
                channel.run('reconstruct_' + str(index), command)
            raw = channel.run('full_readback', f"printf '\\nRX2_BOOT_READ_BEGIN\\n' && od -b -v {REMOTE} && printf '\\nRX2_BOOT_READ_END\\n'", timeout=180)
            got = transport.bootstrap.validate_readback({'elf_bytes': len(new), 'elf_sha256': args.sha256}, raw)
            assert got == new
            result['reader_full_readback_sha256'] = args.sha256
            channel.run('chmod_verified', 'chmod 700 ' + REMOTE)
            raw = channel.run('extract', REMOTE + ' ' + link.GAME, timeout=120)
            assert len(re.findall(rb'^STAGE_FM4A_OK bytes=16640496 crc=fa358bf4\r?$', raw, re.M)) == 1
            result.update(passed=True, game=link.GAME, game_bytes=16640496,
                          game_crc32='fa358bf4', game_sha256_hardware_measured=False)
    except BaseException as error:
        result['error'] = repr(error)
        result['automatic_retry'] = False
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)
        (args.out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)
    raise SystemExit(not result['passed'])


if __name__ == '__main__':
    main()
