#!/usr/bin/env python3
"""Prepare a Neo-only copy of N56r8 with passive scanout observation.

No source used by either production board is edited. The original GPU debug
slave remains at 0xe9005000; a second snapshot slave is added at 0xe9006000.
No DDR source, timing exception, frequency or placement constraint changes.
"""
import hashlib
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PARENT = ROOT/'tang/impl/console_neo_n56r8_hdmi_sg4'
CANDIDATE = HERE/'scan_observer_candidate'
SHA = '51841fe4ae76a7eb635a0398534f35b6c7030fa8b768d88b892fede3b1601c35'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def replace(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Ambiguous insertion: '+old)
    return text.replace(old, new, 1)

MONITOR = '''// Passive Neo diagnostic. All event inputs use the DDR UI clock.
// accepted_by_arbiter counts enqueueing, NOT native DDR command acceptance.
`default_nettype none
module neo_scan_observe(
    input wire clk,resetn,
    input wire scan_valid,scan_ready,arb_valid,arb_ready,data_valid,
    input wire [28:0] arb_addr,
    input wire [95:0] state_words,
    output wire [255:0] live
);
    reg [1:0] up=0;
    always @(posedge clk or negedge resetn)
        if(!resetn)up<=0;else up<={up[0],1'b1};
    reg [31:0] accepted_by_queue=0,accepted_by_arbiter=0,returned=0;
    reg [28:0] last_address=0;
    always @(posedge clk)begin
        if(!up[1])begin
            accepted_by_queue<=0;accepted_by_arbiter<=0;
            returned<=0;last_address<=0;
        end else begin
            if(scan_valid && scan_ready)accepted_by_queue<=accepted_by_queue+1'b1;
            if(arb_valid && arb_ready)begin
                accepted_by_arbiter<=accepted_by_arbiter+1'b1;
                last_address<=arb_addr;
            end
            if(data_valid)returned<=returned+1'b1;
        end
    end
    assign live={24'h53434e,2'b0,scan_valid,scan_ready,arb_valid,arb_ready,data_valid,up[1],
        3'b0,last_address,returned,accepted_by_arbiter,accepted_by_queue,state_words};
endmodule
`default_nettype wire
'''

def transforms(original):
    edited = dict(original)
    name = 'tang/rtl/video/gpu_rgb_reader.v'
    text = replace(edited[name], 'output reg [255:0] block_data\n',
                   'output reg [255:0] block_data,\n    output wire [31:0] scan_debug_state\n')
    text = replace(text, 'endmodule\n', '''    // Explicit seven-bit slots also cover the 800-pixel profile.
    assign scan_debug_state[6:0]=last;
    assign scan_debug_state[13:7]=position;
    assign scan_debug_state[20:14]=issued;
    assign scan_debug_state[23:21]=state;
    assign scan_debug_state[31:24]=0;
endmodule
''')
    edited[name] = text
    name = 'tang/rtl/video/gpu_scanout.v'
    text = replace(edited[name], 'output wire [5:0] lcd_r, lcd_g, lcd_b\n',
                   'output wire [5:0] lcd_r, lcd_g, lcd_b,\n    output wire [95:0] scan_debug_state\n')
    text = replace(text, '.block_valid(rgb_block_valid),.block_index(rgb_block_index),.block_data(rgb_block_data));',
                   '.block_valid(rgb_block_valid),.block_index(rgb_block_index),.block_data(rgb_block_data),\n        .scan_debug_state(scan_debug_state[95:64]));')
    text = replace(text, 'endmodule\n', '''    // Every observed state below belongs to mem_clk. No feedback to GPU.
    assign scan_debug_state[31:22]=line_y;
    assign scan_debug_state[21:0]={fetch_valid,returned_valid,line_sprites,line_layers,
        line_half,line_rgb565,prefetch_active,cache_busy,done_pending,reader_done,
        reader_start,rgb_done,rgb_start,rgb_phase,dispatch_line,line_pending,
        acknowledge,1'b0,request_sync,mrst};
    assign scan_debug_state[63:32]=line_base;
endmodule
''')
    edited[name] = text
    name = 'tang/boards/neo/console_neo.v'
    text = replace(edited[name], '(selected[0] ? debug_hrdata:pad_hrdata)',
                   '(selected[1] ? scan_debug_hrdata:(selected[0] ? debug_hrdata:pad_hrdata))')
    text = replace(text, "(selected[0] ? debug_hready:1'b1)",
                   "(selected[1] ? scan_debug_hready:(selected[0] ? debug_hready:1'b1))")
    text = replace(text, '    wire [31:0] debug_hrdata;', '''    wire [31:0] scan_debug_hrdata;
    wire scan_debug_hready;
    wire [95:0] scan_debug_state;
    wire [255:0] scan_debug_live;
    neo_scan_observe u_scan_observe(.clk(gpu_clk),.resetn(vid_hrstn),
        .scan_valid(scan_valid),.scan_ready(scan_ready),
        .arb_valid(gpu_valid),.arb_ready(gpu_ready),.arb_addr(gpu_addr),
        .data_valid(gpu_data_valid),.state_words(scan_debug_state),.live(scan_debug_live));
    neo_gpu_debug u_scan_debug(.hclk(vid_hclk),.resetn(vid_hrstn),.mem_clk(gpu_clk),
        .hsel(bus_hsel && bus_haddr[14:12]==6),.hwrite(bus_hwrite),
        .htrans(bus_htrans),.haddr(bus_haddr),.hwdata(bus_hwdata),
        .hrdata(scan_debug_hrdata),.hready(scan_debug_hready),
        .host_accept(1'b0),.live(scan_debug_live),.observe_packet_words(64'd0));
    wire [31:0] debug_hrdata;''')
    text = replace(text, '.lcd_en(de),.lcd_hs(hs),.lcd_vs(vs),.lcd_r(red),.lcd_g(green),.lcd_b(blue));',
                   '.lcd_en(de),.lcd_hs(hs),.lcd_vs(vs),.lcd_r(red),.lcd_g(green),.lcd_b(blue),\n        .scan_debug_state(scan_debug_state));')
    edited[name] = text
    return edited

def main():
    assert sha(PARENT/'impl/pnr/console_neo.fs') == SHA
    old = json.loads((PARENT/'sources.json').read_text())
    actual = {str(p.relative_to(PARENT/'source')):sha(p) for p in (PARENT/'source').rglob('*') if p.is_file()}
    assert actual == old
    names = ['tang/rtl/video/gpu_rgb_reader.v','tang/rtl/video/gpu_scanout.v','tang/boards/neo/console_neo.v']
    originals = {n:(PARENT/'source'/n).read_text() for n in names}
    edited = transforms(originals)
    CANDIDATE.mkdir(exist_ok=False)
    shutil.copytree(PARENT/'source', CANDIDATE/'source')
    for n,text in edited.items():
        (CANDIDATE/'source'/n).write_text(text)
    (CANDIDATE/'source/tang/boards/neo/neo_scan_observe.v').write_text(MONITOR)
    new = {str(p.relative_to(CANDIDATE/'source')):sha(p) for p in (CANDIDATE/'source').rglob('*') if p.is_file()}
    assert sorted(n for n in old if old[n]!=new[n]) == sorted(names)
    assert set(new)-set(old) == {'tang/boards/neo/neo_scan_observe.v'}
    sys.path.insert(0,str(ROOT/'tools'))
    from check_ddr_profile import audit
    ddr = audit(CANDIDATE/'source',variant='neo-fifo-registers')
    assert ddr['passed']
    (CANDIDATE/'sources.json').write_text(json.dumps(new,indent=2)+'\n')
    record = dict(parent=str(PARENT),parent_bitstream_sha256=SHA,
        changed=names,added=['tang/boards/neo/neo_scan_observe.v'],ddr_profile=ddr,
        source_manifest_sha256=sha(CANDIDATE/'sources.json'),
        script_sha256=sha(Path(__file__)),hardware_access=False,
        mmio='0xe9006000',snapshot_words='0xe9006020..0xe900603c',
        words=['scanout flags and line_y','line_base','RGB last/position/issued/state',
            'reader requests accepted by queue','queue requests accepted by arbiter',
            'DDR returns tagged scanout','last arbiter-enqueued word address','SCN signature and handshakes'],
        limits=['No native DDR command counter: arbiter READY only acknowledges enqueueing.',
            'MMIO 0x10/0x14 and raw observation fields are inherited but not meaningful for scanout.',
            'Snapshot captures eight words atomically on mem_clk, then holds until acknowledged.',
            'Added loads and new synthesis/routing may change the reproduced failure.'])
    (CANDIDATE/'observation.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))

if __name__ == '__main__':
    main()
