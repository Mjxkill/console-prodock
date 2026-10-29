"""Frozen Neo timing experiment, with post-route checks of every assumption.

Gowin includes generated-clock source latency in set_max_delay, even for
Q/D endpoints. Normalize only the pre-existing asynchronous 8 ns bounds,
in BOTH directions. Distribution skew, C2Q and setup remain timed. The
initial measured-latency method must match after routing. The optional
zero-origin method retains literal 8 ns bounds and verifies the origins.
No clock period, false path, multicycle, USB or DDR RTL is changed here.
"""
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

PROFILE = Path('tang/boards/neo/timing_closure.json')
BOUND = re.compile(r'^set_max_delay ([-\d.]+) -from \[get_clocks \{(\w+)\}\] -to \[get_clocks \{(\w+)\}\]$', re.M)
ORIGIN_CLOCKS=('vid_pclk','vid_clk5x','PHY_CLKOUT','fclk_960M')
ORIGIN_COMMAND='set_clock_latency -source 0 [get_clocks {'+' '.join(ORIGIN_CLOCKS)+'}]'


def sections(text):
    for index, kind in enumerate(('Setup', 'Hold', 'Recovery', 'Removal'), 1):
        found = re.search(r'^3\.3\.'+str(index)+' '+kind+
                          r' Analysis Report\n(.*?)(?=^3\.3\.[1-4] [A-Z]|^3\.[4-9][. ]|\Z)', text, re.M | re.S)
        if not found:
            raise ValueError('Missing detailed '+kind+' report')
        yield kind.lower(), found[1].split('Path Summary:')[1:]


def source_latencies(text):
    """Slow-corner source tCL only, never hold/removal fast-corner values."""
    values = {}
    for kind, blocks in sections(text):
        if kind not in ('setup', 'recovery'):
            continue
        for block in blocks:
            for label, start, end in (('Launch','Data Arrival Path:','Data Required Path:'),
                                      ('Latch','Data Required Path:','Path Statistics:')):
                clock = re.search(label+r' Clk\s*:\s*(\w+):\[[RF]\]', block)
                part = block.split(start)[-1].split(end)[0]
                delays = re.findall(r'^\s*[-\d.]+\s+([-\d.]+)\s+tCL\s+', part, re.M)
                if clock and delays:
                    values.setdefault(clock[1], set()).add(sum(map(Decimal, delays)))
    if not values or any(len(v) != 1 for v in values.values()):
        raise ValueError('Missing or ambiguous slow source clock latencies')
    return {clock: str(next(iter(value))) for clock, value in sorted(values.items())}


def compensate(sdc, latencies):
    matches = list(BOUND.finditer(sdc))
    pairs = {(m[2], m[3]) for m in matches}
    if len(matches) != 14 or len(pairs) != 14:
        raise ValueError('Expected fourteen unique existing CDC bounds')
    if any(a == b or (b, a) not in pairs for a, b in pairs):
        raise ValueError('CDC bounds must be bidirectional, never same-clock')
    entries = []
    def replace(m):
        if Decimal(m[1]) != 8:
            raise ValueError('Expected original 8 ns CDC budget')
        a, b = m[2], m[3]
        if a not in latencies or b not in latencies:
            raise ValueError('Missing latency for '+a+' -> '+b)
        limit = Decimal(8) + Decimal(latencies[a]) - Decimal(latencies[b])
        entries.append(dict(source=a, sink=b, budget_ns='8.000', sdc_limit_ns=f'{limit:.3f}'))
        return m[0].replace('set_max_delay '+m[1], f'set_max_delay {limit:.3f}', 1)
    return BOUND.sub(replace, sdc), entries


def freeze(source, reference, column=150):
    source, reference = Path(source), Path(reference).resolve(strict=True)
    board = source/'tang/boards/neo'
    if (source/PROFILE).exists():
        raise ValueError('Timing experiment already applied')
    if column != 150:
        raise ValueError('Only the characterized HDMI reset column 150 is supported')
    original = {name:(board/name).read_bytes() for name in ('console_neo.v','neo.cst','neo.sdc')}
    top = original['console_neo.v'].decode()
    old = "DHCE u_video_fast(.CLKIN(clk5x_raw),.CLKOUT(clk5x),.CEN(1'b0));"
    new = "DCE u_video_fast(.CLKIN(clk5x_raw),.CLKOUT(clk5x),.CE(1'b1));"
    if top.count(old) != 1:
        raise ValueError('Unexpected Neo HDMI clock driver')
    top = top.replace(old, new)
    cst = original['neo.cst'].decode()
    cst, count = re.subn(r'(u_hdmi/g_reset\[[012]\]\.reset_sync_fall_s1" R\d+C)181',
                         lambda m:m[1]+str(column), cst)
    if count != 3:
        raise ValueError('Expected three fixed HDMI reset FF sites')
    cst += ('\n// Neo timing closure experiment: measured HDMI reset placement.\n'
            'CLOCK_LOC "clk5x" BUFG[4] = CLK;\n'
            '// Scan queue reset receivers near their existing bus reset driver.\n'
            'INS_LOC "u_scan_queue/up_0_s0" R[67:75]C[71:79];\n'
            'INS_LOC "u_scan_queue/up_1_s0" R[67:75]C[71:79];\n')
    raw = reference.read_bytes()
    latencies = source_latencies(raw.decode())
    sdc, entries = compensate(original['neo.sdc'].decode(), latencies)
    # Preserve every reset edge in the detailed report even in the full design.
    for kind in ('recovery','removal'):
        sdc, count = re.subn(r'report_timing -'+kind+r' -max_paths \d+ -max_common_paths 1',
            'report_timing -'+kind+' -max_paths 10000 -max_common_paths 3', sdc)
        if count != 1:
            raise ValueError('Missing reset report request')
    record = dict(version=1, reference=str(reference),
        reference_sha256=hashlib.sha256(raw).hexdigest(),
        source_latency_ns=latencies, cdc_bounds=entries, hdmi_reset_column=column,
        original_sha256={k:hashlib.sha256(v).hexdigest() for k,v in original.items()},
        scope='Experimental Neo-only clock distribution, reset placement and CDC latency normalization; requires post-route audit.')
    for name, text in (('console_neo.v',top), ('neo.cst',cst), ('neo.sdc',sdc)):
        (board/name).write_text(text)
    (source/PROFILE).write_text(json.dumps(record,indent=2)+'\n')


def audit(source, report):
    source, report = Path(source), Path(report)
    record = json.loads((source/PROFILE).read_text())
    text = report.read_text()
    actual = source_latencies(text)
    errors, bounds = [], []
    sdc = (source/'tang/boards/neo/neo.sdc').read_text()
    cst = (source/'tang/boards/neo/neo.cst').read_text()
    requested_index=record.get('hdmi_clock_index',4)
    expected_index=[] if requested_index=='auto' else [str(requested_index)]
    if re.findall(r'CLOCK_LOC "clk5x" BUFG\[(\d+)\] = CLK;',cst) != expected_index:
        errors.append('Changed HDMI clock allocation')
    site=record.get('hdmi_dce_site')
    if site and cst.count(f'INS_LOC "u_video_fast" {site};')!=1:
        errors.append('Changed HDMI DCE placement')
    if site:
        observed=set(re.findall(r'\s((?:PG|SG)\[\d+\])\s+u_video_fast/(?:CLKIN|CLKOUT)\s*$',text,re.M))
        if observed!={site}:errors.append('HDMI DCE site not confirmed by routed timing paths')
    if record.get('required_primary_clocks'):
        resources=report.with_suffix('.rpt.txt')
        table=re.search(r'^\s*6\. Global Clock Signals\s*$(.*?)^\s*7\. ',
                        resources.read_text() if resources.exists() else '',re.M|re.S)
        actual_primary=set(re.findall(r'^\s*([^|\n]+?)\s*\|\s*PRIMARY\s*\|',table[1],re.M)) if table else set()
        for net in record['required_primary_clocks']:
            if net not in actual_primary:errors.append('Required primary clock not retained: '+net)
    column=record['hdmi_reset_column']
    for ch,row,slot in ((0,102,1),(1,102,2),(2,57,1)):
        wanted=f'INS_LOC "u_hdmi/g_reset[{ch}].reset_sync_fall_s1" R{row}C{column}[{slot}][A];'
        if cst.count(wanted)!=1:errors.append('Changed HDMI reset placement '+str(ch))
    limits = {(m[2],m[3]):Decimal(m[1]) for m in BOUND.finditer(sdc)}
    if record.get('normalization')=='zero-source-origins':
        if sdc.splitlines().count(ORIGIN_COMMAND)!=1:
            errors.append('Missing normalized generated-clock origins')
        for clock in ORIGIN_CLOCKS:
            if clock in actual and Decimal(actual[clock])!=0:
                errors.append('Nonzero normalized source origin '+clock)
    expected_pairs = {(e['source'], e['sink']) for e in record['cdc_bounds']}
    if len(expected_pairs) != 14 or set(limits) != expected_pairs:
        errors.append('Missing or extra CDC bounds')
    for entry in record['cdc_bounds']:
        a,b = entry['source'],entry['sink']
        if a not in actual or b not in actual or (a,b) not in limits:
            errors.append('Missing measured clock/bound '+a+' -> '+b)
            continue
        effective = limits[a,b] - Decimal(actual[a]) + Decimal(actual[b])
        # Do not accept either loose or overconstrained stale normalization.
        if abs(effective - Decimal(8)) > Decimal('0.002'):
            errors.append(f'Stale source latency: {a} -> {b}, effective budget {effective} ns')
        if limits[a,b] != Decimal(entry['sdc_limit_ns']):
            errors.append('Changed frozen CDC bound '+a+' -> '+b)
        bounds.append(dict(source=a,sink=b,effective_budget_ns=str(effective)))
    reset_paths = []
    for kind, blocks in sections(text):
        if kind not in ('recovery','removal'):
            continue
        for block in blocks:
            target = re.search(r'^To\s*:\s*u_hdmi/g_ser\[([012])\]\.u_ser\s*$',block,re.M)
            if not target:
                continue
            driver = f'u_hdmi/g_reset[{target[1]}].reset_sync_fall_s1'
            origin = re.search(r'^From\s*:\s*(\S+)',block,re.M)
            if not origin or origin[1] != driver:
                errors.append('Unexpected HDMI reset driver for channel '+target[1])
            launch = re.search(r'Launch Clk\s*:\s*(\w+:\[[RF]\])',block)
            latch = re.search(r'Latch Clk\s*:\s*(\w+:\[[RF]\])',block)
            slack = re.search(r'^Slack\s*:\s*([-\d.]+)',block,re.M)
            if not launch or not latch or not slack:
                errors.append('Incomplete HDMI reset timing path')
                continue
            reset_paths.append(dict(kind=kind,channel=int(target[1]),launch=launch[1],
                                    latch=latch[1],slack_ns=float(slack[1])))
    for kind in ('recovery','removal'):
        for ch in range(3):
            for clock in ('vid_pclk:[R]','vid_clk5x:[R]','vid_clk5x:[F]'):
                found=[p for p in reset_paths if p['kind']==kind and p['channel']==ch and p['latch']==clock]
                if not found or any(p['launch']!='vid_pclk:[F]' for p in found):
                    errors.append(f'Missing/wrong {kind} check HDMI {ch} {clock}')
                elif min(p['slack_ns'] for p in found) < 0:
                    errors.append(f'Negative {kind} check HDMI {ch} {clock}')
    return dict(passed=not errors,errors=errors,source_latency_ns=actual,
                cdc_bounds=bounds,hdmi_reset_paths=reset_paths)


def refresh(source, reference):
    """Renormalize an existing frozen experiment before a new complete route.

    Never modify the parent build or its report. The new build still needs
    the full post-route audit: latency may change again with placement.
    """
    source, reference = Path(source), Path(reference).resolve(strict=True)
    record = json.loads((source/PROFILE).read_text())
    if record.get('normalization')=='zero-source-origins':
        raise ValueError('Zero-source origins do not need measured latency compensation')
    path = source/'tang/boards/neo/neo.sdc'
    sdc = path.read_text()
    prior = {(e['source'],e['sink']):e for e in record['cdc_bounds']}
    def original(m):
        entry = prior.get((m[2],m[3]))
        if not entry or Decimal(m[1]) != Decimal(entry['sdc_limit_ns']):
            raise ValueError('Changed existing CDC experiment')
        return m[0].replace('set_max_delay '+m[1], 'set_max_delay 8', 1)
    base = BOUND.sub(original,sdc)
    raw = reference.read_bytes()
    latencies = source_latencies(raw.decode())
    normalized, entries = compensate(base,latencies)
    record.setdefault('previous_references',[]).append(dict(
        reference=record['reference'],reference_sha256=record['reference_sha256'],
        source_latency_ns=record['source_latency_ns']))
    record.update(reference=str(reference),reference_sha256=hashlib.sha256(raw).hexdigest(),
                  source_latency_ns=latencies,cdc_bounds=entries)
    path.write_text(normalized)
    (source/PROFILE).write_text(json.dumps(record,indent=2)+'\n')


def select_hdmi_clock(source, index):
    """Change only the characterized HDMI clock index in a new frozen copy."""
    source=Path(source)
    if index not in (4,8,12):
        raise ValueError('Uncharacterized HDMI clock index')
    record=json.loads((source/PROFILE).read_text())
    path=source/'tang/boards/neo/neo.cst'
    cst=path.read_text()
    old=record.get('hdmi_clock_index',4)
    expected=f'CLOCK_LOC "clk5x" BUFG[{old}] = CLK;'
    if cst.count(expected)!=1:
        raise ValueError('Changed original HDMI clock allocation')
    cst=cst.replace(expected,f'CLOCK_LOC "clk5x" BUFG[{index}] = CLK;',1)
    record['hdmi_clock_index']=index
    path.write_text(cst)
    (source/PROFILE).write_text(json.dumps(record,indent=2)+'\n')


def auto_hdmi_clock(source):
    """Let the router allocate HDMI without changing any other clock request."""
    source=Path(source)
    record=json.loads((source/PROFILE).read_text())
    path=source/'tang/boards/neo/neo.cst';cst=path.read_text()
    expected=f'CLOCK_LOC "clk5x" BUFG[{record.get("hdmi_clock_index",4)}] = CLK;'
    if cst.count(expected)!=1:
        raise ValueError('Changed original HDMI clock allocation')
    path.write_text(cst.replace(expected,'// HDMI DCE clock resource selected by P&R.',1))
    record['hdmi_clock_index']='auto'
    (source/PROFILE).write_text(json.dumps(record,indent=2)+'\n')


def select_hdmi_placement(source, choice):
    """Second characterized physical solution; identical RTL and clock rates."""
    placements={'pg8-c181':('PG[8]',181),'pg9-c181':('PG[9]',181),
                'sg0-c150':('SG[0]',150),'sg0-c160':('SG[0]',160)}
    if choice not in placements:
        raise ValueError('Uncharacterized HDMI placement')
    source=Path(source)
    auto_hdmi_clock(source)
    record=json.loads((source/PROFILE).read_text())
    path=source/'tang/boards/neo/neo.cst';cst=path.read_text()
    if record['hdmi_reset_column']!=150 or 'INS_LOC "u_video_fast"' in cst:
        raise ValueError('Changed original HDMI placement')
    site,column=placements[choice]
    cst,count=re.subn(r'(u_hdmi/g_reset\[[012]\]\.reset_sync_fall_s1" R\d+C)150',
                      lambda m:m[1]+str(column),cst)
    if count!=3:raise ValueError('Missing HDMI reset drivers')
    cst+=f'INS_LOC "u_video_fast" {site};\n'
    record.update(hdmi_reset_column=column,hdmi_dce_site=site)
    if site=='SG[0]':
        record['required_primary_clocks']=['clk_d','pixel_clk','clk48','fclk_960m','phy_clk',
            'vid_hclk','gpu_clk','u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/sclk']
    path.write_text(cst)
    (source/PROFILE).write_text(json.dumps(record,indent=2)+'\n')


def move_hdmi_resets(source, column):
    """Move an existing SG[0] experiment between its two characterized columns."""
    source=Path(source)
    record=json.loads((source/PROFILE).read_text())
    previous=record.get('hdmi_reset_column')
    if (column not in (150,160) or previous not in (150,160) or
            record.get('hdmi_dce_site')!='SG[0]' or record.get('hdmi_clock_index')!='auto'):
        raise ValueError('Expected characterized SG[0] HDMI placement')
    path=source/'tang/boards/neo/neo.cst';cst=path.read_text()
    if cst.count('INS_LOC "u_video_fast" SG[0];')!=1:
        raise ValueError('Changed HDMI DCE constraint')
    for ch,row,slot in ((0,102,1),(1,102,2),(2,57,1)):
        old=f'INS_LOC "u_hdmi/g_reset[{ch}].reset_sync_fall_s1" R{row}C{previous}[{slot}][A];'
        if cst.count(old)!=1:
            raise ValueError('Changed HDMI reset constraint')
        cst=cst.replace(old,old.replace(f'C{previous}[',f'C{column}['),1)
    record['hdmi_reset_column']=column
    path.write_text(cst)
    (source/PROFILE).write_text(json.dumps(record,indent=2)+'\n')


def zero_clock_origins(source):
    """Use local origins for existing async bounds, preserve HDMI common phase.

    Measured Gowin behavior: this overrides generated source tCL while the
    actual clock distribution arcs remain in STA. Both related HDMI clocks
    share one origin, so their recovery/removal/setup/hold remain unchanged.
    USB PHY/fclk domains already follow the vendor asynchronous clock group.
    All fourteen pre-existing maximum delays return to literal 8 ns.
    """
    source=Path(source)
    record=json.loads((source/PROFILE).read_text())
    path=source/'tang/boards/neo/neo.sdc';sdc=path.read_text()
    if 'set_clock_latency ' in sdc:
        raise ValueError('Source origins already constrained')
    lat=record['source_latency_ns']
    if 'vid_pclk' not in lat or 'vid_clk5x' not in lat or lat['vid_pclk']!=lat['vid_clk5x']:
        raise ValueError('HDMI clocks do not share a common source origin')
    vendor='set_clock_groups -asynchronous -group [get_clocks {PHY_CLKOUT}] -group [get_clocks {sclk}] -group [get_clocks {fclk_960M}]'
    if sdc.splitlines().count(vendor)!=1:
        raise ValueError('Unknown USB PHY clock relationships')
    entries={(e['source'],e['sink']):e for e in record['cdc_bounds']}
    def replace(m):
        entry=entries.get((m[2],m[3]))
        if not entry or Decimal(m[1])!=Decimal(entry['sdc_limit_ns']):
            raise ValueError('Changed CDC bound')
        return m[0].replace('set_max_delay '+m[1],'set_max_delay 8',1)
    normalized=BOUND.sub(replace,sdc)
    # Validate count, symmetry and original budget before writing anything.
    _,bounds=compensate(normalized,{k:'0.000' for k in lat})
    marker='report_timing -setup '
    if normalized.count(marker)!=1:raise ValueError('Missing setup report')
    normalized=normalized.replace(marker,
        '// Local timing origins; common HDMI phase and distribution arcs remain checked.\n'+ORIGIN_COMMAND+'\n'+marker,1)
    record.update(normalization='zero-source-origins',cdc_bounds=bounds,
                  original_measured_latency_ns=dict(lat))
    record['source_latency_ns']={k:('0.000' if k in ORIGIN_CLOCKS else v) for k,v in lat.items()}
    path.write_text(normalized)
    (source/PROFILE).write_text(json.dumps(record,indent=2)+'\n')


def focused_hdmi_reports(source):
    """Append focused reports; retain the complete unfiltered global checks."""
    source=Path(source)
    record=json.loads((source/PROFILE).read_text())
    path=source/'tang/boards/neo/neo.sdc';sdc=path.read_text()
    pins=' '.join(f'u_hdmi/g_ser[{ch}].u_ser/RESET' for ch in range(3))
    for kind in ('recovery','removal'):
        lines=[l for l in sdc.splitlines() if l.startswith('report_timing -'+kind+' ')]
        if len(lines)!=1 or re.fullmatch(r'report_timing -'+kind+r' -max_paths \d+ -max_common_paths \d+',lines[0]) is None:
            raise ValueError('Expected one unfiltered global '+kind+' report')
        sdc+=f'report_timing -{kind} -to [get_pins {{{pins}}}] -max_paths 32 -max_common_paths 3\n'
    record['focused_hdmi_reports']=True
    path.write_text(sdc)
    (source/PROFILE).write_text(json.dumps(record,indent=2)+'\n')
