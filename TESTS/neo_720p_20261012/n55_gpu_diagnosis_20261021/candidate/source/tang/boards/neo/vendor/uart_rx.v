// uart_rx.v — récepteur 8N1, cycles par bit programmable, échantillonnage au milieu du bit.
// Un stop bit à 0 rejette l'octet : rien n'est inventé.
// Le front de start est vu SYNC_LAT = 2 cycles après son arrivée (double bascule) :
// le compte jusqu'au milieu du bit en tient compte, sinon à 5 cycles/bit (20 Mbps)
// l'échantillon tombe sur la frontière du bit.
`default_nettype none
module uart_rx #(parameter DIV_WIDTH = 8) (
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
