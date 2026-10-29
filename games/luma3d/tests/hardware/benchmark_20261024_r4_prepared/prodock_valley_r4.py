#!/usr/bin/env python3
"""Frozen R3/R4 comparison. Run only after package review and board authorization."""
import argparse
import fcntl
import json
import re
import signal
import sys
import time
from pathlib import Path
import serial
from prodock_transport import Transport, RECEIVER_SHA
from prodock_valley_ab import process, stop, launch, progress, PORT, RELEASE
from prodock_valley_trial import sha, display, game_counters
from prodock_valley_benchmark import readback, supervisor, wait_exit, parse_benchmark, fields, POSES

R3_SHA = '131ff6d7ca404e0188bb7e0ff68c25bd2db29b52ae27c561e019f6c53dfcc270'
R3_PROGRAM = 'luma3d-b3v2'
R3_INITIAL_PID = 302
R3_LIVE_PIDFILE = '/tmp/luma3d-live.pid'
R4_SHA = 'd346506621fa1f5177d746c43919610e866420d22cb3fe51c9b066ea6ff98a51'
R4_PROGRAM = 'luma3d-b4r1'
HELPER = 'runtime-helper-r4'


def confirm_r3(tx):
    """Read-only preflight: exact last qualified process, not an old R2 PID."""
    assert process(tx, 'r3_initial', R3_PROGRAM, R3_LIVE_PIDFILE)
    data = tx.run('r3_pid_identity',
                  'p=`cat /tmp/luma3d-live.pid`; cat /proc/$p/comm; cat /proc/$p/status')
    assert re.search(rb'^'+R3_PROGRAM.encode()+rb'\r?$', data, re.M)
    pid = re.search(rb'^Pid:\s+(\d+)\r?$', data, re.M)
    state = re.search(rb'^State:\s+([A-Z])\s', data, re.M)
    assert pid and int(pid[1]) == R3_INITIAL_PID and state and state[1] not in (b'Z', b'X')
    return R3_INITIAL_PID


def restore_r3(tx, current, ever_started):
    """Called only after the caller armed cleanup before stopping R3."""
    if current:
        stop(tx, current[0], 'stop_failed_r4', current[1])
    if not ever_started and process(tx, 'possible_live_r3', R3_PROGRAM, R3_LIVE_PIDFILE):
        return progress(tx, R3_PROGRAM, 'l3v2_live.log', 'r3_preserved', R3_LIVE_PIDFILE)
    pidfile = '/tmp/l3r4_restore.pid'
    launch(tx, R3_PROGRAM, 'l3r4_restore.log', 'restore_r3', pidfile)
    counters = progress(tx, R3_PROGRAM, 'l3r4_restore.log', 'restored_r3', pidfile)
    tx.run('publish_restored_r3_pid', 'cp /tmp/l3r4_restore.pid /tmp/luma3d-live.pid')
    return counters


def improvement(records):
    """Explicit conservative acceptance, separate from successful execution."""
    import math
    ratios = []
    for pose in (0, 700, 1600, 2200):
        baseline = next(r for r in records if r['pose'] == pose and r['variant'] == 'r3')
        candidate = next(r for r in records if r['pose'] == pose and r['variant'] == 'r4')
        ratios.append(baseline['result']['elapsed']/candidate['result']['elapsed'])
    geometric_mean = math.prod(ratios)**.25
    return dict(accepted=geometric_mean >= 1.10 and min(ratios) >= .97,
                elapsed_ratios=ratios, geometric_mean=geometric_mean,
                rule='At least 10% geometric-mean throughput gain, no pose slower by more than 3%; pixels/errors checked separately')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.bundle/'manifest.json').read_text())
    assert manifest['live_sha256'] == R3_SHA
    for key, expected, name in (('r3', R3_SHA, R3_PROGRAM), ('r4', R4_SHA, R4_PROGRAM)):
        program = manifest['programs'][key]
        assert program['sha256'] == expected and program['name'] == name
        frozen = json.loads((args.bundle/(key+'_game_manifest.json')).read_text())
        assert frozen['riscv']['sha256'] == expected
        assert frozen['riscv']['bytes'] == program['bytes'] and frozen['riscv']['crc32'] == program['crc32']
        for pose in POSES:
            ref = program['references'][str(pose)]
            assert ref['bytes'] == 192000 and ref['sha256'] == frozen['captures'][f'frame_{pose}']['image_sha256']
            assert ref['file'] == (f'l3v2-r3-p{pose}.lz4' if key == 'r3' else f'l3r4-r4-p{pose}.lz4')
    candidate = manifest['programs']['r4']; delta = candidate['delta']
    assert delta['old_sha256'] == R3_SHA and delta['new_sha256'] == R4_SHA
    assert delta['new_bytes'] == candidate['bytes'] and delta['new_crc32'] == candidate['crc32']
    assert delta['file'] == 'l3r4.delta.lz4'
    for name, record in manifest['files'].items():
        assert re.fullmatch(r'[a-zA-Z0-9_.-]+', name)
        path = args.bundle/name
        assert path.stat().st_size == record['bytes'] and sha(path) == record['sha256'], name
    for name in ('prodock_valley_r4.py', 'prodock_valley_benchmark.py', 'prodock_transport.py',
                 'prodock_valley_ab.py', 'prodock_valley_trial.py'):
        assert sha(Path(__file__).with_name(name)) == manifest['files'][name]['sha256'], name
    assert manifest['files'][HELPER]['sha256'] == '579d5a85fb798950f2f249299299c1084ce873c288d769c4b87fa539842563c9'
    for name, expected in manifest['shared_tools'].items():
        assert sha(args.root/'tools'/name) == expected
    args.out.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.bundle.resolve()))
    from check_linux import command
    result = dict(passed=False, candidate_accepted=False, manifest_sha256=sha(args.bundle/'manifest.json'),
                  programs=manifest['programs'], transfers=[], benchmarks=[],
                  fpga='G22r0 unchanged', kernel=RELEASE.decode(), fpga_writes=0, sd_writes=0, flash_writes=0)
    def interrupted(signum, frame):
        raise KeyboardInterrupt('Signal '+str(signum))
    signal.signal(signal.SIGTERM, interrupted); signal.signal(signal.SIGHUP, interrupted)
    with open('/tmp/prodock-diagnostic.lock', 'a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with serial.Serial(PORT, 115200, timeout=.1, exclusive=True) as uart:
            tx = Transport(uart, command, args.out)
            stopped = False; current = None; ever_started = False
            try:
                uart.write(b'\n'); time.sleep(.2); uart.read(16000)
                before = tx.run('before', 'uname -r; prodockctl display; cat /proc/mounts')
                assert re.search(rb'^'+RELEASE+rb'\r?$', before, re.M)
                assert b'tmpfs /tmp tmpfs ' in before and not re.search(rb'^/dev/mmc\S* ', before, re.M)
                result['before'] = display(before); result['initial_pid'] = confirm_r3(tx)
                tags = [f'l3r4_{key}_{pose}' for pose in POSES for key in ('r3', 'r4')]
                tags += ['l3r4_endurance', 'l3r4_live', 'l3r4_restore']
                tx.run('fresh_launch_files', ' && '.join('test ! -f /tmp/'+tag+'.pid' for tag in tags))
                readback(tx, 'receiver_readback', '/tmp/luma-rx', 1464, RECEIVER_SHA)
                # Reinstall the already-reviewed helper into a fresh RAM file.
                # Receiver CRC avoids repeating a 140-second octal helper dump.
                result['transfers'].append(tx.transfer(args.bundle/HELPER, HELPER))
                tx.run('helper_mode', 'chmod 700 /tmp/'+HELPER)
                result['transfers'].append(tx.transfer(args.bundle/delta['file'], delta['file']))
                installed = tx.run('install_r4',
                    f'/tmp/{HELPER} patch /tmp/{delta["file"]} /tmp/{R4_PROGRAM} '
                    f'{delta["patch_bytes"]} {delta["patch_crc32"]} /tmp/{R3_PROGRAM}', 60)
                assert f'LUMA3D_UNPACK_OK bytes={candidate["bytes"]} crc32={candidate["crc32"]}'.encode() in installed
                tx.run('mode_r4', 'chmod 700 /tmp/'+R4_PROGRAM)
                for key in ('r3', 'r4'):
                    for pose in POSES:
                        ref = manifest['programs'][key]['references'][str(pose)]
                        if key == 'r4':
                            result['transfers'].append(tx.transfer(args.bundle/ref['file'], ref['file']))
                        checked = tx.run(f'verify_{key}_{pose}', f'/tmp/{HELPER} verify /tmp/{ref["file"]} unused 192000 {ref["crc32"]}')
                        assert f'LUMA3D_VERIFY_OK bytes=192000 crc32={ref["crc32"]}'.encode() in checked
                assert process(tx, 'r3_preserved_until_ready', R3_PROGRAM)
                print('R4_BENCHMARK_READY: all identities checked; R3/R4 comparison starts in 10 seconds', flush=True)
                time.sleep(10)
                stopped = True; stop(tx, R3_PROGRAM, 'stop_live_r3')
                result['released'] = display(tx.run('released', 'prodockctl display'))
                for pose in POSES:
                    for key in ('r3', 'r4'):
                        program = manifest['programs'][key]
                        tag = f'l3r4_{key}_{pose}'
                        if key == 'r4' and pose == 0:
                            print('R4_READY_TO_RUN: first native R4 execution follows in 10 seconds', flush=True)
                            time.sleep(10)
                        current = (program['name'], '/tmp/'+tag+'.pid'); ever_started = True
                        initial = tx.run(tag+'_launch', supervisor(program['name'], tag, pose))
                        code = wait_exit(uart, args.out, tag, initial=initial)
                        log = tx.run(tag+'_log', 'cat /tmp/'+tag+'.log')
                        assert code == 0, (tag, code)
                        current = None
                        record = parse_benchmark(log, pose)
                        record.update(variant=key, pose=pose, display=display(tx.run(tag+'_display', 'prodockctl display')))
                        ref = program['references'][str(pose)]
                        pixels = tx.run(tag+'_pixels', f'/tmp/{HELPER} pixels /tmp/{ref["file"]} page0 192000 {ref["crc32"]}', 60)
                        assert f'LUMA3D_PIXELS pixels=96000 mismatch=0 actual_crc={ref["crc32"]} expected_crc={ref["crc32"]}'.encode() in pixels
                        record['pixel_mismatches'] = 0; result['benchmarks'].append(record)
                        print(f'{tag}: pixels PASS, {record["result"]["fps"]} FPS', flush=True)
                result['improvement'] = improvement(result['benchmarks'])
                current = (R4_PROGRAM, '/tmp/l3r4_endurance.pid')
                launch(tx, R4_PROGRAM, 'l3r4_endurance.log', 'endurance_launch', current[1])
                result['warm_display'] = progress(tx, R4_PROGRAM, 'l3r4_endurance.log', 'endurance_warm', current[1])
                begin = time.monotonic(); print('R4 endurance: 75 seconds without UART commands', flush=True)
                while time.monotonic()-begin < 75:
                    time.sleep(max(0, min(5, 75-(time.monotonic()-begin))))
                assert process(tx, 'endurance_alive_at_deadline', R4_PROGRAM, current[1])
                stop(tx, R4_PROGRAM, 'endurance_stop', current[1]); current = None
                log = tx.run('endurance_log', 'cat /tmp/l3r4_endurance.log')
                result['endurance'] = fields(log, 'LUMA3D_RESULT')
                assert result['endurance']['elapsed'] >= 75 and result['endurance']['frames'] > 1
                assert re.search(rb'^LUMA3D_PERF [^\r\n]*\bcollected=4/4\b', log, re.M)
                result['endurance']['four_letters_observed'] = True
                result['endurance_counters'] = game_counters(log)
                result['after_endurance'] = display(tx.run('after_endurance', 'prodockctl display'))
                selected = R4_PROGRAM if result['improvement']['accepted'] else R3_PROGRAM
                current = (selected, '/tmp/l3r4_live.pid')
                launch(tx, selected, 'l3r4_live.log', 'live_launch', current[1])
                result['live_display'] = progress(tx, selected, 'l3r4_live.log', 'live', current[1])
                tx.run('publish_live_pid', 'cp /tmp/l3r4_live.pid /tmp/luma3d-live.pid')
                result['passed'] = True; result['candidate_accepted'] = result['improvement']['accepted']
                result['left_running'] = selected+' automatic valley; no NEBULA'
            except BaseException as error:
                result['error'] = repr(error)
                if stopped:
                    try:
                        uart.write(b'\x03'); uart.flush(); time.sleep(.3); uart.read(16000)
                        result['restored_display'] = restore_r3(tx, current, ever_started)
                        result['restored_r3'] = True
                    except BaseException as cleanup:
                        result['cleanup_error'] = repr(cleanup)
                raise
            finally:
                (args.out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
                print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
