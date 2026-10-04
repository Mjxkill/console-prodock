// console_top.v — E2 : mire LCD 800×480 + soft USB CDC + SoC AE350 (socle analyseur porté).
//
// Le SoC et sa DDR3 : le socle VALIDÉ de l'analyseur (ae350_soc.v + ddr_subsys + pont Sipeed +
// IP DDR3 standalone Gowin). Le contrôleur DDR3 embarqué du SoC est écarté (faits mesurés :
// son pont AHB interne rend 0x00000000 — ARCHI_V3 § E1, en-tête ae350_soc.v).
// Horloges (faits mesurés V3) : memory_clk 300 MHz (400 ne calibre pas de façon fiable),
// DDR_CLK/HCLK 50 MHz, CORE 800 / AHB = APB 80 / RTC 10 depuis la PLL système.
// La console AE350 (UART2) rejoint le CDC par le pont uart2_to_ep2 (EP2).
`default_nettype none
module console_top (
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
    // soft USB (brochage usb_ref.cst)
`ifndef CONSOLE_USB_FS_PHY
    inout  wire       usb_dxp_io,
    inout  wire       usb_dxn_io,
    input  wire       usb_rxdp_i,
    input  wire       usb_rxdn_i,
`endif
    output wire       usb_pullup_en_o,
    inout  wire       usb_term_dp_io,
    inout  wire       usb_term_dn_io,
    // DDR3 (brochage pro_ddr_test Sipeed, banques 1.5 V)
    output wire [2:0] ddr_bank,
    output wire       ddr_cs, ddr_ras, ddr_cas, ddr_we, ddr_ck, ddr_ck_n, ddr_cke, ddr_reset_n, ddr_odt,
    output wire [15:0] ddr_addr,
    output wire [3:0]  ddr_dm,
    inout  wire [31:0] ddr_dq,
    inout  wire [3:0]  ddr_dqs, ddr_dqs_n,
    // JTAG du AE350 (PMOD1)
    input  wire       ae350_tck,
    input  wire       ae350_tms,
    input  wire       ae350_tdi,
     output wire       ae350_tdo,
     output wire       ae350_tx_pin   // espion UART2 sur broche (comme l'analyseur : F19)
);
    assign ae350_tx_pin = ae350_tx;
    // ====================== LCD 800×480, 35 MHz ==========================
    wire lcd_clk_pix;
    Gowin_PLL_LCD u_pll_lcd (.clkout0 (lcd_clk_pix), .clkin (clk));
    wire rst_n = 1'b1;
    wire vid_hclk, vid_hrstn, vid_hsel, vid_hwrite, vid_hready;
    wire [31:0] vid_haddr, vid_hwdata, vid_hrdata;
    wire [1:0] vid_htrans;
    wire gpu_clk, gpu_valid, gpu_ready, gpu_data_valid;
    wire [28:0] gpu_addr;
    wire [255:0] gpu_data;
    wire blit_valid, blit_write, blit_ready, blit_rd_valid;
    wire [28:0] blit_addr;
    wire [255:0] blit_wr_data, blit_rd_data;
    wire [31:0] blit_wr_mask;
`ifdef CONSOLE_GPU
    wire [31:0] scan_hrdata, blit_hrdata, usb_trace_hrdata;
    wire scan_hready, blit_hready, usb_trace_hready;
    reg blit_selected, usb_trace_selected;
    always @(posedge vid_hclk) begin
        if (!vid_hrstn) begin blit_selected <= 1'b0; usb_trace_selected <= 1'b0; end
        else if (vid_hready) begin
            blit_selected <= vid_haddr[12]; usb_trace_selected <= vid_haddr[13];
        end
    end
    assign vid_hrdata = usb_trace_selected ? usb_trace_hrdata : (blit_selected ? blit_hrdata : scan_hrdata);
    assign vid_hready = usb_trace_selected ? usb_trace_hready : (blit_selected ? blit_hready : scan_hready);
    gpu_scanout u_gpu (
        .hclk(vid_hclk), .hresetn(vid_hrstn), .hsel(vid_hsel && !vid_haddr[13] && !vid_haddr[12] && vid_hready), .hwrite(vid_hwrite),
        .haddr(vid_haddr), .hwdata(vid_hwdata), .htrans(vid_htrans), .hrdata(scan_hrdata), .hready(scan_hready),
        .pixel_clk(lcd_clk_pix), .mem_clk(gpu_clk),
        .fetch_valid(gpu_valid), .fetch_addr(gpu_addr), .fetch_ready(gpu_ready),
        .fetch_data(gpu_data), .fetch_data_valid(gpu_data_valid),
        .lcd_en(lcd_en), .lcd_hs(lcd_hs), .lcd_vs(lcd_vs), .lcd_r(lcd_r), .lcd_g(lcd_g), .lcd_b(lcd_b)
    );
    gpu_accel u_accel (
        .hclk(vid_hclk), .hresetn(vid_hrstn), .hsel(vid_hsel && !vid_haddr[13] && vid_haddr[12] && vid_hready), .hwrite(vid_hwrite),
        .haddr(vid_haddr), .hwdata(vid_hwdata), .htrans(vid_htrans), .hrdata(blit_hrdata), .hready(blit_hready),
        .mem_clk(gpu_clk), .valid(blit_valid), .write(blit_write), .addr(blit_addr),
        .wr_data(blit_wr_data), .wr_mask(blit_wr_mask), .ready(blit_ready),
        .rd_data(blit_rd_data), .rd_valid(blit_rd_valid));
    // Read through AE350 JTAG even if the USB control endpoint is unusable.
    // The E9002000 window adds no control to the USB datapath.
    usb_idle_trace u_usb_idle_trace (
        .clk(phy_clk),.reset_n(vid_hrstn && !rst_usb),.bus_reset(usb_busreset),.sof(usb_sof),
        .rx_active(PHY_RXACTIVE),.rx_valid(PHY_RXVALID),.rx_error(PHY_RXERROR),.rx_data(PHY_DATAIN),
        .tx_valid(PHY_TXVALID),.tx_ready(PHY_TXREADY),.tx_data(PHY_DATAOUT),.endpoint(endpt_sel),.cork(usb_txcork),
        .hclk(vid_hclk),.hsel(vid_hsel && vid_haddr[13] && vid_hready),.hwrite(vid_hwrite),
        .htrans(vid_htrans),.haddr(vid_haddr),.hwdata(vid_hwdata),.hrdata(usb_trace_hrdata),.hready(usb_trace_hready));
`else
    lcd_timing u_lcd (
        .lcd_clk(lcd_clk_pix), .rst_n(rst_n), .lcd_en(lcd_en), .lcd_hs(lcd_hs), .lcd_vs(lcd_vs),
        .lcd_r(lcd_r), .lcd_g(lcd_g), .lcd_b(lcd_b));
    assign vid_hrdata = 32'd0;
    assign vid_hready = 1'b1;
    assign gpu_valid = 1'b0;
    assign gpu_addr = 29'd0;
    assign blit_valid = 0; assign blit_write = 0; assign blit_addr = 0;
    assign blit_wr_data = 0; assign blit_wr_mask = 32'hffffffff;
`endif
    assign lcd_bl = rst_n;
    assign lcd_clk = lcd_clk_pix;

    // ====================== soft USB CDC (copie Sipeed E0b) ==============
    wire pll_f_lock, pll_b_lock, clk48, fclk_960m, phy_clk;
    Gowin_PLL_F u_pll_f (.lock (pll_f_lock), .clkout0 (clk48), .clkin (clk), .reset (1'b0));
    // UG306-1.0.9E, table 5-2: monitor LOCK continuously for at least 2 ms.
    // Use the independent board 50 MHz reference while PLL outputs settle:
    // 104000 cycles = 2.08 ms for each stage of the cascaded PLLs.
    // Then synchronize release into the controller's 60 MHz clock domain.
    // Internal PHY calibration starts after PHY_RESET is released;
    // these qualification delays do not include that calibration.
    wire pll_b_reset, phy_lock_reset, rst_usb;
    usb_reset_release #(.HOLD_CYCLES(104000)) u_usb_ref_start
        (.clk(clk), .locked(pll_f_lock), .reset(pll_b_reset));
    Gowin_PLL_B u_pll_b (.lock (pll_b_lock),
`ifdef CONSOLE_USB_FS_PHY
        .clkout0 (),
`else
        .clkout0 (fclk_960m),
`endif
        .clkout1 (phy_clk), .clkin (clk48), .reset (pll_b_reset));
    usb_reset_release #(.HOLD_CYCLES(104000)) u_usb_phy_start (.clk(clk),
        .locked(pll_f_lock & pll_b_lock & ~pll_b_reset), .reset(phy_lock_reset));
    usb_reset_release #(.HOLD_CYCLES(64)) u_usb_controller_start
        (.clk(phy_clk), .locked(~phy_lock_reset), .reset(rst_usb));

    wire        usb_highspeed, usb_online, usb_suspend, usb_busreset, usb_sof;
    // The controller registers usbrst_o with a synchronous SET. It cannot
    // propagate lock loss while phy_clk is stopped. Reset all application
    // state together with the UART bridge, also during that interval.
    wire        usb_app_reset = RESET | usb_busreset;
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
    wire        ep_usb_rxrdy, ep_usb_txcork, ep2_rx_dval;
    wire [11:0] ep_usb_txlen; wire [7:0] ep_usb_txdat;
    wire [7:0]  ep2_rx_data;
    wire [7:0]  inf_alter_i, inf_alter_o, inf_sel_o;
    wire        inf_set_o;
    reg  [7:0]  interface0_alter, interface1_alter;
    wire        uart_en;
    wire [31:0] uart_dte_rate;
    wire [7:0]  uart_char_format, uart_parity_type, uart_data_bits;
    wire        uart_rx_data_val;      // EP2 TX : impulsion par octet (console AE350)
    wire [7:0] uart_rx_data;
    wire ep2_rx_rdy;

    localparam ENDPT_UART_CONFIG = 4'd0;

    // LED0 = USB configuré, LED1 = PLL_F, LED2 = ae350_rstn, LED3 = DDR3 lock, LED4 = ddr3_stop, LED5 = UART2
    assign led[0] = ~usb_online;
    assign led[1] = ~pll_f_lock;
    assign led[2] = soc_dbg[0];        // ae350_rstn : 1 = CPU actif
    assign led[3] = soc_dbg[1];        // ddr3_lock
    reg led_uart = 1'b1;               // activité après décodage d'un octet UART2 valide
    always @(posedge phy_clk or posedge RESET)
        if (RESET) led_uart <= 1'b1;
        else if (uart_rx_data_val) led_uart <= ~led_uart;
    assign led[5] = led_uart;

    usb_fifo u_usb_fifo (
`ifdef CONSOLE_USB_DIAG
        .diagnostic_data(fifo_diagnostic),
`endif
        .i_clk         (phy_clk),
        .i_reset       (usb_app_reset),
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
        .i_ep2_tx_dval (uart_rx_data_val & usb_online),
        .i_ep2_tx_data (uart_rx_data[7:0]),
        .i_ep2_rx_clk  (phy_clk),
        .i_ep2_rx_rdy  (ep2_rx_rdy),
        .o_ep2_rx_dval (ep2_rx_dval),
        .o_ep2_rx_data (ep2_rx_data)
    );
    // EP0 status OUT must be accepted even for requests handled internally
    // by the controller. Controller 3.2 NAKs that status when RXRDY is low.
    assign usb_rxrdy     = (endpt_sel == ENDPT_UART_CONFIG) ? 1'b1 : ep_usb_rxrdy;
    assign usb_txcork    = (endpt_sel == ENDPT_UART_CONFIG) ? 1'b0 : ep_usb_txcork;
    assign usb_txdat     = (endpt_sel == ENDPT_UART_CONFIG) ? endpt0_dat : ep_usb_txdat;
    assign usb_txdat_len = (endpt_sel == ENDPT_UART_CONFIG) ? uart_config_txdat_len : ep_usb_txlen;

    always @(posedge phy_clk or posedge RESET) begin
        if (RESET) begin
            interface0_alter <= 8'd0; interface1_alter <= 8'd0;
        end else if (inf_set_o) begin
            if (inf_sel_o == 8'd0)      interface0_alter <= inf_alter_o;
            else if (inf_sel_o == 8'd1) interface1_alter <= inf_alter_o;
        end
    end
    assign inf_alter_i = (inf_sel_o == 8'd0) ? interface0_alter :
                         (inf_sel_o == 8'd1) ? interface1_alter : 8'd0;

`ifdef CONSOLE_USB_FULL_SPEED
    localparam USB_HS_SUPPORT = 0;
`else
    localparam USB_HS_SUPPORT = 1;
`endif
    usb_desc #(
        .SERIALSTR("11252024"), .SERIALSTR_LEN(8),
        .VENDORSTR("Electrosens"), .VENDORSTR_LEN(11),
        .PRODUCTSTR("MegaPro Console"), .PRODUCTSTR_LEN(15),
        .VENDORID(16'h359F), .PRODUCTID(16'h2011),
        .VERSIONBCD(16'h0112), .HSSUPPORT(USB_HS_SUPPORT), .SELFPOWERED(0)
    ) u_usb_desc (
        .CLK(phy_clk), .RESET(RESET), .i_pid(16'd0), .i_vid(16'd0),
        .i_descrom_raddr(DESCROM_RADDR), .o_descrom_rdat(DESCROM_RDAT),
        .o_desc_dev_addr(DESC_DEV_ADDR), .o_desc_dev_len(DESC_DEV_LEN),
        .o_desc_qual_addr(DESC_QUAL_ADDR), .o_desc_qual_len(DESC_QUAL_LEN),
        .o_desc_fscfg_addr(DESC_FSCFG_ADDR), .o_desc_fscfg_len(DESC_FSCFG_LEN),
        .o_desc_hscfg_addr(DESC_HSCFG_ADDR), .o_desc_hscfg_len(DESC_HSCFG_LEN),
        .o_desc_oscfg_addr(DESC_OSCFG_ADDR),
        .o_desc_strlang_addr(DESC_STRLANG_ADDR),
        .o_desc_strvendor_addr(DESC_STRVENDOR_ADDR), .o_desc_strvendor_len(DESC_STRVENDOR_LEN),
        .o_desc_strproduct_addr(DESC_STRPRODUCT_ADDR), .o_desc_strproduct_len(DESC_STRPRODUCT_LEN),
        .o_desc_strserial_addr(DESC_STRSERIAL_ADDR), .o_desc_strserial_len(DESC_STRSERIAL_LEN),
        .o_descrom_have_strings(DESCROM_HAVE_STRINGS)
    );

    USB_Device_Controller_Top u_usb_device_controller_top (
        .clk_i(phy_clk), .reset_i(RESET),
        .usbrst_o(usb_busreset), .highspeed_o(usb_highspeed),
        .suspend_o(usb_suspend), .online_o(usb_online),
        .txdat_i(usb_txdat), .txval_i(endpt0_send & (endpt_sel == ENDPT_UART_CONFIG)),
        .txdat_len_i(usb_txdat_len), .txcork_i(usb_txcork), .txiso_pid_i(4'b0011),
        .txpop_o(usb_txpop), .txact_o(usb_txact), .txpktfin_o(usb_txpktfin),
        .rxdat_o(usb_rxdat), .rxval_o(usb_rxval), .rxact_o(usb_rxact), .rxrdy_i(usb_rxrdy),
        .rxpktval_o(usb_rxpktval), .setup_o(setup_active), .endpt_o(endpt_sel), .sof_o(usb_sof),
        .inf_alter_i(inf_alter_i), .inf_alter_o(inf_alter_o), .inf_sel_o(inf_sel_o), .inf_set_o(inf_set_o),
        .descrom_rdata_i(DESCROM_RDAT), .descrom_raddr_o(DESCROM_RADDR),
        .desc_index_o(DESC_INDEX), .desc_type_o(DESC_TYPE),
        .desc_dev_addr_i(DESC_DEV_ADDR), .desc_dev_len_i(DESC_DEV_LEN),
        .desc_qual_addr_i(DESC_QUAL_ADDR), .desc_qual_len_i(DESC_QUAL_LEN),
        .desc_fscfg_addr_i(DESC_FSCFG_ADDR), .desc_fscfg_len_i(DESC_FSCFG_LEN),
        .desc_hscfg_addr_i(DESC_HSCFG_ADDR), .desc_hscfg_len_i(DESC_HSCFG_LEN),
        .desc_oscfg_addr_i(DESC_OSCFG_ADDR),
        .desc_hidrpt_addr_i(16'd0), .desc_hidrpt_len_i(16'd0),
        .desc_bos_addr_i(DESC_BOS_ADDR), .desc_bos_len_i(DESC_BOS_LEN),
        .desc_strlang_addr_i(DESC_STRLANG_ADDR),
        .desc_strvendor_addr_i(DESC_STRVENDOR_ADDR), .desc_strvendor_len_i(DESC_STRVENDOR_LEN),
        .desc_strproduct_addr_i(DESC_STRPRODUCT_ADDR), .desc_strproduct_len_i(DESC_STRPRODUCT_LEN),
        .desc_strserial_addr_i(DESC_STRSERIAL_ADDR), .desc_strserial_len_i(DESC_STRSERIAL_LEN),
        .desc_have_strings_i(DESCROM_HAVE_STRINGS),
        .utmi_dataout_o(PHY_DATAOUT), .utmi_txvalid_o(PHY_TXVALID), .utmi_txready_i(PHY_TXREADY),
        .utmi_datain_i(PHY_DATAIN), .utmi_rxactive_i(PHY_RXACTIVE), .utmi_rxvalid_i(PHY_RXVALID),
        .utmi_rxerror_i(PHY_RXERROR), .utmi_linestate_i(PHY_LINESTATE),
        .utmi_opmode_o(PHY_OPMODE), .utmi_xcvrselect_o(PHY_XCVRSELECT),
        .utmi_termselect_o(PHY_TERMSELECT), .utmi_reset_o(PHY_RESET)
    );

`ifdef CONSOLE_USB_FS_PHY
    // Dedicated 60 MHz Full Speed PHY, connected exactly as the validated
    // Pro Dock witness. The unused HS pins are absent from this variant.
    USB_SoftPHY_Top u_usb_fs_softphy_top (
        .clk_i(phy_clk), .rst_i(PHY_RESET),
        .utmi_data_out_i(PHY_DATAOUT), .utmi_txvalid_i(PHY_TXVALID),
        .utmi_op_mode_i(PHY_OPMODE), .utmi_xcvrselect_i(PHY_XCVRSELECT),
        .utmi_termselect_i(PHY_TERMSELECT), .utmi_data_in_o(PHY_DATAIN),
        .utmi_txready_o(PHY_TXREADY), .utmi_rxvalid_o(PHY_RXVALID),
        .utmi_rxactive_o(PHY_RXACTIVE), .utmi_rxerror_o(PHY_RXERROR),
        .utmi_linestate_o(PHY_LINESTATE),
        .usb_dp_io(usb_term_dp_io), .usb_dn_io(usb_term_dn_io)
    );
    assign usb_pullup_en_o = 1'b1;
`else
    USB2_0_SoftPHY_Top u_usb_softphy_top (
        // Assert reset even when phy_clk stops. Both reset release and the
        // qualified lock rising edge are local to the PHY's 60 MHz domain.
        .clk_i(phy_clk), .rst_i(PHY_RESET | rst_usb), .fclk_i(fclk_960m), .pll_locked_i(~rst_usb),
        .utmi_data_out_i(PHY_DATAOUT), .utmi_txvalid_i(PHY_TXVALID),
        .utmi_op_mode_i(PHY_OPMODE), .utmi_xcvrselect_i(PHY_XCVRSELECT),
        .utmi_termselect_i(PHY_TERMSELECT), .utmi_data_in_o(PHY_DATAIN),
        .utmi_txready_o(PHY_TXREADY), .utmi_rxvalid_o(PHY_RXVALID),
        .utmi_rxactive_o(PHY_RXACTIVE), .utmi_rxerror_o(PHY_RXERROR),
        .utmi_linestate_o(PHY_LINESTATE),
        .usb_dxp_io(usb_dxp_io), .usb_dxn_io(usb_dxn_io),
        .usb_rxdp_i(usb_rxdp_i), .usb_rxdn_i(usb_rxdn_i),
        .usb_pullup_en_o(usb_pullup_en_o),
        .usb_term_dp_io(usb_term_dp_io), .usb_term_dn_io(usb_term_dn_io)
    );
`endif

    usb_uart_config u_usb_uart_config (
`ifdef CONSOLE_USB_DIAG
        .diagnostic_data(usb_diagnostic_data),
`endif
        .PHY_CLKOUT(phy_clk), .RESET_IN(usb_app_reset),
        .setup_active(setup_active), .endpt_sel(endpt_sel),
        .usb_rxval(usb_rxval), .usb_rxact(usb_rxact), .usb_rxdat(usb_rxdat),
        .usb_txact(usb_txact), .usb_txpop(usb_txpop),
        .usb_txpktfin(usb_txpktfin),
        .usb_txdat_len_o(uart_config_txdat_len),
        .endpt0_dat_o(endpt0_dat), .endpt0_send_o(endpt0_send),
        .uart1_en_o(uart_en), .uart1_BAUD_RATE_o(uart_dte_rate),
        .uart1_PARITY_BIT_o(uart_parity_type), .uart1_STOP_BIT_o(uart_char_format),
        .uart1_DATA_BITS_o(uart_data_bits)
    );
    defparam u_usb_uart_config.ENDPT_UART_CONFIG = ENDPT_UART_CONFIG;

`ifdef CONSOLE_USB_DIAG
    // Observe only; the control endpoint remains usable when bulk CDC stalls.
    reg [31:0] diag_uart,diag_out,diag_delivered,diag_rxerror,diag_packets;
    reg [15:0] diag_pop,diag_ack;
    reg [31:0] diag_status;
    // Slow board state, observed through two registers in the USB domain.
    // These bits never control resets or data flow. Keep them live on EP0,
    // including when the CPU cannot answer any bulk command.
    reg [3:0] diag_board_meta,diag_board_sync;
    always @(posedge phy_clk or posedge usb_app_reset)begin
        if(usb_app_reset)begin diag_board_meta<=0;diag_board_sync<=0;end
        else begin
            diag_board_meta<={pll_ae350_lock,soc_dbg[2:0]};
            diag_board_sync<=diag_board_meta;
        end
    end
    reg [7:0] diag_last_uart,diag_last_out,diag_last_delivered;
    wire [31:0] fifo_diagnostic;
    wire [255:0] usb_tx_packet_history;
    usb_packet_trace #(.INPUT_PIPELINE(1)
`ifdef CONSOLE_USB_CAPTURE_FIRST
        ,.CAPTURE_FIRST(1)
`endif
        ) u_usb_packet_trace(.clk(phy_clk),.reset(usb_app_reset),
        .new_packet(endpt_sel==2 && !usb_txpktfin && fifo_diagnostic[24] && !fifo_diagnostic[27]),
        .valid(PHY_TXVALID),.ready(PHY_TXREADY),.data(PHY_DATAOUT),
        .endpoint(endpt_sel),.cork(usb_txcork),.active(usb_txact),
        .length(usb_txdat_len),.history(usb_tx_packet_history),
        .rx_active(PHY_RXACTIVE),.rx_valid(PHY_RXVALID),.rx_error(PHY_RXERROR),
        .rx_data(PHY_DATAIN),.packet_ack(usb_txpktfin),.fifo_pending(fifo_diagnostic[27]));
    wire [511:0] usb_diagnostic_data={usb_tx_packet_history,diag_packets,diag_rxerror,
        8'hd1,diag_last_delivered,diag_last_out,diag_last_uart,
        diag_board_sync,diag_status[27:0],diag_ack,diag_pop,diag_delivered,diag_out,diag_uart};
    always @(posedge phy_clk or posedge usb_app_reset)begin
        if(usb_app_reset)begin
            diag_uart<=0;diag_out<=0;diag_delivered<=0;diag_rxerror<=0;diag_packets<=0;
            diag_pop<=0;diag_ack<=0;diag_status<=0;
            diag_last_uart<=0;diag_last_out<=0;diag_last_delivered<=0;
        end else begin
            if(uart_rx_data_val)begin diag_uart<=diag_uart+1'b1;diag_last_uart<=uart_rx_data;end
            if(ep2_rx_dval)begin diag_delivered<=diag_delivered+1'b1;diag_last_delivered<=ep2_rx_data;end
            if(PHY_RXERROR)diag_rxerror<=diag_rxerror+1'b1;
            if(endpt_sel==2)begin
                diag_status<=fifo_diagnostic;
                if(usb_rxval)begin diag_out<=diag_out+1'b1;diag_last_out<=usb_rxdat;end
                if(usb_rxpktval)diag_packets<=diag_packets+1'b1;
                if(usb_txpop)diag_pop<=diag_pop+1'b1;
                if(usb_txpktfin)diag_ack<=diag_ack+1'b1;
            end
        end
    end
`endif

    // ====================== AE350 : PLLs + SoC + DDR3 (socle analyseur) ======================
    wire        core_clk, ahb_clk, apb_clk, rtc_clk, bus80_clk, pll_ae350_lock;  // horloges du SoC (PLL AE350)
    wire        ddr_init;               // 1 : calibration DDR3 terminée (sortie du socle)
    wire        ae350_tx, ae350_rx;     // console UART2 du AE350
    wire ddr3_pll_lock, ddr3_memory_clk, ddr3_clk_in, ddr3_stop, ddr3_init_completed;
    wire        ae350_rstn, ddr3_rstn;
    wire [3:0] soc_dbg;
    wire [7:0]  soc_ahb_dbg;
    wire [15:0] soc_ddr_dbg;
    wire [63:0] ev_data_unused; wire ev_ready_unused, evin_valid_unused;
    wire [31:0] evin_data_unused;
    wire [63:0] rr_data_unused; wire rr_valid_unused;
    // PLL système du AE350 (socle analyseur : lock + init_clk + PLL_INIT) :
    // clkout0 = 80 MHz (bus AHB/APB), clkout1 = core 800 MHz, clkout4 = RTC 10 MHz
    Gowin_PLL_AE350 u_pll_ae350 (
        .lock    (pll_ae350_lock),
        .clkin   (clk),
        .init_clk (clk),
        .clkout0 (bus80_clk), .clkout1 (core_clk), .clkout2 (), .clkout3 (), .clkout4 (rtc_clk),
        .enclk0  (1'b1), .enclk1 (1'b1), .enclk2 (1'b1), .enclk3 (1'b1), .enclk4 (1'b1)
    );
    // ahb_clk/apb_clk : DÉJÀ déclarés ligne 232 (wire) : NE PAS redéclarer ici !
    // (EX2830 : « Second declaration of 'ahb_clk' is ignored » : le wire local était ignoré,
    //  l'entrée AHB_CLK du SoC restait non câblée → bus APB mort → CPU figé au 1er accès APB.)
    assign ahb_clk = bus80_clk;
    assign apb_clk = ahb_clk;   // APB = net de l'AHB (1:1 exigé par le SoC, en-tête du socle)
    // Reset du CPU : attend le LOCK de la PLL AE350 (schéma de l'analyseur : rst = sync ~lock)
    reg [1:0] ae350_rst_sync = 2'b11;
    always @(posedge bus80_clk) ae350_rst_sync <= {ae350_rst_sync[0], ~pll_ae350_lock};
    wire ae350_por_n = ~ae350_rst_sync[1];

    // SoC AE350 + DDR3 standalone + pont Sipeed (socle analyseur, validé V3)
    wire core_wfi_w;                 // CORE0_WFI_MODE du cœur (preuve de vie sans bus)
    ae350_soc u_soc (
        .clk50(clk),
        .rst_key_n(ae350_por_n),
        .core_clk(core_clk), .ahb_clk(ahb_clk), .apb_clk(apb_clk), .rtc_clk(rtc_clk),
        .ddr_bank(ddr_bank), .ddr_cs(ddr_cs), .ddr_ras(ddr_ras), .ddr_cas(ddr_cas), .ddr_we(ddr_we),
        .ddr_ck(ddr_ck), .ddr_ck_n(ddr_ck_n), .ddr_cke(ddr_cke), .ddr_reset_n(ddr_reset_n), .ddr_odt(ddr_odt),
        .ddr_addr(ddr_addr), .ddr_dm(ddr_dm), .ddr_dq(ddr_dq), .ddr_dqs(ddr_dqs), .ddr_dqs_n(ddr_dqs_n),
        .tck(ae350_tck), .tms(ae350_tms), .tdi(ae350_tdi), .tdo(ae350_tdo),
        .uart2_tx(ae350_tx), .uart2_rx(ae350_rx), .ddr_init(ddr_init), .dbg(soc_dbg),
        .ahb_dbg(soc_ahb_dbg), .ddr_dbg(soc_ddr_dbg), .core_wfi_dbg(core_wfi_w),
        // Legacy acquisition inputs are inactive; video uses its own DDR port.
        .ev_clk(clk), .ev_valid(1'b0), .ev_data(64'd0),
        .evin_valid(), .evin_data(), .evin_ready(1'b0),
        .rr_valid(), .rr_data(), .rr_ready(1'b0),
        .acq_v3(1'b0), .acq_start(1'b0), .acq_run(1'b0), .acq_div(8'd0), .acq_mask(16'hFFFF),
        .acq_now(32'd0),
        .vid_hclk(vid_hclk), .vid_hrstn(vid_hrstn), .vid_hsel(vid_hsel), .vid_hwrite(vid_hwrite),
        .vid_haddr(vid_haddr), .vid_hwdata(vid_hwdata), .vid_htrans(vid_htrans),
        .vid_hrdata(vid_hrdata), .vid_hready(vid_hready),
        .gpu_clk(gpu_clk), .gpu_valid(gpu_valid), .gpu_addr(gpu_addr), .gpu_ready(gpu_ready),
        .gpu_data(gpu_data), .gpu_data_valid(gpu_data_valid),
        .blit_valid(blit_valid), .blit_write(blit_write), .blit_addr(blit_addr),
        .blit_wr_data(blit_wr_data), .blit_wr_mask(blit_wr_mask), .blit_ready(blit_ready),
        .blit_rd_data(blit_rd_data), .blit_rd_valid(blit_rd_valid)
    );
    // LED4 = WFI du cœur : si le CPU exécute la boucle wfi, le signal monte → LED s'allume
    assign led[4] = ~core_wfi_w;

    // ====================== pont UART2 (AE350) ↔ CDC EP2 ===================
    uart2_to_ep2 u_pont (
        .phy_clk          (phy_clk),
        .reset            (usb_app_reset),
        .uart2_txd        (ae350_tx),
        .uart2_rxd        (ae350_rx),
        .uart_rx_data_val (uart_rx_data_val),
        .uart_rx_data     (uart_rx_data),
        .ep2_rx_dval      (ep2_rx_dval),
        .ep2_rx_data      (ep2_rx_data),
        .ep2_rx_rdy       (ep2_rx_rdy)
    );

endmodule
`default_nettype wire
