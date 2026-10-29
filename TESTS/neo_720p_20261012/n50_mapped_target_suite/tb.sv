`timescale 1ns/1ps
module tb;
GSR GSR(.GSRI(1'b1));
reg clk=0,resetn=0,start=0;
always #5 clk=~clk;
reg [255:0] command=0;
wire done,target_valid,native_valid;
wire [31:0] rejected;
gpu_geometry dut(.gpu_clk(clk),
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
.gpu_debug_state_48(resetn),
.gpu_debug_state_49(resetn),
.gpu_debug_state_50(resetn),
.gpu_debug_state_51(resetn),
.gpu_debug_state_52(resetn),
.gpu_debug_state_53(resetn),
.v1_done(done),
.v1_rejected(rejected),
.native_valid(native_valid));
assign target_valid=dut.shader_target_valid;
integer checks=0,timeout;reg [31:0] rejected_before;
task check_target(input [255:0] words,input wanted);
begin
 @(negedge clk);command=words;rejected_before=rejected;
 repeat(4)@(negedge clk);start=1;@(negedge clk);start=0;
 timeout=0;
 while(!done && timeout<100)begin @(negedge clk);timeout++;
  if(native_valid!==1'b0)$fatal(1,"TARGET issued a DDR request");
 end
 $display("TARGET %0d done=%b valid=%b rejected=%0d bad=%b predicates=%b end=%h,%h width=%0d height=%0d",checks,done,target_valid,rejected,dut.u_pixels.bad_target,dut.u_pixels.target_bad,dut.u_pixels.color_end,dut.u_pixels.z_end,dut.u_pixels.width,dut.u_pixels.height);
 if(done!==1'b1 || target_valid!==wanted || rejected!==rejected_before+!wanted)
  $fatal(1,"Mapped geometry TARGET mismatch case %0d",checks);
 checks++;repeat(5)@(negedge clk);
end
endtask
initial begin
 repeat(10)@(negedge clk);resetn=1;repeat(10)@(negedge clk);
 check_target(256'h0000000000000000000000000040004000200040120010001200000016000000,1'b1);
 check_target(256'h0000000000000000000000000800080004000200009000000080000016000000,1'b1);
 check_target(256'h0000000000000000000000000020002000080010000010000000000016000000,1'b1);
 check_target(256'h0000000000000000000000000020002000000010000010000000000016000000,1'b0);
 check_target(256'h0000000000000000000000000020002000080000000010000000000016000000,1'b0);
 check_target(256'h0000000000000000000000000020002000080010000010000000000116000000,1'b0);
 check_target(256'h0000000000000000000000000020002000080010000000030000000016000000,1'b0);
 check_target(256'h0000000000000000000000000020002000080010000000000000000016000000,1'b0);
 check_target(256'h0000000000000000000000000020002000200010000010000000000016000000,1'b0);
 check_target(256'h0000000000000000000000000020002000080010000010003fffffe016000000,1'b0);
 check_target(256'h0000000000000000000000000020002000080010001000000000000016000000,1'b1);
 check_target(256'h0000000000000000000000000040004000200040001000000000000016000000,1'b1);
 check_target(256'h00000000000000000000000003200320019000f0001000000000000016000000,1'b1);
 check_target(256'h0000000000000000000000000020002000080010009000000080000016000000,1'b1);
 check_target(256'h0000000000000000000000000040004000200040009000000080000016000000,1'b1);
 check_target(256'h00000000000000000000000003200320019000f0009000000080000016000000,1'b1);
 check_target(256'h0000000000000000000000000020002000080010101000001000000016000000,1'b1);
 check_target(256'h0000000000000000000000000040004000200040101000001000000016000000,1'b1);
 check_target(256'h00000000000000000000000003200320019000f0101000001000000016000000,1'b1);
 check_target(256'h0000000000000000000000000020002000080010121000001200000016000000,1'b1);
 check_target(256'h0000000000000000000000000040004000200040121000001200000016000000,1'b1);
 check_target(256'h00000000000000000000000003200320019000f0121000001200000016000000,1'b1);
 check_target(256'h0000000000000000000000000020002000080010201000002000000016000000,1'b1);
 check_target(256'h0000000000000000000000000040004000200040201000002000000016000000,1'b1);
 check_target(256'h00000000000000000000000003200320019000f0201000002000000016000000,1'b1);
 check_target(256'h0000000000000000000000000020002000080010301000003000000016000000,1'b1);
 check_target(256'h0000000000000000000000000040004000200040301000003000000016000000,1'b1);
 check_target(256'h00000000000000000000000003200320019000f0301000003000000016000000,1'b1);
 check_target(256'h0000000000000000000000000040004000200040120010001200000016000000,1'b1);
 $display("PASS mapped geometry TARGET: %0d cases",checks);$finish;
end
initial begin #100000;$fatal(1,"Watchdog");end
endmodule
