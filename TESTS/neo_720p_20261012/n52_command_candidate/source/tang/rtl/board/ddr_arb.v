// ddr_arb.v — arbitre sur l'interface utilisateur de l'IP DDR3 Gowin entre trois maîtres (ARCHI_V3 § 9.2, § 12) :
//   m0 : le pont AHB Sipeed (cœur AE350) — lectures et écritures, une commande à la fois ;
//   m1 : `ddr_writer` (flux d'événements) — écritures seules, ready/valid respecté au cycle de cmd_en ;
//   m2 : `ddr_reader` (E2-g : relecture de l'anneau en fabric) — lectures seules, ready/valid.
// Tout est dans le domaine clk_out de l'IP (75 MHz). Reset synchrone (voir ae350_soc.v : pas de reset
// asynchrone à fort fanout).
//
// Pourquoi un tampon pour m0 : le pont Sipeed ne teste cmd_ready/wr_data_rdy qu'AVANT de s'engager
// (état SELECT_LANE_CHK de gw_ahb_ddr3.v : `lpddr_cmd_ready && lpddr_data_ready && ahb_req`), puis émet
// cmd_en (et wr_data_en au même cycle pour une écriture) sans regarder ready. L'arbitre accepte donc
// toujours la commande du pont dans un registre d'une entrée (m0_cmd_ready = m0_wr_rdy = tampon vide) et
// la relaie à l'IP quand elle est libre. Une lecture du pont attend rd_data_valid, donc tout retard est
// invisible pour lui ; une écriture est « terminée » pour le pont à ahb_end, et sa commande suivante ne
// part qu'après un nouveau SELECT_LANE_CHK, bloqué tant que le tampon est plein. Aucun délai interne du
// pont n'est supposé.
//
// Priorité : writer urgent (FIFO au-delà de la moitié) > pont (latence du cœur) > writer > lecteur (il
// n'a besoin que du débit moyen). Le writer étant tamponné 16 k événements en amont, il ne perd rien tant
// que l'IP suit ; ses pertes sont comptées par lui, jamais ici.
// Données lues : l'IP rend dans l'ordre d'émission → file d'étiquettes (0 = m0, 1 = m2) remplie à chaque
// lecture servie, dépilée à chaque rd_data_valid, qui route valid vers le bon maître. `tq_full` est
// registré (chemin critique sinon : étiquettes → ready → mux de données → IP, cf. ddr_ui_adapt).
`default_nettype none
module ddr_arb #(
    parameter TAG_LOG2 = 4              // lectures en vol au plus (pont : 1 ; lecteur : crédit ≤ 8)
) (
    input  wire         clk,
    input  wire         rst_n,          // synchrone : init_calib_complete
    // m0 : pont Sipeed (ports ui_* de gw_ahb_ddr3)
    input  wire         m0_cmd_en,
    input  wire [2:0]   m0_cmd,
    input  wire [28:0]  m0_addr,
    output wire         m0_cmd_ready,
    input  wire         m0_wr_en,
    input  wire [127:0] m0_wr_data,
    input  wire [15:0]  m0_wr_mask,
    output wire         m0_wr_rdy,
    output wire [127:0] m0_rd_data,
    output wire         m0_rd_valid,
    output wire         m0_rd_end,
    // m1 : ddr_writer (écritures seules)
    input  wire         m1_cmd_en,      // = m1_wr_en : commande et donnée au même cycle
    input  wire [28:0]  m1_addr,
    input  wire [127:0] m1_wr_data,
    input  wire [15:0]  m1_wr_mask,
    input  wire         m1_urgent,
    output wire         m1_ready,       // la commande présentée est prise ce cycle
    // m2 : ddr_reader (lectures seules)
    input  wire         m2_cmd_en,
    input  wire [28:0]  m2_addr,
    output wire         m2_ready,       // la lecture présentée est prise ce cycle
    output wire [127:0] m2_rd_data,
    output wire         m2_rd_valid,
    // IP DDR3 (DDR3_Memory_Interface_Top)
    output wire         ui_cmd_en,
    output wire [2:0]   ui_cmd,
    output wire [28:0]  ui_addr,
    input  wire         ui_cmd_ready,
    output wire         ui_wr_data_en,
    output wire         ui_wr_data_end,
    output wire [127:0] ui_wr_data,
    output wire [15:0]  ui_wr_data_mask,
    input  wire         ui_wr_data_rdy,
    input  wire [127:0] ui_rd_data,
    input  wire         ui_rd_data_valid,
    input  wire         ui_rd_data_end,
    output wire [3:0]   dbg             // {m1_urgent, m1 servi, m0 servi, tampon plein}
);
    // --- Tampon d'une commande du pont ---------------------------------------------------------
    reg          b_full;
    reg  [2:0]   b_cmd;
    reg  [28:0]  b_addr;
    reg          b_wr;                  // une donnée accompagne la commande (écriture)
    reg  [127:0] b_data;
    reg  [15:0]  b_mask;

    assign m0_cmd_ready = !b_full;
    assign m0_wr_rdy    = !b_full;

    // --- File d'étiquettes des lectures en vol ---------------------------------------------------
    localparam DEPTH = 1 << TAG_LOG2;
    reg                 tags [0:DEPTH-1];               // 0 = m0, 1 = m2
    reg  [TAG_LOG2:0]   tq_w = 0, tq_r = 0;
    reg                 tq_full = 1'b0;
    wire                tq_empty = (tq_w == tq_r);

    // --- Choix du maître servi ce cycle ----------------------------------------------------------
    // L'IP prend une commande quand cmd_ready (et wr_data_rdy pour une écriture) ; commande et donnée
    // sont toujours présentées au même cycle, donc on exige les deux ready.
    wire ip_ok    = ui_cmd_ready && ui_wr_data_rdy;
    wire m0_is_rd = (b_cmd == 3'b001);
    // Choose the payload independently of downstream ready. Using accepted
    // grants for this mux fed DDR reset/ready back through arbitration, address
    // rotation and the CPU buffer. Factoring ready out preserves every accepted
    // command and its cycle; payload while ui_cmd_en=0 is deliberately irrelevant.
    wire choose_m1 = m1_cmd_en && (!b_full || m1_urgent);
    wire choose_m0 = b_full && !(m1_cmd_en && m1_urgent) && !(m0_is_rd && tq_full);
    wire choose_m2 = m2_cmd_en && !b_full && !m1_cmd_en && !tq_full;
    wire serve_m1 = ip_ok && choose_m1;
    wire serve_m0 = ip_ok && choose_m0;
    wire serve_m2 = ip_ok && choose_m2;

    assign m1_ready       = serve_m1;
    assign m2_ready       = serve_m2;
    assign ui_cmd_en      = serve_m0 || serve_m1 || serve_m2;
    assign ui_cmd         = choose_m1 ? 3'b000 : choose_m2 ? 3'b001 : b_cmd;
    assign ui_addr        = choose_m1 ? m1_addr : choose_m2 ? m2_addr : b_addr;
    assign ui_wr_data_en  = serve_m1 || (serve_m0 && b_wr);
    assign ui_wr_data_end = ui_wr_data_en;                 // une donnée par commande (burst = 1, BL8)
    assign ui_wr_data     = choose_m1 ? m1_wr_data : b_data;
    assign ui_wr_data_mask= choose_m1 ? m1_wr_mask : b_mask;

    // --- Retour des lectures, routé par l'étiquette de tête ---------------------------------------
    wire   push = (serve_m0 && m0_is_rd) || serve_m2;
    wire   pop  = ui_rd_data_valid;
    wire   tag_r = tags[tq_r[TAG_LOG2-1:0]];
    assign m0_rd_data  = ui_rd_data;
    assign m2_rd_data  = ui_rd_data;
    assign m0_rd_valid = ui_rd_data_valid && !tag_r;
    assign m2_rd_valid = ui_rd_data_valid &&  tag_r;
    assign m0_rd_end   = ui_rd_data_end && !tag_r;
    /* verilator lint_off UNUSEDSIGNAL */
    wire tq_underflow = pop && tq_empty;                   // donnée sans lecture en vol : incohérence (banc)
    /* verilator lint_on UNUSEDSIGNAL */
    wire [TAG_LOG2:0] tq_w_n = tq_w + {{TAG_LOG2{1'b0}}, push};
    wire [TAG_LOG2:0] tq_r_n = tq_r + {{TAG_LOG2{1'b0}}, pop};
    wire [TAG_LOG2:0] tq_count = tq_w - tq_r;

    always @(posedge clk) begin
        if (!rst_n) begin
            b_full <= 1'b0; b_cmd <= 3'b0; b_addr <= 29'd0; b_wr <= 1'b0; b_data <= 128'd0; b_mask <= 16'd0;
            tq_w <= 0; tq_r <= 0; tq_full <= 1'b0;
        end else begin
            if (serve_m0) b_full <= 1'b0;
            if (m0_cmd_en && !b_full) begin              // toujours accepté (m0_cmd_ready = !b_full)
                b_full <= 1'b1; b_cmd <= m0_cmd; b_addr <= m0_addr;
                b_wr <= m0_wr_en; b_data <= m0_wr_data; b_mask <= m0_wr_mask;
            end
            if (push) tags[tq_w[TAG_LOG2-1:0]] <= serve_m2;
            tq_w <= tq_w_n; tq_r <= tq_r_n;
            // L11 : même valeur que (tq_w_n, tq_r_n) « écart = DEPTH », calculée sur les pointeurs courants ; push et
            // pop, qui arrivent tard (arbitre, IP), ne font plus que choisir entre trois comparaisons déjà prêtes.
            tq_full <= (push && !pop) ? tq_count == DEPTH - 1 : (!push && pop) ? tq_count == DEPTH + 1 : tq_count == DEPTH;
        end
    end

    assign dbg = {m1_urgent, serve_m1, serve_m0, b_full};
endmodule
`default_nettype wire
