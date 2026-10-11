#!/usr/bin/env python3
"""Summarize physical geometry timing; qualify only a complete, clean build."""
import argparse
import hashlib
import json
import re
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def family(node):
    return re.sub(r'_\d+_s\d*$', '', node.rsplit('/', 1)[0] if node.endswith(('/D', '/Q')) else node)


def inspect(stage):
    name = 'console_'+stage.name
    report = stage/f'impl/pnr/{name}.tr'
    text = report.read_text()
    groups = [dict(clock=c, analysis=a, tns=float(t), endpoints=int(n)) for c, a, t, n in
              re.findall(r'^\s*(\S+)\s+(setup|hold)\s+([-\d.]+)\s+(\d+)\s*$', text, re.M)]
    slacks = [float(s) for s in re.findall(r'^Slack\s*:\s*([-\d.]+)', text, re.M)]
    counts = {kind.lower(): int(value) for kind, value in
              re.findall(r'<Numbers of (Setup|Hold) Violated Endpoints>:(\d+)', text)}
    complete = bool(slacks and groups and set(counts) == {'setup', 'hold'})
    clean = complete and min(slacks) >= 0 and not any(counts.values()) and all(g['tns'] == 0 and g['endpoints'] == 0 for g in groups)
    paths = []
    for block in text.split('Path Summary:')[1:]:
        def field(label):
            found = re.search(r'^'+label+r'\s*:\s*(.*?)\s*$', block, re.M)
            return found.group(1) if found else None
        slack = field('Slack')
        if slack is not None and float(slack) < 0:
            paths.append(dict(slack_ns=float(slack), source=field('From'), destination=field('To'), clock=field('Latch Clk')))
    worst = {}
    for path in sorted(paths, key=lambda p:p['slack_ns']):
        key = (path['clock'], family(path['source']), family(path['destination']))
        if key not in worst:
            worst[key] = path
    resources = {}
    resource_text = (stage/f'impl/pnr/{name}.rpt.txt').read_text()
    for resource in ('Logic', 'Register', 'CLS', 'BSRAM', 'DSP'):
        found = re.search(r'^\s*'+resource+r'\s*\|\s*(\d+)/(\d+)', resource_text, re.M)
        if found:
            resources[resource] = dict(used=int(found[1]), available=int(found[2]))
    return dict(status='PASS' if clean else 'FAIL', stage=stage.name, timing_sha256=sha(report),
                minimum_slack_ns=min(slacks) if slacks else None, violated_endpoints=counts,
                groups=groups, worst_families=list(worst.values()), resources=resources)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--qualify', action='store_true', help='Write bitstream.sha256 only after all checks pass')
    args = parser.parse_args()
    stage = args.stage.resolve(strict=True)
    result = inspect(stage)
    print(json.dumps(result, indent=2))
    if args.qualify:
        if result['status'] != 'PASS':
            raise SystemExit('Timing gate failed; no bitstream qualification written')
        log = (stage/'build.log').read_text()
        if re.search(r'^ERROR', log, re.M) or 'Bitstream generation completed' not in log or 'Power analysis completed' not in log:
            raise SystemExit('Incomplete or failed build')
        manifest = json.loads((stage/'sources.json').read_text())
        for source, digest in manifest.items():
            if sha(stage/'source'/source) != digest:
                raise SystemExit('Changed frozen source: '+source)
        # readmemh resolves this font relative to the build directory. Check
        # its mirror as well as the canonical file in the source manifest.
        if sha(stage/'rtl/video/font8x16.hex') != sha(stage/'source/tang/rtl/video/font8x16.hex'):
            raise SystemExit('Changed runtime font mirror')
        netlist = stage/f'impl/gwsynthesis/console_{stage.name}.vg'
        metadata = json.loads((stage/'geometry_build.json').read_text())
        if metadata.get('synthesis_reused') and sha(netlist) != metadata['synthesis_reused']['sha256']:
            raise SystemExit('Changed reused synthesis netlist')
        result['build_inputs_sha256'] = {str(p.relative_to(stage)): sha(p) for p in
            [stage/name for name in ('build.tcl', 'constraints_resolved.cst',
             'geometry_build.json', 'sources.json', 'build_driver.py', 'rtl/video/font8x16.hex')]+[netlist]}
        bitstream = stage/f'impl/pnr/console_{stage.name}.fs'
        result['bitstream_sha256'] = sha(bitstream)
        (stage/'physical_qualification.json').write_text(json.dumps(result, indent=2)+'\n')
        (stage/'bitstream.sha256').write_text(result['bitstream_sha256']+'  '+bitstream.name+'\n')


if __name__ == '__main__':
    main()
