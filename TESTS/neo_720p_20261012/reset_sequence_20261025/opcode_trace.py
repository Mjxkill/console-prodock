#!/usr/bin/env python3
"""Decode the 32-signal R17 observation without inventing unobserved data."""
import csv
import io
from pixel_trace import word


def parse_csv(text,m):
    lines=text.splitlines()
    assert lines and lines[0].strip()=='Data:'
    table=list(csv.reader(io.StringIO('\n'.join(lines[1:])),skipinitialspace=True))
    table=[[v.strip() for v in (row[:-1] if row and not row[-1].strip() else row)]
           for row in table if row]
    assert table and table[0][0].startswith('time unit:')
    names=table[0][1:]
    assert set(names)==set(m['unique_signals'])
    counts={n:names.count(n) for n in names}
    trigger=m['controls']['shader_start']
    assert all(c==1 or (n==trigger and c==2) for n,c in counts.items())
    rows=[]
    for i,fields in enumerate(table[1:]):
        assert len(fields)==len(names)+1 and fields[0]==str(i)
        row={}
        for name,token in zip(names,fields[1:]):
            assert token.lower() in ('0','1','x','z')
            value=int(token) if token in ('0','1') else None
            if name in row: assert row[name]==value, 'Duplicate disagreement'
            row[name]=value
        rows.append(row)
    assert len(rows)>=2
    return rows


def analyze(rows,m):
    decoded=[]
    for i,row in enumerate(rows):
        d=dict(sample=i)
        d.update({stage:word(row,m[stage]) for stage in ('geometry_header','actual_pixel_D','pixel_Q')})
        d.update({key:row[name] for key,name in m['controls'].items()})
        decoded.append(d)
    captures=[]; mismatches=[]; ce_errors=[]; skipped=[]
    for i,(a,b) in enumerate(zip(decoded,decoded[1:])):
        rst,ce,start,idle=(a[k] for k in ('pixel_reset_active_high','pixel_capture_enable','shader_start','pixel_idle'))
        if None not in (ce,start,idle) and ce!=(start & idle): ce_errors.append(i)
        if rst==1: expected,rule=0,'reset'
        elif rst==0 and ce==1:
            expected,rule=a['actual_pixel_D'],'capture'
            captures.append(dict(sample=i,D=expected,Q_before=a['pixel_Q'],Q_next=b['pixel_Q'],geometry=a['geometry_header']))
        elif rst==0 and ce==0: expected,rule=a['pixel_Q'],'hold'
        else: expected,rule=None,'unknown_control'
        if expected is None or b['pixel_Q'] is None: skipped.append(i)
        elif expected!=b['pixel_Q']: mismatches.append(dict(sample=i,rule=rule,expected=expected,observed_next=b['pixel_Q']))
    unknown=sum(v is None for row in rows for v in row.values())
    return dict(samples=len(rows),observed_mask='0xff000000',rows=decoded,
        sampled_capture_events=captures,conditional_dffre_mismatches=mismatches,
        conditional_checks_skipped=skipped,ce_and_disagreements=ce_errors,
        unknown_values=unknown,
        sampled_capture_consistent=bool(captures) and not any((mismatches,skipped,ce_errors,unknown)),
        hardware_cause_established=False,
        limits='Only opcode bits [31:24]. Same-domain pre-edge alignment assumed; encrypted GAO pipeline and subcycle behavior are not verified.')
