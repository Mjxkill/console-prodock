`timescale 1ns/1ps
module tb;
reg clk=0,resetn=0,child_resetn=0,start=0;
reg [255:0] command=0;
reg cap_arm=0,cap_snap=0;
wire arm_ack,snap_ack,cap_ready,cap_beat;wire [63:0] cap_held;
wire [31:0] geometry_header,pixel_header,rejected;
wire done,native_valid,copy_valid,cache_valid,fetch_valid;
realtime half_period=6.6665,clock_phase=0,reset_offset=0;
initial begin
 if($value$plusargs("half=%f",half_period))begin end
 if($value$plusargs("phase=%f",clock_phase))begin end
 if($value$plusargs("reset_offset=%f",reset_offset))begin end
 #(clock_phase);forever #(half_period)clk=~clk;
end
GSR GSR(.GSRI(1'b1));
gpu_geometry dut(
.trace_resetn(resetn),
.trace_arm_req(cap_arm),
.trace_snap_req(cap_snap),
.gpu_clk(clk),
.v1_select(1'b1),
.v1_rx_valid(1'b0),
.v1_accepted(1'b1),
.ext_command(command[255:32]),
.gpu_debug_state_98(start),
.gpu_debug_state_104(command[24]),
.gpu_debug_state_105(command[25]),
.gpu_debug_state_106(command[26]),
.gpu_debug_state_107(command[27]),
.gpu_debug_state_108(command[28]),
.gpu_debug_state_109(command[29]),
.gpu_debug_state_110(command[30]),
.gpu_debug_state_111(command[31]),
.gpu_debug_state_224(command[0]),
.gpu_debug_state_225(command[1]),
.gpu_debug_state_226(command[2]),
.gpu_debug_state_227(command[3]),
.gpu_debug_state_228(command[4]),
.gpu_debug_state_229(command[5]),
.gpu_debug_state_230(command[6]),
.gpu_debug_state_231(command[7]),
.gpu_debug_state_232(command[8]),
.gpu_debug_state_233(command[9]),
.gpu_debug_state_234(command[10]),
.gpu_debug_state_235(command[11]),
.gpu_debug_state_236(command[12]),
.gpu_debug_state_237(command[13]),
.gpu_debug_state_238(command[14]),
.gpu_debug_state_239(command[15]),
.gpu_debug_state_240(command[16]),
.gpu_debug_state_241(command[17]),
.gpu_debug_state_242(command[18]),
.gpu_debug_state_243(command[19]),
.gpu_debug_state_244(command[20]),
.gpu_debug_state_245(command[21]),
.gpu_debug_state_246(command[22]),
.gpu_debug_state_247(command[23]),
.v1_rx_data(256'd0),
.gpu_debug_state_46(resetn),
.gpu_debug_state_48(child_resetn),
.gpu_debug_state_49(child_resetn),
.gpu_debug_state_50(child_resetn),
.gpu_debug_state_51(child_resetn),
.gpu_debug_state_52(child_resetn),
.gpu_debug_state_53(child_resetn),
.trace_arm_ack(arm_ack),.trace_snap_ack(snap_ack),.trace_ready(cap_ready),.trace_heartbeat(cap_beat),.trace_held(cap_held),
.gpu_observe_packet_words(geometry_header),.gpu_observe_packet_words_113(pixel_header),
.v1_done(done),.v1_rejected(rejected),.native_valid(native_valid),.copy_valid(copy_valid),.cache_valid(cache_valid),.fetch_valid(fetch_valid));


reg observer_arm=0,observer_snap=0;
wire observer_arm_ack,observer_snap_ack,observer_ready,observer_beat;
wire [63:0] observer_held;
wire [23:0] copy_sample={dut.u_pixels.u_copy.copy_done,dut.u_pixels.u_copy.copy_bad,
    (dut.u_pixels.u_copy.state_0==17),(dut.u_pixels.u_copy.state_0==1),
    (dut.u_pixels.u_copy.state_0==0),dut.u_pixels.state[41],!child_resetn,
    dut.u_pixels.u_copy.n7630_6,dut.u_pixels.u_copy.packet_0[87:80],dut.u_pixels.packet[87:80]};
wire [3:0] observer_events={2'b00,(native_valid|cache_valid|copy_valid),dut.u_pixels.native_issue};
// External observer has an isolated module name to coexist with the original
// observer already in the unmodified R19 netlist. The helper body is exact.
neo_capture_observed_test observer(.clk(clk),.resetn(resetn),.sample(copy_sample),
 .mem_events(observer_events),.arm_req(observer_arm),.snap_req(observer_snap),
 .arm_ack(observer_arm_ack),.snap_ack(observer_snap_ack),.ready(observer_ready),
 .heartbeat(observer_beat),.held(observer_held));
integer fault=0,checks=0;
task send(input[255:0]words);
 @(negedge clk);command=words;start=1;
 @(negedge clk);start=0;command={8{32'hbaddcafe}};
endtask
task arm_observer;
 integer n;
 @(negedge clk);observer_arm=~observer_arm;n=0;
 while(observer_arm_ack!==observer_arm && n<20)begin @(negedge clk);n++;end
 if(observer_arm_ack!==observer_arm)$fatal(1,"Observer ARM timeout");
endtask
task snapshot_observer;
 integer n;
 @(negedge clk);observer_snap=~observer_snap;n=0;
 while(observer_snap_ack!==observer_snap && n<20)begin @(negedge clk);n++;end
 if(observer_snap_ack!==observer_snap || observer_held[63:60]!==4'hd || (^observer_held)===1'bx)
  $fatal(1,"Observer SNAP timeout/unknown");
endtask
integer n;
reg[63:0]saved;
initial begin
 if($value$plusargs("fault=%d",fault))begin end
 repeat(10)@(negedge clk);resetn=1;repeat(3)@(negedge clk);child_resetn=1;
 repeat(8)@(negedge clk);
 send(256'h0000000000000000000000000100010000800010008100000080002016000000);
 n=0;while(done!==1 && n<200)begin @(negedge clk);n++;end
 if(done!==1 || rejected!==0 || dut.shader_target_valid!==1)$fatal(1,"Actual mapped TARGET failed");
 repeat(8)@(negedge clk);
 arm_observer();snapshot_observer();
 if(observer_held[51:48]!==8 || observer_held[59:56]!==0)$fatal(1,"Old events before COPY");checks++;
 if(fault==1)force dut.u_pixels.u_copy.n7630_6=0;
 if(fault==2)force dut.u_pixels.u_copy.packet_0[87:80]=0;
 if(fault==3)force dut.u_pixels.packet[87:80]=0;
 send(256'h000000000010000100000000000000000000002000100001008080001d000000);
 n=0;while(done!==1 && copy_valid!==1 && n<300)begin @(negedge clk);n++;end
 if(n==300)$fatal(1,"COPY did not reach descriptor result");
 // The source stimulus remains honest: faults are explicit mapped signal
 // injections, never presented as observations of hardware behavior.
 snapshot_observer();saved=observer_held;
 if(saved[51:48]!==7)$fatal(1,"Missing at/after capture %h",saved);checks++;
 if(saved[7:0] !== (fault==3 ? 8'h00:8'h10))$fatal(1,"Observed COPY D wrong");
 if(saved[31:24] !== (fault==3 ? 8'h00:8'h10))$fatal(1,"Observed after D wrong");
 if(saved[39:32] !== (fault==0 ? 8'h10:8'h00))$fatal(1,"Observed after Q wrong");
 if(saved[16] !== (fault!=1) || saved[18]!==1 || saved[19]!==1 || saved[17]!==0)
  $fatal(1,"Observed capture edge controls wrong");
 if(saved[59:56] !== (fault==0 ? 4'h2:4'h0))$fatal(1,"Producer sticky event wrong");
 if(fault==0)begin
  if(copy_valid!==1 || rejected!==0 || dut.u_pixels.u_copy.descriptor_bad!==0)$fatal(1,"Valid COPY result");
 end else begin
  if(done!==1 || rejected!==1 || dut.u_pixels.u_copy.descriptor_bad !== (fault==1 ? 3'b011:3'b001))
   $fatal(1,"Injected COPY fault result");
 end
 checks+=7;
 // Explicit held bus must survive an idle interval and repeated snapshot.
 repeat(20)@(negedge clk);if(observer_held!==saved)$fatal(1,"HELD spontaneous change");
 snapshot_observer();if(observer_held!==saved)$fatal(1,"Stable snapshot changed");checks+=2;
 arm_observer();snapshot_observer();
 if(observer_held[51:48]!==8)$fatal(1,"Re-arm replayed prior capture");checks++;
 $display("PASS MAPPED COPY OBSERVER fault=%0d checks=%0d trace=%h bad=%b",fault,checks,saved,dut.u_pixels.u_copy.descriptor_bad);
 $finish;
end
initial begin #1000000;$fatal(1,"Bounded mapped observer timeout");end
endmodule
