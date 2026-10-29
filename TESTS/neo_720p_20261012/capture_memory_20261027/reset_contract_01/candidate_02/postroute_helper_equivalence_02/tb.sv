`timescale 1ns/1ps
module tb;
reg a,b,c,d;wire s0,k0,s1,k1,ni,nl,wrong_s,wrong_k;
integer i,j,n,binary=0,four_differences=0,negative=0;
reg [1:0] vals[0:3];
ALU #(.ALU_MODE(0)) first(.I0(a),.I1(b),.I3(d),.CIN(c),.SUM(s0),.COUT(k0));
ALU #(.ALU_MODE(0)) swapped(.I0(b),.I1(a),.I3(d),.CIN(c),.SUM(s1),.COUT(k1));
ALU #(.ALU_MODE(1)) wrong_mode(.I0(a),.I1(b),.I3(d),.CIN(c),.SUM(wrong_s),.COUT(wrong_k));
INV inv(.I(a),.O(ni));LUT1 #(.INIT(2'h1)) lut(.I0(a),.F(nl));
function state;input integer v;begin case(v)0:state=0;1:state=1;2:state=1'bx;3:state=1'bz;endcase end endfunction
initial begin
 for(i=0;i<16;i=i+1)begin {a,b,c,d}=i;#1;
  if({s0,k0} !== {s1,k1})$fatal(1,"BINARY_ADD_MISMATCH %d",i);
  if(ni!==nl)$fatal(1,"INVERTER_MISMATCH");
  if({s0,k0} !== {wrong_s,wrong_k})negative=negative+1;
  binary=binary+1;
 end
 for(i=0;i<4;i=i+1)begin a=state(i);#1;if(ni!==nl)$fatal(1,"FOUR_STATE_INV");end
 for(i=0;i<4;i=i+1)for(j=0;j<4;j=j+1)begin
  a=state(i);b=0;c=state(j);d=1;#1;
  if({s0,k0} !== {s1,k1})begin four_differences=four_differences+1;$display("XPROP_DIFFERENCE data=%b carry=%b original=%b routed=%b",a,c,{s0,k0},{s1,k1});end
 end
 if(negative==0)$fatal(1,"NEGATIVE_CONTROL_INEFFECTIVE");
 $display("PASS BINARY_CASES=%0d INV_4STATE=4 NEGATIVE=%0d XPROP_DIFFERENCES=%0d",binary,negative,four_differences);$finish;
end
endmodule
