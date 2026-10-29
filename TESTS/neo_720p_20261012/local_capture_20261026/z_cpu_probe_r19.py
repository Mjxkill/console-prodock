#!/usr/bin/env python3
"""Exact R19: depth-only CLEAR, then bounded CPU writes during a native stall."""
import argparse
import fcntl
import json
from pathlib import Path
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

COLOR, DEPTH, WITNESS = 0x00800020, 0x00810000, 0x00820000
CASES = [
    ('TARGET', [22 << 24, COLOR, DEPTH, (128 << 16) | 16, (256 << 16) | 256, 0, 0, 0], True),
    ('LEGACY', [0x0100a600, 32 << 16, (32 << 16) | 1, 0, 0, 0, 0, 0], False),
    ('FLAGS_ZERO', [28 << 24, 0, 0x5aa5, 0x7bde, 0, 16 << 16 | 1, 0, 0], True),
    ('EMPTY', [28 << 24, 3, 0x5aa5, 0x7bde, 0, 0, 0, 0], True),
    ('DEPTH_ONLY', [28 << 24, 2, 0x5aa5, 0x7bde, 0, 16 << 16 | 1, 0, 0], True),
    ('COLOR_ONLY', [28 << 24, 1, 0x5aa5, 0x7bde, 0, 16 << 16 | 1, 0, 0], True),
]
CSRS = 'riscv expose_csrs 1994,1996,2000\n'
UNCACHED = '''set cc [get_reg -force {csr1994}]
if {[dict get $cc csr1994]!=0} {error "Cache control is not disabled"}
echo "CACHE_CONTROL [dict get $cc csr1994]"
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    proof = preflight()
    seed_c = bytes((i * 37 + 19) & 255 for i in range(4160))
    seed_z = bytes((i * 53 + 41) & 255 for i in range(4160))
    seed_w = bytes((i * 61 + 7) & 255 for i in range(96))
    assert COLOR - 32 + len(seed_c) < DEPTH - 32
    assert DEPTH - 32 + len(seed_z) < WITNESS - 32
    assert all(len(words) == 8 for _, words, _ in CASES)
    if args.check_only:
        print(json.dumps(dict(ready=True, hardware=False, bitstream_sha256=BIT_SHA,
                              cases=[x[0] for x in CASES], native_bytes=32, cpu_probe_bytes=32)))
        return
    out = HERE / ('r19_depth_cpu_' + time.strftime('%Y%m%d_%H%M%S'))
    r = dict(bitstream_sha256=BIT_SHA, qualification='FAIL', static_proof=proof,
             scope='Depth-only native CLEAR and CPU writes in guarded volatile DDR on existing R19',
             cases=[], cpu_probes=[], complete=False, fallback_attempted=False,
             fpga_new_build=False, SD_written=False, flash_written=False,
             CPU_resumed=False, DDR_written=True)

    def save():
        (out / 'result.json').write_text(json.dumps(r, indent=2) + '\n')

    def run(name, code, timeout=40):
        cfg = out / (name + '.tcl')
        cfg.write_text(code + '\nshutdown\n')
        log = out / (name + '.log')
        hw.run_child(['/usr/local/bin/openocd', '-f', str(ROOT / 'tools/neo/ae350_espprog.cfg'),
            '-c', 'adapter speed 1000; gdb_port disabled; tcl_port disabled; telnet_port disabled',
            '-f', str(cfg)], log, timeout)
        return log.read_text()

    def dumps(label):
        return ''.join(f'dump_image {{{out / (label + "_" + name + ".bin")}}} {addr - 32:#x} {size}\n'
                       for name, addr, size in [('color', COLOR, 4160), ('depth', DEPTH, 4160)])

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
        out.mkdir()
        shutil.copy2(__file__, out / 'controller.py')
        r['started_unix'] = time.time()
        save()
        touched = False
        try:
            code = CSRS + BASE_GUARD + '''foreach addr {0xe9001004 0xe9001008 0xe9001034 0xe9005088 0xe900508c} {
    if {[lindex [read_memory $addr 32 1] 0]!=0} {error "Expected fresh idle R19; do not proceed"}
}
if {[lindex [read_memory 0xe9005080 32 1] 0]!=0x4e435031} {error "Wrong observer"}
echo FRESH_R19_CONFIRMED
'''
            assert 'FRESH_R19_CONFIRMED' in run('fresh_guard', code)
            touched = True
            code = CSRS + BASE_GUARD + CACHE + UNCACHED
            for name, data, address in [('color_seed', seed_c, COLOR - 32), ('depth_seed', seed_z, DEPTH - 32),
                                         ('witness_seed', seed_w, WITNESS - 32)]:
                p = out / (name + '.bin')
                p.write_bytes(data)
                code += f'load_image {{{p}}} {address:#x} bin\nverify_image {{{p}}} {address:#x} bin\n'
            assert 'SEEDS_OK' in run('seeds', code + 'echo SEEDS_OK\n')
            previous_c, previous_z = seed_c, seed_z
            prefix = CSRS + BASE_GUARD + UNCACHED
            for name, words, capture in CASES:
                code = prefix + PACKET + SNAPSHOT + (ARM if capture else '')
                code += 'packet {' + ' '.join(hex(w) for w in words) + '}\n'
                code += (CAPTURE if capture else '') + 'gpu_snapshot after\n' + dumps(name) + DISABLED
                log = run(name, code + 'echo CASE_OBSERVED\n')
                assert 'CASE_OBSERVED' in log
                item = dict(name=name, words=words,
                    completed=bool(int(re.search(r'^COMMAND_COMPLETE ([01])$', log, re.M)[1])))
                for key in ('BEFORE', 'AFTER'):
                    item['gpu_' + key.lower()] = [int(w, 0) for w in re.search(r'^GPU_' + key + r' (.+)$', log, re.M)[1].split()]
                item['error_deltas'] = {str(i): (item['gpu_after'][i] - item['gpu_before'][i]) & 0xffffffff
                                       for i in (3, 7, 9, 13, 19)}
                if capture:
                    raw = [int(w, 0) for w in re.search(r'^NCP (.+)$', log, re.M)[1].split()]
                    epoch = int(re.search(r'^ARM_EPOCH ([01])$', log, re.M)[1])
                    item['capture'] = decode(raw[4] | raw[5] << 32, words[0] >> 24, epoch)
                expected_c, expected_z = previous_c, previous_z
                if name == 'LEGACY': expected_c = seed_c[:32] + b'\xa6' * 32 + seed_c[64:]
                if name == 'DEPTH_ONLY': expected_z = seed_z[:32] + struct.pack('<H', 0x7bde) * 16 + seed_z[64:]
                if name == 'COLOR_ONLY': expected_c = seed_c[:32] + struct.pack('<H', 0x5aa5) * 16 + seed_c[64:]
                got = []
                for label, initial, previous, expected in [('color', seed_c, previous_c, expected_c),
                                                          ('depth', seed_z, previous_z, expected_z)]:
                    data = (out / (name + '_' + label + '.bin')).read_bytes()
                    assert len(data) == len(initial)
                    item[label] = dict(expected_matches=data == expected, unchanged=data == previous,
                        guards_unchanged=data[:32] == initial[:32] and data[-32:] == initial[-32:],
                        first_payload=data[32:64].hex())
                    got.append(data)
                r['cases'].append(item)
                save()
                print(json.dumps(item), flush=True)
                assert all(item[k]['guards_unchanged'] for k in ('color', 'depth')), 'Guard changed'
                assert not any(item['error_deltas'].values()), 'GPU error delta'
                if not item['completed']:
                    r['stopped_on'] = name
                    break
                assert item['color']['expected_matches'] and item['depth']['expected_matches'], 'Incorrect completed write'
                previous_c, previous_z = got
            if r.get('stopped_on'):
                stalled = r['cases'][-1]['gpu_after']
                assert stalled[1] == 1
                guard = prefix + f'''if {{[lindex [read_memory 0xe9001004 32 1] 0]!=1 || [lindex [read_memory 0xe9001008 32 1] 0]!={stalled[2]}}} {{error "Stall state changed"}}
'''
                for i in range(3):
                    p = out / f'cpu_pattern_{i}.bin'
                    data = bytes((j * (37 + i * 8) + 59 + i * 67) & 255 for j in range(32))
                    p.write_bytes(data)
                    dumped = out / f'cpu_readback_{i}.bin'
                    code = guard + f'load_image {{{p}}} {WITNESS:#x} bin\n'
                    code += f'dump_image {{{dumped}}} {WITNESS - 32:#x} 96\n'
                    code += 'echo "GPU_AFTER_CPU [read_memory 0xe9001000 32 26]"\necho CPU_WRITE_READ_COMPLETE\n'
                    log = run(f'cpu_probe_{i}', code)
                    assert 'CPU_WRITE_READ_COMPLETE' in log
                    expected = seed_w[:32] + data + seed_w[64:]
                    exact = dumped.read_bytes() == expected
                    gpu = [int(w, 0) for w in re.search(r'^GPU_AFTER_CPU (.+)$', log, re.M)[1].split()]
                    row = dict(index=i, exact_guarded_readback=exact, gpu_after=gpu, stall_unchanged=gpu[1:3] == stalled[1:3])
                    r['cpu_probes'].append(row)
                    save()
                    print(json.dumps(row), flush=True)
                    assert exact, 'CPU guarded readback differs'
                    if not row['stall_unchanged']:
                        break
                log = run('final_snapshot', prefix + SNAPSHOT + 'gpu_snapshot final\n' + dumps('final') + DISABLED + 'echo FINAL_OBSERVED\n')
                assert 'FINAL_OBSERVED' in log
                r['native_targets_unchanged_during_cpu_probes'] = all(
                    (out / ('final_' + name + '.bin')).read_bytes() ==
                    (out / (r['stopped_on'] + '_' + name + '.bin')).read_bytes()
                    for name in ('color', 'depth'))
            r['complete'] = True
            r['left_state'] = 'Internal bars; CPU halted; native ' + r.get('stopped_on', 'commands complete')
        except BaseException as exc:
            r['error'] = repr(exc)
            save()
            if touched:
                r['fallback_attempted'] = True
                for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP): signal.signal(sig, signal.SIG_IGN)
                try:
                    hw.Hardware(out, r).program('fallback_same_r19', DEST / 'impl/pnr/console_neo.fs', BIT_SHA)
                    run('fallback_guard', BASE_GUARD)
                    r['fallback_restored'] = True
                    r['left_state'] = 'Exact R19 reloaded; internal bars and halted CPU; GPU fresh'
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
