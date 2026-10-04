#!/usr/bin/env python3
"""Prepare/inspect an isolated, hypothetical 60/120 MHz USB timing sweep.

The eight sclk clocks are alternatives, not eight physical clocks. No source,
production constraint or vendor netlist is changed. Configuration identity is
required before associating the measured routing with the reference bitstream.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

from check_usb_phy_cdc_timing import MODEL, expected_paths

ROOT = Path(__file__).resolve().parents[1]
PHY = 'u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(a):
    a.stage.mkdir(parents=True, exist_ok=False)
    for name in ('source.vg', 'source.cst'):
        shutil.copy2(a.reference_audit / name, a.stage / name)
    base = a.reference_stage / 'source/tang/constr/gpu.sdc'
    original = base.read_text()
    lines = []
    for line in original.splitlines():
        if line.startswith('create_clock -name sclk ') or line.startswith('set_clock_groups '):
            continue
        lines.append(line)
        if line.startswith('create_generated_clock -name fclk_960M '):
            for phase in range(8):
                lines.append(f'create_generated_clock -name sclk_p{phase} '
                             '-source [get_pins {u_pll_b/PLL_inst/CLKOUT0}] '
                             f'-master_clock fclk_960M -divide_by 8 -phase {45*phase} '
                             f'[get_pins {{{PHY}/clkdiv_inst/CLKOUT}}] -add')
    lines += ['// DIAGNOSTIC ONLY: eight alternative phases; never load this image.',
              '// No Gray exception added. All asynchronous groups removed in this copy.',
              '// Classify Gray and non-Gray paths after reporting setup and hold.']
    for mode in ('setup', 'hold'):
        for phase in range(8):
            for source, target in [('PHY_CLKOUT', f'sclk_p{phase}'), (f'sclk_p{phase}', 'PHY_CLKOUT')]:
                lines.append(f'report_timing -{mode} -from_clock [get_clocks {{{source}}}] '
                             f'-to_clock [get_clocks {{{target}}}] -max_paths 20000 -max_common_paths 20')
    # Explicit requests ensure Gray paths remain visible even when common-path
    # pruning in the broad clock-pair reports selects a different endpoint.
    gray = expected_paths(MODEL)
    for (source_pin, target_pin), info in gray.items():
        if not ('_rq1_' in info['group'] or '_wq1_' in info['group']):
            continue
        sclk_source = info['group'] in ('rx_rq1_wptr', 'tx_wq1_rptr')
        for phase in range(8):
            source, target = ((f'sclk_p{phase}', 'PHY_CLKOUT') if sclk_source else
                              ('PHY_CLKOUT', f'sclk_p{phase}'))
            for mode in ('setup', 'hold'):
                lines.append(f'report_timing -{mode} -from_clock [get_clocks {{{source}}}] '
                             f'-to_clock [get_clocks {{{target}}}] '
                             f'-from [get_pins {{{source_pin}}}] -to [get_pins {{{target_pin}}}] '
                             '-max_paths 1 -max_common_paths 1')
    (a.stage / 'diagnostic.sdc').write_text('\n'.join(lines) + '\n')
    (a.stage / 'audit.tcl').write_text((a.reference_audit / 'audit.tcl').read_text())
    manifest = dict(reference_stage=str(a.reference_stage.resolve()),
                    reference_audit=str(a.reference_audit.resolve()),
                    source_sdc=str(base.resolve()), source_sdc_sha256=sha(base),
                    production_sdc_sha256=sha(ROOT / 'tang/constr/gpu.sdc'),
                    phase_step_ns=1000/960, phase_count=8,
                    guide='Gowin SUG940-2.0.1E section 5.2.2 / 5.5.1',
                    sha256={name: sha(a.stage / name) for name in
                            ('source.vg', 'source.cst', 'diagnostic.sdc', 'audit.tcl')})
    (a.stage / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(a.stage)


def inspect(a):
    gray = expected_paths(MODEL)
    reference_pairs = set()
    if a.reference_pairs:
        reference_pairs = {(p['from'],p['to']) for p in
                           json.loads(a.reference_pairs.read_text())['reported_non_pointer_paths']}
    gray_crossing_pairs = {key for key, info in gray.items()
                           if '_rq1_' in info['group'] or '_wq1_' in info['group']}
    records, mode, command = [], None, None
    with a.report.open() as stream:
        for line in stream:
            if line.startswith('3.2 '):
                break
            match = re.match(r'3\.1\.\d+ (Setup|Hold|Recovery|Removal)', line)
            if match:
                mode = match[1].lower()
            if line.startswith('<Report Command>:'):
                command = line.strip().split(':', 1)[1]
            fields = line.split()
            if mode not in ('setup', 'hold') or len(fields) != 9 or not fields[0].isdigit():
                continue
            phase_match = re.search(r'sclk_p([0-7]):', fields[4]+' '+fields[5])
            if not phase_match or 'PHY_CLKOUT:' not in fields[4]+' '+fields[5]:
                continue
            key = tuple(fields[2:4])
            records.append(dict(phase=int(phase_match[1]), mode=mode,
                                classification='gray' if key in gray else 'non_gray',
                                slack_ns=float(fields[1]), source=fields[2], target=fields[3],
                                launch_clock=fields[4], capture_clock=fields[5],
                                relation_ns=float(fields[6]), skew_ns=float(fields[7]),
                                data_delay_ns=float(fields[8]), command=command,
                                path_number=int(fields[0])))
    groups = []
    for phase in range(8):
        group = dict(phase=phase, degrees=phase*45, offset_ns=phase*1000/960)
        for kind in ('gray', 'non_gray'):
            group[kind] = {}
            for mode in ('setup', 'hold'):
                found = [r for r in records if r['phase']==phase and r['classification']==kind and r['mode']==mode]
                unique = {(r['source'],r['target'],r['launch_clock'],r['capture_clock']): r for r in found}
                group[kind][mode] = dict(reported_paths=len(found), distinct_endpoint_pairs=len(unique),
                                        min_slack_ns=min((r['slack_ns'] for r in found),default=None),
                                        violations=sum(r['slack_ns']<0 for r in found),
                                        worst=sorted(found,key=lambda r:r['slack_ns'])[:10])
                pairs = {(r['source'],r['target']) for r in found}
                expected = gray_crossing_pairs if kind=='gray' else reference_pairs
                group[kind][mode]['coverage'] = dict(
                    expected_pairs=len(expected),exact_pairs_found=len(pairs & expected),
                    missing_pairs=[dict(source=s,target=t) for s,t in sorted(expected-pairs)],
                    expected_destination_pins=len({t for s,t in expected}),
                    destination_pins_found=len({t for s,t in expected} & {t for s,t in pairs}))
        group['non_gray_setup_hold_nonnegative'] = all(
            group['non_gray'][m]['min_slack_ns'] is not None and group['non_gray'][m]['min_slack_ns'] >= 0
            for m in ('setup','hold'))
        groups.append(group)
    refhash, audithash = sha(a.reference_bin), sha(a.audit_bin)
    report_text = a.report.read_text()
    clock_summary = report_text.split('2.2 Clock Summary',1)[1].split('2.3 Max Frequency Summary',1)[0].strip()
    manifest_path = a.report.parents[2] / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['production_sdc_current_sha256'] = sha(ROOT / 'tang/constr/gpu.sdc')
    manifest['production_sdc_unchanged'] = manifest['production_sdc_current_sha256']==manifest['production_sdc_sha256']
    result = dict(report=str(a.report.resolve()), report_sha256=sha(a.report),
                  diagnostic_manifest=manifest,clock_summary=clock_summary,
                  reference_pairs_report=str(a.reference_pairs) if a.reference_pairs else None,
                  configuration=dict(reference=str(a.reference_bin.resolve()),audit=str(a.audit_bin.resolve()),
                                     reference_sha256=refhash,audit_sha256=audithash,identical=refhash==audithash),
                  phases=groups,paths=records,
                  saturated_broad_report=any(r['path_number']>=20000 for r in records),
                  limits=['Phases alternatives hypothétiques ; relation réelle au reset non établie.',
                          'Aucune fausse voie Gray ajoutée ; leur marge synchrone ne qualifie pas leur CDC.',
                          'Setup/hold des chemins rapportés, sans preuve de métastabilité ou reset.',
                          'Rapports limités à 20000 chemins et 20 chemins communs ; le tri peut omettre certaines sources vers une destination couverte.',
                          'Les huit valeurs sont des points discrets, pas une fenêtre continue démontrée.',
                          'Le séquenceur coupe HCLK, libère RESETN puis reprend HCLK : la phase réelle ne découle pas du seul paramètre PLL.',
                          'La configuration binaire doit être identique avant attribution au routage de référence.'])
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('Configuration identical:', refhash==audithash)
    for g in groups:
        print(g['phase'], g['non_gray']['setup']['min_slack_ns'],g['non_gray']['hold']['min_slack_ns'])
    return 0 if refhash==audithash and len(records)>0 else 1


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    prep=sub.add_parser('prepare')
    prep.add_argument('--stage',type=Path,required=True)
    prep.add_argument('--reference-audit',type=Path,default=ROOT/'tang/impl/gpu_usb_cdc_audit_r29_1')
    prep.add_argument('--reference-stage',type=Path,default=ROOT/'tang/impl/gpu_l12_diag_r29')
    view=sub.add_parser('inspect')
    view.add_argument('report',type=Path)
    view.add_argument('--reference-bin',type=Path,required=True)
    view.add_argument('--audit-bin',type=Path,required=True)
    view.add_argument('--output',type=Path,required=True)
    view.add_argument('--reference-pairs',type=Path)
    a=p.parse_args()
    return prepare(a) if a.command=='prepare' else inspect(a)


if __name__=='__main__':
    raise SystemExit(main())
