`timescale 1ns/1ps
module usb_packet_trace_first_tb;
 reg clk=0;always #5 clk=~clk;
 reg reset=1,valid=0,ready=0,cork=0,active=1;
 reg [7:0] data=0;
 reg [3:0] endpoint=2;
 reg [11:0] length=0;
 reg rx_active=0,rx_valid=0,rx_error=0,packet_ack=0,fifo_pending=0,new_packet=0;
 reg [7:0] rx_data=0;
 wire [255:0] history;
 reg [255:0] frozen;
 usb_packet_trace #(.CAPTURE_FIRST(1)) dut(.*);
 task byte_out(input [7:0] value);
  data=value;valid=1;ready=0;repeat(2)@(negedge clk);
  ready=1;@(negedge clk);ready=0;
 endtask
 task finish_packet;
  valid=0;repeat(3)@(negedge clk);
 endtask
 task publish;
  new_packet=1;@(negedge clk);new_packet=0;fifo_pending=1;
 endtask
 task host_ack(input bit bad,input bit extra);
  rx_active=1;@(negedge clk);rx_valid=1;rx_data=8'hd2;rx_error=bad;
  @(negedge clk);rx_valid=extra;rx_data=0;
  @(negedge clk);rx_valid=0;rx_error=0;rx_active=0;
  repeat(3)@(negedge clk);
 endtask
 task completion;
  packet_ack=1;@(negedge clk);packet_ack=0;fifo_pending=0;
  repeat(8)@(negedge clk);
 endtask
 task payload(input [7:0] pid,input [7:0] value,input [15:0] crc);
  endpoint=2;cork=0;length=1;
  byte_out(pid);byte_out(value);byte_out(crc[15:8]);byte_out(crc[7:0]);finish_packet();
 endtask
 task zlp(input [7:0] pid);
  endpoint=2;cork=1;length=0;
  byte_out(pid);byte_out(0);byte_out(0);finish_packet();
 endtask
 initial begin
  repeat(5)@(negedge clk);reset=0;
  // A correctly empty predecessor with its own ACK/FIN must survive five
  // later retries of the useful packet, not only its latest two attempts.
  zlp(8'hc3);host_ack(0,0);completion();
  zlp(8'h4b);
  zlp(8'h4b);host_ack(0,0);completion();
  if(history!==0)$fatal(1,"Unpublished idle traffic created a first snapshot");
  publish();
  // Unrelated transmissions between publication and DATA do not consume it.
  endpoint=0;byte_out(8'hd2);finish_packet();
  endpoint=2;byte_out(8'h5a);finish_packet();
  payload(8'hc3,8'h5a,16'hc084);
  if(history[7:0]!=8'hc3 || history[23:8]!=16'hc084 || history[33:24]!=4 ||
     history[51:40]!=1 || !history[63] || history[38:34]!=0)
    $fatal(1,"First payload not captured without ACK/FIN");
  if(history[71:64]!=8'h4b || history[97:88]!=3 || !history[102] || !history[101] ||
     !history[99] || history[98])$fatal(1,"ACKed ZLP predecessor not retained");
  if(history[135:128]!=8'h4b || history[161:152]!=3 || history[166] || history[165])
    $fatal(1,"Unacknowledged second predecessor not retained");
  if(history[199:192]!=8'hc3 || history[225:216]!=3 || !history[230] || !history[229])
    $fatal(1,"Third predecessor not retained");
  frozen=history;
  for(integer retry=0;retry<5;retry++)begin
   payload(8'hc3,8'h5a,16'hc084);
   if(retry==4)begin host_ack(0,0);completion();end
   if(history!==frozen)$fatal(1,"Retry %0d overwrote first attempt or its ACK flags",retry);
  end
  repeat(12)begin zlp(8'h4b);host_ack(0,0);completion();end
  if(history!==frozen)$fatal(1,"Idle ZLP erased first attempt");
  // A publication during the first attempt (after PID acceptance) is valid.
  endpoint=2;cork=0;length=1;byte_out(8'h4b);publish();
  byte_out(8'ha3);byte_out(8'h01);byte_out(8'h39);finish_packet();
  if(history[7:0]!=8'h4b || history[23:8]!=16'h0139 || history[38:34]!=0)
    $fatal(1,"Publication after PID was missed or inherited old ACK flags");
  host_ack(0,0);completion();
  if(!history[38] || !history[37] || !history[35] || history[34])
    $fatal(1,"First attempt own ACK/FIN/retirement missing");
  frozen=history;
  endpoint=0;byte_out(8'h4b);byte_out(8'haa);byte_out(0);byte_out(0);finish_packet();
  host_ack(0,0);completion();
  if(history!==frozen)$fatal(1,"EP0 changed captured first attempt");
  // A pulse at the completion edge also belongs to that DATA. Deliberately
  // advertise zero bytes: publication must expose this anomalous first ZLP.
  endpoint=2;length=0;cork=0;byte_out(8'hc3);byte_out(0);byte_out(0);
  new_packet=1;valid=0;@(negedge clk);new_packet=0;fifo_pending=1;
  repeat(3)@(negedge clk);
  if(history[7:0]!=8'hc3 || history[33:24]!=3 || history[51:40]!=0)
    $fatal(1,"Published first ZLP with zero advertised length was hidden");
  host_ack(1,0);host_ack(0,1);
  if(history[38] || history[37] || !history[36])$fatal(1,"Invalid ACK changed first attempt evidence");
  frozen=history;
  payload(8'hc3,8'h35,16'h80a8);host_ack(0,0);completion();
  if(history!==frozen)$fatal(1,"Later useful DATA erased first ZLP");
  // Reset clears both retained evidence and a publication not yet emitted.
  publish();reset=1;repeat(3)@(negedge clk);reset=0;
  payload(8'h4b,8'h11,16'h80b3);
  if(history!==0)$fatal(1,"Reset left a stale publication armed");
  publish();payload(8'hc3,8'hec,16'h8172);
  if(history[7:0]!=8'hc3 || history[23:8]!=16'h8172)
    $fatal(1,"New packet after reset not captured");
  host_ack(0,0);repeat(8)@(negedge clk);
  if(!history[38] || history[37] || !history[35] || !history[34])
    $fatal(1,"First PHY-only ACK must retain pending without FIN");
  frozen=history;
  payload(8'hc3,8'hec,16'h8172);host_ack(0,0);completion();
  if(history!==frozen)$fatal(1,"Retry FIN contaminated first PHY-only ACK");
  $display("PASS: first publication captures before/during/completion, keeps ZLP predecessor and own ACK/FIN across five retries, EP0/idle, invalid ACKs and reset");
  $finish;
 end
endmodule
