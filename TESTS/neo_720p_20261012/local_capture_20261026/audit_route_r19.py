#!/usr/bin/env python3
"""Read-only R19 route comparison against R18r1. SDF bounds are not a replacement for STA."""
import functools
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BUILD = ROOT/'tang/impl/console_neo_n56r19_capture_ce_local'
PARENT = ROOT/'tang/impl/console_neo_n56r18r1_local_capture'
OUT = HERE/'r19_postroute_01'
sys.path.insert(0, str(ROOT/'tools'))
sys.path.insert(0, str(HERE.parent/'reset_sequence_20261025'))
from audit_routed import cells, norm
from check_geometry_timing import inspect
from neo.timing import timing_checks
from neo.timing_closure import global_clock_routes

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def clean(s): return s.replace('\\', '')
def vec(s):
    v = tuple(float(x) for x in s.split(':'))
    assert len(v) == 3
    return v
def plus(a,b): return tuple(x+y for x,y in zip(a,b))

def main():
    assert not OUT.exists()
    assert json.loads((BUILD/'route_result.json').read_text())['returncode'] == 0
    assembly = json.loads((BUILD/'experiment.json').read_text())
    for name, digest in assembly['inputs'].items(): assert sha(BUILD/name) == digest, name
    src = BUILD/'source'
    assert {str(p.relative_to(src)):sha(p) for p in src.rglob('*') if p.is_file()} == json.loads((BUILD/'sources.json').read_text())
    pnr = BUILD/'impl/pnr'
    stable = [BUILD/n for n in ('console_neo.vg','sources.json','experiment.json','build.tcl','route_result.json')]
    stable += [pnr/('console_neo'+ext) for ext in ('.vo','.sdf','.tr','.fs','.rpt.txt')]
    stable += [PARENT/'impl/pnr/console_neo.vo', Path(__file__)]
    hashes = {str(p):sha(p) for p in stable}
    new, params = cells(pnr/'console_neo.vo')
    old, old_params = cells(PARENT/'impl/pnr/console_neo.vo')
    excluded = ('u_la0_top/','u_icon_top/','u_gw_jtag/')
    # Removal of GAO removes its private cells. Report every other delta;
    # the new HRDATA mux deliberately renames the legacy FF outputs.
    missing = sorted(n for n in old.keys()-new.keys() if not n.startswith(excluded))
    changes = {n:dict(before=old[n],after=new[n]) for n in old.keys()&new.keys() if old[n] != new[n]}
    param_changes = {k:dict(before=v,after=params.get(k)) for k,v in old_params.items()
                     if not k.startswith(excluded) and params.get(k) != v}
    additions = sorted(new.keys()-old.keys())
    # Flat SDF graph: interconnect and combinational IOPATHs; stop at FF Q.
    text = (pnr/'console_neo.sdf').read_text()
    assert '(TIMESCALE 1 ns)' in text
    incoming = {}
    clock_q = {}
    timing = {}
    def edge(dst, src, delay): incoming.setdefault(dst, []).append((src, delay))
    for block in text.split('\n  (CELL\n')[1:]:
        m = re.search(r'\(INSTANCE ([^\s)]+)\)', block)
        if not m: continue
        n = clean(m[1]); typ = re.search(r'\(CELLTYPE "([^"]+)"\)',block)[1]
        for a,b,d in re.findall(r'\(IOPATH (\S+) (\S+) \(([^)]+)\)\)',block):
            delay = vec(d)
            if typ.startswith('DFF'):
                if a == 'CLK' and b == 'Q': clock_q[n] = delay
            else: edge(n+'/'+clean(b), n+'/'+clean(a), delay)
        if typ.startswith('DFF'):
            timing[n] = block[block.find('(TIMINGCHECK'):]
    for a,b,d in re.findall(r'\(INTERCONNECT (\S+) (\S+) \(([^)]+)\)\)',text):
        edge(clean(b),clean(a),vec(d))
    del text
    @functools.lru_cache(None)
    def origins(pin):
        """Maximum per-corner delay from each registered Q through this cone."""
        cell, port = pin.rsplit('/',1)
        if cell in clock_q and port == 'Q': return {cell:clock_q[cell]}
        result = {}
        for source, delay in incoming.get(pin, []):
            for origin, before in origins(source).items():
                v = plus(before, delay)
                if origin in result: v=tuple(max(a,b) for a,b in zip(v,result[origin]))
                result[origin] = v
        return result
    local = 'u_accel/u_v1/u_pixels/u_capture/'
    bus = 'u_gpu_debug/u_capture_bus/'
    observer = {n:v for n,v in new.items() if n.startswith((local,bus))}
    ff = {n:v for n,v in observer.items() if v[0].startswith('DFF')}
    assert len(ff) == 344, len(ff)
    assert all(v[1]['CLK'] == ('gpu_clk' if n.startswith(local) else 'vid_hclk') for n,v in ff.items())
    shadow = {n:v for n,v in ff.items() if n.startswith(bus+'shadow_')}
    samples = {n:v for n,v in ff.items() if n.startswith((local+'at_event_',local+'after_event_'))}
    assert len(samples) == 48
    held_paths=[]
    for n,v in shadow.items():
        found=origins(n+'/D')
        for origin, delay in found.items():
            if origin.startswith(local+'held_'):
                held_paths.append(dict(source=origin,destination=n,max_by_corner_ns=delay))
    assert held_paths
    # Even just two further AHB cycles provide 25 ns after the synchronized
    # ACK. Conservatively require the whole data path to be below 20 ns.
    held_max=max(max(p['max_by_corner_ns']) for p in held_paths)
    assert held_max < 20, held_max
    sample_paths=[]
    for n in samples:
        for port in ('D','CE'):
            for origin, delay in origins(n+'/'+port).items():
                sample_paths.append(dict(source=origin,destination=n+'/'+port,
                                         max_by_corner_ns=delay,source_clock=new[origin][1].get('CLK')))
    tr=(pnr/'console_neo.tr').read_text()
    route_text=(pnr/'console_neo.rpt.txt').read_text()
    summary=inspect(BUILD,'console_neo')
    routes=global_clock_routes(route_text)
    required=json.loads((src/'tang/boards/neo/timing_closure.json').read_text())['required_primary_clocks']
    missing_primary=sorted(set(required)-{n for n,k,_ in routes if k=='PRIMARY'})
    constraints=re.findall(r'^\s*TC_\S+\s+(\S+)\s+(.+?)\s*$',tr,re.M)
    sdc=(src/'tang/boards/neo/neo.sdc').read_text()
    expected={' '.join(l.split()) for l in sdc.splitlines() if l.startswith(('create_','set_','report_timing '))}
    assert constraints and all(state=='Actived' for state,_ in constraints)
    assert expected == {' '.join(c.split()) for _,c in constraints}
    assert not missing_primary
    result=dict(candidate=str(BUILD),hardware_access=False,loaded=False,
        bitstream_sha256=sha(pnr/'console_neo.fs'),input_sha256=hashes,
        qualification_status=summary['status'],timing=timing_checks(tr),timing_summary=summary,
        missing_parent_cells=missing,changed_parent_cells=changes,changed_parent_parameters=param_changes,
        added_cells=additions,observer_ff_count=len(ff),sample_ff_count=len(samples),
        shadow_ff_count=len(shadow),held_shadow_paths=held_paths,held_shadow_max_ns=held_max,
        held_shadow_bound_ns=20,held_shadow_bound_passed=True,
        sample_cone_paths=sample_paths,required_primary=required,missing_primary=missing_primary,
        global_routes=routes,active_constraints=len(constraints),
        limits=['SDF data-delay bounds alone are not setup/hold qualification.',
                'Global timing FAIL retained; first-stage async crossings and recovery need separate interpretation.',
                'Observer reset is followed by two local guarded cycles; snapshot protocol must wait for ready.',
                'No hardware capture or GPU correctness result is implied.'])
    assert all(sha(Path(p))==digest for p,digest in hashes.items())
    OUT.mkdir();(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(timing=result['timing'],missing=len(missing),changes=len(changes),
        parameter_changes=len(param_changes),added=len(additions),held_shadow_max_ns=held_max,
        samples=len(samples),shadow=len(shadow),bitstream=result['bitstream_sha256'])))

if __name__=='__main__': main()
