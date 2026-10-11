`timescale 1ns/1ps
module gpu_geom_div_tb;
 reg clk=0,rst=1,start=0;always #5 clk=~clk;
 reg signed [63:0] a=0,b=1;wire busy,done,invalid;wire signed [63:0] q;
 gpu_geom_div dut(.clk(clk),.rst(rst),.start(start),.numerator(a),.denominator(b),.busy(busy),.done(done),.invalid(invalid),.quotient(q));
 task automatic check(input logic signed [63:0] aa,bb);
  logic bad;logic signed [63:0] refq;
  bad=bb==0||(aa==64'h8000000000000000&&bb==-64'sd1);refq=bad ? 0:aa/bb;
  @(negedge clk);a=aa;b=bb;start=1;@(negedge clk);start=0;
  while(!done)@(negedge clk);
  if(invalid!==bad||q!==refq)$fatal(1,"divide %0d / %0d = %0d expected %0d bad=%b",aa,bb,q,refq,invalid);
 endtask
 initial begin
  repeat(3)@(negedge clk);rst=0;
  check(0,1);check(-1,0);check(64'h8000000000000000,-1);check(64'h8000000000000000,1);
  check(64'h7fffffffffffffff,-1);check(64'h8000000000000000,64'h8000000000000000);
  for(integer i=0;i<2000;i++)check({$urandom,$urandom},i%4==0 ? $urandom:{$urandom,$urandom});
  @(negedge clk);a=77;b=3;start=1;@(negedge clk);start=0;repeat(4)@(negedge clk);rst=1;
  @(negedge clk);rst=0;repeat(40)begin @(negedge clk);if(done||busy)$fatal(1,"stale division after reset");end
  check(123456,123);$display("PASS 2007 signed divisions and reset cancellation");$finish;
 end
 initial begin #10000000;$fatal(1,"timeout");end
endmodule
