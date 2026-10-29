#!/usr/bin/env python3
"""Mapped pixel CLEAR replay with backpressure, byte masks, and diagnostic wires."""
import json
from pathlib import Path
import re
import shutil
import subprocess
from prepare_memory_observer import HERE, ROOT, sha, HANDSHAKES, block, pins
from format_memory_observer import DEST as BUILD

def main():
    prior=HERE/'r20r1_config_01/result.json';p=json.loads(prior.read_text())
    net=BUILD/'console_neo.vg';assert p['passed'] and p['netlist_sha256']==sha(net)
    for name,h in p['inputs'].items():assert sha(Path(name))==h,name
    out=HERE/'r20r1_memory_sim_01';out.mkdir(exist_ok=False)
    s=net.read_text();obs=json.loads((BUILD/'observation.json').read_text())
    # Independent checks: only the diagnostic instance gets these 128 rewires.
    top=block(s,'console_neo');ports=pins(top,'u_gpu_debug')
    for n,v in obs['debug_port_rewires'].items():assert ports[n]==v,n
    assert pins(top,'u_accel')['diag_pixels']=='diag_pixels[63:0]'
    assert pins(top,'u_accel')['diag_handshake']=='diag_handshake[15:0]'
    for name,child in [('gpu_accel','u_v1'),('gpu_geometry','u_pixels')]:
        assert pins(block(s,name),child)['diag_pixels']=='diag_pixels[63:0]'
    accel=block(s,'gpu_accel')
    for i,signal in enumerate(HANDSHAKES):assert f'assign diag_handshake[{i}] = {signal};' in accel
    pixel=block(s,'gpu_v1')
    for i,signal in enumerate(obs['scalar_pixel_signals_lsb_first']):assert f'assign diag_pixels[{i}] = {signal};' in pixel
    for n in ('mapped.v','primitives.v'):shutil.copy2(prior.parent/n,out/n)
    tb=(prior.parent/'tb.sv').read_text().split('integer captures=0;')[0]
    assert tb.count('.v1_accepted(1\'b1)')==1
    tb=tb.replace(".v1_accepted(1'b1)",'.v1_accepted(accepted)')
    tb=tb.replace('reg [255:0] command=0;','reg [255:0] command=0;\nreg accepted=0;wire [63:0] diag_pixels;')
    tb=tb.replace('.fetch_valid(fetch_valid));','.fetch_valid(fetch_valid),.diag_pixels(diag_pixels));')
    tb+='''
reg pending=0;
reg [27:0] slot_addr;
reg [255:0] slot_data;
reg [31:0] slot_mask;
reg slot_write;
integer tick=0,hold_cycles=0,stall_cycles=0,bursts=0,total_bursts=0,checks=0;
wire grant=hold_cycles==0 && tick%7>=2;
reg [7:0] mem_color[0:4095],mem_depth[0:4095];
integer k,offset;
always @(posedge clk) begin
    tick<=tick+1;
    if(hold_cycles>0)hold_cycles<=hold_cycles-1;
    if(!resetn || !child_resetn)begin accepted<=0;pending<=0;end
    else begin
        accepted<=pending && grant;
        if(pending)begin
            if(grant)begin
                if(slot_write!==1 || slot_addr[2:0]!==0)$fatal(1,"Invalid native write");
                for(k=0;k<32;k=k+1)if(!slot_mask[k])begin
                    if(slot_addr>=28'h4800000 && slot_addr<28'h4800400)begin
                        offset=(slot_addr-28'h4800000)*4+k;mem_color[offset]=slot_data[k*8+:8];
                    end else if(slot_addr>=28'h4804000 && slot_addr<28'h4804400)begin
                        offset=(slot_addr-28'h4804000)*4+k;mem_depth[offset]=slot_data[k*8+:8];
                    end else $fatal(1,"Native address outside guarded model: %h",slot_addr);
                end
                pending<=0;bursts=bursts+1;total_bursts=total_bursts+1;
            end else stall_cycles=stall_cycles+1;
        end else if(native_valid && !accepted)pending<=1;
        if(!pending)begin
            slot_addr<={dut.u_pixels.native_addr[27:3],3'b0};
            slot_data<=dut.u_pixels.native_data;slot_mask<=dut.u_pixels.native_mask;
            slot_write<=dut.u_pixels.native_write;
        end
    end
    #1;
    if(resetn && child_resetn)begin
        if((^diag_pixels)===1'bx)$fatal(1,"Unknown diagnostic field");
        if(diag_pixels[57:0]!==dut.u_pixels.state)$fatal(1,"FSM wiring");
        if(diag_pixels[58]!==dut.u_pixels.native_valid_s1.D ||
           diag_pixels[59]!==dut.u_pixels.native_valid_s1.CE ||
           diag_pixels[60]!==dut.u_pixels.native_valid_s1.RESET)$fatal(1,"Actual native FF pin mapping");
        if(copy_valid || cache_valid || fetch_valid)$fatal(1,"Unexpected reader in CLEAR replay");
    end
end
task packet(input [255:0] words);
    integer deadline;
    reg [31:0] before_bad;
    begin
        before_bad=rejected;
        @(negedge clk);command=words;start=1;
        @(negedge clk);start=0;deadline=0;
        while(done!==1 && deadline<4000)begin @(negedge clk);deadline=deadline+1;end
        if(done!==1)$fatal(1,"CLEAR replay timeout, opcode=%h state=%h",words[31:0],diag_pixels);
        if(rejected!==before_bad)$fatal(1,"Unexpected reject");
        repeat(8)@(negedge clk);
        if(pending || accepted || native_valid)$fatal(1,"Pending or duplicate write after completion");
    end
endtask
task clear_test(input integer flags,x,y,w,h,expected_bursts);
    integer i,px,py;reg [255:0] words;reg [15:0] c,z;
    begin
        for(i=0;i<4096;i=i+1)begin mem_color[i]=(i*37+19)&255;mem_depth[i]=(i*53+41)&255;end
        bursts=0;hold_cycles=60;
        words=0;words[31:0]=32'h1c000000;words[63:32]=flags;
        words[95:64]=32'h5aa5;words[127:96]=32'h7bde;
        words[159:128]=(x<<16)|y;words[191:160]=(w<<16)|h;
        packet(words);
        if(bursts!=expected_bursts)$fatal(1,"Wrong burst count flags=%0d got=%0d expected=%0d",flags,bursts,expected_bursts);
        for(py=0;py<16;py=py+1)for(px=0;px<128;px=px+1)begin
            i=py*256+px*2;
            c=(((i+1)*37+19)&255)<<8 | ((i*37+19)&255);
            z=(((i+1)*53+41)&255)<<8 | ((i*53+41)&255);
            if(px>=x && px<x+w && py>=y && py<y+h)begin
                if(flags&1)c=16'h5aa5;if(flags&2)z=16'h7bde;
            end
            if({mem_color[i+1],mem_color[i]}!==c || {mem_depth[i+1],mem_depth[i]}!==z)
                $fatal(1,"Pixel/mask mismatch xy=%0d,%0d flags=%0d",px,py,flags);
            checks=checks+2;
        end
        $display("CLEAR flags=%0d xy=%0d,%0d wh=%0d,%0d bursts=%0d",flags,x,y,w,h,bursts);
    end
endtask
integer repeat_index;
initial begin
    for(repeat_index=0;repeat_index<2;repeat_index=repeat_index+1)begin
        resetn=0;child_resetn=0;
        repeat(8)@(negedge clk);resetn=1;
        repeat(6)@(negedge clk);child_resetn=1;
        repeat(8)@(negedge clk);
        packet({96'd0,32'h01000100,32'h00800010,32'h12010000,32'h12000000,32'h16000000});
        clear_test(0,0,0,16,1,0);
        clear_test(3,0,0,0,0,0);
        clear_test(1,0,0,16,1,1);
        clear_test(2,0,0,16,1,1);
        clear_test(3,3,2,19,2,8);
        clear_test(3,0,0,128,16,256);
    end
    if(stall_cycles<50 || total_bursts!=532)$fatal(1,"Insufficient backpressure coverage");
    $display("PASS mapped CLEAR observer checks=%0d bursts=%0d stalls=%0d",checks,total_bursts,stall_cycles);
    $finish;
end
initial begin #1000000;$fatal(1,"Global timeout");end
endmodule
'''
    (out/'tb.sv').write_text(tb)
    result=dict(passed=False,netlist_sha256=sha(net),config_proof_sha256=sha(prior),
        scope='Exact mapped geometry/pixels, official primitive functional models; RTL model of registered memory slot, no routed-delay or DDR PHY qualification',
        observation_rewired_inputs=128,application_primitives_added=0)
    compiler=Path('/tmp/console-usb-sim-tools/extracted/usr/bin/iverilog')
    try:
        with (out/'compile.log').open('x') as log:
            subprocess.run([str(compiler),'-B',str(compiler.parent.parent/'lib/x86_64-linux-gnu/ivl'),'-g2012','-s','tb','-o',str(out/'sim.vvp'),*[str(out/n) for n in ('tb.sv','mapped.v','primitives.v')]],stdout=log,stderr=log,check=True,timeout=90)
        with (out/'simulation.log').open('x') as log:
            subprocess.run([str(compiler.parent/'vvp'),str(out/'sim.vvp')],stdout=log,stderr=log,check=True,timeout=120)
        result['passed']='PASS mapped CLEAR observer' in (out/'simulation.log').read_text()
    except Exception as exc:result['error']=repr(exc)
    finally:
        result['inputs']={str(f):sha(f) for f in [Path(__file__),net,BUILD/'observation.json',prior,out/'tb.sv',out/'mapped.v',out/'primitives.v']}
        result['logs']={f.name:sha(f) for f in out.glob('*.log')}
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
