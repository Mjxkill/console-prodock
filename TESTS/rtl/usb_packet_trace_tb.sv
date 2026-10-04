`timescale 1ns/1ps
module usb_packet_trace_tb;
 reg clk=0;always #5 clk=~clk;
 reg reset=1,valid=0,ready=0,cork=0,active=1;
 reg [7:0] data=0;
 reg [3:0] endpoint=2;
 reg [11:0] length=2;
 reg rx_active=0,rx_valid=0,rx_error=0,packet_ack=0;
 reg fifo_pending=1;
 reg [7:0] rx_data=0;
 wire [255:0] history;
 usb_packet_trace dut(.new_packet(1'b0),.*);
 task byte_out(input [7:0] value);
  data=value;valid=1;ready=0;repeat(2)@(negedge clk);
  ready=1;@(negedge clk);ready=0;
 endtask
 task finish_packet;
  valid=0;repeat(3)@(negedge clk);
 endtask
 task host_ack(input bit bad,input bit extra);
  rx_active=1;@(negedge clk);rx_valid=1;rx_data=8'hd2;rx_error=bad;
  @(negedge clk);rx_valid=extra;rx_data=0;
  @(negedge clk);rx_valid=0;rx_error=0;rx_active=0;
  repeat(3)@(negedge clk);
 endtask
 task completion;
  packet_ack=1;@(negedge clk);packet_ack=0;@(negedge clk);
 endtask
 task payload(input [7:0] pid);
  cork=0;length=1;byte_out(pid);byte_out(8'h33);byte_out(0);byte_out(0);finish_packet();
 endtask
 initial begin
  repeat(5)@(negedge clk);reset=0;
  byte_out(8'hc3);byte_out(8'h11);byte_out(8'h22);byte_out(8'hab);byte_out(8'hcd);finish_packet();
  if(history[7:0]!=8'hc3 || history[33:24]!=5 || history[23:8]!=16'habcd
     || history[51:40]!=2 || history[55:52]!=2 || !history[57] || !history[63])$fatal(1,"DATA record");
  cork=1;length=0;
  byte_out(8'h4b);byte_out(0);byte_out(0);finish_packet();
  if(history[7:0]!=8'hc3)$fatal(1,"Idle ZLP erased DATA history");
  // A ZLP that advertised data is anomalous and must remain observable.
  cork=0;length=1;
  byte_out(8'h4b);byte_out(0);byte_out(0);finish_packet();
  if(history[7:0]!=8'h4b || history[33:24]!=3 || history[23:8]!=0
     || history[56] || history[51:40]!=1 || history[71:64]!=8'h4b
     || history[97:88]!=3 || history[135:128]!=8'hc3)$fatal(1,"Anomalous ZLP and preceding empty context");
  endpoint=0;byte_out(8'hd2);finish_packet();
  if(history[7:0]!=8'h4b)$fatal(1,"Other endpoint recorded");
  endpoint=2;byte_out(8'h5a);finish_packet();
  if(history[7:0]!=8'h4b || history[33:24]!=3 || history[71:64]!=8'h4b)$fatal(1,"NAK erased DATA history");
  repeat(20)begin byte_out(8'h5a);finish_packet();end
  byte_out(8'hd2);finish_packet();
  if(history[7:0]!=8'h4b || history[71:64]!=8'h4b)$fatal(1,"Idle erased DATA history");
  // Independently record PHY ACKs and controller completions, at the start
  // of each attempt. Retries, invalid ACKs and other endpoints cannot advance
  // that evidence. Correctly empty DATA also participates in PID alternation.
  reset=1;repeat(3)@(negedge clk);reset=0;
  payload(8'hc3);
  if(history[62:58]!=5'b00001)$fatal(1,"ACK state after reset");
  host_ack(0,0);
  if(!history[39] || !history[38] || history[37])$fatal(1,"Own PHY ACK without controller completion");
  repeat(8)@(negedge clk);
  if(!history[35] || !history[34])$fatal(1,"Pending packet after PHY-only ACK");
  payload(8'h4b);
  if(history[38:34]!=0)$fatal(1,"Previous attempt flags leaked into new packet");
  if(history[62:58]!=5'b10001)$fatal(1,"PHY ACK independent of completion");
  completion();
  fifo_pending=0;repeat(8)@(negedge clk);
  if(history[38] || !history[37] || !history[35] || history[34])$fatal(1,"Own finish without PHY ACK, retired FIFO");
  payload(8'hc3);
  if(history[62:58]!=5'b10111)$fatal(1,"Controller completion independent of PHY ACK");
  host_ack(1,0);host_ack(0,1);
  if(history[38] || !history[36])$fatal(1,"Bad ACK must record RX error, no ACK");
  payload(8'hc3);
  if(history[62:58]!=5'b10111)$fatal(1,"Invalid ACK changed evidence");
  endpoint=0;host_ack(0,0);completion();endpoint=2;
  payload(8'hc3);
  if(history[62:58]!=5'b10111)$fatal(1,"Other endpoint ACK changed evidence");
  host_ack(0,0);completion();
  payload(8'h4b);
  if(history[62:58]!=5'b10101)$fatal(1,"Prior DATA0 ACK missing");
  host_ack(0,0);completion();
  cork=1;length=0;byte_out(8'hc3);byte_out(0);byte_out(0);finish_packet();
  host_ack(0,0);completion();
  payload(8'h4b);
  if(history[62:58]!=5'b10101)$fatal(1,"Empty DATA ACK not tracked");
  payload(8'h4b);
  if(history[62:58]!=5'b10101)$fatal(1,"Retry changed ACK evidence");
  // Idle ZLPs enter the live context, including their own ACK/FIN, but
  // cannot replace the snapshot ending with the most recent useful DATA.
  begin : context_test
   reg [255:0] frozen;
   frozen=history;
   for(integer i=0;i<12;i++)begin
    cork=1;length=0;
    byte_out(i[0] ? 8'h4b : 8'hc3);byte_out(0);byte_out(0);finish_packet();
    if(i!=11)begin host_ack(0,0);completion();end
    if(history!==frozen)$fatal(1,"Idle ZLP overwrote useful snapshot");
   end
   payload(8'h4b);
   if(history[71:64]!=8'h4b || history[97:88]!=3 || history[102] || history[101])
    $fatal(1,"Unacknowledged ZLP immediately before DATA missing");
   if(history[135:128]!=8'hc3 || history[161:152]!=3 || !history[166] || !history[165])
    $fatal(1,"Acknowledged ZLP context missing");
   cork=1;length=0;byte_out(8'hc3);byte_out(0);byte_out(0);finish_packet();
   host_ack(0,0);completion();
   payload(8'h4b);
   if(history[71:64]!=8'hc3 || history[97:88]!=3 || !history[102] || !history[101])
    $fatal(1,"Acknowledged ZLP predecessor missing");
  end
  $display("PASS: useful DATA snapshot with preceding DATA/ZLP attempts, own and previous ACK/FIN, idle retention, stalls, invalid ACKs, endpoints and reset");$finish;
 end
endmodule
