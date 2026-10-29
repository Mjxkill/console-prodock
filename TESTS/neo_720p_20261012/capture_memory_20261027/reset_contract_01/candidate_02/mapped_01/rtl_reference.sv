`timescale 1ns/1ps
`default_nettype none
// Exact extracted fabric reset blocks. NO hard CPU or PLL behavioral substitute.
module exact_soc_reset_rtl(input wire ahb_clk, rst_key_n, trial_release, output wire por_n);
    reg  [1:0] init_sync = 2'b00;
    always @(posedge ahb_clk or negedge rst_key_n)
        if (!rst_key_n) init_sync <= 2'b00;
        else init_sync <= {init_sync[0], trial_release};
    wire ae350_rstn = init_sync[1];
    assign por_n=ae350_rstn;
endmodule
module exact_chain_rtl(input wire clk, bus80_clk, rtc_clk, pll_ae350_lock, ddr_init, uart_rx,
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
    neo_reset_trial_rtl u_reset_trial (
        .clk_ref(clk), .ahb_clk(bus80_clk), .rtc_clk(rtc_clk), .serial_rx(uart_rx),
        .ddr_ready(ddr_init), .pll_ready(pll_ae350_lock && ae350_por_n), .cpu_reset_n(soc_dbg[0]),
        .release_request(trial_request), .delay_mode(trial_mode), .command_epoch(trial_epoch),
        .holding(trial_holding), .delay_done(trial_done),
        .ahb_tick(trial_ahb_tick), .rtc_tick(trial_rtc_tick));
 exact_soc_reset_rtl u_soc(.ahb_clk(ahb_clk),.rst_key_n(ae350_por_n && trial_request),.trial_release(trial_request),.por_n(por_n));
 assign trial_done_o=trial_done;
 assign trial_holding_o=trial_holding;
endmodule
`default_nettype wire

// Neo-only experiment. This module never drives a PLL or DDR reset.
// The existing AE350 two-flop reset synchronizer remains downstream.
`default_nettype none
module neo_reset_trial_rtl #(
    parameter integer WAIT_CYCLES = 2500000, // user-selected 50 ms at 50 MHz
    parameter integer MIN_LOCK_CYCLES = 104000, // 2.08 ms minimum in diagnostic mode0
    parameter integer HOLD_CYCLES = 1000,    // common 20 us warm-reset hold
    parameter integer GAP_CYCLES = 100000,
    parameter integer UART_DIV = 25         // existing BL616 relay: 2 Mbit/s
) (
    input wire clk_ref, ahb_clk, rtc_clk, serial_rx,
    input wire ddr_ready, pll_ready, cpu_reset_n,
    output wire release_request,
    output reg delay_mode = 1'b1,
    output reg [3:0] command_epoch = 0,
    output reg holding = 0,
    output reg delay_done = 0,
    output wire ahb_tick, rtc_tick
);
    localparam integer MAX_WAIT_CYCLES = WAIT_CYCLES > MIN_LOCK_CYCLES ? WAIT_CYCLES : MIN_LOCK_CYCLES;
    localparam integer WAIT_WIDTH = MAX_WAIT_CYCLES > 1 ? $clog2(MAX_WAIT_CYCLES) : 1;
    localparam integer HOLD_WIDTH = HOLD_CYCLES > 1 ? $clog2(HOLD_CYCLES) : 1;
    localparam integer GAP_WIDTH = GAP_CYCLES > 1 ? $clog2(GAP_CYCLES) : 1;
    // Independent activity witnesses: never reset by the CPU/bus under test.
    reg [7:0] ahb_div = 0, rtc_div = 0;
    always @(posedge ahb_clk) ahb_div <= ahb_div + 1'b1;
    always @(posedge rtc_clk) rtc_div <= rtc_div + 1'b1;
    assign ahb_tick = ahb_div[7];
    assign rtc_tick = rtc_div[7];

    reg [2:0] up = 0;
    always @(posedge clk_ref) up <= {up[1:0], 1'b1};
    wire [7:0] rx_byte;
    wire rx_valid;
    neo_reset_trial_rx_rtl #(.DIV_WIDTH(16)) u_rx (
        .clk(clk_ref), .rst(!up[2]), .clk_div(16'(UART_DIV)),
        .rx(serial_rx), .data(rx_byte), .valid(rx_valid));

    // A5 5A 52 31 35 mode complement 0D. Only mode 0/1 is accepted.
    // Parser timeout prevents unrelated console bytes completing a stale command.
    reg [2:0] parse_state = 0;
    reg pending_mode = 0;
    reg [GAP_WIDTH-1:0] gap_count = 0;
    reg command_valid = 0, command_mode = 0;
    always @(posedge clk_ref) begin
        command_valid <= 0;
        if (!up[2]) begin parse_state <= 0; gap_count <= 0; end
        else if (parse_state != 0 && gap_count == GAP_WIDTH'(GAP_CYCLES-1)) begin
            parse_state <= 0; gap_count <= 0;
        end else if (rx_valid) begin
            gap_count <= 0;
            case (parse_state)
                0: parse_state <= rx_byte == 8'ha5 ? 1 : 0;
                1: parse_state <= rx_byte == 8'h5a ? 2 : 0;
                2: parse_state <= rx_byte == 8'h52 ? 3 : 0;
                3: parse_state <= rx_byte == 8'h31 ? 4 : 0;
                4: parse_state <= rx_byte == 8'h35 ? 5 : 0;
                5: begin
                    if (rx_byte < 2) begin pending_mode <= rx_byte[0]; parse_state <= 6; end
                    else parse_state <= 0;
                end
                6: parse_state <= rx_byte == (pending_mode ? 8'hfe : 8'hff) ? 7 : 0;
                7: begin
                    parse_state <= 0;
                    if (rx_byte == 8'h0d) begin command_valid <= 1; command_mode <= pending_mode; end
                end
            endcase
        end else if (parse_state != 0) gap_count <= gap_count + 1'b1;
    end

    // Loss invalidates the authorization even between reference-clock edges.
    // Release is synchronized; counters remain ordinary clk_ref registers.
    wire available = ddr_ready && pll_ready;
    reg [1:0] ready_meta = 0, reset_meta = 0;
    always @(posedge clk_ref or negedge available) begin
        if (!available) ready_meta <= 2'b00;
        else ready_meta <= {ready_meta[0], 1'b1};
    end
    always @(posedge clk_ref) reset_meta <= {reset_meta[0], cpu_reset_n};
    reg [WAIT_WIDTH-1:0] wait_count = 0;
    reg [HOLD_WIDTH-1:0] hold_count = 0;
    always @(posedge clk_ref) begin
        if (command_valid) begin
            delay_mode <= command_mode;
            command_epoch <= command_epoch + 1'b1;
            holding <= 1;
            hold_count <= 0;
        end else begin
            if (holding) begin
                // Do not lose a reset request while AHB is stopped: wait until
                // the existing two-flop synchronizer has actually asserted reset.
                if (reset_meta[1]) hold_count <= 0;
                else if (hold_count == HOLD_WIDTH'(HOLD_CYCLES-1)) begin
                    holding <= 0; hold_count <= 0;
                end else hold_count <= hold_count + 1'b1;
            end
        end
    end
    // Mode0 is diagnostic, but never bypasses the documented LOCK interval.
    // A command first asserts holding, clears stale qualification, and requires
    // a fresh full interval after holding ends. Mode1 retains the real50ms wait.
    always @(posedge clk_ref) begin
        if (!ready_meta[1] || holding || command_valid) begin
            wait_count <= 0;
            delay_done <= 0;
        end else if (!delay_done) begin
            if (wait_count == WAIT_WIDTH'((delay_mode ? WAIT_CYCLES : MIN_LOCK_CYCLES)-1))
                delay_done <= 1;
            else wait_count <= wait_count + 1'b1;
        end
    end
    // The Neo top also uses this permission as asynchronous assertion input
    // of its existing two-flop CPU reset chain, flushing any stale pipeline bit.
    assign release_request = available && ready_meta[1] && !holding && delay_done;
endmodule
`default_nettype wire

// uart_rx.v — récepteur 8N1, cycles par bit programmable, échantillonnage au milieu du bit.
// Un stop bit à 0 rejette l'octet : rien n'est inventé.
// Le front de start est vu SYNC_LAT = 2 cycles après son arrivée (double bascule) :
// le compte jusqu'au milieu du bit en tient compte, sinon à 5 cycles/bit (20 Mbps)
// l'échantillon tombe sur la frontière du bit.
`default_nettype none
module neo_reset_trial_rx_rtl #(parameter DIV_WIDTH = 8) (
    input  wire       clk,
    input  wire       rst,
    input  wire [DIV_WIDTH-1:0] clk_div,
    input  wire       rx,
    output reg  [7:0] data,
    output reg        valid
);
    localparam [DIV_WIDTH-1:0] SYNC_LAT = 2;
    reg [1:0] rx_sync = 2'b11;
    reg [DIV_WIDTH-1:0] cnt;
    wire [DIV_WIDTH-1:0] half = {1'b0, clk_div[DIV_WIDTH-1:1]};
    wire [DIV_WIDTH-1:0] first_cnt = (half > SYNC_LAT) ? (half - SYNC_LAT) : 0;
    reg [3:0] bit_idx;
    reg [7:0] shift;
    reg       busy;
    always @(posedge clk) rx_sync <= {rx_sync[0], rx};
    wire rxs = rx_sync[1];

    always @(posedge clk) begin
        valid <= 1'b0;
        if (rst) begin
            busy <= 1'b0;
        end else if (!busy) begin
            if (!rxs) begin busy <= 1'b1; bit_idx <= 4'd0; cnt <= first_cnt; end
        end else if (cnt != 0) begin
            cnt <= cnt - 1'b1;
        end else begin
            cnt <= clk_div - 1'b1;
            case (bit_idx)
            4'd0: if (rxs) busy <= 1'b0; else bit_idx <= 4'd1;
            4'd9: begin busy <= 1'b0; if (rxs) begin data <= shift; valid <= 1'b1; end end
            default: begin shift <= {rxs, shift[7:1]}; bit_idx <= bit_idx + 4'd1; end
            endcase
        end
    end
endmodule
`default_nettype wire
