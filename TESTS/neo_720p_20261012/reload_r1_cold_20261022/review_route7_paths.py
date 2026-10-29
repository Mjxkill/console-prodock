#!/usr/bin/env python3
"""Read completed Neo routes and preserve a path-level comparison.

No synthesis, routing, process control, hardware, or writes in build folders.
Refuses partial timing reports; does not promote a diagnostic to qualified.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def section(text, number):
    found = re.search(r'^3\.3\.' + re.escape(number) + r' [^\n]+\n', text, re.M)
    if not found:
        raise ValueError('Missing analysis section ' + number)
    end = re.search(r'^3\.\d+(?:\.\d+)* [A-Za-z]', text[found.end():], re.M)
    # Main setup/hold sections end at the next main section. HDMI requests
    # use their explicit recovery/removal subsection and end at the next one.
    if number in ('1', '2'):
        end = re.search(r'^3\.3\.[234] ', text[found.end():], re.M)
    return text[found.end():found.end()+end.start()] if end else text[found.end():]


def paths(text):
    result = []
    for block in text.split('Path Summary:')[1:]:
        def field(name):
            m = re.search(r'^' + re.escape(name) + r'\s*:\s*(.+)$', block, re.M)
            return m[1].strip() if m else None
        if field('Slack') is None:
            continue
        arrival = block.split('Data Arrival Path:', 1)[1].split('Data Required Path:', 1)[0]
        rows = []
        data = False
        for line in arrival.splitlines():
            m = re.match(r'\s*([-\d.]+)\s+([-\d.]+)\s+(t\w+)\s+(\w+)\s+(\d+)\s+(\S+)\s+(\S+)\s*$', line)
            if not m:
                continue
            if m[3] == 'tC2Q' or m[3] == 'tCO':
                data = True
            if data:
                rows.append(dict(arrival_ns=float(m[1]), delay_ns=float(m[2]), kind=m[3],
                                 fanout=int(m[5]), location=m[6], node=m[7]))
        breakdown = re.search(r'Arrival Data Path Delay: \(cell:\s*([-\d.]+).*?route:\s*([-\d.]+).*?tC2Q:\s*([-\d.]+)', block, re.S)
        result.append(dict(slack_ns=float(field('Slack')), source=field('From'), destination=field('To'),
                           launch_clock=field('Launch Clk'), latch_clock=field('Latch Clk'),
                           arrival_ns=float(field('Data Arrival Time')), required_ns=float(field('Data Required Time')),
                           data_rows=rows,
                           route_ns=float(breakdown[2]) if breakdown else None,
                           cell_ns=float(breakdown[1]) if breakdown else None,
                           clock_to_q_ns=float(breakdown[3]) if breakdown else None,
                           longest_routes=sorted((r for r in rows if r['kind']=='tNET'), key=lambda r:r['delay_ns'], reverse=True)[:3]))
    return result


def read(build):
    log = (build/'build.log').read_text()
    report = build/'impl/pnr/console_neo.tr'
    if 'Bitstream generation completed' not in log or f'Generate file "{report}" completed' not in log:
        raise ValueError(f'Build incomplete: {build.name}; no result inferred')
    q = json.loads((build/'qualification.json').read_text())
    assert q['timing_sha256'] == sha(report)
    assert q['bitstream_sha256'] == sha(build/'impl/pnr/console_neo.fs')
    text = report.read_text()
    setup = paths(section(text,'1'))
    hdmi = {kind: paths(section(text, number)) for kind,number in [('recovery','3.2'),('removal','4.2')]}
    for kind, values in hdmi.items():
        hdmi[kind] = [p for p in values if re.fullmatch(r'u_hdmi/g_ser\[[012]\]\.u_ser',p['destination'])]
        assert {re.search(r'\[(\d)\]',p['destination'])[1] for p in hdmi[kind]} == {'0','1','2'}
    channels = []
    for channel in range(3):
        dest=f'u_hdmi/g_ser[{channel}].u_ser'
        record={'channel':channel}
        for kind in hdmi:
            values=[p for p in hdmi[kind] if p['destination']==dest]
            worst=min(values,key=lambda p:p['slack_ns'])
            record[kind]=worst
        channels.append(record)
    unique = {}
    for p in sorted(setup,key=lambda p:p['slack_ns']):
        key=(p['source'],p['destination'])
        if p['slack_ns']<0 and key not in unique:
            unique[key]=p
    used = ['qualification.json','automatic_checks.json','build.log','route.json','sources.json',
            'console_neo.vg','source/tang/boards/neo/neo.cst','source/tang/boards/neo/neo.sdc',
            'impl/pnr/console_neo.tr','impl/pnr/console_neo.fs']
    return dict(build=str(build),status=q['status'],timing_checks_ns=q['timing_checks_ns'],
                violated_endpoints=q['violated_endpoints'],groups=q['groups'],
                worst_setup=list(unique.values())[:20],hdmi_channels=channels,
                automatic_checks=json.loads((build/'automatic_checks.json').read_text()) if (build/'automatic_checks.json').exists() else None,
                identities={p:sha(build/p) for p in used if (build/p).exists()})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',type=Path,action='append',required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    assert not args.out.exists(), 'Preserve previous evidence'
    builds=[read(p.resolve()) for p in args.build]
    result=dict(hardware_access=False,process_control=False,read_only_builds=True,
                script_sha256=sha(Path(__file__)),builds=builds,
                limits='STA report comparison only. No equivalence, hardware, or physical reset release qualification.')
    args.out.mkdir(parents=True)
    (args.out/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    for b in builds:
        print(Path(b['build']).name,b['status'],b['timing_checks_ns'])
        for c in b['hdmi_channels']:
            print('  HDMI',c['channel'],'recovery',c['recovery']['slack_ns'],'removal',c['removal']['slack_ns'])
        for p in b['worst_setup'][:3]:
            print('  setup',p['slack_ns'],p['source'],'->',p['destination'],'route',p['route_ns'])


if __name__=='__main__':
    main()
