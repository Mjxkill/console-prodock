// Export officiel du contrôleur HS3.3 exact avec ROM descripteur réelle.
// Réduit uniquement le nombre d'I/O du projet d'export ; pas de logique CDC ici.
module USB_HS_Controller_Model(
 input phy_clk,RESET,
 input [7:0] usb_txdat,input endpt0_send,input [11:0] usb_txdat_len,
 input usb_txcork,input usb_rxrdy,input [7:0] inf_alter_i,
 output usb_busreset,usb_highspeed,usb_suspend,usb_online,usb_sof,
 output usb_txpop,usb_txact,usb_txpktfin,
 output [7:0] usb_rxdat,output usb_rxval,usb_rxact,usb_rxpktval,setup_active,
 output [3:0] endpt_sel,
 output [7:0] inf_alter_o,inf_sel_o,output inf_set_o,
 output [7:0] PHY_DATAOUT,output PHY_TXVALID,input PHY_TXREADY,
 input [7:0] PHY_DATAIN,input PHY_RXACTIVE,PHY_RXVALID,PHY_RXERROR,
 input [1:0] PHY_LINESTATE,output [1:0] PHY_OPMODE,PHY_XCVRSELECT,
 output PHY_TERMSELECT,PHY_RESET
);
 localparam ENDPT_UART_CONFIG=4'd0;
 localparam USB_HS_SUPPORT=1;
    wire [15:0] DESC_DEV_ADDR, DESC_DEV_LEN, DESC_QUAL_ADDR, DESC_QUAL_LEN,
                DESC_FSCFG_ADDR, DESC_FSCFG_LEN, DESC_HSCFG_ADDR, DESC_HSCFG_LEN,
                DESC_OSCFG_ADDR, DESC_BOS_ADDR, DESC_BOS_LEN,
                DESC_STRLANG_ADDR, DESC_STRVENDOR_ADDR, DESC_STRVENDOR_LEN,
                DESC_STRPRODUCT_ADDR, DESC_STRPRODUCT_LEN,
                DESC_STRSERIAL_ADDR, DESC_STRSERIAL_LEN;
    wire [7:0]  DESCROM_RDAT, DESC_INDEX, DESC_TYPE;
    wire [15:0] DESCROM_RADDR;
    wire        DESCROM_HAVE_STRINGS;
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

    USB_Device_Controller_Top controller (
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
        .desc_bos_addr_i(16'd0), .desc_bos_len_i(16'd0),
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


endmodule
