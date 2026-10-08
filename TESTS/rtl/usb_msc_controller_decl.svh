    // Disque USB : port AHB du firmware et ses liaisons vers EP1 de usb_fifo.
    reg hclk = 0;
    always #6.25 hclk = ~hclk;
    wire        msc_flush, msc_tx_dval, msc_rx_rdy, msc_rx_dval, msc_bot_reset;
    wire [7:0]  msc_tx_data, msc_rx_data;
    wire [15:0] msc_tx_committed, msc_tx_sent;
    wire msc_halted, msc_halt_request;
    wire [7:0] controller_dataout;
    reg guard_enable=1;
    usb_msc_guard u_guard (
        .clk(phy_clk),.reset(usb_app_reset || !guard_enable),.bot_reset(msc_bot_reset),.abort_request(msc_halt_request),
        .highspeed(usb_highspeed),
        .endpoint(endpt_sel),.rxact(usb_rxact),.rxval(usb_rxval),.rxpktval(usb_rxpktval),.setup(setup_active),.rxdata(usb_rxdat),
        .txpktfin(usb_txpktfin),.txlen(ep_usb_txlen),
        .utmi_data(controller_dataout),.utmi_valid(PHY_TXVALID),.utmi_ready(PHY_TXREADY),
        .halted(msc_halted),.idle(),.phy_data(PHY_DATAOUT));
    reg         hsel = 0, hwrite = 0;
    reg  [1:0]  htrans = 0;
    reg  [31:0] haddr = 0, hwdata = 0;
    wire [31:0] hrdata;
    wire        hready;
    usb_msc_port u_usb_msc_port (
        .clk(phy_clk), .reset_n(!reset), .bus_reset(usb_busreset), .bot_reset(msc_bot_reset),
        .online(usb_online), .highspeed(usb_highspeed), .ep_flush(msc_flush),
        .ep_halted(msc_halted),.halt_request(msc_halt_request),
        .ep_tx_dval(msc_tx_dval), .ep_tx_data(msc_tx_data),
        .ep_tx_committed(msc_tx_committed), .ep_tx_sent(msc_tx_sent),
        .ep_rx_rdy(msc_rx_rdy), .ep_rx_dval(msc_rx_dval && !msc_halted), .ep_rx_data(msc_rx_data),
        .hclk(hclk), .hsel(hsel), .hwrite(hwrite), .htrans(htrans), .haddr(haddr), .hwdata(hwdata),
        .hrdata(hrdata), .hready(hready));
