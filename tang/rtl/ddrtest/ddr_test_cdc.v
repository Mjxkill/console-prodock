// ddr_test_cdc.v — E1 : test DDR3 Sipeed, console par notre CDC USB (port SOFT-USB, ttyACM0).
//
// Le top console_top E0b (LCD 800×480 mire + CDC) est conservé, on y ajoute le moteur de test DDR3
// de Sipeed (ddr3_test + netlist DDR3) et une machine qui émet en boucle `W R num_ok[23:0]` sur l'EP2 TX
// (uart_rx_data_val/uart_rx_data du usb_fifo = entrée EP2 TX). Le critère reste "57 52 FF FF FF" :
// W + R + 0xFFFFFF = les 16 777 215 mots de 256 bits tous corrects.
// La liaison CDC a été validée en E0a/E0b (énumération + loopback bidirectionnel).
`default_nettype none
module console_top #(
    parameter RUN_DDR_TEST = 1
) (
    input  wire       clk,            // 50 MHz P16
    output wire [5:0] lcd_r,
    output wire [5:0] lcd_g,
    output wire [5:0] lcd_b,
    output wire       lcd_en,
    output wire       lcd_hs,
    output wire       lcd_vs,
    output wire       lcd_bl,
    output wire       lcd_clk,
    output wire [5:0] led,
    inout  wire       usb_dxp_io,
    inout  wire       usb_dxn_io,
    input  wire       usb_rxdp_i,
    input  wire       usb_rxdn_i,
    output wire       usb_pullup_en_o,
    inout  wire       usb_term_dp_io,
    inout  wire       usb_term_dn_io,
    output wire       uart_tx,
    // DDR3 (brochage Pro Dock, cf. constr/ddr_e1.cst)
    output wire       DDR3_INIT,
    output wire [2:0] DDR3_BANK,
    output wire       DDR3_CS_N,
    output wire       DDR3_RAS_N,
    output wire       DDR3_CAS_N,
    output wire       DDR3_WE_N,
    output wire       DDR3_CK,
    output wire       DDR3_CK_N,
    output wire       DDR3_CKE,
    output wire       DDR3_RESET_N,
    output wire       DDR3_ODT,
    output wire [15:0] DDR3_ADDR,
    output wire [3:0] DDR3_DM,
    inout  wire [31:0] DDR3_DQ,
    inout  wire [3:0]  DDR3_DQS,
    inout  wire [3:0]  DDR3_DQS_N
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

    // LED0 = battement de cœur du fabric
    reg [24:0] led_cnt;
    always @(posedge lcd_clk_pix or negedge rst_n) begin
        if (!rst_n)                 led_cnt <= 25'd0;
        else if (led_cnt == 25'd1700000) led_cnt <= 25'd0;  // ~10 Hz aller-retour
        else                        led_cnt <= led_cnt + 1'b1;
    end

    // ====================== soft USB CDC (copie Sipeed E0b) ==============
    wire pll_f_lock, pll_b_lock, clk48, fclk_960m, phy_clk;
    Gowin_PLL_F u_pll_f (
        .lock    (pll_f_lock),
        .clkout0 (clk48),
        .clkin   (clk),
        .reset   (1'b0)
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
    wire        uart_tx_busy, uart_rx_data_val;
    wire [15:0] uart_rx_data;
    wire [7:0]  endpt0_dat;
    wire        endpt0_send;
    wire [11:0] uart_config_txdat_len;
    wire        ep_usb_rxrdy, ep_usb_txcork, ep2_rx_dval;
    wire [11:0] ep_usb_txlen; wire [7:0] ep_usb_txdat;
    wire [7:0]  ep2_rx_data;
    wire [7:0]  inf_alter_i, inf_alter_o, inf_sel_o;
    wire        inf_set_o;
    reg  [7:0]  interface0_alter, interface1_alter;
    wire        uart_txd;
    wire        uart_en;
    wire [31:0] uart_dte_rate;
    wire [7:0]  uart_char_format, uart_parity_type, uart_data_bits;
    wire        uart_cts = 1'b0;
    wire        uart_rxd;

    localparam ENDPT_UART_CONFIG = 4'd0;

    assign uart_tx = uart_txd;
    assign uart_rxd = uart_txd;                       // loopback matériel conservé (E0a)
    assign led[0] = ~(&led_cnt[23:16]);
    assign led[1] = ~pll_b_lock;
    assign led[2] = ~rst_usb;
    assign led[3] = ~PHY_XCVRSELECT[0];
    assign led[4] = ~PHY_XCVRSELECT[1];
    assign led[5] = ~usb_highspeed;

    UART #(.CLK_FREQ(30'd60000000)) u_uart (
        .CLK        (phy_clk),
        .RST        (RESET),
        .UART_TXD   (uart_txd),
        .UART_RXD   (uart_rxd),
        .UART_RTS   (),
        .UART_CTS   (uart_cts),
        .BAUD_RATE  (uart_dte_rate),
        .PARITY_BIT (uart_parity_type),
        .STOP_BIT   (uart_char_format),
        .DATA_BITS  (uart_data_bits),
        .TX_DATA    ({8'd0, ep2_rx_data}),
        .TX_DATA_VAL(ep2_rx_dval),
        .TX_BUSY    (uart_tx_busy),
        .RX_DATA    (uart_rx_data),
        .RX_DATA_VAL(uart_rx_data_val)
    );

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
        .i_ep2_rx_rdy  (!uart_tx_busy),
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

    // ====================== moteur de test DDR3 (Sipeed) ======================
    wire memory_clk, pll_stop, pll_ddr_lock, clk_x1, init_calib_complete;
    wire app_rdy, app_wdf_rdy, app_rd_data_valid, app_burst;
    wire [2:0]   app_cmd;
    wire         app_en;
    wire [28:0]  app_addr;
    wire [255:0] app_wdf_data, app_rd_data;
    wire         app_wdf_wren, app_wdf_end;

    Gowin_PLL_DDR u_pll_ddr (
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

    wire        DDR3_INIT;
    wire        ddr_cs, ddr_ras, ddr_cas, ddr_we;
    wire        ddr_ck, ddr_ck_n, ddr_cke, ddr_odt, ddr_reset_n;
    wire [14:0] ddr_addr;
    wire [2:0]  ddr_bank;
    wire [3:0]  ddr_dm;
    wire [31:0] ddr_dq;
    wire [3:0]  ddr_dqs, ddr_dqs_n;

    DDR3_Memory_Interface_Top u_ddr3 (
        .memory_clk         (memory_clk),
        .pll_stop           (pll_stop),
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
        .wr_data_mask       (32'd0),
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
        .O_ddr_cs_n         (ddr_cs),
        .O_ddr_ras_n        (ddr_ras),
        .O_ddr_cas_n        (ddr_cas),
        .O_ddr_we_n         (ddr_we),
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

    reg         read_av;
    reg [255:0] read_data;
    always @(posedge clk_x1) begin
        read_av   <= app_rd_data_valid;
        read_data <= app_rd_data;
    end

    wire        wdone, rdone;
    wire [23:0] num_ok;
    wire [2:0]  test_state;

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
        .app_wdf_mask       (app_wdf_mask),
        .app_burst          (app_burst),
        .app_rd_data_valid  (read_av),
        .app_rd_data        (read_data),
        .init_calib_complete(init_calib_complete),
        .wdone              (wdone),
        .rdone              (rdone),
        .num_ok             (num_ok),
        .test_state         (test_state)
    );

    // ====================== émission CDC : rafale "57 52 num_ok" en boucle =========
    // Rythme : 1 rafale (5 octets) toutes les 1 s ; 5 octets = W, R, num_ok[23:16], [15:8], [7:0].
    // La chaîne EP2 TX (usb_fifo : i_ep2_tx_dval/i_ep2_tx_data) a été validée en E0 (loopback).
    // ATTENTION : i_ep2_rx_rdy(!uart_tx_busy) — l'UART physique est la porte de sortie du FIFO EP2.
    // Ici, on n'utilise PAS l'UART physique : le UART_TX Sipeed (u_uart) est conservé pour son loopback
    // matériel (E0a) et son TX reste inutilisé. Les octets du test vont dans l'EP2 TX du CDC.
    reg [23:0] cdc_cnt;
    reg [27:0] cdc_pause;
    reg [2:0]  cdc_state;
    reg [2:0]  cdc_seq;

    localparam CDC_PAUSE_1S = 27'd59_999_999;  // 60 M cycles @ phy_clk 60 MHz ≈ 1 s

    always @(posedge phy_clk or posedge RESET) begin
        if (RESET) begin
            cdc_cnt    <= 24'd0;
            cdc_pause  <= 27'd0;
            cdc_state  <= 3'd0;
            cdc_seq    <= 3'd0;
        end
        else begin
            // par défaut : rien à émettre
            case (cdc_state)
                3'd0: if (wdone & rdone) begin           // test DDR3 fini : rafale vers le PC
                    cdc_state <= 3'd1;
                    cdc_seq   <= 3'd0;
                    cdc_pause <= 27'd0;
                end
                3'd1: begin                              // W
                    if (cdc_pause == 27'd0) begin
                        i_ep2_tx_dval <= 1'b1;
                        i_ep2_tx_data <= "W";
                    end
                    if (cdc_pause >= 27'd599_999) begin  // 10 ms
                        cdc_pause <= 27'd0;
                        cdc_state <= 3'd2;
                    end else cdc_pause <= cdc_pause + 1'b1;
                end
                3'd2: begin                              // R
                    if (cdc_pause == 27'd0) begin
                        i_ep2_tx_dval <= 1'b1;
                        i_ep2_tx_data <= "R";
                    end
                    if (cdc_pause >= 27'd599_999) begin
                        cdc_pause <= 27'd0;
                        cdc_state <= 3'd3;
                    end else cdc_pause <= cdc_pause + 1'b1;
                end
                3'd3: begin                              // num_ok[23:16]
                    if (cdc_pause == 27'd0) begin
                        i_ep2_tx_dval <= 1'b1;
                        i_ep2_tx_data <= num_ok[23:16];
                    end
                    if (cdc_pause >= 27'd599_999) begin
                        cdc_pause <= 27'd0;
                        cdc_state <= 3'd4;
                    end else cdc_pause <= cdc_pause + 1'b1;
                end
                3'd4: begin                              // num_ok[15:8]
                    if (cdc_pause == 27'd0) begin
                        i_ep2_tx_dval <= 1'b1;
                        i_ep2_tx_data <= num_ok[15:8];
                    end
                    if (cdc_pause >= 27'd599_999) begin
                        cdc_pause <= 27'd0;
                        cdc_state <= 3'd5;
                    end else cdc_pause <= cdc_pause + 1'b1;
                end
                3'd5: begin                              // num_ok[7:0] puis pause 1 s → nouvelle rafale
                    if (cdc_pause == 27'd0) begin
                        i_ep2_tx_dval <= 1'b1;
                        i_ep2_tx_data <= num_ok[7:0];
                    end
                    if (cdc_pause >= CDC_PAUSE_1S) begin
                        cdc_pause <= 27'd0;
                        cdc_state <= 3'd1;           // nouvelle rafale
                    end else cdc_pause <= cdc_pause + 1'b1;
                end
                default: cdc_state <= 3'd0;
            endcase
        end
    end

endmodule
`default_nettype wire