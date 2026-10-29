"""Read-only Gowin timing analysis. A partial report can never pass."""
import hashlib
import json
from pathlib import Path
import re

from runtime import sha

NUMBER = r'-?\d+(?:\.\d+)?'
LOC = re.compile(r'^R(\d+)C(\d+)\[(\d+)\]\[([AB])\]$')


def diagnose_path(path):
    """Measured data arcs only; suggestions are hypotheses, never timing waivers."""
    arcs = path.get('arcs', [])
    if not arcs:
        return None
    route = sum(a['delay_ns'] for a in arcs if a['kind'] in ('tNET', 'routing'))
    clock_to_q = sum(a['delay_ns'] for a in arcs if a['kind'] == 'tC2Q')
    logic = sum(a['delay_ns'] for a in arcs if a['kind'] not in ('tNET', 'routing', 'tC2Q'))
    total = route + clock_to_q + logic
    fanout = max((a.get('fanout') or 0 for a in arcs), default=0)
    fraction = route / total if total > 0 else 0
    same_clock = path.get('launch_clock') == path.get('clock') and bool(path.get('clock'))
    hint = 'Lire les contraintes et les synchroniseurs avant toute modification.'
    if path['analysis'] == 'setup' and same_clock:
        if fraction >= .6:
            hint = 'Tester un regroupement des cellules et vérifier la congestion.'
            if fanout >= 64:
                hint += ' Forte charge : tester des registres locaux ou découpler la commande du bus de données.'
        elif fraction <= .4:
            hint = 'Examiner la profondeur logique et les possibilités de pipeline.'
        else:
            hint = 'Examiner conjointement la profondeur logique et le placement.'
    wires = sorted((a for a in arcs if a['kind'] in ('tNET', 'routing')),
                   key=lambda a:a['delay_ns'], reverse=True)[:3]
    return dict(route_ns=round(route, 3), logic_ns=round(logic, 3),
                clock_to_q_ns=round(clock_to_q, 3), total_ns=round(total, 3),
                route_percent=round(100*fraction, 1), max_fanout=fanout,
                largest_wires=wires, hypothesis=hint,
                limits='Arcs de données publiés ; hypothèse à tester par routage complet et contrôles fonctionnels.')


def field(text, name):
    match = re.search(r'^\s*' + re.escape(name) + r'\s*:\s*(.*?)\s*$', text, re.M)
    return match[1] if match else None


def clock_routing(text, log):
    """Report actual clock/control resources, without inferring board health.

    Gowin lists the same net twice when it uses both a primary tree and HCLK.
    Keep both entries, including long hierarchical names without padded spaces.
    A LW allocation is evidence to inspect, not by itself a timing violation.
    """
    section = re.search(r'^\s*6\. Global Clock Signals\s*$(.*?)^\s*7\. ', text, re.M | re.S)
    entries = []
    if section:
        entries = [dict(net=net.strip(), resource=kind, location=location.strip())
                   for net, kind, location in re.findall(
                       r'^\s*([^|\n]+)\|\s*(PRIMARY|LW|HCLK)\s*\|([^\n]*)', section[1], re.M)]
    warnings = re.findall(r'^WARN\s+\((?:CT1018|PR1014)\)[^\n]*', log, re.M)
    return dict(entries=entries, lw_nets=[e['net'] for e in entries if e['resource']=='LW'],
                warnings=warnings,
                scope='Routage publié par Gowin ; une allocation LW ne prouve pas un défaut sur carte.')


def attach_board_results(report, paths):
    """Attach explicit test records by exact bitstream hash, never by build name.

    These records describe the supplied tests only. Mixed pass/fail evidence
    stays visible; it must not turn into a global hardware qualification.
    """
    records = []
    for path in dict.fromkeys(Path(p).resolve(strict=True) for p in paths):
        path = path/'result.json' if path.is_dir() else path
        raw = path.read_bytes()
        data = json.loads(raw)
        digest = data.get('bitstream_sha256')
        if type(data.get('passed')) is not bool or not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('Board evidence requires a boolean verdict and SHA-256: '+str(path))
        if not any(b.get('bitstream_sha256') == digest for b in report['builds']):
            raise ValueError('Board evidence matches no reported bitstream: '+str(path))
        records.append(dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(),
                            bitstream_sha256=digest, passed=data['passed'],
                            error=str(data.get('load_error') or data.get('transport_error') or '')[:2000]))
    for build in report['builds']:
        tests = [r for r in records if r['bitstream_sha256'] == build.get('bitstream_sha256')]
        outcomes = {r['passed'] for r in tests}
        state = ('MIXED_RESULTS' if len(outcomes) == 2 else
                 'TESTS_FAILED' if outcomes == {False} else
                 'TESTS_PASSED' if outcomes == {True} else 'NOT_TESTED')
        build['board_tests'] = dict(state=state, records=tests,
            scope='Résultats des essais fournis, rattachés par SHA-256 du bitstream ; pas une validation complète de la carte.')


def parse_timing(text):
    counts = {kind.lower(): int(value) for kind, value in re.findall(
        r'<Numbers of (Setup|Hold) Violated Endpoints>:\s*(\d+)', text)}
    groups = [dict(clock=c, analysis=a, tns_ns=float(t), endpoints=int(n)) for c, a, t, n in
              re.findall(r'^\s*(\S+)\s+(setup|hold)\s+(' + NUMBER + r')\s+(\d+)\s*$', text, re.M)]
    clocks = {name: float(freq) for name, freq in re.findall(
        r'^\s*\d+\s+(\S+)\s+(?:Base|Generated)\s+[\d.]+\s+([\d.]+)MHz', text, re.M)}
    constraints = [dict(state=s, command=' '.join(c.split())) for s, c in re.findall(
        r'^\s*TC_\S+\s+(\S+)\s+(.+?)\s*$', text, re.M)]
    pulses = [float(n) for n in re.findall(
        r'^\s*\d+\s+(' + NUMBER + r')\s+[\d.]+\s+[\d.]+\s+(?:High|Low) Pulse Width\s+', text, re.M)]
    paths = []
    # Explicit sections exclude exception reports and abbreviated path tables.
    sections = list(re.finditer(r'^3\.3\.[1-4] (Setup|Hold|Recovery|Removal) Analysis Report\s*$', text, re.M))
    for index, section in enumerate(sections):
        end = sections[index + 1].start() if index + 1 < len(sections) else text.find('\n3.4 ', section.end())
        body = text[section.end():end if end >= 0 else len(text)]
        for block in body.split('Path Summary:')[1:]:
            slack = field(block, 'Slack')
            if slack is None:
                continue
            path = dict(analysis=section[1].lower(), slack_ns=float(slack),
                        source=field(block, 'From'), destination=field(block, 'To'),
                        launch_clock=field(block, 'Launch Clk'), clock=field(block, 'Latch Clk'), arcs=[])
            data = block.split('Data Arrival Path:', 1)
            if len(data) > 1:
                arrival = data[1].split('Data Required Path:', 1)[0]
                started = False
                for delay, kind, fanout, loc, node in re.findall(
                    r'^\s*' + NUMBER + r'\s+(' + NUMBER + r')\s+(t\w+)\s+[RF]{2}\s+(\d+)\s+(\S+)\s+(\S+)\s*$', arrival, re.M):
                    if kind == 'tC2Q':
                        started = True
                    if not started:
                        continue
                    coords = LOC.fullmatch(loc)
                    path['arcs'].append(dict(delay_ns=float(delay), kind=kind, fanout=int(fanout),
                                             loc=loc, node=node, cell=node.rsplit('/', 1)[0],
                                             row=int(coords[1]) if coords else None,
                                             col=int(coords[2]) if coords else None))
            stats = re.search(r'Arrival Data Path Delay:\s*\(cell:\s*(' + NUMBER + r').*?route:\s*(' + NUMBER + r')', block, re.S)
            if stats:
                path['cell_ns'], path['route_ns'] = map(float, stats.groups())
            path['diagnosis'] = diagnose_path(path)
            if path['diagnosis']:
                # Include clock-to-Q in the denominator, as Gowin does.
                path['route_fraction'] = path['diagnosis']['route_percent']/100
            paths.append(path)
    slacks = [float(v) for v in re.findall(r'^Slack\s*:\s*(' + NUMBER + ')', text, re.M)]
    complete = bool(set(counts) == {'setup', 'hold'} and groups and clocks and constraints and slacks and pulses)
    complete = complete and all({g['analysis'] for g in groups if g['clock'] == c} == {'setup', 'hold'} for c in clocks)
    complete = complete and len(sections) == 4
    analysis_path_counts = {kind:sum(p['analysis']==kind for p in paths)
                            for kind in ('setup','hold','recovery','removal')}
    # An empty report section can result from a bad timing exception. Never
    # count its heading alone as coverage. A design with no reset paths needs
    # a separate structural justification; this generic reader cannot infer it.
    missing_analysis = [kind for kind,count in analysis_path_counts.items() if not count]
    complete = complete and not missing_analysis
    clean = complete and min(slacks + pulses) >= 0 and not any(counts.values())
    clean = clean and all(g['tns_ns'] >= 0 and g['endpoints'] == 0 for g in groups)
    clean = clean and all(c['state'] == 'Actived' for c in constraints)
    return dict(complete=complete, timing_clean=clean, clocks_mhz=clocks, constraints=constraints,
                analysis_path_counts=analysis_path_counts, missing_analysis=missing_analysis,
                violated_endpoints=counts, groups=groups, paths=sorted(paths, key=lambda p:p['slack_ns']),
                wns_ns=min(slacks + pulses) if slacks else None, pulse_wns_ns=min(pulses) if pulses else None,
                tns_ns=sum(g['tns_ns'] for g in groups),
                no_fmax_clocks=re.findall(r'No timing paths to get frequency of (\S+)!', text))


def inspect_build(build):
    build = Path(build).resolve(strict=True)
    result = dict(backend='gowin', name=build.name, directory=str(build), status='INCOMPLETE', issues=[], paths=[])
    log_path = build / 'build.log'
    log = log_path.read_text(errors='replace') if log_path.exists() else ''
    result['clock_routing'] = clock_routing('', log)
    errors = re.findall(r'^ERROR[^\n]*', log, re.M)
    result['errors'] = errors
    if errors:
        result['status'] = 'BUILD_FAILED'
    reports = list((build / 'impl/pnr').glob('*.tr'))
    if len(reports) != 1:
        result['issues'].append('Missing or ambiguous timing report')
        return result
    report = reports[0]
    text = report.read_text(errors='replace')
    result.update(parse_timing(text))
    if result['missing_analysis']:
        result['issues'].append('Missing detailed timing checks: '+', '.join(result['missing_analysis']))
    result['report_sha256'] = sha(report)
    result['part'] = field(text, '<Part Number>')
    result['tool_version'] = field(text, '<Tool Version>')
    result['resources'] = {}
    resource_path = report.with_suffix('.rpt.txt')
    if resource_path.exists():
        resources = resource_path.read_text()
        result['clock_routing'] = clock_routing(resources, log)
        for resource in ('Logic', 'Register', 'CLS', 'BSRAM', 'DSP'):
            found = re.search(r'^\s*' + resource + r'\s*\|\s*([\d.]+)/(\d+)', resources, re.M)
            if found:
                result['resources'][resource] = dict(used=float(found[1]), available=int(found[2]))
    completed = f'Generate file "{report}" completed' in log and 'Bitstream generation completed' in log
    bitstream = report.with_suffix('.fs')
    if not completed or not bitstream.is_file() or errors:
        result['issues'].append('Build completion/bitstream not verified')
        return result
    result['bitstream_sha256'] = sha(bitstream)
    # Validate declared source, netlist, SDC and pin identity, independent of
    # any previously written PASS flag. Never trust a stale qualification.
    manifest_path = build / 'sources.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    if not manifest:
        result['issues'].append('Missing source hashes')
    for rel, digest in manifest.items():
        source = build / 'source' / rel
        if not source.is_file() or sha(source) != digest:
            result['issues'].append('Changed/missing source: ' + rel)
    sdc = Path(field(text, '<Timing Constraints File>') or '')
    cst = Path(field(text, '<Physical Constraints File>') or '')
    net = Path(field(text, '<Design File>') or '')
    if not all(p.is_file() and p.is_relative_to(build) for p in (sdc, cst, net)):
        result['issues'].append('Unverified or external netlist/constraints')
    else:
        expected = {' '.join(line.split()) for line in sdc.read_text().splitlines()
                    if line.startswith(('create_', 'set_', 'report_timing '))}
        if expected != {c['command'] for c in result['constraints']}:
            result['issues'].append('Frozen SDC and active report constraints differ')
        result['netlist_sha256'] = sha(net)
        result['cst_path'] = str(cst)
        result['sdc_sha256'] = sha(sdc)
        result['cst_sha256'] = sha(cst)
        fixed = '\n'.join(fixed_constraints(cst.read_text()))
        identity = dict(part=result['part'], tool=result['tool_version'], net=sha(net), sdc=sha(sdc),
                        pins=hashlib.sha256(fixed.encode()).hexdigest())
        result['comparison_identity'] = identity
        result['comparison_group'] = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:16]
    result['options'] = {}
    script = build / 'build.tcl'
    if script.exists():
        for key, value in re.findall(r'^set_option -(place_option|route_option|replicate_resources) (\d+)$', script.read_text(), re.M):
            result['options'][key] = int(value)
    if errors:
        result['status'] = 'BUILD_FAILED'
    elif result['issues'] or not result['complete']:
        result['status'] = 'UNVERIFIED'
    else:
        result['status'] = 'TIMING_PASS' if result['timing_clean'] else 'TIMING_FAIL'
    result['qualification'] = 'NOT_CHECKED'
    result['qualification_issues'] = []
    for name in ('qualification.json', 'physical_qualification.json'):
        path = build / name
        if path.exists():
            qualified = json.loads(path.read_text())
            current = (qualified.get('timing_sha256') == result['report_sha256'] and
                       qualified.get('bitstream_sha256') == result['bitstream_sha256'])
            owner = qualified.get('synthesis_audits', {}).get('gpu_owner_replication')
            if owner is not None:
                routed = report.with_suffix('.vo')
                current = current and routed.is_file() and sha(routed) == owner.get('netlist_sha256')
            result['qualification'] = qualified.get('status', 'UNKNOWN') if current else 'STALE'
            result['qualification_issues'] = []
            if current:
                for audit, details in qualified.get('synthesis_audits', {}).items():
                    if details.get('passed') is False:
                        result['qualification_issues'].extend(
                            f'{audit}: {error}' for error in details.get('errors', ['Audit failed']))
                        # Even an inconsistent persisted PASS cannot conceal
                        # a functional audit failure beside clean timing.
                        result['qualification'] = 'FAIL'
    return result


def fixed_constraints(text):
    # Compare statements, not lines: an INS_LOC followed by an IO_LOC on
    # the same line must not conceal a pin change from the isolation gate.
    clean = '\n'.join(raw.split('//', 1)[0] for raw in text.splitlines())
    statements = [' '.join(part.split()) for part in clean.split(';')]
    return [s for s in statements if s and not s.startswith('INS_LOC ')]


def rank_key(result):
    # Within identical netlist/clock/pin groups only. Never reward missing data.
    if result.get('backend') == 'nextpnr':
        phase = {'COMPILED':0,'TIMING_FAILED':1,'PACK_FAILED':2,'PNR_FAILED':3,'UNVERIFIED':4}
        clocks = result.get('fmax', {})
        ratio = min((v['achieved']/v['constraint'] for v in clocks.values() if v['constraint'] > 0), default=0)
        return (phase.get(result['status'],5), -ratio)
    status = {'TIMING_PASS': 0, 'TIMING_FAIL': 1, 'UNVERIFIED': 2, 'BUILD_FAILED': 3, 'INCOMPLETE': 4}
    return (status.get(result['status'], 5), -(result.get('wns_ns') or 0),
            -(result.get('tns_ns') or 0), sum(result.get('violated_endpoints', {}).values()))


def comparison(builds):
    results = []
    for build in builds:
        path = Path(build)
        if (path/'result.json').exists() and json.loads((path/'result.json').read_text()).get('backend') == 'nextpnr':
            results.extend(inspect_open(path))
        else:
            results.append(inspect_build(path))
    groups = {}
    for result in results:
        key = result.get('comparison_group', 'unverified:' + result['name'])
        groups.setdefault(key, []).append(result['name'])
    return dict(schema=1, builds=sorted(results, key=lambda r:(r.get('comparison_group', '~'), rank_key(r))),
                comparison_groups=groups,
                scope='Gowin reported paths only; TIMING_PASS is not board/CDC/functional qualification')


def inspect_open(build):
    build = Path(build).resolve(strict=True)
    result = json.loads((build/'result.json').read_text())
    project = result['project']
    records = []
    for candidate in result['candidates']:
        stage = build/f"seed_{candidate['seed']}"
        timing = candidate.get('timing', {})
        clocks = timing.get('fmax', {})
        identity = dict(net=result['netlist_sha256'], cst=result['inputs']['pins.cst']['sha256'],
                        sdc=result['inputs'].get('timing.sdc'), part=project['device'], family=project['family'],
                        mhz=project['frequency_mhz'], toolchain=result['toolchain']['sha256'],
                        packer=result.get('legacy_packer', 'bundled'))
        group = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:16]
        item = dict(name=build.name+'/'+stage.name, backend='nextpnr', directory=str(stage),
                    status=candidate['status'], qualification='COMPILE_ONLY', part=project['device'],
                    comparison_group='open:'+group, netlist_sha256=result['netlist_sha256'],
                    clocks_mhz={c:v['constraint'] for c,v in clocks.items()}, fmax=clocks,
                    resources=timing.get('utilization', {}), options=dict(seed=candidate['seed'], **result['strategies']),
                    wns_ns=None, tns_ns=None, violated_endpoints={}, paths=[], placements=[], issues=[])
        # Keep nextpnr's coordinates explicitly separate from Gowin R/C sites.
        for path in timing.get('critical_paths', []):
            arcs = []
            for arc in path['path']:
                target = arc['to']
                arcs.append(dict(cell=target['cell'], node=target['cell']+'/'+target['port'],
                                 kind=arc['type'], delay_ns=arc['delay'], fanout=None,
                                 col=target['loc'][0], row=target['loc'][1], loc=str(target['loc'])))
            if arcs:
                item['paths'].append(dict(source=arcs[0]['cell'], destination=arcs[-1]['cell'],
                                          clock=path['to'], analysis='nextpnr setup', slack_ns=None, arcs=arcs,
                                          route_ns=sum(a['delay_ns'] for a in arcs if a['kind']=='routing'),
                                          cell_ns=sum(a['delay_ns'] for a in arcs if a['kind']!='routing')))
        routed = stage/'routed.json'
        if routed.exists():
            cells = json.loads(routed.read_text())['modules'][project['top']]['cells']
            for name, cell in cells.items():
                bel = cell.get('attributes', {}).get('NEXTPNR_BEL', '')
                match = re.fullmatch(r'X(\d+)Y(\d+)/(.+)', bel)
                if match:
                    item['placements'].append(dict(cell=name, col=int(match[1]), row=int(match[2]), type=cell['type']))
        bitstream = stage/'design.fs'
        if item['status'] == 'COMPILED' and (not bitstream.exists() or sha(bitstream) != candidate.get('bitstream_sha256')):
            item.update(status='UNVERIFIED', issues=['Bitstream absent or changed'])
        if not (build/'netlist.json').exists() or sha(build/'netlist.json') != result['netlist_sha256']:
            item.update(status='UNVERIFIED')
            item['issues'].append('Synthesis netlist absent or changed')
        for name, meta in result['inputs'].items():
            if not (build/'source'/name).exists() or sha(build/'source'/name) != meta['sha256']:
                item.update(status='UNVERIFIED')
                item['issues'].append('Frozen source absent or changed: '+name)
        for name, digest in candidate.get('output_sha256', {}).items():
            if not (stage/name).exists() or sha(stage/name) != digest:
                item.update(status='UNVERIFIED')
                item['issues'].append('Generated output absent or changed: '+name)
        records.append(item)
    return records
