`timescale 1ns/1ps
module usb_idle_trace_tb;
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
 usb_idle_trace dut(.*);
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
 reg [31:0] s;
 initial begin
  #100;reset_n=1;repeat(20)@(negedge hclk);
  arm();
  token(3);response(8'h5a,1,3,2);
  token(2);response(8'h5a,1,2,0);
  token(2);response(8'h4b,4,2,0);
  token(3,1);repeat(150)@(negedge clk);
  token(3,0,1);repeat(150)@(negedge clk);
  token(3,0,0,8);repeat(150)@(negedge clk);
  token(3);repeat(150)@(negedge clk); // no response
  token(3);response(8'h5a,2); // malformed NAK
  @(negedge clk);bus_reset=1;sof=1;
  @(negedge clk);sof=0;
  repeat(3)@(negedge clk);bus_reset=0;
  capture();
  check(4,2);check(5,3);check(6,1);check(7,1);check(8,1);check(9,0);
  check(10,0);check(11,1);check(12,1);check(13,1);check(14,2);check(15,1);check(16,1);
  check(17,2);
  if(!words[29][31] || !words[29][30])$fatal(1,"first timeout not retained");
  if(words[20][7:0]!=4 || words[20][15:8]!=6)$fatal(1,"NAK latency %08x",words[20]);
  // Returned snapshot must not change while the live trace progresses.
  token(3);response(8'h5a,1);
  bus_read(32'h54,s);if(s!=3)$fatal(1,"torn snapshot");
  capture();check(5,4);check(7,2);
  // A reply to EP0 must not retire the unanswered EP3 poll.
  token(3);token(0);response(8'h5a,1);
  capture();check(5,5);check(7,2);check(11,2);
  // Include acceptance on the exact token_end edge.
  @(negedge clk);rx_active=1;rx_valid=1;rx_data=8'h69;
  @(negedge clk);rx_data=8'h87;
  @(negedge clk);rx_data={host_crc({4'd3,7'd7}),3'b001};
  @(negedge clk);rx_active=0;rx_valid=0;tx_valid=1;tx_ready=1;tx_data=8'h5a;endpoint=3;
  @(negedge clk);tx_valid=0;tx_ready=0;
  repeat(3)@(negedge clk);
  capture();check(5,6);check(7,3);check(11,2);
  arm();token(3);response(8'hd2,1);token(3);response(8'h5a,1);
  capture();check(5,2);check(7,1);check(12,1);
  if(!words[29][29] || words[29][23:16]!=8'hd2)$fatal(1,"unexpected ACK not retained");
  arm();token(3);
  tx_valid=1;tx_ready=1;tx_data=8'h5a;
  @(negedge clk);tx_ready=0;
  repeat(1100)@(negedge clk);tx_valid=0;
  capture();check(5,1);check(7,0);check(11,1);
  // Rejected concurrent command remains observable; no partial second bank.
  bus_write(12,2);bus_write(12,2);bus_read(4,s);
  if(!s[1])$fatal(1,"missing command rejection");
  repeat(250)@(negedge hclk);
  arm();capture();check(4,0);check(5,0);
  // Back-to-back pipelined reads, with the next address held through WAIT.
  @(negedge hclk);haddr=0;hsel=1;htrans=2;
  @(posedge hclk);
  @(negedge hclk);haddr=32'h40;
  @(posedge hclk);while(!hready)@(posedge hclk);
  if(hrdata!=32'h55544e41)$fatal(1,"first pipelined read");
  @(negedge hclk);hsel=0;htrans=0;
  @(posedge hclk);while(!hready)@(posedge hclk);
  if(hrdata!=32'h55544e41)$fatal(1,"second pipelined read");
  // Reset with the source clock stopped invalidates pending commands and
  // stale response words. Release must wait for the stopped clock to run.
  @(negedge clk);u_run=0;
  bus_write(12,32'h0701);
  #200;reset_n=0;#200;reset_n=1;
  repeat(30)@(negedge hclk);
  u_run=1;repeat(40)@(negedge clk);
  capture();check(4,0);check(5,0);
  if(words[31][10])$fatal(1,"old arm command replayed");
  // Stop destination clock with snapshot in flight, then reset both ends.
  arm();token(3);response(8'h5a,1);bus_write(12,2);
  @(negedge hclk);h_run=0;
  repeat(50)@(negedge clk);reset_n=0;
  repeat(20)@(negedge clk);reset_n=1;
  repeat(20)@(negedge clk);h_run=1;
  repeat(40)@(negedge hclk);
  capture();check(5,0);check(7,0);
  $display("PASS IN/NAK, CRC, address, stalls, timeout, coherent FIFO snapshots, stopped-clock reset hp=%f up=%f phase=%f",hp,up,phase);
  $finish;
 end
 initial begin #1000000;$fatal(1,"test deadline");end
endmodule
