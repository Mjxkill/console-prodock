module probe(input wire clk, other, output wire led_n);
(* syn_preserve=1, syn_keep=1 *) reg toggle=0;
(* syn_preserve=1, syn_keep=1 *) reg stage1=0, stage2=0;
always @(posedge other) toggle <= !toggle;
always @(posedge clk) begin stage1<=toggle; stage2<=stage1; end
assign led_n=stage2;
endmodule
