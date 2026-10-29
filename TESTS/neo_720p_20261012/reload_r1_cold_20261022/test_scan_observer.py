#!/usr/bin/env python3
"""Validate isolated instrumentation against exact pixels and a DDR stall."""
import json
from pathlib import Path
import subprocess
from prepare_scan_observer import ROOT, HERE, CANDIDATE, sha, replace

def main():
    out = HERE/'scan_observer_sim'
    out.mkdir(exist_ok=False)
    source = CANDIDATE/'source'
    tb = (ROOT/'TESTS/rtl/gpu_scanout_tb.sv').read_text()
    tb = replace(tb, '    always #14.285 pc=~pc;', '    always #6.722689 pc=~pc;')
    tb = replace(tb, '    wire [5:0] r,g,b;', '''    wire [5:0] r,g,b;
    wire qv,qr;
    wire [28:0] qa;
    wire [95:0] scan_words;
    wire [255:0] scan_live;
    neo_scan_queue queue(.clk(mc),.resetn(rst),.in_valid(fv),.in_ready(fr),.in_addr(fa),
        .out_valid(qv),.out_ready(qr),.out_addr(qa));
    neo_scan_observe monitor(.clk(mc),.resetn(rst),.scan_valid(fv),.scan_ready(fr),
        .arb_valid(qv),.arb_ready(qr),.arb_addr(qa),.data_valid(fdv),
        .state_words(scan_words),.live(scan_live));
    reg ds=0,dw=0;
    reg [31:0] da=0,dd=0;
    reg [1:0] dt=0;
    wire dr;
    wire [31:0] dout;
    neo_gpu_debug debug_slave(.hclk(hc),.resetn(rst),.mem_clk(mc),
        .hsel(ds),.hwrite(dw),.htrans(dt),.haddr(da),.hwdata(dd),
        .hrdata(dout),.hready(dr),.host_accept(1'b0),.live(scan_live),
        .observe_packet_words(64'd0));
    task debug_read(input [31:0] address,output [31:0] value);
        @(negedge hc);ds=1;dw=0;dt=2;da=address;
        @(negedge hc);ds=0;dt=0;
        if(dr!==0)$fatal(1,"Missing debug wait state");
        @(negedge hc);
        if(dr!==1)$fatal(1,"Debug read did not finish");
        value=dout;
    endtask
    reg [31:0] snap[0:7];
    task snapshot;
        reg [31:0] status;
        @(negedge hc);ds=1;dw=1;dt=2;da=4;
        @(negedge hc);ds=0;dt=0;dd=1;
        @(negedge hc);dw=0;
        repeat(20)@(negedge hc);
        debug_read(4,status);
        if(status!==6)$fatal(1,"Snapshot did not acknowledge %h",status);
        for(integer n=0;n<8;n++)debug_read(32+n*4,snap[n]);
        if(snap[7][31:8]!==24'h53434e)$fatal(1,"Wrong scan signature");
        if(snap[3]<snap[4] || snap[3]-snap[4]>2)$fatal(1,"Queue accounting incoherent");
        if(snap[4]<snap[5] || snap[4]-snap[5]>18)$fatal(1,"Arbiter accounting incoherent");
    endtask''')
    tb = replace(tb, '.lcd_en(de),.lcd_hs(hs),.lcd_vs(vs),.lcd_r(r),.lcd_g(g),.lcd_b(b));',
                 '.lcd_en(de),.lcd_hs(hs),.lcd_vs(vs),.lcd_r(r),.lcd_g(g),.lcd_b(b),.scan_debug_state(scan_words));')
    tb = replace(tb, '.g_valid(fv),.g_addr(fa),.g_ready(fr)', '.g_valid(qv),.g_addr(qa),.g_ready(qr)')
    tb = replace(tb, '        // Submit a flip during active pixels:', '''        snapshot();
        if(snap[3]==0 || snap[4]==0 || snap[5]==0)$fatal(1,"No traffic observed");
        $display("RUNNING queue=%0d arb=%0d returns=%0d",snap[3],snap[4],snap[5]);
        // Submit a flip during active pixels:''')
    tb = replace(tb, '        stalled=0;', '''        snapshot();
        if(snap[3]<=snap[5] || !snap[0][6])$fatal(1,"Stall not exposed by observer");
        if(snap[2][23:21]!==5)$fatal(1,"Expected blocked RGB PIPE state");
        if(snap[3]-snap[4]!=2 || snap[7][4]!==0)$fatal(1,"Queue should be full");
        $display("BLOCKED queue=%0d arb=%0d returns=%0d flags=%h rgb=%h",snap[3],snap[4],snap[5],snap[0],snap[2]);
        // A snapshot must remain stable while memory makes progress again.
        stalled=0;
        repeat(500)@(negedge mc);
        for(integer n=0;n<8;n++)begin
            debug_read(32+n*4,value);
            if(value!==snap[n])$fatal(1,"Snapshot changed before a new request");
        end''')
    tb = replace(tb, '        $finish;', '''        snapshot();
        if(snap[5]<=10000)$fatal(1,"Insufficient observed return traffic");
        $display("PASS: passive scanout observer, coherent counters, DDR stall localization and held snapshot");
        $finish;''')
    (out/'tb.sv').write_text(tb)
    files = [source/f'tang/rtl/video/{n}.v' for n in ('gpu_scanout','gpu_rgb_reader','gpu_line_reader','gpu_sprite_cache','gpu_tile_row')]
    files += [source/f'tang/rtl/board/{n}.v' for n in ('cdc_word','ddr_gpu_arb')]
    files += [source/f'tang/boards/neo/{n}.v' for n in ('neo_gpu_debug','neo_scan_queue','neo_scan_observe')]
    files += [out/'tb.sv']
    report = dict(passed=False,scope='Frozen candidate RTL, full 1280x720, CPU contention, DDR backpressure and prolonged stall; no PHY/SDF',
        sources_sha256={str(p):sha(p) for p in files},hardware_access=False)
    try:
        cmd = ['verilator','--binary','--timing','-Wno-fatal','-j','2','--top-module','gpu_scanout_tb',
            '--Mdir',str(out/'obj'),'-GW=1280','-GH=720','-GHT=1650','-GVT=750',
            '-GHSTART=260','-GVSTART=25','-GHSYNC=40','-GVSYNC=5','-GRGB=1',*map(str,files)]
        with (out/'build.log').open('w') as log:
            subprocess.run(cmd,stdout=log,stderr=log,check=True,timeout=240)
        run = subprocess.run([str(out/'obj/Vgpu_scanout_tb')],capture_output=True,text=True,timeout=180)
        (out/'run.log').write_text(run.stdout+run.stderr)
        report['returncode']=run.returncode
        report['passed']=run.returncode==0 and 'PASS: passive scanout observer' in run.stdout
        print(run.stdout,flush=True)
    finally:
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    if not report['passed']:
        raise SystemExit('Observer simulation failed')

if __name__ == '__main__':
    main()
