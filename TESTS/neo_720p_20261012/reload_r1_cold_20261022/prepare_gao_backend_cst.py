#!/usr/bin/env python3
"""Prepare R13: frozen R10 backend inputs plus a separate GAO clock CST."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from board_contract import before_build, record_build
from gowin_toolchain import IDE, environment

PARENT = ROOT / 'tang/impl/console_neo_n56r10_gao_startup'
OUT = ROOT / 'tang/impl/console_neo_n56r13_gao_tck_cst'
RESEARCH = HERE / 'gao_cst_namespace'
REFERENCE_BUILDER = HERE / 'prepare_gao_tck_bufg.py'
REFERENCE_BUILDER_SHA = '054f3c8f0183c331dccc197c0040cb64ac5bebb1f9a0746d0be2ec455d49339d'
EXTRA = 'tang/boards/neo/startup_clock.cst'
LINE = 'CLOCK_LOC "control0[0]" BUFG = CLK;\n'
TOOL_PINS = {
    'lib/libgowin.so': '7e7920244fbfa518c228e51a2e8143c67d8c19cfba535d1c4d3700b780f10b4d',
    'lib/libGWTE.so': '321f74d8f9603ccfd8c31438b4eac8cb23e44945b95aec8b73c5e794ef1c8df4',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def manifest(path):
    assert not any(p.is_symlink() for p in path.rglob('*')), 'Symlink in frozen inputs'
    return {str(p.relative_to(path)): sha(p) for p in sorted(path.rglob('*')) if p.is_file()}


def parent_preflight():
    assert sha(REFERENCE_BUILDER) == REFERENCE_BUILDER_SHA
    spec = importlib.util.spec_from_file_location('frozen_r12_contract', REFERENCE_BUILDER)
    ref = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ref)
    sources = ref.preflight()  # Pin all R10 inputs, completion and audit selectors.
    for name, digest in TOOL_PINS.items():
        assert sha(IDE / name) == digest, 'Installed tool changed: ' + name
    assert EXTRA not in sources
    assert not (OUT / 'source').is_symlink()
    return ref.PINS, sources


def expected_command():
    original = (PARENT / 'impl/pnr/cmd.do').read_text()
    assert original.count('-cst_error\n') == 1
    assert '-gao_cst' not in original
    # No option changes; only isolate paths and append the separate GAO CST.
    return original.replace(str(PARENT), str(OUT)) + '-gao_cst ' + str(OUT / 'source' / EXTRA) + '\n'


def tcl(mode):
    assert mode in ('args-only', 'route')
    return ('load {' + str(OUT / 'gao_backend.so') + '} Gaobackend\n'
            'puts [luma_gao_backend ' + mode + ']\nexit 0\n')


def verify_prepared(pins, sources):
    saved = json.loads((OUT / 'backend_prepared.json').read_text())
    assert saved['parent_sha256'] == pins
    assert saved['builder_sha256'] == sha(Path(__file__)) == sha(OUT / 'builder.py')
    assert saved['reference_builder_sha256'] == sha(REFERENCE_BUILDER)
    assert saved['tool_sha256'] == {str(IDE / n): sha(IDE / n) for n in TOOL_PINS}
    assert saved['gw_sh_sha256'] == sha(IDE / 'bin/gw_sh')
    assert saved['tcl_library_sha256'] == sha(IDE / 'lib/libtcl8.6.so')
    assert saved['wrapper_source_sha256'] == sha(RESEARCH / 'gao_backend_tcl.cpp')
    for name, digest in saved['prepared_sha256'].items():
        path = OUT / name
        assert not path.is_symlink() and sha(path) == digest, 'Prepared input changed: ' + name
    actual = manifest(OUT / 'source')
    assert actual == sources | {EXTRA: hashlib.sha256(LINE.encode()).hexdigest()}
    assert actual == json.loads((OUT / 'sources.json').read_text())
    assert (OUT / 'impl/pnr/cmd.do').read_text() == expected_command()
    assert sha(OUT / 'impl/pnr/device.cfg') == sha(PARENT / 'impl/pnr/device.cfg')
    assert sha(OUT / 'impl/gao/gao.v') == pins['impl/gao/gao.v']
    for mode in ('args-only', 'route'):
        assert (OUT / ('backend_' + mode + '.tcl')).read_text() == tcl(mode)
    route = json.loads((OUT / 'route.json').read_text())
    parent_route = json.loads((PARENT / 'route.json').read_text())
    for field in ('required_qualification_audits', 'optional_audit_selectors_present',
                  'wide_gpu_controls_catalog_present', 'netlist_sha256',
                  'sdc_sha256', 'candidate_cst_sha256'):
        assert route[field] == parent_route[field]
    assert route['hardware_access'] is False and route['qualified'] is False
    return saved


def prepare(contract, pins, sources):
    OUT.mkdir(exist_ok=False)
    record_build(OUT, contract)
    shutil.copytree(PARENT / 'source', OUT / 'source')
    (OUT / 'source' / EXTRA).write_text(LINE)
    for name in ('console_neo.vg', 'font8x16.hex', 'rtl/video/font8x16.hex',
                 'rtl/usbhost/usb_hid_host_rom.hex', 'constraint_mapping.json',
                 'impl/pnr/device.cfg'):
        destination = OUT / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PARENT / name, destination)
    shutil.copytree(PARENT / 'impl/gao', OUT / 'impl/gao')
    (OUT / 'sources.json').write_text(json.dumps(manifest(OUT / 'source'), indent=2) + '\n')
    (OUT / 'impl/pnr/cmd.do').write_text(expected_command())
    shutil.copy2(RESEARCH / 'gao_backend_tcl.cpp', OUT / 'gao_backend_tcl.cpp')
    compile_command = ['g++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror',
        '-fPIC', '-shared', '-Wl,--no-undefined', '-DLUMA_GAO_OUT="' + str(OUT) + '"',
        str(OUT / 'gao_backend_tcl.cpp'), '-o', str(OUT / 'gao_backend.so'),
        '-L' + str(IDE / 'lib'), '-Wl,-rpath,' + str(IDE / 'lib'), '-lgowin', '-ltcl8.6']
    # Host module compilation only; no Gowin execution or FPGA work.
    process = subprocess.run(compile_command, capture_output=True, text=True, timeout=60)
    (OUT / 'wrapper_compile.log').write_text(process.stdout + process.stderr)
    assert process.returncode == 0, 'Host Tcl module compilation failed'
    for mode in ('args-only', 'route'):
        (OUT / ('backend_' + mode + '.tcl')).write_text(tcl(mode))
    shutil.copy2(Path(__file__), OUT / 'builder.py')
    route = json.loads((PARENT / 'route.json').read_text())
    route.update(kind='frozen_R10_backend_with_separate_GAO_CST', parent_inputs=str(PARENT),
        output=str(OUT), source_changes=['source/' + EXTRA],
        synthesis='Both application VG and generated GAO netlist reused byte-for-byte',
        parent_bitstream_sha256=pins['impl/pnr/ao_0.fs'],
        parent_qualification_status='FAIL', parent_hold_violations=13,
        hardware_access=False, qualified=False, candidate=True,
        application_cst_sdc_unchanged=True, generated_GAO_sha256=pins['impl/gao/gao.v'],
        backend_clock_constraint=LINE.strip(), backend_flag='-gao_cst',
        metadata_installation_phase='Prepared before backend execution; not qualification',
        required_postroute_checks=['All inherited audits without exemptions',
            'All 8 application PRIMARY clocks preserved',
            'Actual TCK resource distribution and sinks verified',
            'All 13 prior GAO hold paths reassessed; no frequency/slack exemption',
            'All 20 probe bindings and independent clk_d clock rechecked'])
    (OUT / 'route.json').write_text(json.dumps(route, indent=2) + '\n')
    files = manifest(OUT)
    saved = dict(parent_sha256=pins, builder_sha256=sha(Path(__file__)),
        reference_builder_sha256=sha(REFERENCE_BUILDER),
        tool_sha256={str(IDE / n): sha(IDE / n) for n in TOOL_PINS},
        gw_sh_sha256=sha(IDE / 'bin/gw_sh'), tcl_library_sha256=sha(IDE / 'lib/libtcl8.6.so'),
        wrapper_source_sha256=sha(RESEARCH / 'gao_backend_tcl.cpp'),
        compile_command=compile_command, prepared_sha256=files,
        hardware_access=False, backend_executed=False, local_regressions=contract['local_regressions'])
    (OUT / 'backend_prepared.json').write_text(json.dumps(saved, indent=2) + '\n')
    verify_prepared(pins, sources)
    print(json.dumps(dict(prepared=str(OUT), route_started=False, backend_executed=False)))


def execute(mode):
    name = 'backend_args' if mode == 'args-only' else 'build'
    assert not (OUT / (name + '.log')).exists(), 'Never overwrite a backend attempt'
    if mode == 'route':
        previous = json.loads((OUT / 'backend_args_result.json').read_text())
        assert previous['status'] == 'ARGUMENTS_ACCEPTED_NOT_ROUTED'
        assert previous['prepared_sha256'] == sha(OUT / 'backend_prepared.json')
        assert previous['log_sha256'] == sha(OUT / 'backend_args.log')
    with (OUT / (name + '.log')).open('x') as log:
        child = subprocess.Popen([str(IDE / 'bin/gw_sh'), str(OUT / ('backend_' + mode + '.tcl'))],
            cwd=OUT / 'impl/pnr', env=environment(), stdout=log, stderr=log, start_new_session=True)
        try:
            rc = child.wait(timeout=60 if mode == 'args-only' else None)
        except BaseException as exc:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
            log.flush()
            interrupted = dict(status='BACKEND_INTERRUPTED', hardware_access=False,
                exception=type(exc).__name__, prepared_sha256=sha(OUT / 'backend_prepared.json'),
                log_sha256=sha(OUT / (name + '.log')))
            (OUT / ('backend_args_result.json' if mode == 'args-only' else 'route_result.json')).write_text(json.dumps(interrupted, indent=2) + '\n')
            raise
    text = (OUT / (name + '.log')).read_text()
    passed = rc == 0 and 'BACKEND_ARGUMENT_IDENTITY_PASS' in text and not re.search(r'^ERROR', text, re.M)
    if mode == 'route':
        passed = passed and 'Bitstream generation completed' in text
    verify_prepared(*parent_preflight())
    status = ('ARGUMENTS_ACCEPTED_NOT_ROUTED' if mode == 'args-only' else 'ROUTED_NOT_QUALIFIED') if passed else 'BACKEND_FAILED'
    record = dict(status=status, returncode=rc, hardware_access=False,
        prepared_sha256=sha(OUT / 'backend_prepared.json'), log_sha256=sha(OUT / (name + '.log')))
    (OUT / ('backend_args_result.json' if mode == 'args-only' else 'route_result.json')).write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record))
    if not passed:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for option in ('check-only', 'prepare', 'verify-prepared', 'backend-args', 'route'):
        modes.add_argument('--' + option, action='store_true')
    args = parser.parse_args()
    pins, sources = parent_preflight()
    contract = before_build('neo', candidate=True)
    if args.check_only:
        print(json.dumps(dict(passed=True, backend_executed=False, hardware_access=False,
            output=str(OUT), source_delta=[EXTRA], constraint=LINE.strip())))
        return
    if args.prepare:
        prepare(contract, pins, sources)
        return
    verify_prepared(pins, sources)
    if args.verify_prepared:
        print(json.dumps(dict(passed=True, backend_executed=False, hardware_access=False)))
        return
    execute('args-only' if args.backend_args else 'route')


def interrupted(signum, _frame):
    raise KeyboardInterrupt('Signal ' + str(signum))


if __name__ == '__main__':
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, interrupted)
    main()
