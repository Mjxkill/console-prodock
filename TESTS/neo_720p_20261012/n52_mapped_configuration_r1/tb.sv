`timescale 1ns/1ps
module tb;
GSR GSR(.GSRI(1'b1));
reg clk=0,resetn=0,start=0;
always #5 clk=~clk;
reg [255:0] command=0;
wire done;
wire [3:0] requests;
wire [31:0] rejected,geometry_rejected;
gpu_geometry dut(
.gpu_clk(clk),
.v1_select(1'b1),
.v1_rx_valid(1'b0),
.v1_accepted(1'b1),
.ext_command(command[255:32]),
.gpu_debug_state_98(start),
.v1_rx_data(256'd0),
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
.gpu_debug_state_46(resetn),
.gpu_debug_state_48(resetn),
.gpu_debug_state_49(resetn),
.gpu_debug_state_50(resetn),
.gpu_debug_state_51(resetn),
.gpu_debug_state_52(resetn),
.gpu_debug_state_53(resetn),
.v1_done(done),
.v1_rejected(rejected),
.\geometry_stat[0] (geometry_rejected),
.native_valid(requests[0]),
.fetch_valid(requests[1]),
.copy_valid(requests[2]),
.cache_valid(requests[3]));
integer checks=0,timeout,rounds;
reg [31:0] rejected_before,geometry_before;
always @(negedge clk)
 if(resetn && requests !== 4'b0)$fatal(1,"Configuration issued memory request: %b",requests);
task check_config(input [255:0] words,input bad,input geometry_bad,input is_target);
begin
 @(negedge clk);command=words;
 rejected_before=rejected;geometry_before=geometry_rejected;
 repeat(4)@(negedge clk);
 start=1;@(negedge clk);start=0;
 timeout=0;
 while(!done && timeout<100)begin
  // The accepted packet must remain private and held during busy.
  command={8{32'hfedcba98 ^ timeout}};
  @(negedge clk);timeout++;
 end
 if(done!==1'b1 || rejected!==rejected_before+bad ||
    geometry_rejected!==geometry_before+geometry_bad)
  $fatal(1,"Configuration mismatch case %0d done=%b rejects=%0d/%0d geom=%0d/%0d",
      checks,done,rejected,rejected_before+bad,geometry_rejected,geometry_before+geometry_bad);
 if(is_target && dut.shader_target_valid !== !bad)
  $fatal(1,"Wrong TARGET validity case %0d",checks);
 checks++;
 repeat(5)@(negedge clk);
end
endtask
initial begin
 for(rounds=0;rounds<2;rounds++)begin
  resetn=0;start=0;
  repeat(10)@(negedge clk);
  resetn=1;repeat(10)@(negedge clk);
  if(rejected!==0 || geometry_rejected!==0 || dut.shader_target_valid!==0)
   $fatal(1,"Reset did not clear counters and descriptor validity");
 check_config(256'h0000000000000000000000000040004000200040120010001200000016000000,1'b0,1'b0,1'b1);
 check_config(256'h0000000000000000000000000800080004000200009000000080000016000000,1'b0,1'b0,1'b1);
 check_config(256'h0000000000000000000000000020002000080010000010000000000016000000,1'b0,1'b0,1'b1);
 check_config(256'h0000000000000000000000000020002000000010000010000000000016000000,1'b1,1'b0,1'b1);
 check_config(256'h0000000000000000000000000020002000080000000010000000000016000000,1'b1,1'b0,1'b1);
 check_config(256'h0000000000000000000000000020002000080010000010000000000116000000,1'b1,1'b0,1'b1);
 check_config(256'h0000000000000000000000000020002000080010000000030000000016000000,1'b1,1'b0,1'b1);
 check_config(256'h0000000000000000000000000020002000080010000000000000000016000000,1'b1,1'b0,1'b1);
 check_config(256'h0000000000000000000000000020002000200010000010000000000016000000,1'b1,1'b0,1'b1);
 check_config(256'h0000000000000000000000000020002000080010000010003fffffe016000000,1'b1,1'b0,1'b1);
 check_config(256'h0000000000000000000000000020002000080010001000000000000016000000,1'b0,1'b0,1'b1);
 check_config(256'h0000000000000000000000000040004000200040001000000000000016000000,1'b0,1'b0,1'b1);
 check_config(256'h00000000000000000000000003200320019000f0001000000000000016000000,1'b0,1'b0,1'b1);
 check_config(256'h0000000000000000000000000020002000080010009000000080000016000000,1'b0,1'b0,1'b1);
 check_config(256'h0000000000000000000000000040004000200040009000000080000016000000,1'b0,1'b0,1'b1);
 check_config(256'h00000000000000000000000003200320019000f0009000000080000016000000,1'b0,1'b0,1'b1);
 check_config(256'h0000000000000000000000000020002000080010101000001000000016000000,1'b0,1'b0,1'b1);
 check_config(256'h0000000000000000000000000040004000200040101000001000000016000000,1'b0,1'b0,1'b1);
 check_config(256'h00000000000000000000000003200320019000f0101000001000000016000000,1'b0,1'b0,1'b1);
 check_config(256'h0000000000000000000000000020002000080010121000001200000016000000,1'b0,1'b0,1'b1);
 check_config(256'h0000000000000000000000000040004000200040121000001200000016000000,1'b0,1'b0,1'b1);
 check_config(256'h00000000000000000000000003200320019000f0121000001200000016000000,1'b0,1'b0,1'b1);
 check_config(256'h0000000000000000000000000020002000080010201000002000000016000000,1'b0,1'b0,1'b1);
 check_config(256'h0000000000000000000000000040004000200040201000002000000016000000,1'b0,1'b0,1'b1);
 check_config(256'h00000000000000000000000003200320019000f0201000002000000016000000,1'b0,1'b0,1'b1);
 check_config(256'h0000000000000000000000000020002000080010301000003000000016000000,1'b0,1'b0,1'b1);
 check_config(256'h0000000000000000000000000040004000200040301000003000000016000000,1'b0,1'b0,1'b1);
 check_config(256'h00000000000000000000000003200320019000f0301000003000000016000000,1'b0,1'b0,1'b1);
 check_config(256'h0000000000000000000000000040004000200040120010001200000016000000,1'b0,1'b0,1'b1);
 check_config(256'h000000000000000000000000000000000000000000010000000000001f000000,1'b0,1'b0,1'b0);
 check_config(256'h000000000000000000000000000000000001000000000000000000011f000000,1'b0,1'b0,1'b0);
 check_config(256'h000000000000000000000000000100000000000000000000000000021f000000,1'b0,1'b0,1'b0);
 check_config(256'h000000000000000000000000000000000000000000000000000000031f000000,1'b1,1'b1,1'b0);
 check_config(256'h0000000000000000000000000000000000000100000000000000000021000000,1'b0,1'b0,1'b0);
 check_config(256'h000000000000000000000000000000000000000000000000000000001e000000,1'b0,1'b0,1'b0);
 check_config(256'h000000000000000000000000040201000000ffff000001000000000019000000,1'b0,1'b0,1'b0);
 check_config(256'h000000000000000000000000040201000000ffff000001010000000019000000,1'b1,1'b0,1'b0);
 check_config(256'h0000000000000000000000000000000000000020000100010170000018000000,1'b0,1'b0,1'b0);
 check_config(256'h000000000000000000000000000000000000000000000000000100001a000000,1'b0,1'b0,1'b0);
 check_config(256'h000000000000000000000000000000000000000000000000000000001e000000,1'b0,1'b0,1'b0);
 end
 $display("PASS mapped GPU configuration: %0d cases, 2 resets",checks);$finish;
end
initial begin #1000000;$fatal(1,"Watchdog");end
endmodule
