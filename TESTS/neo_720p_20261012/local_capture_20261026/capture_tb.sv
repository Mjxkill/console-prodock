`timescale 1ns/1ps
module tb;
reg hclk=0,gclk=0,run_gpu=1,run_host=1,resetn=0;
real gh=6.6665;
always begin #6.25;if(run_host)hclk=~hclk;else hclk=0;end
always begin #(gh);if(run_gpu)gclk=~gclk;else gclk=0;end
reg hsel=0,hwrite=0;reg [1:0] htrans=0;reg [31:0] haddr=0,hwdata=0;
wire [31:0] legacy_data,hrdata;wire legacy_ready;
reg [7:0] d=0,q=0;reg ce=0,rst=0,start=0,idle=1,dwait=0,decode=0,bad=0,done=0,drop=0;
wire [23:0] sample={done,bad,decode,dwait,idle,start,rst,ce,q,d};
wire arm_req,snap_req,arm_ack,snap_ack,ready,heartbeat;wire [63:0] held;
neo_gpu_debug legacy(.hclk(hclk),.resetn(resetn),.mem_clk(gclk),.hsel(hsel),.hwrite(hwrite),
 .htrans(htrans),.haddr(haddr),.hwdata(hwdata),.hrdata(legacy_data),.hready(legacy_ready),
 .host_accept(1'b0),.live(256'd0),.observe_packet_words(64'd0));
neo_capture_bus bus(.clk(hclk),.resetn(resetn),.legacy_wait(!legacy_ready),
 .write_pending(legacy.bus_write),.write_bit(hwdata[0]),.write_addr(legacy.bus_addr),
 .read_addr(haddr[7:0]),.legacy_data(legacy_data),.hrdata(hrdata),
 .arm_req(arm_req),.snap_req(snap_req),.arm_ack(arm_ack),.snap_ack(snap_ack),
 .ready(ready),.heartbeat(heartbeat),.held(held));
neo_capture_local cap(.clk(gclk),.resetn(resetn),.sample(sample),
 .arm_req(arm_req),.snap_req(snap_req),.arm_ack(arm_ack),.snap_ack(snap_ack),
 .ready(ready),.heartbeat(heartbeat),.held(held));
`ifdef MAPPED
GSR GSR(.GSRI(1'b1));
`endif
always @(posedge gclk)if(rst)q<=0;else if(ce&&!drop)q<=d;
integer checks=0,scenario=0;
reg [31:0] value,status;reg [63:0] trace,first_trace;
reg [23:0] expected_at,expected_after;
task rd(input [7:0] addr,output [31:0] v);
 integer n;begin
  @(negedge hclk);hsel=1;hwrite=0;htrans=2;haddr={24'he90050,addr};
  @(negedge hclk);hsel=0;htrans=0;n=0;
  while(!legacy_ready && n<10)begin @(negedge hclk);n=n+1;end
  if(!legacy_ready)$fatal(1,"AHB stalled");
  v=hrdata;@(negedge hclk);
 end
endtask
task wr(input [7:0] addr);
 begin
  @(negedge hclk);hsel=1;hwrite=1;htrans=2;haddr={24'he90050,addr};hwdata=0;
  @(negedge hclk);hsel=0;hwrite=0;htrans=0;hwdata=1;
  @(negedge hclk);hwdata=0;
 end
endtask
task wait_idle;
 integer n;begin
  n=0;rd(8'h84,status);
  while(status[1:0]!==0 && n<100)begin rd(8'h84,status);n=n+1;end
  if(status[1:0]!==0 || (^status)===1'bx)$fatal(1,"Mailbox timeout/unknown scenario %0d",scenario);
 end
endtask
task arm;
 reg [31:0] old_count,new_count;begin
  rd(8'h88,old_count);wr(8'h84);wait_idle();if(status[6]!==0)$fatal(1,"Arm rejected");
  rd(8'h88,new_count);if((^old_count)===1'bx || new_count!==old_count+1)$fatal(1,"Arm counter stuck");
  if(status[5]!==new_count[0])$fatal(1,"Arm epoch mismatch");checks++;
 end
endtask
task snapshot;
 reg [31:0] low,high,old_seq,new_seq;begin
  rd(8'h8c,old_seq);wr(8'h88);wait_idle();if(status[3]!==1)$fatal(1,"Snapshot not valid");
  rd(8'h8c,new_seq);if((^old_seq)===1'bx || new_seq!==old_seq+1)$fatal(1,"Snapshot sequence stuck");
  rd(8'h90,low);rd(8'h94,high);trace={high,low};
  if(trace[63:56]!==8'hc1 || (^trace)===1'bx)$fatal(1,"Bad/unknown trace %h",trace);
  if(trace[54]!==status[5])$fatal(1,"Snapshot belongs to old arm epoch");checks++;
 end
endtask
task packet(input [7:0] data,input en,input reset,input drop_capture);
 begin
  @(negedge gclk);d=data;ce=en;rst=reset;drop=drop_capture;start=1;
  #0.1;expected_at=sample;
  @(negedge gclk);start=0;ce=0;dwait=1;#0.1;expected_after=sample;
  @(negedge gclk);dwait=0;rst=0;drop=0;
  repeat(3)@(negedge gclk);
 end
endtask
task verify_capture;
 begin
  snapshot();
  if(trace[23:0]!==expected_at || trace[47:24]!==expected_after || trace[51:48]!==4'b0111)
    $fatal(1,"Trace mismatch scenario=%0d got=%h at=%h after=%h",scenario,trace,expected_at,expected_after);
  if(trace[52]!==(expected_at[17]|expected_after[17]) || trace[53]!==(expected_at[16]|expected_after[16]))$fatal(1,"Sticky reset/CE evidence wrong");
  checks=checks+1;first_trace=trace;
  packet(8'hfa,1,0,0);snapshot();
  if(trace!==first_trace)$fatal(1,"Frozen trace overwritten");checks=checks+1;
 end
endtask
task sys_reset;
 begin
  resetn=0;start=0;ce=0;rst=0;drop=0;hsel=0;htrans=0;hwdata=0;
  repeat(5)@(negedge hclk);resetn=1;repeat(12)@(negedge hclk);
 end
endtask
integer k;
initial begin
 sys_reset();rd(0,value);if(value!==32'h4e474442)$fatal(1,"Legacy ID changed");checks++;
 rd(8'h80,value);if(value!==32'h4e435031)$fatal(1,"New ID missing");checks++;
 for(k=0;k<5;k=k+1)begin
  // 75 MHz nominal and differing frequency/phase; no common-edge assumption.
  case(k)0:gh=6.6665;1:gh=6.7;2:gh=6.61;3:gh=4.016;4:gh=4.000;endcase
  scenario=k*10;arm();packet(8'h16,1,0,0);verify_capture();
  scenario++;arm();packet(8'h21,0,0,0);verify_capture(); // CE missing
  scenario++;arm();packet(8'h16,1,1,0);verify_capture(); // synchronous reset wins
  scenario++;arm();packet(8'h07,1,0,1);verify_capture(); // Q fails to capture
  scenario++;arm();packet(8'h00,1,0,0);verify_capture(); // zero already present at D
  scenario++;arm();snapshot();if(trace[51:48]!==4'b1000)$fatal(1,"No-start reported as complete");checks++;
 end
 // No indefinite wait on AHB when GPU clock stops. Reject a second request.
 @(negedge gclk);run_gpu=0;wr(8'h84);rd(8'h84,status);
 if(status[0]!==1)$fatal(1,"Stopped clock arm lost");wr(8'h88);rd(8'h84,status);
 if(status[6]!==1||status[0]!==1||status[1]!==0)$fatal(1,"Busy request accepted");checks++;
 run_gpu=1;wait_idle();packet(8'h16,1,0,0);snapshot();if(trace[50]!==1)$fatal(1,"Restart lost capture");checks++;
 // Reset cancels in-flight mailbox; no old acknowledgement may replay it.
 @(negedge gclk);run_gpu=0;wr(8'h88);sys_reset();rd(8'h84,status);
 if(status[3:0]!==0)$fatal(1,"Stale mailbox after reset");checks++;
 run_gpu=1;repeat(16)@(negedge hclk);rd(8'h8c,value);
 if(value!==0)$fatal(1,"Old snapshot replayed");arm();snapshot();if(trace[51:48]!==4'b1000)$fatal(1,"Old capture replayed");checks++;
 // A snapshot can complete while AHB is idle and remains consistent across reads.
 arm();packet(8'h1c,1,0,0);snapshot();first_trace=trace;
 repeat(600)@(negedge gclk);snapshot();if(trace!==first_trace)$fatal(1,"Delayed snapshot differs");checks++;
 rd(8'h98,value);if(value===0 || (^value)===1'bx)$fatal(1,"Heartbeat absent/unknown");checks++;
 // HCLK may stop after a request: native capture and held response survive.
 wr(8'h88);@(negedge hclk);run_host=0;
 repeat(30)@(negedge gclk);run_host=1;wait_idle();
 rd(8'h90,value);if(value!==first_trace[31:0])$fatal(1,"Stopped HCLK snapshot low");
 rd(8'h94,value);if(value!==first_trace[63:32])$fatal(1,"Stopped HCLK snapshot high");checks++;
 // System reset while HCLK is stopped must cancel both sides, not replay
 // the old host request after release. The AHB address phase stays idle.
 wr(8'h88);@(negedge hclk);run_host=0;resetn=0;
 repeat(8)@(negedge gclk);resetn=1;repeat(16)@(negedge gclk);run_host=1;
 repeat(16)@(negedge hclk);rd(8'h84,status);
 if(status[3:0]!==4'b0100)$fatal(1,"Old host request survived reset");
 rd(8'h8c,value);if(value!==0)$fatal(1,"Snapshot replayed after HCLK reset");checks++;
 // Existing snapshot command 04 still works independently of the extension.
 rd(8'h0c,value);if(value!==0)$fatal(1,"Unexpected legacy sequence");
 wr(8'h04);repeat(24)@(negedge hclk);rd(8'h04,status);
 if(status[1:0]!==2'b10)$fatal(1,"Legacy snapshot did not complete");
 rd(8'h0c,value);if(value!==1)$fatal(1,"Legacy command 04 broken");
 rd(8'h8c,value);if(value!==0)$fatal(1,"Legacy command triggered new snapshot");checks++;
 rd(0,value);if(value!==32'h4e474442)$fatal(1,"Legacy passthrough broken");checks++;
 $display("PASS local capture checks=%0d",checks);$finish;
end
initial begin #1000000;$fatal(1,"Global test timeout");end
endmodule
