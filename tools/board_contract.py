#!/usr/bin/env python3
"""Explicit source ownership and preservation of the measured Pro Dock release.

This checks inputs, not hardware. A successful local regression never certifies
a new bitstream. No command in this module accesses a board or updates a reference.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CATALOG = 'tang/boards/ownership.json'
REFERENCE = 'tang/boards/prodock/reference.json'
CACHE = 'TESTS/dual_board/latest.json'
SCOPES = ('tang/rtl/', 'tang/constr/', 'tang/boards/', 'fw_console/', 'linux/', 'tools/')
REQUIRED_TESTS = ('contract', 'bridge', 'ddr_prodock', 'ddr_neo', 'usb_msc', 'geometry',
                  'scanout_prodock', 'scanout_neo', 'text_both', 'dashboard_both', 'nebula_both',
                  'spi_pio', 'spi_uboot', 'spi_linux', 'mmc_spi_init')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def production_path(name):
    p = Path(name)
    if name in (CATALOG, REFERENCE) or p.suffix in ('.md', '.txt', '.pyc'):
        return False
    if any(x in ('temp', '__pycache__') or x == 'build' or x.startswith('build-')
           for x in p.parts[:-1]):
        return False
    if name.startswith('tools/'):
        return p.suffix == '.py'
    return name.startswith(SCOPES) or name == 'tang/build_gpu.tcl'


def discover(root):
    # Include untracked inputs, so adding a new source cannot silently escape ownership.
    names = subprocess.check_output(['git', 'ls-files', '-co', '--exclude-standard', '-z'],
                                    cwd=root).decode().split('\0')
    return sorted({n for n in names if n and production_path(n)})


def inventory(root=ROOT):
    root = Path(root)
    catalog = json.loads((root/CATALOG).read_text())
    files = catalog['files']
    found = set(discover(root))
    if found != set(files):
        raise ValueError('Source ownership inventory differs: unclassified='+str(sorted(found-set(files)))+
                         '; missing='+str(sorted(set(files)-found)))
    for name, item in files.items():
        if item['owner'] not in ('shared', 'prodock', 'neo'):
            raise ValueError('Invalid owner: '+name)
        p = root/name
        if not p.is_file() or p.is_symlink():
            raise ValueError('Missing or symlinked source: '+name)
    return catalog


def reference_check(root=ROOT):
    root = Path(root)
    record = json.loads((root/REFERENCE).read_text())
    errors = []
    for name, expected in record['protected_files'].items():
        p = root/name
        if not p.is_file() or sha(p) != expected:
            errors.append(name)
    if errors:
        raise ValueError('Protected Pro Dock reference changed/missing: '+str(errors))
    return record


def regression_inputs(root=ROOT):
    root = Path(root)
    catalog = inventory(root)
    inputs = {n: sha(root/n) for n in catalog['files']}
    # Include test benches and Python oracles, but never generated test outputs.
    for pattern in ('TESTS/*.py', 'TESTS/rtl/*.sv', 'TESTS/rtl/*.v', 'TESTS/rtl/*.svh'):
        for p in root.glob(pattern):
            inputs[str(p.relative_to(root))] = sha(p)
    for name in (CATALOG, REFERENCE, 'assets/nebula/packed/nebula.bin'):
        inputs[name] = sha(root/name)
    return inputs


def audit(root=ROOT):
    root = Path(root)
    catalog = inventory(root)
    reference = reference_check(root)
    changed = []
    for name, item in catalog['files'].items():
        expected = item.get('prodock_commit_sha256')
        if item['owner'] != 'neo' and sha(root/name) != expected:
            changed.append(dict(path=name, owner=item['owner'], kind=item['kind'],
                                reference_sha256=expected, current_sha256=sha(root/name)))
    return dict(reference_preserved=True, reference_commit=reference['commit'],
                reference_bitstream_sha256=reference['bitstream_sha256'],
                owners=dict(Counter(i['owner'] for i in catalog['files'].values())),
                changes_since_prodock=changed,
                prodock_hardware_validation='pending_for_changed_inputs' if changed else 'historical_reference_only',
                neo_hardware_validation='not_established_by_this_check',
                scope='Input integrity and ownership only; not build, timing or hardware qualification')


def require_local_regressions(root=ROOT):
    root = Path(root)
    path = root/CACHE
    if not path.is_file():
        raise ValueError('Run python3 tools/run_board_regressions.py --out TESTS/dual_board/<new-run> first')
    latest = json.loads(path.read_text())
    result_path = (root/latest['result']).resolve()
    if not result_path.is_relative_to(root/'TESTS/dual_board') or sha(result_path) != latest['sha256']:
        raise ValueError('Changed or misplaced dual-board regression result')
    result = json.loads(result_path.read_text())
    if (result.get('passed') is not True or result.get('inputs_digest') != digest(regression_inputs(root))
            or tuple(t['name'] for t in result.get('tests', [])) != REQUIRED_TESTS
            or not all(t['passed'] for t in result['tests'])):
        raise ValueError('Dual-board regression results are failed, incomplete or stale; rerun them')
    for test in result['tests']:
        log = (root/test['log']).resolve()
        if not log.is_relative_to(result_path.parent) or sha(log) != test['log_sha256']:
            raise ValueError('Changed regression evidence: '+test['name'])
    return dict(result=latest['result'], sha256=latest['sha256'], hardware_validation=False)


def before_build(board, *, candidate=False, root=ROOT):
    """Candidate builds allowed after local checks; never auto-promote Pro Dock."""
    if board not in ('prodock', 'neo'):
        raise ValueError('Unknown board')
    report = audit(root)
    if board == 'prodock' and report['changes_since_prodock'] and not candidate:
        raise ValueError('Pro Dock inputs differ from the measured reference. Use --candidate for '
                         'an explicitly unvalidated build; local dual-board regressions are required.')
    report['local_regressions'] = require_local_regressions(root)
    report.update(board=board, candidate=True, release_qualified=False)
    return report


def record_build(out, report):
    """Keep this outside sources.json: it is evidence, not synthesized input."""
    (Path(out)/'board_contract.json').write_text(json.dumps(report, indent=2)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--release-check', action='store_true',
                        help='Reject current inputs differing from the retained measured Pro Dock reference')
    args = parser.parse_args()
    report = audit()
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(reference_preserved=True, owners=report['owners'],
                         changed_inputs=len(report['changes_since_prodock']),
                         hardware=report['prodock_hardware_validation']), indent=2))
    if args.release_check and report['changes_since_prodock']:
        raise SystemExit('Changed inputs are not a validated Pro Dock release; hardware checks pending')


if __name__ == '__main__':
    main()
