`timescale 1ns/1ps
// Fault-injection boundary, NOT a model of an observed physical LOCK pulse.
// The first AHB reset detector accepts an event while the raw input observed
// by the qualifier does not change. Require requalification after that event.
module tb;
 reg clk=0, bus80=0, rtc=0, locked=0, ready=0, active=0;
 wire por, done, holding;
 realtime observed_return=0;
 integer releases=0;
 exact_chain dut(.clk(clk), .bus80_clk(bus80), .rtc_clk(rtc),
   .pll_ae350_lock(locked), .ddr_init(ready), .uart_rx(1'b1),
   .por_n(por), .trial_done_o(done), .trial_holding_o(holding));
 always #10 clk=~clk;
 initial begin #3.125;bus80=1;forever #6.25 bus80=~bus80;end
 always #50 rtc=~rtc;
 always @(posedge dut.ae350_por_n) if(active) observed_return=$realtime;
 always @(posedge por) begin
   releases=releases+1;
   if(active) begin
     if(observed_return==0 || $realtime-observed_return<50000000.0)
       $fatal(1,"CAPTURE_ASYMMETRY_STALE_QUALIFICATION delta_ns=%0.3f",$realtime-observed_return);
     $display("CAPTURE_ASYMMETRY_REQUALIFIED delta_ns=%0.3f",$realtime-observed_return);
   end
 end
 initial begin
   #211;locked=1;#177;ready=1;
   wait(por===1'b1);#100;
   if(!done || holding)$fatal(1,"Initial state invalid");
   active=1;
   force dut.ae350_rst_sync=2'b11;
   #0.001;if(por)$fatal(1,"Injected assertion not propagated");
   #30;release dut.ae350_rst_sync;
   wait(por===1'b1);#1;
   if(releases!=2 || !done || !locked || !ready)$fatal(1,"Invalid final state");
   $display("ASYMMETRY_PASS releases=%0d",releases);$finish;
 end
 initial begin #120000000;$fatal(1,"Timeout");end
endmodule
