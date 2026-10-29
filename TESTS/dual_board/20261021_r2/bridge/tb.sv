`timescale 1ns/1ps
module tb;
reg hclk=0,hresetn=0,m_hsel=0,m_hwrite=0,s0_hready=0,s1_hready=0;
reg[31:0] m_haddr=0,m_hwdata=0,s0_hrdata=0,s1_hrdata=0;
reg[1:0] m_htrans=0;
wire[31:0] m_hrdata,s_haddr,s_hwdata;
wire m_hready,s_hwrite;wire[1:0]s_hsel,s_htrans;
wire [31:0] ref_m_hrdata;
wire [0:0] ref_m_hready;
wire [1:0] ref_s_hsel;
wire [1:0] ref_s_htrans;
wire [0:0] ref_s_hwrite;
wire [31:0] ref_s_haddr;
wire [31:0] ref_s_hwdata;
ahb_exts_bridge dut(.hclk(hclk),.hresetn(hresetn),.m_hsel(m_hsel),.m_haddr(m_haddr),.m_htrans(m_htrans),.m_hwrite(m_hwrite),.m_hwdata(m_hwdata),.s0_hrdata(s0_hrdata),.s0_hready(s0_hready),.s1_hrdata(s1_hrdata),.s1_hready(s1_hready),.m_hrdata(m_hrdata),.m_hready(m_hready),.s_hsel(s_hsel),.s_htrans(s_htrans),.s_hwrite(s_hwrite),.s_haddr(s_haddr),.s_hwdata(s_hwdata));
bridge_reference ref_dut(.hclk(hclk),.hresetn(hresetn),.m_hsel(m_hsel),.m_haddr(m_haddr),.m_htrans(m_htrans),.m_hwrite(m_hwrite),.m_hwdata(m_hwdata),.s0_hrdata(s0_hrdata),.s0_hready(s0_hready),.s1_hrdata(s1_hrdata),.s1_hready(s1_hready),.m_hrdata(ref_m_hrdata),.m_hready(ref_m_hready),.s_hsel(ref_s_hsel),.s_htrans(ref_s_htrans),.s_hwrite(ref_s_hwrite),.s_haddr(ref_s_haddr),.s_hwdata(ref_s_hwdata));

always #6.25 hclk=~hclk;
integer cycles=0,accepted=0,issued=0,cancelled=0;
reg pending=0,expect_issue=0,expected_wr=0;
reg[31:0] expected_addr=0,expected_data=0;
always @(posedge hclk)begin
 if(!hresetn)begin
  if(pending)cancelled=cancelled+1;
  pending<=0;expect_issue<=0;
 end else begin
  expect_issue<=pending;
  if(pending)expected_data<=m_hwdata;
  pending<=m_hready && m_hsel && m_htrans[1];
  if(m_hready && m_hsel && m_htrans[1])begin
   expected_addr<=m_haddr;expected_wr<=m_hwrite;accepted=accepted+1;
  end
 end
end
always @(negedge hclk)begin
 if({m_hready,s_hsel,s_htrans,s_hwrite,s_haddr,s_hwdata}!=={ref_m_hready,ref_s_hsel,ref_s_htrans,ref_s_hwrite,ref_s_haddr,ref_s_hwdata})$fatal(1,"Bridge output/cycle mismatch at %0d",cycles);
 if(m_hready && m_hrdata!==ref_m_hrdata)$fatal(1,"Completed read data mismatch at %0d",cycles);
 if(expect_issue)begin
  if(s_hsel!==(expected_addr[24]?2'b10:2'b01) || s_htrans!==2'b10 ||
     s_haddr!==expected_addr || s_hwrite!==expected_wr || s_hwdata!==expected_data)
   $fatal(1,"Accepted payload mismatch at %0d",cycles);
  issued=issued+1;
 end else if(s_hsel!=0)$fatal(1,"Unaccepted request replayed");
end
initial begin
 repeat(4)@(negedge hclk);
 for(integer i=0;i<250000;i=i+1)begin
  #1;hresetn=(i%997!=0);m_hsel=$urandom_range(0,3)!=0;
  m_htrans=$urandom_range(0,3);m_hwrite=$urandom_range(0,1);
  m_haddr=$urandom;m_hwdata=$urandom;
  s0_hrdata=$urandom;s1_hrdata=$urandom;
  s0_hready=$urandom_range(0,7)==0;s1_hready=$urandom_range(0,3)==0;
  cycles=cycles+1;@(negedge hclk);
 end
 #1;hresetn=0;repeat(4)@(negedge hclk);
 #1;if(accepted!=issued+cancelled)$fatal(1,"Request accounting %0d/%0d/%0d",accepted,issued,cancelled);
 $display("PASS: %0d cycles, %0d accepted, %0d issued, %0d cancelled before issue by reset; controls and valid data exact",cycles,accepted,issued,cancelled);
 $finish;
end
endmodule
