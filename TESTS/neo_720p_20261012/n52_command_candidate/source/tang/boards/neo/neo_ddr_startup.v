// Explicit DDR IP reset in its continuous reference domain. pll_stop may
// stop memory_clk during calibration, so it must never clock this sequencer.
`default_nettype none
module neo_ddr_startup #(
    parameter HOLD_BITS = 10
)(
    input wire ref_clk, resetn, cpu_clk, pll_locked, calib_complete,
    output reg ip_resetn = 1'b0,
    output wire cpu_resetn
);
    // PLL lock is independent of its gated CLKOUT2. A lock loss must also
    // restart the controller, otherwise a stale calibration flag could let
    // the CPU resume against a DDR PHY that has lost its phase alignment.
    wire start_allowed = resetn && pll_locked;
    reg [1:0] start_sync /* synthesis syn_preserve=1 */ = 2'b00;
    always @(posedge ref_clk or negedge start_allowed)
        if (!start_allowed) start_sync <= 2'b00;
        else start_sync <= {start_sync[0], 1'b1};

    // 1024 reference cycles (20.48 us at 50 MHz), after synchronizing reset
    // release. The vendor IP owns the JEDEC power-up/calibration sequence.
    reg [HOLD_BITS-1:0] hold_count = 0;
    always @(posedge ref_clk or negedge start_sync[1]) begin
        if (!start_sync[1]) begin
            hold_count <= 0;
            ip_resetn <= 1'b0;
        end else if (!ip_resetn) begin
            if (&hold_count) ip_resetn <= 1'b1;
            else hold_count <= hold_count + 1'b1;
        end
    end

    // Assert immediately on reset, loss of DDR PLL lock or calibration.
    // Release only on CPU bus edges; no dependency on the gated DDR clock.
    wire ready_async = resetn && ip_resetn && pll_locked && calib_complete;
    reg [1:0] cpu_sync /* synthesis syn_preserve=1 */ = 2'b00;
    always @(posedge cpu_clk or negedge ready_async)
        if (!ready_async) cpu_sync <= 2'b00;
        else cpu_sync <= {cpu_sync[0], 1'b1};
    assign cpu_resetn = cpu_sync[1];
endmodule
`default_nettype wire
