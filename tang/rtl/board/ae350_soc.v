// ae350_soc.v — wrapper du SoC AE350 (cœur RISC-V A25) et de sa mémoire DDR3 pour la Tang Console 138K.
//
// Architecture (identique au démonstrateur AE350 de Sipeed pour ce SoM et à LiteX) : l'IP AE350 est
// générée en « Customized Data Memory » (`AE350_EXT_D_MEM_EN`) : son bus mémoire de données (AHB 64 bits
// DDR_H*, horloge DDR_HCLK = DDR_CLK) sort dans le fabric et rejoint l'IP DDR3 standalone de Gowin
// (`ddr3_standalone/`, 16 bits pour l'instant = une des deux Hynix H5TQ4G63, 512 Mo ; 32 bits = E1-g) par le pont `sipeed/gw_ahb_ddr3.v` (Apache 2.0),
// tous deux instanciés dans `ddr_subsys.v` (E2 : arbitre sur l'interface utilisateur de l'IP).
// Pour le cœur, la DDR reste sa mémoire de données à l'adresse 0x00000000.
//
// Pourquoi pas le contrôleur DDR3 embarqué dans l'IP AE350 (E1, TESTS_V3) : il calibre, ses ports lane4/lane5
// écrivent et relisent la DDR, mais son pont AHB interne (chiffré) rend 0x00000000 au cœur quel que soit
// le contenu de la DRAM (test croisé). Sipeed et LiteX ne l'utilisent pas non plus.
//
// Resets : rst_n du contrôleur DDR3 attaché à 1 (comme 486tang) ; le cœur (POR_RSTN = HW_RSTN) sort de
// reset quand init_calib_complete est monté (2 bascules sur ahb_clk), et la PLL système verrouillée.
// Le CPU attend donc que la DDR soit
// prête. Si l'init n'aboutit pas, la console reste muette et `ddr_init` reste à 0 : signal de la porte E1.
// Le pont est reset par le même init_calib_complete resynchronisé sur son HCLK (hrst_sync), PAS par la
// sortie DDR_HRSTN du SoC : mesurée à 0 dans tous les builds avec le pont (TESTS_V3 §E1, 2026-09-20) ; et
// le net qui reset le pont doit être contraint `CLOCK_LOC ... LOCAL_CLOCK` (la16.cst) : routé sur la
// ressource globale LW par le P&R, il sort figé à 0 (mesuré bascule par bascule, cause non comprise).
//
// Horloges : CORE 800 / AHB = APB 80 / RTC 10 MHz depuis la PLL système (PLL_R[0], MUG1030 §2.6.4) ;
// DDR_CLK du SoC = HCLK du pont = 50 MHz (clkout0 de la PLL DDR3, comme le démonstrateur Sipeed) : à
// 100 MHz (> lpddr_clk 75 MHz) les lectures enchaînées du cœur bloquaient le pont (TESTS_V3 §E1) ;
// PLL DDR3 (PLL_L[0]) : 50 MHz (clk de l'IP DDR3) et 300 MHz (memory_clk, validé par pll_stop → enclk2 ;
// 400 MHz ne calibre pas de façon fiable sur cette carte).
//
// Sous Verilator (banc cocotb V2) : netlists non simulables, le wrapper est un bouchon.
`default_nettype none
module ae350_soc #(
    parameter RAM_PROBE = 0          // 1 (diag E1) : RAM AHB 4 Ko (ahb64_ram_probe.v) à la place de la DDR3, trafic sur ahb_dbg
                                     // 2 (diag E1) : idem, mais IP DDR3 + pont instanciés avec un bus AHB inactif
                                     //   (teste l'effet de la seule présence de l'IP sur DDR_HRSTN, TESTS_V3 §E1)
) (
    input  wire        clk50,
    input  wire        rst_key_n,     // reset actif bas, inclut le verrouillage de la PLL système
    input  wire        core_clk,
    input  wire        ahb_clk,
    input  wire        apb_clk,
    input  wire        rtc_clk,
    // DDR3 32 bits (2 puces, un rang) : A0-A14 ; A15 forcé à 0 (présent sur la puce, non adressé)
    output wire [2:0]  ddr_bank,
    output wire        ddr_cs, ddr_ras, ddr_cas, ddr_we, ddr_ck, ddr_ck_n, ddr_cke, ddr_reset_n, ddr_odt,
    output wire [15:0] ddr_addr,
    output wire [3:0]  ddr_dm,
    inout  wire [31:0] ddr_dq,
    inout  wire [3:0]  ddr_dqs, ddr_dqs_n,
    // JTAG du cœur (PMOD1, ESP-Prog) ; TRST non câblé, tiré à 1 ici
    input  wire        tck, tms, tdi,
    output wire        tdo,
    // Console : UART2 (printf du BSP Gowin)
    output wire        uart2_tx,
    input  wire        uart2_rx,
    // Native DDR3 graphics reads (gpu_clk = DDR UI clock).
    output wire gpu_clk,
    input wire gpu_valid,
    input wire [28:0] gpu_addr,
    output wire gpu_ready,
    output wire [255:0] gpu_data,
    output wire gpu_data_valid,
    input wire blit_valid, blit_write,
    input wire [28:0] blit_addr,
    input wire [255:0] blit_wr_data,
    input wire [31:0] blit_wr_mask,
    output wire blit_ready,
    output wire [255:0] blit_rd_data,
    output wire blit_rd_valid,
    // État
    output wire        ddr_init,      // 1 : calibration DDR3 terminée
    output wire [3:0]  dbg,           // diag E1 : {1'b1, ddr3_stop, ddr3_lock, ae350_rstn}
    output wire [7:0]  ahb_dbg,       // diag E1 (RAM_PROBE) : trafic du bus mémoire de données du cœur
    output wire [15:0] ddr_dbg,       // diag E1 : interface IP DDR3 / AHB vue du pont Sipeed (gw_ahb_ddr3 DBG)
    output wire        core_wfi_dbg,  // DIAG : CORE0_WFI_MODE du cœur (preuve de vie sans bus)
    // --- Mode V3 (E2-d, ARCHI_V3 § 9.1), domaine ev_clk = clk 100 MHz de l'acquisition ---
    input  wire        ev_clk,
    input  wire        ev_valid,      // événement brut {time32, state16, lost16} à écrire dans l'anneau DDR
    input  wire [63:0] ev_data,
    output wire        ev_ready,
    output wire        evin_valid,    // mot 32 bits encodé par le cœur, vers le framer
    output wire [31:0] evin_data,
    input  wire        evin_ready,
    output wire        rr_valid,      // E2-g : entrées de l'anneau relues en fabric, vers event_enc (domaine ev_clk)
    output wire [63:0] rr_data,
    input  wire        rr_ready,
    input  wire        acq_v3,        // mode V3 actif (appliqué au start)
    input  wire        acq_start,     // impulsion 'S' : vide les FIFO, remet wptr à 0, incrémente SEQ
    input  wire        acq_run,
    // --- Carte vidéo (V5, étape 3c) : second esclave sur l'interface EXTS du SoC, fenêtre 0xE9000000 (haddr[24] = 1) ; l'esclave vit
    //     dans la_top (g_fb, avec la SDRAM), ici seulement le décodage et le multiplexage des réponses ---
    output wire        vid_hclk,
    output wire        vid_hrstn,
    output wire        vid_hsel,
    output wire        vid_hwrite,
    output wire [31:0] vid_haddr,
    output wire [31:0] vid_hwdata,
    output wire [1:0]  vid_htrans,
    input  wire [31:0] vid_hrdata,
    input  wire        vid_hready,
    input  wire [7:0]  acq_div,
    input  wire [15:0] acq_mask,
    input  wire [31:0] acq_now
);
`ifdef VERILATOR
    /* verilator lint_off UNUSEDSIGNAL */
    wire unused = &{1'b0, clk50, rst_key_n, core_clk, ahb_clk, apb_clk, rtc_clk, tck, tms, tdi, uart2_rx, v3_unused};
    /* verilator lint_on UNUSEDSIGNAL */
    assign ddr_bank = 3'b0; assign ddr_cs = 1'b1; assign ddr_ras = 1'b1; assign ddr_cas = 1'b1;
    assign ddr_we = 1'b1; assign ddr_ck = 1'b0; assign ddr_ck_n = 1'b1; assign ddr_cke = 1'b0;
    assign ddr_reset_n = 1'b0; assign ddr_odt = 1'b0; assign ddr_addr = 16'b0; assign ddr_dm = 4'b0;
    assign ddr_dq = 32'bz; assign ddr_dqs = 4'bz; assign ddr_dqs_n = 4'bz;
    assign tdo = 1'b0; assign uart2_tx = 1'b1; assign ddr_init = 1'b0; assign dbg = 4'b0; assign ahb_dbg = 8'b0; assign ddr_dbg = 16'b0;
    assign core_wfi_dbg = 1'b0;
    assign gpu_clk = 0; assign gpu_ready = 0; assign gpu_data = 0; assign gpu_data_valid = 0;
    assign blit_ready = 0; assign blit_rd_data = 0; assign blit_rd_valid = 0;
    // mode V3 : au banc, la_top expose ev_*/evin_* directement (ports sim_*) ; ici rien ne passe
    assign ev_ready = 1'b0; assign evin_valid = 1'b0; assign evin_data = 32'd0; assign rr_valid = 1'b0; assign rr_data = 64'd0;
    assign vid_hclk = 1'b0; assign vid_hrstn = 1'b0; assign vid_hsel = 1'b0; assign vid_hwrite = 1'b0; assign vid_haddr = 32'd0; assign vid_hwdata = 32'd0; assign vid_htrans = 2'b00;
    wire v3_unused = &{1'b0, ev_clk, ev_valid, ev_data, evin_ready, rr_ready, acq_v3, acq_start, acq_run, acq_div, acq_mask, acq_now, vid_hrdata, vid_hready};
`else
    // --- PLL DDR3 ---------------------------------------------------------------------------
    // P0-a (V4, réappliqué le 2026-09-25) : l'horloge 50 MHz de l'IP DDR3 / DDR_CLK du SoC / HCLK du pont est la BROCHE clk50, comme
    // dans l'exemple Gowin-Sipeed ddr_test (`.clk(clk)` = broche, `memory_clk` = PLL) : un arbre d'horloge global de moins (build V4
    // complet : 10 horloges globales demandées, clk50_d et ddr3_clk_in tombaient sur LW). Validé sur UART le 22/09 (TESTS_V3).
    wire ddr3_memory_clk, ddr3_lock, ddr3_stop, clk0_unused, clk1_unused;
    wire ddr3_clk_in = clk50;
    Gowin_PLL_DDR3 u_pll_ddr3 (
        .lock    (ddr3_lock),
        .clkout0 (clk0_unused),        // 50 MHz : plus utilisé (P0-a)
        .clkout1 (clk1_unused),        // non utilisé
        .clkout2 (ddr3_memory_clk),    // 300 MHz
        .clkin   (clk50),
        .init_clk(clk50),
        .reset   (1'b0),
        .enclk0  (1'b1),
        .enclk1  (1'b0),
        .enclk2  (ddr3_stop)
    );

    // --- Resets -----------------------------------------------------------------------------
    wire ddr3_init_completed;
    wire ddr3_init_ip;                // état de calibration réel de l'IP (diag : ddr3_init_completed peut être forcé)
    reg  [1:0] init_sync = 2'b00;
    always @(posedge ahb_clk or negedge rst_key_n)
        if (!rst_key_n) init_sync <= 2'b00;
        else init_sync <= {init_sync[0], ddr3_init_completed};
    wire ae350_rstn = init_sync[1];
    assign ddr_init = ddr3_init_completed;
    assign dbg = {1'b1, ddr3_stop, ddr3_lock, ae350_rstn};
    assign ddr_addr[15] = 1'b0;

    // --- Bus mémoire de données du SoC (AHB 64 bits) -> pont Sipeed -> IP DDR3 -----------------
    wire [63:0] ddr_hrdata, ddr_hwdata;
    wire [31:0] ddr_haddr;
    wire [2:0]  ddr_hburst, ddr_hsize;
    wire [3:0]  ddr_hprot;
    wire [1:0]  ddr_htrans;
    wire        ddr_hready, ddr_hresp, ddr_hwrite, ddr_hclk, ddr_hrstn;
    wire [1:0]  ddr_hresp2;
    assign ddr_hresp = ddr_hresp2[0];
    // ddr_writer : état/commandes, domaine clk_out de l'IP ; resynchronisation dans la section registres
    localparam [31:0] RING_BASE = 32'h2000_0000;   // E2-f1-d : anneau = moitié haute du Go (512 Mo = 67 M entrées)
    localparam [31:0] RING_SIZE = 32'h2000_0000;   // la moitié basse reste au cœur (test mémoire E1, données)
    wire        wr_clk, wr_done, wr_active, wr_restart_tgl, wr_restart, wr_ring_full;
    assign gpu_clk = wr_clk;
    wire [31:0] wr_wptr, wr_cycles, wr_seed, wr_rptr, wr_used;
    // FIFO événements (ev_clk → clk_out) et pointeurs de l'anneau
    wire        fi_valid, fi_ready, ev_wr_rst, ev_rd_rst, start_wr;
    wire [31:0] rd_lost;                                    // E2-g : entrées non poussées par le lecteur (doit rester 0)
    wire [63:0] fi_data;
    wire [9:0]  fi_count, ev_wr_count;
    wire [31:0] ev_lost;
    // Reset du pont : calibration DDR3 resynchronisée sur son HCLK (voir en-tête ; DDR_HRSTN et DDR_HCLK
    // du SoC ne sont pas utilisés — DDR_HCLK n'est qu'une copie de DDR_CLK dans la netlist).
    reg  [1:0] hrst_sync = 2'b00;
    always @(posedge ddr3_clk_in) hrst_sync <= {hrst_sync[0], ddr3_init_completed};
    /* verilator lint_off UNUSEDSIGNAL */
    wire hresp_unused = ddr_hresp2[1];
    wire [3:0] hprot_unused = ddr_hprot;
    wire hclk_unused = ddr_hclk, hrstn_unused = ddr_hrstn;
    /* verilator lint_on UNUSEDSIGNAL */
    generate if (RAM_PROBE == 0) begin : g_ddr
    ddr_subsys #(.RING_BASE(RING_BASE), .RING_SIZE(RING_SIZE), .PATTERN(0)) u_ddr (
        .DDR3_MEMORY_CLK(ddr3_memory_clk), .DDR3_CLK_IN(ddr3_clk_in), .DDR3_RSTN(1'b1),
        .DDR3_LOCK(ddr3_lock), .DDR3_STOP(ddr3_stop), .DDR3_INIT(ddr3_init_completed),
        .DDR3_BANK(ddr_bank), .DDR3_CS_N(ddr_cs), .DDR3_RAS_N(ddr_ras), .DDR3_CAS_N(ddr_cas), .DDR3_WE_N(ddr_we),
        .DDR3_CK(ddr_ck), .DDR3_CK_N(ddr_ck_n), .DDR3_CKE(ddr_cke), .DDR3_RESET_N(ddr_reset_n), .DDR3_ODT(ddr_odt),
        .DDR3_ADDR(ddr_addr[14:0]), .DDR3_DM(ddr_dm), .DDR3_DQ(ddr_dq), .DDR3_DQS(ddr_dqs), .DDR3_DQS_N(ddr_dqs_n),
        .HCLK(ddr3_clk_in), .HRESETN(hrst_sync[1]), .HADDR(ddr_haddr), .HSIZE(ddr_hsize), .HWRITE(ddr_hwrite),
        .HTRANS(ddr_htrans), .HBURST(ddr_hburst), .HWDATA(ddr_hwdata),
        .HREADY_O(ddr_hready), .HRESP(ddr_hresp2), .HRDATA(ddr_hrdata), .DBG(ddr_dbg),
        .wr_clk(wr_clk), .wr_done(wr_done), .wr_active(wr_active), .wr_wptr(wr_wptr), .wr_cycles(wr_cycles),
        .wr_restart(wr_restart || start_wr), .wr_seed(wr_seed),
        .wr_rptr(wr_rptr), .wr_ring_full(wr_ring_full), .wr_used(wr_used),
        .rd_clk(ev_clk), .rd_rst_wr(ev_rd_rst), .rd_rst_rd(ev_wr_rst), .rd_valid(rr_valid), .rd_data(rr_data), .rd_ready(rr_ready),
        .rd_lost(rd_lost),
        .fi_valid(fi_valid), .fi_data(fi_data), .fi_ready(fi_ready), .fi_count(fi_count),
        .gpu_valid(gpu_valid), .gpu_addr(gpu_addr), .gpu_ready(gpu_ready),
        .gpu_data(gpu_data), .gpu_data_valid(gpu_data_valid),
        .blit_valid(blit_valid), .blit_write(blit_write), .blit_addr(blit_addr),
        .blit_wr_data(blit_wr_data), .blit_wr_mask(blit_wr_mask), .blit_ready(blit_ready),
        .blit_rd_data(blit_rd_data), .blit_rd_valid(blit_rd_valid)
    );
    // FIFO événements : écrite par l'acquisition (ev_clk), lue par le writer (clk_out) ; vidée au 'S'
    ddr_dcfifo #(.WIDTH(64), .DEPTH_LOG2(9)) u_evfifo (
        .wr_clk(ev_clk), .wr_rst(ev_wr_rst), .wr_valid(ev_valid), .wr_data(ev_data), .wr_ready(ev_ready),
        .wr_lost(ev_lost), .wr_count(ev_wr_count),
        .rd_clk(wr_clk), .rd_rst(ev_rd_rst), .rd_valid(fi_valid), .rd_data(fi_data), .rd_ready(fi_ready), .rd_count(fi_count));
    cdc_clear u_evclr (.clk_a(ev_clk), .req(acq_start), .rst_a(ev_wr_rst), .clk_b(wr_clk), .rst_b(ev_rd_rst));
    assign start_wr = ev_rd_rst;                       // writer ET lecteur repartent de 0 sur le vidage de la FIFO amont
    assign ahb_dbg = 8'b0;
    assign ddr3_init_ip = ddr3_init_completed;
    end else begin : g_ram
    assign gpu_ready = 0; assign gpu_data = 0; assign gpu_data_valid = 0;
    assign blit_ready = 0; assign blit_rd_data = 0; assign blit_rd_valid = 0;
    // Diag E1 : RAM AHB en fabric à la place de la DDR3 ; le SoC est « initialisé » d'office.
    assign ddr3_init_completed = 1'b1;
    assign ddr_hresp2[1] = 1'b0;
    if (RAM_PROBE == 2) begin : g_idle
    // IP DDR3 + pont présents et calibrés, bus AHB inactif : seule différence avec RAM_PROBE=1 = présence de l'IP.
    ddr_subsys u_ddr (
        .DDR3_MEMORY_CLK(ddr3_memory_clk), .DDR3_CLK_IN(ddr3_clk_in), .DDR3_RSTN(1'b1),
        .DDR3_LOCK(ddr3_lock), .DDR3_STOP(ddr3_stop), .DDR3_INIT(ddr3_init_ip),
        .DDR3_BANK(ddr_bank), .DDR3_CS_N(ddr_cs), .DDR3_RAS_N(ddr_ras), .DDR3_CAS_N(ddr_cas), .DDR3_WE_N(ddr_we),
        .DDR3_CK(ddr_ck), .DDR3_CK_N(ddr_ck_n), .DDR3_CKE(ddr_cke), .DDR3_RESET_N(ddr_reset_n), .DDR3_ODT(ddr_odt),
        .DDR3_ADDR(ddr_addr[14:0]), .DDR3_DM(ddr_dm), .DDR3_DQ(ddr_dq), .DDR3_DQS(ddr_dqs), .DDR3_DQS_N(ddr_dqs_n),
        .HCLK(ddr3_clk_in), .HRESETN(hrst_sync[1]), .HADDR(32'd0), .HSIZE(3'd0), .HWRITE(1'b0),
        .HTRANS(2'b00), .HBURST(3'd0), .HWDATA(64'd0),
        .HREADY_O(), .HRESP(), .HRDATA(), .DBG(ddr_dbg),
        .wr_clk(wr_clk), .wr_done(wr_done), .wr_active(wr_active), .wr_wptr(wr_wptr), .wr_cycles(wr_cycles),
        .wr_restart(wr_restart), .wr_seed(wr_seed),
        .wr_rptr(wr_rptr), .wr_ring_full(wr_ring_full), .wr_used(wr_used),
        .rd_clk(ev_clk), .rd_rst_wr(ev_rd_rst), .rd_rst_rd(ev_wr_rst), .rd_valid(rr_valid), .rd_data(rr_data), .rd_ready(rr_ready),
        .rd_lost(rd_lost),
        .fi_valid(1'b0), .fi_data(64'd0), .fi_ready(fi_ready), .fi_count(10'd0),
        .gpu_valid(1'b0), .gpu_addr(29'd0), .gpu_ready(), .gpu_data(), .gpu_data_valid(),
        .blit_valid(1'b0), .blit_write(1'b0), .blit_addr(29'd0), .blit_wr_data(256'd0),
        .blit_wr_mask(32'hffffffff), .blit_ready(), .blit_rd_data(), .blit_rd_valid()
    );
    assign ev_ready = 1'b0; assign fi_valid = 1'b0; assign fi_data = 64'd0; assign fi_count = 10'd0;
    assign ev_wr_rst = 1'b0; assign ev_rd_rst = 1'b0; assign start_wr = 1'b0; assign ev_lost = 32'd0; assign ev_wr_count = 10'd0;
    end else begin : g_off
    // DDR3 laissée au repos.
    assign ddr_dbg = 16'b0; assign ddr3_init_ip = 1'b1; assign ddr3_stop = 1'b1;
    assign wr_clk = ddr3_clk_in; assign wr_done = 1'b0; assign wr_active = 1'b0; assign wr_wptr = 32'd0; assign wr_cycles = 32'd0;
    assign wr_ring_full = 1'b0; assign wr_used = 32'd0; assign fi_ready = 1'b0; assign ev_ready = 1'b0; assign fi_valid = 1'b0;
    assign fi_data = 64'd0; assign fi_count = 10'd0; assign ev_wr_rst = 1'b0; assign ev_rd_rst = 1'b0; assign start_wr = 1'b0;
    assign ev_lost = 32'd0; assign ev_wr_count = 10'd0; assign rr_valid = 1'b0; assign rr_data = 64'd0; assign rd_lost = 32'd0; assign wr_rptr = 32'd0;
    assign ddr_bank = 3'b0; assign ddr_cs = 1'b1; assign ddr_ras = 1'b1; assign ddr_cas = 1'b1; assign ddr_we = 1'b1;
    assign ddr_ck = 1'b0; assign ddr_ck_n = 1'b1; assign ddr_cke = 1'b0; assign ddr_reset_n = 1'b0; assign ddr_odt = 1'b0;
    assign ddr_addr[14:0] = 15'b0; assign ddr_dm = 4'b0; assign ddr_dq = 32'bz; assign ddr_dqs = 4'bz; assign ddr_dqs_n = 4'bz;
    end
    ahb64_ram_probe u_ram (
        .hclk(ddr3_clk_in), .hresetn(hrst_sync[1]), .haddr(ddr_haddr), .hsize(ddr_hsize), .hwrite(ddr_hwrite),
        .htrans(ddr_htrans), .hwdata(ddr_hwdata), .hrdata(ddr_hrdata), .hready(ddr_hready), .hresp(ddr_hresp2[0]),
        .dbg(ahb_dbg));
    /* verilator lint_off UNUSEDSIGNAL */
    wire [2:0] hburst_unused = ddr_hburst; wire mclk_unused = ddr3_memory_clk; wire lock_unused2 = ddr3_lock; wire cin_unused = ddr3_clk_in;
    /* verilator lint_on UNUSEDSIGNAL */
    end endgenerate

    // --- SoC --------------------------------------------------------------------------------
    // --- Registres V3 (E2-a) : esclave AHB étendu du SoC (0xE8000000, horloge EXTS_HCLK = AHB_CLK) -------
    // Netlist regénérée avec `AE350_EXT_AHB_SLAVE_EN` et `AE350_EXT_INT_EN` (cfg/riscv_ae350_config.v).
    wire [31:0] exts_haddr, exts_hwdata, exts_hrdata;
    wire [2:0]  exts_hsize, exts_hburst;
    wire [3:0]  exts_hprot;
    wire [1:0]  exts_htrans;
    wire        exts_hsel, exts_hwrite, exts_hclk, exts_hrstn, exts_hready, exts_hresp;
    /* verilator lint_off UNUSEDSIGNAL */
    wire [5:0] exts_unused = {exts_hburst, exts_hprot};
    /* verilator lint_on UNUSEDSIGNAL */
    // ddr_writer (domaine clk_out 75 MHz) ↔ registres (EXTS_HCLK 80 MHz) : bits d'état par 2 bascules ;
    // wptr/cycles lus tels quels (le firmware ne les lit que quand done est vu, valeurs alors stables) ;
    // redémarrage : bascule côté registres → 2 bascules + détection de front côté writer.
    reg  [1:0]  done_s = 2'b00, active_s = 2'b00;
    always @(posedge exts_hclk) begin done_s <= {done_s[0], wr_done}; active_s <= {active_s[0], wr_active}; end
    reg  [2:0]  restart_s = 3'b000;
    always @(posedge wr_clk) restart_s <= {restart_s[1:0], wr_restart_tgl};
    assign      wr_restart = restart_s[2] ^ restart_s[1];
    // Transferts de mots entre domaines (cdc_word : valeur toujours cohérente, image en retard de quelques cycles)
    wire [31:0] r_wptr, r_used, r_seq, r_now, r_evlost, rd_ptr;
    cdc_word u_cdc_wptr (.src_clk(wr_clk),   .src_data(wr_wptr),  .dst_clk(exts_hclk), .dst_data(r_wptr));
    cdc_word u_cdc_used (.src_clk(wr_clk),   .src_data(wr_used),  .dst_clk(exts_hclk), .dst_data(r_used));
    cdc_word u_cdc_rptr (.src_clk(wr_clk),   .src_data(wr_rptr),  .dst_clk(exts_hclk), .dst_data(rd_ptr));   // E2-g : rptr du lecteur fabric → registre RO
    cdc_word u_cdc_now  (.src_clk(ev_clk),   .src_data(acq_now),  .dst_clk(exts_hclk), .dst_data(r_now));
    cdc_word u_cdc_lost (.src_clk(ev_clk),   .src_data(ev_lost),  .dst_clk(exts_hclk), .dst_data(r_evlost));
    reg  [31:0] seq_cnt = 32'd0;                       // nombre de 'S' (domaine ev_clk)
    always @(posedge ev_clk) if (acq_start) seq_cnt <= seq_cnt + 32'd1;
    cdc_word u_cdc_seq  (.src_clk(ev_clk),   .src_data(seq_cnt),  .dst_clk(exts_hclk), .dst_data(r_seq));
    reg  [2:0] v3_s = 3'b000, run_s = 3'b000, full_s = 3'b000;
    reg  [7:0] div_s1 = 8'd0, div_s2 = 8'd0; reg [15:0] mask_s1 = 16'd0, mask_s2 = 16'd0;
    always @(posedge exts_hclk) begin
        v3_s <= {v3_s[1:0], acq_v3}; run_s <= {run_s[1:0], acq_run}; full_s <= {full_s[1:0], wr_ring_full};
        div_s1 <= acq_div; div_s2 <= div_s1; mask_s1 <= acq_mask; mask_s2 <= mask_s1;   // quasi statiques
    end
    // FIFO ev_in : écrite par les registres (EXTS_HCLK), lue par le framer (ev_clk) ; vidée au 'S'
    wire        evin_wr_valid, evin_wr_ready, evin_wr_rst, evin_rd_rst;
    wire [31:0] evin_wr_data, evin_lost;
    wire [9:0]  evin_wr_count, evin_rd_count;
    ddr_dcfifo #(.WIDTH(32), .DEPTH_LOG2(9)) u_evinfifo (
        .wr_clk(exts_hclk), .wr_rst(evin_wr_rst), .wr_valid(evin_wr_valid), .wr_data(evin_wr_data), .wr_ready(evin_wr_ready),
        .wr_lost(evin_lost), .wr_count(evin_wr_count),
        .rd_clk(ev_clk), .rd_rst(evin_rd_rst), .rd_valid(evin_valid), .rd_data(evin_data), .rd_ready(evin_ready), .rd_count(evin_rd_count));
    // vidage : req dans le domaine ev_clk (start), reset côté écriture (EXTS_HCLK) via cdc_clear « à l'envers »
    cdc_clear u_evinclr (.clk_a(ev_clk), .req(acq_start), .rst_a(evin_rd_rst), .clk_b(exts_hclk), .rst_b(evin_wr_rst));
    /* verilator lint_off UNUSEDSIGNAL */
    wire [19:0] evin_cnt_unused = {evin_rd_count, ev_wr_count}; wire evin_wr_ready_unused = evin_wr_ready;
    /* verilator lint_on UNUSEDSIGNAL */
    // Décodage EXTS : haddr[24] = 0 → ext_regs (0xE8000000), 1 → carte vidéo (0xE9000000, dans la_top). L'esclave de la phase de
    // données est celui de la phase d'adresse acceptée (hready = 1) ; réponses multiplexées vers le SoC.
    // Pont registré (ahb_exts_bridge.v) : le SoC ne voit que des bascules sur EXTS_HREADYIN / EXTS_HRDATA (l'entrée HREADYIN du bloc dur
    // consomme ≈ 9 ns de budget : un mux devant elle faisait −5 / −8 ns aux builds V5_p12-p14). ext_regs = esclave 0, vidéo = esclave 1.
    wire [31:0] regs_hrdata; wire regs_hready, regs_hresp; wire [1:0] br_hsel, br_htrans; wire br_hwrite; wire [31:0] br_haddr, br_hwdata;
    ahb_exts_bridge u_bridge (.hclk(exts_hclk), .hresetn(exts_hrstn), .m_hsel(exts_hsel), .m_haddr(exts_haddr), .m_htrans(exts_htrans), .m_hwrite(exts_hwrite), .m_hwdata(exts_hwdata),
                              .m_hrdata(exts_hrdata), .m_hready(exts_hready),
                              .s_hsel(br_hsel), .s_htrans(br_htrans), .s_hwrite(br_hwrite), .s_haddr(br_haddr), .s_hwdata(br_hwdata),
                              .s0_hrdata(regs_hrdata), .s0_hready(regs_hready), .s1_hrdata(vid_hrdata), .s1_hready(vid_hready));
    assign exts_hresp = 1'b0;
    /* verilator lint_off UNUSEDSIGNAL */ wire regs_hresp_unused = regs_hresp; /* verilator lint_on UNUSEDSIGNAL */
    // reset vidéo = copie registrée d'exts_hrstn : un net sous CLOCK_LOC ne doit pas sortir par un port (la synthèse le renomme d'après
    // le port et la contrainte ne le trouve plus : CT1135 au build V5_p12)
    reg vid_hrstn_r = 1'b0; always @(posedge exts_hclk) vid_hrstn_r <= exts_hrstn;
    assign vid_hclk = exts_hclk; assign vid_hrstn = vid_hrstn_r;
    assign vid_hsel = br_hsel[1]; assign vid_htrans = br_htrans; assign vid_hwrite = br_hwrite; assign vid_haddr = br_haddr; assign vid_hwdata = br_hwdata;
    ext_regs u_ext_regs (
        .hclk(exts_hclk), .hresetn(exts_hrstn), .hsel(br_hsel[0]), .haddr(br_haddr), .htrans(br_htrans),
        .hwrite(br_hwrite), .hsize(exts_hsize), .hwdata(br_hwdata),
        .hrdata(regs_hrdata), .hreadyout(regs_hready), .hresp(regs_hresp),
        .wr_done(done_s[1]), .wr_active(active_s[1]), .wr_wptr(r_wptr), .wr_cycles(wr_cycles), .wr_lost(r_evlost),
        .wr_restart_tgl(wr_restart_tgl), .wr_seed(wr_seed),
        .mode_v3(v3_s[2]), .ring_base(RING_BASE), .ring_size(RING_SIZE), .rd_ptr(rd_ptr),
        .ring_full(full_s[2]), .ring_used(r_used),
        .evin_valid(evin_wr_valid), .evin_data(evin_wr_data), .evin_space((10'd512 - evin_wr_count) >= 10'd64), .evin_lost(evin_lost),
        .acq_run(run_s[2]), .acq_div(div_s2), .acq_mask(mask_s2), .seq(r_seq), .now(r_now));

    // --- SoC (suite) : pas d'interruption externe pour l'instant, GPIO/UART2 modem en l'air. ---------------
    /* verilator lint_off PINCONNECTEMPTY */
    wire        core0_wfi;                 // DIAG : le cœur exécute une instruction WFI (preuve de vie pure, sans bus)
    RiscV_AE350_SOC_Top u_ae350 (
        .DDR_HRDATA(ddr_hrdata), .DDR_HREADY(ddr_hready), .DDR_HRESP(ddr_hresp),
        .DDR_HADDR(ddr_haddr), .DDR_HBURST(ddr_hburst), .DDR_HPROT(ddr_hprot), .DDR_HSIZE(ddr_hsize),
        .DDR_HTRANS(ddr_htrans), .DDR_HWDATA(ddr_hwdata), .DDR_HWRITE(ddr_hwrite),
        .DDR_HCLK(ddr_hclk), .DDR_HRSTN(ddr_hrstn),
        .TCK_IN(tck), .TMS_IN(tms), .TRST_IN(1'b1), .TDI_IN(tdi), .TDO_OUT(tdo), .TDO_OE(),
        .EXT_INT(16'd0),
        .EXTS_HRDATA(exts_hrdata), .EXTS_HREADYIN(exts_hready), .EXTS_HRESP(exts_hresp),
        .EXTS_HADDR(exts_haddr), .EXTS_HBURST(exts_hburst), .EXTS_HPROT(exts_hprot), .EXTS_HSEL(exts_hsel),
        .EXTS_HSIZE(exts_hsize), .EXTS_HTRANS(exts_htrans), .EXTS_HWDATA(exts_hwdata), .EXTS_HWRITE(exts_hwrite),
        .EXTS_HCLK(exts_hclk), .EXTS_HRSTN(exts_hrstn),
        .UART2_TXD(uart2_tx), .UART2_RTSN(), .UART2_RXD(uart2_rx), .UART2_CTSN(1'b0), .UART2_DCDN(1'b0),
        .UART2_DSRN(1'b0), .UART2_RIN(1'b1), .UART2_DTRN(), .UART2_OUT1N(), .UART2_OUT2N(),
        .GPIO(), .CORE0_WFI_MODE(core0_wfi), .RTC_WAKEUP(),
        .CORE_CLK(core_clk), .DDR_CLK(ddr3_clk_in), .AHB_CLK(ahb_clk), .APB_CLK(apb_clk), .RTC_CLK(rtc_clk),
        .POR_RSTN(ae350_rstn), .HW_RSTN(ae350_rstn)
    );
    assign core_wfi_dbg = core0_wfi;
    /* verilator lint_on PINCONNECTEMPTY */
`endif
endmodule
`default_nettype wire
