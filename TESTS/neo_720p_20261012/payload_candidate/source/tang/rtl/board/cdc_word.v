// cdc_word.v — transfert d'un mot de WIDTH bits d'un domaine d'horloge à un autre par poignée de main
// (req/ack à bascule, 2 synchroniseurs) : la valeur est figée côté source pendant le transfert, donc
// toujours cohérente côté destination (aucun bit arraché). Rafraîchi en continu (un transfert dure ~6 cycles
// du domaine le plus lent) : la destination voit une image en retard de quelques cycles, jamais fausse.
// Sert pour wptr (writer → registres), rptr (registres → writer), now et seq (acquisition → registres).
`default_nettype none
module cdc_word #(parameter WIDTH = 32) (
    input  wire             src_clk,
    input  wire [WIDTH-1:0] src_data,
    input  wire             dst_clk,
    output reg  [WIDTH-1:0] dst_data
);
    reg              req = 1'b0;                 // domaine source, bascule à chaque transfert
    reg  [WIDTH-1:0] hold = {WIDTH{1'b0}};       // valeur figée pendant le transfert
    reg  [1:0]       ack_s = 2'b00;              // ack synchronisé dans le domaine source
    reg  [2:0]       req_s = 3'b000;             // req synchronisé dans le domaine destination
    reg              ack = 1'b0;                 // domaine destination

    always @(posedge src_clk) begin
        ack_s <= {ack_s[0], ack};
        if (ack_s[1] == req) begin               // transfert précédent acquitté : en lancer un autre
            hold <= src_data;
            req  <= ~req;
        end
    end

    always @(posedge dst_clk) begin
        req_s <= {req_s[1:0], req};
        if (req_s[2] != req_s[1]) begin          // nouveau transfert vu : hold est stable depuis ≥ 2 cycles source
            dst_data <= hold;
            ack      <= req_s[1];
        end
    end
endmodule
`default_nettype wire
