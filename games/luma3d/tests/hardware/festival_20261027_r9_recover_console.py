#!/usr/bin/env python3
"""Recover the idle shell after the failed R9 transfer; never stop/restart GM1."""
import argparse
import fcntl
import json
from pathlib import Path
import socket
import sys
import time


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if socket.gethostname() != 'michael-AX15':
        raise RuntimeError('Pro Dock is on michael-AX15 only')
    sys.path.insert(0, str(a.bundle.resolve()))
    import festival_trial as trial
    m = trial.preflight(a.bundle, 'b72932159cf1f27f199be1bacc0a225aff0414ca9f8e09b2ca5f9910baa816d1')
    mods = trial.dependencies(a.bundle, m)
    import serial
    a.out.mkdir(parents=True, exist_ok=False)
    result = {'passed': False, 'board': 'prodock', 'game_stop_commands': 0,
              'game_start_commands': 0, 'fpga_writes': 0, 'file_writes_on_board': 0}
    try:
        with open(trial.LOCK, 'a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with serial.Serial(trial.PORT, 115200, timeout=.1, exclusive=True) as uart:
                # Cancel a partial shell line. Do not send another binary packet.
                received = bytearray()
                for _ in range(3):
                    uart.write(b'\x03\x15\n')
                    uart.flush()
                    until = time.monotonic() + 1
                    while time.monotonic() < until:
                        received.extend(uart.read(4096))
                (a.out / 'resync.log').write_bytes(received)
                tx = mods['prodock_transport'].Transport(uart, mods['check_linux'].command, a.out)
                raw = tx.run('shell', 'echo FESTIVAL_SHELL_RECOVERED', 20)
                trial.require(b'\nFESTIVAL_SHELL_RECOVERED\r\n' in raw, 'Shell marker missing')
                identity = mods['trial_guards'].identity(tx, 'gm1')
                trial.require(identity == trial.ANCHOR, 'GM1 anchor changed')
                first = mods['prodock_valley_trial'].display(tx.run('display_before', 'prodockctl display'))
                time.sleep(3)
                second = mods['prodock_valley_trial'].display(tx.run('display_after', 'prodockctl display'))
                trial.require((second['presents'] - first['presents']) & 0xffffffff, 'GM1 not presenting')
                saved = mods['prodock_arcade'].saved_bytes(tx, 'saved_game', mods['trial_guards'].BASE_SAVE, 4)
                trial.require(saved['sha256'] == trial.SAVE_SHA, 'Save changed')
                result.update(passed=True, identity=identity, display_before=first,
                              display_after=second, save={'bytes': saved['bytes'], 'sha256': saved['sha256']})
    except BaseException as error:
        result['error'] = repr(error)
        if hasattr(error, 'data'):
            (a.out / 'timeout.log').write_bytes(error.data)
    finally:
        (a.out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
