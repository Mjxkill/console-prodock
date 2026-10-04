#!/usr/bin/env python3
"""Extract an isolated USB PHY CEN timing audit without qualifying absent paths.

Reads only the audit inputs, official generated timing/VO outputs and logs.
Writes the requested JSON; never runs Gowin or modifies constraints/netlists.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def one_file(stage, pattern):
    paths = sorted(stage.glob(pattern))
    return paths[0] if len(paths) == 1 else None


def parse_summary(text):
    mode, command, paths = None, None, []
    # The heading also occurs in the table of contents; only a line beginning
    # "3.2 " terminates the actual summary region.
    for line in text.splitlines():
        if line.startswith('3.2 '):
            break
        found = re.match(r'3\.1\.\d+ (Setup|Hold|Recovery|Removal)', line)
        if found:
            mode = found[1].lower()
        if line.startswith('<Report Command>:'):
            command = line.split(':', 1)[1].strip()
        fields = line.split()
        if mode is None or len(fields) != 9 or not fields[0].isdigit():
            continue
        try:
            paths.append(dict(mode=mode, command=command, number=int(fields[0]),
                              slack_ns=float(fields[1]), source=fields[2],
                              target=fields[3], launch_clock=fields[4],
                              capture_clock=fields[5], relationship_ns=float(fields[6]),
                              skew_ns=float(fields[7]), data_delay_ns=float(fields[8])))
        except ValueError:
            continue
    return paths


def relevant_details(text):
    details = []
    for part in re.split(r'(?m)^\s*Path\d+\s*$', text):
        match = re.search(r'(?m)^From\s*:\s*(.+)\nTo\s*:\s*(.+)', part)
        if not match or not any(token in match[1] + match[2]
                               for token in ('reset_stop', 'reset_calib',
                                             'dhcen_inst', 'clkdiv_inst')):
            continue
        # A following report command belongs to the next block.
        block = part.split('<Report Command>:', 1)[0].strip()
        details.append(dict(source=match[1], target=match[2], text=block))
    return details


def normalize_net(value):
    return re.sub(r'\s+', '', value).lstrip('\\')


def inspect_official_vo(path):
    text = path.read_text(errors='replace')
    cells = []
    pattern = r'(?m)^\s*(DFF\w*|DHCE|DHCEN|CLKDIV)\s+(\\?[^\s(]+)\s*\(\s*\n(.*?)\n\s*\);'
    for match in re.finditer(pattern, text, re.S):
        name = match[2].lstrip('\\')
        if 'u_usb_softphy_top/' not in name:
            continue
        ports = {key: normalize_net(value)
                 for key, value in re.findall(r'\.(\w+)\(([^)]*)\)', match[3])}
        cells.append(dict(type=match[1], name=name, ports=ports))
    gates = [cell for cell in cells if cell['type'] in ('DHCE', 'DHCEN')]
    dividers = [cell for cell in cells if cell['type'] == 'CLKDIV']
    drivers = {cell['ports']['Q']: cell for cell in cells if 'Q' in cell['ports']}
    links = []
    for gate in gates:
        cen_net = gate['ports'].get('CEN', gate['ports'].get('CE'))
        driver = drivers.get(cen_net)
        links.append(dict(gate=gate, enable_driver=driver,
                          divider_loads=[cell for cell in dividers
                                         if cell['ports'].get('HCLKIN') ==
                                         gate['ports'].get('CLKOUT')]))
    relevant = [cell for cell in cells if cell['type'] in ('DHCE', 'DHCEN', 'CLKDIV')
                or 'reset_stop' in cell['name'] or 'reset_calib' in cell['name']]
    return dict(path=str(path), sha256=sha(path), cells=relevant, enable_links=links,
                limits='Official unmodified export; connectivity alone does not establish timing arcs.')


def classify(path):
    target = path['target']
    if '/dhcen_inst/CEN' in target:
        return 'cen'
    if '/clkdiv_inst/RESETN' in target:
        return 'calib_reset'
    if any(token in target for token in
           ('/dhcen_inst/CLKIN', '/clkdiv_inst/HCLKIN', '/reset_stop_s2/CLK')):
        return 'clock_route'
    if '/u_oser_rst/' in target or '/u_oser_rst/' in path['source']:
        return 'sequencer_other'
    return 'other'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    stage = args.stage.resolve(strict=True)
    manifest_path = stage / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    checks = []
    for group, relative in (('reference_source_hashes', False),
                            ('copied_hashes', True), ('diagnostic_hashes', True),
                            ('production_hashes', False)):
        for name, expected in manifest[group].items():
            path = stage / name if relative else Path(name)
            actual = sha(path) if path.exists() else None
            checks.append(dict(group=group, path=str(path), expected_sha256=expected,
                               current_sha256=actual, unchanged=actual == expected))
    report = one_file(stage, 'impl/pnr/*.tr')
    binary = one_file(stage, 'impl/pnr/*.bin')
    reference = stage / 'reference.bin'
    configuration = dict(reference=str(reference), reference_sha256=sha(reference),
                         audit=str(binary) if binary else None,
                         audit_sha256=sha(binary) if binary else None)
    configuration['identical'] = (configuration['reference_sha256'] ==
                                  configuration['audit_sha256']) if binary else None
    if binary:
        before, after = reference.read_bytes(), binary.read_bytes()
        configuration.update(reference_bytes=len(before), audit_bytes=len(after),
                             differing_common_bytes=sum(a != b for a, b in zip(before, after)),
                             differing_common_bits=sum((a ^ b).bit_count() for a, b in zip(before, after)))
    logs = []
    for path in sorted(stage.glob('*.log')):
        content = path.read_text(errors='replace')
        warnings = [dict(line=number, text=line)
                    for number, line in enumerate(content.splitlines(), 1)
                    if re.search(r'WARN|ERROR|FAIL|not found|not match|[Cc]annot|[Cc]ould not|No timing|No paths', line)]
        logs.append(dict(path=str(path), sha256=sha(path), warnings=warnings,
                         tail=content.splitlines()[-16:],
                         pnr_error_trace=bool(re.search(r'while executing\s+"run pnr"', content))))
    text = report.read_text() if report else ''
    paths = parse_summary(text)
    for path in paths:
        path['classification'] = classify(path)
    cen = [path for path in paths if path['classification'] == 'cen']
    coverage = {mode: any(path['mode'] == mode and
                          path['launch_clock'] == 'PHY_CLKOUT:[R]' and
                          path['capture_clock'] == 'fclk_960M:[F]' for path in cen)
                for mode in ('setup', 'hold')}
    models = [inspect_official_vo(path) for path in sorted(stage.glob('impl/pnr/*.vo'))]
    target_tokens = ['reset_stop_s2/Q', 'dhcen_inst/CEN', 'reset_calib_s2/Q',
                     'clkdiv_inst/RESETN', 'dhcen_inst/CLKIN', 'clkdiv_inst/HCLKIN']
    resolution = []
    exported_cells = {cell['name']: cell for model in models for cell in model['cells']}
    prefix = manifest['phy_prefix']
    for token in target_tokens:
        name, pin = (prefix + '/' + token).rsplit('/', 1)
        if token.startswith(('reset_stop', 'reset_calib')):
            name = prefix + '/u_oser_rst/' + token.rsplit('/', 1)[0]
        model_match = exported_cells.get(name)
        exact = bool(model_match and pin in model_match['ports'])
        reported = any(path['source'] == name + '/' + pin or path['target'] == name + '/' + pin
                       for path in paths)
        resolution.append(dict(pin=name + '/' + pin, official_vo=exact, timing_report=reported))
    result = dict(scope='Read-only extraction of isolated HS33 CEN/calibration audit',
                  stage=str(stage), manifest_sha256=sha(manifest_path), source_checks=checks,
                  configuration=configuration, logs=logs,
                  report=dict(path=str(report), sha256=sha(report),
                              no_path_messages=[dict(line=n, text=line)
                                                for n, line in enumerate(text.splitlines(), 1)
                                                if 'Nothing to report!' in line or
                                                re.search(r'No (?:setup|hold) paths to report', line)],
                              request_dispositions=[line.strip() for line in text.splitlines()
                                                    if 'TC_REPORT_TIMING' in line]) if report else None,
                  pin_resolution=resolution, official_models=models,
                  requested_cen_coverage=coverage,
                  targeted_paths=[path for path in paths if path['classification'] != 'other'],
                  targeted_details=relevant_details(text),
                  cen_data_delays_ns={mode: [path['data_delay_ns'] for path in cen if path['mode'] == mode]
                                      for mode in ('setup', 'hold')},
                  phase_window_established=False,
                  limits=['No path is not a PASS. Missing CEN endpoint timing cannot identify a physical phase.',
                          'Binary identity is required before attributing diagnostic routing delays to the loaded image.',
                          'Setup/hold report values are tool/corner bounds, not measured silicon latencies.',
                          'No CEN aperture/phase is inferred automatically from unrelated sequencer paths.',
                          'Official export connectivity is evidence of names, not evidence that the library times CEN.'])
    inputs_unchanged = all(item['unchanged'] for item in checks
                           if item['group'] != 'production_hashes')
    result['status'] = ('audit_inputs_changed' if not inputs_unchanged else
                        'pnr_failed_outputs_missing' if (not report or not binary) and
                        any(log['pnr_error_trace'] for log in logs) else
                        'pending_outputs' if not report or not binary else
                        'routing_differs' if not configuration['identical'] else
                        'cen_not_covered' if not all(coverage.values()) else
                        'cen_paths_reported_manual_phase_analysis_required')
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print('Status:', result['status'])
    print('Binary identical:', configuration['identical'], '; CEN coverage:', coverage)
    print('Targeted paths:', len(result['targeted_paths']), '; official VO models:', len(models))
    return 0 if result['status'] == 'cen_paths_reported_manual_phase_analysis_required' else 2


if __name__ == '__main__':
    raise SystemExit(main())
