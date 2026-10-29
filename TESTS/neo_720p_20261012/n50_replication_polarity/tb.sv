`timescale 1ns/1ps
module tb;
reg clk=0,resetn=0,ext_active=0,select_d=0;
always #5 clk=~clk;
wire original_q,copy_q,idle_enable,reset_high;
GSR GSR(.GSRI(1'b1));
DFFRE \u_accel/v1_select_s0  (
	.D(select_d),
	.CLK(clk),
	.CE(idle_enable),
	.RESET(reset_high),
	.Q(original_q)
);
defparam \u_accel/v1_select_s0 .INIT=1'b0;
DFFRE \u_accel/gowin_replicate_reg_v1_select_1  (
	.D(select_d),
	.CLK(clk),
	.CE(ext_active),
	.RESET(resetn),
	.Q(copy_q)
);
defparam \u_accel/gowin_replicate_reg_v1_select_1 .INIT=1'b0;
INV \u_accel/n249_s2  (
	.I(resetn),
	.O(reset_high)
);
INV \u_accel/v1_select_s6  (
	.I(ext_active),
	.O(idle_enable)
);
integer failures=0;
initial begin
 repeat(4)@(negedge clk);
 resetn=1;select_d=1;
 repeat(4)@(negedge clk);
 $display("NORMAL idle: original=%b copy=%b resetn=%b",original_q,copy_q,resetn);
 if(original_q!==1 || copy_q!==0)$fatal(1,"Unexpected observation");
 if(original_q!==copy_q)failures++;
 ext_active=1;
 repeat(4)@(negedge clk);
 $display("NORMAL busy: original=%b copy=%b resetn=%b",original_q,copy_q,resetn);
 if(original_q!==1 || copy_q!==0)$fatal(1,"Unexpected observation");
 if(original_q!==copy_q)failures++;
 resetn=0;
 repeat(4)@(negedge clk);
 $display("RESET busy: original=%b copy=%b resetn=%b",original_q,copy_q,resetn);
 if(original_q!==0 || copy_q!==1)$fatal(1,"Unexpected observation");
 if(original_q!==copy_q)failures++;
 if(failures!=3)$fatal(1,"Missing divergence");
 $display("REPRODUCED: 3 divergent original/copy states from post-PnR netlist");$finish;
end
endmodule
