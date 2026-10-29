#!/usr/bin/env python3
"""Exact R19 mapped TARGET/COPY descriptor/capture tests; no board or PnR."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BUILD = ROOT/'tang/impl/console_neo_n56r19_capture_ce_local'
sys.path.insert(0,str(ROOT/'tools'))
from gowin_toolchain import PRIMITIVES

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    out=HERE/'copy_mapped_01';out.mkdir()
    net=BUILD/'console_neo.vg'
    assert sha(net)=='dfac41d80eecaa0b6a3c152d36d8fcdb902060cecbd450647ede445d1c8004b6'
    allmods={m[1]:m[0] for m in re.finditer(r'^module (\w+)\b.*?^endmodule',net.read_text(),re.M|re.S)}
    needed={'gpu_geometry'}
    while True:
        calls=set().union(*(set(re.findall(r'^\s*(\w+)\s+\\?\S+\s*\(',allmods[n],re.M)) for n in needed))
        expanded=needed|(calls&allmods.keys())
        if expanded==needed:break
        needed=expanded
    mapped='\n\n'.join(allmods[n] for n in sorted(needed))+'\n'
    (out/'mapped.v').write_text(mapped)
    prim=PRIMITIVES.read_text();pm={m[1]:m[0] for m in re.finditer(r'^module (\w+)\b.*?^endmodule',prim,re.M|re.S)}
    pn={'GSR'}|(set(re.findall(r'^\s*(\w+)\s+\\?\S+\s*\(',mapped,re.M))&pm.keys())
    while True:
        calls=set().union(*(set(re.findall(r'^\s*(\w+)\s+\\?\S+\s*\(',pm[n],re.M)) for n in pn))
        expanded=pn|(calls&pm.keys())
        if expanded==pn:break
        pn=expanded
    (out/'primitives.v').write_text('`timescale 1ns/1ps\n'+'\n'.join(re.findall(r'^primitive .*?^endprimitive',prim,re.M|re.S))+'\n'+'\n'.join(pm[n] for n in sorted(pn)))
    # Reuse only the already-verified named port wiring, not any logic model.
    wiring=ROOT/'TESTS/neo_720p_20261012/local_capture_20261026/r20_config_01/tb.sv'
    tb=wiring.read_text().split('integer captures=0;')[0]
    declared=set(re.findall(r'^input (?:\[[^]]+\] )?(\w+);',allmods['gpu_geometry'],re.M))
    connected=set(re.findall(r'\.(\w+)\(',tb))
    assert declared<=connected, declared-connected
    cases=[]
    base=[0x1d000000,0x00808000,0x00100001,32,0,0,0x00100001,0]
    def case(name,changes,bad,empty=False):
        words=base.copy()
        for i,v in changes.items():words[i]=v
        cases.append(dict(name=name,words=words,bad=bad,empty=empty))
    case('canonical',{},0)
    case('unaligned_source',{1:0x00808002},1)
    case('width_zero',{2:0x00000001},1)
    case('width_1025',{2:0x04010001,3:2080},1)
    case('height_zero',{2:0x00100000},2)
    case('height_513',{2:0x00100201},2)
    case('stride_short',{3:16},2)
    case('stride_high_bits',{3:0x10020},2)
    case('reserved_word7',{7:1},4)
    case('source_end_overflow',{1:0x3fffffe0,2:0x00100002},4)
    case('overlap_wrong_base',{1:0x00800040},4)
    case('valid_overlap',{1:0x00800020,2:0x00800010,3:256},0)
    case('maximum_shape',{2:0x04000200,3:2048},0)
    case('empty_extent',{6:0},0,True)
    tb+='''
integer captures=0,checks=0,drop_capture=0,strict=0,rounds=0;
reg capture_expected;reg [223:0] expected_payload;
always @(posedge clk)begin
    capture_expected=child_resetn && dut.u_pixels.state[41] && dut.u_pixels.u_copy.state_0==0;
    expected_payload=dut.u_pixels.packet[255:32];
    if(capture_expected && strict && dut.u_pixels.u_copy.n7630_6!==1)
        $fatal(1,"COPY packet capture disabled");
    #1;
    if(capture_expected)begin
        captures=captures+1;
        if(!drop_capture && dut.u_pixels.u_copy.packet_0[255:32]!==expected_payload)
            $fatal(1,"COPY stored packet differs from actual input");
    end
end
task send(input [255:0] words);
 begin
    @(negedge clk);command=words;start=1;
    @(negedge clk);start=0;
    // The accepted words must be private, not sampled again later.
    command={8{32'hbaddcafe}};
 end
endtask
task reset_target;
 integer deadline;
 begin
    resetn=0;child_resetn=0;start=0;
    repeat(10)@(negedge clk);resetn=1;
    repeat(3)@(negedge clk);child_resetn=1;
    repeat(8)@(negedge clk);
    send(256'h0000000000000000000000000100010000800010008100000080002016000000);
    deadline=0;
    while(done!==1 && deadline<200)begin @(negedge clk);deadline++;end
    if(done!==1 || rejected!==0 || dut.shader_target_valid!==1)$fatal(1,"Real mapped TARGET failed");
    if(dut.u_pixels.u_copy.color_base!==30'h00800020 || dut.u_pixels.u_copy.color_end!==33'h00801020 ||
       dut.u_pixels.u_copy.color_stride!==256 || dut.u_pixels.u_copy.right!==128 || dut.u_pixels.u_copy.bottom!==16)
        $fatal(1,"Real mapped TARGET fields differ");
    repeat(8)@(negedge clk);
 end
endtask
task check_copy(input [255:0] words,input [2:0] bad,input empty);
 integer deadline,before_capture;
 begin
    before_capture=captures;
    send(words);deadline=0;
    while(done!==1 && copy_valid!==1 && deadline<300)begin @(negedge clk);deadline++;end
    if(deadline==300)$fatal(1,"COPY descriptor progress timeout");
    if(captures!=before_capture+1)$fatal(1,"COPY capture count");
    if(dut.u_pixels.u_copy.descriptor_bad!==bad)$fatal(1,"descriptor_bad actual=%b expected=%b case=%0d",dut.u_pixels.u_copy.descriptor_bad,bad,checks);
    if(bad!=0 || empty)begin
        if(done!==1 || rejected!==(bad!=0) || copy_valid || native_valid || cache_valid || fetch_valid)
            $fatal(1,"Rejected/empty COPY result differs case=%0d",checks);
    end else begin
        if(copy_valid!==1 || rejected!==0 || dut.u_pixels.u_copy.copy_bad || dut.u_pixels.u_copy.copy_write)
            $fatal(1,"Valid COPY did not issue first read case=%0d",checks);
        if(dut.u_pixels.u_copy.copy_addr!==words[61:37])$fatal(1,"First COPY read address differs");
    end
    checks++;
    $display("COPY_DESCRIPTOR case=%0d bad=%b empty=%b captures=%0d",checks,bad,empty,captures);
 end
endtask
initial begin
    if($value$plusargs("drop_capture=%d",drop_capture))begin end
    if($value$plusargs("strict=%d",strict))begin end
    if(drop_capture)begin
        reset_target();
        force dut.u_pixels.u_copy.n7630_6=1'b0;
        check_copy(256'h000000000010000100000000000000000000002000100001008080001d000000,3'b011,0);
        release dut.u_pixels.u_copy.n7630_6;
        $display("PASS MAPPED COPY NEGATIVE: missing first capture gives bad011 without memory request");
        $finish;
    end
    for(rounds=0;rounds<2;rounds++)begin
'''
    for c in cases:
        words=''.join(f'{w:08x}' for w in reversed(c['words']))
        tb+=f" reset_target(); check_copy(256'h{words},3'd{c['bad']},1'b{int(c['empty'])});\n"
    tb+='''
    end
    $display("PASS MAPPED COPY DESCRIPTORS checks=%0d captures=%0d",checks,captures);$finish;
end
initial begin #2000000;$fatal(1,"Bounded watchdog");end
endmodule
'''
    (out/'tb.sv').write_text(tb)
    tool=Path('/tmp/console-usb-sim-tools/extracted/usr')
    command=[str(tool/'bin/iverilog'),'-B',str(tool/'lib/x86_64-linux-gnu/ivl'),'-g2012','-s','tb','-o',str(out/'sim.vvp'),*[str(out/n) for n in ('tb.sv','mapped.v','primitives.v')]]
    result=dict(passed=False,hardware_access=False,netlist_sha256=sha(net),cases=cases,modules=sorted(needed),primitives=sorted(pn),
        module_sha256={n:hashlib.sha256(allmods[n].encode()).hexdigest() for n in needed},
        inputs={str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p):sha(p) for p in [Path(__file__),net,wiring,PRIMITIVES,out/'tb.sv',out/'mapped.v',out/'primitives.v']},
        scope='Exact mapped geometry/pixels/COPY+official primitives; real TARGET; descriptor first-request test only, no memory/slot/DDR/timing qualification',runs=[])
    try:
        with (out/'compile.log').open('x') as log:subprocess.run(command,stdout=log,stderr=log,check=True,timeout=180)
        for name,args,ok,signature in [('normal',[],True,'PASS MAPPED COPY DESCRIPTORS'),('missing_capture',['+drop_capture=1'],True,'PASS MAPPED COPY NEGATIVE'),('strict_missing_capture',['+drop_capture=1','+strict=1'],False,'COPY packet capture disabled')]:
            with (out/(name+'.log')).open('x') as log:
                p=subprocess.run([str(tool/'bin/vvp'),str(out/'sim.vvp'),*args],stdout=log,stderr=log,timeout=120)
            passed=(p.returncode==0)==ok and signature in (out/(name+'.log')).read_text()
            result['runs'].append(dict(name=name,returncode=p.returncode,expected_success=ok,passed=passed))
            assert passed,name
        result['passed']=True
    except Exception as exc:result['error']=repr(exc)
    finally:
        result['logs']={p.name:sha(p) for p in out.glob('*.log')}
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({k:result[k] for k in ('passed','runs','scope')}),flush=True)
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
