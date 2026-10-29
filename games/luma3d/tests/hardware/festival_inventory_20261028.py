#!/usr/bin/env python3
"""Read current Pro Dock software and tmpfs inventory under the UART lock.

Uses the frozen, previously exercised transport. Does not stop the game,
remove files, transfer a payload or change FPGA/kernel/SD.
"""
import fcntl
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

FROZEN = Path('/tmp/festival_persistent_20261028_prepared_r1')
PORT = '/dev/serial/by-id/usb-Electrosens_MegaPro_Console_11252024-if00'
OUT = Path('/tmp/festival_inventory_20261028_board_r1')


def main():
    assert socket.gethostname().split('.')[0] == 'michael-AX15'
    assert not OUT.exists()
    sys.path.insert(0, str(FROZEN))
    import probe_channel as transport
    import policy
    OUT.mkdir()
    result = dict(passed=False, read_only=True, game_stopped=False)
    descriptor = os.open('/tmp/prodock-diagnostic.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        owner = subprocess.run(['fuser', PORT], capture_output=True)
        assert owner.returncode == 1 and not owner.stdout.strip() and not owner.stderr.strip()
        uart = transport.UART(PORT)
        channel = transport.Channel(uart, OUT)
        try:
            channel.initial_shell()
            raw = channel.run('identity', 'cat /tmp/fm4live1.pid && cat /proc/3940/stat && od -b -v /proc/3940/cmdline && ls -l /proc/3940/exe')
            result['identity'] = policy.parse_identity(raw, 'luma3d-fm4a', ['--festival', '--festival-save', '/tmp/fm4live1.festival.save', '--memory-save', '/tmp/fm4live1.memory.save'])
            assert result['identity'] == dict(pid=3940, start_ticks=35705238)
            channel.run('inventory', 'uname -r && LC_ALL=C df -Pk /tmp && ls -l /tmp && ps')
            channel.run('executables', 'ls -l /proc/[0-9]*/exe')
            result['display'] = transport.gpu(channel.run('display', 'prodockctl display'))
            result['passed'] = True
        except Exception as error:
            result['error'] = repr(error)
        finally:
            channel.close()
            uart.close()
    (OUT / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
