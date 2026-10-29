#!/usr/bin/env python3
"""Generate an isolated Neo DDR3 6.0 IP with the existing memory parameters.

No shared RTL, installed IP, board, flash or SD is modified. The output is
an IP candidate, not a qualified FPGA build.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from gowin_toolchain import IDE, environment

CONFIG = 'tang/rtl/board/ddr3_standalone_32b/cfg'
NETLIST = 'tang/rtl/board/ddr3_standalone_32b/ddr3_standalone.v'
CONFIG_FILES = ('DDR3_define.v', 'ddr3_name.v', 'gwmc_param.v')
PART = 'GW5AST-LV138PG484AC1/I0'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parameters(text):
    pairs = re.findall(r'^parameter\s+(\w+)\s*=\s*([^;]+);', text, re.M)
    result = dict(pairs)
    if len(result) < 30 or len(result) != len(pairs):
        raise ValueError('Incomplete or duplicate DDR parameter declarations')
    return {key: value.strip() for key, value in result.items()}


def generator_options(baseline, memory_clock_mhz=None):
    fields = {'nCK_PER_CLK': 'CLK_Ratio', 'DQ_WIDTH': 'Dq_Width',
              'DRAM_WIDTH': 'Dram_Width', 'RANK_WIDTH': 'Rank_Address',
              'BANK_WIDTH': 'Bank_Address', 'ROW_WIDTH': 'Row_Address',
              'COL_WIDTH': 'Column_Address', 'BURST_TYPE': 'Burst_Type',
              'CL': 'CAS_Latency', 'CWL': 'CW_Latency', 'AL': 'Additive_Latency',
              'RTT_NOM': 'Rtt_Nom', 'RTT_WR': 'Rtt_Wr',
              'ADDR_CMD_MODE': 'Addr_Cmd_Mode', 'OUTPUT_DRV': 'OUTPUT_DRV'}
    fields.update({key: key+'_Period' for key in
                   ('tRTP','tRP','tWTR','tRC','tRAS','tRCD','tFAW','tRRD','tCKE','tREFI','tRFC')})
    fields['tDLLK'] = 'tDLLK'
    result = {'User_Interface': 'Controller', 'Memory_Type': 'Components',
              'Memory_Clock': str(1000000 // int(baseline['tCK']))}
    for key, option in fields.items():
        result[option] = baseline[key].strip('"')
    result['CLK_Ratio'] = '1:' + baseline['nCK_PER_CLK']
    result['AXI4_Interface'] = 'false'
    if memory_clock_mhz is not None:
        if memory_clock_mhz not in (300,325,400):
            raise ValueError('Only the explicit Neo 300/325/400 MHz PLL profiles are supported')
        result['Memory_Clock'] = str(memory_clock_mhz)
        result.update(MC_BSRAM='true', MC_SSRAM='false', MC_REG='false')
    # ECC off and BL8 are fixed by the selected device. The emitted
    # parameters, including those fixed settings, are checked below.
    return result


def ports(text):
    blocks = re.findall(r'^module DDR3_Memory_Interface_Top\s*\(.*?^endmodule', text, re.M | re.S)
    if len(blocks) != 1:
        raise ValueError('Expected one public DDR3 interface')
    declarations = re.findall(r'^(input|output|inout)\s+(?:wire\s+)?(\[[^]]+\]\s*)?(\w+)\s*;', blocks[0], re.M)
    result = {name: (direction, re.sub(r'\s+', '', width)) for direction, width, name in declarations}
    if len(result) < 35 or len(result) != len(declarations):
        raise ValueError('Incomplete or ambiguous DDR3 port declarations')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    parser.add_argument('--memory-clock-mhz', type=int, choices=[300,325,400],
                        help='Explicit Neo correction; otherwise preserve the historical parameters')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_]+', args.name):
        parser.error('Invalid build name')
    vendor = IDE / 'ipcore/DDR3'
    spec = vendor / 'ddr3.ipspec'
    ip = ET.parse(spec).getroot().find('ip')
    if ip.get('id') != 'ddr3' or ip.get('version') != '6.0':
        raise ValueError('This experiment requires DDR3 IP 6.0')
    out = ROOT / 'tang/impl' / args.name
    out.mkdir(exist_ok=False)
    cfg = out / 'baseline_cfg'
    cfg.mkdir()
    for name in CONFIG_FILES:
        shutil.copyfile(ROOT / CONFIG / name, cfg / name)
    shutil.copyfile(spec, out / spec.name)
    baseline = parameters((cfg / 'gwmc_param.v').read_text())
    options = generator_options(baseline, args.memory_clock_mhz)
    expected = dict(baseline)
    if args.memory_clock_mhz is not None:
        expected['tCK'] = str(1000000 // args.memory_clock_mhz)
    commands = [f'create_project -name ddr6 -dir {{{out}/project}} -pn {PART} -device_version C',
                f'create_ipc -name ddr3 -module_name DDR3_Memory_Interface_Top -file_name ddr3_standalone -language Verilog -dir {{{out}/ip}}']
    commands += [f'set_property CONFIG.{key} {{{value}}} [get_ips DDR3_Memory_Interface_Top]'
                 for key, value in options.items()]
    commands += ['report_property [get_ips DDR3_Memory_Interface_Top]',
                 'generate_target [get_ips DDR3_Memory_Interface_Top]',
                 'puts {DDR6_GENERATOR_FINISHED}', 'exit 0']
    (out / 'generate.tcl').write_text('\n'.join(commands)+'\n')
    shutil.copyfile(Path(__file__), out / 'build_driver.py')
    inputs = {str(p.relative_to(out)): sha(p) for p in out.rglob('*') if p.is_file()}
    record = dict(ide=str(IDE), ip_version='6.0', part=PART,
                  configuration={name: sha(cfg / name) for name in CONFIG_FILES},
                  options=options, baseline_parameters=baseline,
                  expected_parameters=expected,
                  parameter_overrides={k:v for k,v in expected.items() if baseline[k]!=v},
                  vendor_sha256={str(p.relative_to(vendor)):sha(p)
                                 for p in (vendor/'data/ddr3_1_4code_hs').iterdir() if p.is_file()},
                  baseline_netlist_sha256=sha(ROOT / NETLIST), inputs=inputs,
                  passed=False, scope=__doc__)
    print(out, flush=True)
    try:
        with (out / 'synth.log').open('w') as log:
            result = subprocess.run([str(IDE / 'bin/gw_sh'), 'generate.tcl'],
                                    cwd=out, env=environment(), stdout=log, stderr=log)
        log = (out / 'synth.log').read_text()
        if result.returncode or re.search(r'^ERROR', log, re.M) or 'DDR6_GENERATOR_FINISHED' not in log:
            raise RuntimeError('IP generation failed; inspect ' + str(out / 'synth.log'))
        generated = out / 'ip/ddr3_standalone'
        net = generated / 'ddr3_standalone.v'
        actual_parameters = parameters((generated / 'temp/DDR3/gwmc_param.v').read_text())
        differences = {k: (v, actual_parameters.get(k)) for k, v in expected.items()
                       if actual_parameters.get(k) != v}
        if differences:
            raise ValueError('Memory parameters changed: '+str(differences))
        baseline_ports = ports((ROOT / NETLIST).read_text())
        candidate_ports = ports(net.read_text())
        if candidate_ports != baseline_ports:
            raise ValueError('Generated DDR3 public interface differs from the baseline')
        if any(sha(out / name) != digest for name, digest in inputs.items()):
            raise ValueError('Generator modified a frozen input')
        shutil.copyfile(net, out / 'ddr3_standalone.vg')
        shutil.copytree(generated / 'temp/DDR3', out / 'cfg',
                        ignore=shutil.ignore_patterns('*.vg', '*.log', '*.html', '*.xml', '*_tmp.v', 'project.ini'))
        record.update(passed=True, netlist_sha256=sha(net), ports=candidate_ports,
                      generated_parameters=actual_parameters,
                      added_parameters={k:v for k,v in actual_parameters.items() if k not in baseline},
                      generated_files={str(p.relative_to(out)):sha(p)
                                       for p in (out/'cfg').iterdir() if p.is_file()})
        print('IP generated; interface and explicitly requested parameters match. Not board-qualified.', flush=True)
    finally:
        (out / 'result.json').write_text(json.dumps(record, indent=2) + '\n')


if __name__ == '__main__':
    main()
