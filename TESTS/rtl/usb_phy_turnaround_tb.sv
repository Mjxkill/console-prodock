`timescale 1ns/1ps
// Public-port PHY turnaround test. Official PHY/primitives remain untouched.
module usb_phy_turnaround_tb;
reg clk60=0, clk960=0, reset=1, locked=0;
reg [7:0] txdata=0;
reg txvalid=0, host_drive=0, host_dp=0,host_dn=0;
tri dp,dn,term_dp,term_dn;
assign dp=host_drive ? host_dp : 1'bz;
assign dn=host_drive ? host_dn : 1'bz;
pulldown(dp,dn);
wire txready,rxvalid,rxactive,rxerror;
wire [7:0] rxdata;
real phase=0,bit_ns=1000.0/480.0,last_edge=0,last_eop=0;
integer rxbytes=0,rxacks=0,rxerrors=0,txpackets=0,framing=0;
integer first_k_bad=0,tail_bad=0;
integer overlap_samples=0,unknown_samples=0,mismatch_samples=0;
real last_drive_release=0;
// Output enable is observed at the original primitive, never forced.
wire phy_oen=phy.\usb2_0_softphy/u_usb_20_phy_utmi/u_TLVDS_IOBUF .OEN;
reg [7:0] response[0:15];
integer response_len=0;
USB2_0_SoftPHY_Top phy (
 .clk_i(clk60),.fclk_i(clk960),.rst_i(reset),.pll_locked_i(locked),
 .utmi_data_out_i(txdata),.utmi_txvalid_i(txvalid),.utmi_op_mode_i(2'b00),
 .utmi_xcvrselect_i(2'b00),.utmi_termselect_i(1'b0),
 .utmi_txready_o(txready),.utmi_data_in_o(rxdata),.utmi_rxvalid_o(rxvalid),
 .utmi_rxactive_o(rxactive),.utmi_rxerror_o(rxerror),
 .usb_rxdp_i(dp),.usb_rxdn_i(dn),
 .usb_dxp_io(dp),.usb_dxn_io(dn),.usb_term_dp_io(term_dp),.usb_term_dn_io(term_dn)
);
initial begin : clock60
 real deadline;
 deadline=0;
 forever begin deadline=deadline+1000.0/120.0; #(deadline-$realtime);clk60=~clk60;end
end
initial begin : clock960
 real deadline;
 if($value$plusargs("LOCAL_PHASE_NS=%f",phase))begin end
 deadline=phase;
 forever begin deadline=deadline+1000.0/1920.0; #(deadline-$realtime);clk960=~clk960;end
end
always @(posedge clk60)if(!reset)begin
 if(rxerror)rxerrors++;
 if(rxvalid)begin
  rxbytes++;
  if(rxdata==8'hd2)rxacks++;
  $display("RX t=%0.6f data=%02x active=%b error=%b",$realtime,rxdata,rxactive,rxerror);
 end
end
always @(dp or dn)begin
 #0.001;
 if((dp===0&&dn===1)||(dp===1&&dn===0))last_edge=$realtime;
end
always @(posedge phy_oen)last_drive_release=$realtime;
always @(posedge clk960)begin
 // Avoid sampling in the same time slot as the host's rounded bit boundary.
 #0.050;
 if(host_drive)begin
  if(phy_oen!==1'b1)overlap_samples++;
  if(dp===1'bx||dn===1'bx)unknown_samples++;
  if(dp!==host_dp||dn!==host_dn)mismatch_samples++;
 end
end
task automatic send_ack;
 real deadline;
 bit nrzi;
 integer ones;
 reg [7:0] pid;
 begin
  deadline=$realtime;nrzi=1;ones=1;pid=8'hd2;
  host_drive=1;
  for(integer b=0;b<32;b++)begin
   if(b<31)nrzi=~nrzi;
   host_dp=nrzi;host_dn=~nrzi;
   deadline=deadline+bit_ns;#(deadline-$realtime);
  end
  for(integer b=0;b<8;b++)begin
   if(!pid[b])nrzi=~nrzi;
   host_dp=nrzi;host_dn=~nrzi;
   if(pid[b])ones++;else ones=0;
   deadline=deadline+bit_ns;#(deadline-$realtime);
   if(ones==6)begin
    nrzi=~nrzi;host_dp=nrzi;host_dn=~nrzi;ones=0;
    deadline=deadline+bit_ns;#(deadline-$realtime);
   end
  end
  // Eight-bit HS EOP: one transition, then seven repeated bits.
  nrzi=~nrzi;host_dp=nrzi;host_dn=~nrzi;
  deadline=deadline+8*bit_ns;#(deadline-$realtime);
  host_dp=0;host_dn=0;host_drive=0;
 end
endtask
function automatic [15:0] crc16(input [7:0] data);
 reg [15:0] c;
 begin
  c=16'hffff;
  for(integer b=0;b<8;b++)begin
   if(c[0]^data[b])c=(c>>1)^16'ha001;else c=c>>1;
  end
  crc16=~c;
 end
endfunction
task automatic transmit_data;
 reg [15:0] crc;
 reg [7:0] bytes[0:3];
 begin
  crc=crc16(8'hea);bytes[0]=8'hc3;bytes[1]=8'hea;bytes[2]=crc[7:0];bytes[3]=crc[15:8];
  @(negedge clk60);txvalid=1;txdata=bytes[0];
  for(integer i=0;i<4;i++)begin
   @(posedge clk60);while(!txready)@(posedge clk60);
   $display("TX_ACCEPT t=%0.6f data=%02x",$realtime,txdata);
   @(negedge clk60);
   if(i<3)txdata=bytes[i+1];else txvalid=0;
  end
 end
endtask
task automatic receive_tx;
 real sample_time,previous_sample,first_k,after_eop,k_width,tail;
 bit previous_level,value,sync_found,eop;
 integer symbols,ones,bits;
 reg [7:0] current_byte;
 begin
  first_k=$realtime;
  wait(dp===1&&dn===0);k_width=$realtime-first_k;
  if(k_width>1.55*bit_ns||k_width<0.45*bit_ns)begin first_k_bad++;framing++;end
  sample_time=$realtime+bit_ns/2;
  previous_sample=$realtime;previous_level=0;sync_found=0;symbols=0;
  while(!sync_found)begin
   #(sample_time-$realtime);
   if(symbols>=12&&previous_level==0&&dp===0)sync_found=1;
   if(dp!==!dn)$fatal(1,"Invalid TX differential SYNC");
   previous_level=dp;symbols++;
   if(symbols>40)$fatal(1,"No TX SYNC end");
   if(last_edge>previous_sample)sample_time=last_edge+bit_ns/2;
   previous_sample=$realtime;sample_time=sample_time+bit_ns;
  end
  response_len=0;ones=1;bits=0;current_byte=0;eop=0;
  while(!eop)begin
   #(sample_time-$realtime);
   if(dp!==!dn)$fatal(1,"TX DATA ended before EOP");
   value=(dp===previous_level);previous_level=dp;
   if(ones==6)begin if(value)eop=1;else ones=0;end
   else begin
    current_byte[bits]=value;bits++;
    if(value)ones++;else ones=0;
    if(bits==8)begin
     if(response_len>=16)$fatal(1,"TX response overflow");
     response[response_len]=current_byte;response_len++;bits=0;
    end
   end
   if(last_edge>previous_sample)sample_time=last_edge+bit_ns/2;
   previous_sample=$realtime;sample_time=sample_time+bit_ns;
  end
  if(bits!=7)$fatal(1,"TX EOP byte alignment %0d",bits);
  after_eop=$realtime+bit_ns/2;
  wait(dp===0&&dn===0);last_eop=$realtime;tail=$realtime-after_eop;
  if(tail>bit_ns)begin tail_bad++;framing++;end
  $write("WIRE t=%0.6f first_k_t=%0.6f first_k_ns=%0.6f sync_samples=%0d eop_tail_ns=%0.6f len=%0d bytes=",$realtime,first_k,k_width,symbols,tail,response_len);
  for(integer i=0;i<response_len;i++)$write("%02x",response[i]);
  $display("");
  txpackets++;
 end
endtask
initial begin
 wait(!reset);
 forever begin wait(!host_drive&&dp===0&&dn===1);receive_tx();end
end
initial begin : stimulus
 integer before_bytes,before_acks,before_errors,before_packets,before_overlap,before_unknown,before_mismatch;
 real gaps[0:3];
 reg [15:0] crc;
 gaps[0]=40;gaps[1]=100;gaps[2]=200;gaps[3]=340;
 #103.3;locked=1;#97;reset=0;#30000;
 $display("IDLE_ACK t=%0.6f",$realtime);send_ack();#1000;
 if(rxbytes!=1||rxacks!=1||rxerrors!=0)$fatal(1,"Idle ACK did not reach UTMI exactly");
 crc=crc16(8'hea);
 for(integer c=0;c<4;c++)begin
  before_bytes=rxbytes;before_acks=rxacks;before_errors=rxerrors;before_packets=txpackets;
  before_overlap=overlap_samples;before_unknown=unknown_samples;before_mismatch=mismatch_samples;
  transmit_data();wait(txpackets==before_packets+1);
  if(response_len!=4||response[0]!=8'hc3||response[1]!=8'hea||response[2]!=crc[7:0]||response[3]!=crc[15:8])
   $fatal(1,"TX payload or CRC differs");
  #(gaps[c]);$display("ACK_SENT case=%0d t=%0.6f gap_ns=%0.6f oen=%b since_drive_release_ns=%0.6f",c,$realtime,$realtime-last_eop,phy_oen,$realtime-last_drive_release);
  send_ack();#1200;
  $display("RESULT case=%0d gap_ns=%0.3f rxbytes=%0d rxacks=%0d rxerrors=%0d overlap_samples=%0d unknown_samples=%0d mismatch_samples=%0d",c,gaps[c],rxbytes-before_bytes,rxacks-before_acks,rxerrors-before_errors,overlap_samples-before_overlap,unknown_samples-before_unknown,mismatch_samples-before_mismatch);
  if(rxbytes-before_bytes!=rxacks-before_acks||rxacks-before_acks>1)$fatal(1,"Unexpected UTMI data");
 end
 $display("DONE phase=%0.9f txpackets=%0d rxbytes=%0d rxacks=%0d rxerrors=%0d framing=%0d first_k_bad=%0d tail_bad=%0d",phase,txpackets,rxbytes,rxacks,rxerrors,framing,first_k_bad,tail_bad);
 $finish;
end
initial begin #100000;$fatal(1,"Turnaround watchdog");end
endmodule
