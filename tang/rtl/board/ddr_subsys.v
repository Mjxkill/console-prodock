// ddr_subsys.v — sous-système DDR3 : IP DDR3 standalone Gowin (16 bits, 512 Mo) + pont AHB 64 bits Sipeed
// (`sipeed/gw_ahb_ddr3.v`, module `gw_ahb_ddr3`). Remplace `gw_ahb_ddr3_top` de Sipeed (mêmes ports) : l'IP est
// instanciée ICI pour que son interface utilisateur (cmd/addr/wr_data 128 bits, BL8) puisse être partagée en E2
// entre le pont (cœur AE350) et `ddr_writer` par `ddr_arb` (ARCHI_V3 § 9). E2-b : 1er temps = pont seul en
// câblage direct (E1 rejoué à l'identique) ; 2e temps = `ddr_arb` inséré, port writer (m1) inactif, E1 rejoué.
//
// INS_LOC/sdc (la16.cst, la16.sdc) : `.../u_ddr/u_ip/gw3_top/u_ddr_phy_top/{u_dll,fclkdiv}`.
`default_nettype none
module ddr_subsys #(
    parameter [31:0] RING_BASE = 32'h1000_0000,
    parameter [31:0] RING_SIZE = 32'h1000_0000,
    parameter        PATTERN   = 0                  // 1 : motif de test E2-c au lieu du flux
) (
    // PLL DDR3 et IP
    input  wire         DDR3_MEMORY_CLK,   // 300 MHz
    input  wire         DDR3_CLK_IN,       // 50 MHz : clk de l'IP (= DDR_CLK du SoC = HCLK)
    input  wire         DDR3_RSTN,         // 1 (486tang)
    input  wire         DDR3_LOCK,
    output wire         DDR3_STOP,         // pll_stop -> enclk2 de la PLL
    output wire         DDR3_INIT,         // init_calib_complete
    // Puce DDR3 (16 bits)
    output wire [2:0]   DDR3_BANK,
    output wire         DDR3_CS_N, DDR3_RAS_N, DDR3_CAS_N, DDR3_WE_N,
    output wire         DDR3_CK, DDR3_CK_N, DDR3_CKE, DDR3_RESET_N, DDR3_ODT,
    output wire [14:0]  DDR3_ADDR,
    output wire [3:0]   DDR3_DM,                  // E2-f1 : IP en DQ 32 bits (deux puces, 1 Go), ARCHI_V3 § 11
    inout  wire [31:0]  DDR3_DQ,
    inout  wire [3:0]   DDR3_DQS, DDR3_DQS_N,
    // AHB 64 bits (esclave, depuis le SoC)
    input  wire         HCLK, HRESETN,
    input  wire [31:0]  HADDR,
    input  wire [2:0]   HSIZE, HBURST,
    input  wire         HWRITE,
    input  wire [1:0]   HTRANS,
    input  wire [63:0]  HWDATA,
    output wire         HREADY_O,
    output wire [1:0]   HRESP,
    output wire [63:0]  HRDATA,
    output wire [15:0]  DBG,               // diag (voir gw_ahb_ddr3)
    // Graphics uses the native 256-bit interface in the ui_clk domain.
    input wire gpu_valid,
    input wire [28:0] gpu_addr,
    output wire gpu_ready,
    output wire [255:0] gpu_data,
    output wire gpu_data_valid,
    // ddr_writer (E2-c : motif ; domaine clk_out de l'IP — le wrapper resynchronise)
    output wire         wr_clk,            // clk_out, pour que le wrapper synchronise ses signaux
    output wire         wr_done,
    output wire         wr_active,
    output wire [31:0]  wr_wptr,
    output wire [31:0]  wr_cycles,
    input  wire         wr_restart,        // impulsion, domaine wr_clk
    input  wire [31:0]  wr_seed,
    // E2-d : anneau (mode flux) — rptr du cœur (déjà resynchronisé), plein, octets présents ; FIFO événements
    output wire [31:0]  wr_rptr,           // E2-g : pointeur de lecture du lecteur fabric (domaine wr_clk), publié
    output wire         wr_ring_full,
    output wire [31:0]  wr_used,
    input  wire         fi_valid,
    input  wire [63:0]  fi_data,
    output wire         fi_ready,
    input  wire [9:0]   fi_count,
    // E2-g : sortie du lecteur d'anneau vers event_enc (domaine rd_clk = clk 100 MHz), FIFO vidée au 'S'
    input  wire         rd_clk,
    input  wire         rd_rst_wr,         // 'S' : reset côté écriture de la FIFO du lecteur ET redémarrage du lecteur
                                           // (domaine wr_clk) = la MÊME impulsion que le vidage de la FIFO amont et le
                                           // redémarrage du writer (un seul cdc_clear : sinon course, entrées périmées)
    input  wire         rd_rst_rd,         // 'S' : reset côté lecture (domaine rd_clk), tenu pendant la poignée de main
    output wire         rd_valid,
    output wire [63:0]  rd_data,
    input  wire         rd_ready,
    output wire [31:0]  rd_lost            // entrées que le lecteur n'a pas pu pousser (ne doit jamais bouger)
);
    // Interface utilisateur de l'IP (noms de DDR3_Memory_Interface_Top)
    wire         ui_clk;                   // clk_out de l'IP (75 MHz = memory_clk / 4)
    wire         ui_cmd_ready, ui_cmd_en, ui_wr_data_rdy, ui_wr_data_en, ui_wr_data_end;
    wire         ui_rd_data_valid, ui_rd_data_end;
    wire [2:0]   ui_cmd;
    wire [28:0]  ui_addr;
    wire [127:0] ui_wr_data, ui_rd_data;
    wire [15:0]  ui_wr_data_mask;

    // Côté IP : sortie de l'arbitre (ip_*) ; côté pont : m0 de l'arbitre (ui_* du pont)
    wire         ip_cmd_ready, ip_cmd_en, ip_wr_data_rdy, ip_wr_data_en, ip_wr_data_end;
    wire [2:0]   ip_cmd;
    wire [28:0]  ip_addr;
    wire [127:0] ip_wr_data;
    wire [15:0]  ip_wr_data_mask;
    wire [3:0]   arb_dbg;
    /* verilator lint_off UNUSEDSIGNAL */
    wire [3:0] arb_dbg_unused = arb_dbg;
    wire end_unused = ui_wr_data_end;      // l'arbitre pose end = en lui-même
    /* verilator lint_on UNUSEDSIGNAL */

    // E2-f1 : l'IP est en DQ 32 bits (rafales de 256 bits, adresses en mots de 32 bits, 1 Go) ; ddr_ui_adapt reproduit
    // devant l'arbitre l'interface 128 bits du contrôleur 16 bits (ARCHI_V3 § 11) — pont, arbitre, writer inchangés.
    wire         w_cmd_ready, w_cmd_en, w_wr_data_rdy, w_wr_data_en, w_wr_data_end, w_rd_data_valid, w_rd_data_end;
    wire [2:0]   w_cmd;
    wire [28:0]  w_addr;
    wire [255:0] w_wr_data, w_rd_data;
    wire [31:0]  w_wr_data_mask;
    ddr_ui_adapt u_adapt (
        .clk(ui_clk), .rst_n(DDR3_INIT),
        .u_cmd_en(ip_cmd_en), .u_cmd(ip_cmd), .u_addr(ip_addr), .u_cmd_ready(ip_cmd_ready),
        .u_wr_data_en(ip_wr_data_en), .u_wr_data_end(ip_wr_data_end), .u_wr_data(ip_wr_data), .u_wr_data_mask(ip_wr_data_mask),
        .u_wr_data_rdy(ip_wr_data_rdy), .u_rd_data(ui_rd_data), .u_rd_data_valid(ui_rd_data_valid), .u_rd_data_end(ui_rd_data_end),
        .ip_cmd_en(w_cmd_en), .ip_cmd(w_cmd), .ip_addr(w_addr), .ip_cmd_ready(w_cmd_ready),
        .ip_wr_data_en(w_wr_data_en), .ip_wr_data_end(w_wr_data_end), .ip_wr_data(w_wr_data), .ip_wr_data_mask(w_wr_data_mask),
        .ip_wr_data_rdy(w_wr_data_rdy), .ip_rd_data(w_rd_data), .ip_rd_data_valid(w_rd_data_valid), .ip_rd_data_end(w_rd_data_end));

    wire m_cmd_ready, m_cmd_en, m_wr_data_rdy, m_wr_data_en, m_wr_data_end;
    wire m_rd_data_valid, m_rd_data_end;
    wire [2:0] m_cmd;
    wire [28:0] m_addr;
    wire [255:0] m_wr_data, m_rd_data;
    wire [31:0] m_wr_data_mask;
    ddr_gpu_arb u_gpu_arb (
        .clk(ui_clk), .rst_n(DDR3_INIT),
        .c_en(w_cmd_en), .c_cmd(w_cmd), .c_addr(w_addr), .c_ready(w_cmd_ready),
        .c_wr_en(w_wr_data_en), .c_wr_end(w_wr_data_end), .c_wr_data(w_wr_data), .c_wr_mask(w_wr_data_mask),
        .c_wr_ready(w_wr_data_rdy), .c_rd_data(w_rd_data), .c_rd_valid(w_rd_data_valid), .c_rd_end(w_rd_data_end),
        .g_valid(gpu_valid), .g_addr(gpu_addr), .g_ready(gpu_ready), .g_data(gpu_data), .g_data_valid(gpu_data_valid),
        .m_en(m_cmd_en), .m_cmd(m_cmd), .m_addr(m_addr), .m_ready(m_cmd_ready),
        .m_wr_en(m_wr_data_en), .m_wr_end(m_wr_data_end), .m_wr_data(m_wr_data), .m_wr_mask(m_wr_data_mask),
        .m_wr_ready(m_wr_data_rdy), .m_rd_data(m_rd_data), .m_rd_valid(m_rd_data_valid), .m_rd_end(m_rd_data_end));

    DDR3_Memory_Interface_Top u_ip (
        .clk(DDR3_CLK_IN), .pll_stop(DDR3_STOP), .memory_clk(DDR3_MEMORY_CLK), .pll_lock(DDR3_LOCK), .rst_n(DDR3_RSTN),
        .cmd_ready(m_cmd_ready), .cmd(m_cmd), .cmd_en(m_cmd_en), .addr(m_addr),
        .wr_data_rdy(m_wr_data_rdy), .wr_data(m_wr_data), .wr_data_en(m_wr_data_en), .wr_data_end(m_wr_data_end),
        .wr_data_mask(m_wr_data_mask),
        .rd_data(m_rd_data), .rd_data_valid(m_rd_data_valid), .rd_data_end(m_rd_data_end),
        .sr_req(1'b0), .ref_req(1'b0), .sr_ack(), .ref_ack(),
        .init_calib_complete(DDR3_INIT), .clk_out(ui_clk), .ddr_rst(), .burst(1'b1),
        .O_ddr_addr(DDR3_ADDR), .O_ddr_ba(DDR3_BANK), .O_ddr_cs_n(DDR3_CS_N), .O_ddr_ras_n(DDR3_RAS_N),
        .O_ddr_cas_n(DDR3_CAS_N), .O_ddr_we_n(DDR3_WE_N), .O_ddr_clk(DDR3_CK), .O_ddr_clk_n(DDR3_CK_N),
        .O_ddr_cke(DDR3_CKE), .O_ddr_odt(DDR3_ODT), .O_ddr_reset_n(DDR3_RESET_N), .O_ddr_dqm(DDR3_DM),
        .IO_ddr_dq(DDR3_DQ), .IO_ddr_dqs(DDR3_DQS), .IO_ddr_dqs_n(DDR3_DQS_N)
    );

    // ddr_writer (E2-d : mode flux, anneau [RING_BASE, +RING_SIZE[ ; le mode motif E2-c reste disponible par le
    // paramètre PATTERN) → m1 de l'arbitre. La FIFO événements est dans le wrapper (elle franchit ev_clk → clk_out).
    assign wr_clk = ui_clk;
    wire         m1_cmd_en, m1_urgent, m1_ready;
    wire [28:0]  m1_addr;
    wire [127:0] m1_wr_data;
    wire [15:0]  m1_wr_mask;
    ddr_writer #(.BASE_BYTES(RING_BASE), .SIZE_BYTES(RING_SIZE), .PATTERN(PATTERN), .URGENT_LEVEL(10'd384)) u_writer (
        .clk(ui_clk), .rst_n(DDR3_INIT), .pat_seed({wr_seed, wr_seed}), .restart(wr_restart),
        .rptr(wr_rptr), .ring_full(wr_ring_full),
        .fi_valid(fi_valid), .fi_data(fi_data), .fi_ready(fi_ready), .fi_count(fi_count),
        .m1_cmd_en(m1_cmd_en), .m1_addr(m1_addr), .m1_wr_data(m1_wr_data), .m1_wr_mask(m1_wr_mask),
        .m1_urgent(m1_urgent), .m1_ready(m1_ready),
        .wptr(wr_wptr), .done(wr_done), .active(wr_active), .cycles(wr_cycles));
    assign wr_used = (wr_wptr >= wr_rptr) ? (wr_wptr - wr_rptr) : (RING_SIZE - wr_rptr + wr_wptr);

    // E2-g : lecteur d'anneau (m2) → FIFO 64 bits clk_out → rd_clk → event_enc. Vidage au 'S' par les impulsions du
    // cdc_clear de la FIFO amont (wrapper) : writer, lecteur et les deux FIFO repartent sur la même impulsion.
    wire         m2_cmd_en, m2_ready, m2_rd_valid, fo_valid, fo_ready, rd_active;
    wire         fo_wr_rst = rd_rst_wr, fo_rd_rst = rd_rst_rd;
    wire [28:0]  m2_addr;
    wire [127:0] m2_rd_data;
    wire [63:0]  fo_data;
    wire [9:0]   fo_count, fo_rd_count;
    wire [31:0]  fo_lost;
    ddr_reader #(.SIZE_BYTES(RING_SIZE), .BASE_BYTES(RING_BASE), .FO_LOG2(9)) u_reader (
        .clk(ui_clk), .rst_n(DDR3_INIT), .restart(fo_wr_rst), .wptr(wr_wptr), .rptr(wr_rptr),
        .fo_valid(fo_valid), .fo_data(fo_data), .fo_ready(fo_ready), .fo_count(fo_count),
        .m2_cmd_en(m2_cmd_en), .m2_addr(m2_addr), .m2_ready(m2_ready), .m2_rd_data(m2_rd_data), .m2_rd_valid(m2_rd_valid),
        .active(rd_active), .lost(rd_lost));
    ddr_dcfifo #(.WIDTH(64), .DEPTH_LOG2(9)) u_rdfifo (
        .wr_clk(ui_clk), .wr_rst(fo_wr_rst), .wr_valid(fo_valid), .wr_data(fo_data), .wr_ready(fo_ready),
        .wr_lost(fo_lost), .wr_count(fo_count),
        .rd_clk(rd_clk), .rd_rst(fo_rd_rst), .rd_valid(rd_valid), .rd_data(rd_data), .rd_ready(rd_ready), .rd_count(fo_rd_count));
    /* verilator lint_off UNUSEDSIGNAL */
    wire [41:0] rd_unused = {rd_active, fo_lost, fo_rd_count};   // fo_lost = 0 par le crédit du lecteur
    /* verilator lint_on UNUSEDSIGNAL */

    // Arbitre : m0 = pont (tampon d'une commande), m1 = ddr_writer.
    // Reset synchrone = calibration terminée (comme le domaine lpddr du pont).
    wire         b_rd_valid, b_rd_end;
    wire [127:0] b_rd_data;
    ddr_arb u_arb (
        .clk(ui_clk), .rst_n(DDR3_INIT),
        .m0_cmd_en(ui_cmd_en), .m0_cmd(ui_cmd), .m0_addr(ui_addr), .m0_cmd_ready(ui_cmd_ready),
        .m0_wr_en(ui_wr_data_en), .m0_wr_data(ui_wr_data), .m0_wr_mask(ui_wr_data_mask), .m0_wr_rdy(ui_wr_data_rdy),
        .m0_rd_data(b_rd_data), .m0_rd_valid(b_rd_valid), .m0_rd_end(b_rd_end),   // E2-g : routées par étiquette (m0 / m2)
        .m1_cmd_en(m1_cmd_en), .m1_addr(m1_addr), .m1_wr_data(m1_wr_data), .m1_wr_mask(m1_wr_mask),
        .m1_urgent(m1_urgent), .m1_ready(m1_ready),
        .m2_cmd_en(m2_cmd_en), .m2_addr(m2_addr), .m2_ready(m2_ready), .m2_rd_data(m2_rd_data), .m2_rd_valid(m2_rd_valid),
        .ui_cmd_en(ip_cmd_en), .ui_cmd(ip_cmd), .ui_addr(ip_addr), .ui_cmd_ready(ip_cmd_ready),
        .ui_wr_data_en(ip_wr_data_en), .ui_wr_data_end(ip_wr_data_end), .ui_wr_data(ip_wr_data),
        .ui_wr_data_mask(ip_wr_data_mask), .ui_wr_data_rdy(ip_wr_data_rdy),
        .ui_rd_data(ui_rd_data), .ui_rd_data_valid(ui_rd_data_valid), .ui_rd_data_end(ui_rd_data_end),
        .dbg(arb_dbg));

    gw_ahb_ddr3 u_bridge (
        .rst_n(DDR3_RSTN),
        .HCLK(HCLK), .HRESETN(HRESETN), .HSEL(1'b1), .HREADY(HREADY_O),
        .HADDR(HADDR), .HSIZE(HSIZE), .HWRITE(HWRITE), .HTRANS(HTRANS), .HBURST(HBURST), .HWDATA(HWDATA),
        .HREADY_O(HREADY_O), .HRESP(HRESP), .HSPLIT(), .HRDATA(HRDATA), .DBG(DBG),
        .ddr_clk(ui_clk), .init_calib_complete(DDR3_INIT),
        .ui_cmd_ready(ui_cmd_ready), .ui_cmd(ui_cmd), .ui_cmd_en(ui_cmd_en), .ui_addr(ui_addr),
        .ui_wr_data_rdy(ui_wr_data_rdy), .ui_wr_data(ui_wr_data), .ui_wr_data_en(ui_wr_data_en),
        .ui_wr_data_end(ui_wr_data_end), .ui_wr_data_mask(ui_wr_data_mask),
        .ui_rd_data(b_rd_data), .ui_rd_data_valid(b_rd_valid), .ui_rd_data_end(b_rd_end)
    );
endmodule
`default_nettype wire
