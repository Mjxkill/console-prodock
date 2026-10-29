module mapped_mask(input gpu_clk,gpu_debug_state_48,color_load,pixel_visible,
input [57:0] state,input [3:0] lane,output [15:0] pixel_written);
wire [15:0] pixel_written_next;
wire GND=1'b0,VCC=1'b1;
wire n35720_4;
wire pixel_written_next_0_6;
wire pixel_written_next_0_8;
wire pixel_written_next_10_5;
wire pixel_written_next_11_5;
wire pixel_written_next_12_5;
wire pixel_written_next_13_5;
wire pixel_written_next_14_5;
wire pixel_written_next_15_5;
wire pixel_written_next_1_5;
wire pixel_written_next_2_5;
wire pixel_written_next_3_5;
wire pixel_written_next_4_5;
wire pixel_written_next_5_5;
wire pixel_written_next_6_5;
wire pixel_written_next_7_5;
wire pixel_written_next_8_5;
wire pixel_written_next_9_5;
  LUT2 n35720_s1 (
    .F(n35720_4),
    .I0(state[13]),
    .I1(gpu_debug_state_48) 
);
defparam n35720_s1.INIT=4'hB;
  DFFCE pixel_written_0_s0 (
    .Q(pixel_written[0]),
    .D(pixel_written_next[0]),
    .CLK(gpu_clk),
    .CLEAR(GND),
    .CE(VCC) 
);
defparam pixel_written_0_s0.INIT=1'b0;
  DFFCE pixel_written_10_s0 (
    .Q(pixel_written[10]),
    .D(pixel_written_next[10]),
    .CLK(gpu_clk),
    .CLEAR(GND),
    .CE(VCC) 
);
defparam pixel_written_10_s0.INIT=1'b0;
  DFFCE pixel_written_11_s0 (
    .Q(pixel_written[11]),
    .D(pixel_written_next[11]),
    .CLK(gpu_clk),
    .CLEAR(GND),
    .CE(VCC) 
);
defparam pixel_written_11_s0.INIT=1'b0;
  DFFCE pixel_written_12_s0 (
    .Q(pixel_written[12]),
    .D(pixel_written_next[12]),
    .CLK(gpu_clk),
    .CLEAR(GND),
    .CE(VCC) 
);
defparam pixel_written_12_s0.INIT=1'b0;
  DFFCE pixel_written_13_s0 (
    .Q(pixel_written[13]),
    .D(pixel_written_next[13]),
    .CLK(gpu_clk),
    .CLEAR(GND),
    .CE(VCC) 
);
defparam pixel_written_13_s0.INIT=1'b0;
  DFFCE pixel_written_14_s0 (
    .Q(pixel_written[14]),
    .D(pixel_written_next[14]),
    .CLK(gpu_clk),
    .CLEAR(GND),
    .CE(VCC) 
);
defparam pixel_written_14_s0.INIT=1'b0;
  DFFCE pixel_written_15_s0 (
    .Q(pixel_written[15]),
    .D(pixel_written_next[15]),
    .CLK(gpu_clk),
    .CLEAR(GND),
    .CE(VCC) 
);
defparam pixel_written_15_s0.INIT=1'b0;
  DFFCE pixel_written_1_s0 (
    .Q(pixel_written[1]),
    .D(pixel_written_next[1]),
    .CLK(gpu_clk),
    .CLEAR(GND),
    .CE(VCC) 
);
defparam pixel_written_1_s0.INIT=1'b0;
  DFFCE pixel_written_2_s0 (
    .Q(pixel_written[2]),
    .D(pixel_written_next[2]),
    .CLK(gpu_clk),
    .CLEAR(GND),
    .CE(VCC) 
);
defparam pixel_written_2_s0.INIT=1'b0;
  DFFCE pixel_written_3_s0 (
    .Q(pixel_written[3]),
    .D(pixel_written_next[3]),
    .CLK(gpu_clk),
    .CLEAR(GND),
    .CE(VCC) 
);
defparam pixel_written_3_s0.INIT=1'b0;
  DFFCE pixel_written_4_s0 (
    .Q(pixel_written[4]),
    .D(pixel_written_next[4]),
    .CLK(gpu_clk),
    .CLEAR(GND),
    .CE(VCC) 
);
defparam pixel_written_4_s0.INIT=1'b0;
  DFFCE pixel_written_5_s0 (
    .Q(pixel_written[5]),
    .D(pixel_written_next[5]),
    .CLK(gpu_clk),
    .CLEAR(GND),
    .CE(VCC) 
);
defparam pixel_written_5_s0.INIT=1'b0;
  DFFCE pixel_written_6_s0 (
    .Q(pixel_written[6]),
    .D(pixel_written_next[6]),
    .CLK(gpu_clk),
    .CLEAR(GND),
    .CE(VCC) 
);
defparam pixel_written_6_s0.INIT=1'b0;
  DFFCE pixel_written_7_s0 (
    .Q(pixel_written[7]),
    .D(pixel_written_next[7]),
    .CLK(gpu_clk),
    .CLEAR(GND),
    .CE(VCC) 
);
defparam pixel_written_7_s0.INIT=1'b0;
  DFFCE pixel_written_8_s0 (
    .Q(pixel_written[8]),
    .D(pixel_written_next[8]),
    .CLK(gpu_clk),
    .CLEAR(GND),
    .CE(VCC) 
);
defparam pixel_written_8_s0.INIT=1'b0;
  DFFCE pixel_written_9_s0 (
    .Q(pixel_written[9]),
    .D(pixel_written_next[9]),
    .CLK(gpu_clk),
    .CLEAR(GND),
    .CE(VCC) 
);
defparam pixel_written_9_s0.INIT=1'b0;
  LUT4 pixel_written_next_0_s1 (
    .F(pixel_written_next[0]),
    .I0(pixel_written_next_0_8),
    .I1(pixel_written_next_0_6),
    .I2(pixel_written[0]),
    .I3(n35720_4) 
);
defparam pixel_written_next_0_s1.INIT=16'h00F8;
  LUT4 pixel_written_next_0_s3 (
    .F(pixel_written_next_0_6),
    .I0(lane[0]),
    .I1(lane[1]),
    .I2(lane[2]),
    .I3(lane[3]) 
);
defparam pixel_written_next_0_s3.INIT=16'h0001;
  LUT4 pixel_written_next_0_s4 (
    .F(pixel_written_next_0_8),
    .I0(color_load),
    .I1(state[26]),
    .I2(state[55]),
    .I3(pixel_visible) 
);
defparam pixel_written_next_0_s4.INIT=16'h5400;
  LUT4 pixel_written_next_10_s1 (
    .F(pixel_written_next[10]),
    .I0(pixel_written_next_0_8),
    .I1(pixel_written_next_10_5),
    .I2(pixel_written[10]),
    .I3(n35720_4) 
);
defparam pixel_written_next_10_s1.INIT=16'h00F8;
  LUT4 pixel_written_next_10_s2 (
    .F(pixel_written_next_10_5),
    .I0(lane[0]),
    .I1(lane[2]),
    .I2(lane[1]),
    .I3(lane[3]) 
);
defparam pixel_written_next_10_s2.INIT=16'h1000;
  LUT4 pixel_written_next_11_s1 (
    .F(pixel_written_next[11]),
    .I0(pixel_written_next_0_8),
    .I1(pixel_written_next_11_5),
    .I2(pixel_written[11]),
    .I3(n35720_4) 
);
defparam pixel_written_next_11_s1.INIT=16'h00F8;
  LUT4 pixel_written_next_11_s2 (
    .F(pixel_written_next_11_5),
    .I0(lane[2]),
    .I1(lane[1]),
    .I2(lane[0]),
    .I3(lane[3]) 
);
defparam pixel_written_next_11_s2.INIT=16'h4000;
  LUT4 pixel_written_next_12_s1 (
    .F(pixel_written_next[12]),
    .I0(pixel_written_next_0_8),
    .I1(pixel_written_next_12_5),
    .I2(pixel_written[12]),
    .I3(n35720_4) 
);
defparam pixel_written_next_12_s1.INIT=16'h00F8;
  LUT4 pixel_written_next_12_s2 (
    .F(pixel_written_next_12_5),
    .I0(lane[0]),
    .I1(lane[1]),
    .I2(lane[2]),
    .I3(lane[3]) 
);
defparam pixel_written_next_12_s2.INIT=16'h1000;
  LUT4 pixel_written_next_13_s1 (
    .F(pixel_written_next[13]),
    .I0(pixel_written_next_0_8),
    .I1(pixel_written_next_13_5),
    .I2(pixel_written[13]),
    .I3(n35720_4) 
);
defparam pixel_written_next_13_s1.INIT=16'h00F8;
  LUT4 pixel_written_next_13_s2 (
    .F(pixel_written_next_13_5),
    .I0(lane[1]),
    .I1(lane[0]),
    .I2(lane[2]),
    .I3(lane[3]) 
);
defparam pixel_written_next_13_s2.INIT=16'h4000;
  LUT4 pixel_written_next_14_s1 (
    .F(pixel_written_next[14]),
    .I0(pixel_written_next_0_8),
    .I1(pixel_written_next_14_5),
    .I2(pixel_written[14]),
    .I3(n35720_4) 
);
defparam pixel_written_next_14_s1.INIT=16'h00F8;
  LUT4 pixel_written_next_14_s2 (
    .F(pixel_written_next_14_5),
    .I0(lane[0]),
    .I1(lane[1]),
    .I2(lane[2]),
    .I3(lane[3]) 
);
defparam pixel_written_next_14_s2.INIT=16'h4000;
  LUT4 pixel_written_next_15_s1 (
    .F(pixel_written_next[15]),
    .I0(pixel_written_next_0_8),
    .I1(pixel_written_next_15_5),
    .I2(pixel_written[15]),
    .I3(n35720_4) 
);
defparam pixel_written_next_15_s1.INIT=16'h00F8;
  LUT4 pixel_written_next_15_s2 (
    .F(pixel_written_next_15_5),
    .I0(lane[0]),
    .I1(lane[1]),
    .I2(lane[2]),
    .I3(lane[3]) 
);
defparam pixel_written_next_15_s2.INIT=16'h8000;
  LUT4 pixel_written_next_1_s1 (
    .F(pixel_written_next[1]),
    .I0(pixel_written_next_0_8),
    .I1(pixel_written_next_1_5),
    .I2(pixel_written[1]),
    .I3(n35720_4) 
);
defparam pixel_written_next_1_s1.INIT=16'h00F8;
  LUT4 pixel_written_next_1_s2 (
    .F(pixel_written_next_1_5),
    .I0(lane[1]),
    .I1(lane[2]),
    .I2(lane[3]),
    .I3(lane[0]) 
);
defparam pixel_written_next_1_s2.INIT=16'h0100;
  LUT4 pixel_written_next_2_s1 (
    .F(pixel_written_next[2]),
    .I0(pixel_written_next_0_8),
    .I1(pixel_written_next_2_5),
    .I2(pixel_written[2]),
    .I3(n35720_4) 
);
defparam pixel_written_next_2_s1.INIT=16'h00F8;
  LUT4 pixel_written_next_2_s2 (
    .F(pixel_written_next_2_5),
    .I0(lane[0]),
    .I1(lane[2]),
    .I2(lane[3]),
    .I3(lane[1]) 
);
defparam pixel_written_next_2_s2.INIT=16'h0100;
  LUT4 pixel_written_next_3_s1 (
    .F(pixel_written_next[3]),
    .I0(pixel_written_next_0_8),
    .I1(pixel_written_next_3_5),
    .I2(pixel_written[3]),
    .I3(n35720_4) 
);
defparam pixel_written_next_3_s1.INIT=16'h00F8;
  LUT4 pixel_written_next_3_s2 (
    .F(pixel_written_next_3_5),
    .I0(lane[2]),
    .I1(lane[3]),
    .I2(lane[0]),
    .I3(lane[1]) 
);
defparam pixel_written_next_3_s2.INIT=16'h1000;
  LUT4 pixel_written_next_4_s1 (
    .F(pixel_written_next[4]),
    .I0(pixel_written_next_0_8),
    .I1(pixel_written_next_4_5),
    .I2(pixel_written[4]),
    .I3(n35720_4) 
);
defparam pixel_written_next_4_s1.INIT=16'h00F8;
  LUT4 pixel_written_next_4_s2 (
    .F(pixel_written_next_4_5),
    .I0(lane[0]),
    .I1(lane[1]),
    .I2(lane[3]),
    .I3(lane[2]) 
);
defparam pixel_written_next_4_s2.INIT=16'h0100;
  LUT4 pixel_written_next_5_s1 (
    .F(pixel_written_next[5]),
    .I0(pixel_written_next_0_8),
    .I1(pixel_written_next_5_5),
    .I2(pixel_written[5]),
    .I3(n35720_4) 
);
defparam pixel_written_next_5_s1.INIT=16'h00F8;
  LUT4 pixel_written_next_5_s2 (
    .F(pixel_written_next_5_5),
    .I0(lane[1]),
    .I1(lane[3]),
    .I2(lane[2]),
    .I3(lane[0]) 
);
defparam pixel_written_next_5_s2.INIT=16'h1000;
  LUT4 pixel_written_next_6_s1 (
    .F(pixel_written_next[6]),
    .I0(pixel_written_next_0_8),
    .I1(pixel_written_next_6_5),
    .I2(pixel_written[6]),
    .I3(n35720_4) 
);
defparam pixel_written_next_6_s1.INIT=16'h00F8;
  LUT4 pixel_written_next_6_s2 (
    .F(pixel_written_next_6_5),
    .I0(lane[0]),
    .I1(lane[3]),
    .I2(lane[2]),
    .I3(lane[1]) 
);
defparam pixel_written_next_6_s2.INIT=16'h1000;
  LUT4 pixel_written_next_7_s1 (
    .F(pixel_written_next[7]),
    .I0(pixel_written_next_0_8),
    .I1(pixel_written_next_7_5),
    .I2(pixel_written[7]),
    .I3(n35720_4) 
);
defparam pixel_written_next_7_s1.INIT=16'h00F8;
  LUT4 pixel_written_next_7_s2 (
    .F(pixel_written_next_7_5),
    .I0(lane[3]),
    .I1(lane[1]),
    .I2(lane[2]),
    .I3(lane[0]) 
);
defparam pixel_written_next_7_s2.INIT=16'h4000;
  LUT4 pixel_written_next_8_s1 (
    .F(pixel_written_next[8]),
    .I0(pixel_written_next_0_8),
    .I1(pixel_written_next_8_5),
    .I2(pixel_written[8]),
    .I3(n35720_4) 
);
defparam pixel_written_next_8_s1.INIT=16'h00F8;
  LUT4 pixel_written_next_8_s2 (
    .F(pixel_written_next_8_5),
    .I0(lane[0]),
    .I1(lane[1]),
    .I2(lane[2]),
    .I3(lane[3]) 
);
defparam pixel_written_next_8_s2.INIT=16'h0100;
  LUT4 pixel_written_next_9_s1 (
    .F(pixel_written_next[9]),
    .I0(pixel_written_next_0_8),
    .I1(pixel_written_next_9_5),
    .I2(pixel_written[9]),
    .I3(n35720_4) 
);
defparam pixel_written_next_9_s1.INIT=16'h00F8;
  LUT4 pixel_written_next_9_s2 (
    .F(pixel_written_next_9_5),
    .I0(lane[1]),
    .I1(lane[2]),
    .I2(lane[0]),
    .I3(lane[3]) 
);
defparam pixel_written_next_9_s2.INIT=16'h1000;
endmodule
