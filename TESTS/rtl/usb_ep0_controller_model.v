// Assemblage d'export officiel : contrôleur fournisseur intact et ROM réelle.
// Les ports publics sont réduits pour tenir dans les I/O du FPGA d'export.
module USB_EP0_Controller_Model #(
    parameter HS_SUPPORT = 0
)(
    input clk, input reset, input rxready,
    input [7:0] rxdata, input rxvalid, input rxactive, input rxerror,
    input [1:0] linestate, input txready,
    output [7:0] txdata, output txvalid,
    output [1:0] opmode, output [1:0] xcvrselect,
    output termselect, output phyreset,
    output busreset, output highspeed, output online, output suspend,
    output setup, output [3:0] endpoint,
    output app_rxvalid, output app_rxactive, output app_rxpktvalid,
    output [7:0] app_rxdata, output app_txactive, output app_txpop,
    output app_txfinish,
    output [15:0] descaddr, output [7:0] descdata,
    output [7:0] desctype, output [7:0] descindex
);
    wire [15:0] devaddr, devlen, qualaddr, quallen, fsaddr, fslen,
                hsaddr, hslen, osaddr, langaddr, vendoraddr, vendorlen,
                productaddr, productlen, serialaddr, seriallen;
    wire strings;
    usb_desc #(.SERIALSTR("11252024"), .SERIALSTR_LEN(8),
        .VENDORSTR("Sipeed"), .VENDORSTR_LEN(6),
        .PRODUCTSTR("Tang USB2Serial"), .PRODUCTSTR_LEN(15),
        .VENDORID(16'h359f), .PRODUCTID(16'h2010), .VERSIONBCD(16'h0112),
        .HSSUPPORT(HS_SUPPORT), .SELFPOWERED(0)) descriptor (
        .CLK(clk), .RESET(reset), .i_pid(16'd0), .i_vid(16'd0),
        .i_descrom_raddr(descaddr), .o_descrom_rdat(descdata),
        .o_desc_dev_addr(devaddr), .o_desc_dev_len(devlen),
        .o_desc_qual_addr(qualaddr), .o_desc_qual_len(quallen),
        .o_desc_fscfg_addr(fsaddr), .o_desc_fscfg_len(fslen),
        .o_desc_hscfg_addr(hsaddr), .o_desc_hscfg_len(hslen),
        .o_desc_oscfg_addr(osaddr), .o_desc_strlang_addr(langaddr),
        .o_desc_strvendor_addr(vendoraddr), .o_desc_strvendor_len(vendorlen),
        .o_desc_strproduct_addr(productaddr), .o_desc_strproduct_len(productlen),
        .o_desc_strserial_addr(serialaddr), .o_desc_strserial_len(seriallen),
        .o_descrom_have_strings(strings));
    USB_Device_Controller_Top controller (
        .clk_i(clk), .reset_i(reset), .usbrst_o(busreset),
        .highspeed_o(highspeed), .suspend_o(suspend), .online_o(online),
        // GET_DESCRIPTOR interne : txval=0, txcork=0 ; longueur CDC héritée7.
        .txdat_i(8'd0), .txval_i(1'b0), .txdat_len_i(12'd7),
        .txiso_pid_i(4'b0011), .txcork_i(1'b0), .txpop_o(app_txpop),
        .txact_o(app_txactive), .txpktfin_o(app_txfinish),
        .rxdat_o(app_rxdata), .rxval_o(app_rxvalid), .rxrdy_i(rxready),
        .rxact_o(app_rxactive), .rxpktval_o(app_rxpktvalid),
        .setup_o(setup), .endpt_o(endpoint), .sof_o(),
        .inf_alter_i(8'd0), .inf_alter_o(), .inf_sel_o(), .inf_set_o(),
        .descrom_raddr_o(descaddr), .desc_index_o(descindex), .desc_type_o(desctype),
        .descrom_rdata_i(descdata), .desc_dev_addr_i(devaddr), .desc_dev_len_i(devlen),
        .desc_qual_addr_i(qualaddr), .desc_qual_len_i(quallen),
        .desc_fscfg_addr_i(fsaddr), .desc_fscfg_len_i(fslen),
        .desc_hscfg_addr_i(hsaddr), .desc_hscfg_len_i(hslen),
        .desc_oscfg_addr_i(osaddr), .desc_hidrpt_addr_i(16'd0), .desc_hidrpt_len_i(16'd0),
        .desc_bos_addr_i(16'd0), .desc_bos_len_i(16'd0),
        .desc_strlang_addr_i(langaddr), .desc_strvendor_addr_i(vendoraddr),
        .desc_strvendor_len_i(vendorlen), .desc_strproduct_addr_i(productaddr),
        .desc_strproduct_len_i(productlen), .desc_strserial_addr_i(serialaddr),
        .desc_strserial_len_i(seriallen), .desc_have_strings_i(strings),
        .utmi_dataout_o(txdata), .utmi_txvalid_o(txvalid), .utmi_txready_i(txready),
        .utmi_datain_i(rxdata), .utmi_rxactive_i(rxactive), .utmi_rxvalid_i(rxvalid),
        .utmi_rxerror_i(rxerror), .utmi_linestate_i(linestate),
        .utmi_opmode_o(opmode), .utmi_xcvrselect_o(xcvrselect),
        .utmi_termselect_o(termselect), .utmi_reset_o(phyreset));
endmodule
