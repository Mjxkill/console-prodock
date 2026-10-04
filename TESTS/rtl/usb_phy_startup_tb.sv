`timescale 1ns/1ps
// Observe the unmodified official PHY. No internal force, no controller, no USB traffic.
module usb_phy_startup_tb;
reg clk60=0, clk960=0, reset=1, locked=0;
tri dp,dn,term_dp,term_dn;
real local_phase_ns=0;
integer epoch=0, samples=0;
real last60=0;
USB2_0_SoftPHY_Top phy (
 .clk_i(clk60),.fclk_i(clk960),.rst_i(reset),.pll_locked_i(locked),
 .utmi_data_out_i(8'h00),.utmi_txvalid_i(1'b0),.utmi_op_mode_i(2'b00),
 .utmi_xcvrselect_i(2'b00),.utmi_termselect_i(1'b0),
 .usb_rxdp_i(1'b0),.usb_rxdn_i(1'b0),
 .usb_dxp_io(dp),.usb_dxn_io(dn),.usb_term_dp_io(term_dp),.usb_term_dn_io(term_dn)
);
wire stop_clock=phy.\usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/u_oser_rst/reset_stop_s2 .Q;
wire calib_reset=phy.\usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/u_oser_rst/reset_calib_s2 .Q;
wire gated_clock=phy.\usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/dhcen_inst .CLKOUT;
wire sclk=phy.\usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/clkdiv_inst .CLKOUT;
wire [2:0] state=phy.\usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/u_oser_rst/Fsm_serdes_rst_ctrl ;
wire [8:0] count=phy.\usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/u_oser_rst/Cnt_serdes_rst_ctrl ;
initial begin : clock60
 real deadline;
 deadline=0;
 forever begin deadline=deadline+1000.0/120.0; #(deadline-$realtime);clk60=~clk60;end
end
initial begin : clock960
 real deadline;
 if($value$plusargs("LOCAL_PHASE_NS=%f",local_phase_ns))begin end
 deadline=local_phase_ns;
 forever begin deadline=deadline+1000.0/1920.0; #(deadline-$realtime);clk960=~clk960;end
end
initial begin
 $display("START local_phase_ns=%0.9f",local_phase_ns);
 #103.3;locked=1;
 #97;reset=0;
 #10800;epoch=1;reset=1;
 #100;reset=0;
 #11000;$display("DONE");$finish;
end
always @(posedge clk60)last60=$realtime;
always @(reset or locked or stop_clock or calib_reset or state)
 $strobe("CONTROL t=%0.6f epoch=%0d reset=%b locked=%b state=%b count=%0d stop=%b calib=%b gated=%b sclk=%b",$realtime,epoch,reset,locked,state,count,stop_clock,calib_reset,gated_clock,sclk);
always @(negedge calib_reset) samples=0;
always @(posedge gated_clock) if(samples==0 && !calib_reset)
 $display("HCLK_FIRST t=%0.6f epoch=%0d stop=%b calib=%b since60=%0.6f",$realtime,epoch,stop_clock,calib_reset,$realtime-last60);
always @(posedge sclk) if(!calib_reset && samples<8)begin
 $display("SCLK t=%0.6f epoch=%0d sample=%0d stop=%b since60=%0.6f",$realtime,epoch,samples,stop_clock,$realtime-last60);
 samples=samples+1;
end
endmodule
