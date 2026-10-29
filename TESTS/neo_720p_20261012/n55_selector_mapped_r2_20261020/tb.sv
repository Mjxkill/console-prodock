`timescale 1ns/1ps
module tb;
GSR GSR(.GSRI(1'b1));
reg clk=0,resetn=0;
reg [57:0] state=0;
wire actual;
reg wanted=0;
integer checks=0,r,s,repeat_count,n;
always #6.666 clk=~clk;
mapped_selector dut(.gpu_clk(clk),.gpu_debug_state_48(resetn),.state(state),.per_select(actual));
task tick;
begin
 @(posedge clk);
 if(!resetn || state[13])wanted=0;
 else if(state[26] || state[27] || state[55])wanted=~wanted;
 @(negedge clk);
 if(actual !== wanted)$fatal(1,"Selector differs at %0d: actual=%b expected=%b",checks,actual,wanted);
 checks++;
end
endtask
initial begin
 tick;
 // Priority, held state, consecutive advances, all three advance states.
 for(repeat_count=0;repeat_count<7;repeat_count++)for(r=0;r<2;r++)for(s=0;s<16;s++)begin
  resetn=r;state=0;state[13]=s&1;state[26]=(s>>1)&1;state[27]=(s>>2)&1;state[55]=(s>>3)&1;
  tick;tick;tick;
 end
 // Every new chunk starts at divider 0, including singleton/odd chunks.
 resetn=1;
 for(n=1;n<=17;n++)begin
  state=0;state[13]=1;tick;
  state=0;state[55]=1;repeat(n)tick;
 end
 // Reset or CHUNK dominates unknown private state.
 resetn=0;state='x;tick;
 resetn=1;state=0;state[13]=1;state[26]=1'bx;tick;
 $display("PASS: mapped perspective selector %0d checks",checks);$finish;
end
endmodule
