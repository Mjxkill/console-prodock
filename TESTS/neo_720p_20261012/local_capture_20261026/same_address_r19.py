#!/usr/bin/env python3
"""Same R19 bitstream: legacy FILL and V1 CLEAR at the identical DDR address."""
import argparse
import fcntl
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import time

from board_trial_r19 import HERE, ROOT, BIT_SHA, BASE_GUARD, DISABLED, DEST, hw, sha, preflight
from board_trial import decode
from framebuffer_trial import CACHE
from isolate_r19_clear import ARM, CAPTURE, PACKET
from observe_r19_clear import SNAPSHOT
from trial_memory_observer import STALLED_GUARD

COLOR = 0x00800020
DEPTH = 0x00810000
CASES = [
    ('TARGET', [22 << 24, COLOR, DEPTH, (128 << 16) | 16, (256 << 16) | 256, 0, 0, 0], True),
    ('LEGACY_32B', [0x0100a600, 32 << 16, (32 << 16) | 1, 0, 0, 0, 0, 0], False),
    ('CLEAR_FLAGS_ZERO', [28 << 24, 0, 0x5aa5, 0x7bde, 0, (16 << 16) | 1, 0, 0], True),
    ('CLEAR_EMPTY', [28 << 24, 3, 0x5aa5, 0x7bde, 0, 0, 0, 0], True),
    ('CLEAR_COLOR_16PX', [28 << 24, 1, 0x5aa5, 0x7bde, 0, (16 << 16) | 1, 0, 0], True),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    preflight()
    anchor = HERE / 'r19_clear_isolate_01/result.json'
    old = json.loads(anchor.read_text())
    assert old['bitstream_sha256'] == BIT_SHA and old['measurements_complete']
    assert old['stopped_on'] == 'CLEAR_COLOR_16PX' and old['cases'][-1]['gpu_after'][1:3] == [1, 4]
    for name, digest in old['files'].items():
        assert sha(anchor.parent / name) == digest, name
    assert COLOR == 0x800000 + (CASES[1][1][1] >> 16)
    assert COLOR % 32 == 0 and 2 * (CASES[-1][1][5] >> 16) == 32
    seed = bytes((i * 37 + 19) & 255 for i in range(4160))
    zseed = bytes((i * 53 + 41) & 255 for i in range(4160))
    after_legacy = seed[:32] + bytes([0xa6]) * 32 + seed[64:]
    after_clear = seed[:32] + struct.pack('<H', 0x5aa5) * 16 + seed[64:]
    assert len(seed) == len(after_legacy) == len(after_clear) == 4160
    assert after_clear != after_legacy != seed
    assert COLOR - 32 + len(seed) < DEPTH - 32
    if args.check_only:
        print(json.dumps(dict(preflight_passed=True, hardware=False, bitstream_sha256=BIT_SHA,
                              common_byte_address=hex(COLOR), byte_count=32, case_count=len(CASES))))
        return
    out = HERE / 'r19_same_address_01'
    assert not out.exists()
    result = dict(bitstream_sha256=BIT_SHA, qualification='FAIL', anchor_sha256=sha(anchor),
                  scope='Reload exact R19 into Neo SRAM; legacy and native writes at identical byte address',
                  common_byte_address=COLOR, byte_count=32, source_RTL_changed=False,
                  fpga_reloaded=False, measurements_complete=False, SD_written=False,
                  flash_written=False, cases=[])

    def save():
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')

    def run(name, code):
        cfg = out / (name + '.tcl')
        cfg.write_text(code + '\nshutdown\n')
        log = out / (name + '.log')
        hw.run_child(['/usr/local/bin/openocd', '-f', str(ROOT / 'tools/neo/ae350_espprog.cfg'),
                      '-c', 'adapter speed 1000; gdb_port disabled; tcl_port disabled; telnet_port disabled',
                      '-f', str(cfg)], log, 40)
        return log.read_text()

    with (ROOT / 'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        active = subprocess.run(['ps', '-C', 'openocd', '-C', 'openFPGALoader', '-C', 'gao_sh',
                                 '-C', 'gao_analyzer', '-C', 'jtagserver', '-o', 'pid=,comm='],
                                capture_output=True, text=True)
        assert active.returncode == 1 and not active.stdout.strip(), active.stdout
        result['identity'] = hw.usb_identity()
        assert result['identity']['neo']['path'].endswith('/3-4.4.1')
        assert result['identity']['esp']['path'].endswith('/3-4.4.2')
        out.mkdir()
        shutil.copy2(Path(__file__), out / 'controller.py')
        result['started_unix'] = time.time()
        save()
        try:
            run('guard_stalled', STALLED_GUARD)
            hw.Hardware(out, result).program('reload_same_r19', DEST / 'impl/pnr/console_neo.fs', BIT_SHA)
            result['fpga_reloaded'] = True
            save()
            prefix = 'riscv expose_csrs 1994,1996,2000\n' + BASE_GUARD + CACHE
            code = prefix + '''foreach addr {0xe9001004 0xe9001008 0xe9001034 0xe9005088 0xe900508c} {
    if {[lindex [read_memory $addr 32 1] 0]!=0} {error "R19 fresh state mismatch"}
}
'''
            for name, data, address in [('common_seed', seed, COLOR - 32), ('depth_seed', zseed, DEPTH - 32)]:
                path = out / (name + '.bin')
                path.write_bytes(data)
                code += f'load_image {{{path}}} {address:#x} bin\nverify_image {{{path}}} {address:#x} bin\n'
            assert 'SEEDS_READY' in run('seeds', code + 'echo SEEDS_READY\n')
            previous_color = seed
            for name, words, capture in CASES:
                code = prefix + PACKET + SNAPSHOT + (ARM if capture else '')
                code += 'packet {' + ' '.join(hex(w) for w in words) + '}\n'
                code += (CAPTURE if capture else '') + 'gpu_snapshot after\n'
                for region, address in [('color', COLOR - 32), ('depth', DEPTH - 32)]:
                    code += f'dump_image {{{out / (name + "_" + region + ".bin")}}} {address:#x} 4160\n'
                text = run(name, code + DISABLED + 'echo CASE_OBSERVED\n')
                item = dict(name=name, words=words,
                            completed=bool(int(re.search(r'^COMMAND_COMPLETE ([01])$', text, re.M)[1])))
                for key in ('BEFORE', 'AFTER'):
                    item['gpu_' + key.lower()] = [int(w, 0) for w in re.search(r'^GPU_' + key + r' (.+)$', text, re.M)[1].split()]
                item['error_deltas'] = {str(j): (item['gpu_after'][j] - item['gpu_before'][j]) & 0xffffffff
                                        for j in (3, 7, 9, 13, 19)}
                if capture:
                    raw = [int(w, 0) for w in re.search(r'^NCP (.+)$', text, re.M)[1].split()]
                    epoch = int(re.search(r'^ARM_EPOCH ([01])$', text, re.M)[1])
                    item['capture_raw'] = raw
                    item['capture'] = decode(raw[4] | raw[5] << 32, words[0] >> 24, epoch)
                expected_color = seed if name == 'TARGET' else after_clear if name == 'CLEAR_COLOR_16PX' else after_legacy
                for region, before, expected in [('color', seed, expected_color), ('depth', zseed, zseed)]:
                    got = (out / (name + '_' + region + '.bin')).read_bytes()
                    assert len(got) == len(expected)
                    item[region] = dict(bytes=len(got), expected_matches=got == expected,
                                        guards_unchanged=got[:32] == before[:32] and got[-32:] == before[-32:],
                                        different_offsets=[i for i, (a, b) in enumerate(zip(got, expected)) if a != b][:32])
                    if region == 'color':
                        item[region]['unchanged_since_previous'] = got == previous_color
                        item[region]['first_32_payload_bytes'] = got[32:64].hex()
                        previous_color = got
                result['cases'].append(item)
                save()
                print(json.dumps(item), flush=True)
                if not item['completed'] or any(item['error_deltas'].values()):
                    result['stopped_on'] = name
                    result['measurements_complete'] = True
                    break
                assert all(item[k]['expected_matches'] for k in ('color', 'depth')), 'DDR mismatch'
            else:
                result['measurements_complete'] = True
        except BaseException as exc:
            result['error'] = repr(exc)
            raise
        finally:
            result['finished_unix'] = time.time()
            result['files'] = {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'result.json'}
            save()
            print(json.dumps({k: v for k, v in result.items() if k not in ('identity', 'files', 'cases')}), flush=True)


if __name__ == '__main__':
    main()
