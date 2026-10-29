#!/usr/bin/env python3
"""Read-only health checks after the recorded, successful receiver/shell return.

The original recovery already sent its one-shot sequence. Never send it again.
Use ls for the executable symlink because this rootfs has no readlink command.
"""
import fcntl
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
import sys

BASE = Path('/home/michael/festival_20261028_r6_recovery_prepared_r1')
PRIOR = Path('/home/michael/festival_20261028_r6_recovery_board_r1')
OUT = Path('/home/michael/festival_20261028_r6_health_resume_r2')
sys.path.insert(0, str(BASE))
import recover as r

def checked_identity(raw):
    lines = re.findall(rb'^(3158) \(luma3d-gm1\) ([^\r\n]+)', raw, re.M)
    r.need(len(lines) == 1, 'Wrong GM1 process')
    fields = lines[0][1].split()
    r.need(len(fields) >= 20 and fields[0] not in (b'Z', b'X')
           and int(fields[19]) == r.ANCHOR['start_ticks'], 'GM1 state/start changed')
    r.need(r.octets(raw, 512) == b'/tmp/luma3d-gm1\0--showcase\0', 'GM1 argv changed')
    r.need(re.search(rb'^3158\r?$', raw, re.M), 'Published PID changed')
    links = re.findall(rb'^l[^\r\n]* /proc/3158/exe -> ([^\r\n]+)', raw, re.M)
    r.need(links == [b'/tmp/luma3d-gm1'], 'GM1 executable symlink changed')
    return r.ANCHOR.copy()

def inspect_available(recovery):
    q = r.Queries(recovery, r.os.urandom(8).hex())
    result = {'identity_before': checked_identity(q.run('identity_before', 'identity'))}
    system = q.run('system', 'system')
    r.need(re.search(rb'^'+r.KERNEL.encode()+rb'\r?$', system, re.M), 'Kernel changed')
    r.need(b'tmpfs /tmp tmpfs ' in system, 'Unexpected /tmp filesystem')
    result['kernel'] = r.KERNEL
    result['save_before'] = r.save(q.run('save_before', 'save'))
    first = r.gpu(q.run('gpu_before', 'gpu'))
    recovery.sleep(3)
    second = r.gpu(q.run('gpu_after', 'gpu'))
    delta = (second['presents']-first['presents']) & 0xffffffff
    r.need(0 < delta < 100000, 'No bounded GPU progression')
    result['gpu'] = {'before': first, 'after': second, 'presents_delta': delta}
    raw = q.run('space', 'space')
    rows = [x.split() for x in raw.replace(b'\r', b'').splitlines()
            if x.split() and x.split()[-1] == b'/tmp']
    r.need(len(rows) == 1 and len(rows[0]) == 6
           and all(x.isdigit() for x in rows[0][1:4]), 'Unexpected df')
    result['tmp_available_kib'] = int(rows[0][3])
    raw = q.run('partial', 'partial')
    rows = [x.split() for x in raw.replace(b'\r', b'').splitlines()
            if x.startswith(b'-') and x.split()[-1:] == [b'/tmp/festival-r9f.delta.lz4']]
    r.need(len(rows) == 1 and len(rows[0]) >= 8 and rows[0][4].isdigit(), 'Unexpected ls')
    result['failed_delta_bytes'] = int(rows[0][4])
    result['failed_delta_reusable'] = False
    result['identity_after'] = checked_identity(q.run('identity_after', 'identity'))
    result['save_after'] = r.save(q.run('save_after', 'save'))
    return result

def main():
    r.need(socket.gethostname() == r.HOST, 'Wrong host')
    r.preflight(BASE, 'd8a504a17ab2c07fd6729c02584b3f197f8b35830b5d6fed057c9da1c3366588')
    prior = json.loads((PRIOR / 'result.json').read_text())
    r.need(prior['state'] == 'shell_confirmed' and prior['recovery']['receiver_return_confirmed']
           and prior['recovery']['shell_confirmed'] and prior['recovery']['receiver_exit'] == 1,
           'Shell return not independently recorded')
    r.need(prior['error'] == "Refused('Query failed or duplicate return')", 'Unexpected failure')
    r.need(b'sh: readlink: not found' in (PRIOR / 'identity_before.log').read_bytes(),
           'Missing command diagnosis not reproduced')
    r.QUERIES['identity'] = ('cat /tmp/luma3d-live.pid && cat /proc/3158/stat && '
                            'od -b -v /proc/3158/cmdline && ls -l /proc/3158/exe')
    r.identity = checked_identity
    r.QUERIES['partial'] = 'ls -ln /tmp/festival-r9f.delta.lz4'
    OUT.mkdir(exist_ok=False)
    result = dict(passed=False, hardware=True, recovery_bytes_sent=0,
                  stop_gm1=False, relaunch_gm1=False, fpga_writes=0, sd_writes=0,
                  save_writes=0, failed_delta_reusable=False,
                  prior_sha256=hashlib.sha256((PRIOR / 'result.json').read_bytes()).hexdigest())
    try:
        with open(r.LOCK, 'a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            owner = subprocess.run(['fuser', r.PORT], capture_output=True)
            r.need(owner.returncode == 1 and not owner.stdout.strip()
                   and not owner.stderr.strip(), 'Port busy')
            uart = r.UART(r.PORT)
            try:
                recovery = r.Recovery(uart, OUT)
                recovery.state = 'shell_confirmed'
                result['preservation'] = inspect_available(recovery)
                result['passed'] = True
            finally:
                uart.close()
    except BaseException as error:
        result['error'] = repr(error)
    finally:
        (OUT / 'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result), flush=True)
    return 0 if result['passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
