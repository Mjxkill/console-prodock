from pathlib import Path
import hashlib,json,re
R=Path('/home/michael/console'); O=Path(__file__).resolve().parent
builds=[R/'tang/impl/console_neo_n56r19_capture_ce_local/source',R/'tang/impl/console_neo_n56r21r1_capture_memory/source']
def block(text,start,end):
 a=text.index(start);z=text.index(end,a)+len(end);return text[a:z],text[:a].count('\n')+1,text[:z].count('\n')+1
proof=[];selections=[]
for b in builds:
 top=b/'tang/boards/neo/console_neo.v';soc=b/'tang/rtl/board/ae350_soc.v';t=top.read_text();s=soc.read_text()
 a=block(t,"    reg [1:0] ae350_rst_sync = 2'b11;",'    wire ae350_por_n = ~ae350_rst_sync[1];')
 c=block(t,'    wire trial_request, trial_mode, trial_holding, trial_done;','        .ahb_tick(trial_ahb_tick), .rtc_tick(trial_rtc_tick));')
 d=block(s,"    reg  [1:0] init_sync = 2'b00;",'    wire ae350_rstn = init_sync[1];')
 selections.append((a[0],c[0],d[0]))
 for p in [top,soc,b/'tang/boards/neo/neo_reset_trial.v',b/'tang/boards/neo/neo_reset_trial_rx.v']:
  proof.append(dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
 for name,item in [('top_reset',a),('trial_instance',c),('soc_reset',d)]:
  proof.append(dict(build=str(b.parent),fragment=name,line_start=item[1],line_end=item[2],fragment_sha256=hashlib.sha256(item[0].encode()).hexdigest()))
assert selections[0]==selections[1]
for name in ['neo_reset_trial.v','neo_reset_trial_rx.v']:
 bs=[(b/'tang/boards/neo'/name).read_bytes()for b in builds];assert bs[0]==bs[1];(O/name).write_bytes(bs[1])
a,c,d=selections[1]
h="""`timescale 1ns/1ps
`default_nettype none
// Exact extracted fabric reset blocks. NO hard CPU or PLL behavioral substitute.
module exact_soc_reset(input wire ahb_clk, rst_key_n, trial_release, output wire por_n);
"""+d+"\n    assign por_n=ae350_rstn;\nendmodule\n"+"""module exact_chain(input wire clk, bus80_clk, rtc_clk, pll_ae350_lock, ddr_init, uart_rx,
 output wire por_n, trial_done_o, trial_holding_o);
 wire ahb_clk=bus80_clk;
 wire [3:0] soc_dbg={3'b000,por_n}; // Only bit0 is consumed by exact trial instance.
"""+a+'\n'+c+"""
 exact_soc_reset u_soc(.ahb_clk(ahb_clk),.rst_key_n(ae350_por_n),.trial_release(trial_request),.por_n(por_n));
 assign trial_done_o=trial_done;
 assign trial_holding_o=trial_holding;
endmodule
`default_nettype wire
"""
(O/'exact_chain.sv').write_text(h)
r=dict(hardware_access=False,shared_sources_modified=False,r19_r21_reset_sources_equal=True,extraction='Verbatim procedural blocks and verbatim trial instance; only hierarchy/ports added; no functional CPU/PLL model',source_proof=proof,generated_sha256={n:hashlib.sha256((O/n).read_bytes()).hexdigest()for n in ['exact_chain.sv','neo_reset_trial.v','neo_reset_trial_rx.v']})
(O/'source_manifest.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items()if k!='source_proof'},indent=2))
