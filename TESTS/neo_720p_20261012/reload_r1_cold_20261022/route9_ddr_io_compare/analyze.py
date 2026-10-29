#!/usr/bin/env python3
"""Read-only, reproducible comparison of routed DDR I/O arcs; no board access.

SDF paths end at the logical PAD pin of an I/O primitive. They do not include
PCB flight times, measured calibration taps, analog eye margins or a new STA.
Delays are retained as MIN/TYP/MAX and rise/fall separately, in integer ps.
"""
from collections import defaultdict, Counter
from decimal import Decimal
import csv
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
IP = 'u_soc/g_ddr.u_ddr/u_ip/'
PHY = IP + 'gw3_top/u_ddr_phy_top/'
BUILDS = {
    'n56r8': ('console_neo_n56r8_hdmi_sg4', '51841fe4ae76a7eb635a0398534f35b6c7030fa8b768d88b892fede3b1601c35'),
    'r2': ('console_neo_n56r9_route2', '150bd72724ef7ec79c511afe2cc1c01f5976113ec00c39e8fc15e1f272731a01'),
    'r9': ('console_neo_n56r9_route9_dma_c150', '1593a2aaf7d84e5d099520d96b5d60852340601fd861d2c21108bace846e2fde'),
}
BUF = {'OBUF', 'TBUF', 'IOBUF', 'ELVDS_IOBUF', 'ELVDS_OBUF'}
SER = {'OSER8', 'OSER8_MEM', 'IDES8_MEM', 'DQS', 'IODELAY', 'DDRDLL', 'CLKDIV'}


def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def norm(s):
    return re.sub(r'\\(.)', r'\1', s)


def net(s):
    return s.strip().replace('\\', '').replace(' ', '')


def expand(s):
    if s.startswith('{'):
        assert s.endswith('}')
        parts=[]; start=0; depth=0; body=s[1:-1]
        for i,c in enumerate(body):
            if c=='{': depth+=1
            elif c=='}': depth-=1
            elif c==',' and depth==0:
                parts.append(body[start:i]); start=i+1
        parts.append(body[start:])
        return [x for part in parts for x in expand(part)]
    m=re.fullmatch(r'(.*)\[(\d+):(\d+)\]',s)
    if m:
        a,b=int(m[2]),int(m[3]); step=1 if b>a else -1
        return [m[1]+f'[{i}]' for i in range(a,b+step,step)]
    return [s]


def ps(s):
    v = s.split(':')
    assert len(v) == 3 and all(v), s
    return [int(Decimal(x) * 1000) for x in v]


def delay_values(tail):
    vals = re.findall(r'\(([-\d.:]+)\)', tail)
    assert len(vals) in (1, 2), tail
    vv = [ps(v) for v in vals]
    return dict(rise_ps=vv[0], fall_ps=vv[-1])


def netlist(path):
    body = path.read_text()
    cc = {}
    for m in re.finditer(r'^(\w+)\s+(\\\S+|\w+)\s*\((.*?)\);', body, re.M | re.S):
        if m[1] == 'module':
            continue
        name = m[2].lstrip('\\')
        assert name not in cc, name
        cc[name] = dict(kind=m[1], pins={p: net(n) for p, n in re.findall(r'\.(\w+)\(([^()]*)\)', m[3])})
    params = defaultdict(dict)
    for m in re.finditer(r'^defparam\s+(\\\S+|\w+)\s*\.([A-Za-z0-9_]+)\s*=\s*([^;]+);', body, re.M):
        params[m[1].lstrip('\\')][m[2]] = m[3].strip()
    return cc, dict(params)


def parse_sdf(path, cc):
    arcs, io, checks = {}, defaultdict(list), defaultdict(list)
    instance = None
    selected = False
    with path.open() as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if line.startswith('(TIMESCALE'):
                assert line == '(TIMESCALE 1 ns)', line
            elif line.startswith('(INSTANCE '):
                instance = norm(line[len('(INSTANCE '):-1])
                selected = (instance.startswith(IP) or instance.startswith('u_soc/u_pll_ddr3/')
                            or instance == 'ddr_addr_15_obuf')
            elif line.startswith('(IOPATH ') and selected:
                m = re.fullmatch(r'\(IOPATH ([^\s()]+) ([^\s()]+)\s*(\(.+)\)', line)
                assert m, line
                io[instance].append(dict(source=m[1], destination=m[2],
                    line=lineno, **delay_values(m[3])))
            elif selected and re.match(r'\((SETUPHOLD|RECOVERY|REMOVAL|WIDTH|PERIOD) ', line):
                checks[instance].append(line)
            elif line.startswith('(INTERCONNECT '):
                m = re.fullmatch(r'\(INTERCONNECT (\S+) (\S+) (.+)\)', line)
                assert m, line
                s, d = norm(m[1]), norm(m[2])
                if IP not in s and IP not in d and 'u_soc/u_pll_ddr3/' not in s and 'u_soc/u_pll_ddr3/' not in d and 'ddr_addr_15_obuf/' not in d:
                    continue
                assert (s, d) not in arcs, (s, d)
                arcs[(s, d)] = dict(source=s, destination=d, line=lineno, **delay_values(m[3]))
    assert io and arcs
    return arcs, dict(io), dict(checks)


def summarize_segments(segments, inverted_output=False):
    # SDF IOPATH rise/fall values refer to that arc's OUTPUT transition.
    # For a final differential inverted pad, every upstream transition flips.
    return {k: [sum(s[('fall_ps' if k=='rise_ps' else 'rise_ps')
                      if inverted_output and j<len(segments)-1 else k][i]
                    for j,s in enumerate(segments)) for i in range(3)]
            for k in ('rise_ps', 'fall_ps')}


def analyze(label, dirname, bit):
    b = ROOT / 'tang/impl' / dirname
    paths = ['impl/pnr/console_neo.' + x for x in ('vo', 'sdf', 'fs', 'tr', 'rpt.txt')]
    paths += ['source/tang/boards/neo/neo.cst', 'source/tang/boards/neo/neo.sdc', 'sources.json', 'qualification.json']
    identities = {p: sha(b / p) for p in paths}
    assert identities['impl/pnr/console_neo.fs'] == bit
    q = json.loads((b / 'qualification.json').read_text())
    assert q['status'] == 'FAIL' and q['bitstream_sha256'] == bit
    cc, params = netlist(b / 'impl/pnr/console_neo.vo')
    arcs, io, checks = parse_sdf(b / 'impl/pnr/console_neo.sdf', cc)
    inc, out = defaultdict(list), defaultdict(list)
    for arc in arcs.values():
        inc[arc['destination']].append(arc)
        out[arc['source']].append(arc)
        # Independently check every retained route against routed Verilog nets.
        sc, sp = arc['source'].rsplit('/', 1)
        dc, dp = arc['destination'].rsplit('/', 1)
        def value(cell, pin):
            if pin in cc[cell]['pins']:
                return cc[cell]['pins'][pin]
            p, ix = re.fullmatch(r'(\w+)\[(\d+)\]', pin).groups()
            raw = cc[cell]['pins'][p]
            assert raw.startswith('{') and raw.endswith('}'), (cell, pin, raw)
            bits=expand(raw)
            assert int(ix)<len(bits), (cell,pin,raw,bits)
            return bits[::-1][int(ix)]
        assert value(sc, sp) == value(dc, dp), (label, sc, sp, dc, dp)

    def cellarc(name, source, dest):
        matches = [a for a in io.get(name, []) if a['source'] == source and a['destination'] == dest]
        assert len(matches) == 1, (label, name, source, dest, matches)
        return dict(matches[0], source=name + '/' + source, destination=name + '/' + dest, type='cell')

    def route_to(node):
        assert len(inc[node]) == 1, (label, node, inc[node])
        return dict(inc[node][0], type='route')

    def route_from(node):
        assert len(out[node]) == 1, (label, node, out[node])
        return dict(out[node][0], type='route')

    pins = {}
    rpt = (b / 'impl/pnr/console_neo.rpt.txt').read_text()
    for line in rpt.splitlines():
        fields = [p.strip() for p in line.split('|')]
        if len(fields) > 10 and re.fullmatch(r'[A-Z]+\d+/\d+',fields[0]) and re.fullmatch(r'ddr_\w+(?:\[\d+\])?', fields[1]):
            row=dict(ball_bank=fields[0], direction=fields[2], site=fields[3], fields=fields)
            if fields[1] in pins:
                assert pins[fields[1]]==row, (fields[1],pins[fields[1]],row)
            pins[fields[1]] = row
    assert len(pins) == 72, len(pins)
    rows = {}
    connected = {}
    for name, c in cc.items():
        if c['kind'] not in BUF:
            continue
        for pin, n in c['pins'].items():
            if n not in pins or pin not in {'IO', 'IOB', 'O', 'OB'}:
                continue
            connected[n] = dict(instance=name, pin=pin, **c)
            r = route_to(name + '/I')
            segments = [r, cellarc(name, 'I', pin)]
            inverted=pin in {'OB','IOB'}
            rows[n + ':out'] = dict(port=n, direction='out', package=pins[n],
                inverted_final_buffer=inverted, segments=segments, **summarize_segments(segments,inverted))
            drv, dp = r['source'].rsplit('/', 1)
            if cc[drv]['kind'].startswith('OSER'):
                clockarcs = [a for a in io[drv] if a['destination'] == dp and a['source'] in {'TCLK', 'FCLK', 'PCLK'}]
                assert len(clockarcs) == 1, (drv, dp, clockarcs)
                clk = clockarcs[0]['source']
                seg = [cellarc(drv, clk, dp)] + segments
                rows[n + ':launch'] = dict(port=n, direction='launch', package=pins[n],
                    reference=drv + '/' + clk, inverted_final_buffer=inverted,
                    segments=seg, **summarize_segments(seg,inverted))
            if 'OEN' in c['pins']:
                enroute=route_to(name+'/OEN')
                seg=[enroute,cellarc(name,'OEN',pin)]
                rows[n+':enable']=dict(port=n,direction='enable',package=pins[n],
                    note='SDF OEN control timing; not a DQ data edge',
                    segments=seg,**summarize_segments(seg))
                edrv,edp=enroute['source'].rsplit('/',1)
                if cc[edrv]['kind'].startswith('OSER'):
                    ea=[a for a in io[edrv] if a['destination']==edp and a['source'] in {'TCLK','FCLK','PCLK'}]
                    assert len(ea)==1,(edrv,edp,ea)
                    eseg=[cellarc(edrv,ea[0]['source'],edp)]+seg
                    rows[n+':enable_launch']=dict(port=n,direction='enable_launch',package=pins[n],
                        reference=edrv+'/'+ea[0]['source'],note='SDF OEN control timing; not a DQ data edge',
                        segments=eseg,**summarize_segments(eseg))
            if c['kind'] not in {'IOBUF', 'ELVDS_IOBUF'}:
                continue
            input_paths=[]
            for a in out[name+'/O']:
                seg=[cellarc(name,pin,'O'),dict(a,type='route')]
                recv,rp=a['destination'].rsplit('/',1)
                if cc[recv]['kind']=='IODELAY':
                    seg.append(cellarc(recv,rp,'DO'))
                    assert out[recv+'/DO']
                    input_paths.extend(seg+[dict(aa,type='route')] for aa in out[recv+'/DO'])
                else:
                    input_paths.append(seg)
            assert input_paths
            primary=0; tap=0
            for seg in sorted(input_paths,key=lambda s:s[-1]['destination']):
                recv,rp=seg[-1]['destination'].rsplit('/',1)
                if (cc[recv]['kind'],rp) in {('IDES8_MEM','D'),('DQS','DQSIN')}:
                    direction='in'; primary+=1
                else:
                    direction=f'in_fabric_tap{tap}'; tap+=1
                rows[n+':'+direction]=dict(port=n,direction=direction,package=pins[n],
                    segments=seg,**summarize_segments(seg))
            assert primary==1,(n,primary,input_paths)
    assert set(connected) == set(pins)
    hard = {n: dict(c, parameters=params.get(n, {})) for n, c in cc.items()
            if n.startswith(IP) and (c['kind'] in SER or c['kind'] in BUF)}
    groups = defaultdict(list)
    for a in arcs.values():
        sc, sp = a['source'].rsplit('/', 1)
        dc, dp = a['destination'].rsplit('/', 1)
        kind = cc[dc]['kind']
        if dc in hard:
            if dp in {'FCLK', 'HCLKIN', 'CLKIN'}: group = 'phy_fast_clock_routes'
            elif dp == 'PCLK': group = 'phy_ui_clock_routes'
            elif dp in {'TCLK', 'ICLK'}: group = 'phy_dqs_clock_routes'
            elif dp in {'RESET', 'RESETN', 'RST', 'CLEAR', 'CALIB'}: group = 'phy_reset_routes'
            elif re.fullmatch(r'D\d|TX\d', dp): group = 'fabric_to_serializer_data_routes'
            elif kind in {'DQS', 'DDRDLL', 'IODELAY'}: group = 'phy_calibration_control_routes'
            else: group = 'other_phy_routes'
            groups[group].append(a)
        if sc.startswith(IP) and cc[sc]['kind'] == 'IDES8_MEM' and re.fullmatch(r'Q[0-7]', sp):
            groups['deserializer_to_fabric_routes'].append(a)
    result = dict(build=str(b), identities=identities, bitstream_sha256=bit,
        qualification_status=q['status'], timing_ns=q['timing_checks_ns'],
        paths=rows, pins=pins, hard_primitives=hard,
        primitive_iopaths={n: [{k:v for k,v in a.items() if k!='line'} for a in io.get(n, [])] for n in hard},
        primitive_timing_checks={n: checks.get(n, []) for n in hard},
        route_groups=dict(groups), interconnect_count=len(arcs))
    (HERE / (label + '.json')).write_text(json.dumps(result, indent=2) + '\n')
    # All DDR-related routes, including calibration logic, available to review.
    with (HERE / (label + '_all_ddr_routes.csv')).open('w') as f:
        w=csv.writer(f); w.writerow(['source', 'destination', 'rise_min_ps', 'rise_typ_ps', 'rise_max_ps', 'fall_min_ps', 'fall_typ_ps', 'fall_max_ps', 'sdf_line'])
        for a in sorted(arcs.values(), key=lambda x:(x['source'],x['destination'])):
            w.writerow([a['source'], a['destination'], *a['rise_ps'], *a['fall_ps'], a['line']])
    return result


def without_line(a):
    return {k:v for k,v in a.items() if k!='line'}


def compare(data):
    result = dict(scope='Routed DDR I/O SDF comparison; NOT hardware calibration or timing qualification',
                  hardware_access=False, hardware_cause_proven=False, comparisons={})
    r9=data['r9']
    for label in ('n56r8', 'r2'):
        old=data[label]
        assert set(old['paths']) == set(r9['paths'])
        c=dict(pin_config_identical=old['pins']==r9['pins'], path_count=len(r9['paths']))
        c['path_differences']={}
        for key, a in old['paths'].items():
            b=r9['paths'][key]
            if [without_line(x) for x in a['segments']] != [without_line(x) for x in b['segments']]:
                c['path_differences'][key]=dict(before_rise_ps=a['rise_ps'], after_rise_ps=b['rise_ps'],
                    delta_rise_ps=[v-u for u,v in zip(a['rise_ps'],b['rise_ps'])],
                    before_fall_ps=a['fall_ps'], after_fall_ps=b['fall_ps'])
        c['primitive_diff']={n:dict(before=old['hard_primitives'].get(n),after=r9['hard_primitives'].get(n))
            for n in old['hard_primitives'].keys() | r9['hard_primitives'].keys()
            if old['hard_primitives'].get(n)!=r9['hard_primitives'].get(n)}
        c['primitive_iopaths_identical']=old['primitive_iopaths']==r9['primitive_iopaths']
        c['primitive_timing_checks_identical']=old['primitive_timing_checks']==r9['primitive_timing_checks']
        c['groups']={}
        for group, bb in r9['route_groups'].items():
            aa=old['route_groups'][group]
            a={(x['source'],x['destination']):x for x in aa}
            b={(x['source'],x['destination']):x for x in bb}
            common=a.keys() & b.keys()
            diffs=[]
            for key in common:
                if without_line(a[key])!=without_line(b[key]):
                    diffs.append(dict(source=key[0], destination=key[1], before_ps=a[key]['rise_ps'],after_ps=b[key]['rise_ps'],
                        delta_max_ps=b[key]['rise_ps'][2]-a[key]['rise_ps'][2]))
            c['groups'][group]=dict(before_count=len(a), after_count=len(b), common=len(common),
                missing_before=sorted(b.keys()-a.keys()), missing_after=sorted(a.keys()-b.keys()),
                max_route_before_ps=max(x['rise_ps'][2] for x in aa), max_route_after_ps=max(x['rise_ps'][2] for x in bb),
                changed=len(diffs), largest_differences=sorted(diffs,key=lambda x:abs(x['delta_max_ps']),reverse=True)[:30])
        result['comparisons'][label]=c
    (HERE/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    with (HERE/'pin_paths.csv').open('w') as f:
        w=csv.writer(f)
        w.writerow(['port','direction','ball_bank','site','start','end']+[f'{b}_{e}_{corner}_ps' for b in data for e in ('rise','fall') for corner in ('min','typ','max')])
        for key,r in sorted(r9['paths'].items()):
            w.writerow([r['port'],r['direction'],r['package']['ball_bank'],r['package']['site'],r['segments'][0]['source'],r['segments'][-1]['destination']]+
                [x for b in data for e in ('rise','fall') for x in data[b]['paths'][key][e+'_ps']])
    print(json.dumps({k:{f:v for f,v in c.items() if f not in ('primitive_diff','groups')} for k,c in result['comparisons'].items()},indent=2))


def main():
    data={}
    for label,(dirname,bit) in BUILDS.items():
        print('Extracting '+label,flush=True)
        data[label]=analyze(label,dirname,bit)
    compare(data)
    manifest=dict(script_sha256=sha(Path(__file__)), inputs={k:v['identities'] for k,v in data.items()},
        outputs={p.name:sha(p) for p in HERE.iterdir() if p.suffix in {'.json','.csv'} and p.name!='manifest.json'})
    (HERE/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')


if __name__ == '__main__':
    main()
