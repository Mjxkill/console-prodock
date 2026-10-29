#!/usr/bin/env python3
"""Compare COPY565 and native CLEAR on the exact, already tested Neo R19."""
import argparse
import fcntl
import json
import re
import shutil
import signal
import struct
import subprocess
import time

from board_trial_r19 import HERE, ROOT, BIT_SHA, BASE_GUARD, DISABLED, DEST, hw, sha, preflight
from board_trial import decode
from framebuffer_trial import CACHE
from isolate_r19_clear import ARM, CAPTURE, PACKET
from observe_r19_clear import SNAPSHOT
from z_cpu_probe_r19 import CSRS, UNCACHED

COLOR, SOURCE, DEPTH = 0x00800020, 0x00808000, 0x00810000
ANCHOR = HERE / 'r19_depth_cpu_20261026_234857/result.json'
ANCHOR_SHA = '54001816cb8c28b782c06454227bd4b6a5670c6ee5a0675abbd9d191ef2dddae'
CASES = [
    ('TARGET', [22 << 24, COLOR, DEPTH, (128 << 16) | 16, (256 << 16) | 256, 0, 0, 0]),
    ('COPY16', [29 << 24, SOURCE, (16 << 16) | 1, 32, 0, 0, (16 << 16) | 1, 0]),
    ('COPY7', [29 << 24, SOURCE, (16 << 16) | 1, 32, 5 << 16, 3 << 16, (7 << 16) | 1, 0]),
    ('CLEAR_COLOR16', [28 << 24, 1, 0x5aa5, 0x7bde, 0, (16 << 16) | 1, 0, 0]),
]
LIVE_GUARD = '''foreach {addr expected} {
    0xe9005080 0x4e435031 0xe9005088 4 0xe900508c 4
    0xe9001004 1 0xe9001008 4 0xe9001034 0 0xe900500c 6
} {
    if {[lindex [read_memory $addr 32 1] 0]!=$expected} {error "Previous depth-CLEAR state changed"}
}
echo DEPTH_STALL_ANCHOR_CONFIRMED
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    proof = preflight()
    assert sha(ANCHOR) == ANCHOR_SHA
    previous = json.loads(ANCHOR.read_text())
    assert previous['complete'] and previous['stopped_on'] == 'DEPTH_ONLY'
    assert previous['cases'][-1]['gpu_after'][1:3] == [1, 4]
    assert all(row['exact_guarded_readback'] and row['stall_unchanged'] for row in previous['cpu_probes'])
    for name, digest in previous['files'].items():
        assert sha(ANCHOR.parent / name) == digest, name
    regions = {
        'color': (COLOR - 32, bytes((i * 37 + 19) & 255 for i in range(4160))),
        'source': (SOURCE - 32, bytes((i * 53 + 41) & 255 for i in range(96))),
        'depth': (DEPTH - 32, bytes((i * 61 + 7) & 255 for i in range(4160))),
    }
    ordered = sorted(regions.values())
    assert all(a + len(d) < b for (a, d), (b, _) in zip(ordered, ordered[1:]))
    assert all(len(words) == 8 for _, words in CASES)
    expected_color = dict(TARGET=regions['color'][1])
    copied = bytearray(expected_color['TARGET'])
    copied[32:64] = regions['source'][1][32:64]
    expected_color['COPY16'] = bytes(copied)
    copied[38:52] = regions['source'][1][42:56]
    expected_color['COPY7'] = bytes(copied)
    copied[32:64] = struct.pack('<H', 0x5aa5) * 16
    expected_color['CLEAR_COLOR16'] = bytes(copied)
    assert len(set(expected_color.values())) == 4
    if args.check_only:
        print(json.dumps(dict(ready=True, hardware=False, bitstream_sha256=BIT_SHA,
                              cases=CASES, anchor_sha256=ANCHOR_SHA)))
        return
    out = HERE / ('r19_copy_' + time.strftime('%Y%m%d_%H%M%S'))
    r = dict(bitstream_sha256=BIT_SHA, qualification='FAIL', static_proof=proof,
             anchor_sha256=ANCHOR_SHA, scope='Same R19 COPY565 versus native CLEAR; guarded volatile DDR',
             cases=[], complete=False, fallback_attempted=False, fpga_reloaded=False,
             fpga_new_build=False, SD_written=False, flash_written=False, CPU_resumed=False)

    def save():
        (out / 'result.json').write_text(json.dumps(r, indent=2) + '\n')

    def run(name, code):
        cfg, log = out / (name + '.tcl'), out / (name + '.log')
        cfg.write_text(code + '\nshutdown\n')
        hw.run_child(['/usr/local/bin/openocd', '-f', str(ROOT / 'tools/neo/ae350_espprog.cfg'),
            '-c', 'adapter speed 1000; gdb_port disabled; tcl_port disabled; telnet_port disabled',
            '-f', str(cfg)], log, 40)
        return log.read_text()

    def interrupt(sig, frame):
        raise KeyboardInterrupt('Signal ' + str(sig))

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, interrupt)
    with (ROOT / 'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        active = subprocess.run(['ps', '-C', 'openocd', '-C', 'openFPGALoader', '-C', 'gao_sh',
            '-C', 'gao_analyzer', '-C', 'jtagserver', '-o', 'pid=,comm='], capture_output=True, text=True)
        assert active.returncode == 1 and not active.stdout.strip(), active.stdout
        r['identity'] = hw.usb_identity()
        assert r['identity']['neo']['serial'] == '2025041420'
        assert r['identity']['neo']['path'].endswith('/3-4.4.1')
        assert r['identity']['esp']['path'].endswith('/3-4.4.2')
        out.mkdir()
        shutil.copy2(__file__, out / 'controller.py')
        r['started_unix'] = time.time()
        save()
        touched = False
        try:
            assert 'DEPTH_STALL_ANCHOR_CONFIRMED' in run('live_guard', CSRS + BASE_GUARD + UNCACHED + LIVE_GUARD)
            touched = True
            hw.Hardware(out, r).program('reload_same_r19', DEST / 'impl/pnr/console_neo.fs', BIT_SHA)
            r['fpga_reloaded'] = True
            save()
            code = CSRS + BASE_GUARD + CACHE + UNCACHED + '''foreach addr {0xe9001004 0xe9001008 0xe9001034 0xe9005088 0xe900508c} {
    if {[lindex [read_memory $addr 32 1] 0]!=0} {error "Expected fresh idle R19"}
}
'''
            for name, (address, data) in regions.items():
                p = out / (name + '_seed.bin')
                p.write_bytes(data)
                code += f'load_image {{{p}}} {address:#x} bin\nverify_image {{{p}}} {address:#x} bin\n'
            assert 'SEEDS_OK' in run('seeds', code + 'echo SEEDS_OK\n')
            last = {name: data for name, (_, data) in regions.items()}
            prefix = CSRS + BASE_GUARD + UNCACHED
            for name, words in CASES:
                code = prefix + PACKET + SNAPSHOT + ARM
                code += 'packet {' + ' '.join(hex(w) for w in words) + '}\n'
                code += CAPTURE + 'gpu_snapshot after\n'
                for region, (address, data) in regions.items():
                    code += f'dump_image {{{out / (name + "_" + region + ".bin")}}} {address:#x} {len(data)}\n'
                log = run(name, code + DISABLED + 'echo CASE_OBSERVED\n')
                assert 'CASE_OBSERVED' in log
                row = dict(name=name, words=words,
                           completed=bool(int(re.search(r'^COMMAND_COMPLETE ([01])$', log, re.M)[1])))
                for key in ('BEFORE', 'AFTER'):
                    row['gpu_' + key.lower()] = [int(w, 0) for w in re.search(r'^GPU_' + key + r' (.+)$', log, re.M)[1].split()]
                    assert len(row['gpu_' + key.lower()]) == 26
                row['error_deltas'] = {str(i): (row['gpu_after'][i] - row['gpu_before'][i]) & 0xffffffff
                                       for i in (3, 7, 9, 13, 19)}
                raw = [int(w, 0) for w in re.search(r'^NCP (.+)$', log, re.M)[1].split()]
                epoch = int(re.search(r'^ARM_EPOCH ([01])$', log, re.M)[1])
                row['capture_raw'] = raw
                row['capture'] = decode(raw[4] | raw[5] << 32, words[0] >> 24, epoch)
                for region, (_, initial) in regions.items():
                    got = (out / (name + '_' + region + '.bin')).read_bytes()
                    expected = expected_color[name] if region == 'color' else initial
                    assert len(got) == len(expected)
                    row[region] = dict(expected_matches=got == expected, unchanged=got == last[region],
                        outside_target_unchanged=(got[:32] == initial[:32] and got[64:] == initial[64:])
                        if region == 'color' else got == initial,
                        payload=got[32:64].hex(), differing_expected_bytes=sum(a != b for a, b in zip(got, expected)))
                    last[region] = got
                r['cases'].append(row)
                save()
                print(json.dumps(row), flush=True)
                assert all(row[k]['outside_target_unchanged'] for k in regions), 'Memory outside destination changed'
                if not row['completed'] or any(row['error_deltas'].values()):
                    r['stopped_on'] = name
                    break
                assert all(row[k]['expected_matches'] for k in regions), 'Incorrect completed operation'
                assert row['capture']['finding'] == 'OPCODE_CAPTURE_CONSISTENT', 'Opcode capture differs'
            r['complete'] = True
            r['left_state'] = 'Internal bars; CPU halted; ' + ('GPU stopped on ' + r['stopped_on'] if r.get('stopped_on') else 'all commands completed')
        except BaseException as exc:
            r['error'] = repr(exc)
            save()
            if touched:
                r['fallback_attempted'] = True
                for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
                    signal.signal(sig, signal.SIG_IGN)
                try:
                    hw.Hardware(out, r).program('fallback_same_r19', DEST / 'impl/pnr/console_neo.fs', BIT_SHA)
                    run('fallback_guard', BASE_GUARD)
                    r['fallback_restored'] = True
                    r['left_state'] = 'Exact R19 reloaded; internal bars; CPU halted; GPU fresh'
                except BaseException as fallback:
                    r['fallback_error'] = repr(fallback)
            raise
        finally:
            r['finished_unix'] = time.time()
            r['files'] = {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'result.json'}
            save()
            print(json.dumps(dict(output=str(out), complete=r['complete'], stopped_on=r.get('stopped_on'),
                                  error=r.get('error'), left_state=r.get('left_state'))), flush=True)


if __name__ == '__main__':
    main()
