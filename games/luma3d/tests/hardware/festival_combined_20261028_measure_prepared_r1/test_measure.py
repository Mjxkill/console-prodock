"""Offline guards, exact R4 logs and real cleanup method with fake process I/O."""
import copy
import json
from pathlib import Path
import types
from unittest import mock

import measure as m


def rejects(function, *args):
    try:
        function(*args)
    except (ValueError, KeyError):
        return
    raise AssertionError('Invalid input accepted')


class Channel:
    def __init__(self):
        self.shell = True
        self.launch_attempted = False
        self.commands = []

    def run(self, label, command):
        self.commands.append(command)
        return b''


class CleanupFixture(m.Hardware):
    """Only external observations are mocked; recover() itself is unchanged."""
    def __init__(self, manifest, pending, candidate, baseline=None):
        super().__init__(Channel(), manifest)
        self.stopping = True
        self.current = pending
        self.c.launch_attempted = pending is not None
        self.pending_result = candidate
        self.old_baseline = baseline
        self.new_baseline = dict(pid=5001, start_ticks=40000000)
        self.stop_calls = []
        self.save_snapshot = {'same':True}

    def identity(self, label, program, argv, pidfile):
        if label == 'cleanup_window':
            if isinstance(self.pending_result, Exception):raise self.pending_result
            return self.pending_result
        if label == 'cleanup_baseline':return self.old_baseline
        assert label in ('restored','published')
        assert program == m.BASE_PROGRAM and argv == m.BASE_ARGS
        return self.new_baseline

    def stop(self, *args):self.stop_calls.append(args)
    def demo_saves(self, label):return {'same':True}
    def raw_verify(self, *args):pass
    def progress(self, *args):return {'presents_delta':7}
    def saved(self, *args):return {'sha256':m.policy.SAVE_SHA}


def main():
    plan, digest = m.preflight()
    valid = dict(host=m.policy.HOST, port=m.policy.PORT, manifest_sha256=digest,
                 stage_result_sha256='a'*64, anchor=m.ANCHOR, fpga_sha256=m.policy.FPGA_SHA,
                 target_sha256=m.TARGET_SHA, reviewed_unix=1000)
    for key in ('root_authorized_seven_windows_and_restore_fm4a','same_fm4a_since_stage',
                'same_g22r0_since_stage','same_helper_target_since_stage','ordinary_shell_confirmed','no_other_console_session'):
        valid[key] = True
    m.review_check(valid,digest,'a'*64,m.policy.HOST,1001)
    for key,value in [('anchor',dict(pid=3158,start_ticks=27508908)),('ordinary_shell_confirmed',False),
                      ('stage_result_sha256','b'*64),('reviewed_unix',0)]:
        bad=copy.deepcopy(valid);bad[key]=value
        rejects(m.review_check,bad,digest,'a'*64,m.policy.HOST,2000)
    for index,row in enumerate(plan['windows']):
        command=m.launch_command(m.TAG+'_'+str(index),row)
        assert ('LUMA_SUBMIT_DIAG=1 ' in command)==(index==6)
        assert '--save' not in command and '--festival-save' not in command
        assert '--memory-save' not in command
    bad=copy.deepcopy(plan['windows'][0]);bad['args']=['--save','/tmp/forbidden']
    rejects(m.launch_command,'safe',bad)
    required={'hardware':1,'batches':2,'commands':78,'geometry_commands':72,'draws':32,
              'failed_batches':0,'sampled_batches':2,'invalid_samples':0,'wall_ns':10000000,
              'feed_us':100,'wait_us':9000,'cache_us':100,'cycles':1234,'vertices':300,'triangles':100}
    def line(value):return ('LUMA3D_SUBMIT_DIAG '+' '.join(f'{k}={v}' for k,v in value.items())+'\n').encode()
    assert m.diagnostic(line(required))==required
    rejects(m.diagnostic,line(required)*2)
    for key,value in [('hardware',0),('invalid_samples',1),('sampled_batches',1),('failed_batches',1),('wall_ns',0)]:
        bad=dict(required);bad[key]=value;rejects(m.diagnostic,line(bad))
    row=plan['windows'][0];pending=(m.TAG+'_0',row)
    # Before first byte: current exists, but no transmission; restore is allowed.
    f=CleanupFixture(plan,pending,ValueError('unpublished'));f.c.launch_attempted=False
    assert f.recover()['restored_fm4a'] and not f.stop_calls
    # Emission uncertain + no valid PID: never start a second GPU program.
    f=CleanupFixture(plan,pending,ValueError('unpublished'))
    rejects(f.recover);assert not f.c.commands and not f.restore_attempted
    # Published candidate: exact stop precedes exact baseline restoration.
    f=CleanupFixture(plan,pending,dict(pid=5000,start_ticks=39999999))
    assert f.recover()['restored_fm4a'] and len(f.stop_calls)==1
    assert f.stop_calls[0][2]==m.PROGRAM and f.stop_calls[0][3]==row['args']
    assert any('/tmp/luma3d-fm4a --festival --festival-save /tmp/fm4live1.festival.save' in x for x in f.c.commands)
    assert not any('luma3d-gm1' in x for x in f.c.commands)
    # Completed candidate: no redundant stop; still restore and publish new PID.
    f=CleanupFixture(plan,None,None);r=f.recover();assert r['identity']==f.new_baseline and not f.stop_calls
    f=CleanupFixture(plan,None,None,baseline=m.ANCHOR);assert f.recover()['preserved'] and not f.c.commands
    f=CleanupFixture(plan,None,None);f.demo_saves=lambda _: {'changed':True}
    rejects(f.recover);assert not f.c.commands
    print(json.dumps(dict(passed=True,hardware=False,review_guards=5,windows=7,diagnostic_guards=7,cleanup_cases=6,manifest_sha256=digest)))


if __name__ == '__main__':
    main()
