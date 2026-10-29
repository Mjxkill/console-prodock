// uart_tx.v — émetteur 8N1, nombre de cycles par bit programmable (clk_div).
// 100 MHz : clk_div = 10 -> 10 Mbps (BL616), 50 -> 2 Mbps (test par USB).
// `ready` = libre. Changer clk_div pendant un octet le corrompt : ctrl.v
// n'applique 'U' qu'à l'octet suivant, l'hôte attend 1 ms avant de changer.
`default_nettype none
module uart_tx #(parameter DIV_WIDTH = 8) (
    input  wire       clk,
    input  wire       rst,
    input  wire [DIV_WIDTH-1:0] clk_div,
    input  wire [7:0] data,
    input  wire       valid,
    output wire       ready,
    output reg        tx
);
    reg [DIV_WIDTH-1:0] cnt;
    reg [3:0] bit_idx;
    reg [9:0] shift;
    reg       busy;
    assign ready = !busy && !rst;

    always @(posedge clk) begin
        if (rst) begin
            busy <= 1'b0; tx <= 1'b1;
        end else if (!busy) begin
            tx <= 1'b1;
            if (valid) begin
                busy <= 1'b1; shift <= {1'b1, data, 1'b0}; bit_idx <= 4'd0; cnt <= 0;
            end
        end else if (cnt != 0) begin
            cnt <= cnt - 1'b1;
        end else if (bit_idx == 4'd10) begin
            busy <= 1'b0; tx <= 1'b1;
        end else begin
            cnt     <= clk_div - 1'b1;
            tx      <= shift[0];
            shift   <= {1'b1, shift[9:1]};
            bit_idx <= bit_idx + 4'd1;
        end
    end
endmodule
`default_nettype wire
