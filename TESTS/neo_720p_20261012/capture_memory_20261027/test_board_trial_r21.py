#!/usr/bin/env python3
"""Local controller fixtures: retained faults, exact bytes and explicit outcomes."""
import hashlib
import json
from pathlib import Path
import tempfile

import board_trial_r21 as trial


def fixture(raw=0xd2670010100d0010, completed=1, rejected=0):
    before,after = [0]*26,[0]*26
    before[0]=after[0]=0x424c5432
    before[2]=1;after[2]=2 if completed else 1
    after[1]=0 if completed else 1
    after[13]=rejected
    lines = ['GPU_BEFORE '+' '.join(map(str,before)),
             'GPU_AFTER '+' '.join(map(str,after)),
             f'COMMAND_COMPLETE {completed}', 'ARM_EPOCH 1',
             f'NCP 0x4e435031 0x2c 1 1 {raw&0xffffffff} {raw>>32}',
             'CASE_OBSERVED']
    return '\n'.join(lines)+'\n'


def main():
    checks=0
    regions,expected=trial.local_plan()
    assert expected['COPY16'][32:64] == regions['source'][1][32:64]
    assert expected['CLEAR_COLOR16'][32:64] == b'\xa5\x5a'*16
    for data in expected.values():
        assert data[:32] == regions['color'][1][:32] and data[64:] == regions['color'][1][64:]
    checks+=4
    row=trial.parse_case(fixture(),16)
    assert row['capture']['findings']==['COPY_WIDTH_CAPTURE_CONSISTENT']
    checks+=1
    broken=trial.parse_case(fixture(0xd2e70010100d0010),16)
    assert broken['capture'] is None and broken['decode_error']
    assert broken['capture_raw'][4] == 0x100d0010
    checks+=2
    incomplete=trial.parse_case(fixture(0xd240000000000000),16)
    assert incomplete['capture']['findings']==['COPY_CAPTURE_INCOMPLETE']
    checks+=1
    for completed,rejected,exact,unchanged,outcome in [
        (1,0,True,False,'completed_exact'),
        (1,0,False,False,'completed_wrong_memory'),
        (1,1,False,True,'rejected_unchanged'),
        (1,1,False,False,'rejected_with_memory_change'),
        (0,0,False,True,'timeout_unchanged'),
        (0,0,False,False,'timeout_with_memory_change'),
        (0,1,False,False,'timeout_with_memory_change_and_errors'),
    ]:
        row=trial.parse_case(fixture(completed=completed,rejected=rejected),16)
        row['name']='COPY16'
        for key in ('color','depth','source'):
            row[key]=dict(expected_matches=exact if key=='color' else True,
                          unchanged=unchanged if key=='color' else True)
        assert trial.classify(row)==outcome
        assert row['copy_width_capture_complete']
        checks+=2
    incomplete.update(name='COPY16',**{k:dict(unchanged=True,expected_matches=False)
                                     for k in ('color','depth','source')})
    trial.classify(incomplete)
    assert not incomplete['copy_width_capture_complete']
    checks+=1
    # Malformed register records never reach a hardware action or produce a
    # misleading decoded result. A valid record with malformed D* is retained.
    for bad in [fixture().replace('CASE_OBSERVED',''),
                fixture().replace('0x4e435031','0x12345678'),
                fixture().replace('0x2c','0x0c')]:
        try:trial.parse_case(bad,16)
        except AssertionError:checks+=1
        else:raise AssertionError('Malformed register record accepted')
    with tempfile.TemporaryDirectory(prefix='neo-r21-controller-') as tmp:
        path=Path(tmp)/'review.json'
        path.write_text(json.dumps(dict(board='neo',diagnostic_access_ready=True,
                                       controller_sha256='0'*64)))
        try:trial.route_review(path)
        except AssertionError:checks+=1
        else:raise AssertionError('Stale controller hash accepted')
    files=[Path(__file__),Path(trial.__file__),trial.HERE/'decode_capture.py',trial.ANCHOR]
    result=dict(passed=True,hardware=False,checks=checks,
        limitations=['Route-output positive preflight awaits the actual bitstream and physical-path review.',
                     'No board programming or OpenOCD process is invoked by these fixtures.'],
        inputs={str(p.relative_to(trial.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    out=trial.HERE/'board_controller_test_01.json';assert not out.exists()
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()
