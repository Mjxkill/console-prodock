// Compile with usb_packet_trace_tb.sv and the pre-change observer renamed to
// usb_packet_trace_reference. The reference must be an immutable RTL snapshot.
// Compare every cycle, including arbitrary new_packet pulses ignored by mode0.
`timescale 1ns/1ps
module usb_packet_trace_equiv;
 usb_packet_trace_tb stimulus();
 wire [255:0] expected,with_pulses;
 reg new_packet=0;
 always @(negedge stimulus.clk)new_packet<=~new_packet;
 usb_packet_trace_reference reference(
  .clk(stimulus.clk),.reset(stimulus.reset),.valid(stimulus.valid),.ready(stimulus.ready),
  .data(stimulus.data),.endpoint(stimulus.endpoint),.cork(stimulus.cork),.active(stimulus.active),
  .length(stimulus.length),.rx_active(stimulus.rx_active),.rx_valid(stimulus.rx_valid),
  .rx_error(stimulus.rx_error),.packet_ack(stimulus.packet_ack),.fifo_pending(stimulus.fifo_pending),
  .rx_data(stimulus.rx_data),.history(expected));
 usb_packet_trace #(.CAPTURE_FIRST(0)) pulse_observer(
  .clk(stimulus.clk),.reset(stimulus.reset),.valid(stimulus.valid),.ready(stimulus.ready),
  .data(stimulus.data),.endpoint(stimulus.endpoint),.cork(stimulus.cork),.active(stimulus.active),
  .length(stimulus.length),.rx_active(stimulus.rx_active),.rx_valid(stimulus.rx_valid),
  .rx_error(stimulus.rx_error),.packet_ack(stimulus.packet_ack),.fifo_pending(stimulus.fifo_pending),
  .rx_data(stimulus.rx_data),.new_packet(new_packet),.history(with_pulses));
 always @(negedge stimulus.clk)begin
  #0.001;
  if(stimulus.history!==expected || with_pulses!==expected)
   $fatal(1,"Default trace changed relative to immutable reference");
 end
endmodule
