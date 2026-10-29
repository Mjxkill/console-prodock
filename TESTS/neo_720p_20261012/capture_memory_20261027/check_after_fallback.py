#!/usr/bin/env python3
"""One bounded read-only check after the recorded R19 fallback; no programming."""
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import time
from board_trial_r21 import HERE, ROOT, BASE_GUARD, R19_SHA, hw


def main():
    prior = HERE/'board_trial_20261027_085157/result.json'
    previous = json.loads(prior.read_text())
    assert previous['fallback_r19_status']['done']
    assert previous['finished_unix'] and not previous['cases']
    report = dict(board='neo', programming=False, CPU_resumed=False,
                  DDR_written=False, SD_written=False, flash_written=False,
                  last_programmed_sha256=R19_SHA, startup_verified=False,
                  prior_sha256=hashlib.sha256(prior.read_bytes()).hexdigest())
    out = HERE/('fallback_check_'+time.strftime('%Y%m%d_%H%M%S'))
    with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
        active = subprocess.run(['ps','-C','openocd','-C','openFPGALoader','-C','gao_sh',
            '-C','gao_analyzer','-C','jtagserver','-o','pid=,comm='], capture_output=True, text=True)
        assert active.returncode == 1 and not active.stdout.strip()
        identity = hw.usb_identity()
        assert identity['neo']['serial'] == '2025041420'
        assert identity['neo']['path'].endswith('/3-4.4.1')
        assert identity['esp']['path'].endswith('/3-4.4.2')
        report['identity'] = identity
        out.mkdir()
        try:
            text = hw.Hardware(out, report).observe('read100k', BASE_GUARD+'''
echo "GPU [read_memory 0xe9001000 32 26]"
echo "NCP [read_memory 0xe9005080 32 7]"
echo FALLBACK_READ_OK
shutdown
''')
            report['startup_verified'] = 'FALLBACK_READ_OK' in text
        except Exception as exc:
            report['error'] = repr(exc)
        report['files'] = {p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in out.iterdir() if p.is_file()}
        (out/'result.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps({'output':str(out), **report}), flush=True)


if __name__ == '__main__':
    main()
