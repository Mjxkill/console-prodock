// ext_regs.v — registres V3 vus par l'AE350 : esclave AHB-lite 32 bits sur l'interface « Extended AHB Slave »
// du SoC (0xE8000000–0xEFFFFFFF, MUG1029 §3 table 3-1 ; horloge EXTS_HCLK = AHB_CLK).
//
// Carte des registres (offsets depuis 0xE8000000, 32 bits) :
//   0x00 ID        RO  0x4C413136 « LA16 »
//   0x04 VERSION   RO  0x0003xxyy : V3, étape xx, révision yy
//   0x08 STATUS    RO  bit0 wr_done, bit1 wr_active (ddr_writer, resynchronisés dans ce domaine)
//   0x0C WR_WPTR   RO  octets écrits dans l'anneau par ddr_writer (valide quand wr_done ; E2-d : handshake)
//   0x10 WR_CYCLES RO  cycles clk_out (75 MHz) de la dernière passe du writer (valide quand wr_done)
//   0x14 WR_LOST   RO  mots refusés par la FIFO double horloge (E2-d ; 0 en E2-c)
//   0x18 CTRL      WO  bit0 = 1 : redémarre la passe du writer (motif) — impulsion, lecture : 0
//   0x1C SEED      RW  graine XORée dans le motif du writer (E2-c : mesure de la cohérence du D-cache)
//   0x20 MODE      RO  bit0 : mode V3 actif (commande 'V' du PC, appliquée au 'S')
//   0x24 RING_BASE RO  adresse d'octet du début de l'anneau (paramètre du wrapper)
//   0x28 RING_SIZE RO  taille de l'anneau en octets
//   0x2C RD_PTR    RO  pointeur de lecture de l'anneau (ddr_reader en fabric, E2-g) ; écriture ignorée
//   0x30 EV_IN     WO  un mot 32 bits {state16, delta16} vers le framer (FIFO 512 mots) ; STATUS bit2 = place ≥ 64
//   0x34 EVIN_LOST RO  mots refusés par la FIFO ev_in (pleine) — jamais silencieux
//   0x38 ACQ       RO  {8'b0, div[7:0], mask[15:0]} de ctrl ; bit 31 = run
//   0x3C SEQ       RO  compteur de 'S' (départs) : un changement = nouvelle capture, le cœur repart de rptr = 0
//   0x40 NOW       RO  temps courant du sampler (32 bits, périodes d'échantillonnage) pour les ticks de repos
//   0x44 RING_USED RO  octets présents dans l'anneau vus du writer (wptr − rptr modulo size)
// STATUS (0x08) : bit0 wr_done (motif), bit1 wr_active, bit2 ev_in : place ≥ 64 mots, bit3 anneau plein.
// Réponse en un cycle (hreadyout toujours à 1), jamais d'erreur (hresp = 0).
//
// Reset synchrone depuis EXTS_HRSTN : pas de reset asynchrone à fort fanout (voir ae350_soc.v, en-tête :
// un net de reset routé sur la ressource LW sortait figé à 0).
`default_nettype none
module ext_regs (
    input  wire        hclk,
    input  wire        hresetn,
    input  wire        hsel,
    input  wire [31:0] haddr,
    input  wire [1:0]  htrans,
    input  wire        hwrite,
    input  wire [2:0]  hsize,
    input  wire [31:0] hwdata,
    output reg  [31:0] hrdata,
    output wire        hreadyout,
    output wire        hresp,
    // état du writer (déjà dans ce domaine d'horloge, synchronisé par le wrapper)
    input  wire        wr_done,
    input  wire        wr_active,
    input  wire [31:0] wr_wptr,
    input  wire [31:0] wr_cycles,
    input  wire [31:0] wr_lost,
    // commandes vers le writer
    output reg         wr_restart_tgl,  // bascule à chaque écriture de CTRL.bit0 (resynchronisée côté writer)
    output reg  [31:0] wr_seed,
    // E2-d : anneau et flux (tous déjà dans ce domaine d'horloge sauf mention)
    input  wire        mode_v3,
    input  wire [31:0] ring_base,
    input  wire [31:0] ring_size,
    input  wire [31:0] rd_ptr,        // E2-g : publié par ddr_reader (cdc_word), lecture seule
    input  wire        ring_full,
    input  wire [31:0] ring_used,
    output reg         evin_valid,      // impulsion : evin_data à écrire dans la FIFO ev_in
    output reg  [31:0] evin_data,
    input  wire        evin_space,      // place ≥ 64 mots
    input  wire [31:0] evin_lost,
    input  wire        acq_run,
    input  wire [7:0]  acq_div,
    input  wire [15:0] acq_mask,
    input  wire [31:0] seq,
    input  wire [31:0] now
);
    localparam [31:0] REG_ID      = 32'h4C41_3136;   // "LA16"
    localparam [31:0] REG_VERSION = 32'h0003_0401;   // V3, étape E2, pas d, révision 1

    // Lecture en DEUX cycles de données (2026-09-20) : l'adresse arrive du SoC chiffré avec ≈6 ns de routage ; décoder
    // le mux de 18 registres dans le même cycle ne tient pas 12,5 ns (−0,38 ns). Phase d'adresse : on mémorise l'index ;
    // 1er cycle de données : hreadyout = 0, le mux est registré ; 2e cycle : hreadyout = 1, hrdata valide. Le maître
    // AHB-lite tient sa phase suivante tant que hreadyout = 0 : on n'échantillonne une nouvelle phase d'adresse que
    // quand hreadyout = 1. Les écritures restent en un cycle.
    reg       rd_pend;                                // 1er cycle de données d'une lecture (état d'attente)
    reg [5:0] rd_idx;
    assign hreadyout = !rd_pend;
    assign hresp     = 1'b0;

    /* verilator lint_off UNUSEDSIGNAL */
    wire [2:0] unused = hsize;                        // accès 32 bits seulement
    /* verilator lint_on UNUSEDSIGNAL */

    // Phase d'adresse -> phase de données (AHB-lite, hreadyout = 1) : l'adresse et le sens sont mémorisés
    // au cycle de sélection ; la donnée lue est présentée le cycle suivant, la donnée écrite (hwdata) est
    // prise le cycle suivant aussi. Décodage sur les 8 bits bas (registres de 4 octets).
    reg       wr_pend;
    reg [5:0] wr_idx;
    always @(posedge hclk) begin
        if (!hresetn) begin
            hrdata <= 32'd0; wr_pend <= 1'b0; wr_idx <= 6'd0; wr_restart_tgl <= 1'b0; wr_seed <= 32'd0;
            evin_valid <= 1'b0; evin_data <= 32'd0; rd_pend <= 1'b0; rd_idx <= 6'd0;
        end else begin
            evin_valid <= 1'b0;
            // phase de données d'une écriture
            if (wr_pend) begin
                case (wr_idx)
                    6'd6:  if (hwdata[0]) wr_restart_tgl <= ~wr_restart_tgl;  // CTRL
                    6'd7:  wr_seed <= hwdata;                                  // SEED
                    6'd12: begin evin_data <= hwdata; evin_valid <= 1'b1; end  // EV_IN
                    default: ;
                endcase
            end
            wr_pend <= hsel && htrans[1] && hwrite && !rd_pend;
            wr_idx  <= haddr[7:2];
            // phase de données d'une lecture : 1er cycle (rd_pend) = mux registré, 2e cycle = hrdata présenté
            rd_pend <= hsel && htrans[1] && !hwrite && !rd_pend;
            rd_idx  <= haddr[7:2];
            if (rd_pend) begin
                case (rd_idx)
                    6'd0:    hrdata <= REG_ID;
                    6'd1:    hrdata <= REG_VERSION;
                    6'd2:    hrdata <= {28'd0, ring_full, evin_space, wr_active, wr_done};
                    6'd3:    hrdata <= wr_wptr;
                    6'd4:    hrdata <= wr_cycles;
                    6'd5:    hrdata <= wr_lost;
                    6'd7:    hrdata <= wr_seed;
                    6'd8:    hrdata <= {31'd0, mode_v3};
                    6'd9:    hrdata <= ring_base;
                    6'd10:   hrdata <= ring_size;
                    6'd11:   hrdata <= rd_ptr;
                    6'd13:   hrdata <= evin_lost;
                    6'd14:   hrdata <= {acq_run, 7'd0, acq_div, acq_mask};
                    6'd15:   hrdata <= seq;
                    6'd16:   hrdata <= now;
                    6'd17:   hrdata <= ring_used;
                    default: hrdata <= 32'd0;
                endcase
            end else begin
                hrdata <= 32'd0;                      // hors transfert : 0 (hrdata reste valide pendant le 2e cycle)
            end
        end
    end
endmodule
`default_nettype wire
