`timescale 1ns/1ps
module usb_idle_trace_protocol_tb;
 real hp=6.25,up=8.333333,phase=0.317;
 reg hclk=0,clk=0,h_run=1,u_run=1,reset_n=0;
 initial begin
  if($value$plusargs("hp=%f",hp))begin end
  forever begin #(hp);if(h_run)hclk=~hclk;end
 end
 initial begin
  if($value$plusargs("up=%f",up))begin end
  if($value$plusargs("phase=%f",phase))begin end
  #(phase);
  forever begin #(up);if(u_run)clk=~clk;end
 end
 reg bus_reset=0,sof=0,rx_active=0,rx_valid=0,rx_error=0,tx_valid=0,tx_ready=0,cork=1;
 reg [7:0] rx_data=0,tx_data=0;
 reg [3:0] endpoint=3;
 reg hsel=0,hwrite=0;
 reg [1:0] htrans=0;
 reg [31:0] haddr=0,hwdata=0;
 wire [31:0] hrdata;
 wire hready;
 wire read_pending_net,reset_merge_net;
 wire m_hsel,m_hwrite,m_hready;
 wire [1:0] m_htrans;
 wire [31:0] m_haddr,m_hwdata,m_hrdata,trace_hrdata;
 reg [2:0] selected=0;
 always @(posedge hclk)begin
  if(!reset_n)selected<=0;
  else if(m_hsel)selected<=m_haddr[14:12];
 end
 assign m_hrdata=selected==2 ? trace_hrdata:32'hdeadbeef;
 assign m_hready=selected==2 ? !read_pending_net:1'b1;
 video_bus_stage stage(.clk(hclk),.resetn(reset_n),.s_hsel(hsel),.s_hwrite(hwrite),.s_htrans(htrans),
  .s_haddr(32'he9002000|haddr),.s_hwdata(hwdata),.s_hready(hready),.s_hrdata(hrdata),
  .m_hsel(m_hsel),.m_hwrite(m_hwrite),.m_htrans(m_htrans),.m_haddr(m_haddr),.m_hwdata(m_hwdata),.m_hready(m_hready),.m_hrdata(m_hrdata));
 GSR GSR(.GSRI(1'b1));
 usb_idle_trace dut(
  .vid_hclk(hclk),.phy_clk(clk),.PHY_RESET(bus_reset),.usb_sof(sof),
  .PHY_RXACTIVE(rx_active),.PHY_RXVALID(rx_valid),.PHY_RXERROR(rx_error),
  .PHY_TXVALID(tx_valid),.PHY_TXREADY(tx_ready),.n949_8(cork),.n960_9(endpoint==0),
  .bus_hwrite(m_hwrite),.rst_usb(1'b0),.vid_hrstn(reset_n),
  .bus_haddr_0(m_haddr[0]),.bus_haddr_1(m_haddr[1]),.bus_haddr_2(m_haddr[2]),.bus_haddr_3(m_haddr[3]),
  .bus_haddr_4(m_haddr[4]),.bus_haddr_5(m_haddr[5]),.bus_haddr_6(m_haddr[6]),.bus_haddr_7(m_haddr[7]),
  .bus_haddr_12(m_haddr[12]),.bus_haddr_13(m_haddr[13]),.bus_haddr_14(m_haddr[14]),
  .PHY_DATAIN(rx_data),.PHY_DATAOUT(tx_data),.endpt_sel(endpoint),
  .bus_htrans(m_htrans[1]&&m_hsel),.bus_hwdata(m_hwdata),.read_pending(read_pending_net),
  .n6_5(reset_merge_net),.usb_trace_hrdata(trace_hrdata));
 reg [31:0] words[0:31];
 task bus_write(input [31:0] addr,input [31:0] value);
  @(negedge hclk);haddr=addr;hwrite=1;hsel=1;htrans=2;
  @(posedge hclk);while(!hready)@(posedge hclk);
  @(negedge hclk);hsel=0;htrans=0;hwdata=value;
  @(posedge hclk);while(!hready)@(posedge hclk);
  @(negedge hclk);hwrite=0;
 endtask
 task bus_read(input [31:0] addr,output [31:0] value);
  @(negedge hclk);haddr=addr;hwrite=0;hsel=1;htrans=2;
  @(posedge hclk);while(!hready)@(posedge hclk);
  @(negedge hclk);hsel=0;htrans=0;
  @(posedge hclk);while(!hready)@(posedge hclk);
  value=hrdata;
  @(negedge hclk);
 endtask
 task wait_reply;
  reg [31:0] s;integer n;
  n=0;s=1;
  while(s[0])begin
   bus_read(4,s);n=n+1;if(n>200)$fatal(1,"snapshot timeout");
  end
  if(s[1])$fatal(1,"unexpected rejected command");
 endtask
 task capture;
  bus_write(12,2);wait_reply();
  for(integer i=0;i<32;i=i+1)bus_read(32'h40+32'(i*4),words[i]);
  if(words[0]!=32'h55544e41 || words[1]!=1)$fatal(1,"incoherent header");
 endtask
 task arm;
  bus_write(12,32'h0701);wait_reply();
 endtask
 // Independent token generation via the shift-left USB CRC-5 polynomial.
 function [4:0] host_crc(input [10:0] data);
  reg [4:0] c;reg feedback;
  c=31;
  for(integer k=0;k<11;k=k+1)begin
   feedback=c[4]^data[k];c=c<<1;if(feedback)c=c^5'h05;
  end
  return ~{c[0],c[1],c[2],c[3],c[4]};
 endfunction
 task token(input [3:0] ep,input bit bad_crc=0,input bit bad_rx=0,input [6:0] addr=7);
  reg [10:0] t;reg [4:0] c;
  t={ep,addr};c=host_crc(t);if(bad_crc)c=c^1;
  @(negedge clk);rx_active=1;rx_valid=1;rx_data=8'h69;
  @(negedge clk);rx_valid=0;
  @(negedge clk);rx_valid=1;rx_data=t[7:0];
  @(negedge clk);rx_data={c,t[10:8]};rx_error=bad_rx;
  @(negedge clk);rx_active=0;rx_valid=0;rx_error=0;
  @(negedge clk);endpoint=ep;
 endtask
 task response(input [7:0] pid,input integer n,input integer delay_cycles=2,input integer stall_cycles=0);
  repeat(delay_cycles)@(negedge clk);
  tx_valid=1;tx_data=pid;tx_ready=0;
  repeat(stall_cycles)@(negedge clk);
  tx_ready=1;
  for(integer i=0;i<n;i=i+1)begin
   @(negedge clk);tx_data=8'(i);
  end
  tx_valid=0;tx_ready=0;
  repeat(3)@(negedge clk);
 endtask
 task check(input integer idx,input [31:0] expected);
  if(words[idx]!==expected)$fatal(1,"word%0d got%08x expected%08x",idx,words[idx],expected);
 endtask
 reg [31:0] s,seq,oldseq,disarm_ticks,held[0:31];
 task command(input [31:0] value);
  bus_read(8,oldseq);bus_write(12,value);wait_reply();bus_read(8,seq);
  if(seq!==oldseq+1)$fatal(1,"sequence wrong");
  for(integer k=0;k<32;k=k+1)bus_read(32'h40+32'(k*4),words[k]);
  $display("NETLIST_HEADER command=%h ID=%h version=%h command_word=%h seq=%h",value,words[0],words[1],words[2],seq);
  if(words[0]!==32'h55544e41 || words[1]!==1 || words[2]!==value)$fatal(1,"header");
  for(integer k=0;k<32;k=k+1)held[k]=words[k];
  repeat(100)@(negedge clk);
  for(integer k=0;k<32;k=k+1)begin
   bus_read(32'h40+32'(k*4),s);if(s!==held[k])$fatal(1,"held bank changed");
  end
 endtask
 initial begin
  #100;reset_n=1;repeat(40)@(negedge hclk);
  bus_read(0,s);if(s!==32'h55544e41)$fatal(1,"ID");
  for(integer k=0;k<32;k=k+1)begin
   bus_read(32'h40+32'(k*4),s);if(s!==0)$fatal(1,"initial bank not zero index=%d value=%h",k,s);
  end
  command(2); if(words[2]!==2 || seq!==1)$fatal(1,"first snapshot discriminant");
  bus_read(8,s);if(s!==1)$fatal(1,"control sequence");
  bus_read('h48,s);if(s!==2)$fatal(1,"bank alias to sequence");
  bus_read('h44,s);if(s!==1)$fatal(1,"bank version");
  bus_read(4,s);if(s!==0)$fatal(1,"control idle status");
  $display("DISCRIMINANT initial_bank_zero=1 control_status=0 bank_version=1 control_seq=1 bank_command=2");
  command(1);if(words[3]!==0 || words[31][10]!==0)$fatal(1,"arm reply not pre-clear");
  repeat(2000)@(negedge clk);
  command(6);disarm_ticks=words[3];
  if(disarm_ticks==0 || words[31][10]!==1)$fatal(1,"disarm reply not armed pre-state");
  repeat(1000)@(negedge clk);
  command(2);
  if(words[31][10]!==0)$fatal(1,"still armed");
  if($test$plusargs("wrong_equal"))begin
   if(words[3]!==disarm_ticks)$fatal(1,"negative witness: disarm front adds one tick");
  end else if(words[3]!==disarm_ticks+1)$fatal(1,"missing exact final tick");
  repeat(1000)@(negedge clk);command(2);
  if(words[3]!==disarm_ticks+1 || words[31][10]!==0)$fatal(1,"counter not stopped");
  $display("PASS EXACT SNAPSHOT seq=%0d ticks=%0d disarm_ticks=%0d hp=%f up=%f phase=%f",seq,words[3],disarm_ticks,hp,up,phase);
  $finish;
 end
 initial begin #1000000;$fatal(1,"deadline");end
endmodule
