#!/usr/bin/env python3
"""Stop only the identified R17 compiler, explicitly requested by the user."""
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BUILD = ROOT/'tang/impl/console_neo_n56r17_gao_opcode'
PID = 2794912
LAUNCH_SHA = '268ff046be021a3369267eb550da5c17945477369d71629d0d40bd9fd9276c8c'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    launch = BUILD/'route_launch.json'
    assert sha(launch) == LAUNCH_SHA
    record = json.loads(launch.read_text())
    assert record['pid'] == PID and record['candidate'] == str(BUILD)
    proc = Path('/proc')/str(PID)
    fd = os.pidfd_open(PID)
    result = dict(request='User: stop R17 and propose another approach',
                  started_unix=time.time(), pid=PID, launch_sha256=LAUNCH_SHA,
                  signals=[], stopped=False, hardware_access=False,
                  other_compilers_touched=False)
    try:
        assert (proc/'cwd').resolve(strict=True) == BUILD.resolve(strict=True)
        assert (proc/'cmdline').read_bytes().rstrip(b'\0').split(b'\0') == [os.fsencode(record['tool']), b'build.tcl']
        assert sha(proc/'exe') == record['tool_sha256']
        stat = (proc/'stat').read_text().rsplit(')', 1)[1].split()
        assert int(stat[19]) == 43756901, 'PID was reused'
        result['start_ticks'] = int(stat[19])
        poll = select.poll()
        poll.register(fd, select.POLLIN)
        assert not poll.poll(0), 'Process already exited'
        out = HERE/'r17_cancelled_by_user_01'
        out.mkdir(exist_ok=False)
        (out/'controller.py').write_text(Path(__file__).read_text())
        for sig, timeout in ((signal.SIGTERM, 12000), (signal.SIGKILL, 5000)):
            signal.pidfd_send_signal(fd, sig)
            result['signals'].append(sig.name)
            if poll.poll(timeout):
                result['stopped'] = True
                break
        result['finished_unix'] = time.time()
        result['available_final_outputs'] = [str(p.relative_to(BUILD))
            for ext in ('*.fs', '*.tr', '*.sdf') for p in (BUILD/'impl/pnr').glob(ext)]
        (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result), flush=True)
        assert result['stopped'], 'Compiler has not exited'
    finally:
        os.close(fd)


if __name__ == '__main__':
    main()
