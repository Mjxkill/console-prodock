// ddr_reader.v — relit l'anneau d'événements DDR3 en logique (E2-g, ARCHI_V3 § 12) par le port m2 de ddr_arb et
// pousse les entrées de 64 bits {time32, state16, lost16} dans une FIFO double horloge vers event_enc (domaine clk 100 MHz).
// Domaine clk_out de l'IP (75 MHz), reset synchrone = calibration terminée, redémarrage (rptr = 0) au 'S' comme le writer.
//
// Fonctionnement : tant que wptr ≠ rptr (le writer a écrit au moins une entrée) et qu'il reste du crédit aval, une
// lecture de 16 octets est émise à l'adresse rptr. Sémantique de l'interface (validée E1/E2, ddr3_ui_model.py) :
// « le mot demandé en tête » — les 64 bits bas sont l'entrée à rptr ; les 64 bits hauts sont l'entrée à rptr + 8 quand
// rptr est aligné 16 (sinon l'entrée précédente, ignorée). On consomme donc n = 2 entrées si rptr est aligné 16 et que
// deux entrées sont disponibles, sinon 1 : une entrée isolée est lue dès qu'elle est visible (latence bornée, pas
// de paire requise). Le nombre d'entrées à consommer est décidé à l'émission et mis en file (l'IP rend dans l'ordre).
// Réception : l'IP peut rendre une lecture par cycle (2 entrées) alors que la FIFO aval n'en prend qu'une par cycle →
// petite file locale (QD entrées, 2 poussées par cycle, 1 dépilée). Crédit : entrées déjà présentes (aval + locale) plus
// celles pouvant encore arriver (2 par lecture en vol) plus 2 pour la lecture à émettre ≤ places → jamais de perte ;
// `lost` compte ce qui ne devrait jamais arriver (jamais silencieux). L'anneau plein est géré par le writer, qui compare
// wptr à ce rptr (même domaine, pas de CDC).
`default_nettype none
module ddr_reader #(
    parameter [31:0] SIZE_BYTES = 32'h1000_0000,
    parameter [31:0] BASE_BYTES = 32'h1000_0000,
    parameter        FO_LOG2    = 9,                 // profondeur de la FIFO aval (512)
    parameter        INF_LOG2   = 2,                 // ≤ 4 lectures en vol
    parameter        Q_LOG2     = 3                  // file locale de 8 entrées
) (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         restart,                     // impulsion : rptr = 0 (le writer repart de 0 au même moment)
    input  wire [31:0]  wptr,                        // pointeur d'écriture du writer (octets, relatif à BASE)
    output reg  [31:0]  rptr,                        // pointeur de lecture (octets, relatif à BASE, aligné 8)
    // FIFO aval (côté écriture, même domaine)
    output wire         fo_valid,
    output wire [63:0]  fo_data,
    input  wire         fo_ready,
    input  wire [FO_LOG2:0] fo_count,
    // ddr_arb, port m2
    output wire         m2_cmd_en,
    output wire [28:0]  m2_addr,
    input  wire         m2_ready,
    input  wire [127:0] m2_rd_data,
    input  wire         m2_rd_valid,
    // état
    output wire         active,                      // au moins une lecture en vol ou une entrée locale
    output reg  [31:0]  lost                         // entrées perdues faute de place (ne doit jamais arriver)
);
    localparam FO_DEPTH = 1 << FO_LOG2;
    localparam QD       = 1 << Q_LOG2;
    localparam INF_MAX  = 1 << INF_LOG2;

    // --- file locale des entrées reçues (2 poussées / cycle, 1 dépilée) -------------------------------------------
    reg  [63:0]     q [0:QD-1];
    reg  [Q_LOG2:0] q_w = 0, q_r = 0;
    wire [Q_LOG2:0] q_count = q_w - q_r;
    wire            q_empty = (q_w == q_r);
    assign fo_valid = !q_empty;
    assign fo_data  = q[q_r[Q_LOG2-1:0]];
    wire            pop = fo_valid && fo_ready;

    // --- lectures en vol : nombre d'entrées à consommer par lecture, dans l'ordre d'émission ----------------------
    reg  [INF_LOG2:0] inflight = 0;
    reg  [1:0]        ncons [0:INF_MAX-1];
    reg  [INF_LOG2:0] nq_w = 0, nq_r = 0;
    // n_recv REGISTRÉ (timing : nq_r → RAM ncons → comparaison → écriture de la file locale, −0,6 ns) : image de la tête
    // de file au cycle courant, rafraîchie chaque cycle depuis le pointeur du cycle suivant.
    reg  [1:0]        n_recv = 2'd0;
    wire [INF_LOG2:0] nq_r_n = nq_r + {{INF_LOG2{1'b0}}, m2_rd_valid};
    always @(posedge clk) n_recv <= ncons[nq_r_n[INF_LOG2-1:0]];
    // Redémarrage ('S') avec des lectures en vol : l'IP les rendra quand même (elle rend tout, dans l'ordre) ;
    // on les compte dans `drop` et on jette leurs données au retour, sans toucher aux compteurs d'ordre.
    reg  [INF_LOG2:0] drop = 0;

    // --- émission --------------------------------------------------------------------------------------------------
    // Disponibilité REGISTRÉE (E2-g, timing) : rptr ne change qu'à une émission, les émissions sont espacées de deux
    // cycles et wptr ne fait que croître → l'image d'un cycle est toujours prudente. SIZE_BYTES est une puissance de 2 :
    // le retour à 0 se fait par masque, sans comparateur 32 bits.
    wire [31:0] avail   = (wptr >= rptr) ? (wptr - rptr) : (SIZE_BYTES - rptr + wptr);   // octets lisibles
    reg         one = 1'b0, two = 1'b0;
    always @(posedge clk) begin
        one <= (avail >= 32'd8)  && !restart;
        two <= (rptr[3] == 1'b0) && (avail >= 32'd16) && !restart;
    end
    // places engagées : aval + locale + 2 par lecture en vol ; il faut 2 de plus pour émettre
    wire [FO_LOG2+2:0] engaged = {2'b0, fo_count} + {{(FO_LOG2+2-Q_LOG2){1'b0}}, q_count}
                               + {{(FO_LOG2+1-INF_LOG2){1'b0}}, inflight, 1'b0};
    // Marge de 4 (au lieu de 2) : l'éligibilité est REGISTRÉE (chaîne disponibilité → crédit → arbitre → étiquettes
    // trop longue pour 13,3 ns, −0,76 ns au build E2-g) ; l'image peut être en retard d'une émission : la marge la couvre.
    // Débit ≤ 25 M commandes/s (une tous les trois cycles), sans objet devant le lien.
    wire        credit   = (engaged + 4) <= FO_DEPTH && (q_count + {{(Q_LOG2-INF_LOG2){1'b0}}, inflight, 1'b0} + 4) <= QD;
    // Image en deux registres (one/two puis can_issue_r) : après une émission (rptr change) l'image est périmée pendant
    // deux cycles → `hold` bloque deux cycles ; idem après un redémarrage. Une émission tous les trois cycles au plus.
    reg         can_issue_r = 1'b0;
    reg  [1:0]  hold = 2'd0;
    always @(posedge clk) begin
        can_issue_r <= one && credit && (inflight != INF_MAX[INF_LOG2:0]) && !restart && (drop == 0);
        if (issue || restart) hold <= 2'd2; else if (hold != 0) hold <= hold - 2'd1;
    end
    wire        can_issue = can_issue_r && (hold == 0) && !restart;
    assign m2_cmd_en = can_issue;
    wire [31:0] byte_addr = BASE_BYTES + rptr;
    assign m2_addr = byte_addr[29:1];                          // adresse en mots de 16 bits (rotation par l'IP/adaptateur)
    wire        issue = can_issue && m2_ready;
    wire [1:0]  n_issue = two ? 2'd2 : 2'd1;
    wire [31:0] rptr_n = rptr + {27'd0, n_issue, 3'b000};
    assign active = (inflight != 0) || !q_empty;

    wire drop_now = (drop != 0) || restart;                     // retour à jeter (lecture émise avant le redémarrage)
    always @(posedge clk) begin
        if (!rst_n) begin
            rptr <= 32'd0; inflight <= 0; nq_w <= 0; nq_r <= 0; q_w <= 0; q_r <= 0; lost <= 32'd0; drop <= 0;
        end else begin
            // émission (bloquée pendant le redémarrage : can_issue l'exclut via restart plus bas)
            if (issue) begin
                ncons[nq_w[INF_LOG2-1:0]] <= n_issue;
                nq_w <= nq_w + 1'b1;
                rptr <= rptr_n & (SIZE_BYTES - 32'd1);            // SIZE puissance de 2
            end
            inflight <= inflight + {{INF_LOG2{1'b0}}, issue} - {{INF_LOG2{1'b0}}, m2_rd_valid};
            if (restart) begin
                rptr <= 32'd0; q_w <= 0; q_r <= 0;
                drop <= inflight - {{INF_LOG2{1'b0}}, m2_rd_valid};     // ce qui reste en vol après ce cycle
            end else if (drop != 0 && m2_rd_valid) begin
                drop <= drop - 1'b1;
            end
            if (pop && !restart) q_r <= q_r + 1'b1;
            if (m2_rd_valid) begin
                nq_r <= nq_r + 1'b1;
                if (drop_now) begin
                    // donnée d'avant le redémarrage : jetée
                end else if (q_count + {{(Q_LOG2-1){1'b0}}, n_recv} <= QD) begin
                    q[q_w[Q_LOG2-1:0]] <= m2_rd_data[63:0];
                    if (n_recv == 2'd2) q[q_w[Q_LOG2-1:0] + 1'b1] <= m2_rd_data[127:64];
                    q_w <= q_w + {{(Q_LOG2-1){1'b0}}, n_recv};
                end else begin
                    lost <= lost + {30'd0, n_recv};            // impossible par le crédit : compté, pas caché
                end
            end
        end
    end
endmodule
`default_nettype wire
