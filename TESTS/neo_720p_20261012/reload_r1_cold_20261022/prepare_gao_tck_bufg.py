#!/usr/bin/env python3
"""Neo-only GAO TCK routing experiment; one CST statement, no hardware access."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from board_contract import before_build, record_build
from gowin_toolchain import IDE, environment

PARENT = ROOT / 'tang/impl/console_neo_n56r10_gao_startup'
OUT = ROOT / 'tang/impl/console_neo_n56r12_gao_tck_bufg'
CST = 'tang/boards/neo/neo.cst'
LINE = 'CLOCK_LOC "control0[0]" BUFG = CLK;'
ADDITION = '\n// Isolated R12: distribute GAO readout TCK after GW_JTAG.\n' + LINE + '\n'
PINS = {
    'sources.json': '377ebf1c381044784f52786c30db93955bc2f64f2cf14890c4939acea0bfe918',
    'console_neo.vg': '0b5ea22b83faf2bae943f399bdb734dc1e66c8507310dc25e054290e24ad6157',
    'build.tcl': 'af318cf5825b2187e77c580ce4d3ddf224f6659b2f0ef90992d91d260a6da94a',
    'source/tang/boards/neo/neo.cst': 'e08dd2bd88b2074a758a828a91393cbbbd5a870e77f99c7bc34071cf41a82c89',
    'source/tang/boards/neo/neo.sdc': 'c8da535e839157a361e78b06b2f65b2912891f8e9dc48b02d5b315ae9f953113',
    'source/tang/boards/neo/startup.gao': '0116f9daba8ac6d88af534f426d9f168eae56a669c48df9372114a2795fbb7e6',
    'impl/pnr/ao_0.fs': '7ca33ea0a54a4ba557319489239e330f6fbfca69840982894ca447a705b05f28',
    'impl/gao/gao.v': '34ba95774df302b6cecc51eb7ee5cb23413188075b9b61d8259fdd86de5c3198',
    'impl/pnr/cmd.do': '7620bbbf9a7b70494794429ba8a28e8705549069547cf6227fcd9e1df5ceb8f2',
    'route.json': '5ad9c42ba6ef686b81586da57d60ba19e2e12409458368497c11603d37b2b026',
    'route_result.json': 'f39fd4c16654e20949b7daaa4c67de8c149621798c04fd17eadcc0a0470941fe',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest(path):
    assert not any(p.is_symlink() for p in path.rglob('*')), 'Symlink in frozen source tree'
    return {str(p.relative_to(path)): sha(p) for p in sorted(path.rglob('*')) if p.is_file()}


def preflight():
    for path, digest in PINS.items():
        assert sha(PARENT / path) == digest, 'Parent changed: ' + path
    sources = json.loads((PARENT / 'sources.json').read_text())
    assert sources == manifest(PARENT / 'source')
    route_result = json.loads((PARENT / 'route_result.json').read_text())
    assert route_result['status'] == 'ROUTED_NOT_QUALIFIED' and route_result['returncode'] == 0
    log = (PARENT / 'build.log').read_text()
    assert 'Bitstream generation completed' in log
    assert f'Generate file "{PARENT}/impl/pnr/console_neo.tr" completed' in log
    gao = (PARENT / 'impl/gao/gao.v').read_text()
    assert gao.count('.tck_o(control0[0])') == 1
    assert '"control0[0]"' not in (PARENT / 'source' / CST).read_text()
    assert '\n-cst_error\n' in (PARENT / 'impl/pnr/cmd.do').read_text()
    route = json.loads((PARENT / 'route.json').read_text())
    assert route['optional_audit_selectors_present'] == []
    assert not any(k in route for k in ('incremental', 'wide_gpu_controls_local',
        'requested_primary_gpu_control_nets', 'requested_local_gpu_control_nets'))
    assert not (PARENT / 'wide_gpu_controls.json').exists()
    return sources


def verify_prepared(sources):
    saved = json.loads((OUT / 'route.json').read_text())
    assert saved['parent_inputs'] == str(PARENT) and saved['output'] == str(OUT)
    assert saved['parent_sha256'] == PINS and saved['cst_addition'] == LINE
    assert saved['builder_sha256'] == sha(Path(__file__)) == sha(OUT / 'builder.py')
    assert saved['build_tcl_sha256'] == sha(OUT / 'build.tcl')
    assert (OUT / 'build.tcl').read_text() == (PARENT / 'build.tcl').read_text().replace(str(PARENT), str(OUT))
    assert saved['sources_sha256'] == sha(OUT / 'sources.json')
    actual = manifest(OUT / 'source')
    assert actual == json.loads((OUT / 'sources.json').read_text())
    assert set(actual) == set(sources)
    assert [n for n in actual if actual[n] != sources[n]] == [CST]
    assert (OUT / 'source' / CST).read_text() == (PARENT / 'source' / CST).read_text() + ADDITION
    assert sha(OUT / 'console_neo.vg') == PINS['console_neo.vg']
    for name in ('font8x16.hex', 'rtl/video/font8x16.hex', 'rtl/usbhost/usb_hid_host_rom.hex', 'constraint_mapping.json'):
        assert sha(OUT / name) == sha(PARENT / name)
    return saved


def main():
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check-only', action='store_true')
    mode.add_argument('--prepare', action='store_true')
    mode.add_argument('--verify-prepared', action='store_true')
    mode.add_argument('--route', action='store_true')
    args = p.parse_args()
    sources = preflight()
    contract = before_build('neo', candidate=True)
    if args.check_only:
        print(json.dumps(dict(passed=True, hardware_access=False, cst_addition=LINE,
            expected_source='GW_JTAG u_gw_jtag.tck_o -> control0[0]',
            clock_resolution_and_timing_proven=False)))
        return
    if args.prepare:
        OUT.mkdir(exist_ok=False)
        record_build(OUT, contract)
        shutil.copytree(PARENT / 'source', OUT / 'source')
        with (OUT / 'source' / CST).open('a') as f:
            f.write(ADDITION)
        actual = manifest(OUT / 'source')
        assert set(actual) == set(sources)
        assert [name for name in actual if actual[name] != sources[name]] == [CST]
        for name in ('console_neo.vg', 'font8x16.hex', 'rtl/video/font8x16.hex',
                     'rtl/usbhost/usb_hid_host_rom.hex', 'constraint_mapping.json'):
            dest = OUT / name; dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(PARENT / name, dest)
            assert sha(dest) == sha(PARENT / name)
        (OUT / 'sources.json').write_text(json.dumps(actual, indent=2) + '\n')
        tcl = (PARENT / 'build.tcl').read_text().replace(str(PARENT), str(OUT))
        (OUT / 'build.tcl').write_text(tcl)
        record = dict(parent_inputs=str(PARENT), output=str(OUT), candidate=True,
            hardware_access=False, release_qualified=False, source_changes=[CST],
            netlist_sha256=PINS['console_neo.vg'], parent_sha256=PINS,
            build_tcl_sha256=sha(OUT / 'build.tcl'), sources_sha256=sha(OUT / 'sources.json'),
            builder_sha256=sha(Path(__file__)), cst_addition=LINE,
            parent_qualification_status='FAIL', parent_hold_violations=13,
            hypothesis='Reduce skew on the shared GAO TCK distribution after GW_JTAG; no result presumed.',
            required_postroute_checks=['Generated cmd.do retains -cst_error',
                'CST resolves intended GAO net, not a functional application net',
                'TCK output and actual sinks use the requested global clock resource',
                'Eight application PRIMARY clocks and all previous controls preserved',
                'All timing and original application audits retained; GAO hold must be assessed'],
            application_hdl_and_gao_configuration_unchanged=True,
            sdc_and_clock_frequencies_unchanged=True,
            local_regressions=contract['local_regressions'])
        (OUT / 'route.json').write_text(json.dumps(record, indent=2) + '\n')
        shutil.copy2(Path(__file__), OUT / 'builder.py')
        verify_prepared(sources)
        print(json.dumps(dict(prepared=str(OUT), hardware_access=False, route_started=False)))
        return
    verify_prepared(sources)
    if args.verify_prepared:
        print(json.dumps(dict(passed=True, hardware_access=False, route_started=False,
                              prepared=str(OUT), cst_addition=LINE)))
        return
    assert not (OUT / 'build.log').exists(), 'Never overwrite a route attempt'
    print('Routing isolated GAO TCK BUFG experiment ' + str(OUT), flush=True)
    with (OUT / 'build.log').open('x') as log:
        result = subprocess.run([str(IDE / 'bin/gw_sh'), 'build.tcl'], cwd=OUT,
                                env=environment(), stdout=log, stderr=log)
    log = (OUT / 'build.log').read_text()
    failed = result.returncode != 0 or bool(re.search(r'^ERROR', log, re.M)) or 'Bitstream generation completed' not in log
    record = dict(returncode=result.returncode, hardware_access=False,
                  status='ROUTING_FAILED' if failed else 'ROUTED_NOT_QUALIFIED')
    (OUT / 'route_result.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record), flush=True)
    if failed: raise SystemExit(1)


if __name__ == '__main__':
    main()
