`timescale 1ns/1ps
module tb;
 GSR GSR(.GSRI(1'b1));
 wire GND=0,VCC=1;
 reg gpu_clk=0,reset=1,enable=0;
 always #5 gpu_clk=~gpu_clk;
 reg [8:0] alpha=0, texture_alpha=0;
 wire [57:0] state={36'd0,enable,21'd0};
 wire [23:0] DOUT_17;
 wire [17:0] alpha_product;
 wire [23:0] observed={DOUT_17[23:17],alpha_product[16:7],DOUT_17[6:0]};
 wire n33072_6=texture_alpha[8];
 wire n1388_5=reset;
  MULT12X12 n18068_s (
    .DOUT({DOUT_17[23:17],alpha_product[16:7],DOUT_17[6:0]}),
    .A({GND,GND,GND,alpha[8:0]}),
    .B({GND,GND,GND,n33072_6,texture_alpha[7:4],texture_alpha[7:4]}),
    .CLK({GND,gpu_clk}),
    .CE({VCC,state[21]}),
    .RESET({GND,n1388_5}) 
);
defparam n18068_s.MULT_RESET_MODE="SYNC";
defparam n18068_s.OREG_CLK="CLK0";
defparam n18068_s.OREG_CE="CE0";
defparam n18068_s.OREG_RESET="RESET0";
defparam n18068_s.AREG_CLK="BYPASS";
defparam n18068_s.AREG_CE="CE0";
defparam n18068_s.AREG_RESET="RESET0";
defparam n18068_s.BREG_CLK="BYPASS";
defparam n18068_s.BREG_CE="CE0";
defparam n18068_s.BREG_RESET="RESET0";
defparam n18068_s.PREG_CLK="BYPASS";
defparam n18068_s.PREG_CE="CE0";
defparam n18068_s.PREG_RESET="RESET0";
 integer expected=0,checks=0;
 task check;
  @(posedge gpu_clk);#1;
  if(observed!==expected)$fatal(1,"Mapped alpha got %h expected %h",observed,expected);
  checks++;
 endtask
 initial begin
  check();@(negedge gpu_clk);reset=0;
  for(integer a=0;a<512;a++)for(integer t=0;t<16;t++)begin
   @(negedge gpu_clk);alpha=a;texture_alpha=t==15?256:t*17;enable=1;
   expected=a*(t==15?256:t*17);check();
   @(negedge gpu_clk);alpha=511-a;texture_alpha=0;enable=0;check();
   if(t==15 && a%64==0)begin
    @(negedge gpu_clk);reset=1;expected=0;check();
    @(negedge gpu_clk);reset=0;
   end
  end
  $display("PASS mapped alpha: %0d checks, exhaustive 8192 operand pairs, held enables and resets",checks);
  $finish;
 end
 initial begin #500000;$fatal(1,"Timeout");end
endmodule
