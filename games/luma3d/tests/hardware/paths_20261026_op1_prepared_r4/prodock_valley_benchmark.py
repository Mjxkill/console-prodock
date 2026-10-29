#!/usr/bin/env python3
"""Frozen R2/R3 fixed-pose comparison; one Pro Dock owner, RAM files only."""
import argparse
import fcntl
import hashlib
import json
import re
import signal
import sys
import time
from pathlib import Path

import serial
from prodock_transport import Transport, RECEIVER_SHA
from prodock_valley_trial import sha, display, game_counters
from prodock_valley_ab import process, stop, launch, progress, PORT, RELEASE

LIVE_SHA = '05b64630c267e364fa2bda14b64406cfa2eb1ae8c78ba58bc2b9ed4e053053f5'
EXPECTED = {
    'r2': 'ba5683209db75001a2c550751b1ed1850755bb75a126acc228e94df9b3d84beb',
    'r3': '131ff6d7ca404e0188bb7e0ff68c25bd2db29b52ae27c561e019f6c53dfcc270',
}
POSES = (0, 700, 1600, 2200)
FRAMES, WARMUP = 30, 3


def readback(tx, name, path, expected_bytes, expected_sha):
    # At the observed live-game console rate the 62 KiB helper's octal output
    # takes about 140 s. Keep the complete readback, with a bounded margin.
    data = tx.run(name, 'od -b -v '+path, 240)
    octets = bytearray()
    for line in data.replace(b'\r', b'').splitlines():
        if re.fullmatch(rb'[0-7]{7,} (?:[0-7]{3} ?){1,16}', line.strip()):
            octets.extend(int(x, 8) for x in line.split()[1:])
    assert len(octets) == expected_bytes and hashlib.sha256(octets).hexdigest() == expected_sha, path


def supervisor(program, tag, pose):
    # The actual child PID is published before wait. EXIT reaches the UART only
    # after process termination, all counter reads and GPU close have completed.
    return (f'( /tmp/{program} --benchmark --frames {FRAMES} --warmup {WARMUP} --advance {pose}'
            f' < /dev/null > /tmp/{tag}.log 2>&1 & p=$!; echo "$p" > /tmp/{tag}.pid;'
            f' wait "$p"; rc=$?; echo "$rc" > /tmp/{tag}.exit;'
            f' printf "\\nL3_EXIT_{tag}:%s\\n" "$rc" ) < /dev/null & echo BENCHMARK_LAUNCHED')


def wait_exit(uart, out, tag, timeout=300, initial=b''):
    # Deliberately no run(), write(), process query, prompt or periodic command.
    data = bytearray(initial)
    pattern = re.compile(rb'^L3_EXIT_'+tag.encode()+rb':(\d+)\r?$', re.M)
    start = last = time.monotonic()
    try:
        while time.monotonic()-start < timeout:
            found = pattern.search(data)
            if found:
                return int(found[1])
            data.extend(uart.read(4096))
            if time.monotonic()-last >= 15:
                print(f'{tag}: waiting for EXIT, UART read only', flush=True)
                last = time.monotonic()
        raise TimeoutError('No EXIT for '+tag)
    finally:
        (out/(tag+'_wait.log')).write_bytes(data)


def fields(log, prefix):
    lines = re.findall(rb'^'+prefix.encode()+rb' [^\r\n]+', log, re.M)
    assert len(lines) == 1, (prefix, lines)
    return {k.decode(): float(v) if b'.' in v else int(v)
            for k, v in re.findall(rb'(\w+)=([\d.]+)', lines[0])}


def parse_benchmark(log, pose):
    config = fields(log, 'LUMA3D_BENCHMARK')
    assert config == dict(pose=pose, warmup=WARMUP, measured_frames=FRAMES, fixed_pose=1, hardware=1)
    result = fields(log, 'LUMA3D_RESULT')
    assert result['frames'] == FRAMES and result['warmup'] == WARMUP
    assert result['benchmark'] == result['hardware'] == 1 and result['elapsed'] > 0
    counters = game_counters(log)
    assert counters['frames'] == FRAMES+WARMUP and counters['slivers'] == 0
    measured = fields(log, 'LUMA3D_BENCHMARK_COUNTERS')
    assert measured['cycles'] > 0 and measured['vertices'] > 0 and measured['slivers'] == 0
    assert set(measured) == {'cycles', 'vertices', 'raster_triangles', 'culled', 'intersections',
                             'slivers', 'feed_us', 'wait_us', 'cache_us', 'present_us'}
    return dict(result=result, measured=measured, whole_process_counters=counters,
                scope='30 fixed-pose measured frames after 3 warmup frames; no percentile claim')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.bundle/'manifest.json').read_text())
    assert manifest['live_sha256'] == LIVE_SHA
    for key, expected in EXPECTED.items():
        program = manifest['programs'][key]
        assert program['sha256'] == expected
        assert program['delta']['old_sha256'] == LIVE_SHA
        assert program['delta']['new_sha256'] == expected
        assert program['delta']['new_bytes'] == program['bytes']
        assert program['delta']['new_crc32'] == program['crc32']
        assert program['name'] == ('luma3d-b2v2' if key == 'r2' else 'luma3d-b3v2')
        frozen = json.loads((args.bundle/(key+'_game_manifest.json')).read_text())
        assert frozen['riscv']['sha256'] == expected
        for pose in POSES:
            reference = program['references'][str(pose)]
            assert reference['bytes'] == 192000
            assert reference['sha256'] == frozen['captures'][f'frame_{pose}']['image_sha256']
    for name, record in manifest['files'].items():
        assert re.fullmatch(r'[a-zA-Z0-9_.-]+', name)
        path = args.bundle/name
        assert path.stat().st_size == record['bytes'] and sha(path) == record['sha256'], name
    for module in ('prodock_valley_benchmark.py', 'prodock_transport.py', 'prodock_valley_ab.py', 'prodock_valley_trial.py'):
        assert sha(Path(__file__).with_name(module)) == manifest['files'][module]['sha256'], module
    for name, expected in manifest['shared_tools'].items():
        assert sha(args.root/'tools'/name) == expected, name
    args.out.mkdir(parents=True, exist_ok=False)
    # Import the copied, hashed transport dependencies, not mutable work files.
    sys.path.insert(0, str(args.bundle.resolve()))
    from check_linux import command
    result = dict(passed=False, manifest_sha256=sha(args.bundle/'manifest.json'),
                  programs=manifest['programs'], transfers=[], benchmarks=[],
                  fpga='G22r0 unchanged', kernel=RELEASE.decode(), fpga_writes=0, sd_writes=0, flash_writes=0)
    def interrupted(signum, frame):
        raise KeyboardInterrupt('Signal '+str(signum))
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGHUP, interrupted)
    with open('/tmp/prodock-diagnostic.lock', 'a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with serial.Serial(PORT, 115200, timeout=.1, exclusive=True) as uart:
            tx = Transport(uart, command, args.out)
            stopped = False
            current = None
            ever_started = False
            try:
                uart.write(b'\n'); time.sleep(.2); uart.read(16000)
                before = tx.run('before', 'uname -r; prodockctl display; cat /proc/mounts')
                assert re.search(rb'^'+RELEASE+rb'\r?$', before, re.M)
                assert b'tmpfs /tmp tmpfs ' in before and not re.search(rb'^/dev/mmc\S* ', before, re.M)
                result['before'] = display(before)
                assert process(tx, 'r2_initial', 'luma3d-r2')
                tags = [f'l3v2_{key}_{pose}' for pose in POSES for key in ('r2', 'r3')]
                tags += ['l3v2_endurance', 'l3v2_live', 'l3v2_restore']
                tx.run('fresh_launch_files', ' && '.join('test ! -f /tmp/'+tag+'.pid' for tag in tags))
                readback(tx, 'receiver_readback', '/tmp/luma-rx', 1464, RECEIVER_SHA)
                helper = manifest['helper']
                readback(tx, 'helper_readback', '/tmp/runtime-helper-r2', helper['bytes'], helper['sha256'])
                for key in ('r2', 'r3'):
                    program = manifest['programs'][key]
                    delta = program['delta']
                    result['transfers'].append(tx.transfer(args.bundle/delta['file'], delta['file']))
                    installed = tx.run('install_'+key,
                        f'/tmp/runtime-helper-r2 patch /tmp/{delta["file"]} /tmp/{program["name"]}'
                        f' {delta["patch_bytes"]} {delta["patch_crc32"]} /tmp/luma3d-r2', 60)
                    assert f'LUMA3D_UNPACK_OK bytes={program["bytes"]} crc32={program["crc32"]}'.encode() in installed
                    tx.run('mode_'+key, 'chmod 700 /tmp/'+program['name'])
                    for pose in POSES:
                        ref = program['references'][str(pose)]
                        result['transfers'].append(tx.transfer(args.bundle/ref['file'], ref['file']))
                        verified = tx.run(f'verify_{key}_{pose}',
                            f'/tmp/runtime-helper-r2 verify /tmp/{ref["file"]} unused 192000 {ref["crc32"]}')
                        assert f'LUMA3D_VERIFY_OK bytes=192000 crc32={ref["crc32"]}'.encode() in verified
                assert process(tx, 'r2_preserved_until_ready', 'luma3d-r2')
                print('BENCHMARK_READY_TO_SWITCH: installation verified; R2/R3 fixed-pose tests start', flush=True)
                # User requested an announcement before the recompiled version
                # is executed. This is a relay window, not an approval wait.
                time.sleep(10)
                stopped = True
                stop(tx, 'luma3d-r2', 'stop_live_r2')
                result['released'] = display(tx.run('released', 'prodockctl display'))
                for pose in POSES:
                    for key in ('r2', 'r3'):
                        program = manifest['programs'][key]
                        tag = f'l3v2_{key}_{pose}'
                        if key == 'r3' and pose == 0:
                            print('R3_READY_TO_RUN: first native R3 execution follows in 10 seconds', flush=True)
                            time.sleep(10)
                        current = (program['name'], '/tmp/'+tag+'.pid')
                        ever_started = True
                        initial = tx.run(tag+'_launch', supervisor(program['name'], tag, pose))
                        code = wait_exit(uart, args.out, tag, initial=initial)
                        log = tx.run(tag+'_log', 'cat /tmp/'+tag+'.log')
                        assert code == 0, (tag, code)
                        current = None
                        record = parse_benchmark(log, pose)
                        record.update(variant=key, pose=pose, display=display(tx.run(tag+'_display', 'prodockctl display')))
                        ref = program['references'][str(pose)]
                        pixels = tx.run(tag+'_pixels',
                            f'/tmp/runtime-helper-r2 pixels /tmp/{ref["file"]} page0 192000 {ref["crc32"]}', 60)
                        assert f'LUMA3D_PIXELS pixels=96000 mismatch=0 actual_crc={ref["crc32"]} expected_crc={ref["crc32"]}'.encode() in pixels
                        record['pixel_mismatches'] = 0
                        result['benchmarks'].append(record)
                        print(f'{tag}: pixels PASS, {record["result"]["fps"]} FPS / {record["measured"]["cycles"]} cycles', flush=True)
                program = manifest['programs']['r3']['name']
                current = (program, '/tmp/l3v2_endurance.pid')
                launch(tx, program, 'l3v2_endurance.log', 'endurance_launch', current[1])
                result['warm_display'] = progress(tx, program, 'l3v2_endurance.log', 'endurance_warm', current[1])
                begin = time.monotonic()
                print('R3 automatic endurance: 75 seconds without UART commands', flush=True)
                while time.monotonic()-begin < 75:
                    time.sleep(max(0, min(5, 75-(time.monotonic()-begin))))
                assert process(tx, 'endurance_alive_at_deadline', program, current[1])
                stop(tx, program, 'endurance_stop', current[1]); current = None
                log = tx.run('endurance_log', 'cat /tmp/l3v2_endurance.log')
                result['endurance'] = fields(log, 'LUMA3D_RESULT')
                assert result['endurance']['elapsed'] >= 75 and result['endurance']['frames'] > 1
                assert re.search(rb'^LUMA3D_PERF [^\r\n]*\bcollected=4/4\b', log, re.M)
                result['endurance']['four_letters_observed'] = True
                result['endurance_counters'] = game_counters(log)
                result['after_endurance'] = display(tx.run('after_endurance', 'prodockctl display'))
                current = (program, '/tmp/l3v2_live.pid')
                launch(tx, program, 'l3v2_live.log', 'live_launch', current[1])
                result['live_display'] = progress(tx, program, 'l3v2_live.log', 'live', current[1])
                tx.run('publish_live_pid', 'cp /tmp/l3v2_live.pid /tmp/luma3d-live.pid')
                result['passed'] = True
                result['left_running'] = 'R3 automatic 3D valley; exact original R2 executable preserved; no NEBULA'
            except BaseException as error:
                result['error'] = repr(error)
                if stopped:
                    try:
                        uart.write(b'\x03'); uart.flush(); time.sleep(.3); uart.read(16000)
                        if current:
                            stop(tx, current[0], 'stop_failed_candidate', current[1])
                        if not ever_started and process(tx, 'possible_old_r2', 'luma3d-r2'):
                            result['restored_display'] = progress(tx, 'luma3d-r2', 'luma3d-r2-live.log', 'old_r2')
                        else:
                            launch(tx, 'luma3d-r2', 'l3v2_restore.log', 'restore_r2', '/tmp/l3v2_restore.pid')
                            result['restored_display'] = progress(tx, 'luma3d-r2', 'l3v2_restore.log', 'restored_r2', '/tmp/l3v2_restore.pid')
                            tx.run('publish_restored_pid', 'cp /tmp/l3v2_restore.pid /tmp/luma3d-live.pid')
                        result['restored_r2'] = True
                    except BaseException as cleanup:
                        result['cleanup_error'] = repr(cleanup)
                raise
            finally:
                (args.out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
                print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
