`timescale 1ns/1ps
module tb;reg clk=0,hclk=0,resetn=0;always #6.666 clk=~clk;always #6.25 hclk=~hclk;
gpu_accel #(.FONT_FILE("font8x16.hex")) dut(.hclk(hclk),.hresetn(resetn),.hsel(1'b0),.hwrite(1'b0),.haddr(32'd0),.hwdata(32'd0),.htrans(2'd0),.mem_clk(clk),.ready(1'b0),.rd_data(256'd0),.rd_valid(1'b0));
integer ticks=0;always @(posedge clk)begin ticks++;if(ticks<4)$display("CLOCK time=%t",$time);end
initial begin #200;resetn=1;#800;$display("PASS TIME_ADVANCE ticks=%0d",ticks);$finish;end
endmodule
