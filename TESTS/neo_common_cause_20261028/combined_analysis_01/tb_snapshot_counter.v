`timescale 1ns/1ps
module tb;
reg hclk=0, mem_clk=0, resetn=0;
always #5 hclk=~hclk;
always #7 mem_clk=~mem_clk;
reg hsel=0,hwrite=0,host_accept=0;
reg [1:0] htrans=0;
reg [31:0] haddr=0,hwdata=0;
reg [255:0] live=0;
wire [31:0] hrdata;
wire hready;
neo_gpu_debug dut(.hclk(hclk),.resetn(resetn),.mem_clk(mem_clk),
 .hsel(hsel),.hwrite(hwrite),.htrans(htrans),.haddr(haddr),.hwdata(hwdata),
 .hrdata(hrdata),.hready(hready),.host_accept(host_accept),.live(live),.observe_packet_words(64'd0));
task read_check;
 input [31:0] addr,want;
 begin
  @(negedge hclk);hsel=1;hwrite=0;htrans=2;haddr=addr;
  repeat(3) @(negedge hclk);
  if(hrdata!==want)begin $display("FAIL addr=%h got=%h want=%h",addr,hrdata,want);$fatal(1);end
  $display("READ addr=%h value=%h",addr,hrdata);
  hsel=0;htrans=0;
  repeat(3) @(negedge hclk);
 end
endtask
task capture;
 input [31:0] seq;
 integer n;
 begin
  @(negedge hclk);hsel=1;hwrite=1;htrans=2;haddr=4;hwdata=1;
  @(negedge hclk);hsel=0;htrans=0;
  @(negedge hclk);hwrite=0;hwdata=0;
  n=0;
  while(dut.sequence_id!==seq && n<100)begin @(negedge hclk);n=n+1;end
  if(n==100)$fatal(1,"snapshot timeout");
  read_check(4,6);read_check(12,seq);
 end
endtask
integer i;
initial begin
 repeat(8) @(negedge hclk);resetn=1;
 repeat(10) @(negedge hclk);
 capture(1);read_check(8,0);read_check(16,0);
 // Accepted host words and observed GPU words are distinct clock domains.
 for(i=0;i<8;i=i+1)begin @(negedge hclk);host_accept=1;end
 @(negedge hclk);host_accept=0;
 for(i=0;i<8;i=i+1)begin @(negedge mem_clk);live[36]=1;end
 @(negedge mem_clk);live[36]=0;live[15:0]=1;
 repeat(5) @(negedge hclk);
 read_check(8,8);read_check(16,0); // old capture: expected, not a lost word
 capture(2);read_check(8,8);read_check(16,8);read_check(32,1);
 capture(3);read_check(8,8);read_check(16,8);read_check(32,1);
 $display("PASS exact RTL shows live host and held received counter");$finish;
end
initial begin #100000;$fatal(1,"overall timeout");end
endmodule
