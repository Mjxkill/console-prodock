// Passive UTMI observer: an EP2 DATA and the three DATA attempts immediately
// before it, INCLUDING empty DATA. CAPTURE_FIRST=0 retains the last useful DATA
// during idle polls (historical behavior). CAPTURE_FIRST=1 retains the FIRST
// attempt after new_packet, including an unexpectedly empty DATA; retries and
// idle traffic cannot replace it until the next publication pulse.
// new_packet is a one-clock pulse in clk, at the first admitted payload POP of
// a new EP2 packet, not on retries. It may precede the accepted PID or arrive
// during that attempt, at latest on its completion clock. This explicit event
// avoids inferring publication from fifo_pending after it has already risen.
// ACK/FIN/error flags belong only to the captured attempt, never later retries.
// Each 64-bit record: valid[63], previous PHY ACK valid/PID1[62:61],
// previous controller completion valid/PID1[60:59], format marker[58]=1,
// txact[57], cork[56], endpoint[55:52],
// advertised length[51:40], transaction-format marker[39]=1,
// own ACK[38], own controller finish[37], RX error after TX[36],
// post-ACK/finish FIFO sample valid[35], pending at that sample[34],
// accepted bytes (saturating)[33:24], last two bytes[23:8],
// first byte (USB PID)[7:0]. Newest record is in history[63:0].
module usb_packet_trace #(
 parameter CAPTURE_FIRST = 0,
 parameter INPUT_PIPELINE = 0
)(
 input wire clk,reset,valid,ready,
 input wire [7:0] data,
 input wire [3:0] endpoint,
 input wire cork,active,
 input wire [11:0] length,
 input wire rx_active,rx_valid,rx_error,packet_ack,fifo_pending,
 input wire [7:0] rx_data,
 input wire new_packet,
 output reg [255:0] history
);
 // Register the complete observation together when requested by the full
 // integration. This removes analyzer logic from the late TXREADY return
 // path without changing USB traffic or relative event timing.
 wire [41:0] observed;
 generate if(INPUT_PIPELINE)begin: g_tap
  (* syn_preserve=1 *) reg [41:0] tap;
  always @(posedge clk or posedge reset)
   if(reset)tap<=0;
   else tap<={valid,ready,data,endpoint,cork,active,length,rx_active,rx_valid,
              rx_error,packet_ack,fifo_pending,rx_data,new_packet};
  assign observed=tap;
 end else begin:g_direct
  assign observed={valid,ready,data,endpoint,cork,active,length,rx_active,rx_valid,
                   rx_error,packet_ack,fifo_pending,rx_data,new_packet};
 end endgenerate
 wire valid_observed,ready_observed,cork_observed,active_observed;
 wire [7:0] data_observed,rx_data_observed;
 wire [3:0] endpoint_observed;
 wire [11:0] length_observed;
 wire rx_active_observed,rx_valid_observed,rx_error_observed,packet_ack_observed;
 wire fifo_pending_observed,new_packet_observed;
 assign {valid_observed,ready_observed,data_observed,endpoint_observed,cork_observed,
         active_observed,length_observed,rx_active_observed,rx_valid_observed,
         rx_error_observed,packet_ack_observed,fifo_pending_observed,rx_data_observed,
         new_packet_observed}=observed;
 reg busy;
 reg [15:0] count,tail;
 reg [7:0] pid;
 reg [3:0] saved_ep;
 reg saved_cork,saved_active;
 reg [11:0] saved_length;
 reg [4:0] saved_acks;
 reg last_tx_data,last_tx_pid1;
 reg wire_ack_seen,wire_ack_pid1,fin_seen,fin_pid1;
 reg [1:0] rx_count;
 reg [7:0] rx_pid;
 reg rx_bad;
 reg last_record;
 reg snapshot_record;
 reg [191:0] live_history;
 reg [2:0] retire_wait;
 reg first_armed;
 wire wire_ack = !rx_active_observed && rx_count==1 && rx_pid==8'hd2 && !rx_bad && !rx_error_observed;
 wire [63:0] completed_record = {1'b1,saved_acks,saved_active,saved_cork,
                                saved_ep,saved_length,6'b100000,
                                (count>1023 ? 10'h3ff : count[9:0]),tail,pid};
 always @(posedge clk or posedge reset)begin
  if(reset)begin
   busy<=0;count<=0;tail<=0;pid<=0;saved_ep<=0;
   saved_cork<=0;saved_active<=0;saved_length<=0;history<=0;saved_acks<=0;
   last_tx_data<=0;last_tx_pid1<=0;
   wire_ack_seen<=0;wire_ack_pid1<=0;fin_seen<=0;fin_pid1<=0;
   rx_count<=0;rx_pid<=0;rx_bad<=0;
   last_record<=0;snapshot_record<=0;live_history<=0;retire_wait<=0;first_armed<=0;
  end else begin
   if(CAPTURE_FIRST && new_packet_observed)first_armed<=1;
   // These flags describe this recorded attempt, not the previous packet.
   // Stop following an attempt as soon as another transmission starts.
   if(last_record)begin
    if(rx_error_observed)begin live_history[36]<=1;if(snapshot_record)history[36]<=1;end
    if(wire_ack)begin live_history[38]<=1;if(snapshot_record)history[38]<=1;end
    if(packet_ack_observed && endpoint_observed==2)begin
     live_history[37]<=1;if(snapshot_record)history[37]<=1;
    end
    if(wire_ack || (packet_ack_observed && endpoint_observed==2))retire_wait<=6;
    else if(retire_wait!=0)begin
     retire_wait<=retire_wait-1'b1;
     if(retire_wait==1)begin
      live_history[35]<=1;live_history[34]<=fifo_pending_observed;
      if(snapshot_record)begin history[35]<=1;history[34]<=fifo_pending_observed;end
     end
    end
   end
   // Observe host ACKs independently of the controller's completion pulse.
   // An ACK is exactly one UTMI byte, with no PHY reception error. Include
   // correctly empty DATA packets, also kept in the live context below.
   if(rx_active_observed)begin
    if(rx_error_observed)rx_bad<=1;
    if(rx_valid_observed)begin
     if(rx_count==0)rx_pid<=rx_data_observed;
     if(rx_count!=2)rx_count<=rx_count+1'b1;
    end
   end else begin
    if(rx_count==1 && rx_pid==8'hd2 && !rx_bad && !rx_error_observed
       && endpoint_observed==2 && last_tx_data)begin
     wire_ack_seen<=1;wire_ack_pid1<=last_tx_pid1;
    end
    rx_count<=0;rx_bad<=0;
   end
   if(packet_ack_observed && endpoint_observed==2 && last_tx_data)begin
    fin_seen<=1;fin_pid1<=last_tx_pid1;
   end
   if(valid_observed && ready_observed)begin
    if(!busy)begin
     last_record<=0;snapshot_record<=0;retire_wait<=0;
     busy<=1;count<=1;pid<=data_observed;tail<={8'd0,data_observed};
     saved_ep<=endpoint_observed;saved_cork<=cork_observed;saved_active<=active_observed;saved_length<=length_observed;
     saved_acks<={wire_ack_seen,wire_ack_pid1,fin_seen,fin_pid1,1'b1};
     last_tx_data<=endpoint_observed==2 && (data_observed==8'hc3 || data_observed==8'h4b);
     last_tx_pid1<=data_observed[3];
    end else begin
     if(count!=16'hffff)count<=count+1'b1;
     tail<={tail[7:0],data_observed};
    end
   end
   if(busy && !valid_observed)begin
    busy<=0;
    if(saved_ep==2 && (pid==8'hc3 || pid==8'h4b))begin
     live_history<={live_history[127:0],completed_record};
     if(CAPTURE_FIRST ? (first_armed || new_packet_observed) : (count>3 || saved_length!=0))begin
      history<={live_history,completed_record};
      snapshot_record<=1;
      if(CAPTURE_FIRST)first_armed<=0;
     end
     last_record<=1;
    end
   end
  end
 end
endmodule
