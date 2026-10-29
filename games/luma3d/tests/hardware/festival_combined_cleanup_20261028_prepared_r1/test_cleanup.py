"""Local allowlist/order/refusal tests; no remote or local deletion is run."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import types

import cleanup as c


def rejects(function,*args):
    try:function(*args)
    except (ValueError,RuntimeError):return
    raise AssertionError('Unsafe request accepted')


class Transcript:
    def __init__(self,fail=None):self.commands=[];self.fail=fail
    def run(self,label,command,timeout=90):
        self.commands.append((label,command))
        if self.fail==label:raise ValueError('Injected guard failure '+label)
        if label=='kernel_tmpfs':return b'6.12.112-prodock-luma3d-g3d1-r1\ntmpfs /tmp tmpfs rw 0 0\n'
        if label.startswith('size_'):
            path=list(c.TARGETS)[int(label[-1])]
            return f'-rwx------ 1 {c.TARGETS[path][0]} {path}\n'.encode()
        if label.startswith('remove_'):
            path=list(c.TARGETS)[int(label[-1])];size,_,crc=c.TARGETS[path]
            return f'FC1_REMOVED {path} {size} {crc}\n'.encode()
        return b''


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runtime',type=Path,required=True);args=parser.parse_args()
    plan,digest,runtime=c.preflight(args.runtime.resolve())
    for path,(size,sha,crc) in c.TARGETS.items():
        raw=f'-rwx------ 1 {size} {path}\r\n'.encode()
        assert c.size_check(raw,path)==size
        rejects(c.size_check,raw.replace(str(size).encode(),b'1'),path)
        rejects(c.size_check,raw.replace(b'-rwx',b'lrwx'),path)
        rejects(c.size_check,raw+raw,path)
        command=c.delete_command(path)
        subprocess.run(['/bin/sh','-n','-c',command],check=True)
        assert command.count('rm ')==1 and 'rm '+path+' &&' in command
        assert command.index('/tmp/mc1-helper raw '+path)<command.index('for fcdir')<command.index('rm '+path)
        assert '2097152' in command and 'shift 21; test "$1" = 35705238' in command
        assert 'exit 32' in command and 'exit 35' in command
        assert len(command.encode())*.002<10, 'Exceeds existing Channel text deadline'
    for path in ('/tmp/luma3d-gm1','/tmp/luma3d-fm4a','/tmp/op2-live.save','/tmp/gm1-*','/media/sd/foo'):
        rejects(c.delete_command,path)
    fake=types.SimpleNamespace(policy=runtime.policy,
        health=lambda channel,label: dict(identity=runtime.ANCHOR,gpu={'presents':1}),
        raw_check=lambda *args: None)
    tx=Transcript();result={'removed':[]};c.execute(tx,fake,result)
    assert [r['path'] for r in result['removed']]==list(c.TARGETS)
    for failure in ('helper_permissions','active_executables','size_0','remove_0','size_1','remove_1'):
        tx=Transcript(failure);result={'removed':[]};rejects(c.execute,tx,fake,result)
        if failure in ('helper_permissions','active_executables','size_0'):
            assert not any(label.startswith('remove_') for label,_ in tx.commands)
        assert not any('rm /tmp/luma3d-' in command or 'kill ' in command for _,command in tx.commands)
        if failure in ('remove_0','size_0'):
            assert not any(label=='remove_1' for label,_ in tx.commands)
    good=dict(host=runtime.policy.HOST,port=runtime.policy.PORT,plan_sha256=digest,runtime_plan_sha256=c.RUNTIME_SHA,anchor=runtime.ANCHOR,targets=list(c.TARGETS),reviewed_unix=1000)
    for key in ('root_authorized_two_obsolete_files_only','archives_verified_and_preserved','same_fm4a_since_inventory','same_g22r0_since_inventory','helper_unchanged_since_full_readback','ordinary_shell_confirmed','no_other_console_session'):good[key]=True
    c.review_check(good,digest,runtime,runtime.policy.HOST,1001)
    for key,value in [('anchor',dict(pid=3158,start_ticks=27508908)),('targets',['/tmp/luma3d-fm4a']),('ordinary_shell_confirmed',False),('reviewed_unix',0)]:
        bad=copy.deepcopy(good);bad[key]=value;rejects(c.review_check,bad,digest,runtime,runtime.policy.HOST,2000)
    print(json.dumps(dict(passed=True,hardware=False,plan_sha256=digest,archive_count=2,size_refusals=6,protected_path_refusals=5,injected_guard_failures=6,review_refusals=4,shell_syntax_cases=2,delete_commands=[c.delete_command(path) for path in c.TARGETS],scope='Pure guards/transcripts and shell parse only; no deletion command executed')))


if __name__=='__main__':main()
