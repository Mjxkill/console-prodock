`timescale 1ns/1ps
module tb;reg clk=0,hclk=0,resetn=0;always #6.666 clk=~clk;always #6.25 hclk=~hclk;
gpu_v1 dut(.child_resetn({4{resetn}}),.clk(clk),.rst(!resetn),.start(1'b0),.command(256'd0),.ready(1'b0),.rd_valid(1'b0),.rd_data(256'd0));
integer ticks=0;always @(posedge clk)begin ticks++;if(ticks<4)$display("CLOCK time=%t",$time);end
initial begin #200;resetn=1;#800;$display("PASS TIME_ADVANCE ticks=%0d",ticks);$finish;end
endmodule
