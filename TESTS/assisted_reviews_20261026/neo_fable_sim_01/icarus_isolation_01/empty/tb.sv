`timescale 1ns/1ps
module tb;reg clk=0,hclk=0,resetn=0;always #6.666 clk=~clk;always #6.25 hclk=~hclk;

integer ticks=0;always @(posedge clk)begin ticks++;if(ticks<4)$display("CLOCK time=%t",$time);end
initial begin #200;resetn=1;#800;$display("PASS TIME_ADVANCE ticks=%0d",ticks);$finish;end
endmodule
