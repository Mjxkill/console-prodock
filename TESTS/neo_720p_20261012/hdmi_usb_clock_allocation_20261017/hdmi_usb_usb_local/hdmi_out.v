// hdmi_out.v — sortie HDMI/DVI 720p (ARCHI_V4 § 9.4) : 3 encodeurs TMDS (svo_tmds) + 3 sérialiseurs OSER10 (10:1, pclk / clk5x)
// + 4 paires ELVDS_OBUF (LVCMOS33D, comme l'exemple Sipeed sur GW5AST). Canal 0 (bleu) porte hsync/vsync dans les périodes de
// contrôle. Sous Verilator (pas de primitives Gowin) : les dix bits parallèles sont exposés pour le banc, les paires sont à 0.
`default_nettype none
module hdmi_out (
    input  wire        pclk,
    input  wire        clk5x,
    input  wire        rst,
    input  wire        de, hs, vs,
    input  wire [7:0]  r, g, b,
    output wire        tmds_clk_p, tmds_clk_n,
    output wire [2:0]  tmds_d_p, tmds_d_n
`ifdef VERILATOR
    ,output wire [9:0] enc_r, enc_g, enc_b
`endif
);
    wire [9:0] d0, d1, d2;
    wire [2:0] serializer_reset;
    genvar reset_channel;
    generate for (reset_channel = 0; reset_channel < 3; reset_channel = reset_channel + 1) begin : g_reset
        (* syn_preserve = 1, syn_keep = 1 *) reg [1:0] reset_sync = 2'b11;
        (* syn_preserve = 1, syn_keep = 1 *) reg reset_sync_fall = 1'b1;
        always @(posedge pclk or posedge rst) begin
            if (rst) reset_sync <= 2'b11;
            else reset_sync <= {reset_sync[0], 1'b0};
        end
        always @(negedge pclk or posedge rst) begin
            if (rst) reset_sync_fall <= 1'b1;
            else reset_sync_fall <= reset_sync[1];
        end
        assign serializer_reset[reset_channel] = reset_sync_fall;
    end endgenerate
    svo_tmds enc0 (.clk(pclk), .resetn(~rst), .de(de), .ctrl({vs, hs}), .din(b), .dout(d0));
    svo_tmds enc1 (.clk(pclk), .resetn(~rst), .de(de), .ctrl(2'b00),   .din(g), .dout(d1));
    svo_tmds enc2 (.clk(pclk), .resetn(~rst), .de(de), .ctrl(2'b00),   .din(r), .dout(d2));
`ifdef VERILATOR
    assign enc_r = d2; assign enc_g = d1; assign enc_b = d0;
    assign tmds_clk_p = 1'b0; assign tmds_clk_n = 1'b0; assign tmds_d_p = 3'd0; assign tmds_d_n = 3'd0;
    /* verilator lint_off UNUSEDSIGNAL */
    wire unused = &{1'b0, clk5x};
    /* verilator lint_on UNUSEDSIGNAL */
`else
    wire [2:0] ser;
    wire [9:0] dd [0:2];
    assign dd[0] = d0; assign dd[1] = d1; assign dd[2] = d2;
    genvar k;
    generate for (k = 0; k < 3; k = k + 1) begin : g_ser
        OSER10 u_ser (.Q(ser[k]), .D0(dd[k][0]), .D1(dd[k][1]), .D2(dd[k][2]), .D3(dd[k][3]), .D4(dd[k][4]),
                      .D5(dd[k][5]), .D6(dd[k][6]), .D7(dd[k][7]), .D8(dd[k][8]), .D9(dd[k][9]),
                      .PCLK(pclk), .FCLK(clk5x), .RESET(serializer_reset[k]));
    end endgenerate
    ELVDS_OBUF u_bc (.I(pclk),   .O(tmds_clk_p),  .OB(tmds_clk_n));
    ELVDS_OBUF u_b0 (.I(ser[0]), .O(tmds_d_p[0]), .OB(tmds_d_n[0]));
    ELVDS_OBUF u_b1 (.I(ser[1]), .O(tmds_d_p[1]), .OB(tmds_d_n[1]));
    ELVDS_OBUF u_b2 (.I(ser[2]), .O(tmds_d_p[2]), .OB(tmds_d_n[2]));
`endif
endmodule
`default_nettype wire
