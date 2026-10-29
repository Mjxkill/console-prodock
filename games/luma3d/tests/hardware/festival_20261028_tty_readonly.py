#!/usr/bin/env python3
"""Read Pro Dock tty flags and health only, under the established board lock."""
import fcntl,json,socket,sys
from pathlib import Path
import serial

BUNDLE=Path('/home/michael/festival_20261027_r9_prepared_r3')
OUT=Path('/home/michael/festival_20261028_tty_readonly_r1')

def main():
    if socket.gethostname()!='michael-AX15':raise RuntimeError('Wrong host')
    sys.path.insert(0,str(BUNDLE))
    import festival_trial as trial
    manifest=trial.preflight(BUNDLE,'f5811b4ec4313dc859e4429551b3673885b51d7a0fc1f1d32623930fd9f7c56e')
    mods=trial.dependencies(BUNDLE,manifest)
    OUT.mkdir(exist_ok=False)
    result=dict(passed=False,board='prodock',writes_to_files_or_mmio=False,game_signals_sent=False)
    try:
        with open(trial.LOCK,'a+') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with serial.Serial(trial.PORT,115200,timeout=.1,exclusive=True) as uart:
                tx=mods['prodock_transport'].Transport(uart,mods['check_linux'].command,OUT)
                raw=tx.run('tty','echo TTY_DIAG_BEGIN; cat /proc/$$/fdinfo/0 /proc/$$/fdinfo/1; stty -a; echo TTY_DIAG_END',30)
                trial.require(b'\nTTY_DIAG_BEGIN\r\n' in raw and b'\nTTY_DIAG_END\r\n' in raw,'Incomplete diagnostics')
                identity=mods['trial_guards'].identity(tx,'gm1')
                trial.require(identity==trial.ANCHOR,'GM1 changed')
                state=mods['prodock_valley_trial'].display(tx.run('display','prodockctl display'))
                tx.run('receiver_file','ls -l /tmp/f9c-helper /tmp/luma-rx; cat /proc/tty/driver/serial',30)
                result.update(passed=True,identity=identity,display=state)
    except BaseException as error:
        result['error']=repr(error)
        if hasattr(error,'data'):(OUT/'timeout.log').write_bytes(error.data)
    finally:(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
