#!/usr/bin/env python3
"""Read-only clock evidence: frozen netlist connections versus published routes.

No proprietary PR decoding or compiler call. An absent report means UNKNOWN,
never zero routing resources. Logical connectivity is not physical routing.
"""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'optimizer'))
from reports import clock_routing

HERE = Path(__file__).resolve().parent
NAMES = ('clk_d', 'ae350_tck_d', 'rtc_clk')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def logic(text):
    """Follow exact module-port nets to leaves; do not guess aliases/arcs."""
    bodies = dict(re.findall(r'^module (\w+)\b(.*?)^endmodule', text, re.M | re.S))
    assert 'console_top' in bodies
    cache = {}

    def cells(module):
        if module not in cache:
            cache[module] = [(kind, name.strip().removeprefix('\\'),
                             {k:v.strip() for k,v in re.findall(r'\.(\w+)\(([^()]*)\)', body)})
                for kind, name, body in re.findall(
                    r'^\s*(\w+)\s+(\\\S+\s|\S+)\s*\((.*?)\);',
                    bodies[module], re.M | re.S)]
        return cache[module]

    def visit(module, net, path, stack):
        assert module not in stack
        result = []
        for kind, name, ports in cells(module):
            for port, value in ports.items():
                if value != net:
                    continue
                target = path + name
                if kind in bodies:
                    result += visit(kind, port, target+'/', stack+(module,))
                else:
                    result.append(dict(instance=target, primitive=kind, port=port))
        return result

    return {net:sorted(visit('console_top', net, '', ()),
                       key=lambda x:(x['instance'],x['port'])) for net in NAMES}


def collect(stage, stem):
    base = ROOT / 'tang/impl' / stage
    net = base/'impl/gwsynthesis'/(stem+'.vg')
    cst = base/'constraints_resolved.cst'
    sdc = base/'source/diagnostics/timing_reports.sdc'
    log = base/'build.log'
    report = base/'impl/pnr'/(stem+'.rpt.txt')
    pr = base/'impl/pnr'/(stem+'.pr')
    paths = [net,cst,sdc,log,pr,base/'sources.json',base/'impl/pnr/cmd.do']
    if report.exists():
        paths.append(report)
    resources = clock_routing(report.read_text() if report.exists() else '', log.read_text())
    warnings = [line for line in log.read_text().splitlines() if '(PR1014)' in line]
    return dict(stage=stage, files={str(p.relative_to(ROOT)):dict(sha256=digest(p),
                size=p.stat().st_size) for p in paths},
                pr_decoded=False, route_report_state='PUBLISHED' if report.exists() else 'UNKNOWN',
                published_routes=resources, pr1014=warnings,
                connectivity=logic(net.read_text()),
                clock_constraints=[line for line in cst.read_text().splitlines()
                                   if line.startswith('CLOCK_LOC ')],
                clk_input=[line for line in cst.read_text().splitlines()
                           if line.startswith(('IO_LOC "clk"','IO_LOC "ae350_tck"'))])


def main():
    old = collect('gpu_geometry_g22r0','console_gpu_geometry_g22r0')
    new = collect('prodock_sd_boot_20261028_r2','console_prodock_sd_boot_20261028_r2')
    before = ROOT/'tang/impl'/old['stage']
    after = ROOT/'tang/impl'/new['stage']
    old_sources = json.loads((before/'sources.json').read_text())
    checked = []
    for relative, expected in old_sources.items():
        a, b = before/'source'/relative, after/'source'/relative
        assert digest(a) == expected, 'Protected reference differs: '+relative
        checked.append(dict(path=relative, same=digest(a)==digest(b)))
    same = lambda rel: digest(before/rel)==digest(after/rel)
    comparison = dict(pr1014_identical=old['pr1014']==new['pr1014'],
        clock_constraints_identical=old['clock_constraints']==new['clock_constraints'],
        cst_byte_identical=same('constraints_resolved.cst'),
        sdc_byte_identical=same('source/diagnostics/timing_reports.sdc'),
        direct_hierarchical_clock_connectivity_identical=old['connectivity']==new['connectivity'],
        reference_sources_checked=len(checked),
        reference_sources_changed=[x['path'] for x in checked if not x['same']],
        physical_clock_route_comparison='UNKNOWN: R2 reports absent and PR not decoded',
        physical_route_equivalence_claimed=False,
        hardware_validation_claimed=False)
    record = dict(schema=1, status='OFFLINE_EVIDENCE_ONLY', reference=old,
                  candidate=new, comparison=comparison,
                  tools={'audit.py':digest(Path(__file__)),
                         'optimizer/reports.py':digest(ROOT/'optimizer/reports.py')})
    (HERE/'result.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(comparison,indent=2))
    for name, entries in new['connectivity'].items():
        print(name, 'observed_leaf_connections', len(entries))


if __name__ == '__main__':
    main()
