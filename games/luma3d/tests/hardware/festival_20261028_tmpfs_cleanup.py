#!/usr/bin/env python3
"""Remove four obsolete RAM test binaries whose exact local copies are retained."""
import fcntl,hashlib,json,re,socket,sys,time
from pathlib import Path
import serial

BUNDLE=Path('/home/michael/festival_20261027_r9_prepared_r3')
OUT=Path('/home/michael/festival_20261028_tmpfs_cleanup_r1')
META=Path('/home/michael/festival_20261028_tmpfs_cleanup.json')
NAMES=['mc1-baseline','mc1-candidate','mo1-baseline','mo1-candidate']

def main():
    if socket.gethostname()!='michael-AX15':raise RuntimeError('Wrong host')
    if hashlib.sha256(META.read_bytes()).hexdigest()!='6213e6d3391ea93b549150aa4bcbd81295cdbbab57f5100e3ea3ddc862f09e93':raise RuntimeError('Cleanup manifest changed')
    plan=json.loads(META.read_text())
    if [x['name'] for x in plan['files']]!=NAMES:raise RuntimeError('Unexpected file')
    sys.path.insert(0,str(BUNDLE))
    import festival_trial as trial
    m=trial.preflight(BUNDLE,'f5811b4ec4313dc859e4429551b3673885b51d7a0fc1f1d32623930fd9f7c56e')
    mods=trial.dependencies(BUNDLE,m)
    OUT.mkdir(exist_ok=False)
    result=dict(passed=False,board='prodock',deleted=[],fpga_writes=0,save_writes=0,game_signals_sent=False)
    try:
        with open(trial.LOCK,'a+') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with serial.Serial(trial.PORT,115200,timeout=.1,exclusive=True) as uart:
                tx=mods['prodock_transport'].Transport(uart,mods['check_linux'].command,OUT)
                trial.require(mods['trial_guards'].identity(tx,'before')==trial.ANCHOR,'GM1 changed')
                saved=mods['prodock_arcade'].saved_bytes(tx,'save_before',mods['trial_guards'].BASE_SAVE,4)
                trial.require(saved['sha256']==trial.SAVE_SHA,'Save changed')
                helper=plan['helper']
                mods['prodock_valley_benchmark'].readback(tx,'helper_readback','/tmp/'+helper['name'],helper['bytes'],helper['sha256'])
                tx.run('space_before','df /tmp')
                for item in plan['files']:
                    mods['prodock_arcade'].raw_verify(tx,helper['name'],'verify_'+item['name'],'/tmp/'+item['name'],item['binary'])
                trial.require(mods['trial_guards'].identity(tx,'before_remove')==trial.ANCHOR,'GM1 changed')
                # Check each exact process name again in the same shell command
                # immediately preceding removal. No wildcard is passed to rm.
                guard='for p in /proc/[0-9]*/comm; do n=`cat "$p"`; case "$n" in mc1-baseline|mc1-candidate|mo1-baseline|mo1-candidate) echo OBSOLETE_PROBE_ACTIVE; exit 1;; esac; done'
                command='( '+guard+'; rm /tmp/mc1-baseline /tmp/mc1-candidate /tmp/mo1-baseline /tmp/mo1-candidate ) && echo FOUR_OBSOLETE_PROBES_REMOVED'
                raw=tx.run('remove_verified_obsolete',command,30)
                trial.require(re.search(rb'^FOUR_OBSOLETE_PROBES_REMOVED\r?\n',raw,re.M),'Removal unconfirmed')
                result['deleted']=NAMES[:]
                raw=tx.run('space_after','df /tmp')
                rows=re.findall(rb'^tmpfs\s+(\d+)\s+(\d+)\s+(\d+)\s+\d+%\s+/tmp\r?$',raw,re.M)
                trial.require(len(rows)==1 and int(rows[0][2])>=32768,'Insufficient reclaimed space')
                result['available_kib']=int(rows[0][2])
                trial.require(mods['trial_guards'].identity(tx,'after')==trial.ANCHOR,'GM1 changed')
                saved=mods['prodock_arcade'].saved_bytes(tx,'save_after',mods['trial_guards'].BASE_SAVE,4)
                trial.require(saved['sha256']==trial.SAVE_SHA,'Save changed')
                result['save_sha256']=saved['sha256']
                first=mods['prodock_valley_trial'].display(tx.run('display_before','prodockctl display'))
                time.sleep(3)
                second=mods['prodock_valley_trial'].display(tx.run('display_after','prodockctl display'))
                trial.require((second['presents']-first['presents'])&0xffffffff,'GM1 not presenting')
                result.update(passed=True,identity=trial.ANCHOR,display_before=first,display_after=second)
    except BaseException as error:
        result['error']=repr(error)
        if hasattr(error,'data'):(OUT/'timeout.log').write_bytes(error.data)
    finally:(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
