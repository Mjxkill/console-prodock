#!/usr/bin/env python3
"""Exercise reduced GAO visibility using the proven R15 mapped simulation trace."""
import copy
import csv
import io
import json
from pathlib import Path
from prepare_opcode_probe import HERE,PARENT,probes,sha
import pixel_trace as full
import opcode_trace as reduced


def encode(rows,m,duplicate=True):
    names=([m['controls']['shader_start']] if duplicate else [])+m['unique_signals']
    out=io.StringIO();out.write('Data:\n')
    writer=csv.writer(out)
    writer.writerow(['time unit: us',*names,''])
    for i,row in enumerate(rows):
        writer.writerow([i,*[row[n] if row[n] is not None else 'x' for n in names],''])
    return out.getvalue()


def main():
    out=HERE/'opcode_trace_check_01'
    out.mkdir(exist_ok=False)
    old=HERE/'pixel_trace_check_01'
    proof=json.loads((old/'result.json').read_text())
    assert proof['passed'] and proof['captures']==16
    for name,digest in proof['files'].items(): assert sha(old/name)==digest,name
    text=(old/'mapped_trace.csv').read_text()
    all_rows=full.parse_csv(text,full.mapping())
    m=probes((PARENT/'console_neo.vg').read_text())
    rows=[{name:row[name] for name in m['unique_signals']} for row in all_rows]
    encoded=encode(rows,m)
    decoded=reduced.parse_csv(encoded,m)
    assert decoded==rows
    r=reduced.analyze(decoded,m)
    tests={}
    assert r['sampled_capture_consistent'] and len(r['sampled_capture_events'])==16
    original=full.analyze(all_rows,full.mapping())
    assert [v['sample'] for v in r['sampled_capture_events']]==[v['sample'] for v in original['sampled_capture_events']]
    for a,b in zip(r['sampled_capture_events'],original['sampled_capture_events']):
        for key in ('D','Q_before','Q_next','geometry'): assert a[key]==b[key]&0xff000000
    tests['mapped_16_captures_before_and_after_reset']=True
    i=r['sampled_capture_events'][0]['sample']
    bad=copy.deepcopy(rows)
    for net in m['pixel_Q'].values():bad[i+1][net]=0
    assert any(v['sample']==i and v['rule']=='capture' for v in reduced.analyze(bad,m)['conditional_dffre_mismatches'])
    tests['missed_capture_detected']=True
    bad=copy.deepcopy(rows);bad[i][m['controls']['pixel_capture_enable']]=0
    assert i in reduced.analyze(bad,m)['ce_and_disagreements']
    tests['missing_ce_detected']=True
    bad=copy.deepcopy(rows);bad[i][m['controls']['pixel_reset_active_high']]=1
    assert any(v['sample']==i and v['rule']=='reset' for v in reduced.analyze(bad,m)['conditional_dffre_mismatches'])
    tests['unexpected_reset_detected']=True
    bad=copy.deepcopy(rows);bad[i][m['actual_pixel_D']['24']]=None
    unknown=reduced.analyze(reduced.parse_csv(encode(bad,m),m),m)
    assert i in unknown['conditional_checks_skipped'] and not unknown['sampled_capture_consistent']
    tests['unknown_is_not_zero_or_pass']=True
    assert not reduced.analyze(rows[:2],m)['sampled_capture_consistent']
    tests['no_capture_is_not_pass']=True
    alias=copy.deepcopy(rows[i]);alias[m['actual_pixel_D']['31']]=1
    assert full.word(alias,m['actual_pixel_D'])&0xe0000000==0xe0000000
    tests['actual_D_alias_preserved']=True
    lines=encoded.splitlines();fields=next(csv.reader([lines[2]]))
    fields[1]='1' if fields[1]=='0' else '0';lines[2]=','.join(fields)
    try:reduced.parse_csv('\n'.join(lines),m)
    except AssertionError:tests['duplicate_disagreement_rejected']=True
    else:raise AssertionError('Disagreeing duplicate accepted')
    missing=copy.deepcopy(m);missing['unique_signals']=m['unique_signals'][:-1]
    try:reduced.parse_csv(encoded,missing)
    except AssertionError:tests['unexpected_signal_set_rejected']=True
    else:raise AssertionError('Wrong signal set accepted')
    # The lower 24 bits are deliberately outside this observation: retain the
    # limitation explicitly instead of calling the reduced capture a full packet test.
    hidden=copy.deepcopy(all_rows)
    lower=full.mapping()['pixel_Q']['0'];hidden[i+1][lower]=1-hidden[i+1][lower]
    assert full.analyze(hidden,full.mapping())['conditional_dffre_mismatches']
    projected=[{name:row[name] for name in m['unique_signals']} for row in hidden]
    assert reduced.analyze(projected,m)['sampled_capture_consistent']
    tests['unobserved_lower_bit_limitation_demonstrated']=True
    (out/'mapped_opcode.csv').write_text(encoded)
    (out/'decoded.json').write_text(json.dumps(r,indent=2)+'\n')
    result=dict(passed=True,hardware_access=False,mapping=m,samples=len(rows),captures=16,
        tests=tests,scope='Projection of the existing exact-mapped R15 functional trace; not a new timing or hardware test',
        inputs={str(p):sha(p) for p in (PARENT/'console_neo.vg',old/'result.json',old/'mapped_trace.csv',
            HERE/'prepare_pixel_probe.py',HERE/'prepare_opcode_probe.py',HERE/'pixel_trace.py',HERE/'opcode_trace.py',Path(__file__))},
        output_sha256={p.name:sha(p) for p in out.iterdir() if p.is_file()})
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,samples=len(rows),captures=16,checks=len(tests),signals=32)))


if __name__=='__main__':main()
