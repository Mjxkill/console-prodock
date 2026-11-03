// owned/helpers.sv — test-only simulation support for the banked shadow.
//
// The qualified banked helper (banked/banked_words32.v) instantiates vendor
// DFFRE cells. The official extract in primitives/DFFRE.v uses Verilog
// procedural `assign/deassign` to implement the global-set/reset (GSR)
// initialisation. Verilator 5.020 rejects `deassign` (%Error-UNSUPPORTED),
// so the real DFFRE extract cannot be compiled here.
//
// This shim preserves the documented DFFRE contract that the design uses:
//   * INIT initial value,
//   * synchronous RESET cleared at a rising CLK, RESET takes priority,
//   * otherwise update from D at a rising CLK when CE is high.
// The removed construct is the runtime GSR deassign path. The binding
// contract is GSRI=VCC (GSR asserted only as power-on initialisation; no
// runtime GSR assertion), and the helper ties each storage FF RESET to 0.
// Therefore this shim is a simulation-only equivalent for the compiled
// workload. It is NOT a synthesis/qualification model and does not qualify
// GSR timing, CDC, or the vendor primitive.
//
// This file is compiled only instead of primitives/DFFRE.v; primitives/luts.v
// and primitives/GSR.v are used unmodified. The immutable inputs are not edited.
`timescale 1ns/1ps
`default_nettype none
module DFFRE (Q, D, CLK, CE, RESET);
    parameter INIT = 1'b0;
    input  wire D, CLK, RESET, CE;
    output reg  Q;
    initial Q = INIT;
    always @(posedge CLK) begin
        if (RESET) Q <= 1'b0;
        else if (CE) Q <= D;
    end
endmodule
`default_nettype wire
