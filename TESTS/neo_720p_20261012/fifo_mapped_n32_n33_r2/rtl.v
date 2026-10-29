// ddr_dcfifo.v — FIFO double horloge (pointeurs Gray) entre le domaine d'acquisition (clk 100 MHz, sortie de
// raw_fifo / event_enc) et le domaine de l'IP DDR3 (clk_out 75 MHz, ddr_writer) — ARCHI_V3 § 9.2.
//
// Écrite à la main plutôt que générée par l'IP FIFO Gowin : une netlist chiffrée ne se simule pas, celle-ci
// passe au banc cocotb (rapports 100/75 et 100/50, vide/plein, 10 000 mots aléatoires, pertes comptées).
// Aucune perte silencieuse : un mot présenté quand la FIFO est pleine est refusé (wr_ready = 0) ET compté
// dans `wr_lost` (domaine écriture) — l'appelant décide quoi en faire (ddr_writer publie le compteur).
// Profondeur 2^DEPTH_LOG2 mots de WIDTH bits, mémoire inférée en BSRAM (lecture synchrone, 1 cycle).
`default_nettype none
module ddr_dcfifo #(
    parameter WIDTH      = 64,
    parameter DEPTH_LOG2 = 9          // 512 mots
) (
    // écriture
    input  wire             wr_clk,
    input  wire             wr_rst,       // synchrone au domaine écriture
    input  wire             wr_valid,
    input  wire [WIDTH-1:0] wr_data,
    output wire             wr_ready,     // = pas pleine
    output wire             wr_full,      // registered fullness, independent of reset
    output reg  [31:0]      wr_lost,      // mots refusés (pleine), jamais remis à zéro sauf reset
    output wire [DEPTH_LOG2:0] wr_count,  // remplissage vu du côté écriture (pessimiste)
    // lecture
    input  wire             rd_clk,
    input  wire             rd_rst,       // synchrone au domaine lecture
    output wire             rd_valid,     // = pas vide ; rd_data valide
    output wire [WIDTH-1:0] rd_data,
    input  wire             rd_ready,     // consomme le mot présenté
    output wire [DEPTH_LOG2:0] rd_count   // remplissage vu du côté lecture (pessimiste)
);
    localparam AW = DEPTH_LOG2;

    reg [WIDTH-1:0] mem [0:(1<<AW)-1];

    // --- pointeurs binaires et Gray (AW+1 bits : le bit de poids fort distingue plein de vide) ---
    reg  [AW:0] wr_bin, wr_gray, rd_bin, rd_gray;
    reg  [AW:0] wr_gray_s1, wr_gray_s2;      // wr_gray synchronisé dans rd_clk
    reg  [AW:0] rd_gray_s1, rd_gray_s2;      // rd_gray synchronisé dans wr_clk

    function [AW:0] bin2gray; input [AW:0] b; begin bin2gray = b ^ (b >> 1); end endfunction
    function [AW:0] gray2bin; input [AW:0] g; integer i; reg [AW:0] b;
        begin b = 0; for (i = AW; i >= 0; i = i - 1) b[i] = (i == AW) ? g[i] : b[i+1] ^ g[i]; gray2bin = b; end
    endfunction

    // --- côté écriture ----------------------------------------------------------------------
    // `full` et `wr_count` sont REGISTRÉS (E2-e, 2026-09-20) : calculés à partir du pointeur d'écriture du
    // cycle suivant et du pointeur de lecture synchronisé courant. Sans cela, la chaîne Gray → gray2bin →
    // comparaison → wr_ready → rd_ready de raw_fifo (clk100) et → m1_urgent → arbitre → IP (75 MHz) ne fermait
    // plus le timing (−0,32 ns sur clk100, −0,27 ns sur ddr3_sys_clk, build e2e_con2). Pessimisme d'un cycle
    // sur la libération d'une place : sans effet sur les comptes (le lecteur libère bien avant le plein).
    wire [AW:0] rd_bin_w = gray2bin(rd_gray_s2);
    reg         full;
    reg  [AW:0] wr_count_r;
    wire        accept   = wr_valid && !full;
    wire [AW:0] wr_bin_n = wr_bin + {{AW{1'b0}}, accept};
    // Refus pendant le vidage (E2-h, 2026-09-20) : avec wr_ready = !full seul, une écriture arrivant pendant wr_rst était
    // acceptée puis effacée par la remise à zéro du pointeur — la première entrée de chaque capture V3 (état initial,
    // t = 0) disparaissait ; l'amont (out_slice / raw_fifo) retient tant que wr_ready = 0, rien n'est perdu.
    assign wr_ready = !full && !wr_rst;
    assign wr_full = full;
    assign wr_count = wr_count_r;

    always @(posedge wr_clk) begin
        if (wr_rst) begin
            wr_bin <= 0; wr_gray <= 0; wr_lost <= 0; rd_gray_s1 <= 0; rd_gray_s2 <= 0; full <= 1'b0; wr_count_r <= 0;
        end else begin
            rd_gray_s1 <= rd_gray; rd_gray_s2 <= rd_gray_s1;
            full       <= (wr_bin_n[AW] != rd_bin_w[AW]) && (wr_bin_n[AW-1:0] == rd_bin_w[AW-1:0]);
            wr_count_r <= wr_bin_n - rd_bin_w;
            if (accept) begin
                mem[wr_bin[AW-1:0]] <= wr_data;
                wr_bin  <= wr_bin + 1'b1;
                wr_gray <= bin2gray(wr_bin + 1'b1);
            end else if (wr_valid && full) begin
                wr_lost <= wr_lost + 1'b1;
            end
        end
    end

    // --- côté lecture : mot de tête présenté en sortie (registre de tête rechargé à chaque pop) ----
    // Pointeur d'écriture REGISTRÉ après le décodage Gray (build USB 24, 2026-09-21) : la chaîne gray2bin (XOR en série)
    // + comparaison + validation du pop tenait en un cycle par chance de placement (design fusionné : −0,09 ns / 17 chemins
    // clk100 sur le port m2). Une image en retard d'un cycle est prudente (empty un cycle de plus, jamais un faux non-vide).
    wire [AW:0] wr_bin_w = gray2bin(wr_gray_s2);
    reg  [AW:0] wr_bin_r;
    wire        empty    = (rd_bin == wr_bin_r);
    reg  [WIDTH-1:0] head;
    reg              head_valid;
    reg  [AW:0]      rd_count_r;               // registré (même raison que wr_count) : alimente m1_urgent
    assign rd_valid = head_valid;
    assign rd_data  = head;
    assign rd_count = rd_count_r;

    // La mémoire est lue de façon synchrone : quand la tête est libre (ou consommée ce cycle) et que la
    // FIFO n'est pas vide, on charge mem[rd_bin] dans head au front suivant et on avance rd_bin.
    wire pop = !empty && (!head_valid || rd_ready);
    always @(posedge rd_clk) begin
        if (rd_rst) begin
            rd_bin <= 0; rd_gray <= 0; wr_gray_s1 <= 0; wr_gray_s2 <= 0; wr_bin_r <= 0; head_valid <= 1'b0; head <= 0; rd_count_r <= 0;
        end else begin
            wr_gray_s1 <= wr_gray; wr_gray_s2 <= wr_gray_s1; wr_bin_r <= wr_bin_w;
            rd_count_r <= wr_bin_r - rd_bin;
            if (pop) begin
                head       <= mem[rd_bin[AW-1:0]];
                head_valid <= 1'b1;
                rd_bin     <= rd_bin + 1'b1;
                rd_gray    <= bin2gray(rd_bin + 1'b1);
            end else if (rd_ready && head_valid) begin
                head_valid <= 1'b0;
            end
        end
    end
endmodule
`default_nettype wire
