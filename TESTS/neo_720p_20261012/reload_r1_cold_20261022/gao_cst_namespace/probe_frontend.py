#!/usr/bin/env python3
"""Bounded gw_sh configuration introspection; never invokes a build or hardware."""
from pathlib import Path
import hashlib
import json
import os
import signal
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from gowin_toolchain import IDE, environment


def main():
    script = HERE / 'probe_frontend.tcl'
    assert 'run pnr' not in script.read_text() and 'run syn' not in script.read_text()
    out = HERE / 'frontend_result'
    out.mkdir(exist_ok=False)
    command = [str(IDE / 'bin/gw_sh'), str(script)]
    record = {'command': command, 'hardware_access': False, 'build_requested': False,
              'tcl_sha256': hashlib.sha256(script.read_bytes()).hexdigest()}
    with (out / 'frontend.log').open('x') as log:
        child = subprocess.Popen(command, cwd=out, env=environment(), stdout=log,
                                 stderr=log, start_new_session=True)
        try:
            record['returncode'] = child.wait(timeout=45)
        except BaseException:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
            raise
    (out / 'invocation.json').write_text(json.dumps(record, indent=2) + '\n')
    print((out / 'frontend.log').read_text())
    return record['returncode']


if __name__ == '__main__':
    raise SystemExit(main())
