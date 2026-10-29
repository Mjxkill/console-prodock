#!/usr/bin/env python3
"""Replay actual config packets through frozen mapped geometry/pixels, no PNR."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from load_r15 import HERE,ROOT,BUILD,preflight
sys.path.insert(0,str(ROOT/'tools'))
from check_neo_fifo_mapped import module
from gowin_toolchain import PRIMITIVES
sys.path.insert(0,str(ROOT/'TESTS/neo_720p_20261012/n55_gpu_diagnosis_20261021'))
from probe_observer import suite

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    preflight()
    out=HERE/'command_mapped_02';out.mkdir(exist_ok=False)
    net=BUILD/'console_neo.vg';text=net.read_text()
    modules={m[1]:m[0] for m in re.finditer(r'^module (\w+)\b.*?^endmodule',text,re.M|re.S)}
    primitive_text=PRIMITIVES.read_text()
    pmods={m[1]:m[0] for m in re.finditer(r'^module (\w+)\b.*?^endmodule',primitive_text,re.M|re.S)}
    needed={'gpu_geometry'};prims={'GSR'}
    while True:
        kinds=set()
        for n in needed:kinds.update(re.findall(r'^\s*(\w+)\s+\\?\S+\s*\(',modules[n],re.M))
        expanded=needed|(kinds&modules.keys());prims|=kinds&pmods.keys()
        assert not (kinds-set(modules)-set(pmods)-{'module'}),kinds-set(modules)-set(pmods)-{'module'}
        if expanded==needed:break
        needed=expanded
    while True:
        kinds=set()
        for n in prims:kinds.update(re.findall(r'^\s*(\w+)\s+\\?\S+\s*\(',pmods[n],re.M))
        expanded=prims|(kinds&pmods.keys())
        if expanded==prims:break
        prims=expanded
    (out/'mapped.v').write_text('\n'.join(modules[n] for n in sorted(needed)))
    (out/'primitives.v').write_text('`timescale 1ns/1ps\n'+'\n'.join(re.findall(r'^primitive .*?^endprimitive',primitive_text,re.M|re.S))+'\n'+'\n'.join(pmods[n] for n in sorted(prims)))
    root=modules['gpu_geometry']
    inputs=re.findall(r'^input\s+(?:\[[^]]+\]\s+)?(\w+)\s*;',root,re.M)
    values={'gpu_clk':'clk','v1_select':"1'b1",'v1_rx_valid':"1'b0",'v1_accepted':"1'b1",'ext_command':'command[255:32]',
        'v1_rx_data':"256'd0",'gpu_debug_state_98':'start','gpu_debug_state_46':'resetn'}
    values.update({f'gpu_debug_state_{i}':'child_resetn' for i in range(48,54)})
    values.update({f'gpu_debug_state_{i}':f'command[{i-80}]' for i in range(104,112)})
    values.update({f'gpu_debug_state_{i}':f'command[{i-224}]' for i in range(224,248)})
    assert set(inputs)==set(values)
    tb='''`timescale 1ns/1ps
module tb;
reg clk=0,resetn=0,child_resetn=0,start=0;
reg [255:0] command=0;
wire [31:0] geometry_header,pixel_header,rejected;
wire done,native_valid,copy_valid,cache_valid,fetch_valid;
always #6.6665 clk=~clk;
GSR GSR(.GSRI(1'b1));
gpu_geometry dut(
'''+',\n'.join('.'+n+'('+values[n]+')' for n in inputs)+''',
.gpu_observe_packet_words(geometry_header),.gpu_observe_packet_words_113(pixel_header),
.v1_done(done),.v1_rejected(rejected),.native_valid(native_valid),.copy_valid(copy_valid),.cache_valid(cache_valid),.fetch_valid(fetch_valid));
integer captures=0;
reg [31:0] expected_header;
reg capture;
always @(posedge clk) begin
    capture=child_resetn && dut.shader_start && dut.u_pixels.state[0];
    expected_header=dut.shader_command[31:0];
    #1;
    if(capture) begin
        captures=captures+1;
        if(pixel_header!==expected_header)$fatal(1,"Mapped pixel capture failed expected=%h got=%h",expected_header,pixel_header);
        $display("CAPTURE cycle_time=%0t source=%h pixel=%h",$time,expected_header,pixel_header);
    end
    if(resetn && child_resetn && (native_valid || copy_valid || cache_valid || fetch_valid))$fatal(1,"Unexpected DDR command in config-only replay");
end
task run_packet(input [255:0] words,input integer expected_reject,input integer forwards);
    reg [31:0] before_bad;integer deadline;integer old_captures;
    begin
        before_bad=rejected;old_captures=captures;
        @(negedge clk);command=words;start=1;
        @(negedge clk);start=0;
        deadline=0;
        while(done!==1 && deadline<400)begin @(negedge clk);deadline=deadline+1;end
        if(done!==1)$fatal(1,"Mapped command timeout opcode=%h",words[31:0]);
        if(geometry_header!==words[31:0])$fatal(1,"Geometry header differs");
        if(forwards && pixel_header!==words[31:0])$fatal(1,"Pixel header differs");
        if(rejected-before_bad!==expected_reject)$fatal(1,"Rejection differs opcode=%h before=%0d after=%0d expected_delta=%0d",words[31:0],before_bad,rejected,expected_reject);
        if(captures-old_captures!=forwards)$fatal(1,"Unexpected number of captures");
        repeat(5)@(negedge clk);
    end
endtask
initial begin
    repeat(8)@(negedge clk);resetn=1;
    repeat(6)@(negedge clk);child_resetn=1;
    repeat(8)@(negedge clk);
'''
    cases=[c for c in suite() if c['words'][0]>>24>=22]
    calls=''
    for c in cases:
        value=sum(w<<(i*32) for i,w in enumerate(c['words']))
        calls+=f'    run_packet(256\'h{value:064x},{int(not c["accepted"])},{int(c["words"][0]>>24<31)}); // {c["name"]}\n'
    # Synthesized aliases shader_command[29:30] are dangling, because their
    # destinations are tied to GND. Observe the actual D pin of every packet
    # FF rather than an unused alias of the original RTL bus.
    actual_d=[]
    for i in reversed(range(32)):
        instance=re.search(r'\bDFFRE packet_'+str(i)+r'_s0\s*\((.*?)\);',modules['gpu_v1'],re.S)
        assert instance
        signal=re.search(r'\.D\(([^)]+)\)',instance[1])[1].strip()
        assert re.fullmatch(r'\w+',signal),signal
        actual_d.append('dut.u_pixels.'+signal)
    tb=tb.replace('expected_header=dut.shader_command[31:0];','expected_header={'+','.join(actual_d)+'};')
    tb+=calls+'''    @(negedge clk);resetn=0;child_resetn=0;
    repeat(8)@(negedge clk);
    resetn=1;child_resetn=1;
    repeat(8)@(negedge clk);
'''+calls+'''    $display("PASS mapped command replay including warm reset, captures=%0d",captures);
    $finish;
end
initial begin #1000000;$fatal(1,"Global timeout");end
endmodule
'''
    (out/'tb.sv').write_text(tb)
    result=dict(passed=False,scope='Official functional primitive models, actual frozen mapped geometry and pixels; no SDF, no metastability or hardware inference',netlist_sha256=sha(net),primitive_library_sha256=sha(PRIMITIVES),modules=sorted(needed),primitives=sorted(prims),case_count=len(cases)*2)
    compiler=Path('/tmp/console-usb-sim-tools/extracted/usr/bin/iverilog')
    try:
        with (out/'compile.log').open('x') as log:
            subprocess.run([str(compiler),'-B',str(compiler.parent.parent/'lib/x86_64-linux-gnu/ivl'),'-g2012','-s','tb','-o',str(out/'sim.vvp'),*[str(out/n) for n in ('tb.sv','mapped.v','primitives.v')]],stdout=log,stderr=log,check=True,timeout=90)
        with (out/'simulation.log').open('x') as log:
            subprocess.run([str(compiler.parent/'vvp'),str(out/'sim.vvp')],stdout=log,stderr=log,check=True,timeout=120)
        result['passed']='PASS mapped command replay' in (out/'simulation.log').read_text()
    except Exception as exc:result['error']=repr(exc)
    finally:
        result['inputs']={str(p):sha(p) for p in [Path(__file__),out/'tb.sv',out/'mapped.v',out/'primitives.v']}
        result['logs']={p.name:sha(p) for p in out.glob('*.log')}
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result),flush=True)
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
