`timescale 1ns/1ps
module tb;
 reg fast=0, resetn=0, gsrn=0;
 wire ui;
 GSR GSR(.GSRI(gsrn));
 CLKDIV #(.DIV_MODE("4")) dut(.HCLKIN(fast),.RESETN(resetn),.CALIB(1'b0),.CLKOUT(ui));
 always #1.25 fast=~fast;
 realtime released, delay_ns;
 integer phase;
 initial begin
   #10; gsrn=1;
   for(phase=1;phase<2500;phase=phase+25) begin
     @(negedge fast); resetn=0;
     repeat(5) @(negedge fast);
     if(ui!==0) $fatal(1,"Clock not held low during reset");
     #(phase/1000.0); resetn=1; released=$realtime;
     @(posedge ui); delay_ns=$realtime-released;
     if(delay_ns<2.499 || delay_ns>5.001) $fatal(1,"Unexpected CLKDIV release latency %f",delay_ns);
     $display("PHASE %0d FIRST_EDGE_NS %0.3f",phase,delay_ns);
     repeat(3) @(posedge ui);
   end
   $display("PASS CLKDIV functional release phase sweep");
   $finish;
 end
 initial begin #100000; $fatal(1,"Timeout"); end
endmodule
