#!/usr/bin/env python3
"""Reload exact R19 in SRAM after the user power cycle; read-only postcheck."""
import argparse
import fcntl
import json
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time

from board_trial_r19 import HERE, ROOT, DEST, BIT_SHA, BASE_GUARD, preflight, hw, sha

CHECK = BASE_GUARD + '''
proc word {address} {return [lindex [read_memory $address 32 1] 0]}
set gpu [read_memory 0xe9001000 32 26]
echo "GPU_FRESH $gpu"
if {[lindex $gpu 0]!=0x424c5432} {error "GPU signature differs"}
foreach index {1 2 3 7 9 13 19} {
    if {[lindex $gpu $index]!=0} {error "GPU is not fresh after reload"}
}
set ncp [read_memory 0xe9005080 32 7]
echo "NCP_FRESH $ncp"
if {[lindex $ncp 0]!=0x4e435031 || [lindex $ncp 2]!=0 || [lindex $ncp 3]!=0} {
    error "Observer is not fresh after reload"
}
set beat [word 0xe9005098]
set frame [word 0xe9000018]
sleep 200
set frame2 [word 0xe9000018]
if {$frame2==$frame || [word 0xe9005098]==$beat} {error "Video or GPU clock stopped"}
echo "FRAME_PROGRESS $frame $frame2"
echo R19_RELOADED_PARKED_BARS
shutdown
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    proof = preflight()
    identity = hw.usb_identity()
    if args.check_only:
        print(json.dumps(dict(ready=True, hardware=False, bitstream_sha256=BIT_SHA,
                             identity=identity, proof=proof)))
        return
    out = HERE / ('r19_user_powercycle_' + time.strftime('%Y%m%d_%H%M%S'))
    report = dict(board='neo', reason='Explicit user request after power cycle',
                  bitstream=str(DEST / 'impl/pnr/console_neo.fs'),
                  bitstream_sha256=BIT_SHA, static_proof=proof,
                  timing_qualification='FAIL', programming_attempted=False,
                  configured=False, postcheck_passed=False,
                  flash_written=False, SD_written=False, DDR_write_requested=False,
                  GPU_command_requested=False, Linux_started=False,
                  prior_runtime_state_invalidated_by_powercycle=True)

    def save():
        (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')

    def interrupt(sig, frame):
        raise KeyboardInterrupt('Signal ' + str(sig))

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, interrupt)
    with (ROOT / 'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        active = subprocess.run(['ps', '-C', 'openocd', '-C', 'openFPGALoader',
                                 '-C', 'gao_sh', '-C', 'gao_analyzer', '-C', 'jtagserver',
                                 '-o', 'pid=,comm='], capture_output=True, text=True)
        if active.returncode != 1 or active.stdout.strip():
            raise RuntimeError('Another hardware probe is active: ' + active.stdout)
        report['identity'] = hw.usb_identity()
        out.mkdir()
        shutil.copy2(__file__, out / 'controller.py')
        report['started_unix'] = time.time()
        save()
        board = hw.Hardware(out, report)
        try:
            report['programming_attempted'] = True
            save()
            board.program('program_r19', DEST / 'impl/pnr/console_neo.fs', BIT_SHA)
            report['configured'] = True
            save()
            print('R19_CONFIGURED ' + BIT_SHA, flush=True)
            log = board.observe('postcheck', CHECK)
            if 'R19_RELOADED_PARKED_BARS' not in log:
                raise RuntimeError('Missing postcheck marker')
            match = re.search(r'^FRAME_PROGRESS (0x[0-9a-fA-F]+|\d+) (0x[0-9a-fA-F]+|\d+)$', log, re.M)
            if not match:
                raise RuntimeError('Missing frame counter sample')
            report['frame_delta'] = (int(match[2], 0) - int(match[1], 0)) & 0xffffffff
            report['postcheck_passed'] = True
            report['hardware_state'] = ('Exact Neo R19 reloaded in SRAM; CPU halted in parking ROM; '
                'internal bars, framebuffer disabled, GPU idle, observer arm/sequence zero. '
                'No new GPU command. Previous native CLEAR stall remains a historical finding.')
            save()
            try:
                hw.run_child(['/usr/bin/ffmpeg', '-hide_banner', '-loglevel', 'warning',
                    '-f', 'v4l2', '-input_format', 'mjpeg', '-video_size', '1920x1080',
                    '-i', '/dev/video0', '-vf', 'select=gte(n\\,15)', '-frames:v', '1',
                    '-update', '1', '-n', str(out / 'camera.jpg')], out / 'camera.log', 15)
            except Exception as exc:
                report['camera_error'] = repr(exc)
        except BaseException as exc:
            report['error'] = repr(exc)
            raise
        finally:
            report['finished_unix'] = time.time()
            report['files'] = {p.name: sha(p) for p in out.iterdir()
                               if p.is_file() and p.name != 'result.json'}
            save()
            print(json.dumps(dict(output=str(out), configured=report['configured'],
                                  postcheck_passed=report['postcheck_passed'],
                                  error=report.get('error'))), flush=True)


if __name__ == '__main__':
    main()
