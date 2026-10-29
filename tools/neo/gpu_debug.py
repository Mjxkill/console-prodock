"""Add observation-only GPU taps to an isolated Neo build, never shared RTL."""
import hashlib
import json
from pathlib import Path
import re


def local_reset_constraints(cst, netlist):
    """N34 experiment: move only the four observed GPU reset copies off LW.

    Refuse an unrecognized mapping. No change to functional RTL, clocks,
    pins or SDC; the final resource report must confirm the requested routing.
    """
    modules=re.findall(r'^module gpu_accel\b.*?^endmodule',netlist,re.M|re.S)
    if len(modules)!=1:
        raise ValueError('GPU reset experiment requires one mapped gpu_accel')
    for i in range(4):
        cells=re.findall(r'^\s*DFFCE engine_resetn_'+str(i)+r'_s0\s*\((.*?)\);',modules[0],re.M|re.S)
        if len(cells)!=1:
            raise ValueError('Unknown GPU reset driver')
        ports=dict(re.findall(r'\.(\w+)\(([^()]*)\)',cells[0]))
        if ports!=dict(Q=f'gpu_debug_state_{44+i}',D='gpu_debug_state_42',
                       CLK='gpu_clk',CLEAR='n1205_6',CE='VCC'):
            raise ValueError('GPU reset driver mapping changed')
    nets=[f'gpu_debug_state[{i}]' for i in range(44,48)]
    for net in nets:
        if re.search(r'CLOCK_LOC\s+"'+re.escape(net)+'"',cst):
            raise ValueError('Reset clock constraint already exists')
    return cst+'\n// Diagnostic: identical N34 netlist, GPU reset distribution only.\n'+''.join(
        f'CLOCK_LOC "{net}" LOCAL_CLOCK;\n' for net in nets),nets


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('GPU debug insertion missing/ambiguous: '+old)
    return text.replace(old, new, 1)


def instrument(source):
    source=Path(source)
    changed={}
    edits={
        'tang/rtl/video/blitter.v':[
            ('input  wire [7:0]  font_q\n', 'input  wire [7:0]  font_q,\n    output wire [95:0] debug_state\n'),
            ('endmodule\n', '    assign debug_state={st,wp,rp,op,rst,cmd_we,cmd_full,cmd_avail,ext_active,ext_start,ext_done,busy};\nendmodule\n')],
        'tang/rtl/video/gpu_accel.v':[
            ('input wire rd_valid\n', 'input wire rd_valid,\n    output wire [255:0] debug_state,\n    output wire debug_accept\n'),
            ('    wire [11:0] font_addr;', '    wire [95:0] debug_blitter;\n    wire [11:0] font_addr;'),
            ('.font_addr(font_addr), .font_q(font_q));', '.font_addr(font_addr), .font_q(font_q), .debug_state(debug_blitter));'),
            ('endmodule\n', '''    assign debug_accept=hresetn && bus_command && !queue_full;
    assign debug_state={ext_command[31:0],queue_data,debug_blitter,
        command_bad,command_lost,
        16'd0,engine_resetn,mrst,command_word,queue_valid,queue_pop,command_we,command_full,blitter_busy,ext_start,ext_active,
        16'd0,done_count};
endmodule
''')],
        'tang/boards/neo/console_neo.v':[
            ('selected[2] ? pad_hrdata:', 'selected[2] ? (selected[0] ? debug_hrdata:pad_hrdata):'),
            ("selected[2] ? 1'b1:", "selected[2] ? (selected[0] ? debug_hready:1'b1):"),
            ('    wire [31:0] pad_hrdata;', '''    wire [31:0] debug_hrdata;
    wire debug_hready;
    wire [255:0] gpu_debug_state;
    wire gpu_debug_accept;
    neo_gpu_debug u_gpu_debug(.hclk(vid_hclk),.resetn(vid_hrstn),.mem_clk(gpu_clk),
        .hsel(bus_hsel && bus_haddr[14:12]==5),.hwrite(bus_hwrite),
        .htrans(bus_htrans),.haddr(bus_haddr),.hwdata(bus_hwdata),.hrdata(debug_hrdata),.hready(debug_hready),
        .host_accept(gpu_debug_accept),.live(gpu_debug_state));
    wire [31:0] pad_hrdata;'''),
            ('.rd_data(blit_rd_data),.rd_valid(blit_rd_valid));', '.rd_data(blit_rd_data),.rd_valid(blit_rd_valid),\n        .debug_state(gpu_debug_state),.debug_accept(gpu_debug_accept));')]
    }
    # Optional Neo reset-tree experiment keeps the original four flags in
    # place and uses eight previously reserved bits for its extra drivers.
    if "reg [11:0] engine_resetn" in (source/'tang/rtl/video/gpu_accel.v').read_text():
        edits['tang/rtl/video/gpu_accel.v'] = [(old, new.replace(
            "16'd0,engine_resetn,mrst", "8'd0,engine_resetn,mrst"))
            for old, new in edits['tang/rtl/video/gpu_accel.v']]
    # Prepare all edits before writing any file; unsupported source is refused.
    prepared={}
    for rel, operations in edits.items():
        original=(source/rel).read_text();text=original
        for old,new in operations:text=replace_once(text,old,new)
        prepared[rel]=text
        changed[rel]=dict(before=hashlib.sha256(original.encode()).hexdigest(),
                          after=hashlib.sha256(text.encode()).hexdigest())
    for rel,text in prepared.items():(source/rel).write_text(text)
    (source/'tang/boards/neo/gpu_debug.json').write_text(json.dumps(dict(
        purpose='Observation only; no GPU feedback; Neo build copy only',
        mmio='0xe9005000',changed=changed),indent=2)+'\n')
    return changed
