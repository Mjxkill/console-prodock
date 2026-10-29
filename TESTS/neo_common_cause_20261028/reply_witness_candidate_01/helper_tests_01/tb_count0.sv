`timescale 1ns/1ps
module tb;
 reg hclk=0,hreset=1,reply_valid=0,busy=1;reg [4:0] receive_index=0;
 reg [31:0] reply=1,completed_count=0;reg [7:0] address=8'hf0;
 wire read_hit;wire [31:0] read_data;GSR GSR(.GSRI(1'b1));
 neo_usb_reply_witness dut(.*);always #5 hclk=~hclk;
 initial begin
  repeat(2)@(negedge hclk);hreset=0;
  force dut.count0=32'hffffffff;
  reply_valid=1;receive_index=0;busy=1;
  @(posedge hclk);#1;release dut.count0;#1;
  if(dut.count0!==0 || read_data[6]!==1)$fatal(1,"overflow did not wrap/flag");
  @(negedge hclk);reply_valid=0;
  repeat(3)@(negedge hclk);
  if(read_data[6]!==1)$fatal(1,"overflow not sticky");
  hreset=1;@(posedge hclk);#1;if(read_data!==0)$fatal(1,"reset overflow");
  $display("PASS WITNESS OVERFLOW count0");$finish;
 end
endmodule
