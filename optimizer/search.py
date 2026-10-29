"""Prepare a bounded regional-placement search from measured critical paths."""
import math
from pathlib import Path
import re

from gowinflow import make_plan
from placement import propose, propose_grouped
from reports import inspect_build
from runtime import save


def prepare(parent, out, prefix, trials=3, paths=2, split_paths=False):
    if trials not in (1, 2, 3) or not re.fullmatch(r'[A-Za-z0-9_]+', prefix):
        raise ValueError('Choose 1..3 trials and a plain build-name prefix')
    analysis = inspect_build(parent)
    if analysis['status'] != 'TIMING_FAIL':
        raise ValueError('Search requires a complete failing timing report')
    selected = [p for p in analysis['paths'] if p['analysis']=='setup' and p['slack_ns'] < 0][:paths]
    points = [a for p in selected for a in p['arcs'] if a['row'] is not None and a['col'] is not None
              and not a['cell'].startswith(('u_soc/', 'u_usb_'))]
    if not points:
        raise ValueError('No eligible measured setup path for a regional search')
    rows = [p['row'] for p in points]
    cols = [p['col'] for p in points]
    center_row, center_col = (min(rows)+max(rows))/2, (min(cols)+max(cols))/2
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    experiments, regions = [], []
    for index, factor in enumerate((0.75, 1.0, 0.5)[:trials]):
        if split_paths:
            cst = out/f'region_{index}.cst'
            candidate = propose_grouped(parent, analysis['cst_path'], cst, factor, paths)
            region = [group['region'] for group in candidate['regions']]
            if region in regions:
                continue
            regions.append(region)
            experiments.append(dict(name=f'{prefix}_{index}',place=3,route=2,replicate=1,cst=str(cst)))
            continue
        # A measured bounding box and two contractions, not a claim about
        # physical congestion. Gowin evaluates each complete candidate.
        dr = max(2, math.ceil((max(rows)-min(rows))*factor/2))
        dc = max(2, math.ceil((max(cols)-min(cols))*factor/2))
        region = f'R[{max(1,math.floor(center_row-dr))}:{math.ceil(center_row+dr)}]C[{max(1,math.floor(center_col-dc))}:{math.ceil(center_col+dc)}]'
        if region in regions:
            continue
        cst = out/f'region_{index}.cst'
        propose(parent, analysis['cst_path'], cst, region, paths)
        regions.append(region)
        experiments.append(dict(name=f'{prefix}_{index}',place=3,route=2,replicate=1,cst=str(cst)))
    plan = make_plan(parent, out/'plan.json', experiments)
    save(out/'search.json', dict(method=('independent connected path groups' if split_paths else
                                        'measured setup-path bounding box + contractions'),
                                 regions=regions, source_wns_ns=analysis['wns_ns'],
                                 source_tns_ns=analysis['tns_ns'],
                                 no_clock_or_pin_changes=True, trials=len(experiments)))
    return plan
