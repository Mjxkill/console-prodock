`timescale 1ns/1ps
module exact_chain(input wire clk,bus80_clk,rtc_clk,pll_ae350_lock,ddr_init,uart_rx,
 output wire por_n,trial_done_o,trial_holding_o);
 wire clk_d=clk,vid_hclk=bus80_clk,uart_rx_d=uart_rx;
 wire VCC=1'b1,GND=1'b0;
 wire [2:0] state_178=3'b111,state=state_178;
 wire pll_lock=pll_ae350_lock;
 wire [1:0] ae350_rst_sync;
 wire [0:0] soc_dbg;wire [1:0] init_sync;
 wire trial_request,trial_mode,trial_holding,trial_done,trial_ahb_tick,trial_rtc_tick;
 wire [3:0] trial_epoch;
 wire n4009_7,neo_qualified_clear,neo_qualified_pll_ready;
 wire generated_pll_ready;
 wire trial_release=trial_request;
  LUT4 n4009_s2 (
    .F(n4009_7),
    .I0(state_178[0]),
    .I1(state_178[1]),
    .I2(state_178[2]),
    .I3(pll_lock) 
);
defparam n4009_s2.INIT=16'h7FFF;
  DFFPE ae350_rst_sync_0_s0 (
    .Q(ae350_rst_sync[0]),
    .D(GND),
    .CLK(vid_hclk),
    .PRESET(n4009_7),
    .CE(VCC) 
);
defparam ae350_rst_sync_0_s0.INIT=1'b1;
  DFFPE ae350_rst_sync_1_s0 (
    .Q(ae350_rst_sync[1]),
    .D(ae350_rst_sync[0]),
    .CLK(vid_hclk),
    .PRESET(n4009_7),
    .CE(VCC) 
);
defparam ae350_rst_sync_1_s0.INIT=1'b1;
  LUT2 neo_qualified_pll_lut (
    .F(neo_qualified_pll_ready),
    .I0(generated_pll_ready),
    .I1(ae350_rst_sync[1])
);
defparam neo_qualified_pll_lut.INIT=4'h2;

neo_reset_trial u_reset_trial (
    .clk_ref(clk_d), .ahb_clk(vid_hclk), .rtc_clk(rtc_clk), .serial_rx(uart_rx_d),
    .ddr_ready(ddr_init), .pll_ready(neo_qualified_pll_ready), .cpu_reset_n(soc_dbg[0]),
    .release_request(trial_request), .delay_mode(trial_mode), .command_epoch(trial_epoch[3:0]),
    .holding(trial_holding), .delay_done(trial_done),
    .ahb_tick(trial_ahb_tick), .rtc_tick(trial_rtc_tick));

  DFFCE init_sync_0_s0 (
    .Q(init_sync[0]),
    .D(trial_release),
    .CLK(vid_hclk),
    .CLEAR(neo_qualified_clear),
    .CE(VCC) 
);
defparam init_sync_0_s0.INIT=1'b0;
  DFFCE init_sync_1_s0 (
    .Q(soc_dbg[0]),
    .D(init_sync[0]),
    .CLK(vid_hclk),
    .CLEAR(neo_qualified_clear),
    .CE(VCC) 
);
defparam init_sync_1_s0.INIT=1'b0;
  LUT2 neo_qualified_clear_lut (
    .F(neo_qualified_clear),
    .I0(ae350_rst_sync[1]),
    .I1(trial_release)
);
defparam neo_qualified_clear_lut.INIT=4'hB;
  LUT4 pll_ae350_lock_s (
    .F(generated_pll_ready),
    .I0(state[0]),
    .I1(state[1]),
    .I2(state[2]),
    .I3(pll_lock) 
);
defparam pll_ae350_lock_s.INIT=16'h8000;
assign por_n=soc_dbg[0];assign trial_done_o=trial_done;assign trial_holding_o=trial_holding;
endmodule
module neo_reset_trial (
  clk_ref,
  ahb_clk,
  rtc_clk,
  serial_rx,
  ddr_ready,
  pll_ready,
  cpu_reset_n,
  release_request,
  delay_mode,
  command_epoch,
  holding,
  delay_done,
  ahb_tick,
  rtc_tick
)
;
input clk_ref;
input ahb_clk;
input rtc_clk;
input serial_rx;
input ddr_ready;
input pll_ready;
input cpu_reset_n;
output release_request;
output delay_mode;
output [3:0] command_epoch;
output holding;
output delay_done;
output ahb_tick;
output rtc_tick;
wire n628_4;
wire n631_4;
wire n361_3;
wire n672_3;
wire n261_5;
wire n124_21;
wire n126_19;
wire n128_7;
wire n233_4;
wire n234_4;
wire wait_count_21_6;
wire holding_15;
wire n304_7;
wire n305_7;
wire n306_7;
wire n307_7;
wire n309_7;
wire n310_7;
wire n312_7;
wire n313_8;
wire n125_37;
wire n271_4;
wire n270_4;
wire n269_4;
wire n628_5;
wire n628_6;
wire n672_4;
wire n672_5;
wire n672_6;
wire n124_22;
wire n124_23;
wire n124_24;
wire n124_25;
wire n126_20;
wire n128_8;
wire n128_9;
wire n128_10;
wire n233_5;
wire holding_16;
wire n304_8;
wire n306_8;
wire n306_9;
wire n309_8;
wire n310_8;
wire n125_38;
wire n628_7;
wire n628_8;
wire n628_9;
wire n628_10;
wire n672_7;
wire n672_8;
wire n672_9;
wire n672_10;
wire n672_11;
wire n672_12;
wire n672_13;
wire n124_26;
wire n124_27;
wire n124_28;
wire n124_29;
wire n124_30;
wire n124_31;
wire n124_32;
wire n124_33;
wire n124_34;
wire n124_35;
wire n126_21;
wire n126_22;
wire n126_23;
wire holding_17;
wire holding_18;
wire holding_19;
wire n304_9;
wire n125_39;
wire n125_40;
wire n232_6;
wire n308_9;
wire n311_9;
wire n148_11;
wire n130_6;
wire command_valid;
wire command_mode;
wire pending_mode;
wire n12_1;
wire n12_2;
wire n11_1;
wire n11_2;
wire n10_1;
wire n10_2;
wire n9_1;
wire n9_2;
wire n8_1;
wire n8_2;
wire n7_1;
wire n7_2;
wire n6_1;
wire n6_0_COUT;
wire n30_1;
wire n30_2;
wire n29_1;
wire n29_2;
wire n28_1;
wire n28_2;
wire n27_1;
wire n27_2;
wire n26_1;
wire n26_2;
wire n25_1;
wire n25_2;
wire n24_1;
wire n24_0_COUT;
wire n147_1;
wire n147_2;
wire n146_1;
wire n146_2;
wire n145_1;
wire n145_2;
wire n144_1;
wire n144_2;
wire n143_1;
wire n143_2;
wire n142_1;
wire n142_2;
wire n141_1;
wire n141_2;
wire n140_1;
wire n140_2;
wire n139_1;
wire n139_2;
wire n138_1;
wire n138_2;
wire n137_1;
wire n137_2;
wire n136_1;
wire n136_2;
wire n135_1;
wire n135_2;
wire n134_1;
wire n134_2;
wire n133_1;
wire n133_2;
wire n132_1;
wire n132_0_COUT;
wire n421_1;
wire n421_2;
wire n420_1;
wire n420_2;
wire n419_1;
wire n419_2;
wire n418_1;
wire n418_2;
wire n417_1;
wire n417_2;
wire n416_1;
wire n416_2;
wire n415_1;
wire n415_2;
wire n414_1;
wire n414_2;
wire n413_1;
wire n413_2;
wire n412_1;
wire n412_2;
wire n411_1;
wire n411_2;
wire n410_1;
wire n410_2;
wire n409_1;
wire n409_2;
wire n408_1;
wire n408_2;
wire n407_1;
wire n407_2;
wire n406_1;
wire n406_2;
wire n405_1;
wire n405_2;
wire n404_1;
wire n404_2;
wire n403_1;
wire n403_2;
wire n402_1;
wire n402_2;
wire n401_1;
wire n401_0_COUT;
wire n13_6;
wire n31_6;
wire n272_6;
wire n422_6;
wire rx_valid;
wire [6:0] ahb_div;
wire [6:0] rtc_div;
wire [2:0] up;
wire [2:0] parse_state;
wire [16:0] gap_count;
wire [1:0] ready_meta;
wire [1:0] reset_meta;
wire [9:0] hold_count;
wire [21:0] wait_count;
wire [7:0] rx_byte;
wire VCC;
wire GND;
  LUT3 n628_s1 (
    .F(n628_4),
    .I0(n628_5),
    .I1(n628_6),
    .I2(up[2]) 
);
defparam n628_s1.INIT=8'h8F;
  LUT4 n631_s1 (
    .F(n631_4),
    .I0(n628_6),
    .I1(n628_5),
    .I2(rx_valid),
    .I3(up[2]) 
);
defparam n631_s1.INIT=16'hF8FF;
  LUT3 n361_s0 (
    .F(n361_3),
    .I0(holding),
    .I1(command_valid),
    .I2(ready_meta[1]) 
);
defparam n361_s0.INIT=8'hEF;
  LUT4 n672_s0 (
    .F(n672_3),
    .I0(delay_done),
    .I1(n672_4),
    .I2(n672_5),
    .I3(n672_6) 
);
defparam n672_s0.INIT=16'h1000;
  LUT4 release_request_d_s (
    .F(release_request),
    .I0(holding),
    .I1(n261_5),
    .I2(ready_meta[1]),
    .I3(delay_done) 
);
defparam release_request_d_s.INIT=16'h1000;
  LUT2 n261_s1 (
    .F(n261_5),
    .I0(ddr_ready),
    .I1(pll_ready) 
);
defparam n261_s1.INIT=4'h7;
  LUT4 n124_s11 (
    .F(n124_21),
    .I0(n124_22),
    .I1(n124_23),
    .I2(n124_24),
    .I3(n124_25) 
);
defparam n124_s11.INIT=16'hFF0B;
  LUT3 n126_s11 (
    .F(n126_19),
    .I0(n124_23),
    .I1(n126_20),
    .I2(n124_22) 
);
defparam n126_s11.INIT=8'hF1;
  LUT4 n128_s3 (
    .F(n128_7),
    .I0(n128_8),
    .I1(parse_state[1]),
    .I2(n128_9),
    .I3(n128_10) 
);
defparam n128_s3.INIT=16'h8000;
  LUT4 n233_s1 (
    .F(n233_4),
    .I0(n628_6),
    .I1(n628_5),
    .I2(n128_7),
    .I3(n233_5) 
);
defparam n233_s1.INIT=16'h7000;
  LUT4 n234_s1 (
    .F(n234_4),
    .I0(n628_6),
    .I1(n628_5),
    .I2(n124_25),
    .I3(n233_5) 
);
defparam n234_s1.INIT=16'h7000;
  LUT4 wait_count_21_s2 (
    .F(wait_count_21_6),
    .I0(n672_4),
    .I1(n672_5),
    .I2(n672_6),
    .I3(delay_done) 
);
defparam wait_count_21_s2.INIT=16'h00BF;
  LUT4 holding_s11 (
    .F(holding_15),
    .I0(reset_meta[1]),
    .I1(holding_16),
    .I2(holding),
    .I3(command_valid) 
);
defparam holding_s11.INIT=16'hFF10;
  LUT4 n304_s2 (
    .F(n304_7),
    .I0(hold_count[8]),
    .I1(n304_8),
    .I2(hold_count[9]),
    .I3(holding_16) 
);
defparam n304_s2.INIT=16'h7800;
  LUT3 n305_s2 (
    .F(n305_7),
    .I0(hold_count[8]),
    .I1(n304_8),
    .I2(holding_16) 
);
defparam n305_s2.INIT=8'h60;
  LUT4 n306_s2 (
    .F(n306_7),
    .I0(n306_8),
    .I1(n306_9),
    .I2(hold_count[7]),
    .I3(holding_16) 
);
defparam n306_s2.INIT=16'h7800;
  LUT4 n307_s2 (
    .F(n307_7),
    .I0(hold_count[5]),
    .I1(n306_9),
    .I2(hold_count[6]),
    .I3(holding_16) 
);
defparam n307_s2.INIT=16'h7800;
  LUT3 n309_s2 (
    .F(n309_7),
    .I0(hold_count[4]),
    .I1(n309_8),
    .I2(holding_16) 
);
defparam n309_s2.INIT=8'h60;
  LUT4 n310_s2 (
    .F(n310_7),
    .I0(hold_count[2]),
    .I1(n310_8),
    .I2(hold_count[3]),
    .I3(holding_16) 
);
defparam n310_s2.INIT=16'h7800;
  LUT3 n312_s2 (
    .F(n312_7),
    .I0(reset_meta[1]),
    .I1(hold_count[0]),
    .I2(hold_count[1]) 
);
defparam n312_s2.INIT=8'h14;
  LUT2 n313_s3 (
    .F(n313_8),
    .I0(reset_meta[1]),
    .I1(hold_count[0]) 
);
defparam n313_s3.INIT=4'h1;
  LUT4 n125_s21 (
    .F(n125_37),
    .I0(n124_25),
    .I1(n124_23),
    .I2(n125_38),
    .I3(n126_20) 
);
defparam n125_s21.INIT=16'hF0BB;
  LUT2 n271_s0 (
    .F(n271_4),
    .I0(command_epoch[0]),
    .I1(command_epoch[1]) 
);
defparam n271_s0.INIT=4'h6;
  LUT3 n270_s0 (
    .F(n270_4),
    .I0(command_epoch[0]),
    .I1(command_epoch[1]),
    .I2(command_epoch[2]) 
);
defparam n270_s0.INIT=8'h78;
  LUT4 n269_s0 (
    .F(n269_4),
    .I0(command_epoch[0]),
    .I1(command_epoch[1]),
    .I2(command_epoch[2]),
    .I3(command_epoch[3]) 
);
defparam n269_s0.INIT=16'h7F80;
  LUT4 n628_s2 (
    .F(n628_5),
    .I0(n628_7),
    .I1(gap_count[0]),
    .I2(n628_8),
    .I3(n628_9) 
);
defparam n628_s2.INIT=16'h8000;
  LUT4 n628_s3 (
    .F(n628_6),
    .I0(gap_count[6]),
    .I1(gap_count[8]),
    .I2(gap_count[7]),
    .I3(n628_10) 
);
defparam n628_s3.INIT=16'h1000;
  LUT4 n672_s1 (
    .F(n672_4),
    .I0(n672_7),
    .I1(n672_8),
    .I2(wait_count[17]),
    .I3(n672_9) 
);
defparam n672_s1.INIT=16'hF53F;
  LUT4 n672_s2 (
    .F(n672_5),
    .I0(n672_10),
    .I1(wait_count[8]),
    .I2(wait_count[5]),
    .I3(wait_count[9]) 
);
defparam n672_s2.INIT=16'h1004;
  LUT4 n672_s3 (
    .F(n672_6),
    .I0(wait_count[14]),
    .I1(n672_11),
    .I2(n672_12),
    .I3(n672_13) 
);
defparam n672_s3.INIT=16'h4000;
  LUT4 n124_s12 (
    .F(n124_22),
    .I0(n124_26),
    .I1(rx_byte[0]),
    .I2(n124_27),
    .I3(n124_28) 
);
defparam n124_s12.INIT=16'h4000;
  LUT4 n124_s13 (
    .F(n124_23),
    .I0(n124_29),
    .I1(n124_30),
    .I2(n124_31),
    .I3(parse_state[2]) 
);
defparam n124_s13.INIT=16'h7F00;
  LUT4 n124_s14 (
    .F(n124_24),
    .I0(n124_32),
    .I1(n124_33),
    .I2(n124_34),
    .I3(parse_state[2]) 
);
defparam n124_s14.INIT=16'h007F;
  LUT4 n124_s15 (
    .F(n124_25),
    .I0(parse_state[1]),
    .I1(n124_35),
    .I2(parse_state[2]),
    .I3(n128_9) 
);
defparam n124_s15.INIT=16'h4000;
  LUT4 n126_s12 (
    .F(n126_20),
    .I0(n126_21),
    .I1(n126_22),
    .I2(n126_23),
    .I3(parse_state[2]) 
);
defparam n126_s12.INIT=16'h007F;
  LUT2 n128_s4 (
    .F(n128_8),
    .I0(parse_state[2]),
    .I1(rx_byte[2]) 
);
defparam n128_s4.INIT=4'h8;
  LUT4 n128_s5 (
    .F(n128_9),
    .I0(rx_byte[5]),
    .I1(rx_byte[6]),
    .I2(rx_byte[7]),
    .I3(parse_state[0]) 
);
defparam n128_s5.INIT=16'h0100;
  LUT4 n128_s6 (
    .F(n128_10),
    .I0(rx_byte[1]),
    .I1(rx_byte[4]),
    .I2(rx_byte[3]),
    .I3(rx_byte[0]) 
);
defparam n128_s6.INIT=16'h1000;
  LUT2 n233_s2 (
    .F(n233_5),
    .I0(up[2]),
    .I1(rx_valid) 
);
defparam n233_s2.INIT=4'h8;
  LUT4 holding_s12 (
    .F(holding_16),
    .I0(holding_17),
    .I1(holding_18),
    .I2(holding_19),
    .I3(reset_meta[1]) 
);
defparam holding_s12.INIT=16'h007F;
  LUT4 n304_s3 (
    .F(n304_8),
    .I0(n304_9),
    .I1(hold_count[2]),
    .I2(n310_8),
    .I3(holding_19) 
);
defparam n304_s3.INIT=16'h8000;
  LUT2 n306_s3 (
    .F(n306_8),
    .I0(hold_count[5]),
    .I1(hold_count[6]) 
);
defparam n306_s3.INIT=4'h8;
  LUT2 n306_s4 (
    .F(n306_9),
    .I0(hold_count[4]),
    .I1(n309_8) 
);
defparam n306_s4.INIT=4'h8;
  LUT4 n309_s3 (
    .F(n309_8),
    .I0(hold_count[0]),
    .I1(hold_count[1]),
    .I2(hold_count[2]),
    .I3(hold_count[3]) 
);
defparam n309_s3.INIT=16'h8000;
  LUT2 n310_s3 (
    .F(n310_8),
    .I0(hold_count[0]),
    .I1(hold_count[1]) 
);
defparam n310_s3.INIT=4'h8;
  LUT4 n125_s22 (
    .F(n125_38),
    .I0(n125_39),
    .I1(parse_state[0]),
    .I2(n126_22),
    .I3(n125_40) 
);
defparam n125_s22.INIT=16'h8000;
  LUT4 n628_s4 (
    .F(n628_7),
    .I0(gap_count[5]),
    .I1(gap_count[3]),
    .I2(gap_count[4]),
    .I3(gap_count[2]) 
);
defparam n628_s4.INIT=16'h4000;
  LUT4 n628_s5 (
    .F(n628_8),
    .I0(gap_count[11]),
    .I1(gap_count[12]),
    .I2(gap_count[13]),
    .I3(gap_count[10]) 
);
defparam n628_s5.INIT=16'h0100;
  LUT4 n628_s6 (
    .F(n628_9),
    .I0(parse_state[1]),
    .I1(parse_state[2]),
    .I2(parse_state[0]),
    .I3(gap_count[1]) 
);
defparam n628_s6.INIT=16'hFE00;
  LUT4 n628_s7 (
    .F(n628_10),
    .I0(gap_count[14]),
    .I1(gap_count[9]),
    .I2(gap_count[15]),
    .I3(gap_count[16]) 
);
defparam n628_s7.INIT=16'h4000;
  LUT4 n672_s4 (
    .F(n672_7),
    .I0(wait_count[21]),
    .I1(wait_count[12]),
    .I2(wait_count[15]),
    .I3(wait_count[16]) 
);
defparam n672_s4.INIT=16'h4000;
  LUT4 n672_s5 (
    .F(n672_8),
    .I0(wait_count[12]),
    .I1(wait_count[15]),
    .I2(wait_count[16]),
    .I3(wait_count[21]) 
);
defparam n672_s5.INIT=16'h0100;
  LUT4 n672_s6 (
    .F(n672_9),
    .I0(delay_mode),
    .I1(wait_count[13]),
    .I2(wait_count[18]),
    .I3(wait_count[17]) 
);
defparam n672_s6.INIT=16'h7F01;
  LUT3 n672_s7 (
    .F(n672_10),
    .I0(wait_count[8]),
    .I1(wait_count[7]),
    .I2(delay_mode) 
);
defparam n672_s7.INIT=8'h7E;
  LUT2 n672_s8 (
    .F(n672_11),
    .I0(wait_count[19]),
    .I1(wait_count[20]) 
);
defparam n672_s8.INIT=4'h1;
  LUT4 n672_s9 (
    .F(n672_12),
    .I0(wait_count[6]),
    .I1(wait_count[11]),
    .I2(wait_count[10]),
    .I3(wait_count[4]) 
);
defparam n672_s9.INIT=16'h1000;
  LUT4 n672_s10 (
    .F(n672_13),
    .I0(wait_count[0]),
    .I1(wait_count[1]),
    .I2(wait_count[2]),
    .I3(wait_count[3]) 
);
defparam n672_s10.INIT=16'h8000;
  LUT3 n124_s16 (
    .F(n124_26),
    .I0(parse_state[2]),
    .I1(rx_byte[4]),
    .I2(rx_byte[7]) 
);
defparam n124_s16.INIT=8'hE7;
  LUT4 n124_s17 (
    .F(n124_27),
    .I0(parse_state[0]),
    .I1(parse_state[1]),
    .I2(rx_byte[3]),
    .I3(rx_byte[5]) 
);
defparam n124_s17.INIT=16'h0100;
  LUT3 n124_s18 (
    .F(n124_28),
    .I0(rx_byte[1]),
    .I1(rx_byte[6]),
    .I2(rx_byte[2]) 
);
defparam n124_s18.INIT=8'h10;
  LUT3 n124_s19 (
    .F(n124_29),
    .I0(rx_byte[5]),
    .I1(rx_byte[6]),
    .I2(rx_byte[7]) 
);
defparam n124_s19.INIT=8'h80;
  LUT4 n124_s20 (
    .F(n124_30),
    .I0(rx_byte[1]),
    .I1(rx_byte[2]),
    .I2(rx_byte[3]),
    .I3(rx_byte[4]) 
);
defparam n124_s20.INIT=16'h8000;
  LUT4 n124_s21 (
    .F(n124_31),
    .I0(parse_state[0]),
    .I1(rx_byte[0]),
    .I2(pending_mode),
    .I3(parse_state[1]) 
);
defparam n124_s21.INIT=16'h1400;
  LUT4 n124_s22 (
    .F(n124_32),
    .I0(parse_state[0]),
    .I1(parse_state[1]),
    .I2(rx_byte[4]),
    .I3(rx_byte[5]) 
);
defparam n124_s22.INIT=16'h8000;
  LUT4 n124_s23 (
    .F(n124_33),
    .I0(rx_byte[1]),
    .I1(rx_byte[2]),
    .I2(rx_byte[3]),
    .I3(rx_byte[0]) 
);
defparam n124_s23.INIT=16'h0100;
  LUT2 n124_s24 (
    .F(n124_34),
    .I0(rx_byte[6]),
    .I1(rx_byte[7]) 
);
defparam n124_s24.INIT=4'h1;
  LUT4 n124_s25 (
    .F(n124_35),
    .I0(rx_byte[1]),
    .I1(rx_byte[2]),
    .I2(rx_byte[3]),
    .I3(rx_byte[4]) 
);
defparam n124_s25.INIT=16'h0001;
  LUT3 n126_s13 (
    .F(n126_21),
    .I0(rx_byte[3]),
    .I1(rx_byte[7]),
    .I2(rx_byte[4]) 
);
defparam n126_s13.INIT=8'h10;
  LUT3 n126_s14 (
    .F(n126_22),
    .I0(rx_byte[0]),
    .I1(rx_byte[2]),
    .I2(rx_byte[1]) 
);
defparam n126_s14.INIT=8'h10;
  LUT4 n126_s15 (
    .F(n126_23),
    .I0(parse_state[0]),
    .I1(rx_byte[5]),
    .I2(parse_state[1]),
    .I3(rx_byte[6]) 
);
defparam n126_s15.INIT=16'h1000;
  LUT3 holding_s13 (
    .F(holding_17),
    .I0(hold_count[4]),
    .I1(hold_count[8]),
    .I2(hold_count[9]) 
);
defparam holding_s13.INIT=8'h40;
  LUT4 holding_s14 (
    .F(holding_18),
    .I0(hold_count[3]),
    .I1(hold_count[1]),
    .I2(hold_count[2]),
    .I3(hold_count[0]) 
);
defparam holding_s14.INIT=16'h4000;
  LUT3 holding_s15 (
    .F(holding_19),
    .I0(hold_count[5]),
    .I1(hold_count[6]),
    .I2(hold_count[7]) 
);
defparam holding_s15.INIT=8'h80;
  LUT2 n304_s4 (
    .F(n304_9),
    .I0(hold_count[3]),
    .I1(hold_count[4]) 
);
defparam n304_s4.INIT=4'h8;
  LUT2 n125_s23 (
    .F(n125_39),
    .I0(parse_state[1]),
    .I1(rx_byte[7]) 
);
defparam n125_s23.INIT=4'h1;
  LUT4 n125_s24 (
    .F(n125_40),
    .I0(rx_byte[5]),
    .I1(rx_byte[4]),
    .I2(rx_byte[3]),
    .I3(rx_byte[6]) 
);
defparam n125_s24.INIT=16'h4000;
  LUT4 n232_s2 (
    .F(n232_6),
    .I0(n628_6),
    .I1(n628_5),
    .I2(up[2]),
    .I3(rx_valid) 
);
defparam n232_s2.INIT=16'h8FFF;
  LUT4 n308_s3 (
    .F(n308_9),
    .I0(hold_count[5]),
    .I1(hold_count[4]),
    .I2(n309_8),
    .I3(holding_16) 
);
defparam n308_s3.INIT=16'h6A00;
  LUT4 n311_s3 (
    .F(n311_9),
    .I0(reset_meta[1]),
    .I1(hold_count[2]),
    .I2(hold_count[0]),
    .I3(hold_count[1]) 
);
defparam n311_s3.INIT=16'h1444;
  LUT4 n148_s3 (
    .F(n148_11),
    .I0(parse_state[0]),
    .I1(parse_state[1]),
    .I2(parse_state[2]),
    .I3(gap_count[0]) 
);
defparam n148_s3.INIT=16'h01FE;
  LUT3 n130_s1 (
    .F(n130_6),
    .I0(parse_state[0]),
    .I1(parse_state[1]),
    .I2(parse_state[2]) 
);
defparam n130_s1.INIT=8'hFE;
  DFFRE ahb_div_6_s0 (
    .Q(ahb_div[6]),
    .D(n7_1),
    .CLK(ahb_clk),
    .RESET(GND),
    .CE(VCC) 
);
defparam ahb_div_6_s0.INIT=1'b0;
  DFFRE ahb_div_5_s0 (
    .Q(ahb_div[5]),
    .D(n8_1),
    .CLK(ahb_clk),
    .RESET(GND),
    .CE(VCC) 
);
defparam ahb_div_5_s0.INIT=1'b0;
  DFFRE ahb_div_4_s0 (
    .Q(ahb_div[4]),
    .D(n9_1),
    .CLK(ahb_clk),
    .RESET(GND),
    .CE(VCC) 
);
defparam ahb_div_4_s0.INIT=1'b0;
  DFFRE ahb_div_3_s0 (
    .Q(ahb_div[3]),
    .D(n10_1),
    .CLK(ahb_clk),
    .RESET(GND),
    .CE(VCC) 
);
defparam ahb_div_3_s0.INIT=1'b0;
  DFFRE ahb_div_2_s0 (
    .Q(ahb_div[2]),
    .D(n11_1),
    .CLK(ahb_clk),
    .RESET(GND),
    .CE(VCC) 
);
defparam ahb_div_2_s0.INIT=1'b0;
  DFFRE ahb_div_1_s0 (
    .Q(ahb_div[1]),
    .D(n12_1),
    .CLK(ahb_clk),
    .RESET(GND),
    .CE(VCC) 
);
defparam ahb_div_1_s0.INIT=1'b0;
  DFFRE ahb_div_0_s0 (
    .Q(ahb_div[0]),
    .D(n13_6),
    .CLK(ahb_clk),
    .RESET(GND),
    .CE(VCC) 
);
defparam ahb_div_0_s0.INIT=1'b0;
  DFFRE rtc_div_7_s0 (
    .Q(rtc_tick),
    .D(n24_1),
    .CLK(rtc_clk),
    .RESET(GND),
    .CE(VCC) 
);
defparam rtc_div_7_s0.INIT=1'b0;
  DFFRE rtc_div_6_s0 (
    .Q(rtc_div[6]),
    .D(n25_1),
    .CLK(rtc_clk),
    .RESET(GND),
    .CE(VCC) 
);
defparam rtc_div_6_s0.INIT=1'b0;
  DFFRE rtc_div_5_s0 (
    .Q(rtc_div[5]),
    .D(n26_1),
    .CLK(rtc_clk),
    .RESET(GND),
    .CE(VCC) 
);
defparam rtc_div_5_s0.INIT=1'b0;
  DFFRE rtc_div_4_s0 (
    .Q(rtc_div[4]),
    .D(n27_1),
    .CLK(rtc_clk),
    .RESET(GND),
    .CE(VCC) 
);
defparam rtc_div_4_s0.INIT=1'b0;
  DFFRE rtc_div_3_s0 (
    .Q(rtc_div[3]),
    .D(n28_1),
    .CLK(rtc_clk),
    .RESET(GND),
    .CE(VCC) 
);
defparam rtc_div_3_s0.INIT=1'b0;
  DFFRE rtc_div_2_s0 (
    .Q(rtc_div[2]),
    .D(n29_1),
    .CLK(rtc_clk),
    .RESET(GND),
    .CE(VCC) 
);
defparam rtc_div_2_s0.INIT=1'b0;
  DFFRE rtc_div_1_s0 (
    .Q(rtc_div[1]),
    .D(n30_1),
    .CLK(rtc_clk),
    .RESET(GND),
    .CE(VCC) 
);
defparam rtc_div_1_s0.INIT=1'b0;
  DFFRE rtc_div_0_s0 (
    .Q(rtc_div[0]),
    .D(n31_6),
    .CLK(rtc_clk),
    .RESET(GND),
    .CE(VCC) 
);
defparam rtc_div_0_s0.INIT=1'b0;
  DFFCE up_2_s0 (
    .Q(up[2]),
    .D(up[1]),
    .CLK(clk_ref),
    .CLEAR(GND),
    .CE(VCC) 
);
defparam up_2_s0.INIT=1'b0;
  DFFCE up_1_s0 (
    .Q(up[1]),
    .D(up[0]),
    .CLK(clk_ref),
    .CLEAR(GND),
    .CE(VCC) 
);
defparam up_1_s0.INIT=1'b0;
  DFFCE up_0_s0 (
    .Q(up[0]),
    .D(VCC),
    .CLK(clk_ref),
    .CLEAR(GND),
    .CE(VCC) 
);
defparam up_0_s0.INIT=1'b0;
  DFFRE command_valid_s0 (
    .Q(command_valid),
    .D(n128_7),
    .CLK(clk_ref),
    .RESET(n232_6),
    .CE(VCC) 
);
defparam command_valid_s0.INIT=1'b0;
  DFFRE parse_state_2_s0 (
    .Q(parse_state[2]),
    .D(n124_21),
    .CLK(clk_ref),
    .RESET(n628_4),
    .CE(rx_valid) 
);
defparam parse_state_2_s0.INIT=1'b0;
  DFFRE parse_state_1_s0 (
    .Q(parse_state[1]),
    .D(n125_37),
    .CLK(clk_ref),
    .RESET(n628_4),
    .CE(rx_valid) 
);
defparam parse_state_1_s0.INIT=1'b0;
  DFFRE parse_state_0_s0 (
    .Q(parse_state[0]),
    .D(n126_19),
    .CLK(clk_ref),
    .RESET(n628_4),
    .CE(rx_valid) 
);
defparam parse_state_0_s0.INIT=1'b0;
  DFFRE gap_count_16_s0 (
    .Q(gap_count[16]),
    .D(n132_1),
    .CLK(clk_ref),
    .RESET(n631_4),
    .CE(n130_6) 
);
defparam gap_count_16_s0.INIT=1'b0;
  DFFRE gap_count_15_s0 (
    .Q(gap_count[15]),
    .D(n133_1),
    .CLK(clk_ref),
    .RESET(n631_4),
    .CE(n130_6) 
);
defparam gap_count_15_s0.INIT=1'b0;
  DFFRE gap_count_14_s0 (
    .Q(gap_count[14]),
    .D(n134_1),
    .CLK(clk_ref),
    .RESET(n631_4),
    .CE(n130_6) 
);
defparam gap_count_14_s0.INIT=1'b0;
  DFFRE gap_count_13_s0 (
    .Q(gap_count[13]),
    .D(n135_1),
    .CLK(clk_ref),
    .RESET(n631_4),
    .CE(n130_6) 
);
defparam gap_count_13_s0.INIT=1'b0;
  DFFRE gap_count_12_s0 (
    .Q(gap_count[12]),
    .D(n136_1),
    .CLK(clk_ref),
    .RESET(n631_4),
    .CE(n130_6) 
);
defparam gap_count_12_s0.INIT=1'b0;
  DFFRE gap_count_11_s0 (
    .Q(gap_count[11]),
    .D(n137_1),
    .CLK(clk_ref),
    .RESET(n631_4),
    .CE(n130_6) 
);
defparam gap_count_11_s0.INIT=1'b0;
  DFFRE gap_count_10_s0 (
    .Q(gap_count[10]),
    .D(n138_1),
    .CLK(clk_ref),
    .RESET(n631_4),
    .CE(n130_6) 
);
defparam gap_count_10_s0.INIT=1'b0;
  DFFRE gap_count_9_s0 (
    .Q(gap_count[9]),
    .D(n139_1),
    .CLK(clk_ref),
    .RESET(n631_4),
    .CE(n130_6) 
);
defparam gap_count_9_s0.INIT=1'b0;
  DFFRE gap_count_8_s0 (
    .Q(gap_count[8]),
    .D(n140_1),
    .CLK(clk_ref),
    .RESET(n631_4),
    .CE(n130_6) 
);
defparam gap_count_8_s0.INIT=1'b0;
  DFFRE gap_count_7_s0 (
    .Q(gap_count[7]),
    .D(n141_1),
    .CLK(clk_ref),
    .RESET(n631_4),
    .CE(n130_6) 
);
defparam gap_count_7_s0.INIT=1'b0;
  DFFRE gap_count_6_s0 (
    .Q(gap_count[6]),
    .D(n142_1),
    .CLK(clk_ref),
    .RESET(n631_4),
    .CE(n130_6) 
);
defparam gap_count_6_s0.INIT=1'b0;
  DFFRE gap_count_5_s0 (
    .Q(gap_count[5]),
    .D(n143_1),
    .CLK(clk_ref),
    .RESET(n631_4),
    .CE(n130_6) 
);
defparam gap_count_5_s0.INIT=1'b0;
  DFFRE gap_count_4_s0 (
    .Q(gap_count[4]),
    .D(n144_1),
    .CLK(clk_ref),
    .RESET(n631_4),
    .CE(n130_6) 
);
defparam gap_count_4_s0.INIT=1'b0;
  DFFRE gap_count_3_s0 (
    .Q(gap_count[3]),
    .D(n145_1),
    .CLK(clk_ref),
    .RESET(n631_4),
    .CE(n130_6) 
);
defparam gap_count_3_s0.INIT=1'b0;
  DFFRE gap_count_2_s0 (
    .Q(gap_count[2]),
    .D(n146_1),
    .CLK(clk_ref),
    .RESET(n631_4),
    .CE(n130_6) 
);
defparam gap_count_2_s0.INIT=1'b0;
  DFFRE gap_count_1_s0 (
    .Q(gap_count[1]),
    .D(n147_1),
    .CLK(clk_ref),
    .RESET(n631_4),
    .CE(n130_6) 
);
defparam gap_count_1_s0.INIT=1'b0;
  DFFRE command_mode_s0 (
    .Q(command_mode),
    .D(pending_mode),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(n233_4) 
);
defparam command_mode_s0.INIT=1'b0;
  DFFRE pending_mode_s0 (
    .Q(pending_mode),
    .D(rx_byte[0]),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(n234_4) 
);
defparam pending_mode_s0.INIT=1'b0;
  DFFCE ready_meta_1_s0 (
    .Q(ready_meta[1]),
    .D(ready_meta[0]),
    .CLK(clk_ref),
    .CLEAR(n261_5),
    .CE(VCC) 
);
defparam ready_meta_1_s0.INIT=1'b0;
  DFFCE ready_meta_0_s0 (
    .Q(ready_meta[0]),
    .D(VCC),
    .CLK(clk_ref),
    .CLEAR(n261_5),
    .CE(VCC) 
);
defparam ready_meta_0_s0.INIT=1'b0;
  DFFCE reset_meta_1_s0 (
    .Q(reset_meta[1]),
    .D(reset_meta[0]),
    .CLK(clk_ref),
    .CLEAR(GND),
    .CE(VCC) 
);
defparam reset_meta_1_s0.INIT=1'b0;
  DFFCE reset_meta_0_s0 (
    .Q(reset_meta[0]),
    .D(cpu_reset_n),
    .CLK(clk_ref),
    .CLEAR(GND),
    .CE(VCC) 
);
defparam reset_meta_0_s0.INIT=1'b0;
  DFFRE command_epoch_3_s2 (
    .Q(command_epoch[3]),
    .D(n269_4),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(command_valid) 
);
defparam command_epoch_3_s2.INIT=1'b0;
  DFFRE command_epoch_2_s1 (
    .Q(command_epoch[2]),
    .D(n270_4),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(command_valid) 
);
defparam command_epoch_2_s1.INIT=1'b0;
  DFFRE command_epoch_1_s1 (
    .Q(command_epoch[1]),
    .D(n271_4),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(command_valid) 
);
defparam command_epoch_1_s1.INIT=1'b0;
  DFFRE command_epoch_0_s1 (
    .Q(command_epoch[0]),
    .D(n272_6),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(command_valid) 
);
defparam command_epoch_0_s1.INIT=1'b0;
  DFFRE hold_count_9_s0 (
    .Q(hold_count[9]),
    .D(n304_7),
    .CLK(clk_ref),
    .RESET(command_valid),
    .CE(holding) 
);
defparam hold_count_9_s0.INIT=1'b0;
  DFFRE hold_count_8_s0 (
    .Q(hold_count[8]),
    .D(n305_7),
    .CLK(clk_ref),
    .RESET(command_valid),
    .CE(holding) 
);
defparam hold_count_8_s0.INIT=1'b0;
  DFFRE hold_count_7_s0 (
    .Q(hold_count[7]),
    .D(n306_7),
    .CLK(clk_ref),
    .RESET(command_valid),
    .CE(holding) 
);
defparam hold_count_7_s0.INIT=1'b0;
  DFFRE hold_count_6_s0 (
    .Q(hold_count[6]),
    .D(n307_7),
    .CLK(clk_ref),
    .RESET(command_valid),
    .CE(holding) 
);
defparam hold_count_6_s0.INIT=1'b0;
  DFFRE hold_count_5_s0 (
    .Q(hold_count[5]),
    .D(n308_9),
    .CLK(clk_ref),
    .RESET(command_valid),
    .CE(holding) 
);
defparam hold_count_5_s0.INIT=1'b0;
  DFFRE hold_count_4_s0 (
    .Q(hold_count[4]),
    .D(n309_7),
    .CLK(clk_ref),
    .RESET(command_valid),
    .CE(holding) 
);
defparam hold_count_4_s0.INIT=1'b0;
  DFFRE hold_count_3_s0 (
    .Q(hold_count[3]),
    .D(n310_7),
    .CLK(clk_ref),
    .RESET(command_valid),
    .CE(holding) 
);
defparam hold_count_3_s0.INIT=1'b0;
  DFFRE hold_count_2_s0 (
    .Q(hold_count[2]),
    .D(n311_9),
    .CLK(clk_ref),
    .RESET(command_valid),
    .CE(holding) 
);
defparam hold_count_2_s0.INIT=1'b0;
  DFFRE hold_count_1_s0 (
    .Q(hold_count[1]),
    .D(n312_7),
    .CLK(clk_ref),
    .RESET(command_valid),
    .CE(holding) 
);
defparam hold_count_1_s0.INIT=1'b0;
  DFFRE hold_count_0_s0 (
    .Q(hold_count[0]),
    .D(n313_8),
    .CLK(clk_ref),
    .RESET(command_valid),
    .CE(holding) 
);
defparam hold_count_0_s0.INIT=1'b0;
  DFFRE wait_count_21_s0 (
    .Q(wait_count[21]),
    .D(n401_1),
    .CLK(clk_ref),
    .RESET(n361_3),
    .CE(wait_count_21_6) 
);
defparam wait_count_21_s0.INIT=1'b0;
  DFFRE wait_count_20_s0 (
    .Q(wait_count[20]),
    .D(n402_1),
    .CLK(clk_ref),
    .RESET(n361_3),
    .CE(wait_count_21_6) 
);
defparam wait_count_20_s0.INIT=1'b0;
  DFFRE wait_count_19_s0 (
    .Q(wait_count[19]),
    .D(n403_1),
    .CLK(clk_ref),
    .RESET(n361_3),
    .CE(wait_count_21_6) 
);
defparam wait_count_19_s0.INIT=1'b0;
  DFFRE wait_count_18_s0 (
    .Q(wait_count[18]),
    .D(n404_1),
    .CLK(clk_ref),
    .RESET(n361_3),
    .CE(wait_count_21_6) 
);
defparam wait_count_18_s0.INIT=1'b0;
  DFFRE wait_count_17_s0 (
    .Q(wait_count[17]),
    .D(n405_1),
    .CLK(clk_ref),
    .RESET(n361_3),
    .CE(wait_count_21_6) 
);
defparam wait_count_17_s0.INIT=1'b0;
  DFFRE wait_count_16_s0 (
    .Q(wait_count[16]),
    .D(n406_1),
    .CLK(clk_ref),
    .RESET(n361_3),
    .CE(wait_count_21_6) 
);
defparam wait_count_16_s0.INIT=1'b0;
  DFFRE wait_count_15_s0 (
    .Q(wait_count[15]),
    .D(n407_1),
    .CLK(clk_ref),
    .RESET(n361_3),
    .CE(wait_count_21_6) 
);
defparam wait_count_15_s0.INIT=1'b0;
  DFFRE wait_count_14_s0 (
    .Q(wait_count[14]),
    .D(n408_1),
    .CLK(clk_ref),
    .RESET(n361_3),
    .CE(wait_count_21_6) 
);
defparam wait_count_14_s0.INIT=1'b0;
  DFFRE wait_count_13_s0 (
    .Q(wait_count[13]),
    .D(n409_1),
    .CLK(clk_ref),
    .RESET(n361_3),
    .CE(wait_count_21_6) 
);
defparam wait_count_13_s0.INIT=1'b0;
  DFFRE wait_count_12_s0 (
    .Q(wait_count[12]),
    .D(n410_1),
    .CLK(clk_ref),
    .RESET(n361_3),
    .CE(wait_count_21_6) 
);
defparam wait_count_12_s0.INIT=1'b0;
  DFFRE wait_count_11_s0 (
    .Q(wait_count[11]),
    .D(n411_1),
    .CLK(clk_ref),
    .RESET(n361_3),
    .CE(wait_count_21_6) 
);
defparam wait_count_11_s0.INIT=1'b0;
  DFFRE wait_count_10_s0 (
    .Q(wait_count[10]),
    .D(n412_1),
    .CLK(clk_ref),
    .RESET(n361_3),
    .CE(wait_count_21_6) 
);
defparam wait_count_10_s0.INIT=1'b0;
  DFFRE wait_count_9_s0 (
    .Q(wait_count[9]),
    .D(n413_1),
    .CLK(clk_ref),
    .RESET(n361_3),
    .CE(wait_count_21_6) 
);
defparam wait_count_9_s0.INIT=1'b0;
  DFFRE wait_count_8_s0 (
    .Q(wait_count[8]),
    .D(n414_1),
    .CLK(clk_ref),
    .RESET(n361_3),
    .CE(wait_count_21_6) 
);
defparam wait_count_8_s0.INIT=1'b0;
  DFFRE wait_count_7_s0 (
    .Q(wait_count[7]),
    .D(n415_1),
    .CLK(clk_ref),
    .RESET(n361_3),
    .CE(wait_count_21_6) 
);
defparam wait_count_7_s0.INIT=1'b0;
  DFFRE wait_count_6_s0 (
    .Q(wait_count[6]),
    .D(n416_1),
    .CLK(clk_ref),
    .RESET(n361_3),
    .CE(wait_count_21_6) 
);
defparam wait_count_6_s0.INIT=1'b0;
  DFFRE wait_count_5_s0 (
    .Q(wait_count[5]),
    .D(n417_1),
    .CLK(clk_ref),
    .RESET(n361_3),
    .CE(wait_count_21_6) 
);
defparam wait_count_5_s0.INIT=1'b0;
  DFFRE wait_count_4_s0 (
    .Q(wait_count[4]),
    .D(n418_1),
    .CLK(clk_ref),
    .RESET(n361_3),
    .CE(wait_count_21_6) 
);
defparam wait_count_4_s0.INIT=1'b0;
  DFFRE wait_count_3_s0 (
    .Q(wait_count[3]),
    .D(n419_1),
    .CLK(clk_ref),
    .RESET(n361_3),
    .CE(wait_count_21_6) 
);
defparam wait_count_3_s0.INIT=1'b0;
  DFFRE wait_count_2_s0 (
    .Q(wait_count[2]),
    .D(n420_1),
    .CLK(clk_ref),
    .RESET(n361_3),
    .CE(wait_count_21_6) 
);
defparam wait_count_2_s0.INIT=1'b0;
  DFFRE wait_count_1_s0 (
    .Q(wait_count[1]),
    .D(n421_1),
    .CLK(clk_ref),
    .RESET(n361_3),
    .CE(wait_count_21_6) 
);
defparam wait_count_1_s0.INIT=1'b0;
  DFFRE wait_count_0_s0 (
    .Q(wait_count[0]),
    .D(n422_6),
    .CLK(clk_ref),
    .RESET(n361_3),
    .CE(wait_count_21_6) 
);
defparam wait_count_0_s0.INIT=1'b0;
  DFFRE delay_done_s2 (
    .Q(delay_done),
    .D(VCC),
    .CLK(clk_ref),
    .RESET(n361_3),
    .CE(n672_3) 
);
defparam delay_done_s2.INIT=1'b0;
  DFFRE ahb_div_7_s0 (
    .Q(ahb_tick),
    .D(n6_1),
    .CLK(ahb_clk),
    .RESET(GND),
    .CE(VCC) 
);
defparam ahb_div_7_s0.INIT=1'b0;
  DFFSE delay_mode_s3 (
    .Q(delay_mode),
    .D(command_mode),
    .CLK(clk_ref),
    .SET(GND),
    .CE(command_valid) 
);
defparam delay_mode_s3.INIT=1'b1;
  DFFRE holding_s8 (
    .Q(holding),
    .D(command_valid),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(holding_15) 
);
defparam holding_s8.INIT=1'b0;
  DFFRE gap_count_0_s1 (
    .Q(gap_count[0]),
    .D(n148_11),
    .CLK(clk_ref),
    .RESET(n631_4),
    .CE(VCC) 
);
defparam gap_count_0_s1.INIT=1'b0;
  ALU n12_s (
    .SUM(n12_1),
    .COUT(n12_2),
    .I0(ahb_div[1]),
    .I1(ahb_div[0]),
    .I3(VCC),
    .CIN(GND) 
);
defparam n12_s.ALU_MODE=0;
  ALU n11_s (
    .SUM(n11_1),
    .COUT(n11_2),
    .I0(ahb_div[2]),
    .I1(GND),
    .I3(VCC),
    .CIN(n12_2) 
);
defparam n11_s.ALU_MODE=0;
  ALU n10_s (
    .SUM(n10_1),
    .COUT(n10_2),
    .I0(ahb_div[3]),
    .I1(GND),
    .I3(VCC),
    .CIN(n11_2) 
);
defparam n10_s.ALU_MODE=0;
  ALU n9_s (
    .SUM(n9_1),
    .COUT(n9_2),
    .I0(ahb_div[4]),
    .I1(GND),
    .I3(VCC),
    .CIN(n10_2) 
);
defparam n9_s.ALU_MODE=0;
  ALU n8_s (
    .SUM(n8_1),
    .COUT(n8_2),
    .I0(ahb_div[5]),
    .I1(GND),
    .I3(VCC),
    .CIN(n9_2) 
);
defparam n8_s.ALU_MODE=0;
  ALU n7_s (
    .SUM(n7_1),
    .COUT(n7_2),
    .I0(ahb_div[6]),
    .I1(GND),
    .I3(VCC),
    .CIN(n8_2) 
);
defparam n7_s.ALU_MODE=0;
  ALU n6_s (
    .SUM(n6_1),
    .COUT(n6_0_COUT),
    .I0(ahb_tick),
    .I1(GND),
    .I3(VCC),
    .CIN(n7_2) 
);
defparam n6_s.ALU_MODE=0;
  ALU n30_s (
    .SUM(n30_1),
    .COUT(n30_2),
    .I0(rtc_div[1]),
    .I1(rtc_div[0]),
    .I3(VCC),
    .CIN(GND) 
);
defparam n30_s.ALU_MODE=0;
  ALU n29_s (
    .SUM(n29_1),
    .COUT(n29_2),
    .I0(rtc_div[2]),
    .I1(GND),
    .I3(VCC),
    .CIN(n30_2) 
);
defparam n29_s.ALU_MODE=0;
  ALU n28_s (
    .SUM(n28_1),
    .COUT(n28_2),
    .I0(rtc_div[3]),
    .I1(GND),
    .I3(VCC),
    .CIN(n29_2) 
);
defparam n28_s.ALU_MODE=0;
  ALU n27_s (
    .SUM(n27_1),
    .COUT(n27_2),
    .I0(rtc_div[4]),
    .I1(GND),
    .I3(VCC),
    .CIN(n28_2) 
);
defparam n27_s.ALU_MODE=0;
  ALU n26_s (
    .SUM(n26_1),
    .COUT(n26_2),
    .I0(rtc_div[5]),
    .I1(GND),
    .I3(VCC),
    .CIN(n27_2) 
);
defparam n26_s.ALU_MODE=0;
  ALU n25_s (
    .SUM(n25_1),
    .COUT(n25_2),
    .I0(rtc_div[6]),
    .I1(GND),
    .I3(VCC),
    .CIN(n26_2) 
);
defparam n25_s.ALU_MODE=0;
  ALU n24_s (
    .SUM(n24_1),
    .COUT(n24_0_COUT),
    .I0(rtc_tick),
    .I1(GND),
    .I3(VCC),
    .CIN(n25_2) 
);
defparam n24_s.ALU_MODE=0;
  ALU n147_s (
    .SUM(n147_1),
    .COUT(n147_2),
    .I0(gap_count[1]),
    .I1(gap_count[0]),
    .I3(VCC),
    .CIN(GND) 
);
defparam n147_s.ALU_MODE=0;
  ALU n146_s (
    .SUM(n146_1),
    .COUT(n146_2),
    .I0(gap_count[2]),
    .I1(GND),
    .I3(VCC),
    .CIN(n147_2) 
);
defparam n146_s.ALU_MODE=0;
  ALU n145_s (
    .SUM(n145_1),
    .COUT(n145_2),
    .I0(gap_count[3]),
    .I1(GND),
    .I3(VCC),
    .CIN(n146_2) 
);
defparam n145_s.ALU_MODE=0;
  ALU n144_s (
    .SUM(n144_1),
    .COUT(n144_2),
    .I0(gap_count[4]),
    .I1(GND),
    .I3(VCC),
    .CIN(n145_2) 
);
defparam n144_s.ALU_MODE=0;
  ALU n143_s (
    .SUM(n143_1),
    .COUT(n143_2),
    .I0(gap_count[5]),
    .I1(GND),
    .I3(VCC),
    .CIN(n144_2) 
);
defparam n143_s.ALU_MODE=0;
  ALU n142_s (
    .SUM(n142_1),
    .COUT(n142_2),
    .I0(gap_count[6]),
    .I1(GND),
    .I3(VCC),
    .CIN(n143_2) 
);
defparam n142_s.ALU_MODE=0;
  ALU n141_s (
    .SUM(n141_1),
    .COUT(n141_2),
    .I0(gap_count[7]),
    .I1(GND),
    .I3(VCC),
    .CIN(n142_2) 
);
defparam n141_s.ALU_MODE=0;
  ALU n140_s (
    .SUM(n140_1),
    .COUT(n140_2),
    .I0(gap_count[8]),
    .I1(GND),
    .I3(VCC),
    .CIN(n141_2) 
);
defparam n140_s.ALU_MODE=0;
  ALU n139_s (
    .SUM(n139_1),
    .COUT(n139_2),
    .I0(gap_count[9]),
    .I1(GND),
    .I3(VCC),
    .CIN(n140_2) 
);
defparam n139_s.ALU_MODE=0;
  ALU n138_s (
    .SUM(n138_1),
    .COUT(n138_2),
    .I0(gap_count[10]),
    .I1(GND),
    .I3(VCC),
    .CIN(n139_2) 
);
defparam n138_s.ALU_MODE=0;
  ALU n137_s (
    .SUM(n137_1),
    .COUT(n137_2),
    .I0(gap_count[11]),
    .I1(GND),
    .I3(VCC),
    .CIN(n138_2) 
);
defparam n137_s.ALU_MODE=0;
  ALU n136_s (
    .SUM(n136_1),
    .COUT(n136_2),
    .I0(gap_count[12]),
    .I1(GND),
    .I3(VCC),
    .CIN(n137_2) 
);
defparam n136_s.ALU_MODE=0;
  ALU n135_s (
    .SUM(n135_1),
    .COUT(n135_2),
    .I0(gap_count[13]),
    .I1(GND),
    .I3(VCC),
    .CIN(n136_2) 
);
defparam n135_s.ALU_MODE=0;
  ALU n134_s (
    .SUM(n134_1),
    .COUT(n134_2),
    .I0(gap_count[14]),
    .I1(GND),
    .I3(VCC),
    .CIN(n135_2) 
);
defparam n134_s.ALU_MODE=0;
  ALU n133_s (
    .SUM(n133_1),
    .COUT(n133_2),
    .I0(gap_count[15]),
    .I1(GND),
    .I3(VCC),
    .CIN(n134_2) 
);
defparam n133_s.ALU_MODE=0;
  ALU n132_s (
    .SUM(n132_1),
    .COUT(n132_0_COUT),
    .I0(gap_count[16]),
    .I1(GND),
    .I3(VCC),
    .CIN(n133_2) 
);
defparam n132_s.ALU_MODE=0;
  ALU n421_s (
    .SUM(n421_1),
    .COUT(n421_2),
    .I0(wait_count[1]),
    .I1(wait_count[0]),
    .I3(VCC),
    .CIN(GND) 
);
defparam n421_s.ALU_MODE=0;
  ALU n420_s (
    .SUM(n420_1),
    .COUT(n420_2),
    .I0(wait_count[2]),
    .I1(GND),
    .I3(VCC),
    .CIN(n421_2) 
);
defparam n420_s.ALU_MODE=0;
  ALU n419_s (
    .SUM(n419_1),
    .COUT(n419_2),
    .I0(wait_count[3]),
    .I1(GND),
    .I3(VCC),
    .CIN(n420_2) 
);
defparam n419_s.ALU_MODE=0;
  ALU n418_s (
    .SUM(n418_1),
    .COUT(n418_2),
    .I0(wait_count[4]),
    .I1(GND),
    .I3(VCC),
    .CIN(n419_2) 
);
defparam n418_s.ALU_MODE=0;
  ALU n417_s (
    .SUM(n417_1),
    .COUT(n417_2),
    .I0(wait_count[5]),
    .I1(GND),
    .I3(VCC),
    .CIN(n418_2) 
);
defparam n417_s.ALU_MODE=0;
  ALU n416_s (
    .SUM(n416_1),
    .COUT(n416_2),
    .I0(wait_count[6]),
    .I1(GND),
    .I3(VCC),
    .CIN(n417_2) 
);
defparam n416_s.ALU_MODE=0;
  ALU n415_s (
    .SUM(n415_1),
    .COUT(n415_2),
    .I0(wait_count[7]),
    .I1(GND),
    .I3(VCC),
    .CIN(n416_2) 
);
defparam n415_s.ALU_MODE=0;
  ALU n414_s (
    .SUM(n414_1),
    .COUT(n414_2),
    .I0(wait_count[8]),
    .I1(GND),
    .I3(VCC),
    .CIN(n415_2) 
);
defparam n414_s.ALU_MODE=0;
  ALU n413_s (
    .SUM(n413_1),
    .COUT(n413_2),
    .I0(wait_count[9]),
    .I1(GND),
    .I3(VCC),
    .CIN(n414_2) 
);
defparam n413_s.ALU_MODE=0;
  ALU n412_s (
    .SUM(n412_1),
    .COUT(n412_2),
    .I0(wait_count[10]),
    .I1(GND),
    .I3(VCC),
    .CIN(n413_2) 
);
defparam n412_s.ALU_MODE=0;
  ALU n411_s (
    .SUM(n411_1),
    .COUT(n411_2),
    .I0(wait_count[11]),
    .I1(GND),
    .I3(VCC),
    .CIN(n412_2) 
);
defparam n411_s.ALU_MODE=0;
  ALU n410_s (
    .SUM(n410_1),
    .COUT(n410_2),
    .I0(wait_count[12]),
    .I1(GND),
    .I3(VCC),
    .CIN(n411_2) 
);
defparam n410_s.ALU_MODE=0;
  ALU n409_s (
    .SUM(n409_1),
    .COUT(n409_2),
    .I0(wait_count[13]),
    .I1(GND),
    .I3(VCC),
    .CIN(n410_2) 
);
defparam n409_s.ALU_MODE=0;
  ALU n408_s (
    .SUM(n408_1),
    .COUT(n408_2),
    .I0(wait_count[14]),
    .I1(GND),
    .I3(VCC),
    .CIN(n409_2) 
);
defparam n408_s.ALU_MODE=0;
  ALU n407_s (
    .SUM(n407_1),
    .COUT(n407_2),
    .I0(wait_count[15]),
    .I1(GND),
    .I3(VCC),
    .CIN(n408_2) 
);
defparam n407_s.ALU_MODE=0;
  ALU n406_s (
    .SUM(n406_1),
    .COUT(n406_2),
    .I0(wait_count[16]),
    .I1(GND),
    .I3(VCC),
    .CIN(n407_2) 
);
defparam n406_s.ALU_MODE=0;
  ALU n405_s (
    .SUM(n405_1),
    .COUT(n405_2),
    .I0(wait_count[17]),
    .I1(GND),
    .I3(VCC),
    .CIN(n406_2) 
);
defparam n405_s.ALU_MODE=0;
  ALU n404_s (
    .SUM(n404_1),
    .COUT(n404_2),
    .I0(wait_count[18]),
    .I1(GND),
    .I3(VCC),
    .CIN(n405_2) 
);
defparam n404_s.ALU_MODE=0;
  ALU n403_s (
    .SUM(n403_1),
    .COUT(n403_2),
    .I0(wait_count[19]),
    .I1(GND),
    .I3(VCC),
    .CIN(n404_2) 
);
defparam n403_s.ALU_MODE=0;
  ALU n402_s (
    .SUM(n402_1),
    .COUT(n402_2),
    .I0(wait_count[20]),
    .I1(GND),
    .I3(VCC),
    .CIN(n403_2) 
);
defparam n402_s.ALU_MODE=0;
  ALU n401_s (
    .SUM(n401_1),
    .COUT(n401_0_COUT),
    .I0(wait_count[21]),
    .I1(GND),
    .I3(VCC),
    .CIN(n402_2) 
);
defparam n401_s.ALU_MODE=0;
  INV n13_s2 (
    .O(n13_6),
    .I(ahb_div[0]) 
);
  INV n31_s2 (
    .O(n31_6),
    .I(rtc_div[0]) 
);
  INV n272_s2 (
    .O(n272_6),
    .I(command_epoch[0]) 
);
  INV n422_s2 (
    .O(n422_6),
    .I(wait_count[0]) 
);
  neo_reset_trial_rx u_rx (
    .clk_ref(clk_ref),
    .serial_rx(serial_rx),
    .up(up[2]),
    .rx_valid(rx_valid),
    .rx_byte(rx_byte[7:0])
);
  VCC VCC_cZ (
    .V(VCC)
);
  GND GND_cZ (
    .G(GND)
);

endmodule
module neo_reset_trial_rx (
  clk_ref,
  serial_rx,
  up,
  rx_valid,
  rx_byte
)
;
input clk_ref;
input serial_rx;
input [2:2] up;
output rx_valid;
output [7:0] rx_byte;
wire n463_3;
wire n211_3;
wire n212_3;
wire n213_3;
wire n481_3;
wire busy_8;
wire bit_idx_3_6;
wire bit_idx_0_6;
wire cnt_15_6;
wire n107_6;
wire n106_6;
wire n105_6;
wire n104_6;
wire n103_6;
wire n102_6;
wire n101_6;
wire n100_6;
wire n99_6;
wire n98_6;
wire n97_6;
wire n108_6;
wire n110_6;
wire n236_6;
wire n112_6;
wire n109_7;
wire n111_7;
wire n232_7;
wire n463_4;
wire n463_5;
wire n211_4;
wire n212_4;
wire n213_4;
wire n213_5;
wire n481_4;
wire n481_5;
wire busy_9;
wire n107_7;
wire n106_7;
wire n105_7;
wire n104_7;
wire n103_7;
wire n102_7;
wire n101_7;
wire n100_7;
wire n98_7;
wire n108_7;
wire n110_7;
wire n463_7;
wire n463_8;
wire busy_10;
wire n101_8;
wire n100_8;
wire n98_8;
wire n299_6;
wire n463_10;
wire busy;
wire n270_5;
wire [3:0] bit_idx;
wire [15:0] cnt;
wire [7:0] shift;
wire [1:0] rx_sync;
wire VCC;
wire GND;
  LUT4 n463_s0 (
    .F(n463_3),
    .I0(rx_sync[1]),
    .I1(n463_4),
    .I2(n463_5),
    .I3(n463_10) 
);
defparam n463_s0.INIT=16'h8000;
  LUT4 n211_s0 (
    .F(n211_3),
    .I0(rx_sync[1]),
    .I1(n211_4),
    .I2(busy),
    .I3(bit_idx[3]) 
);
defparam n211_s0.INIT=16'h3AC0;
  LUT4 n212_s0 (
    .F(n212_3),
    .I0(rx_sync[1]),
    .I1(n212_4),
    .I2(busy),
    .I3(bit_idx[2]) 
);
defparam n212_s0.INIT=16'h3AC0;
  LUT4 n213_s0 (
    .F(n213_3),
    .I0(n213_4),
    .I1(n213_5),
    .I2(bit_idx[1]),
    .I3(busy) 
);
defparam n213_s0.INIT=16'h14C0;
  LUT4 n481_s0 (
    .F(n481_3),
    .I0(n481_4),
    .I1(n463_5),
    .I2(n481_5),
    .I3(n463_4) 
);
defparam n481_s0.INIT=16'h4000;
  LUT3 busy_s3 (
    .F(busy_8),
    .I0(rx_sync[1]),
    .I1(busy_9),
    .I2(busy) 
);
defparam busy_s3.INIT=8'hC5;
  LUT3 bit_idx_3_s2 (
    .F(bit_idx_3_6),
    .I0(busy_9),
    .I1(busy),
    .I2(up[2]) 
);
defparam bit_idx_3_s2.INIT=8'hB0;
  LUT3 bit_idx_0_s2 (
    .F(bit_idx_0_6),
    .I0(busy_9),
    .I1(busy),
    .I2(cnt_15_6) 
);
defparam bit_idx_0_s2.INIT=8'hB0;
  LUT3 cnt_15_s2 (
    .F(cnt_15_6),
    .I0(rx_sync[1]),
    .I1(busy),
    .I2(up[2]) 
);
defparam cnt_15_s2.INIT=8'hD0;
  LUT4 n107_s1 (
    .F(n107_6),
    .I0(busy_9),
    .I1(n107_7),
    .I2(cnt[5]),
    .I3(busy) 
);
defparam n107_s1.INIT=16'h1400;
  LUT4 n106_s1 (
    .F(n106_6),
    .I0(busy_9),
    .I1(n106_7),
    .I2(cnt[6]),
    .I3(busy) 
);
defparam n106_s1.INIT=16'h1400;
  LUT4 n105_s1 (
    .F(n105_6),
    .I0(busy_9),
    .I1(n105_7),
    .I2(cnt[7]),
    .I3(busy) 
);
defparam n105_s1.INIT=16'h1400;
  LUT4 n104_s1 (
    .F(n104_6),
    .I0(busy_9),
    .I1(n104_7),
    .I2(cnt[8]),
    .I3(busy) 
);
defparam n104_s1.INIT=16'h1400;
  LUT4 n103_s1 (
    .F(n103_6),
    .I0(busy_9),
    .I1(n103_7),
    .I2(cnt[9]),
    .I3(busy) 
);
defparam n103_s1.INIT=16'h1400;
  LUT4 n102_s1 (
    .F(n102_6),
    .I0(busy_9),
    .I1(n102_7),
    .I2(cnt[10]),
    .I3(busy) 
);
defparam n102_s1.INIT=16'h1400;
  LUT3 n101_s1 (
    .F(n101_6),
    .I0(busy_9),
    .I1(busy),
    .I2(n101_7) 
);
defparam n101_s1.INIT=8'h04;
  LUT4 n100_s1 (
    .F(n100_6),
    .I0(n481_5),
    .I1(cnt[12]),
    .I2(n100_7),
    .I3(busy) 
);
defparam n100_s1.INIT=16'h1C00;
  LUT4 n99_s1 (
    .F(n99_6),
    .I0(n481_5),
    .I1(cnt[13]),
    .I2(n463_4),
    .I3(busy) 
);
defparam n99_s1.INIT=16'h1C00;
  LUT4 n98_s1 (
    .F(n98_6),
    .I0(cnt[15]),
    .I1(cnt[14]),
    .I2(n98_7),
    .I3(busy) 
);
defparam n98_s1.INIT=16'h2C00;
  LUT4 n97_s1 (
    .F(n97_6),
    .I0(n98_7),
    .I1(cnt[14]),
    .I2(cnt[15]),
    .I3(busy) 
);
defparam n97_s1.INIT=16'hD000;
  LUT3 n108_s1 (
    .F(n108_6),
    .I0(cnt[4]),
    .I1(n108_7),
    .I2(busy) 
);
defparam n108_s1.INIT=8'h60;
  LUT4 n110_s1 (
    .F(n110_6),
    .I0(busy_9),
    .I1(cnt[2]),
    .I2(n110_7),
    .I3(busy) 
);
defparam n110_s1.INIT=16'h1400;
  LUT3 n236_s1 (
    .F(n236_6),
    .I0(bit_idx[0]),
    .I1(n232_7),
    .I2(busy) 
);
defparam n236_s1.INIT=8'h60;
  LUT3 n112_s1 (
    .F(n112_6),
    .I0(cnt[0]),
    .I1(busy_9),
    .I2(busy) 
);
defparam n112_s1.INIT=8'h10;
  LUT4 n109_s2 (
    .F(n109_7),
    .I0(cnt[2]),
    .I1(n110_7),
    .I2(cnt[3]),
    .I3(busy) 
);
defparam n109_s2.INIT=16'hB4FF;
  LUT4 n111_s2 (
    .F(n111_7),
    .I0(busy),
    .I1(busy_9),
    .I2(cnt[1]),
    .I3(cnt[0]) 
);
defparam n111_s2.INIT=16'h7557;
  LUT4 n232_s2 (
    .F(n232_7),
    .I0(n213_4),
    .I1(rx_sync[1]),
    .I2(busy),
    .I3(n481_4) 
);
defparam n232_s2.INIT=16'h1FFF;
  LUT4 n463_s1 (
    .F(n463_4),
    .I0(cnt[8]),
    .I1(n108_7),
    .I2(n463_7),
    .I3(n463_8) 
);
defparam n463_s1.INIT=16'h4000;
  LUT2 n463_s2 (
    .F(n463_5),
    .I0(up[2]),
    .I1(busy) 
);
defparam n463_s2.INIT=4'h8;
  LUT3 n211_s1 (
    .F(n211_4),
    .I0(bit_idx[0]),
    .I1(bit_idx[1]),
    .I2(bit_idx[2]) 
);
defparam n211_s1.INIT=8'h80;
  LUT2 n212_s1 (
    .F(n212_4),
    .I0(bit_idx[0]),
    .I1(bit_idx[1]) 
);
defparam n212_s1.INIT=4'h8;
  LUT4 n213_s1 (
    .F(n213_4),
    .I0(bit_idx[1]),
    .I1(bit_idx[2]),
    .I2(bit_idx[0]),
    .I3(bit_idx[3]) 
);
defparam n213_s1.INIT=16'h1000;
  LUT3 n213_s2 (
    .F(n213_5),
    .I0(rx_sync[1]),
    .I1(bit_idx[0]),
    .I2(busy) 
);
defparam n213_s2.INIT=8'hCA;
  LUT4 n481_s1 (
    .F(n481_4),
    .I0(bit_idx[1]),
    .I1(bit_idx[2]),
    .I2(bit_idx[0]),
    .I3(bit_idx[3]) 
);
defparam n481_s1.INIT=16'h1001;
  LUT3 n481_s2 (
    .F(n481_5),
    .I0(cnt[13]),
    .I1(cnt[14]),
    .I2(cnt[15]) 
);
defparam n481_s2.INIT=8'h01;
  LUT4 busy_s4 (
    .F(busy_9),
    .I0(busy_10),
    .I1(n108_7),
    .I2(n463_7),
    .I3(n463_8) 
);
defparam busy_s4.INIT=16'h8000;
  LUT2 n107_s2 (
    .F(n107_7),
    .I0(cnt[4]),
    .I1(n108_7) 
);
defparam n107_s2.INIT=4'h4;
  LUT3 n106_s2 (
    .F(n106_7),
    .I0(cnt[4]),
    .I1(cnt[5]),
    .I2(n108_7) 
);
defparam n106_s2.INIT=8'h10;
  LUT4 n105_s2 (
    .F(n105_7),
    .I0(cnt[4]),
    .I1(cnt[5]),
    .I2(cnt[6]),
    .I3(n108_7) 
);
defparam n105_s2.INIT=16'h0100;
  LUT2 n104_s2 (
    .F(n104_7),
    .I0(n108_7),
    .I1(n463_7) 
);
defparam n104_s2.INIT=4'h8;
  LUT3 n103_s2 (
    .F(n103_7),
    .I0(cnt[8]),
    .I1(n108_7),
    .I2(n463_7) 
);
defparam n103_s2.INIT=8'h40;
  LUT4 n102_s2 (
    .F(n102_7),
    .I0(cnt[8]),
    .I1(cnt[9]),
    .I2(n108_7),
    .I3(n463_7) 
);
defparam n102_s2.INIT=16'h1000;
  LUT4 n101_s2 (
    .F(n101_7),
    .I0(n101_8),
    .I1(n108_7),
    .I2(n463_7),
    .I3(cnt[11]) 
);
defparam n101_s2.INIT=16'h807F;
  LUT4 n100_s2 (
    .F(n100_7),
    .I0(cnt[8]),
    .I1(n100_8),
    .I2(n108_7),
    .I3(n463_7) 
);
defparam n100_s2.INIT=16'h4000;
  LUT4 n98_s2 (
    .F(n98_7),
    .I0(n98_8),
    .I1(n108_7),
    .I2(n463_7),
    .I3(n463_8) 
);
defparam n98_s2.INIT=16'h8000;
  LUT4 n108_s2 (
    .F(n108_7),
    .I0(cnt[0]),
    .I1(cnt[1]),
    .I2(cnt[2]),
    .I3(cnt[3]) 
);
defparam n108_s2.INIT=16'h0001;
  LUT2 n110_s2 (
    .F(n110_7),
    .I0(cnt[0]),
    .I1(cnt[1]) 
);
defparam n110_s2.INIT=4'h1;
  LUT4 n463_s4 (
    .F(n463_7),
    .I0(cnt[4]),
    .I1(cnt[5]),
    .I2(cnt[6]),
    .I3(cnt[7]) 
);
defparam n463_s4.INIT=16'h0001;
  LUT4 n463_s5 (
    .F(n463_8),
    .I0(cnt[9]),
    .I1(cnt[10]),
    .I2(cnt[11]),
    .I3(cnt[12]) 
);
defparam n463_s5.INIT=16'h0001;
  LUT4 busy_s5 (
    .F(busy_10),
    .I0(cnt[8]),
    .I1(cnt[13]),
    .I2(cnt[14]),
    .I3(cnt[15]) 
);
defparam busy_s5.INIT=16'h0001;
  LUT3 n101_s3 (
    .F(n101_8),
    .I0(cnt[8]),
    .I1(cnt[9]),
    .I2(cnt[10]) 
);
defparam n101_s3.INIT=8'h01;
  LUT3 n100_s3 (
    .F(n100_8),
    .I0(cnt[9]),
    .I1(cnt[10]),
    .I2(cnt[11]) 
);
defparam n100_s3.INIT=8'h01;
  LUT2 n98_s3 (
    .F(n98_8),
    .I0(cnt[8]),
    .I1(cnt[13]) 
);
defparam n98_s3.INIT=4'h1;
  LUT4 n299_s2 (
    .F(n299_6),
    .I0(n463_4),
    .I1(up[2]),
    .I2(busy),
    .I3(n463_10) 
);
defparam n299_s2.INIT=16'h7FFF;
  LUT4 n463_s6 (
    .F(n463_10),
    .I0(n213_4),
    .I1(cnt[13]),
    .I2(cnt[14]),
    .I3(cnt[15]) 
);
defparam n463_s6.INIT=16'h0002;
  DFFRE valid_s0 (
    .Q(rx_valid),
    .D(rx_sync[1]),
    .CLK(clk_ref),
    .RESET(n299_6),
    .CE(VCC) 
);
defparam valid_s0.INIT=1'b0;
  DFFRE bit_idx_3_s0 (
    .Q(bit_idx[3]),
    .D(n211_3),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(bit_idx_3_6) 
);
defparam bit_idx_3_s0.INIT=1'b0;
  DFFRE bit_idx_2_s0 (
    .Q(bit_idx[2]),
    .D(n212_3),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(bit_idx_3_6) 
);
defparam bit_idx_2_s0.INIT=1'b0;
  DFFRE bit_idx_1_s0 (
    .Q(bit_idx[1]),
    .D(n213_3),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(bit_idx_3_6) 
);
defparam bit_idx_1_s0.INIT=1'b0;
  DFFRE bit_idx_0_s0 (
    .Q(bit_idx[0]),
    .D(n236_6),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(bit_idx_0_6) 
);
defparam bit_idx_0_s0.INIT=1'b0;
  DFFRE cnt_15_s0 (
    .Q(cnt[15]),
    .D(n97_6),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(cnt_15_6) 
);
defparam cnt_15_s0.INIT=1'b0;
  DFFRE cnt_14_s0 (
    .Q(cnt[14]),
    .D(n98_6),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(cnt_15_6) 
);
defparam cnt_14_s0.INIT=1'b0;
  DFFRE cnt_13_s0 (
    .Q(cnt[13]),
    .D(n99_6),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(cnt_15_6) 
);
defparam cnt_13_s0.INIT=1'b0;
  DFFRE cnt_12_s0 (
    .Q(cnt[12]),
    .D(n100_6),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(cnt_15_6) 
);
defparam cnt_12_s0.INIT=1'b0;
  DFFRE cnt_11_s0 (
    .Q(cnt[11]),
    .D(n101_6),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(cnt_15_6) 
);
defparam cnt_11_s0.INIT=1'b0;
  DFFRE cnt_10_s0 (
    .Q(cnt[10]),
    .D(n102_6),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(cnt_15_6) 
);
defparam cnt_10_s0.INIT=1'b0;
  DFFRE cnt_9_s0 (
    .Q(cnt[9]),
    .D(n103_6),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(cnt_15_6) 
);
defparam cnt_9_s0.INIT=1'b0;
  DFFRE cnt_8_s0 (
    .Q(cnt[8]),
    .D(n104_6),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(cnt_15_6) 
);
defparam cnt_8_s0.INIT=1'b0;
  DFFRE cnt_7_s0 (
    .Q(cnt[7]),
    .D(n105_6),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(cnt_15_6) 
);
defparam cnt_7_s0.INIT=1'b0;
  DFFRE cnt_6_s0 (
    .Q(cnt[6]),
    .D(n106_6),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(cnt_15_6) 
);
defparam cnt_6_s0.INIT=1'b0;
  DFFRE cnt_5_s0 (
    .Q(cnt[5]),
    .D(n107_6),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(cnt_15_6) 
);
defparam cnt_5_s0.INIT=1'b0;
  DFFRE cnt_4_s0 (
    .Q(cnt[4]),
    .D(n108_6),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(cnt_15_6) 
);
defparam cnt_4_s0.INIT=1'b0;
  DFFRE cnt_3_s0 (
    .Q(cnt[3]),
    .D(n109_7),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(cnt_15_6) 
);
defparam cnt_3_s0.INIT=1'b0;
  DFFRE cnt_2_s0 (
    .Q(cnt[2]),
    .D(n110_6),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(cnt_15_6) 
);
defparam cnt_2_s0.INIT=1'b0;
  DFFRE cnt_1_s0 (
    .Q(cnt[1]),
    .D(n111_7),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(cnt_15_6) 
);
defparam cnt_1_s0.INIT=1'b0;
  DFFRE cnt_0_s0 (
    .Q(cnt[0]),
    .D(n112_6),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(cnt_15_6) 
);
defparam cnt_0_s0.INIT=1'b0;
  DFFRE data_7_s0 (
    .Q(rx_byte[7]),
    .D(shift[7]),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(n463_3) 
);
defparam data_7_s0.INIT=1'b0;
  DFFRE data_6_s0 (
    .Q(rx_byte[6]),
    .D(shift[6]),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(n463_3) 
);
defparam data_6_s0.INIT=1'b0;
  DFFRE data_5_s0 (
    .Q(rx_byte[5]),
    .D(shift[5]),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(n463_3) 
);
defparam data_5_s0.INIT=1'b0;
  DFFRE data_4_s0 (
    .Q(rx_byte[4]),
    .D(shift[4]),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(n463_3) 
);
defparam data_4_s0.INIT=1'b0;
  DFFRE data_3_s0 (
    .Q(rx_byte[3]),
    .D(shift[3]),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(n463_3) 
);
defparam data_3_s0.INIT=1'b0;
  DFFRE data_2_s0 (
    .Q(rx_byte[2]),
    .D(shift[2]),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(n463_3) 
);
defparam data_2_s0.INIT=1'b0;
  DFFRE data_1_s0 (
    .Q(rx_byte[1]),
    .D(shift[1]),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(n463_3) 
);
defparam data_1_s0.INIT=1'b0;
  DFFRE data_0_s0 (
    .Q(rx_byte[0]),
    .D(shift[0]),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(n463_3) 
);
defparam data_0_s0.INIT=1'b0;
  DFFRE shift_7_s0 (
    .Q(shift[7]),
    .D(rx_sync[1]),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(n481_3) 
);
defparam shift_7_s0.INIT=1'b0;
  DFFRE shift_6_s0 (
    .Q(shift[6]),
    .D(shift[7]),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(n481_3) 
);
defparam shift_6_s0.INIT=1'b0;
  DFFRE shift_5_s0 (
    .Q(shift[5]),
    .D(shift[6]),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(n481_3) 
);
defparam shift_5_s0.INIT=1'b0;
  DFFRE shift_4_s0 (
    .Q(shift[4]),
    .D(shift[5]),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(n481_3) 
);
defparam shift_4_s0.INIT=1'b0;
  DFFRE shift_3_s0 (
    .Q(shift[3]),
    .D(shift[4]),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(n481_3) 
);
defparam shift_3_s0.INIT=1'b0;
  DFFRE shift_2_s0 (
    .Q(shift[2]),
    .D(shift[3]),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(n481_3) 
);
defparam shift_2_s0.INIT=1'b0;
  DFFRE shift_1_s0 (
    .Q(shift[1]),
    .D(shift[2]),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(n481_3) 
);
defparam shift_1_s0.INIT=1'b0;
  DFFRE shift_0_s0 (
    .Q(shift[0]),
    .D(shift[1]),
    .CLK(clk_ref),
    .RESET(GND),
    .CE(n481_3) 
);
defparam shift_0_s0.INIT=1'b0;
  DFFSE rx_sync_1_s1 (
    .Q(rx_sync[1]),
    .D(rx_sync[0]),
    .CLK(clk_ref),
    .SET(GND),
    .CE(VCC) 
);
defparam rx_sync_1_s1.INIT=1'b1;
  DFFSE rx_sync_0_s1 (
    .Q(rx_sync[0]),
    .D(serial_rx),
    .CLK(clk_ref),
    .SET(GND),
    .CE(VCC) 
);
defparam rx_sync_0_s1.INIT=1'b1;
  DFFRE busy_s1 (
    .Q(busy),
    .D(n232_7),
    .CLK(clk_ref),
    .RESET(n270_5),
    .CE(busy_8) 
);
defparam busy_s1.INIT=1'b0;
  INV n270_s2 (
    .O(n270_5),
    .I(up[2]) 
);
  VCC VCC_cZ (
    .V(VCC)
);
  GND GND_cZ (
    .G(GND)
);
endmodule
