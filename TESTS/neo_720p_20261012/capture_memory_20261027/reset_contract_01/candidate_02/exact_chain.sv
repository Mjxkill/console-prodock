`timescale 1ns/1ps
`default_nettype none
// Exact extracted fabric reset blocks. NO hard CPU or PLL behavioral substitute.
module exact_soc_reset(input wire ahb_clk, rst_key_n, trial_release, output wire por_n);
    reg  [1:0] init_sync = 2'b00;
    always @(posedge ahb_clk or negedge rst_key_n)
        if (!rst_key_n) init_sync <= 2'b00;
        else init_sync <= {init_sync[0], trial_release};
    wire ae350_rstn = init_sync[1];
    assign por_n=ae350_rstn;
endmodule
module exact_chain(input wire clk, bus80_clk, rtc_clk, pll_ae350_lock, ddr_init, uart_rx,
 output wire por_n, trial_done_o, trial_holding_o);
 wire ahb_clk=bus80_clk;
 wire [3:0] soc_dbg={3'b000,por_n}; // Only bit0 is consumed by exact trial instance.
    reg [1:0] ae350_rst_sync = 2'b11;
    always @(posedge bus80_clk or negedge pll_ae350_lock)
        if (!pll_ae350_lock) ae350_rst_sync <= 2'b11;
        else ae350_rst_sync <= {ae350_rst_sync[0], 1'b0};
    wire ae350_por_n = ~ae350_rst_sync[1];
    wire trial_request, trial_mode, trial_holding, trial_done;
    wire trial_ahb_tick, trial_rtc_tick;
    wire [3:0] trial_epoch;
    neo_reset_trial u_reset_trial (
        .clk_ref(clk), .ahb_clk(bus80_clk), .rtc_clk(rtc_clk), .serial_rx(uart_rx),
        .ddr_ready(ddr_init), .pll_ready(pll_ae350_lock && ae350_por_n), .cpu_reset_n(soc_dbg[0]),
        .release_request(trial_request), .delay_mode(trial_mode), .command_epoch(trial_epoch),
        .holding(trial_holding), .delay_done(trial_done),
        .ahb_tick(trial_ahb_tick), .rtc_tick(trial_rtc_tick));
 exact_soc_reset u_soc(.ahb_clk(ahb_clk),.rst_key_n(ae350_por_n && trial_request),.trial_release(trial_request),.por_n(por_n));
 assign trial_done_o=trial_done;
 assign trial_holding_o=trial_holding;
endmodule
`default_nettype wire
