`timescale 1ns/1ps
module neo_gamepads_tb;
    reg clk=0;
    always #6.25 clk=~clk;
    reg rst=1,hsel=0,hwrite=0;
    reg [1:0] htrans=0;
    reg [31:0] haddr=0;
    wire [31:0] hrdata;
    wire [1:0] dp,dm;
    neo_gamepads u(.clk(clk),.resetn(!rst),.hsel(hsel),.hwrite(hwrite),
        .htrans(htrans),.haddr(haddr),.hrdata(hrdata),.hready(),.dp(dp),.dm(dm));
    reg p0_attach=0,p0_dev_drive=0,p0_dev_dp=0,p0_dev_dm=1;
    wire p0_dp=dp[0],p0_dm=dm[0];
    pulldown(dp[0]);pullup(dm[0]);
    assign dp[0]=p0_dev_drive ? p0_dev_dp:1'bz;
    assign dm[0]=p0_dev_drive ? p0_dev_dm:1'bz;
    wire p0_host_oe=u.g_port[0].u_pad.u_host.usb_oe;
    wire [31:0] p0_status=u.status[0],p0_identity=u.identity[0],p0_report_count=u.reports[0];
    reg p1_attach=0,p1_dev_drive=0,p1_dev_dp=0,p1_dev_dm=1;
    wire p1_dp=dp[1],p1_dm=dm[1];
    pulldown(dp[1]);pullup(dm[1]);
    assign dp[1]=p1_dev_drive ? p1_dev_dp:1'bz;
    assign dm[1]=p1_dev_drive ? p1_dev_dm:1'bz;
    wire p1_host_oe=u.g_port[1].u_pad.u_host.usb_oe;
    wire [31:0] p1_status=u.status[1],p1_identity=u.identity[1],p1_report_count=u.reports[1];
endmodule
