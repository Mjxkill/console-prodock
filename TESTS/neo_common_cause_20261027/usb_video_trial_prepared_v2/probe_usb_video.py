#!/usr/bin/env python3
"""Compare fresh UTNA and video observations, then always restore exact R19."""
import argparse
import fcntl
import json
from pathlib import Path
import signal
import sys
import re
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE_DIR = ROOT / "TESTS/neo_720p_20261012/capture_memory_20261027/reset_contract_01"
sys.path.insert(0, str(BASE_DIR))
import trial_coupled_startup as base
ANCHOR = BASE_DIR / 'video_readonly_20261027_155600/result.json'
ANCHOR_SHA = '2070bbc5a7cf608fef652c6c8e714b062286c559d290f51009eb9f5399265995'
OLD_REVIEW = BASE_DIR / 'root_startup_review_01.json'
OLD_REVIEW_SHA = '94b9794f392106983cd15046be00dbbac5631da7106d2b7132b2bf1b17fd8f54'
sha = base.prior.t.sha


class StopRequest:
    """Signals request a stop; only explicit non-cleanup checkpoints raise."""
    def __init__(self):
        self.received = []

    def handler(self, number, frame):
        self.received.append(number)

    def install(self):
        for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(number, self.handler)

    def checkpoint(self):
        if self.received:
            raise KeyboardInterrupt('Signal ' + str(self.received[0]))


def required_files():
    return sorted(set(base.dependency_files() + [Path(__file__), Path(base.__file__),
        OLD_REVIEW, ANCHOR, HERE/'video_prefix.tcl', HERE/'utna_protocol.tcl',
        HERE/'usb_video.tcl', HERE/'offline_result.json', HERE/'test_protocol.py',
        HERE/'test_controller.py', HERE/'test_signals.py', HERE/'signal_tests_result.json',
        BASE_DIR/'candidate_02/usb_clock_constraints_01/protocol_result.json']))


def local_checks(path, require_ready=True):
    review = json.loads(path.read_text())
    assert review['board']=='neo' and review['scope']=='fresh_utna_video_then_restore'
    assert review['qualification_status']=='FAIL'
    if require_ready:
        assert review['hardware_ready'] is True, 'Root review has not authorized hardware'
    assert review['controller_sha256']==sha(Path(__file__))
    assert sha(OLD_REVIEW)==OLD_REVIEW_SHA
    # Validate the immutable earlier evidence directly. Calling base.local_checks
    # would add this new controller to that OLD review's dynamic import inventory.
    # The new review binds the current complete dependencies instead, below.
    previous=json.loads(OLD_REVIEW.read_text())
    assert previous['board']=='neo' and previous['scope']=='parked_startup_only'
    assert previous['hardware_ready'] is True
    assert previous['controller_sha256']==sha(Path(base.__file__))
    assert previous['netlist_sha256']==base.NET
    assert previous['parent_r19_sha256']==base.prior.t.R19_SHA
    assert Path(previous['build']).resolve()==base.BUILD
    assert sha(base.BUILD/'console_neo.vg')==base.NET
    bit=base.BUILD/'impl/pnr/console_neo.fs'
    assert sha(bit)==previous['bitstream_sha256']==review['bitstream_sha256']
    assert sha(base.prior.t.R19/'impl/pnr/console_neo.fs')==base.prior.t.R19_SHA
    for name, h in previous['proof_files'].items():
        assert sha(Path(name))==h, name
    assert sha(ANCHOR)==ANCHOR_SHA
    anchor=json.loads(ANCHOR.read_text())
    assert anchor['left_startup_verified'] and anchor['last_programmed_sha256']==base.prior.t.R19_SHA
    for name,h in anchor['files'].items():
        assert sha(ANCHOR.parent/name)==h, name
    assert all(str(p.resolve()) in review['proof_files'] for p in required_files())
    for name,h in review['proof_files'].items():
        assert sha(Path(name))==h, name
    assert json.loads((HERE/'offline_result.json').read_text())['passed'] is True
    code=(HERE/'usb_video.tcl').read_text()
    assert code==(HERE/'video_prefix.tcl').read_text()+'\n'+(HERE/'utna_protocol.tcl').read_text()
    assert 'USB_VIDEO_DONE' in code
    assert re.findall(r'write_memory\s+(0x[0-9a-f]+)',code)==['0xe900200c']
    assert not any(x in code for x in ('load_image','dump_image','resume','reset halt',
        'reset run','irscan','drscan','mww ','mwh ','mwb '))
    return review,bit,code


def restoration_guard():
    return base.prior.check_code(0)+"""
set u [read_memory 0xe9002000 32 3]
echo \"RESTORED_UTNA $u\"
if {[lindex $u 0]!=0x55544e41 || [lindex $u 1]!=0 || [lindex $u 2]!=0} {error \"Restored UTNA not fresh\"}
echo RESTORED_UTNA_FRESH
"""


def execute(io, report, save, bit, code, stop=None):
    stop = stop if stop is not None else StopRequest()
    report['signals_received'] = stop.received
    touched = False
    try:
        stop.checkpoint()
        io.observe('r19_initial_guard', base.prior.check_code(0), 'WARM_CHECK_0')
        stop.checkpoint()
        report['baseline_verified'] = True
        save()
        stop.checkpoint()
        io.camera('r19_before')
        stop.checkpoint()
        # Even a failed baseline UTNA capture may have armed the observer.
        # Restore R19 after that mutation as well, without blind extra commands.
        touched = True
        stop.checkpoint()
        io.observe('r19_usb_video', code, 'USB_VIDEO_DONE')
        stop.checkpoint()
        report['baseline_protocol_completed'] = True
        save()
        stop.checkpoint()
        io.program('program_coupled', bit, report['candidate_sha256'])
        stop.checkpoint()
        io.camera('coupled_before_dmi')
        stop.checkpoint()
        io.observe('coupled_usb_video', code, 'USB_VIDEO_DONE')
        stop.checkpoint()
        io.camera('coupled_after_observation')
        stop.checkpoint()
        report['observations_completed'] = True
        save()
        stop.checkpoint()
    except BaseException as exc:
        report['error'] = repr(exc)
        try:
            save()
        except BaseException as log_error:
            report.setdefault('error_log_errors', []).append(repr(log_error))
        raise
    finally:
        if touched:
            # The installed handlers never raise, including at this boundary.
            # Keep recording signals throughout rollback; do not clear or
            # convert them to exceptions until the rollback has completed.
            def cleanup_save():
                try:
                    save()
                except BaseException as exc:
                    report.setdefault('cleanup_log_errors', []).append(repr(exc))
            # IO.program saves before touching JTAG; a metadata save failure
            # must not prevent even the attempt to restore the reference.
            if hasattr(io, 'save'):
                io.save = cleanup_save
            report['restore_attempted'] = True
            cleanup_save()
            try:
                io.program('restore_r19', base.prior.t.R19 / 'impl/pnr/console_neo.fs', base.prior.t.R19_SHA)
                io.observe('restored_guard', restoration_guard(), 'RESTORED_UTNA_FRESH')
                report.update(left_startup_verified=True, left_state='R19 restored, parked CPU, fresh GPU/NCP, internal bars')
                cleanup_save()
                io.camera('r19_restored')
            except BaseException as exc:
                report['restore_error'] = repr(exc)
                cleanup_save()
                raise
    # A signal first received during cleanup is still an interrupted trial.
    # This checkpoint cannot bypass or interrupt the restoration above.
    stop.checkpoint()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--review', required=True, type=Path)
    ap.add_argument('--check-only', action='store_true')
    args = ap.parse_args()
    path = args.review.resolve()
    assert path.is_relative_to(HERE)
    review, bit, code = local_checks(path, require_ready=not args.check_only)
    if args.check_only:
        print(json.dumps(dict(preflight_passed=True, hardware_ready=review['hardware_ready'], hardware_access=False)))
        return
    stop = StopRequest()
    stop.install()
    stop.checkpoint()
    with (ROOT / 'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        active = subprocess.run(['ps', '-C', 'openocd', '-C', 'openFPGALoader', '-C', 'gao_sh',
                                 '-C', 'gao_analyzer', '-C', 'jtagserver', '-o', 'pid=,comm='],
                                capture_output=True, text=True, timeout=5)
        assert active.returncode == 1 and not active.stdout.strip(), 'Another debug tool is active'
        stop.checkpoint()
        identity = base.prior.hw.usb_identity()
        assert identity['neo']['serial'] == '2025041420' and identity['neo']['path'].endswith('/3-4.4.1')
        assert identity['esp']['path'].endswith('/3-4.4.2')
        stop.checkpoint()
        out = HERE / ('usb_video_' + time.strftime('%Y%m%d_%H%M%S'))
        out.mkdir(exist_ok=False)
        (out / 'controller_used.py').write_bytes(Path(__file__).read_bytes())
        report = dict(board='neo', qualification_status='FAIL', hardware_review_sha256=sha(path),
                      anchor_sha256=ANCHOR_SHA, candidate_sha256=review['bitstream_sha256'],
                      last_programmed_sha256=base.prior.t.R19_SHA, left_startup_verified=False,
                      observations_completed=False, baseline_protocol_completed=False, identity=identity, started_unix=time.time(),
                      observer_commands=[1,6,2,2], observer_write_address=0xe900200c,
                      observer_mutation=True, power_cycle=False,
                      UART_commands=False, DDR_written=False, GPU_commands=False, SD_written=False,
                      flash_written=False, Linux_loaded=False, CPU_resume_command=False,
                      CPU_ROM_restart_possible=True, dynamic_observer_used=False)
        def save():
            (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        save()
        try:
            execute(base.prior.IO(out, report, save), report, save, bit, code, stop)
        finally:
            report['finished_unix'] = time.time()
            report['files'] = {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'result.json'}
            save()
            print(json.dumps(dict(output=str(out), **report)), flush=True)


if __name__ == '__main__':
    main()
