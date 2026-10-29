// usb_msc_empty.v — lecteur de cartes vide : réponses Bulk-Only/SCSI données
// par le matériel quand aucun firmware ne sert le disque USB (voir
// usb_msc_port.v). Un seul domaine d'horloge (60 MHz du contrôleur USB).
//
// Pour chaque commande de 31 octets (signature « USBC ») :
//   - INQUIRY standard : 36 octets d'identité (les mêmes que ceux du firmware) ;
//   - REQUEST SENSE : 18 octets, NOT READY / MEDIUM NOT PRESENT (02/3A/00) ;
//   - toute autre commande échoue (état 1) ;
//   - la phase de données annoncée par l'hôte est toujours respectée : la
//     longueur demandée est émise (complétée par des zéros) ou lue et jetée ;
//   - l'état de 13 octets part dans un paquet à part, données acquittées.
// Les octets émis ne sont validés qu'aux multiples de 512 et en fin de phase.
`default_nettype none
module usb_msc_empty (
    input  wire       clk,
    input  wire       reset,          // synchrone : aussi quand le firmware sert le disque
    output wire       rx_rdy,
    input  wire       rx_dval,
    input  wire [7:0] rx_data,
    input  wire       tx_room,        // place pour un octet de plus
    input  wire       tx_idle,        // tout ce qui a été validé est acquitté
    output reg        tx_dval,
    output reg  [7:0] tx_data,
    output reg        tx_commit,      // valide tout, octet de ce cycle compris
    output wire       idle            // entre deux commandes depuis SETTLE cycles, émission terminée
);
    localparam S_COMMAND = 3'd0, S_IN = 3'd1, S_OUT = 3'd2, S_WAIT = 3'd3, S_STATUS = 3'd4, S_END = 3'd5;
    reg  [2:0]  state;
    reg  [4:0]  index;
    reg  [31:0] tag, length, count;
    reg         to_host, evpd;
    reg  [7:0]  opcode;
    reg  [6:0]  settle;
    // Durée de repos exigée avant de céder le disque au firmware (cycles). La valeur exacte est
    // sans importance fonctionnelle entre 100 et 127.
    localparam [6:0] SETTLE = 7'd127;
    wire        inquiry = opcode == 8'h12 && !evpd;
    wire        sense   = opcode == 8'h03;
    wire [5:0]  reply_length = inquiry ? 6'd36 : sense ? 6'd18 : 6'd0;
    wire [31:0] valid   = length < {26'd0, reply_length} ? length : {26'd0, reply_length};
    wire [31:0] residue = to_host ? length - valid : length;
    assign rx_rdy = !reset && (state == S_COMMAND || state == S_OUT);
    assign idle = state == S_COMMAND && index == 0 && settle == SETTLE && tx_idle && !rx_dval;

    function [7:0] signature_byte(input [1:0] i);
        case (i) 2'd0: signature_byte = 8'h55; 2'd1: signature_byte = 8'h53; 2'd2: signature_byte = 8'h42; default: signature_byte = 8'h43; endcase
    endfunction
    function [7:0] inquiry_byte(input [5:0] i);
        reg [8*28-1:0] text;
        begin
            text = "ElectrosConsole SD      1.00";
            case (i)
                6'd1: inquiry_byte = 8'h80;         // support amovible
                6'd2: inquiry_byte = 8'h04;
                6'd3: inquiry_byte = 8'h02;
                6'd4: inquiry_byte = 8'd31;
                default: inquiry_byte = (i >= 6'd8 && i < 6'd36) ? text[(6'd35 - i) * 8 +: 8] : 8'h00;
            endcase
        end
    endfunction
    function [7:0] sense_byte(input [4:0] i);
        case (i) 5'd0: sense_byte = 8'h70; 5'd2: sense_byte = 8'h02; 5'd7: sense_byte = 8'h0a; 5'd12: sense_byte = 8'h3a; default: sense_byte = 8'h00; endcase
    endfunction
    function [7:0] status_byte(input [3:0] i);
        case (i)
            4'd0: status_byte = 8'h55; 4'd1: status_byte = 8'h53; 4'd2: status_byte = 8'h42; 4'd3: status_byte = 8'h53;
            4'd4: status_byte = tag[7:0]; 4'd5: status_byte = tag[15:8]; 4'd6: status_byte = tag[23:16]; 4'd7: status_byte = tag[31:24];
            4'd8: status_byte = residue[7:0]; 4'd9: status_byte = residue[15:8]; 4'd10: status_byte = residue[23:16]; 4'd11: status_byte = residue[31:24];
            default: status_byte = (inquiry || sense) ? 8'h00 : 8'h01;
        endcase
    endfunction

    always @(posedge clk) begin
        tx_dval <= 1'b0; tx_commit <= 1'b0;
        if (reset) begin
            state <= S_COMMAND; index <= 5'd0; settle <= 7'd0; count <= 32'd0;
            tag <= 32'd0; length <= 32'd0; to_host <= 1'b0; evpd <= 1'b0; opcode <= 8'd0; tx_data <= 8'd0;
        end else case (state)
            S_COMMAND: begin
                if (index != 0 || rx_dval) settle <= 7'd0;
                else if (settle != SETTLE) settle <= settle + 1'b1;
                if (rx_dval) begin
                    index <= index + 1'b1;
                    if (index < 5'd4 && rx_data != signature_byte(index[1:0])) index <= rx_data == 8'h55 ? 5'd1 : 5'd0;
                    case (index)
                        5'd4: tag[7:0] <= rx_data;    5'd5: tag[15:8] <= rx_data;
                        5'd6: tag[23:16] <= rx_data;  5'd7: tag[31:24] <= rx_data;
                        5'd8: length[7:0] <= rx_data; 5'd9: length[15:8] <= rx_data;
                        5'd10: length[23:16] <= rx_data; 5'd11: length[31:24] <= rx_data;
                        5'd12: to_host <= rx_data[7];
                        5'd15: opcode <= rx_data;
                        5'd16: evpd <= rx_data[0];
                        default: ;
                    endcase
                    if (index == 5'd30) begin
                        index <= 5'd0; count <= 32'd0;
                        state <= length == 0 ? S_STATUS : to_host ? S_IN : S_OUT;
                    end
                end
            end
            S_IN: if (tx_room && !tx_dval) begin
                // Un octet tous les deux cycles : tx_room tient compte de l'octet précédent.
                tx_dval <= 1'b1;
                tx_data <= (inquiry && count < 32'd36) ? inquiry_byte(count[5:0]) :
                           (sense && count < 32'd18) ? sense_byte(count[4:0]) : 8'h00;
                count <= count + 1'b1;
                if (count[8:0] == 9'd511 || count + 1'b1 == length) tx_commit <= 1'b1;
                if (count + 1'b1 == length) state <= S_WAIT;
            end
            S_OUT: if (rx_dval) begin
                count <= count + 1'b1;
                if (count + 1'b1 == length) state <= S_STATUS;
            end
            S_WAIT: if (tx_idle && !tx_dval && !tx_commit) state <= S_STATUS;
            S_STATUS: if (tx_room && !tx_dval) begin
                tx_dval <= 1'b1; tx_data <= status_byte(index[3:0]);
                index <= index + 1'b1;
                if (index == 5'd12) begin tx_commit <= 1'b1; index <= 5'd0; state <= S_END; end
            end
            S_END: if (tx_idle && !tx_dval && !tx_commit) begin state <= S_COMMAND; settle <= 7'd0; end
            default: state <= S_COMMAND;
        endcase
    end
endmodule
`default_nettype wire
