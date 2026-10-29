#!/usr/bin/env python3
"""Build the isolated Neo reset probe; no hardware or other build access."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from gowin_toolchain import IDE, environment


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--name',required=True)
    p.add_argument('--routing',choices=['auto','local'],required=True)
    p.add_argument('--telemetry',choices=['uart','jtag'],default='uart',
                   help='JTAG uses the existing ESP-Prog wires and a coherent snapshot mailbox')
    p.add_argument('--ide',type=Path,default=IDE,help='Explicit Gowin installation for a compiler comparison')
    p.add_argument('--system-freetype',action='store_true',help='Use system FreeType with the newer IDE Qt libraries')
    a=p.parse_args()
    ide=a.ide.resolve(strict=True)
    if not (ide/'bin/gw_sh').is_file():p.error('Gowin installation missing')
    if not re.fullmatch('[a-zA-Z0-9_]+',a.name):p.error('Invalid build name')
    out=ROOT/'tang/impl'/a.name
    out.mkdir(exist_ok=False)
    origins=[ROOT/'TESTS/rtl/neo_reset_probe.v',ROOT/'tang/boards/neo/vendor/uart_tx.v']
    if a.telemetry=='jtag':origins.append(ROOT/'TESTS/rtl/neo_reset_jtag.v')
    for origin in origins:
        shutil.copy2(origin,out/origin.name)
    cst='''IO_LOC "clk" V22;
IO_PORT "clk" IO_TYPE=LVCMOS33 PULL_MODE=NONE;
IO_LOC "uart_tx" U15;
IO_PORT "uart_tx" IO_TYPE=LVCMOS33 DRIVE=8;
IO_LOC "led_n" V13;
IO_PORT "led_n" IO_TYPE=LVCMOS33 DRIVE=4 PULL_MODE=NONE;
'''
    sdc='create_clock -name clk50 -period 20 -waveform {0 10} [get_ports {clk}]\n'
    if a.telemetry=='jtag':
        cst=cst.replace('IO_LOC "uart_tx" U15;\nIO_PORT "uart_tx" IO_TYPE=LVCMOS33 DRIVE=8;\n','')
        cst+='''IO_LOC "tck" D22; IO_PORT "tck" IO_TYPE=LVCMOS33 PULL_MODE=UP;
IO_LOC "tms" D21; IO_PORT "tms" IO_TYPE=LVCMOS33 PULL_MODE=UP;
IO_LOC "tdi" W20; IO_PORT "tdi" IO_TYPE=LVCMOS33 PULL_MODE=UP;
IO_LOC "tdo" F20; IO_PORT "tdo" IO_TYPE=LVCMOS33 DRIVE=8;
'''
        sdc+='''create_clock -name tck -period 1000 [get_ports {tck}]
set_input_delay -clock tck -max 520 [get_ports {tdi tms}]
set_input_delay -clock tck -min 480 [get_ports {tdi tms}]
set_output_delay -clock tck -max 20 [get_ports {tdo}]
set_output_delay -clock tck -min -20 [get_ports {tdo}]
# Only the first stage of each one-bit toggle synchronizer is asynchronous.
set_false_path -from [get_regs {request_toggle*}] -to [get_regs {request_sync_0_s0}]
set_false_path -from [get_regs {response_toggle*}] -to [get_regs {response_sync_0_s0}]
# Snapshot is held until a subsequent request; two TCK stages guard capture.
set_max_delay 100 -from [get_regs {snapshot_hold*}] -to [get_regs {dr*}]
set_min_delay 0 -from [get_regs {snapshot_hold*}] -to [get_regs {dr*}]
'''
    if a.routing=='local':
        cst+=''.join(f'CLOCK_LOC "reset_copies[{i}]" LOCAL_CLOCK;\n' for i in range(4))
    (out/'probe.cst').write_text(cst)
    (out/'probe.sdc').write_text(sdc)
    files=[o.name for o in origins]+['probe.cst','probe.sdc']
    script=['set_device -name GW5AST-138C GW5AST-LV138PG484AC1/I0']
    script += ['add_file {'+str(out/f)+'}' for f in files]
    top='neo_reset_jtag' if a.telemetry=='jtag' else 'neo_reset_probe'
    script += ['set_option -top_module '+top,'set_option -output_base_name probe',
               'set_option -verilog_std sysv2017','set_option -use_cpu_as_gpio 1',
               'set_option -use_sspi_as_gpio 0','set_option -gen_text_timing_rpt 1',
               'set_option -gen_verilog_sim_netlist 1','set_option -gen_sdf 1',
               'set_option -place_option 3','set_option -route_option 2','run all']
    (out/'build.tcl').write_text('\n'.join(script)+'\n')
    (out/'manifest.json').write_text(json.dumps(dict(routing=a.routing,telemetry=a.telemetry,ide=str(ide),
        scope='Standalone 50 MHz reset distribution only; no DDR/CPU/USB/SD/GPU',
        sha256={f:hashlib.sha256((out/f).read_bytes()).hexdigest() for f in files}),indent=2)+'\n')
    env=environment(ide,system_freetype=a.system_freetype)
    print(out,flush=True)
    with (out/'build.log').open('w') as log:
        result=subprocess.run([str(ide/'bin/gw_sh'),'build.tcl'],cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT)
    if result.returncode or re.search(r'^ERROR',(out/'build.log').read_text(),re.M):
        raise RuntimeError('Build failed; inspect '+str(out/'build.log'))
    print('Built only; mapping, timing and routing need qualification before a hardware test.')


if __name__=='__main__':main()
