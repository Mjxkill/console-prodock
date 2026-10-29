// ddr_ui_adapt.v — adaptateur de largeur entre l'interface utilisateur « 16 bits » (128 bits par rafale, adresses en
// mots de 16 bits, sémantique du contrôleur DDR3 Gowin en DQ 16 telle que modélisée dans sim/ddr3_ui_model.py et
// validée sur carte en E1/E2) et l'IP DDR3 configurée en DQ 32 bits (256 bits par rafale, adresses en mots de 32 bits,
// 1 Go) — ARCHI_V3 § 11 (E2-f1). Il permet de garder le pont Sipeed, ddr_arb et ddr_writer tels quels.
//
// Sémantique reproduite (côté amont, « u_* ») :
//   - adresse u_addr en mots de 16 bits ; une rafale couvre les 16 octets à (u_addr & ~7) × 2 ; si u_addr n'est pas
//     alignée, la donnée écrite et le masque sont TOURNÉS de (u_addr & 7) mots (c'est ce que faisait le contrôleur
//     16 bits : « la donnée présentée commence au mot demandé »), et une lecture rend la rafale tournée en sens
//     inverse (mot demandé en tête) ;
//   - masque : 1 = octet non écrit.
// Côté IP 32 bits (« ip_* ») : commandes toujours ALIGNÉES sur la rafale de 32 octets (ip_addr = octets / 4 avec les
// 3 bits bas à 0) ; la moitié de 128 bits visée est u_addr[3] (octet 16 de la rafale), l'autre moitié est masquée.
// Hypothèse à vérifier sur carte : rafale alignée = 8 mots de 32 bits en petit-boutiste (mot 0 en bas), comme en 16 bits.
// Lectures : l'IP rend dans l'ordre → file d'étiquettes {moitié, rotation} ; cmd_ready amont = IP prête ET file non
// pleine (jamais de commande perdue en silence). Données d'écriture : wr_data_en passe tel quel (l'IP les apparie).
`default_nettype none
module ddr_ui_adapt #(
    parameter TAG_LOG2 = 4                  // 16 lectures en vol au plus (le pont n'en a qu'une, le writer aucune)
) (
    input  wire         clk,
    input  wire         rst_n,
    // amont : interface 128 bits (sortie de ddr_arb)
    input  wire         u_cmd_en,
    input  wire [2:0]   u_cmd,
    input  wire [28:0]  u_addr,
    output wire         u_cmd_ready,
    input  wire         u_wr_data_en,
    input  wire         u_wr_data_end,
    input  wire [127:0] u_wr_data,
    input  wire [15:0]  u_wr_data_mask,
    output wire         u_wr_data_rdy,
    output wire [127:0] u_rd_data,
    output wire         u_rd_data_valid,
    output wire         u_rd_data_end,
    // aval : IP DDR3 en DQ 32 (256 bits)
    output wire         ip_cmd_en,
    output wire [2:0]   ip_cmd,
    output wire [28:0]  ip_addr,
    input  wire         ip_cmd_ready,
    output wire         ip_wr_data_en,
    output wire         ip_wr_data_end,
    output wire [255:0] ip_wr_data,
    output wire [31:0]  ip_wr_data_mask,
    input  wire         ip_wr_data_rdy,
    input  wire [255:0] ip_rd_data,
    input  wire         ip_rd_data_valid,
    input  wire         ip_rd_data_end
);
    // --- rotation d'un mot de 128 bits par n mots de 16 bits (gauche pour écrire, droite pour lire) -------------
    function [127:0] rotl128; input [127:0] d; input [2:0] n;
        begin rotl128 = (d << (16 * n)) | (d >> (128 - 16 * n)); end
    endfunction
    function [127:0] rotr128; input [127:0] d; input [2:0] n;
        begin rotr128 = (d >> (16 * n)) | (d << (128 - 16 * n)); end
    endfunction
    function [15:0] rotl16; input [15:0] m; input [2:0] n;
        begin rotl16 = (m << (2 * n)) | (m >> (16 - 2 * n)); end
    endfunction

    // --- file d'étiquettes des lectures en vol ------------------------------------------------------------------
    localparam DEPTH = 1 << TAG_LOG2;
    reg  [3:0]          tags [0:DEPTH-1];                    // {half, rot}
    // Keep the current response tag in flip-flops. In particular, the first
    // read after an empty queue must not depend on RAM read-during-write.
    reg  [3:0]          head_tag;
    reg  [TAG_LOG2:0]   tq_w = 0, tq_r = 0;
    // `tq_full` REGISTRÉ (calculé sur les pointeurs du cycle suivant) : combinatoire, il entrait dans u_cmd_ready →
    // arbitre → mux de données 256 bits → tampon d'écriture de l'IP, chemin en violation de 1 ns (E2-f1, sdc corrigé).
    // Pessimiste d'un cycle sur la libération d'une place (16 lectures en vol, le pont n'en a qu'une) : sans effet.
    reg                 tq_full = 1'b0;
    wire                tq_empty = (tq_w == tq_r);
    assign u_cmd_ready = ip_cmd_ready && !tq_full;
    wire   push = u_cmd_en && u_cmd_ready && (u_cmd == 3'b001);
    wire   have_tag = !tq_empty || push;
    wire   pop  = ip_rd_data_valid && have_tag;
    wire [TAG_LOG2:0] next_r = tq_r + 1'b1;
    wire [TAG_LOG2:0] tq_w_n = tq_w + {{TAG_LOG2{1'b0}}, push};
    wire [TAG_LOG2:0] tq_r_n = tq_r + {{TAG_LOG2{1'b0}}, pop};
    // Decode the occupancy boundary from current pointers, before accepting
    // a command. READY/push must not traverse pointer increment/comparison.
    wire [TAG_LOG2:0] next_w = tq_w + 1'b1;
    wire last_free = next_w == {~tq_r[TAG_LOG2], tq_r[TAG_LOG2-1:0]};
    always @(posedge clk) begin
        if (!rst_n) begin
            tq_w <= 0; tq_r <= 0; tq_full <= 1'b0; head_tag <= 0;
        end else begin
            if (push) tags[tq_w[TAG_LOG2-1:0]] <= {half, rot};
            if (pop && !tq_empty) begin
                if (next_r == tq_w) begin
                    if (push) head_tag <= {half, rot};
                end else head_tag <= tags[next_r[TAG_LOG2-1:0]];
            end else if (push && tq_empty) head_tag <= {half, rot};
            tq_w <= tq_w_n; tq_r <= tq_r_n;
            // A full queue cannot accept push. A response either frees one
            // slot or cancels a simultaneous push. Stray responses at empty
            // never make a queue full, including a same-cycle bypass.
            tq_full <= !ip_rd_data_valid && (tq_full || (push && last_free));
        end
    end
    /* verilator lint_off UNUSEDSIGNAL */
    wire tq_underflow = ip_rd_data_valid && !have_tag;        // response without an accepted read
    /* verilator lint_on UNUSEDSIGNAL */

    // --- commande --------------------------------------------------------------------------------------------
    // Le masque et la donnée d'écriture dépendent de l'adresse de la commande : le pont et le writer présentent
    // wr_data_en au même cycle que cmd_en (ddr_arb : ui_wr_data_end = ui_wr_data_en), on utilise donc u_addr du cycle.
    wire [2:0] rot  = u_addr[2:0];
    wire       half = u_addr[3];
    // Contrat amont (celui de ddr_arb) : u_cmd_en seulement quand u_cmd_ready ; on verrouille quand même la file
    // pleine côté IP pour qu'une lecture sans étiquette ne puisse jamais partir (désynchronisation silencieuse).
    assign ip_cmd_en = u_cmd_en && !tq_full;
    assign ip_cmd    = u_cmd;
    assign ip_addr   = {1'b0, u_addr[28:4], 3'b000};        // octets / 4, aligné sur la rafale de 32 octets
    wire [127:0] wdata_eff = rotl128(u_wr_data, rot);
    wire [15:0]  wmask_eff = rotl16(u_wr_data_mask, rot);
    assign ip_wr_data      = {wdata_eff, wdata_eff};
    assign ip_wr_data_mask = half ? {wmask_eff, 16'hFFFF} : {16'hFFFF, wmask_eff};
    assign ip_wr_data_en   = u_wr_data_en;
    assign ip_wr_data_end  = u_wr_data_end;
    assign u_wr_data_rdy   = ip_wr_data_rdy;

    // --- données lues : moitié demandée, tournée pour que le mot demandé soit en tête -----------------------------
    wire [3:0]   tag_r  = tq_empty ? {half, rot} : head_tag;
    wire [127:0] rhalf  = tag_r[3] ? ip_rd_data[255:128] : ip_rd_data[127:0];
    // Capture the selected half together with its valid flag before advancing
    // the tag queue. The upstream arbiter sees one additional cycle of latency.
    reg [127:0] reply_data;
    reg reply_valid, reply_end;
    always @(posedge clk) begin
        if (!rst_n) begin
            reply_valid <= 0; reply_end <= 0;
        end else begin
            reply_valid <= ip_rd_data_valid && have_tag;
            reply_end <= ip_rd_data_valid && ip_rd_data_end && have_tag;
            // Data is observable only with reply_valid. Dropping have_tag
            // here removes the remote READY/push cone from 128 enables;
            // unsolicited responses still never assert VALID or END.
            if (ip_rd_data_valid)
                reply_data <= rotr128(rhalf, tag_r[2:0]);
        end
    end
    assign u_rd_data       = reply_data;
    assign u_rd_data_valid = reply_valid;
    assign u_rd_data_end   = reply_end;
endmodule
`default_nettype wire
