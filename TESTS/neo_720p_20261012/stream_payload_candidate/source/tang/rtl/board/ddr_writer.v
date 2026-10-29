// ddr_writer.v — écrit le flux d'événements dans l'anneau DDR3 par le port m1 de ddr_arb (ARCHI_V3 § 9.2).
// Domaine clk_out de l'IP (75 MHz). Reset synchrone = calibration terminée.
//
// Deux sources, choisies par le paramètre PATTERN :
//   PATTERN = 1 (E2-c, test croisé) : écrit une fois la zone [BASE, BASE+SIZE[ avec le mot 64 bits n° i = i
//     (deux mots par commande de 16 octets), puis lève `done` ; le cœur relit et compare.
//   PATTERN = 0 (E2-d) : consomme la FIFO double horloge (ddr_dcfifo, mots 64 bits {time32, state16, lost16})
//     UN mot par commande : la commande de 16 octets vise l'adresse alignée et masque la moitié qui n'est pas
//     concernée (m1_wr_mask, 1 = octet non écrit, polarité validée sur carte par le pont Sipeed en E1).
//     Anneau sans fin : wptr revient à 0 en atteignant SIZE, le cœur suit avec rptr.
//     Pourquoi pas deux mots par commande (version E2-d1) : un événement isolé restait retenu sans limite de
//     temps en attendant son pair, invisible du cœur, et le tick de repos du cœur pouvait le dépasser (delta
//     négatif → flux corrompu). Ici la latence événement → wptr est bornée par construction.
// Aucune perte ici : une commande est tenue jusqu'à m1_ready ; les pertes possibles sont en amont (dcfifo,
// comptées). `urgent` = FIFO au-delà de URGENT_LEVEL : l'arbitre nous sert avant le pont.
// Unités : wptr en OCTETS (relatif à BASE ; pas de 16 en PATTERN, pas de 8 en flux) ; m1_addr en mots de
// 16 bits (adresse d'octet / 2). `cycles` compte les cycles clk_out entre le départ et `done`.
`default_nettype none
module ddr_writer #(
    parameter [31:0] BASE_BYTES   = 32'h1000_0000,   // 256 Mo
    parameter [31:0] SIZE_BYTES   = 32'h0010_0000,   // 1 Mo
    parameter        PATTERN      = 1,
    parameter [9:0]  URGENT_LEVEL = 10'd384          // 3/4 de 512
) (
    input  wire         clk,
    input  wire         rst_n,
    // PATTERN : graine XORée dans le motif (mot i = i ^ seed) et redémarrage (impulsion, domaine clk) —
    // permet au cœur de relire une zone réécrite et de mesurer la cohérence de son D-cache (E2-c)
    input  wire [63:0]  pat_seed,
    input  wire         restart,
    // anneau (PATTERN = 0) : pointeur de lecture du cœur (octets, relatif à BASE, aligné 8) ; le writer
    // s'arrête quand l'anneau est plein (la dcfifo amont retient puis compte), jamais d'écrasement
    input  wire [31:0]  rptr,
    output wire         ring_full,
    // FIFO double horloge, côté lecture (PATTERN = 0)
    input  wire         fi_valid,
    input  wire [63:0]  fi_data,
    output wire         fi_ready,
    input  wire [9:0]   fi_count,
    // ddr_arb, port m1
    output wire         m1_cmd_en,
    output wire [28:0]  m1_addr,
    output wire [127:0] m1_wr_data,
    output wire [15:0]  m1_wr_mask,
    output wire         m1_urgent,
    input  wire         m1_ready,
    // état
    output reg  [31:0]  wptr,
    output reg          done,
    output wire         active,
    output reg  [31:0]  cycles
);
    reg          run;                 // 1 : en marche (PATTERN : jusqu'à done ; flux : toujours)
    wire [63:0]  idx = {35'd0, wptr[31:3]};           // n° du mot 64 bits courant (PATTERN)
    wire [31:0]  step = (PATTERN != 0) ? 32'd16 : 32'd8;
    wire [31:0]  next_wptr = (wptr + step == SIZE_BYTES) ? 32'd0 : wptr + step;

    // Anneau plein — REGISTRÉ (E2-e, 2026-09-20) : la chaîne rptr (cdc_word) → soustraction → comparaison 32 bits →
    // cmd_valid → arbitre → données de l'IP était le chemin critique du domaine 75 MHz (marge 0,02 ns). Le drapeau
    // est calculé sur les valeurs du cycle précédent avec un seuil de 40 octets : au plus une commande (8 octets)
    // peut passer avant qu'il ne soit vu, le writer s'arrête donc entre SIZE−40 et SIZE−32, jamais au-delà.
    wire [31:0]  used = (wptr >= rptr) ? (wptr - rptr) : (SIZE_BYTES - rptr + wptr);
    reg          ring_full_r = 1'b0;
    always @(posedge clk) ring_full_r <= (PATTERN == 0) && (used >= SIZE_BYTES - 32'd40);
    assign ring_full = ring_full_r;
    // Commande présentée : PATTERN → toujours prête tant que run ; flux → un mot disponible et place dans l'anneau
    wire         cmd_valid = run && !done && (PATTERN != 0 ? 1'b1 : (fi_valid && !ring_full_r));
    assign m1_cmd_en  = cmd_valid;
    wire [31:0]  byte_addr = BASE_BYTES + wptr;
    assign m1_addr    = {byte_addr[29:4], 3'b000};      // commande alignée 16 octets, en mots de 16 bits (512 Mo max)
    // flux : le mot est présenté sur les deux moitiés, le masque ne laisse passer que celle de wptr[3]
    assign m1_wr_data = (PATTERN != 0) ? {(idx + 64'd1) ^ pat_seed, idx ^ pat_seed} : {fi_data, fi_data};
    assign m1_wr_mask = (PATTERN != 0) ? 16'h0000 : (wptr[3] ? 16'h00FF : 16'hFF00);
    assign m1_urgent  = (fi_count > URGENT_LEVEL);
    assign active     = run && !done;
    // flux : le mot est consommé au cycle où la commande est acceptée par l'arbitre
    assign fi_ready   = (PATTERN == 0) && cmd_valid && m1_ready;

    always @(posedge clk) begin
        if (!rst_n) begin
            run <= 1'b0; done <= 1'b0; wptr <= 32'd0; cycles <= 32'd0;
        end else begin
            if (!run) run <= 1'b1;                                   // démarre au cycle après le reset
            if (active) cycles <= cycles + 32'd1;
            if (restart) begin                                       // PATTERN : nouvelle passe sur la zone
                done <= 1'b0; wptr <= 32'd0; cycles <= 32'd0;
            end else if (cmd_valid && m1_ready) begin
                wptr <= next_wptr;
                if (PATTERN != 0 && next_wptr == 32'd0) done <= 1'b1;   // zone écrite une fois
            end
        end
    end
endmodule
`default_nettype wire
