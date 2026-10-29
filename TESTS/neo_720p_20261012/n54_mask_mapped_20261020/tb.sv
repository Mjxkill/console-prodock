`timescale 1ns/1ps
module tb;
GSR GSR(.GSRI(1'b1));
reg clk=0, resetn=0, color_load=0, visible=0;
reg [57:0] state=0;
reg [3:0] lane=0;
wire [15:0] actual;
reg [15:0] wanted=0;
integer checks=0,rounds,r,s,c,l;
always #5 clk=~clk;
mapped_mask dut(.gpu_clk(clk),.gpu_debug_state_48(resetn),
 .color_load(color_load),.pixel_visible(visible),.state(state),.lane(lane),.pixel_written(actual));
task tick;
begin
 @(posedge clk);
 if(!resetn || state[13])wanted=0;
 else if(!color_load && visible && (state[26] || state[55]))wanted[lane]=1;
 @(negedge clk);
 if(actual !== wanted)$fatal(1,"Mask cone differs at %0d: actual=%h expected=%h",checks,actual,wanted);
 checks++;
end
endtask
initial begin
 tick;
 for(rounds=0;rounds<3;rounds++)for(r=0;r<2;r++)for(s=0;s<8;s++)
 for(c=0;c<4;c++)for(l=0;l<16;l++)begin
  resetn=r;state=0;state[13]=s&1;state[26]=(s>>1)&1;state[55]=(s>>2)&1;
  color_load=c&1;visible=(c>>1)&1;lane=l;
  tick;
 end
 // Reset/CHUNK must dominate unknown private data.
 resetn=0;state='x;lane='x;color_load=1'bx;visible=1'bx;tick;
 resetn=1;state=0;state[13]=1;tick;
 $display("PASS: mapped pixel mask %0d checks",checks);$finish;
end
endmodule
