#!/usr/bin/env python3
"""Read a failed internal-mire candidate, then always restore the exact R19."""
import argparse
import fcntl
import json
from pathlib import Path
import signal
import subprocess
import time

import trial_coupled_startup as base

HERE, ROOT = base.HERE, base.ROOT
ANCHOR = HERE / 'startup_20261027_141038/result.json'
ANCHOR_SHA = '8275a0b6422ec09d0a0183f70462da2dc46414617fcb34f42f9093ab86ddf083'
OLD_REVIEW = HERE / 'root_startup_review_01.json'
OLD_REVIEW_SHA = '94b9794f392106983cd15046be00dbbac5631da7106d2b7132b2bf1b17fd8f54'
sha = base.prior.t.sha


def local_checks(path):
    review = json.loads(path.read_text())
    assert review['board'] == 'neo' and review['scope'] == 'read_failed_mire_then_restore'
    assert review['hardware_ready'] is True
    assert review['controller_sha256'] == sha(Path(__file__))
    assert sha(OLD_REVIEW) == OLD_REVIEW_SHA
    previous, bit = base.local_checks(OLD_REVIEW)
    assert review['bitstream_sha256'] == previous['bitstream_sha256']
    assert sha(ANCHOR) == ANCHOR_SHA
    anchor = json.loads(ANCHOR.read_text())
    assert anchor['left_startup_verified'] and anchor['last_programmed_sha256'] == base.prior.t.R19_SHA
    for name, h in anchor['files'].items():
        assert sha(ANCHOR.parent / name) == h, name
    required = base.dependency_files() + [Path(base.__file__), OLD_REVIEW, ANCHOR,
                                        HERE / 'coupled_video_readonly.tcl']
    assert all(str(p.resolve()) in review['proof_files'] for p in required)
    for name, h in review['proof_files'].items():
        assert sha(Path(name)) == h, name
    code = (HERE / 'coupled_video_readonly.tcl').read_text()
    assert 'VIDEO_READONLY_DONE' in code
    assert not any(s in code for s in ('write_memory', 'load_image', 'dump_image', 'resume',
                                      'reset halt', 'reset run', 'irscan', 'drscan'))
    return review, bit, code


def execute(io, report, save, bit, code):
    touched = False
    try:
        io.observe('r19_initial_guard', base.prior.check_code(0), 'WARM_CHECK_0')
        report['baseline_verified'] = True
        save()
        io.observe('r19_video_readonly', code, 'VIDEO_READONLY_DONE')
        io.camera('r19_before')
        touched = True
        io.program('program_coupled', bit, report['candidate_sha256'])
        io.camera('coupled_before_dmi')
        io.observe('video_readonly', code, 'VIDEO_READONLY_DONE')
        report['observations_completed'] = True
        save()
    except BaseException as exc:
        report['error'] = repr(exc)
        save()
        raise
    finally:
        if touched:
            report['restore_attempted'] = True
            save()
            for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
                signal.signal(sig, signal.SIG_IGN)
            try:
                io.program('restore_r19', base.prior.t.R19 / 'impl/pnr/console_neo.fs', base.prior.t.R19_SHA)
                io.observe('restored_guard', base.prior.check_code(0), 'WARM_CHECK_0')
                report.update(left_startup_verified=True, left_state='R19 restored, parked CPU, fresh GPU/NCP, internal bars')
                save()
                io.camera('r19_restored')
            except BaseException as exc:
                report['restore_error'] = repr(exc)
                save()
                raise


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--review', required=True, type=Path)
    ap.add_argument('--check-only', action='store_true')
    args = ap.parse_args()
    path = args.review.resolve()
    assert path.is_relative_to(HERE)
    review, bit, code = local_checks(path)
    if args.check_only:
        print(json.dumps(dict(ready=True, hardware_access=False)))
        return
    def interrupt(sig, frame):
        raise KeyboardInterrupt('Signal ' + str(sig))
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, interrupt)
    with (ROOT / 'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        active = subprocess.run(['ps', '-C', 'openocd', '-C', 'openFPGALoader', '-C', 'gao_sh',
                                 '-C', 'gao_analyzer', '-C', 'jtagserver', '-o', 'pid=,comm='],
                                capture_output=True, text=True, timeout=5)
        assert active.returncode == 1 and not active.stdout.strip(), 'Another debug tool is active'
        identity = base.prior.hw.usb_identity()
        assert identity['neo']['serial'] == '2025041420' and identity['neo']['path'].endswith('/3-4.4.1')
        assert identity['esp']['path'].endswith('/3-4.4.2')
        out = HERE / ('video_readonly_' + time.strftime('%Y%m%d_%H%M%S'))
        out.mkdir(exist_ok=False)
        (out / 'controller_used.py').write_bytes(Path(__file__).read_bytes())
        report = dict(board='neo', qualification_status='FAIL', hardware_review_sha256=sha(path),
                      anchor_sha256=ANCHOR_SHA, candidate_sha256=review['bitstream_sha256'],
                      last_programmed_sha256=base.prior.t.R19_SHA, left_startup_verified=False,
                      observations_completed=False, identity=identity, started_unix=time.time(),
                      UART_commands=False, DDR_written=False, GPU_commands=False, SD_written=False,
                      flash_written=False, Linux_loaded=False, CPU_resume_command=False,
                      CPU_ROM_restart_possible=True, dynamic_observer_used=False)
        def save():
            (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        save()
        try:
            execute(base.prior.IO(out, report, save), report, save, bit, code)
        finally:
            report['finished_unix'] = time.time()
            report['files'] = {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'result.json'}
            save()
            print(json.dumps(dict(output=str(out), **report)), flush=True)


if __name__ == '__main__':
    main()
