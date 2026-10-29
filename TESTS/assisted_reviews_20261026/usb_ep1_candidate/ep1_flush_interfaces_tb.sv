`timescale 1ns/1ps
// Interface-only EP1 purge/EP2 retry regression. No hierarchical observation,
// force, deposit, or replacement RAM. Application bytes enter actual FIFO ports.
module ep1_flush_interfaces_tb;
reg clk=0,reset=1,flush=0,active=0,pop=0,ack=0;
always #8.333 clk=~clk;
reg [3:0] endpoint=1;
reg valid1=0,valid2=0;
reg [7:0] data1=0,data2=0;
reg [15:0] committed=0;
wire [15:0] sent;
wire [11:0] length;
wire cork;
wire [7:0] data_out;
integer selected=0,cycles=1,hold_active=0,event_kind=0,basic=0,n1=13,n2=7;
integer switch_to_ep1=0,nnew=5;
integer checks=0,bytes_checked=0,packets_checked=0;
integer j;
usb_fifo dut(
 .i_clk(clk),.i_reset(reset),.i_usb_endpt(endpoint),
 .i_usb_txact(active),.i_usb_txpop(pop),.i_usb_txpktfin(ack),
 .o_usb_txdat(data_out),.o_usb_txcork(cork),.o_usb_txlen(length),
 .i_usb_rxact(1'b0),.i_usb_rxval(1'b0),.i_usb_rxdat(8'd0),.i_usb_rxpktval(1'b0),.o_usb_rxrdy(),
 .i_ep1_tx_clk(clk),.i_ep1_tx_max(12'd512),.i_ep1_tx_dval(valid1),.i_ep1_tx_data(data1),
 .i_ep1_flush(flush),.i_ep1_tx_committed(committed),.o_ep1_tx_sent(sent),
 .i_ep1_rx_clk(clk),.i_ep1_rx_rdy(1'b1),.o_ep1_rx_dval(),.o_ep1_rx_data(),
 .i_ep2_tx_clk(clk),.i_ep2_tx_max(12'd64),.i_ep2_tx_dval(valid2),.i_ep2_tx_data(data2),
 .i_ep2_rx_clk(clk),.i_ep2_rx_rdy(1'b1),.o_ep2_rx_dval(),.o_ep2_rx_data(),.diagnostic_data()
);
function automatic [7:0] payload(input integer seed,input integer index);
 payload=8'(seed+17*index+71*(index/256));
endfunction
task automatic check_empty(input integer ep);
 begin
  endpoint=4'(ep);active=0;pop=0;ack=0;
  repeat(12) @(negedge clk);
  checks=checks+1;
  if(cork!==1'b1 || length!==12'd0)
   $fatal(1,"STALE_EP%0d_AFTER_FLUSH_OR_ACK length=%0d cork=%b",ep,length,cork);
 end
endtask
task automatic select_ep(input integer ep);
 begin
  endpoint=4'(ep);active=0;pop=0;ack=0;
  repeat(12) @(negedge clk);
 end
endtask
task automatic append1(input integer seed,input integer n,input integer total);
 begin
  for(integer i=0;i<n;i=i+1) begin
   @(negedge clk);valid1=1;data1=payload(seed,i);
  end
  @(negedge clk);valid1=0;committed=16'(total);
  repeat(16) @(negedge clk);
 end
endtask
task automatic append2(input integer seed,input integer n);
 begin
  for(integer i=0;i<n;i=i+1) begin
   @(negedge clk);valid2=1;data2=payload(seed,i);
  end
  @(negedge clk);valid2=0;
  repeat(32) @(negedge clk);
 end
endtask
task automatic read_payload(input integer seed,input integer n);
 begin
  checks=checks+1;
  if(cork!==1'b0 || length!==12'(n))
   $fatal(1,"OFFER ep=%0d got=%0d expected=%0d cork=%b",endpoint,length,n,cork);
  active=1;repeat(4) @(negedge clk);
  for(integer i=0;i<n;i=i+1) begin
   checks=checks+1;bytes_checked=bytes_checked+1;
   if(data_out!==payload(seed,i))
    $fatal(1,"PAYLOAD ep=%0d byte=%0d got=%02x expected=%02x",endpoint,i,data_out,payload(seed,i));
   pop=1;@(negedge clk);
  end
  pop=0;repeat(3) @(negedge clk);packets_checked=packets_checked+1;
 end
endtask
task automatic finish_packet(input bit accepted);
 begin
  if(accepted) begin ack=1;@(negedge clk);ack=0;end
  active=0;repeat(12) @(negedge clk);
 end
endtask
task automatic packet(input integer seed,input integer n,input bit accepted);
 begin read_payload(seed,n);finish_packet(accepted);end
endtask
initial begin
 if($value$plusargs("FLUSH_ENDPOINT=%d",selected))begin end
 if($value$plusargs("FLUSH_CYCLES=%d",cycles))begin end
 if($value$plusargs("TXACT=%d",hold_active))begin end
 if($value$plusargs("EVENT=%d",event_kind))begin end
 if($value$plusargs("BASIC=%d",basic))begin end
 if($value$plusargs("EP1_LENGTH=%d",n1))begin end
 if($value$plusargs("EP2_LENGTH=%d",n2))begin end
 if($value$plusargs("SWITCH_TO_EP1=%d",switch_to_ep1))begin end
 if(selected<0||selected>2||cycles<1||cycles>64||event_kind<0||event_kind>3||n1<1||n1>512||n2<1||n2>63)
  $fatal(1,"Invalid test configuration");
 // ACK/POP on EP2 require a real active transaction. TXACT=0 is covered
 // separately with no strobe; never invent an invalid idle EP2 transaction.
 if(selected==2 && event_kind!=0 && !hold_active)$fatal(1,"Invalid idle EP2 strobe");
 if(switch_to_ep1 && (selected!=2 || event_kind!=0))$fatal(1,"Switch case must not reassign an ACK/POP to another endpoint");
 repeat(6) @(negedge clk);reset=0;
 append1('ha0,n1,n1);select_ep(1);packet('ha0,n1,0);
 checks=checks+1;if(sent!==0)$fatal(1,"Unacknowledged EP1 advanced sent");
 append1('hd0,3,n1+3);packet('ha0,n1,0);
 checks=checks+1;if(sent!==0)$fatal(1,"EP1 retry advanced sent");
 // EP2 pending state is created only by a complete real seven-byte (or
 // boundary-sized) transaction with a missing ACK, then new bytes arrive.
 append2('h30,n2);select_ep(2);packet('h30,n2,0);
 append2('h70,3);packet('h30,n2,0);
 select_ep(selected);
 // If EP2 ACK coincides with EP1 purge it acknowledges an already consumed
 // EP2 payload. POP may coexist as a speculative extra strobe after it.
 if(selected==2 && (event_kind&2))read_payload('h30,n2);
 active=1'(hold_active);flush=1;committed=0;
 pop=1'(event_kind&1);ack=1'((event_kind>>1)&1);
 #1;
 if(!basic && selected==1) begin
  checks=checks+1;
  if(cork!==1'b1 || length!==0)$fatal(1,"FLUSH_NOT_MASKED_IMMEDIATELY");
 end
 if(switch_to_ep1 && cycles==1) begin
  // A synchronous one-cycle pulse can span endpoint selection before its
  // sampling edge; no ACK/POP belongs to the endpoint being left here.
  endpoint=1;#1;checks=checks+1;
  if(cork!==1'b1 || length!==0)$fatal(1,"SWITCH_EP2_TO_EP1_EXPOSED_FLUSHED_OFFER");
 end
 for(j=0;j<cycles;j=j+1) begin
  @(negedge clk);
  if(!basic && endpoint==1) begin
   checks=checks+1;
   if(cork!==1'b1 || length!==0)$fatal(1,"EP1_OFFER_DURING_FLUSH");
  end
  pop=0;ack=0;
  if(switch_to_ep1 && cycles>1 && j==0) begin
   endpoint=1;#1;checks=checks+1;
   if(cork!==1'b1 || length!==0)$fatal(1,"SWITCH_EP2_TO_EP1_EXPOSED_FLUSHED_OFFER");
  end
 end
 flush=0;active=0;
 repeat(12) @(negedge clk);
 checks=checks+1;if(sent!==0)$fatal(1,"Flush did not reset EP1 sent counter");
 check_empty(1);
 // Unrelated EP2 retries survive EP1 purge including extra queued bytes.
 select_ep(2);
 if(!(selected==2 && (event_kind&2)))packet('h30,n2,1);
 packet('h70,3,1);check_empty(2);
 // Fresh EP1 starts from byte zero, has the exact new length, then survives
 // another lost ACK while bytes are appended behind the frozen packet.
 select_ep(1);append1('hb0,nnew,nnew);packet('hb0,nnew,0);
 checks=checks+1;if(sent!==0)$fatal(1,"Fresh unacknowledged packet advanced sent");
 append1('he0,4,nnew+4);packet('hb0,nnew,1);
 checks=checks+1;if(sent!==16'(nnew))$fatal(1,"EP1 sent after new ACK=%0d expected%0d",sent,nnew);
 packet('he0,4,1);checks=checks+1;if(sent!==16'(nnew+4))$fatal(1,"EP1 sent after tail=%0d expected%0d",sent,nnew+4);
 check_empty(1);
 // Empty IN with TXACT high must not reserve a zero-length retry. A fresh
 // committed byte arriving while active must become the next exact offer.
 active=1;pop=1;@(negedge clk);pop=0;
 append1('h5c,1,nnew+5);packet('h5c,1,1);check_empty(1);
 checks=checks+1;if(sent!==16'(nnew+5))$fatal(1,"Final sent mismatch");
 $display("INTERFACE_PASS endpoint=%0d cycles=%0d txact=%0d event=%0d basic=%0d n1=%0d n2=%0d switch=%0d checks=%0d bytes=%0d packets=%0d",selected,cycles,hold_active,event_kind,basic,n1,n2,switch_to_ep1,checks,bytes_checked,packets_checked);
 $finish;
end
initial begin #2000000;$fatal(1,"BOUNDED_TIMEOUT");end
endmodule
