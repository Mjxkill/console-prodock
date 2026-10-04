`timescale 1ns/1ps
// Reuse the complete packet/retry/reset stimuli. Both publication modes
// must retain exactly the direct observer history, delayed by one clock.
module usb_packet_trace_pipeline_tb;
 usb_packet_trace_first_tb s();
 wire [255:0] direct0,delayed0,delayed1;
 reg [255:0] expected0=0,expected1=0;
 usb_packet_trace #(.CAPTURE_FIRST(0)) d0(
  .clk(s.clk),.reset(s.reset),.valid(s.valid),.ready(s.ready),.data(s.data),
  .endpoint(s.endpoint),.cork(s.cork),.active(s.active),.length(s.length),
  .rx_active(s.rx_active),.rx_valid(s.rx_valid),.rx_error(s.rx_error),
  .packet_ack(s.packet_ack),.fifo_pending(s.fifo_pending),.rx_data(s.rx_data),
  .new_packet(s.new_packet),.history(direct0));
 usb_packet_trace #(.CAPTURE_FIRST(0),.INPUT_PIPELINE(1)) p0(
  .clk(s.clk),.reset(s.reset),.valid(s.valid),.ready(s.ready),.data(s.data),
  .endpoint(s.endpoint),.cork(s.cork),.active(s.active),.length(s.length),
  .rx_active(s.rx_active),.rx_valid(s.rx_valid),.rx_error(s.rx_error),
  .packet_ack(s.packet_ack),.fifo_pending(s.fifo_pending),.rx_data(s.rx_data),
  .new_packet(s.new_packet),.history(delayed0));
 usb_packet_trace #(.CAPTURE_FIRST(1),.INPUT_PIPELINE(1)) p1(
  .clk(s.clk),.reset(s.reset),.valid(s.valid),.ready(s.ready),.data(s.data),
  .endpoint(s.endpoint),.cork(s.cork),.active(s.active),.length(s.length),
  .rx_active(s.rx_active),.rx_valid(s.rx_valid),.rx_error(s.rx_error),
  .packet_ack(s.packet_ack),.fifo_pending(s.fifo_pending),.rx_data(s.rx_data),
  .new_packet(s.new_packet),.history(delayed1));
 always @(posedge s.clk or posedge s.reset)
  if(s.reset)begin expected0<=0;expected1<=0;end
  else begin expected0<=direct0;expected1<=s.history;end
 always @(negedge s.clk)begin
  #0.001;
  if(delayed0!==expected0 || delayed1!==expected1)
   $fatal(1,"Pipeline changed packet history");
 end
endmodule
