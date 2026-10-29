#!/usr/bin/env python3
"""Test frozen observation additions; simulation only, no FPGA compiler."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
from probe_config import cases


def main():
    source = HERE/'candidate/source'
    out = HERE/'observer_sim'
    out.mkdir(exist_ok=False)
    record = dict(passed=False, scope='RTL only; no SDF or metastability model; no hardware access',cases=[])
    unit = (ROOT/'TESTS/rtl/neo_gpu_debug_tb.sv').read_text()
    unit = unit.replace('    wire [255:0] live;',
        "    wire [255:0] live;\n    reg [63:0] observe_packet_words=64'hfeed1234a5012345;")
    unit = unit.replace('(a%4)!=0 || a==24 || a==28 || a>=64', '(a%4)!=0 || a>=68')
    unit = unit.replace('        for(integer n=1;n<=30;', '''        read_reg(24,status);
        if(status!==32'ha5012345)$fatal(1,"Raw geometry header before snapshot");
        read_reg(28,status);
        if(status!==32'hfeed1234)$fatal(1,"Raw pixel header before snapshot");
        for(integer n=1;n<=30;''')
    unit = unit.replace('        run_mem=1;check_snapshot(31);', '''        // Independent probes remain readable while the coherent path waits.
        observe_packet_words=64'h89abcdef76543210;
        repeat(8)@(negedge hclk);
        read_reg(24,status);
        if(status!==32'h76543210)$fatal(1,"Raw geometry unavailable while busy");
        read_reg(28,status);
        if(status!==32'h89abcdef)$fatal(1,"Raw pixel unavailable while busy");
        read_reg(64,status);
        if(status[10]!==1 || status[0]===status[3])$fatal(1,"Raw handshake did not expose pending request %h",status);
        run_mem=1;check_snapshot(31);''')
    (out/'neo_gpu_debug_tb.sv').write_text(unit)
    accel = (ROOT/'TESTS/rtl/neo_gpu_debug_accel_tb.sv').read_text()
    accel = accel.replace('    wire [31:0] wr_mask;',
        '    wire [31:0] wr_mask;\n    wire [63:0] observe_packet_words;')
    accel = accel.replace('.debug_accept(debug_accept));', '.debug_accept(debug_accept),.observe_packet_words(observe_packet_words));')
    accel = accel.replace('.live(debug_state));', '.live(debug_state),.observe_packet_words(observe_packet_words));')
    gpu_read = '''    task read_gpu(input [7:0] address,output [31:0] value);
        @(negedge hclk);hsel=1;htrans=2;hwrite=0;haddr=32'h1000+address;
        @(negedge hclk);hsel=0;htrans=0;
        if(gpu_ready!==0)$fatal(1,"GPU read missing wait state");
        @(negedge hclk);
        if(gpu_ready!==1)$fatal(1,"GPU read still waiting");
        value=gpu_data;
    endtask
'''
    accel = accel.replace('    reg [31:0] value;',gpu_read+'    reg [31:0] value;')
    start = accel.index("        write_reg('h1010,'h16000000);")
    end = accel.index('        $finish;',start)
    replacement = []
    rejected = geometry_bad = pixel_word0 = 0
    for index, case in enumerate(cases(),1):
        opcode = case['words'][0]>>24
        if opcode<31:
            pixel_word0 = case['words'][0]
        rejected += int(not case['accepted'])
        geometry_bad += int(not case['accepted'] and opcode>=31)
        replacement += [f'        // {case["name"]}']
        replacement += [f"        write_reg('h1010,32'h{word:08x});" for word in case['words']]
        replacement += ['        repeat(120)@(negedge hclk);',
            f'        read_gpu(8,value);if(value!==32\'d{index})$fatal(1,"Fence case {case["name"]}: %h",value);',
            f'        read_gpu(\'h34,value);if(value!==32\'d{rejected})$fatal(1,"Reject case {case["name"]}: %h",value);',
            f'        read_gpu(\'h4c,value);if(value!==32\'d{geometry_bad})$fatal(1,"Geometry error case {case["name"]}: %h",value);',
            f'        read_debug(24,value);if(value!==32\'h{case["words"][0]:08x})$fatal(1,"Captured geometry {case["name"]}: %h",value);',
            f'        read_debug(28,value);if(value!==32\'h{pixel_word0:08x})$fatal(1,"Captured pixels {case["name"]}: %h",value);',
            f'        read_debug(64,value);if(value[23:16]!==8\'d{opcode})$fatal(1,"Ingress opcode {case["name"]}: %h",value);']
    replacement += ["        write_reg('h5004,1);",'        repeat(30)@(negedge hclk);',
        '        read_debug(4,value);if(value!==6)$fatal(1,"Snapshot ABI changed");',
        f'        read_debug(8,value);if(value!=={len(cases())*8})$fatal(1,"Host words");',
        f'        read_debug(\'h10,value);if(value!=={len(cases())*8})$fatal(1,"Received words");',
        f'        $display("PASS: {len(cases())} configuration cases, headers, error/fence counters, unchanged snapshot ABI; no DMA");']
    accel = accel[:start]+'\n'.join(replacement)+'\n'+accel[end:]
    (out/'neo_gpu_debug_accel_tb.sv').write_text(accel)
    gpu = [source/f'tang/rtl/video/{name}.v' for name in (
        'gpu_accel','gpu_geometry','gpu_geom_div','blitter','gpu_raster','gpu_v1',
        'gpu_texture_cache','gpu_copy565','gpu_perspective','gpu_triangle','gpu_blit_dma','font_ram')]
    gpu += [source/f'tang/rtl/board/{name}.v' for name in ('ddr_dcfifo','cdc_word')]
    debug = source/'tang/boards/neo/neo_gpu_debug.v'
    base = Path('/tmp/console-usb-sim-tools/extracted/usr')
    compiler = shutil.which('iverilog') or str(base/'bin/iverilog')
    flags = ['-B',str(base/'lib/x86_64-linux-gnu/ivl')] if not shutil.which('iverilog') else []
    vvp = shutil.which('vvp') or str(base/'bin/vvp')
    record['sources'] = {str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [debug,*gpu,out/'neo_gpu_debug_tb.sv',out/'neo_gpu_debug_accel_tb.sv']}
    try:
        with (out/'unit_build.log').open('w') as log:
            subprocess.run([compiler,*flags,'-g2012','-s','neo_gpu_debug_tb','-o',str(out/'unit.vvp'),
                str(out/'neo_gpu_debug_tb.sv'),str(debug)],stdout=log,stderr=log,check=True,timeout=60)
        for name,hp,mp,phase in [('nominal',6.25,6.667,.371),('drift',6.29,6.61,4.777),('125_124_5',4,4.016064,.213)]:
            run = subprocess.run([vvp,str(out/'unit.vvp'),f'+hp={hp}',f'+mp={mp}',f'+phase={phase}'],capture_output=True,text=True,timeout=30)
            (out/f'{name}.log').write_text(run.stdout+run.stderr)
            passed = run.returncode==0 and 'PASS:' in run.stdout
            record['cases'].append(dict(name=name,hp=hp,mp=mp,phase=phase,passed=passed))
            print(run.stdout.strip(),flush=True)
            if not passed:
                raise RuntimeError('Observer unit failure')
        obj=out/'obj'
        with (out/'accel_build.log').open('w') as log:
            subprocess.run(['verilator','--binary','--timing','-Wno-fatal','-j','2',
                '--top-module','neo_gpu_debug_accel_tb','--Mdir',str(obj),
                str(out/'neo_gpu_debug_accel_tb.sv'),str(debug),*map(str,gpu)],
                cwd=ROOT,stdout=log,stderr=log,check=True,timeout=240)
        run = subprocess.run([str(obj/'Vneo_gpu_debug_accel_tb')],cwd=ROOT,capture_output=True,text=True,timeout=30)
        (out/'accel.log').write_text(run.stdout+run.stderr)
        passed = run.returncode==0 and 'PASS:' in run.stdout
        record['cases'].append(dict(name='80_actual_gpu_configurations',passed=passed))
        print(run.stdout.strip(),flush=True)
        if not passed:
            raise RuntimeError('Observer GPU configurations failure')
        record['passed']=True
    finally:
        (out/'result.json').write_text(json.dumps(record,indent=2)+'\n')


if __name__=='__main__':
    main()
