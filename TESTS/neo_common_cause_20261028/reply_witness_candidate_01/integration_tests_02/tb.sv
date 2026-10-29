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
 assign hready=!read_pending_net;
 GSR GSR(.GSRI(1'b1));
 usb_idle_trace dut(
  .vid_hclk(hclk),.phy_clk(clk),.PHY_RESET(bus_reset),.usb_sof(sof),
  .PHY_RXACTIVE(rx_active),.PHY_RXVALID(rx_valid),.PHY_RXERROR(rx_error),
  .PHY_TXVALID(tx_valid),.PHY_TXREADY(tx_ready),.n949_8(cork),.n960_9(endpoint==0),
  .bus_hwrite(hwrite),.rst_usb(1'b0),.vid_hrstn(reset_n),
  .bus_haddr_0(haddr[0]),.bus_haddr_1(haddr[1]),.bus_haddr_2(haddr[2]),.bus_haddr_3(haddr[3]),
  .bus_haddr_4(haddr[4]),.bus_haddr_5(haddr[5]),.bus_haddr_6(haddr[6]),.bus_haddr_7(haddr[7]),
  .bus_haddr_12(1'b0),.bus_haddr_13(1'b1),.bus_haddr_14(1'b0),
  .PHY_DATAIN(rx_data),.PHY_DATAOUT(tx_data),.endpt_sel(endpoint),
  .bus_htrans(htrans[1]&&hsel),.bus_hwdata(hwdata),.read_pending(read_pending_net),
  .n6_5(reset_merge_net),.usb_trace_hrdata(hrdata));
 wire base_read_pending,base_reset_merge;wire [31:0] base_hrdata;
 usb_idle_trace_base base(
  .vid_hclk(hclk),.phy_clk(clk),.PHY_RESET(bus_reset),.usb_sof(sof),
  .PHY_RXACTIVE(rx_active),.PHY_RXVALID(rx_valid),.PHY_RXERROR(rx_error),
  .PHY_TXVALID(tx_valid),.PHY_TXREADY(tx_ready),.n949_8(cork),.n960_9(endpoint==0),
  .bus_hwrite(hwrite),.rst_usb(1'b0),.vid_hrstn(reset_n),
  .bus_haddr_0(haddr[0]),.bus_haddr_1(haddr[1]),.bus_haddr_2(haddr[2]),.bus_haddr_3(haddr[3]),
  .bus_haddr_4(haddr[4]),.bus_haddr_5(haddr[5]),.bus_haddr_6(haddr[6]),.bus_haddr_7(haddr[7]),
  .bus_haddr_12(1'b0),.bus_haddr_13(1'b1),.bus_haddr_14(1'b0),
  .PHY_DATAIN(rx_data),.PHY_DATAOUT(tx_data),.endpt_sel(endpoint),
  .bus_htrans(htrans[1]&&hsel),.bus_hwdata(hwdata),.read_pending(base_read_pending),
  .n6_5(base_reset_merge),.usb_trace_hrdata(base_hrdata));
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
  if(addr<192 && hrdata!==base_hrdata)$fatal(1,"old MMIO changed addr%h got%h base%h",addr,hrdata,base_hrdata);
  if(addr>=192 && base_hrdata!==0)$fatal(1,"extension address not reserved zero in baseline");
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
  if(words[0]!==32'h55544e41 || words[1]!==(mode==0?32'd1:32'd0) || words[2]!==value)$fatal(1,"header");
  for(integer k=0;k<32;k=k+1)begin
   held[k]=words[k];$display("BANK seq=%0d word=%0d value=%08h",seq,k,words[k]);
  end
  witness_check(value,seq);
  repeat(100)@(negedge clk);
  for(integer k=0;k<32;k=k+1)begin
   bus_read(32'h40+32'(k*4),s);if(s!==held[k])$fatal(1,"held bank changed");
  end
 endtask

 integer mode=0;
 initial if($value$plusargs("mode=%d",mode))begin end
 // Injection 1 zeroes the already read reply bit presented to BOTH bank and
 // witness at index1. It is a boundary fault model, not an identified FIFO bug.
 always @(negedge hclk)begin
  if(mode==1 && dut.reply_valid && dut.receive_index==1)begin
   force dut.reply[0]=1'b0;force base.reply[0]=1'b0;
  end else begin release dut.reply[0];release base.reply[0];end
 end
 initial begin
  #200;
  // Injection 2 changes only the bank lane1 validity result, downstream from
  // the witness. RAM contents are not claimed to be physically faulty.
  if(mode==2)begin force dut.bank_ER_RS_87=1'b0;force base.bank_ER_RS_87=1'b0;end
 end
 always @(negedge hclk)begin
  if(reset_n && !dut.hreset)begin
   if({dut.reply_valid,dut.reply,dut.busy,dut.receive_index,dut.snapshot_count,read_pending_net} !==
      {base.reply_valid,base.reply,base.busy,base.receive_index,base.snapshot_count,base_read_pending})
    $fatal(1,"witness altered original control or data");
  end
 end
 task witness_check(input [31:0] command_value,input [31:0] sequence_value);
  reg [31:0] v,alias_value;
  bus_read('hc0,v);if(v!==32'h55545731)$fatal(1,"witness ID");
  bus_read('hc4,v);if(v!==32'h00010001)$fatal(1,"witness ABI");
  bus_read('hc8,v);if(v!==32'h55544e41)$fatal(1,"raw0");
  bus_read('hcc,v);if(v!==(mode==1?32'd0:32'd1))$fatal(1,"raw1 boundary");
  bus_read('hd4,alias_value);if(v!==alias_value)$fatal(1,"raw1 alias");
  bus_read('hd0,v);if(v!==command_value)$fatal(1,"raw2");
  for(integer a='hd8;a<='he0;a=a+4)begin bus_read(a,v);if(v!==sequence_value)$fatal(1,"slot count addr%h",a);end
  bus_read('he4,v);if(v!==sequence_value*32)$fatal(1,"event count");
  bus_read('he8,v);if(v!==sequence_value)$fatal(1,"frame count");
  bus_read('hec,v);if(v!==0)$fatal(1,"outside busy");
  bus_read('hf0,v);if(v!==32'h003f0007)$fatal(1,"completion status %h",v);
  for(integer a='hf4;a<='hfc;a=a+4)begin bus_read(a,v);if(v!==sequence_value-1)$fatal(1,"slot tag");end
  $display("WITNESS mode=%0d seq=%0d command=%0d bank1=%h raw1=%h status=%h",mode,sequence_value,command_value,words[1],alias_value,32'h003f0007);
 endtask
 task sweep_byte_addresses;
  reg [31:0] v;
  for(integer a=0;a<256;a=a+1)begin
   bus_read(a,v);
   if(a>=192 && (a%4)!=0 && v!==0)$fatal(1,"unaligned witness address aliased %h",a);
  end
 endtask
 task zero_witness_state;
  reg [31:0] v;
  for(integer a='hc8;a<256;a=a+4)begin bus_read(a,v);if(v!==0)$fatal(1,"state not reset %h=%h",a,v);end
 endtask

 initial begin
  #100;reset_n=1;repeat(40)@(negedge hclk);
  bus_read(0,s);if(s!==32'h55544e41)$fatal(1,"ID");
  zero_witness_state();sweep_byte_addresses();
  for(integer a='hc0;a<256;a=a+1)bus_write(a,32'hffffffff);
  zero_witness_state();bus_read(8,s);if(s!==0)$fatal(1,"extension write changed sequence");
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
  sweep_byte_addresses();witness_check(2,4);
  @(negedge clk);u_run=0;
  bus_write(12,2);repeat(20)@(negedge hclk);
  bus_read(4,s);if(s!==1)$fatal(1,"pending command while USB clock stopped");
  bus_read('he8,s);if(s!==4)$fatal(1,"spurious frame while USB clock stopped");
  @(negedge hclk);reset_n=0;repeat(20)@(negedge hclk);reset_n=1;
  repeat(20)@(negedge hclk);
  if(dut.utw_observer.\r_total.q !==0)$fatal(1,"witness not reset with USB clock stopped");
  u_run=1;repeat(50)@(negedge hclk);zero_witness_state();
  bus_read(8,s);if(s!==0)$fatal(1,"snapshot count not reset");
  command(2);witness_check(2,1);
  $display("PASS EXACT SNAPSHOT seq=%0d ticks=%0d disarm_ticks=%0d hp=%f up=%f phase=%f",seq,words[3],disarm_ticks,hp,up,phase);
  $finish;
 end
 initial begin #1000000;$fatal(1,"deadline");end
endmodule
