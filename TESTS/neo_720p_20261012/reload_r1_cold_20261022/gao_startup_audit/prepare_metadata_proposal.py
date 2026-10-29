#!/usr/bin/env python3
"""Prepare provenance outside the running build; never modify that build.

The parent operator may install the proposal only after --verify-complete.
This is metadata for an unchanged reused application VG plus added GAO,
not a replacement of the toolchain, qualification or instrumentation audit.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PARENT = ROOT / 'tang/impl/console_neo_n56r9_route9_dma_c150'
BUILD = ROOT / 'tang/impl/console_neo_n56r10_gao_startup'
GAO = 'tang/boards/neo/startup.gao'
OPTIONAL = ('incremental', 'wide_gpu_controls_local',
            'requested_primary_gpu_control_nets', 'requested_local_gpu_control_nets')
EXPECTED_AUDITS = ['copy', 'scanout', 'gpu_owner_replication', 'timing_closure',
    'cpu_ddr_fifo_registers', 'gpu_reset_tree', 'gpu_pixel_mask',
    'gpu_pixel_mask_routed', 'gpu_pixel_selector', 'gpu_pixel_selector_routed']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def manifest(directory):
    return {str(p.relative_to(directory)): sha(p)
            for p in sorted(directory.rglob('*')) if p.is_file()}


def complete():
    # Read only the completion record/log until both say the outputs are final.
    result_path = BUILD / 'route_result.json'
    require(result_path.is_file(), 'Route completion record absent: do not inspect final outputs')
    result = json.loads(result_path.read_text())
    require(result['returncode'] == 0 and result['status'] == 'ROUTED_NOT_QUALIFIED',
            'Route did not complete successfully; qualification is a separate operation')
    log = (BUILD / 'build.log').read_text()
    require(not re.search(r'^ERROR', log, re.M), 'Build log contains ERROR')
    require('Bitstream generation completed' in log, 'Bitstream completion absent')
    require(f'Generate file "{BUILD}/impl/pnr/console_neo.tr" completed' in log,
            'Timing report completion absent')


def proposal():
    prep = json.loads((BUILD / 'gao_preparation.json').read_text())
    require(prep['parent'] == str(PARENT), 'Unexpected parent')
    require(prep['parent_qualification'] == 'FAIL', 'Parent FAIL must be retained')
    require(prep['additions'] == [GAO], 'Unexpected additions')
    for name, digest in prep['parent_sha256'].items():
        require(sha(PARENT / name) == digest, 'Changed parent ' + name)
    require(sha(BUILD / 'builder.py') == prep['builder_sha256'], 'Changed frozen builder')
    require(sha(BUILD / 'build.tcl') == prep['build_tcl_sha256'], 'Changed Tcl')
    require(sha(BUILD / 'sources.json') == prep['sources_sha256'], 'Changed source manifest')
    parent_sources = json.loads((PARENT / 'sources.json').read_text())
    sources = json.loads((BUILD / 'sources.json').read_text())
    require(manifest(PARENT / 'source') == parent_sources, 'Changed parent source tree')
    require(manifest(BUILD / 'source') == sources, 'Changed candidate source tree')
    require({k: v for k, v in sources.items() if k != GAO} == parent_sources,
            'Application source delta beyond GAO')
    require(sources[GAO] == prep['gao_sha256'], 'Changed GAO configuration')
    require(sha(BUILD / 'console_neo.vg') == prep['parent_sha256']['console_neo.vg'],
            'Changed reused application VG')
    for name in ('neo.cst', 'neo.sdc'):
        require(sha(BUILD / 'source/tang/boards/neo' / name) ==
                prep['parent_sha256']['source/tang/boards/neo/' + name],
                'Changed ' + name)
    expected_tcl = (PARENT / 'build.tcl').read_text().replace(str(PARENT), str(BUILD))
    expected_tcl = expected_tcl.replace('run pnr\n',
        'add_file -type gao {' + str(BUILD / 'source' / GAO) + '}\nrun pnr\n')
    require((BUILD / 'build.tcl').read_text() == expected_tcl, 'Unexpected Tcl delta/options')
    parent_route = json.loads((PARENT / 'route.json').read_text())
    parent_qual = json.loads((PARENT / 'qualification.json').read_text())
    require(parent_qual['status'] == 'FAIL', 'Parent qualification changed')
    require(set(parent_qual['synthesis_audits']) == set(EXPECTED_AUDITS),
            'Parent audit set changed: review the metadata proposal')
    # Do not invent/drop experiment selectors or a nonexistent catalog.
    require(not any(k in parent_route for k in OPTIONAL),
            'Parent has optional audit selectors: explicit inheritance review required')
    require(not (PARENT / 'wide_gpu_controls.json').exists(),
            'Parent wide-control catalog appeared: explicit inheritance review required')
    require(not (BUILD / 'wide_gpu_controls.json').exists(), 'Unexpected candidate wide-control catalog')
    audited = json.loads((HERE / 'result.json').read_text())
    require(audited['passed'] and not audited['final_bindings_verified'],
            'Wrong pre-PNR audit scope')
    for name, digest in audited['input_sha256'].items():
        require(sha(Path(name)) == digest, 'Generated GAO input changed ' + name)
    # A small manifest identifies precisely which records guide the proposal.
    inputs = [BUILD / name for name in ('gao_preparation.json', 'sources.json',
        'builder.py', 'build.tcl', 'console_neo.vg', 'source/' + GAO,
        'source/tang/boards/neo/neo.cst', 'source/tang/boards/neo/neo.sdc')]
    inputs += [PARENT / 'route.json', PARENT / 'qualification.json', HERE / 'result.json',
               ROOT / 'tools/check_neo_timing.py', ROOT / 'tools/check_geometry_timing.py']
    return dict(schema=1, kind='reused_application_netlist_with_GAO_instrumentation',
        parent_inputs=str(PARENT), output=str(BUILD),
        netlist_sha256=sha(BUILD / 'console_neo.vg'),
        sdc_sha256=sha(BUILD / 'source/tang/boards/neo/neo.sdc'),
        candidate_cst_sha256=sha(BUILD / 'source/tang/boards/neo/neo.cst'),
        source_changes=['source/' + GAO], application_hdl_netlist_unchanged=True,
        application_cst_sdc_unchanged=True, synthesis='application VG reused; GAO synthesized separately',
        parent_qualification_status='FAIL', parent_bitstream_sha256=prep['parent_sha256']['impl/pnr/console_neo.fs'],
        parent_synthesis_audits={name: audit['passed'] for name, audit in parent_qual['synthesis_audits'].items()},
        required_qualification_audits=EXPECTED_AUDITS,
        optional_audit_selectors_present=[], wide_gpu_controls_catalog_present=False,
        metadata_purpose='Select the actual root-level application VG in the unmodified qualifier; no gate reduction',
        metadata_installation_phase='Only after route_result and build-log completion checks pass',
        generated_GAO_pre_PNR_audit=str(HERE / 'result.json'),
        generated_GAO_sha256=sha(BUILD / 'impl/gao/gao.v'),
        final_GAO_bindings_verified=False, hardware_access=False, qualified=False,
        limits=['Not the original R9 bitstream: insertion causes a new physical implementation.',
                'The common qualifier audits the application VG and routed hardware; final GAO wiring requires the separate audit.',
                'Inherited FAIL is historical evidence, not a substituted result for the new candidate.',
                'No optional control-routing audit/catalog was active on this exact parent.'],
        inputs_sha256={str(p): sha(p) for p in inputs})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--write-proposal', action='store_true')
    modes.add_argument('--verify-complete', action='store_true')
    args = parser.parse_args()
    if args.verify_complete:
        complete()
    record = proposal()
    target = HERE / 'route_metadata.proposed.json'
    if args.write_proposal:
        with target.open('x') as output:
            json.dump(record, output, indent=2)
            output.write('\n')
    else:
        require(json.loads(target.read_text()) == record, 'Proposal differs from current frozen inputs')
        installed = BUILD / 'route.json'
        if installed.exists():
            require(json.loads(installed.read_text()) == record, 'Different route metadata already installed')
    print(json.dumps(dict(passed=True, route_complete_verified=args.verify_complete,
        candidate_written=False, proposal=str(target), proposal_sha256=sha(target),
        required_qualification_audits=record['required_qualification_audits'])))


if __name__ == '__main__':
    main()
