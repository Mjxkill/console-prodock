#!/usr/bin/env python3
"""Prepare a firmware-only G22r0 FPGA candidate, preserving the reference.

The HDL, pins and clock constraints come from the protected snapshot.
The pre-synthesized AE350 IP must be regenerated to embed the new ITCM data.
Changing its config alone does not change the old netlist's INIT parameters.
This requires new synthesis;
the old routed design is an incremental hint, never a timing qualification.
No hardware operation is included. Every output is a new, explicit candidate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from board_contract import before_build, record_build, reference_check
from gowin_toolchain import IDE, environment

BASE = ROOT / 'tang/impl/gpu_geometry_g22r0'
SYNTHESIS_TEMPLATE = ROOT / 'tang/impl/gpu_geometry_g22'
ROM = ROOT / 'games/luma3d/candidates/autoboot_fpga_20261028_r1/direct_rom_01'
ROM_SHA = 'd8ab75277c4cb4eb2a4123fbdf269d96fa8a5cd44cb84eaa11c8e3fdf66d8ae8'
CONFIG = 'tang/rtl/board/riscv_ae350_soc_ext/cfg/gw_itcm_config.v'
CPU = 'tang/rtl/board/riscv_ae350_soc_ext/riscv_ae350_soc.v'


def regenerate_cpu(stage):
    """Regenerate only the candidate IP; never overwrite the shared/reference IP.

    Gowin's encrypted .v is already synthesized, including boot RAM INITs.
    The generated artifact and every vendor input are recorded separately.
    """
    cfg = (stage / 'source' / CONFIG).parent
    ip = stage / 'ae350_ip'
    ip.mkdir()
    template = ROOT / 'tang/rtl/board/riscv_ae350_soc_ext/cfg/riscv_ae350_soc.prj'
    project = ET.parse(template)
    project.getroot().find('Device').attrib.update(
        id='GW5AST-138B', package='FCPBGA676A', speed='1',
        partNumber='GW5AST-LV138FPG676AC1/I0')
    vendor = IDE / 'ipcore/RiscV_AE350_SOC/data'
    includes = project.findall(".//Option[@type='include_path']")
    assert len(includes) == 2
    includes[0].set('value', str(cfg))
    includes[1].set('value', str(vendor))
    for node in project.findall('.//File'):
        path = IDE / 'ipcore' / node.get('path').split('/IDE/ipcore/')[1]
        assert path.is_file() and path.is_relative_to(vendor)
        node.set('path', str(path))
    # Freeze evidence before the tool reads its installed vendor sources.
    inputs = {str(p): sha(p) for p in vendor.rglob('*') if p.is_file()}
    inputs.update({str(p): sha(p) for p in cfg.iterdir() if p.is_file()})
    inputs.update({str(p): sha(p) for p in (stage / 'source/boot_firmware/itcm').iterdir() if p.is_file()})
    inputs[str(template)] = sha(template)
    project.write(ip / 'cpu.prj', encoding='UTF-8', xml_declaration=True)
    json_file(ip / 'inputs.json', inputs)
    with (ip / 'synth.log').open('x') as log:
        result = subprocess.run([str(IDE / 'bin/GowinSynthesis'), '-prj', str(ip / 'cpu.prj')],
                                cwd=ip, env=environment(), stdout=log, stderr=subprocess.STDOUT)
    raw = (ip / 'synth.log').read_text()
    assert result.returncode == 0 and 'GowinSynthesis finish' in raw and not re.search(r'^ERROR', raw, re.M), raw[-4000:]
    assert all(sha(Path(p)) == digest for p, digest in inputs.items()), 'IP inputs changed during generation'
    output = ip / 'riscv_ae350_soc.vg'
    assert output.is_file() and sha(output) != sha(BASE / 'source' / CPU)
    shutil.copy2(output, stage / 'source' / CPU)
    json_file(ip / 'result.json', dict(returncode=result.returncode, netlist_sha256=sha(output),
                                     inputs_sha256=sha(ip / 'inputs.json'),
                                     rom_post_route_verification_required=True))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_file(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def prepare(name):
    assert re.fullmatch(r'prodock_sd_[a-z0-9_]+', name), 'Explicit Pro Dock SD candidate name required'
    contract = before_build('prodock', candidate=True)
    frozen = json.loads((BASE / 'sources.json').read_text())
    for relative, expected in frozen.items():
        assert sha(BASE / 'source' / relative) == expected, relative
    audit = json.loads((ROM / 'audit.json').read_text())
    assert audit['passed'] and audit['qualification'] == 'offline_layout_and_binary_only'
    assert sha(ROM / 'build/console_test.bin') == ROM_SHA
    assert audit['symbols']['reset_vector'] == 0x80000000 and audit['symbols']['_start'] == 0x8000000c
    for relative, item in audit['artifacts'].items():
        assert sha(ROM.parent / relative) == item['sha256'], relative
    stage = ROOT / 'tang/impl' / name
    stage.mkdir(exist_ok=False)
    record_build(stage, contract)
    shutil.copytree(BASE / 'source', stage / 'source')
    shutil.copytree(BASE / 'rtl', stage / 'rtl')
    boot = stage / 'source/boot_firmware'
    boot.mkdir()
    for suffix in ('bin', 'elf', 'map'):
        shutil.copy2(ROM / ('build/console_test.' + suffix), boot / ('sd_boot.' + suffix))
    shutil.copytree(ROM / 'build/itcm', boot / 'itcm')
    shutil.copy2(ROM / 'audit.json', boot / 'audit.json')
    config = stage / 'source' / CONFIG
    value = config.read_text()
    value, count = re.subn(r'(?m)^`define ITCM_INIT_PATH "[^"]+"$',
                           '`define ITCM_INIT_PATH "' + str(boot / 'itcm') + '"', value)
    assert count == 1
    config.write_text(value)
    regenerate_cpu(stage)
    # Keep G22r0's actual pin/clock/placement constraints. The source list comes
    # from its original synthesis recipe; the protected reference itself was
    # subsequently routed with replication disabled, which we retain here.
    shutil.copy2(BASE / 'constraints_resolved.cst', stage / 'constraints_resolved.cst')
    routed = BASE / 'impl/pnr/console_gpu_geometry_g22r0.pr'
    reference = stage / 'reference_g22r0.pr'
    shutil.copy2(routed, reference)
    original = (SYNTHESIS_TEMPLATE / 'build.tcl').read_text()
    text = original.replace(str(SYNTHESIS_TEMPLATE), str(stage))
    text = text.replace('console_gpu_geometry_g22', 'console_' + name)
    text, count = re.subn(r'(?m)^set_option -replicate_resources \d+$',
                          'set_option -replicate_resources 0', text)
    assert count == 1 and text.count('run pnr') == 1
    text = text.replace('run pnr', f'set_option -inc_pnr {{{reference}}}\nrun pnr')
    # Preserve the timing constraints, omit only expensive custom reports
    # associated with the previous tool crash. Global STA remains enabled.
    sdc = stage / 'source/diagnostics/timing_reports.sdc'
    original_sdc = sdc.read_text().splitlines(keepends=True)
    removed_queries = [line for line in original_sdc if line.startswith('report_timing ')]
    assert len(removed_queries) == 5
    sdc.write_text(''.join(line for line in original_sdc if not line.startswith('report_timing ')))
    for filename in re.findall(r'^add_file \{(.*?)\}', text, re.M):
        file = Path(filename)
        assert file.is_relative_to(stage) and file.is_file(), filename
    (stage / 'build.tcl').write_text(text)
    shutil.copy2(Path(__file__), stage / 'build_driver.py')
    sources = {str(p.relative_to(stage / 'source')): sha(p)
               for p in (stage / 'source').rglob('*') if p.is_file()}
    changed = [relative for relative in frozen if sources[relative] != frozen[relative]]
    assert set(changed) == {CONFIG, CPU, 'diagnostics/timing_reports.sdc'}, changed
    json_file(stage / 'sources.json', sources)
    proof = dict(candidate=True, hardware_validated=False, target_programmer='2025071717',
                 parent=str(BASE), parent_manifest_sha256=sha(BASE / 'sources.json'),
                 firmware_sha256=ROM_SHA, firmware_bytes=20936, changed_existing_sources=changed,
                 clocks_changed=False, pins_changed=False, cpu_ip_regenerated=True,
                 vendor_ip_changed=True, removed_timing_queries=removed_queries,
                 rom_post_route_verification_required=True,
                 new_synthesis_required=True, incremental_hint_sha256=sha(reference),
                 ide=str(IDE), compiler_sha256=sha(IDE / 'bin/gw_sh'),
                 tcl_sha256=sha(stage / 'build.tcl'), created_unix=time.time(),
                 limits=['G22r0 timing limitations do not qualify this candidate',
                         'New synthesis, timing and cold SD boot require separate review',
                         'No board, SD or flash programmed by this builder'])
    json_file(stage / 'sd_boot_candidate.json', proof)
    reference_check()
    print(json.dumps({'prepared': str(stage), 'firmware_sha256': ROM_SHA, 'changed': changed}), flush=True)
    return stage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    parser.add_argument('--candidate', action='store_true', required=True)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    stage = prepare(args.name)
    if not args.run:
        return
    with (stage / 'build.log').open('x') as log:
        result = subprocess.run([str(IDE / 'bin/gw_sh'), 'build.tcl'], cwd=stage,
                                env=environment(), stdout=log, stderr=subprocess.STDOUT)
    errors = bool(re.search(r'^ERROR', (stage / 'build.log').read_text(), re.M))
    record = dict(tool_returncode=result.returncode, tool_error=errors,
                  timing_review_pending=True, hardware_validated=False)
    json_file(stage / 'build_result.json', record)
    reference_check()
    if result.returncode or errors:
        raise RuntimeError('Candidate build failed; see ' + str(stage / 'build.log'))
    checker = Path(__file__).parent / 'r3_qualification_01/rom_check.py'
    subprocess.run([sys.executable, '-B', str(checker),
                    '--vo', str(stage / f'impl/pnr/console_{stage.name}.vo'),
                    '--binary', str(stage / 'source/boot_firmware/sd_boot.bin'),
                    '--out', str(stage / 'rom_verification')], check=True)
    record['rom_post_route_verified'] = True
    json_file(stage / 'build_result.json', record)
    print(json.dumps(record), flush=True)


if __name__ == '__main__':
    main()
