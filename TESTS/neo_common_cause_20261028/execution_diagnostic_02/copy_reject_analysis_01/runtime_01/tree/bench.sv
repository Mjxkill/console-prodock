`timescale 1ns/1ps
// Extend this isolated bench; gpu_copy565.v and protected checker are read-only.
module bench;
 reg clk=0; always #5 clk=~clk;
 initial begin $display("BENCH_NOT_IMPLEMENTED"); $finish; end
endmodule
