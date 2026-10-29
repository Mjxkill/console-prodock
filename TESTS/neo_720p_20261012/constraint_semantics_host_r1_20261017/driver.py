#!/usr/bin/env python3
"""Measure Gowin max-delay semantics on a tiny isolated two-clock design.

No hardware action or console input change. Artificial source latency makes
it observable whether pin-based bounds include clock insertion/latency.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from gowin_toolchain import IDE, environment

RTL = '''module probe(input wire clk, other, output wire led_n);
(* syn_preserve=1, syn_keep=1 *) reg toggle=0;
(* syn_preserve=1, syn_keep=1 *) reg stage1=0, stage2=0;
always @(posedge other) toggle <= !toggle;
always @(posedge clk) begin stage1<=toggle; stage2<=stage1; end
assign led_n=stage2;
endmodule
'''
CST = '''IO_LOC "clk" V22; IO_PORT "clk" IO_TYPE=LVCMOS33 PULL_MODE=NONE;
IO_LOC "other" D22; IO_PORT "other" IO_TYPE=LVCMOS33 PULL_MODE=NONE;
IO_LOC "led_n" V13; IO_PORT "led_n" IO_TYPE=LVCMOS33 DRIVE=4;
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, out/'driver.py')
    records = []
    for name, latency, endpoint in [('clocks9', 9, 'clocks'),
                                    ('pins9', 9, 'pins'), ('pins0', 0, 'pins')]:
        target = out / name
        target.mkdir()
        (target/'probe.v').write_text(RTL)
        (target/'probe.cst').write_text(CST)
        bound = ('set_max_delay 8 -from [get_clocks {source}] -to [get_clocks {sink}]'
                 if endpoint == 'clocks' else
                 'set_max_delay 8 -from [get_pins {toggle_s1/Q}] -to [get_pins {stage1_s1/D}]')
        sdc = ('create_clock -name source -period 20 [get_ports {other}]\n'
               'create_clock -name sink -period 20 [get_ports {clk}]\n'
               f'set_clock_latency -source {latency} [get_clocks {{source}}]\n'+bound+'\n'
               'set_false_path -hold -from [get_clocks {source}] -to [get_clocks {sink}]\n'
               'report_timing -setup -max_paths 30 -max_common_paths 1\n'
               'report_timing -hold -max_paths 30 -max_common_paths 1\n')
        (target/'probe.sdc').write_text(sdc)
        script = ['set_device -name GW5AST-138C GW5AST-LV138PG484AC1/I0']
        script += ['add_file {'+str(target/f)+'}' for f in ('probe.v','probe.cst','probe.sdc')]
        script += ['set_option -top_module probe', 'set_option -output_base_name probe',
                   'set_option -use_cpu_as_gpio 1', 'set_option -gen_text_timing_rpt 1',
                   'set_option -place_option 3', 'set_option -route_option 2', 'run all']
        (target/'build.tcl').write_text('\n'.join(script)+'\n')
        print('Starting '+name, flush=True)
        with (target/'build.log').open('w') as log:
            process = subprocess.run([str(IDE/'bin/gw_sh'),'build.tcl'], cwd=target,
                                     env=environment(), stdout=log, stderr=subprocess.STDOUT)
        text = (target/'build.log').read_text()
        record = dict(name=name, returncode=process.returncode, requested_bound=bound,
                      artificial_latency_ns=latency,
                      inputs={f:hashlib.sha256((target/f).read_bytes()).hexdigest()
                              for f in ('probe.v','probe.cst','probe.sdc','build.tcl')})
        report = target/'impl/pnr/probe.tr'
        record['complete'] = (process.returncode == 0 and report.is_file() and
                              'Bitstream generation completed' in text and
                              not re.search(r'^ERROR',text,re.M))
        if report.is_file():
            tr = report.read_text()
            record['constraints'] = re.findall(r'^\s*TC_\S+\s+(\S+)\s+(.+?)\s*$',tr,re.M)
            sections = tr.split('3.3.1 Setup Analysis Report')[-1].split('3.3.2 Hold Analysis Report')[0]
            record['paths'] = []
            for block in sections.split('Path Summary:')[1:]:
                fields = {k:v.strip() for k,v in re.findall(
                    r'^(Slack|From|To|Launch Clk|Latch Clk|Data Arrival Time|Data Required Time)\s*:\s*(.+)$',block,re.M)}
                if fields:record['paths'].append(fields)
        records.append(record)
        (out/'result.json').write_text(json.dumps(dict(ide=str(IDE),cases=records,
            scope='Constraint semantics only; not board/console qualification'),indent=2)+'\n')
        print(name+': '+str(record['complete'])+' '+str(record.get('paths',[])),flush=True)
        if not record['complete']:
            raise SystemExit('Failed diagnostic build: '+str(target))


if __name__ == '__main__':
    main()
