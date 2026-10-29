module probe(input wire clk, output wire led_n,
output wire tmds_clk_p,tmds_clk_n,output wire [2:0] tmds_d_p,tmds_d_n);
wire pixel_clk,clk5x_raw,clk5x,pixel_lock;
video_pll u_video_pll(.lock(pixel_lock),.clkout0(clk5x_raw),.clkout2(),
 .clkout1(),.clkout3(),.clkout4(),.clkin(clk),.reset(1'b0),
 .icpsel(6'd0),.lpfres(3'd0),.lpfcap(2'd0),
 .enclk0(1'b1),.enclk1(1'b0),.enclk2(1'b0),.enclk3(1'b0),.enclk4(1'b0));
DHCE u_video_fast(.CLKIN(clk5x_raw),.CLKOUT(clk5x),.CEN(1'b0));
CLKDIV u_video_div(.CLKOUT(pixel_clk),.HCLKIN(clk5x),.RESETN(pixel_lock),.CALIB(1'b0));
defparam u_video_div.DIV_MODE = "5";
reg [2:0] pixel_up=0;
always @(posedge pixel_clk or negedge pixel_lock)
 if(!pixel_lock)pixel_up<=0;else pixel_up<={pixel_up[1:0],1'b1};
wire de,hs,vs,frame;wire [10:0] x;wire [9:0] y;
wire rst=!pixel_up[2];
video_720p timing(.pclk(pixel_clk),.rst(rst),.de(de),.hs(hs),.vs(vs),.x(x),.y(y),.frame(frame));
wire [2:0] band=x<160 ? 7:x<320 ? 6:x<480 ? 5:x<640 ? 4:x<800 ? 3:x<960 ? 2:x<1120 ? 1:0;
wire border=x<8 || x>=1272 || y<8 || y>=712;
wire [7:0] r={8{border || band[2]}},g={8{border || band[1]}},b={8{border || band[0]}};
hdmi_out u_hdmi(.pclk(pixel_clk),.clk5x(clk5x),.rst(rst),.de(de),.hs(hs),.vs(vs),.r(r),.g(g),.b(b),
 .tmds_clk_p(tmds_clk_p),.tmds_clk_n(tmds_clk_n),.tmds_d_p(tmds_d_p),.tmds_d_n(tmds_d_n));
assign led_n=!pixel_up[2];
endmodule
