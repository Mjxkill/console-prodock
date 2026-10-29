// Tang Mega Neo / Console 138K, PG484C: shared console GPU in DDR3, HDMI 720p.
// AE350 800 MHz; AHB/APB 80 MHz; DDR UI 75 MHz; pixel 74.375 MHz.
`define CONSOLE_GPU
`define CONSOLE_USB_DIAG
`default_nettype none
module console_neo (
    input wire clk, uart_rx,
    inout wire [1:0] gamepad_dp,gamepad_dm,
    inout wire usb_dxp_io,usb_dxn_io,usb_term_dp_io,usb_term_dn_io,
    input wire usb_rxdp_i,usb_rxdn_i,
    output wire usb_pullup_en_o,
    output wire uart_tx, led_n, ae350_tx,
    output wire tmds_clk_p,tmds_clk_n,
    output wire [2:0] tmds_d_p,tmds_d_n,
    input wire ae350_tck,ae350_tms,ae350_tdi,
    output wire ae350_tdo,
    output wire [2:0] ddr_bank,
    output wire ddr_cs,ddr_ras,ddr_cas,ddr_we,ddr_ck,ddr_ck_n,ddr_cke,ddr_reset_n,ddr_odt,
    output wire [15:0] ddr_addr,
    output wire [3:0] ddr_dm,
    inout wire [31:0] ddr_dq,
    inout wire [3:0] ddr_dqs,ddr_dqs_n,
    output wire sd_clk,sd_cmd,sd_d3,
    input wire sd_d0
);
    wire pixel_clk,clk5x_raw,clk5x,pixel_lock;
    video_pll u_video_pll(.lock(pixel_lock),.clkout0(clk5x_raw),.clkout2(pixel_clk),
        .clkout1(),.clkout3(),.clkout4(),.clkin(clk),.reset(1'b0),
        .icpsel(6'd0),.lpfres(3'd0),.lpfcap(2'd0),
        .enclk0(1'b1),.enclk1(1'b0),.enclk2(1'b1),.enclk3(1'b0),.enclk4(1'b0));
    DHCE u_video_fast(.CLKIN(clk5x_raw),.CLKOUT(clk5x),.CEN(1'b0));
    reg [2:0] pixel_up=0;
    always @(posedge pixel_clk or negedge pixel_lock)
        if(!pixel_lock)pixel_up<=0;else pixel_up<={pixel_up[1:0],1'b1};
    wire vid_hclk,vid_hrstn,vid_hsel,vid_hwrite,vid_hready;
    wire [31:0] vid_haddr,vid_hwdata,vid_hrdata;
    wire [1:0] vid_htrans;
    wire gpu_clk,gpu_valid,gpu_ready,gpu_data_valid;
    wire [28:0] gpu_addr;
    wire [255:0] gpu_data;
    wire blit_valid,blit_write,blit_ready,blit_rd_valid;
    wire [28:0] blit_addr;
    wire [255:0] blit_wr_data,blit_rd_data;
    wire [31:0] blit_wr_mask;
    wire bus_hsel,bus_hwrite,bus_hready;
    wire [31:0] bus_haddr,bus_hwdata,bus_hrdata;
    wire [1:0] bus_htrans;
    video_bus_stage u_video_bus(.clk(vid_hclk),.resetn(vid_hrstn),
        .s_hsel(vid_hsel),.s_hwrite(vid_hwrite),.s_htrans(vid_htrans),
        .s_haddr(vid_haddr),.s_hwdata(vid_hwdata),.s_hready(vid_hready),.s_hrdata(vid_hrdata),
        .m_hsel(bus_hsel),.m_hwrite(bus_hwrite),.m_htrans(bus_htrans),
        .m_haddr(bus_haddr),.m_hwdata(bus_hwdata),.m_hready(bus_hready),.m_hrdata(bus_hrdata));
    wire [31:0] scan_hrdata,blit_hrdata;
    wire scan_hready,blit_hready;
    wire [31:0] usb_trace_hrdata,usb_msc_hrdata;
    wire usb_trace_hready,usb_msc_hready;
    reg [2:0] selected=0;
    always @(posedge vid_hclk)begin
        if(!vid_hrstn)selected<=0;
        else if(bus_hsel)selected<=bus_haddr[14:12];
    end
    // Same USB trace/MSC ABI as Pro Dock, with registered slave responses.
    assign bus_hrdata=selected[2] ? (selected[0] ? debug_hrdata:pad_hrdata):selected[1] ? (selected[0] ? usb_msc_hrdata:usb_trace_hrdata):
                                  (selected[0] ? blit_hrdata:scan_hrdata);
    assign bus_hready=selected[2] ? (selected[0] ? debug_hready:1'b1):selected[1] ? (selected[0] ? usb_msc_hready:usb_trace_hready):
                                  (selected[0] ? blit_hready:scan_hready);
    wire [31:0] debug_hrdata;
    wire debug_hready;
    wire [255:0] gpu_debug_state;
    wire gpu_debug_accept;
    neo_gpu_debug u_gpu_debug(.hclk(vid_hclk),.resetn(vid_hrstn),.mem_clk(gpu_clk),
        .hsel(bus_hsel && bus_haddr[14:12]==5),.hwrite(bus_hwrite),
        .htrans(bus_htrans),.haddr(bus_haddr),.hwdata(bus_hwdata),.hrdata(debug_hrdata),.hready(debug_hready),
        .host_accept(gpu_debug_accept),.live(gpu_debug_state));
    wire [31:0] pad_hrdata;
    neo_gamepads u_gamepads(.clk(vid_hclk),.resetn(vid_hrstn),
        .hsel(bus_hsel && bus_haddr[14:12]==4),.hwrite(bus_hwrite),
        .htrans(bus_htrans),.haddr(bus_haddr),.hrdata(pad_hrdata),.hready(),
        .dp(gamepad_dp),.dm(gamepad_dm));
    `include "boards/neo/soft_usb.vh"
    wire de,hs,vs;
    wire [5:0] red,green,blue;
    wire scan_valid,scan_ready;
    wire [28:0] scan_addr;
    neo_scan_queue u_scan_queue(.clk(gpu_clk),.resetn(vid_hrstn),
        .in_valid(scan_valid),.in_addr(scan_addr),.in_ready(scan_ready),
        .out_valid(gpu_valid),.out_addr(gpu_addr),.out_ready(gpu_ready));
    gpu_scanout #(.WIDTH(1280),.HEIGHT(720),.H_TOTAL(1650),.V_TOTAL(750),
        .H_START(260),.V_START(25),.H_SYNC(40),.V_SYNC(5)) u_gpu (
        .hclk(vid_hclk),.hresetn(vid_hrstn),.hsel(bus_hsel && bus_haddr[14:12]==0),.hwrite(bus_hwrite),
        .haddr(bus_haddr),.hwdata(bus_hwdata),.htrans(bus_htrans),.hrdata(scan_hrdata),.hready(scan_hready),
        .pixel_clk(pixel_clk),.mem_clk(gpu_clk),
        .fetch_valid(scan_valid),.fetch_addr(scan_addr),.fetch_ready(scan_ready),
        .fetch_data(gpu_data),.fetch_data_valid(gpu_data_valid),
        .lcd_en(de),.lcd_hs(hs),.lcd_vs(vs),.lcd_r(red),.lcd_g(green),.lcd_b(blue));
    gpu_accel u_accel(.hclk(vid_hclk),.hresetn(vid_hrstn),
        .hsel(bus_hsel && bus_haddr[14:12]==1),.hwrite(bus_hwrite),
        .haddr(bus_haddr),.hwdata(bus_hwdata),.htrans(bus_htrans),.hrdata(blit_hrdata),.hready(blit_hready),
        .mem_clk(gpu_clk),.valid(blit_valid),.write(blit_write),.addr(blit_addr),
        .wr_data(blit_wr_data),.wr_mask(blit_wr_mask),.ready(blit_ready),
        .rd_data(blit_rd_data),.rd_valid(blit_rd_valid),
        .debug_state(gpu_debug_state),.debug_accept(gpu_debug_accept));
    hdmi_out u_hdmi(.pclk(pixel_clk),.clk5x(clk5x),.rst(!pixel_up[2]),
        .de(de),.hs(~hs),.vs(~vs),.r({red,red[5:4]}),.g({green,green[5:4]}),.b({blue,blue[5:4]}),
        .tmds_clk_p(tmds_clk_p),.tmds_clk_n(tmds_clk_n),.tmds_d_p(tmds_d_p),.tmds_d_n(tmds_d_n));
    // ====================== AE350 : PLLs + SoC + DDR3 (socle analyseur) ======================
    wire        core_clk, ahb_clk, apb_clk, rtc_clk, bus80_clk, pll_ae350_lock;  // horloges du SoC (PLL AE350)
    wire        ddr_init;               // 1 : calibration DDR3 terminée (sortie du socle)
    wire        ae350_rx;     // console UART2 du AE350
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
    always @(posedge bus80_clk or negedge pll_ae350_lock)
        if (!pll_ae350_lock) ae350_rst_sync <= 2'b11;
        else ae350_rst_sync <= {ae350_rst_sync[0], 1'b0};
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
        .sd_clk(sd_clk), .sd_cmd(sd_cmd), .sd_miso(sd_d0), .sd_cs_n(sd_d3), .sd_detect(1'b0),
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

    // USB and BL616 input are arbitrated as bytes in the USB 60 MHz domain.
    // Neither serial input is combined electrically or switched mid-frame.
    neo_console_input u_console_input(
        .clk(phy_clk),.reset(usb_app_reset),.debug_rx(uart_rx),
        .usb_valid(ep2_rx_dval),.usb_data(ep2_rx_data),.usb_ready(ep2_rx_rdy),
        .cpu_tx(ae350_tx),.cpu_rx(ae350_rx),
        .cpu_valid(uart_rx_data_val),.cpu_data(uart_rx_data),.overflow());
    // Mirror CPU output on the BL616 relay, also when CDC is in use.
    uart_console_channel #(.FIFO_LOG2(3),.REGISTER_FIFO(1)) u_console_output(
        .clk(bus80_clk),.rst(!ae350_por_n),.rx(ae350_tx),.tx(uart_tx),
        .rx_div(16'd694),.tx_div(16'd40),.overflow(),.diagnostic());
    assign led_n=~ddr_init;
endmodule
`default_nettype wire
