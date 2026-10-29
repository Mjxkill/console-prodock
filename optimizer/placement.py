"""Generate explicit, reviewable placement candidates from measured paths."""
import re
import math
from pathlib import Path

from reports import LOC, fixed_constraints, inspect_build
from runtime import save, sha


def anchored_cells(cst):
    clean='\n'.join(line.split('//',1)[0] for line in cst.splitlines())
    return set(re.findall(r'(?:^|;)\s*INS_LOC\s+"([^"]+)"',clean))


def route_created_cell(name):
    # These replicas exist in the routed report but not when Gowin parses
    # the next run's CST against the synthesis netlist (CT1135 in N33p_0).
    # Do not guess a source register name or anchor a future replica.
    return name.rsplit('/', 1)[-1].startswith('gowin_replicate_reg_')


def skipped_replicas(paths):
    return sorted({arc['cell'] for path in paths for arc in path['arcs']
                   if route_created_cell(arc['cell'])})


def path_groups(paths):
    """Connected sets of eligible cells, never a single box across disjoint paths."""
    groups = []
    for index, path in enumerate(paths):
        if path['analysis'] != 'setup' or path['slack_ns'] >= 0:
            continue
        if path.get('launch_clock') != path.get('clock'):
            raise ValueError('Review clock crossings before automatic regional placement')
        cells = {arc['cell']: arc for arc in path['arcs']
                 if LOC.fullmatch(arc['loc'])
                 and not route_created_cell(arc['cell'])
                 and not arc['cell'].startswith(('u_usb_', 'u_soc/'))}
        if not cells:
            continue
        group = dict(paths=[index], cells=cells)
        # A later path may bridge two older groups: merge all intersections.
        separate = []
        for previous in groups:
            if previous['cells'].keys() & cells.keys():
                group['paths'].extend(previous['paths'])
                group['cells'].update(previous['cells'])
            else:
                separate.append(previous)
        groups = separate + [group]
    return sorted(groups, key=lambda group: min(group['paths']))


def propose_grouped(build, base_cst, output, factor=.75, max_paths=2):
    """Propose an independent bounding region for each connected path group."""
    if not 0 < factor <= 1 or not 1 <= max_paths <= 20:
        raise ValueError('Invalid contraction or path count')
    result = inspect_build(build)
    if result['status'] not in ('TIMING_FAIL', 'TIMING_PASS'):
        raise ValueError('Only complete, verified reports can generate placement candidates')
    base_cst = Path(base_cst).resolve(strict=True)
    if sha(base_cst) != result['cst_sha256']:
        raise ValueError('Base CST must be the exact frozen constraint file used by this report')
    base = base_cst.read_text()
    existing = anchored_cells(base)
    cells, regions = {}, []
    for group in path_groups(result['paths'][:max_paths]):
        rows = [a['row'] for a in group['cells'].values()]
        cols = [a['col'] for a in group['cells'].values()]
        cr, cc = (min(rows)+max(rows))/2, (min(cols)+max(cols))/2
        dr, dc = max(2, math.ceil((max(rows)-min(rows))*factor/2)), max(2, math.ceil((max(cols)-min(cols))*factor/2))
        r0, r1 = max(1, math.floor(cr-dr)), math.ceil(cr+dr)
        c0, c1 = max(1, math.floor(cc-dc)), math.ceil(cc+dc)
        region = f'R[{r0}:{r1}]C[{c0}:{c1}]'
        movable = {name: arc for name, arc in group['cells'].items() if name not in existing}
        if not movable:
            continue
        if len(movable) > (r1-r0+1)*(c1-c0+1)*8:
            raise ValueError('Region lacks even nominal cell capacity')
        for name, arc in movable.items():
            if not re.fullmatch(r'[A-Za-z0-9_./\[\]$-]+', name):
                raise ValueError('Unsupported instance name: '+name)
            cells[name] = dict(previous=arc['loc'], region=region)
        regions.append(dict(region=region, paths=sorted(group['paths']), cells=sorted(movable)))
    if not cells:
        raise ValueError('No eligible unconstrained LUT/DFF cells on negative setup paths')
    content = base.rstrip()+'\n\n// Independent path groups; full routing and qualification required.\n'
    content += ''.join(f'INS_LOC "{name}" {item["region"]};\n' for name, item in sorted(cells.items()))
    if fixed_constraints(content) != fixed_constraints(base):
        raise AssertionError('Pin/bank/non-placement constraints changed')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        stream.write(content)
    record = dict(status='PROPOSED', build=str(Path(build).resolve()), report_sha256=result['report_sha256'],
                  netlist_sha256=result['netlist_sha256'], base_cst_sha256=sha(base_cst),
                  candidate_cst_sha256=sha(output), regions=regions, cells=cells,
                  skipped_route_created_cells=skipped_replicas(result['paths'][:max_paths]),
                  limits='Independent measured path groups; no congestion model. Full Gowin routing required.')
    save(output.with_suffix('.json'), record)
    return record


def propose(build, base_cst, output, region, max_paths=2):
    match = re.fullmatch(r'R\[(\d+):(\d+)\]C\[(\d+):(\d+)\]', region)
    if not match:
        raise ValueError('Expected region R[first:last]C[first:last]')
    r0, r1, c0, c1 = map(int, match.groups())
    if not (1 <= r0 <= r1 <= 999 and 1 <= c0 <= c1 <= 999 and 1 <= max_paths <= 20):
        raise ValueError('Invalid region or path count')
    result = inspect_build(build)
    if result['status'] not in ('TIMING_FAIL', 'TIMING_PASS'):
        raise ValueError('Only complete, verified reports can generate placement candidates')
    base_cst = Path(base_cst).resolve(strict=True)
    if sha(base_cst) != result['cst_sha256']:
        raise ValueError('Base CST must be the exact frozen constraint file used by this report')
    base = base_cst.read_text()
    existing = anchored_cells(base)
    cells = {}
    for path in result['paths'][:max_paths]:
        if path['analysis'] != 'setup' or path['slack_ns'] >= 0:
            continue
        for arc in path['arcs']:
            name = arc['cell']
            # Exact LUT/DFF sites only: no DSP/BSRAM/I/O/PLL relocation, no
            # encrypted IP internals, no wildcards, no existing anchor changes.
            if not LOC.fullmatch(arc['loc']) or name in existing or route_created_cell(name):
                continue
            if name.startswith(('u_usb_', 'u_soc/')):
                continue
            if not re.fullmatch(r'[A-Za-z0-9_./\[\]$-]+', name):
                raise ValueError('Unsupported instance name: ' + name)
            cells.setdefault(name, dict(previous=arc['loc'], region=region))
    if not cells:
        raise ValueError('No eligible unconstrained LUT/DFF cells on negative setup paths')
    if len(cells) > (r1 - r0 + 1) * (c1 - c0 + 1) * 8:
        raise ValueError('Region lacks even nominal cell capacity')
    content = base.rstrip() + '\n\n// Experimental placement; full routing and qualification required.\n'
    content += ''.join(f'INS_LOC "{name}" {region};\n' for name in sorted(cells))
    if fixed_constraints(content) != fixed_constraints(base):
        raise AssertionError('Pin/bank/non-placement constraints changed')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        stream.write(content)
    record = dict(status='PROPOSED', build=str(Path(build).resolve()), report_sha256=result['report_sha256'],
                  netlist_sha256=result['netlist_sha256'], base_cst_sha256=sha(base_cst),
                  candidate_cst_sha256=sha(output), region=region, cells=cells,
                  skipped_route_created_cells=skipped_replicas(result['paths'][:max_paths]),
                  limits='Estimated region capacity only; Gowin must verify legality and whole-design timing')
    save(output.with_suffix('.json'), record)
    return record
