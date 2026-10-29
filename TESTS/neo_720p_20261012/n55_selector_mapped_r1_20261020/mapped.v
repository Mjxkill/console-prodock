module mapped_selector(input gpu_clk,gpu_debug_state_48,
input [57:0] state,output per_select);
wire GND=1'b0,VCC=1'b1;
wire per_select_next;
wire per_select_next_7;
  LUT3 per_select_next_s3 (
    .F(per_select_next_7),
    .I0(state[27]),
    .I1(state[26]),
    .I2(state[55]) 
);
defparam per_select_next_s3.INIT=8'h01;
  LUT4 per_select_next_s4 (
    .F(per_select_next),
    .I0(state[13]),
    .I1(gpu_debug_state_48),
    .I2(per_select),
    .I3(per_select_next_7) 
);
defparam per_select_next_s4.INIT=16'h4004;
  DFFCE per_select_s0 (
    .Q(per_select),
    .D(per_select_next),
    .CLK(gpu_clk),
    .CLEAR(GND),
    .CE(VCC) 
);
defparam per_select_s0.INIT=1'b0;
endmodule
