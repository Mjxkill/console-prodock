// Garde BOT, domaine USB uniquement. Les paquets CRC-valides sont contrôlés
// avant que la FIFO ne les livre au firmware. Une faute verrouille EP1
// jusqu'au reset BOT/bus ; une purge locale n'efface jamais cette faute.
// Le contrôleur Gowin n'expose pas de commande STALL utilisateur : EP1 est
// forcé à NAK puis seul ce PID de handshake est remplacé par STALL à l'UTMI.
// Le statut HALT d'EP1 est également reflété par GET_STATUS. Les données
// bulk, le port CDC et les netlists fournisseur restent transparents.
`default_nettype none
module usb_msc_guard (
    input wire clk, reset, bot_reset, abort_request, highspeed,
    input wire [3:0] endpoint,
    input wire rxact, rxval, rxpktval, setup,
    input wire [7:0] rxdata,
    input wire txpktfin,
    input wire [11:0] txlen,
    input wire [7:0] utmi_data,
    input wire utmi_valid, utmi_ready,
    output reg halted,
    output wire idle,
    output reg [7:0] phy_data
);
    localparam CBW=2'd0, DATA_OUT=2'd1, DATA_IN=2'd2, CSW=2'd3;
    reg [1:0] state;
    reg [31:0] remaining, signature, host_length;
    reg to_host;
    reg [11:0] rx_count;
    reg rx_active;
    wire ep_rx=rxact && endpoint==4'd1;
    assign idle=state==CBW && !ep_rx && !halted;

    // Les octets d'une tentative rejetée par le CRC ne changent pas l'état
    // BOT. La tentative suivante recommence son compteur et son en-tête.
    always @(posedge clk) begin
        if(reset || bot_reset) begin
            halted<=0;state<=CBW;remaining<=0;rx_count<=0;rx_active<=0;
            signature<=0;host_length<=0;to_host<=0;
        end else begin
            rx_active<=ep_rx;
            if(ep_rx && !rx_active) begin rx_count<=0;signature<=0;host_length<=0;to_host<=0;end
            if(rxval && endpoint==4'd1) begin
                if(rx_count!=12'hfff)rx_count<=rx_count+1'b1;
                if(rx_count<4)signature[8*rx_count[1:0]+:8]<=rxdata;
                if(rx_count>=8 && rx_count<12)host_length[8*rx_count[1:0]+:8]<=rxdata;
                if(rx_count==12)to_host<=rxdata[7];
            end
            if(rxpktval && endpoint==4'd1 && !halted) begin
                case(state)
                    CBW: begin
                        if(rx_count!=31 || signature!=32'h43425355)halted<=1;
                        else begin
                            remaining<=host_length;
                            state<=host_length==0 ? CSW : to_host ? DATA_IN : DATA_OUT;
                        end
                    end
                    DATA_OUT: begin
                        if(rx_count==0 || {20'd0,rx_count}>remaining ||
                           (rx_count < (highspeed ? 12'd512 : 12'd64) && {20'd0,rx_count}!=remaining))halted<=1;
                        else begin
                            remaining<=remaining-{20'd0,rx_count};
                            if(remaining=={20'd0,rx_count})state<=CSW;
                        end
                    end
                    default: halted<=1;
                endcase
            end
            // txpktfin signifie ACK hôte : une retransmission sans ACK ne
            // consomme ni les données attendues ni le CSW.
            if(txpktfin && endpoint==4'd1 && !halted) begin
                case(state)
                    DATA_IN: begin
                        if(txlen==0 || {20'd0,txlen}>remaining)halted<=1;
                        else begin
                            remaining<=remaining-{20'd0,txlen};
                            if(remaining=={20'd0,txlen})state<=CSW;
                        end
                    end
                    CSW: if(txlen==13)state<=CBW;else halted<=1;
                    default: halted<=1;
                endcase
            end
            if(abort_request)halted<=1;
        end
    end

    // GET_STATUS(endpoint 01/81) doit présenter HALT=1, y compris après
    // CLEAR_FEATURE tant qu'aucun Reset Recovery BOT n'a eu lieu.
    reg [3:0] setup_count;
    reg setup_active;
    reg [63:0] setup_bytes;
    reg status_query;
    wire setup_rx=rxact && setup && endpoint==0;
    always @(posedge clk) begin
        if(reset || bot_reset) begin setup_count<=0;setup_active<=0;setup_bytes<=0;status_query<=0;end
        else begin
            setup_active<=setup_rx;
            if(!setup)setup_count<=0;
            if(setup_rx && !setup_active)begin setup_count<=0;status_query<=0;end
            if(rxval && setup && endpoint==0)begin
                if(setup_count<8)setup_bytes[8*setup_count[2:0]+:8]<=rxdata;
                if(setup_count!=15)setup_count<=setup_count+1'b1;
            end
            if(rxpktval && endpoint==0 && setup)
                status_query<=setup_count==8 &&
                    (setup_bytes==64'h0002008100000082 || setup_bytes==64'h0002000100000082);
        end
    end
    reg in_packet, patch_status, offered, stall_packet;
    reg [2:0] tx_index;
    wire stall_pid=endpoint==1 && halted && utmi_data==8'h5a;
    always @(posedge clk) begin
        if(reset || !utmi_valid)begin offered<=0;stall_packet<=0;end
        else if(!offered)begin offered<=1;stall_packet<=stall_pid;end
    end
    always @(posedge clk) begin
        if(reset)begin in_packet<=0;patch_status<=0;tx_index<=0;end
        else if(!utmi_valid)begin in_packet<=0;patch_status<=0;tx_index<=0;end
        else if(utmi_ready)begin
            in_packet<=1;
            if(!in_packet)begin
                tx_index<=1;
                patch_status<=status_query && halted && endpoint==0 &&
                    (utmi_data==8'hc3 || utmi_data==8'h4b);
            end else if(tx_index!=7)tx_index<=tx_index+1'b1;
        end
    end
    always @* begin
        phy_data=utmi_data;
        if(!in_packet && (offered ? stall_packet : stall_pid))phy_data=8'h1e;
        // CRC16 USB de 01 00 : FF DF (polynôme A001, init FFFF, complément).
        if(in_packet && patch_status)case(tx_index)
            1:phy_data=8'h01;
            2:phy_data=8'h00;
            3:phy_data=8'hff;
            4:phy_data=8'hdf;
            default:begin end
        endcase
    end
endmodule
`default_nettype wire
