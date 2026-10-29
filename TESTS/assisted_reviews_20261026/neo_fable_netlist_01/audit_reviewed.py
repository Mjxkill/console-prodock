#!/usr/bin/env python3
"""Read-only pin-cone SDF inventory; conservative bounds, never STA approval."""
import functools
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BUILD = ROOT / 'tang/impl/console_neo_n56r19_capture_ce_local'
sys.path.insert(0, str(ROOT / 'TESTS/neo_720p_20261012/reset_sequence_20261025'))
from audit_routed import cells


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def norm(s):
    return s.replace('\\', '')


def triple(s):
    v = tuple(float(x) for x in s.split(':'))
    assert len(v) == 3
    return v


def main():
    out = HERE / 'sdf_cones_01'
    assert not out.exists()
    vo = BUILD / 'impl/pnr/console_neo.vo'
    sdf = BUILD / 'impl/pnr/console_neo.sdf'
    cs, params = cells(vo)
    source_hash = {str(p.relative_to(ROOT)): sha(p) for p in
                   [vo, sdf, Path(__file__), ROOT / 'TESTS/neo_720p_20261012/reset_sequence_20261025/audit_routed.py']}
    text = sdf.read_text()
    assert '(TIMESCALE 1 ns)' in text
    # Fail rather than silently ignore conditional or multi-delay timing arcs.
    assert not any(re.search(r'\(' + word + r'\b', text) for word in ('COND', 'CONDELSE', 'RETAIN'))
    incoming = {}
    ctoq = {}
    checks = {}
    def edge(dst, src, delay):
        incoming.setdefault(dst, []).append((src, delay))
    known_comb = {'LUT1','LUT2','LUT3','LUT4','LUT5','LUT6','LUT7','LUT8',
                  'MUX2','MUX4','MUX8','INV','BUF','IBUF','OBUF'}
    ignored_cells = {}
    for block in text.split('\n  (CELL\n')[1:]:
        inst = re.search(r'\(INSTANCE ([^\s)]+)\)', block)
        if not inst:
            continue
        n = norm(inst[1]); typ = re.search(r'\(CELLTYPE "([^"]+)"\)', block)[1]
        if not typ.startswith('DFF') and typ not in known_comb:
            ignored_cells[n] = typ
            continue
        arcs = re.findall(r'\(IOPATH (\S+) (\S+) \(([^)]+)\)\)', block)
        assert len(arcs) == block.count('(IOPATH '), n
        for a,b,v in arcs:
            d = triple(v)
            if typ.startswith('DFF'):
                assert a in ('CLK','CLEAR','PRESET') and b == 'Q', (n,a,b)
                if a == 'CLK':
                    ctoq[n] = d
                # Async control-to-Q is a distinct path class. Do not treat
                # it as a combinational continuation through a register.
            elif typ in known_comb:
                edge(n+'/'+norm(b), n+'/'+norm(a), d)
            else:
                raise AssertionError((n,typ))
        for kind,a,b,setup,hold in re.findall(
                r'\((SETUPHOLD) \((pos|neg)edge (\w+)\) \(posedge CLK\) \(([^)]+)\) \(([^)]+)\)\)', block):
            checks.setdefault(n+'/'+b, []).append(dict(edge=a, setup=triple(setup), hold=triple(hold)))
    interconnects = re.findall(r'\(INTERCONNECT (\S+) (\S+) \(([^)]+)\)\)', text)
    assert len(interconnects) == text.count('(INTERCONNECT ')
    for a,b,v in interconnects:
        edge(norm(b), norm(a), triple(v))
    del text
    active = set()
    unresolved = set()
    @functools.lru_cache(None)
    def origins(pin):
        cell, port = pin.rsplit('/',1)
        if cell in ctoq and port == 'Q':
            return {cell:(ctoq[cell],ctoq[cell])}
        assert pin not in active, 'Combinational cycle: '+pin
        active.add(pin)
        result = {}
        edges = incoming.get(pin, [])
        if not edges:
            net = cs.get(cell, [None,{}])[1].get(port)
            if net not in ('VCC','GND',"1'b0","1'b1"):
                unresolved.add(pin)
        for source, delay in edges:
            for origin,(lo,hi) in origins(source).items():
                bounds = (tuple(x+y for x,y in zip(lo,delay)),tuple(x+y for x,y in zip(hi,delay)))
                if origin in result:
                    old_lo,old_hi=result[origin]
                    bounds=(tuple(min(x,y) for x,y in zip(old_lo,bounds[0])),
                            tuple(max(x,y) for x,y in zip(old_hi,bounds[1])))
                result[origin]=bounds
        active.remove(pin)
        return result
    targets = ['u_accel/u_v1/u_pixels/native_valid_s1','u_accel/v1_pending_s2',
               'u_accel/v1_accepted_s0','u_accel/v1_tx_write_s0',
               'u_soc/g_ddr.u_ddr/u_gpu_arb/take_blitter_s0']
    paths=[]; endpoint=[]
    for target in targets:
        assert cs[target][0].startswith('DFF')
        clocks = incoming.get(target+'/CLK',[])
        assert len(clocks)==1, (target,clocks)
        endpoint.append(dict(cell=target,kind=cs[target][0],pins=cs[target][1],
                             init=params.get(target+'.INIT'),clock=clocks[0]))
        for pin in ('D','CE','RESET'):
            if pin not in cs[target][1]:
                continue
            dst=target+'/'+pin; tc=checks.get(dst,[])
            for origin,(lo,hi) in origins(dst).items():
                src_clock=incoming.get(origin+'/CLK',[])
                item=dict(source=origin,destination=dst,min_delay_ns=lo,max_delay_ns=hi,
                          timing_checks=tc,source_clock=src_clock)
                if len(src_clock)==1 and src_clock[0][0]==clocks[0][0] and tc:
                    # Same modeled clock root. Per-corner skew retained.
                    # Conservative edge aggregation; no path sensitization or
                    # constraint exceptions, jitter or derating modeled.
                    setup=tuple(max(c['setup'][k] for c in tc) for k in range(3))
                    hold=tuple(max(c['hold'][k] for c in tc) for k in range(3))
                    item['raw_setup_bound_ns']=tuple(13.333+clocks[0][1][k]-src_clock[0][1][k]-hi[k]-setup[k] for k in range(3))
                    item['raw_hold_bound_ns']=tuple(src_clock[0][1][k]+lo[k]-clocks[0][1][k]-hold[k] for k in range(3))
                else:
                    item['bound_unavailable']='Different/unknown clock roots or timing check absent'
                paths.append(item)
    assert all(sha(ROOT/n)==v for n,v in source_hash.items())
    result=dict(complete_inventory=not unresolved, hardware_access=False,
                qualification='NOT_A_TIMING_QUALIFICATION', global_R19_status='FAIL',
                inputs=source_hash,endpoints=endpoint,paths=paths,
                unresolved_frontiers=sorted(unresolved),
                untraversed_primitive_types=sorted(set(ignored_cells.values())),
                limits=['Subset pin-cone bounds only, no STA signoff or causal hardware conclusion.',
                        'Clock-root equality is required before computing a raw bound.',
                        'Only DFF Q endpoints and explicit combinational IOPATHs are traversed.',
                        'Recovery/removal, pulse width, signal integrity, derating and constraint exceptions are not proved.',
                        'No claim of physical clock or CE polarity correctness from static net names.'])
    out.mkdir();(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    for t in targets:
        p=[q for q in paths if q['destination'].startswith(t+'/') and 'raw_setup_bound_ns' in q]
        print(t, 'origins',len(p),'raw setup minimum',min((min(q['raw_setup_bound_ns']) for q in p),default=None))
    print('unresolved:',sorted(unresolved))


if __name__=='__main__':
    main()
