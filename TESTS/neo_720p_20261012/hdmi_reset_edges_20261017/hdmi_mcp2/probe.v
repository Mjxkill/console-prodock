module probe(input wire clk, reset_async,
        output wire tmds_clk_p,tmds_clk_n,
        output wire [2:0] tmds_d_p,tmds_d_n);
wire pixel_clk,clk5x_raw,clk5x,pixel_lock;
video_pll u_video_pll(.lock(pixel_lock),.clkout0(clk5x_raw),.clkout2(pixel_clk),
 .clkout1(),.clkout3(),.clkout4(),.clkin(clk),.reset(1'b0),
 .icpsel(6'd0),.lpfres(3'd0),.lpfcap(2'd0),
 .enclk0(1'b1),.enclk1(1'b0),.enclk2(1'b1),.enclk3(1'b0),.enclk4(1'b0));
DHCE u_video_fast(.CLKIN(clk5x_raw),.CLKOUT(clk5x),.CEN(1'b0));
reg [7:0] data=0;
always @(posedge pixel_clk) data<=data+1'b1;
hdmi_out u_hdmi(.pclk(pixel_clk),.clk5x(clk5x),.rst(reset_async || !pixel_lock),
 .de(1'b1),.hs(1'b0),.vs(1'b0),.r(data),.g(~data),.b(data),
 .tmds_clk_p(tmds_clk_p),.tmds_clk_n(tmds_clk_n),
 .tmds_d_p(tmds_d_p),.tmds_d_n(tmds_d_n));
endmodule
