// cdc_clear.v — vidage d'une FIFO double horloge sur un ordre du domaine A (impulsion `req`) : le côté A
// est tenu en reset (`rst_a`) jusqu'à ce que le côté B ait lui aussi été reset (`rst_b`, 2 cycles) et
// l'ait acquitté. Ainsi les deux pointeurs repartent de zéro sans qu'un mot puisse être écrit d'un côté
// pendant que l'autre a encore ses anciens pointeurs. Pendant rst_a, la FIFO refuse (wr_ready = 0) : l'amont
// (raw_fifo, 16 k entrées) retient, rien n'est perdu.
`default_nettype none
module cdc_clear (
    input  wire clk_a,
    input  wire req,          // impulsion (domaine A)
    output wire rst_a,
    input  wire clk_b,
    output reg  rst_b
);
    reg       tgl_a = 1'b0, busy = 1'b0;
    reg [1:0] ack_a = 2'b00;
    reg [2:0] tgl_b = 3'b000;
    reg       ack_b = 1'b0;
    reg [1:0] cnt_b = 2'b00;

    always @(posedge clk_a) begin
        ack_a <= {ack_a[0], ack_b};
        if (req && !busy) begin tgl_a <= ~tgl_a; busy <= 1'b1; end
        else if (busy && ack_a[1] == tgl_a) busy <= 1'b0;
    end
    assign rst_a = busy || req;

    always @(posedge clk_b) begin
        tgl_b <= {tgl_b[1:0], tgl_a};
        if (tgl_b[2] != tgl_b[1]) begin rst_b <= 1'b1; cnt_b <= 2'd2; end
        else if (cnt_b != 2'd0) begin cnt_b <= cnt_b - 2'd1; if (cnt_b == 2'd1) begin rst_b <= 1'b0; ack_b <= tgl_b[1]; end end
    end
endmodule
`default_nettype wire
