// SPDX-License-Identifier: MIT
// AE350 UART2 (115200 8N1) <-> BL616 programmer relay (2 Mbit/s 8N1).
// All logic uses clk100; uart_rx synchronizes each asynchronous serial input.
// No flow control on these pins: limit host paste bursts to 2**INPUT_LOG2
// bytes (4096 by default), then wait for the CPU to drain.
`default_nettype none
module uart_console_bridge #(
    parameter INPUT_LOG2 = 12,
    parameter [15:0] CPU_DIV = 16'd868,
    parameter [15:0] DEBUG_DIV = 16'd50
) (
    input wire clk, rst,
    input wire cpu_tx, debug_rx,
    output wire cpu_rx, debug_tx,
    output wire input_overflow, output_overflow,
    output wire [63:0] diagnostic
);
    uart_console_channel #(.FIFO_LOG2(INPUT_LOG2)) u_input (
        .clk(clk), .rst(rst), .rx(debug_rx), .tx(cpu_rx),
        .rx_div(DEBUG_DIV), .tx_div(CPU_DIV), .overflow(input_overflow),
        .diagnostic(diagnostic[31:0]));
    // Only eight bytes: use explicit registers for the outgoing queue. This
    // keeps its storage/read path explicit instead of inferring LUT SRAM.
    uart_console_channel #(.FIFO_LOG2(3), .REGISTER_FIFO(1)) u_output (
        .clk(clk), .rst(rst), .rx(cpu_tx), .tx(debug_tx),
        .rx_div(CPU_DIV), .tx_div(DEBUG_DIV), .overflow(output_overflow),
        .diagnostic(diagnostic[63:32]));
endmodule

module uart_console_channel #(
    parameter FIFO_LOG2 = 12,
    parameter REGISTER_FIFO = 0
) (
    input wire clk, rst, rx,
    input wire [15:0] rx_div, tx_div,
    output wire tx,
    output reg overflow,
    output wire [31:0] diagnostic
);
    localparam DEPTH = 1 << FIFO_LOG2;
    wire [7:0] rx_data;
    wire rx_valid, tx_ready;
    reg [7:0] mem [0:DEPTH-1];
    reg [FIFO_LOG2-1:0] wr_ptr, rd_ptr;
    reg [FIFO_LOG2:0] count;
    reg [7:0] tx_data;
    reg tx_valid;
    reg [7:0] received, transmitted;
    // Counts wrap modulo 256; observe deltas. All bits are in clk's domain.
    assign diagnostic = {transmitted, received, 8'(count), 3'b0,
                         tx, overflow, tx_valid, tx_ready, rx_valid};
    wire pop = !rst && count != 0 && (!tx_valid || tx_ready);
    // At full capacity wait until the following cycle before reusing a slot:
    // never depend on same-address BSRAM read-during-write behavior.
    wire push = !rst && rx_valid && count != (FIFO_LOG2+1)'(DEPTH);

    uart_rx #(.DIV_WIDTH(16)) u_rx (.clk(clk), .rst(rst), .clk_div(rx_div),
        .rx(rx), .data(rx_data), .valid(rx_valid));
    uart_tx #(.DIV_WIDTH(16)) u_tx (.clk(clk), .rst(rst), .clk_div(tx_div),
        .data(tx_data), .valid(tx_valid), .ready(tx_ready), .tx(tx));

    // Both implementations have the same registered read latency. Storage
    // needs no reset: tx_valid and count guard its contents after reset.
    generate if (REGISTER_FIFO) begin : g_register_fifo
        wire [8*DEPTH-1:0] words;
        for (genvar slot = 0; slot < DEPTH; slot = slot + 1) begin : g_word
            (* syn_preserve = 1 *) reg [7:0] value;
            always @(posedge clk)
                if (push && wr_ptr == FIFO_LOG2'(slot)) value <= rx_data;
            assign words[8*slot +: 8] = value;
        end
        always @(posedge clk)
            if (pop) tx_data <= words[8*rd_ptr +: 8];
    end else begin : g_ram_fifo
        always @(posedge clk) begin
            if (push) mem[wr_ptr] <= rx_data;
            if (pop) tx_data <= mem[rd_ptr];
        end
    end endgenerate
    always @(posedge clk) begin
        if (rst) begin
            wr_ptr <= 0; rd_ptr <= 0; count <= 0;
            tx_valid <= 0; overflow <= 0;
            received <= 0; transmitted <= 0;
        end else begin
            if (rx_valid) received <= received + 1'b1;
            if (tx_valid && tx_ready) transmitted <= transmitted + 1'b1;
            if (push) wr_ptr <= wr_ptr + 1'b1;
            if (pop) begin rd_ptr <= rd_ptr + 1'b1; tx_valid <= 1; end
            else if (tx_ready) tx_valid <= 0;
            case ({push,pop})
                2'b10: count <= count + 1'b1;
                2'b01: count <= count - 1'b1;
                default: ;
            endcase
            if (rx_valid && !push) overflow <= 1;
        end
    end
endmodule
`default_nettype wire
