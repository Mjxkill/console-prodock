// console_top.v — E1 : mire LCD 800×480 + soft USB CDC + moteur de test DDR3 Sipeed.
//
// Domaines (ARCHI_V1 § 4) :
//   - LCD  : Gowin_PLL_LCD (50 MHz pin → 35 MHz pixel, panneau CJ050QGH50 800×480),
//     lcd_timing = exemple Sipeed 800_480_screen SYNC-DE ; mire de barres.
//   - USB  : copie conforme de usb_uart_loopback Sipeed (PLL_F 50→48 MHz, PLL_B 48→960/60 MHz,
//     PHY soft + contrôleur CDC-ACM). Le CDC expose l'EP2 : TX vers le PC, RX du PC.
//   - DDR3 : moteur de test Sipeed (ddr3_test + netlist DDR3_Memory_Interface_Top),
//     brochage exact de pro.cst.
// La machine CDC émet en boucle `W R num_ok[23:0]` (5 octets, 1 rafale/s) sur l'EP2 TX.
// Critère E1 : "57 52 FF FF FF" = W + R + 0xFFFFFF (les 16 777 215 mots de 256 bits tous corrects).
module console_top (
    input  wire       clk,            // 50 MHz P16 (oscillateur du Dock)
    output wire [5:0] lcd_r,
    output wire [5:0] lcd_g,
    output wire [5:0] lcd_b,
    output wire       lcd_en,
    output wire       lcd_hs,         // HSYNC (MIPI-DPI broche 32, H22)
    output wire       lcd_vs,         // VSYNC (MIPI-DPI broche 33, A23)
    output wire       lcd_bl,         // BACKLIGHT enable (F25, broche 47)
    output wire       lcd_clk,
    output wire [5:0] led,
    // soft USB (brochage usb_ref.cst du port SOFT-USB)
    inout  wire       usb_dxp_io,
    inout  wire       usb_dxn_io,
    input  wire       usb_rxdp_i,
    input  wire       usb_rxdn_i,
    output wire       usb_pullup_en_o,
    inout  wire       usb_term_dp_io,
    inout  wire       usb_term_dn_io,
    // DDR3 (brochage pro_ddr_test Sipeed)
    output wire       ddr_init,
    output wire [2:0] ddr_bank,
    output wire       ddr_cs_n,
    output wire       ddr_ras_n,
    output wire       ddr_cas_n,
    output wire       ddr_we_n,
    output wire       ddr_ck,
    output wire       ddr_ck_n,
    output wire       ddr_cke,
    output wire       ddr_odt,
    output wire       ddr_reset_n,
    output wire [15:0] ddr_addr,
    output wire [3:0] ddr_dm,
    inout  wire [31:0] ddr_dq,
    inout  wire [3:0]  ddr_dqs,
    inout  wire [3:0]  ddr_dqs_n
);
    // ====================== LCD 800×480, 35 MHz ==========================
    wire lcd_clk_pix;
    Gowin_PLL_LCD u_pll_lcd (
        .clkout0 (lcd_clk_pix),   // 35 MHz (MDIV 21, ODIV0 30, FCLKIN 50)
        .clkin   (clk)
    );

    wire rst_n = 1'b1;

    lcd_timing u_lcd (
        .lcd_clk (lcd_clk_pix),
        .rst_n   (rst_n),
        .lcd_en  (lcd_en),
        .lcd_hs  (lcd_hs),
        .lcd_vs  (lcd_vs),
        .lcd_r   (lcd_r),
        .lcd_b   (lcd_b),
        .lcd_g   (lcd_g)
    );
    assign lcd_bl = rst_n;
    assign lcd_clk = lcd_clk_pix;

    // LED0 = battement de cœur du fabric (~10 Hz), LED1 = PLL USB (E0b)
    reg [24:0] led_cnt;
    always @(posedge lcd_clk_pix or negedge rst_n) begin
        if (!rst_n)                 led_cnt <= 25'd0;
        else if (led_cnt == 25'd1700000) led_cnt <= 25'd0;
        else                        led_cnt <= led_cnt + 1'b1;
    end

    // ====================== moteur de test DDR3 : signaux ======================
    wire        memory_clk, clk100M_ddr, clk_x1, init_calib_complete;
    wire        pll_stop;                // la netlist commande l'arrêt de sa PLL interne (enclk2)
    wire        app_rdy, app_wdf_rdy, app_rd_data_valid, app_burst;
    wire [2:0]   app_cmd;
    wire         app_en;
    wire [28:0]  app_addr;
    wire [255:0] app_wdf_data, app_rd_data;
    wire         app_wdf_wren, app_wdf_end;
    wire        wdone, rdone;
    wire [23:0] num_ok;
    wire [2:0]  test_state;
    wire [31:0] ddr_mask_zero = 32'd0;

    // netlist DDR3 Gowin (pro_ddr_test Sipeed) : horloges de la PLL_F étendue
    DDR3_Memory_Interface_Top u_ddr3 (
        .memory_clk         (memory_clk),
        .pll_stop           (pll_stop),   // la netlist commande l'arrêt de sa PLL interne
        .clk                (clk100M_ddr),
        .rst_n              (rst_n),
        .cmd_ready          (app_rdy),
        .cmd                (app_cmd),
        .cmd_en             (app_en),
        .addr               (app_addr),
        .wr_data_rdy        (app_wdf_rdy),
        .wr_data            (app_wdf_data),
        .wr_data_en         (app_wdf_wren),
        .wr_data_end        (app_wdf_end),
        .wr_data_mask       (ddr_mask_zero),
        .rd_data            (app_rd_data),
        .rd_data_valid      (app_rd_data_valid),
        .rd_data_end        (),
        .sr_req             (1'b0),
        .ref_req            (1'b0),
        .sr_ack             (),
        .ref_ack            (),
        .init_calib_complete(init_calib_complete),
        .clk_out            (clk_x1),
        .pll_lock           (pll_ddr_lock),
        .burst              (app_burst),
        .ddr_rst            (),
        .O_ddr_addr         (ddr_addr),
        .O_ddr_ba           (ddr_bank),
        .O_ddr_cs_n         (ddr_cs_n),
        .O_ddr_ras_n        (ddr_ras_n),
        .O_ddr_cas_n        (ddr_cas_n),
        .O_ddr_we_n         (ddr_we_n),
        .O_ddr_clk          (ddr_ck),
        .O_ddr_clk_n        (ddr_ck_n),
        .O_ddr_cke          (ddr_cke),
        .O_ddr_odt          (ddr_odt),
        .O_ddr_reset_n      (ddr_reset_n),
        .O_ddr_dqm          (ddr_dm),
        .IO_ddr_dq          (ddr_dq),
        .IO_ddr_dqs         (ddr_dqs),
        .IO_ddr_dqs_n       (ddr_dqs_n)
    );




    // lissage du rd_data_valid (fix timing Sipeed, 2024/04/14)
    reg         read_av;
    reg [255:0] read_data;
    always @(posedge clk_x1) begin
        read_av   <= app_rd_data_valid;
        read_data <= app_rd_data;
    end

    ddr3_test u_ddr_test (
        .clk                (clk_x1),
        .rst_n              (rst_n),
        .app_rdy            (app_rdy),
        .app_cmd            (app_cmd),
        .app_en             (app_en),
        .app_addr           (app_addr),
        .wr_data_rdy        (app_wdf_rdy),
        .app_wdf_data       (app_wdf_data),
        .app_wdf_wren       (app_wdf_wren),
        .app_wdf_end        (app_wdf_end),
        .app_wdf_mask       (ddr_mask_zero),
        .app_burst          (app_burst),
        .app_rd_data_valid  (read_av),
        .app_rd_data        (read_data),
        .init_calib_complete(init_calib_complete),
        .wdone              (wdone),
        .rdone              (rdone),
        .num_ok             (num_ok),
        .test_state         (test_state)
    );

    // LED2-5 = état du test DDR3 (motifs du top Sipeed), LED0 = battement, LED1 = PLL USB
    wire [5:0] led_state =
        (test_state == 3'd0) ? 6'b111110 :
        (test_state == 3'd1) ? 6'b111101 :
        (test_state == 3'd2) ? 6'b111011 :
        (test_state == 3'd3) ? 6'b110111 :
        (test_state == 3'd4) ? 6'b101111 :
        (test_state == 3'd5) ? 6'b011111 : 6'b111111;

    // ====================== soft USB CDC (copie Sipeed E0b) =====================
    wire pll_f_lock, pll_b_lock, clk48, fclk_960m, phy_clk;
    Gowin_PLL_F u_pll_f (
        .lock    (pll_f_lock),
        .clkout0 (clk48),
        .clkin   (clk),
        .reset   (1'b0)
    );
    // PLL DDR de Sipeed (100/400 MHz), placée à gauche près du PHY DDR3
    Gowin_PLL u_pll_ddr (
        .lock   (pll_ddr_lock),
        .clkout0(),
        .clkout1(clk100M_ddr),
        .clkout2(memory_clk),
        .clkin  (clk),
        .reset  (1'b0),
        .enclk0 (1'b1),
        .enclk1 (1'b1),
        .enclk2 (pll_stop)
    );
    Gowin_PLL_B u_pll_b (
        .lock    (pll_b_lock),
        .clkout0 (fclk_960m),
        .clkout1 (phy_clk),
        .clkin   (clk48),
        .reset   (1'b0)
    );

    wire rst_usb = ~(pll_f_lock & pll_b_lock);

    wire        usb_highspeed, usb_online, usb_suspend, usb_busreset, usb_sof;
    wire [1:0]  PHY_XCVRSELECT, PHY_OPMODE, PHY_LINESTATE;
    wire        PHY_TERMSELECT, PHY_TXVALID, PHY_TXREADY, PHY_RXVALID, PHY_RXACTIVE, PHY_RXERROR;
    wire [7:0]  PHY_DATAIN, PHY_DATAOUT;
    wire        PHY_RESET;
    wire [15:0] DESC_DEV_ADDR, DESC_DEV_LEN, DESC_QUAL_ADDR, DESC_QUAL_LEN,
                DESC_FSCFG_ADDR, DESC_FSCFG_LEN, DESC_HSCFG_ADDR, DESC_HSCFG_LEN,
                DESC_OSCFG_ADDR, DESC_BOS_ADDR, DESC_BOS_LEN,
                DESC_STRLANG_ADDR, DESC_STRVENDOR_ADDR, DESC_STRVENDOR_LEN,
                DESC_STRPRODUCT_ADDR, DESC_STRPRODUCT_LEN,
                DESC_STRSERIAL_ADDR, DESC_STRSERIAL_LEN;
    wire [7:0]  DESCROM_RDAT, DESC_INDEX, DESC_TYPE;
    wire [15:0] DESCROM_RADDR;
    wire        DESCROM_HAVE_STRINGS;
    wire        RESET = rst_usb;
    wire        setup_active;
    wire [3:0]  endpt_sel;
    wire        usb_rxval, usb_rxact, usb_rxpktval, usb_rxrdy;
    wire [7:0]  usb_rxdat;
    wire        usb_txact, usb_txpop, usb_txpktfin, usb_txcork;
    wire [7:0]  usb_txdat;
    wire [11:0] usb_txdat_len;
    wire [7:0]  endpt0_dat;
    wire        endpt0_send;
    wire [11:0] uart_config_txdat_len;
    wire        uart_en;                 // config de l'UART (usb_uart_config, inutilisé en E1)
    wire [31:0] uart_dte_rate;
    wire [7:0]  uart_char_format, uart_parity_type, uart_data_bits;
    wire        uart_rx_data_val;      // EP2 TX : impulsion par octet (machine CDC)
    wire [15:0] uart_rx_data;
    wire        ep_usb_rxrdy, ep_usb_txcork, ep2_rx_dval;
    wire [11:0] ep_usb_txlen; wire [7:0] ep_usb_txdat;
    wire [7:0]  ep2_rx_data;
    wire [7:0]  inf_alter_i, inf_alter_o, inf_sel_o;
    wire        inf_set_o;
    reg  [7:0]  interface0_alter, interface1_alter;

    localparam ENDPT_UART_CONFIG = 4'd0;

    // LED0 = battement (~10 Hz), LED1 = PLL_F verrouillée, LED2-5 = test_state DDR3 (0..5)
    assign led[0] = ~usb_online;         // LED0 : configuré USB (fix du battement jamais à 0xFF)
    assign led[1] = ~pll_f_lock;          // PLL_F (48/100/400 MHz) verrouillée
    assign led[2] = test_state[0];
    assign led[3] = test_state[1];
    assign led[4] = test_state[2];
    assign led[5] = init_calib_complete;  // calibration DDR3 terminée

    usb_fifo u_usb_fifo (
        .i_clk         (phy_clk),
        .i_reset       (usb_busreset),
        .i_usb_endpt   (endpt_sel),
        .i_usb_rxact   (usb_rxact),
        .i_usb_rxval   (usb_rxval),
        .i_usb_rxpktval(usb_rxpktval),
        .i_usb_rxdat   (usb_rxdat),
        .o_usb_rxrdy   (ep_usb_rxrdy),
        .i_usb_txact   (usb_txact),
        .i_usb_txpop   (usb_txpop),
        .i_usb_txpktfin(usb_txpktfin),
        .o_usb_txcork  (ep_usb_txcork),
        .o_usb_txlen   (ep_usb_txlen),
        .o_usb_txdat   (ep_usb_txdat),
        .i_ep2_tx_clk  (phy_clk),
        .i_ep2_tx_max  (12'd64),
        .i_ep2_tx_dval (uart_rx_data_val),
        .i_ep2_tx_data (uart_rx_data[7:0]),
        .i_ep2_rx_clk  (phy_clk),
        .i_ep2_rx_rdy  (1'b1),                        // accepte ce que le PC envoie (pas consommé en E1)
        .o_ep2_rx_dval (ep2_rx_dval),
        .o_ep2_rx_data (ep2_rx_data)
    );

    assign usb_rxrdy     = ep_usb_rxrdy;
    assign usb_txcork    = (endpt_sel == ENDPT_UART_CONFIG) ? 1'b0 : ep_usb_txcork;
    assign usb_txdat     = (endpt_sel == ENDPT_UART_CONFIG) ? endpt0_dat : ep_usb_txdat;
    assign usb_txdat_len = (endpt_sel == ENDPT_UART_CONFIG) ? uart_config_txdat_len : ep_usb_txlen;

    always @(posedge phy_clk or posedge RESET) begin
        if (RESET) begin
            interface0_alter <= 8'd0;
            interface1_alter <= 8'd0;
        end
        else if (inf_set_o) begin
            if (inf_sel_o == 8'd0)      interface0_alter <= inf_alter_o;
            else if (inf_sel_o == 8'd1) interface1_alter <= inf_alter_o;
        end
    end
    assign inf_alter_i = (inf_sel_o == 8'd0) ? interface0_alter :
                         (inf_sel_o == 8'd1) ? interface1_alter : 8'd0;

    usb_desc #(
        .SERIALSTR       ("11252024"),
        .SERIALSTR_LEN   (8),
        .VENDORSTR       ("Electrosens"),
        .VENDORSTR_LEN   (11),
        .PRODUCTSTR      ("MegaPro Console"),
        .PRODUCTSTR_LEN  (15),
        .VENDORID        (16'h359F),
        .PRODUCTID       (16'h2011),
        .VERSIONBCD      (16'h0112),
        .HSSUPPORT       (1),
        .SELFPOWERED     (0)
    ) u_usb_desc (
        .CLK                    (phy_clk),
        .RESET                  (RESET),
        .i_pid                  (16'd0),
        .i_vid                  (16'd0),
        .i_descrom_raddr        (DESCROM_RADDR),
        .o_descrom_rdat         (DESCROM_RDAT),
        .o_desc_dev_addr        (DESC_DEV_ADDR),
        .o_desc_dev_len         (DESC_DEV_LEN),
        .o_desc_qual_addr       (DESC_QUAL_ADDR),
        .o_desc_qual_len        (DESC_QUAL_LEN),
        .o_desc_fscfg_addr      (DESC_FSCFG_ADDR),
        .o_desc_fscfg_len       (DESC_FSCFG_LEN),
        .o_desc_hscfg_addr      (DESC_HSCFG_ADDR),
        .o_desc_hscfg_len       (DESC_HSCFG_LEN),
        .o_desc_oscfg_addr      (DESC_OSCFG_ADDR),
        .o_desc_strlang_addr    (DESC_STRLANG_ADDR),
        .o_desc_strvendor_addr  (DESC_STRVENDOR_ADDR),
        .o_desc_strvendor_len   (DESC_STRVENDOR_LEN),
        .o_desc_strproduct_addr (DESC_STRPRODUCT_ADDR),
        .o_desc_strproduct_len  (DESC_STRPRODUCT_LEN),
        .o_desc_strserial_addr  (DESC_STRSERIAL_ADDR),
        .o_desc_strserial_len   (DESC_STRSERIAL_LEN),
        .o_descrom_have_strings (DESCROM_HAVE_STRINGS)
    );

    USB_Device_Controller_Top u_usb_device_controller_top (
        .clk_i                 (phy_clk),
        .reset_i               (RESET),
        .usbrst_o              (usb_busreset),
        .highspeed_o           (usb_highspeed),
        .suspend_o             (usb_suspend),
        .online_o              (usb_online),
        .txdat_i               (usb_txdat),
        .txval_i               (endpt0_send & (endpt_sel == ENDPT_UART_CONFIG)),
        .txdat_len_i           (usb_txdat_len),
        .txcork_i              (usb_txcork),
        .txiso_pid_i           (4'b0011),
        .txpop_o               (usb_txpop),
        .txact_o               (usb_txact),
        .txpktfin_o            (usb_txpktfin),
        .rxdat_o               (usb_rxdat),
        .rxval_o               (usb_rxval),
        .rxact_o               (usb_rxact),
        .rxrdy_i               (usb_rxrdy),
        .rxpktval_o            (usb_rxpktval),
        .setup_o               (setup_active),
        .endpt_o               (endpt_sel),
        .sof_o                 (usb_sof),
        .inf_alter_i           (inf_alter_i),
        .inf_alter_o           (inf_alter_o),
        .inf_sel_o             (inf_sel_o),
        .inf_set_o             (inf_set_o),
        .descrom_rdata_i       (DESCROM_RDAT),
        .descrom_raddr_o       (DESCROM_RADDR),
        .desc_index_o          (DESC_INDEX),
        .desc_type_o           (DESC_TYPE),
        .desc_dev_addr_i       (DESC_DEV_ADDR),
        .desc_dev_len_i        (DESC_DEV_LEN),
        .desc_qual_addr_i      (DESC_QUAL_ADDR),
        .desc_qual_len_i       (DESC_QUAL_LEN),
        .desc_fscfg_addr_i     (DESC_FSCFG_ADDR),
        .desc_fscfg_len_i      (DESC_FSCFG_LEN),
        .desc_hscfg_addr_i     (DESC_HSCFG_ADDR),
        .desc_hscfg_len_i      (DESC_HSCFG_LEN),
        .desc_oscfg_addr_i     (DESC_OSCFG_ADDR),
        .desc_hidrpt_addr_i    (16'd0),
        .desc_hidrpt_len_i     (16'd0),
        .desc_bos_addr_i       (DESC_BOS_ADDR),
        .desc_bos_len_i        (DESC_BOS_LEN),
        .desc_strlang_addr_i   (DESC_STRLANG_ADDR),
        .desc_strvendor_addr_i (DESC_STRVENDOR_ADDR),
        .desc_strvendor_len_i  (DESC_STRVENDOR_LEN),
        .desc_strproduct_addr_i(DESC_STRPRODUCT_ADDR),
        .desc_strproduct_len_i (DESC_STRPRODUCT_LEN),
        .desc_strserial_addr_i (DESC_STRSERIAL_ADDR),
        .desc_strserial_len_i  (DESC_STRSERIAL_LEN),
        .desc_have_strings_i   (DESCROM_HAVE_STRINGS),
        .utmi_dataout_o        (PHY_DATAOUT),
        .utmi_txvalid_o        (PHY_TXVALID),
        .utmi_txready_i        (PHY_TXREADY),
        .utmi_datain_i         (PHY_DATAIN),
        .utmi_rxactive_i       (PHY_RXACTIVE),
        .utmi_rxvalid_i        (PHY_RXVALID),
        .utmi_rxerror_i        (PHY_RXERROR),
        .utmi_linestate_i      (PHY_LINESTATE),
        .utmi_opmode_o         (PHY_OPMODE),
        .utmi_xcvrselect_o     (PHY_XCVRSELECT),
        .utmi_termselect_o     (PHY_TERMSELECT),
        .utmi_reset_o          (PHY_RESET)
    );

    USB2_0_SoftPHY_Top u_usb_softphy_top (
        .clk_i            (phy_clk),
        .rst_i            (PHY_RESET),
        .fclk_i           (fclk_960m),
        .pll_locked_i     (pll_b_lock),
        .utmi_data_out_i  (PHY_DATAOUT),
        .utmi_txvalid_i   (PHY_TXVALID),
        .utmi_op_mode_i   (PHY_OPMODE),
        .utmi_xcvrselect_i(PHY_XCVRSELECT),
        .utmi_termselect_i(PHY_TERMSELECT),
        .utmi_data_in_o   (PHY_DATAIN),
        .utmi_txready_o   (PHY_TXREADY),
        .utmi_rxvalid_o   (PHY_RXVALID),
        .utmi_rxactive_o  (PHY_RXACTIVE),
        .utmi_rxerror_o   (PHY_RXERROR),
        .utmi_linestate_o (PHY_LINESTATE),
        .usb_dxp_io       (usb_dxp_io),
        .usb_dxn_io       (usb_dxn_io),
        .usb_rxdp_i       (usb_rxdp_i),
        .usb_rxdn_i       (usb_rxdn_i),
        .usb_pullup_en_o  (usb_pullup_en_o),
        .usb_term_dp_io   (usb_term_dp_io),
        .usb_term_dn_io   (usb_term_dn_io)
    );

    usb_uart_config u_usb_uart_config (
        .PHY_CLKOUT         (phy_clk),
        .RESET_IN           (usb_busreset),
        .setup_active       (setup_active),
        .endpt_sel          (endpt_sel),
        .usb_rxval          (usb_rxval),
        .usb_rxact          (usb_rxact),
        .usb_rxdat          (usb_rxdat),
        .usb_txact          (usb_txact),
        .usb_txpop          (usb_txpop),
        .usb_txdat_len_o    (uart_config_txdat_len),
        .endpt0_dat_o       (endpt0_dat),
        .endpt0_send_o      (endpt0_send),
        .uart1_en_o         (uart_en),
        .uart1_BAUD_RATE_o  (uart_dte_rate),
        .uart1_PARITY_BIT_o (uart_parity_type),
        .uart1_STOP_BIT_o   (uart_char_format),
        .uart1_DATA_BITS_o  (uart_data_bits)
    );
    defparam u_usb_uart_config.ENDPT_UART_CONFIG = ENDPT_UART_CONFIG;

    // ====================== émission CDC : rafale "57 52 num_ok" en boucle =========
    // Un octet par transition d'état (cdc_dval = 1 un cycle), 1 ms entre octets, 1 s entre rafales.
    // Conditionnée à usb_online (le PC voit l'énumération). La rafale ré-émet wdone/rdone/num_ok
    // du ddr3_test, qui restent valides après la fin du test.
    reg [27:0] cdc_pause;
    reg [2:0]  cdc_state;   // 0 = attente (test pas fini) ; 1 = pause 1 s ; 2..6 = octet seq 0..4
    reg [2:0]  cdc_seq;
    reg        cdc_dval;
    reg [7:0]  cdc_data;

    localparam CDC_BYTE_GAP = 27'd59_999;       // 1 ms entre octets @ 60 MHz
    localparam CDC_PAUSE_1S = 27'd59_999_999;   // 1 s entre rafales

    assign uart_rx_data_val = cdc_dval;
    assign uart_rx_data     = {8'd0, cdc_data};

    always @(posedge phy_clk or posedge RESET) begin
        if (RESET) begin
            cdc_pause <= 27'd0;
            cdc_state <= 3'd0;
            cdc_seq   <= 3'd0;
            cdc_dval  <= 1'b0;
            cdc_data  <= 8'd0;
        end
        else begin
            cdc_dval <= 1'b0;                    // une impulsion par cycle, activée par la machine
            case (cdc_state)
                3'd0: if (usb_online) begin
                    cdc_pause <= 27'd0;
                    cdc_seq   <= 3'd0;
                    cdc_state <= 3'd1;
                end
                3'd1: begin                      // pause 1 s avant chaque rafale
                    if (cdc_pause >= CDC_PAUSE_1S) begin
                        cdc_pause <= 27'd0;
                        cdc_seq   <= 3'd0;
                        cdc_state <= 3'd2;
                    end else cdc_pause <= cdc_pause + 1'b1;
                end
                3'd2, 3'd3, 3'd4, 3'd5, 3'd6: begin
                    case (cdc_seq)
                        3'd0: cdc_data <= "W";
                        3'd1: cdc_data <= "R";
                        3'd2: cdc_data <= num_ok[23:16];
                        3'd3: cdc_data <= num_ok[15:8];
                        default: cdc_data <= num_ok[7:0];
                    endcase
                    cdc_dval <= 1'b1;            // UNE impulsion par état
                    cdc_pause <= 27'd0;
                    cdc_seq   <= (cdc_seq == 3'd4) ? 3'd0 : cdc_seq + 3'd1;
                    cdc_state <= (cdc_seq == 3'd4) ? 3'd1 : cdc_state + 3'd1;
                end
                default: cdc_state <= 3'd0;
            endcase
        end
    end

endmodule
`default_nettype wire
