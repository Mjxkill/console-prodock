#!/usr/bin/env python3
"""Extend the proven mapped R15 packet replay with the actual inserted observer."""
from pathlib import Path
import argparse
import subprocess
import sys

HERE=Path(__file__).resolve().parent
PRIOR=HERE.parent/'reset_sequence_20261025'
ROOT=HERE.parents[2]

def replace(s,a,b):
    assert s.count(a)==1,a
    return s.replace(a,b,1)

def main():
    p=argparse.ArgumentParser();p.add_argument('--build',default='tang/impl/console_neo_n56r18_local_capture');p.add_argument('--out',default='integration_01')
    a=p.parse_args();assert a.out.replace('_','').isalnum()
    s=(PRIOR/'check_command_mapped.py').read_text()
    s=replace(s,'from load_r15 import HERE,ROOT,BUILD,preflight',
        'sys.path.insert(0,'+repr(str(PRIOR))+')\nfrom load_r15 import ROOT,preflight\nHERE=Path(__file__).resolve().parent\nBUILD=ROOT/'+repr(a.build))
    s=replace(s,"out=HERE/'command_mapped_02'","out=HERE/"+repr(a.out))
    s=replace(s,'    assert set(inputs)==set(values)',
        "    values.update(trace_resetn='resetn',trace_arm_req='cap_arm',trace_snap_req='cap_snap')\n    assert set(inputs)==set(values)")
    s=replace(s,'reg [255:0] command=0;',
        'reg [255:0] command=0;\nreg cap_arm=0,cap_snap=0;\nwire arm_ack,snap_ack,cap_ready,cap_beat;wire [63:0] cap_held;')
    s=replace(s,'.gpu_observe_packet_words(geometry_header),.gpu_observe_packet_words_113(pixel_header),',
        '.trace_arm_ack(arm_ack),.trace_snap_ack(snap_ack),.trace_ready(cap_ready),.trace_heartbeat(cap_beat),.trace_held(cap_held),\n.gpu_observe_packet_words(geometry_header),.gpu_observe_packet_words_113(pixel_header),')
    s=replace(s,'        before_bad=rejected;old_captures=captures;', '''        before_bad=rejected;old_captures=captures;
        @(negedge clk);cap_arm=~cap_arm;deadline=0;
        while(arm_ack!==cap_arm && deadline<20)begin @(negedge clk);deadline=deadline+1;end
        if(arm_ack!==cap_arm || cap_ready!==1)$fatal(1,"Observer arm failed");''')
    s=replace(s,'        repeat(5)@(negedge clk);', '''        repeat(5)@(negedge clk);
        cap_snap=~cap_snap;deadline=0;
        while(snap_ack!==cap_snap && deadline<20)begin @(negedge clk);deadline=deadline+1;end
        if(snap_ack!==cap_snap || cap_held[63:56]!==8'hc1 || (^cap_held)===1'bx)$fatal(1,"Observer snapshot failed");
        if(cap_held[54]!==cap_arm)$fatal(1,"Observer old epoch");
        if(forwards)begin
            if(cap_held[51:48]!==4'b0111 || cap_held[7:0]!==words[31:24] || cap_held[39:32]!==words[31:24] || cap_held[16]!==1 || cap_held[17]!==0)
                $fatal(1,"Actual FF observation mismatch header=%h trace=%h",words[31:0],cap_held);
        end else if(cap_held[51:48]!==4'b1000)$fatal(1,"Spurious observed pixel capture");
        $display("OBSERVER opcode=%h forwards=%0d trace=%h",words[31:0],forwards,cap_held);''')
    s=replace(s,'@(negedge clk);resetn=0;child_resetn=0;',
        '@(negedge clk);resetn=0;child_resetn=0;cap_arm=0;cap_snap=0;')
    target=HERE/(a.out+'_controller.py')
    with target.open('x') as f:f.write(s)
    subprocess.run([sys.executable,str(target)],cwd=ROOT,check=True)

if __name__=='__main__':main()
