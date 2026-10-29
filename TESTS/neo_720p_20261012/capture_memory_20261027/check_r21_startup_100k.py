#!/usr/bin/env python3
"""Same R21r1 SRAM image, bounded 100 kHz JTAG check and pre-DMI camera."""
import argparse
import fcntl
import json
from pathlib import Path
import signal
import subprocess
import time
import board_trial_r21 as trial

HERE, ROOT, hw = trial.HERE, trial.ROOT, trial.hw
ANCHOR = HERE/'fallback_check_20261027_085512/result.json'
REVIEW = HERE/'root_route_review_01.json'
FRESH = '''
foreach {addr expected} {
    0xe9005080 0x4e435031 0xe9005088 0 0xe900508c 0
    0xe9001004 0 0xe9001008 0 0xe9001034 0
} {
    if {[lindex [read_memory $addr 32 1] 0]!=$expected} {error "Fresh parked state changed"}
}
echo STARTUP_READ_OK
shutdown
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    review, bit = trial.route_review(REVIEW)
    anchor = json.loads(ANCHOR.read_text())
    assert anchor['startup_verified'] and not anchor['programming']
    assert anchor['last_programmed_sha256'] == trial.R19_SHA
    for name, digest in anchor['files'].items():
        assert trial.sha(ANCHOR.parent/name) == digest
    assert trial.sha(trial.R19/'impl/pnr/console_neo.fs') == trial.R19_SHA
    if args.check_only:
        print(json.dumps(dict(ready=True, hardware=False, bitstream_sha256=review['bitstream_sha256'])))
        return
    out = HERE/('startup_100k_'+time.strftime('%Y%m%d_%H%M%S'))
    report = dict(board='neo', candidate=True, qualification_status='FAIL',
                  jtag_khz=100, CPU_resumed=False, DDR_written=False,
                  SD_written=False, flash_written=False, r21_startup_verified=False,
                  route_review_sha256=trial.sha(REVIEW), anchor_sha256=trial.sha(ANCHOR),
                  candidate_sha256=review['bitstream_sha256'])
    def save():
        (out/'result.json').write_text(json.dumps(report, indent=2)+'\n')
    def observe(name):
        text = hw.Hardware(out, report).observe(name, trial.BASE_GUARD+FRESH)
        assert 'STARTUP_READ_OK' in text
    def program(name, path, digest):
        hw.Hardware(out, report).program(name, path, digest)
        # A successful configuration is not a verified CPU/display startup.
        report['last_programmed_sha256'] = digest
        report['left_startup_verified'] = False
        save()
    def camera(name):
        try:
            hw.run_child(['/usr/bin/ffmpeg','-hide_banner','-loglevel','warning',
                '-f','v4l2','-input_format','mjpeg','-video_size','1920x1080',
                '-i','/dev/video0','-vf','select=gte(n\\,15)','-frames:v','1',
                '-update','1','-n',str(out/(name+'.jpg'))],out/(name+'.log'),15)
        except Exception as exc:
            report[name+'_error'] = repr(exc)
        save()
    def interrupt(sig, frame):
        raise KeyboardInterrupt('Signal '+str(sig))
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, interrupt)
    with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
        active = subprocess.run(['ps','-C','openocd','-C','openFPGALoader','-C','gao_sh',
            '-C','gao_analyzer','-C','jtagserver','-o','pid=,comm='],capture_output=True,text=True)
        assert active.returncode == 1 and not active.stdout.strip()
        identity = hw.usb_identity()
        assert identity['neo']['serial']=='2025041420'
        assert identity['neo']['path'].endswith('/3-4.4.1')
        assert identity['esp']['path'].endswith('/3-4.4.2')
        out.mkdir()
        (out/'controller_used.py').write_bytes(Path(__file__).read_bytes())
        report['controller_sha256'] = trial.sha(out/'controller_used.py')
        report.update(identity=identity, started_unix=time.time())
        save()
        touched = False
        try:
            observe('baseline_r19')
            touched = True
            program('program_r21', bit, review['bitstream_sha256'])
            camera('r21_before_dmi')
            observe('r21_read100k')
            report.update(r21_startup_verified=True, left_startup_verified=True,
                          left_state='R21r1 CPU halted; internal bars selected; no GPU commands submitted')
        except BaseException as exc:
            report['error'] = repr(exc)
            save()
            if touched:
                for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):
                    signal.signal(sig,signal.SIG_IGN)
                try:
                    program('fallback_r19', trial.R19/'impl/pnr/console_neo.fs', trial.R19_SHA)
                    observe('fallback_read100k')
                    report.update(left_startup_verified=True,
                                  left_state='R19 CPU halted; fresh GPU state; internal bars selected')
                    camera('r19_after_restore')
                except BaseException as fallback:
                    report['fallback_error'] = repr(fallback)
        finally:
            report['finished_unix'] = time.time()
            report['files'] = {p.name:trial.sha(p) for p in out.iterdir()
                               if p.is_file() and p.name!='result.json'}
            save()
            print(json.dumps({'output':str(out), **report}), flush=True)


if __name__ == '__main__':
    main()
