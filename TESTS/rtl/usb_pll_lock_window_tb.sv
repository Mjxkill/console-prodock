// Exact reset-release instances are extracted from console_top by the runner.
// The PLL outputs and LOCK flags are digital stimuli, not analog PLL models.
`timescale 1ns/1fs
module usb_pll_lock_window_tb;
parameter integer GUARD_STAGE=2; // 0=reference counter, 1=PHY counter, 2=both
parameter integer REF_HOLD=104000, PHY_HOLD=104000, CONTROLLER_HOLD=64;
parameter integer REF_QUAL_MHZ=50, PHY_QUAL_MHZ=50;
reg clk=0,clk48=0,phy_clk=0,run_outputs=1;
reg pll_f_lock=0,pll_b_lock=0;
wire pll_b_reset,phy_lock_reset,rst_usb;
reg PHY_RESET=0; // Public controller output may remain low with its clock stopped.
wire qualified_phy_lock,combined_phy_reset;
realtime since;
integer qualifiers=0;
always #10 clk=~clk;
always #(500.0/48.0) if(run_outputs)clk48=~clk48;
always #(500.0/60.0) if(run_outputs)phy_clk=~phy_clk;
usb_top_lock_chain_model dut(.*);

task assert_resets;
 begin
  #0.001;
  if(!pll_b_reset || !phy_lock_reset || !rst_usb)
   $fatal(1,"LOCK loss failed to assert the complete reset chain");
  if(GUARD_STAGE==2 && (qualified_phy_lock || !combined_phy_reset))
   $fatal(1,"HS PHY pins did not follow asynchronous common reset");
 end
endtask

task qualified(input integer which,input integer scenario,input realtime began);
 integer count,limit;
 realtime elapsed,maximum;
 begin
  count=0;
  limit=(which?PHY_HOLD:REF_HOLD)*3+100;
  while((which?phy_lock_reset:pll_b_reset)!==1'b0 && count<limit)begin
   @(posedge clk);#0.001;count++;
  end
  if((which?phy_lock_reset:pll_b_reset)!==1'b0)$fatal(1,"qualification never completed");
  elapsed=$realtime-began;
  $display("RELEASE stage=%0d scenario=%0d elapsed_ns=%0.6f ref_clk_edges=%0d",which,scenario,elapsed,count);
  if((GUARD_STAGE==2 || GUARD_STAGE==which) && elapsed<2000000.0)
   $fatal(1,"LOCK released before 2 ms: stage=%0d elapsed_ns=%0.6f",which,elapsed);
  maximum=((which?PHY_HOLD:REF_HOLD)+4)*1000.0/(which?PHY_QUAL_MHZ:REF_QUAL_MHZ);
  if(elapsed>maximum)$fatal(1,"qualification was unexpectedly delayed: %0.6f > %0.6f",elapsed,maximum);
  qualifiers++;
 end
endtask

task controller_released;
 integer edges;
 begin
  edges=0;
  while(rst_usb!==1'b0 && edges<CONTROLLER_HOLD+5)begin
   @(posedge phy_clk);#0.001;edges++;
  end
  if(rst_usb!==1'b0)$fatal(1,"controller reset not released");
  if(edges<CONTROLLER_HOLD || edges>CONTROLLER_HOLD+2)
   $fatal(1,"controller qualification unexpected: %0d edges",edges);
  if(!qualified_phy_lock || combined_phy_reset!==PHY_RESET)
   $fatal(1,"HS PHY inputs did not follow synchronized release");
  $display("CONTROLLER_RELEASE phy_edges=%0d",edges);
 end
endtask

initial begin
 assert_resets();repeat(4)@(negedge clk);
 pll_f_lock=1;since=$realtime;qualified(0,0,since);
 @(negedge clk);pll_b_lock=1;since=$realtime;qualified(1,0,since);
 controller_released();

 // Late glitches in BOTH acquisitions must restart the full 2 ms window.
 @(negedge clk);pll_f_lock=0;pll_b_lock=0;assert_resets();
 @(negedge clk);pll_f_lock=1;
 #1500000.0;if(!pll_b_reset)$fatal(1,"reference reset released before late glitch");
 pll_f_lock=0;assert_resets();
 #0.731;pll_f_lock=1;since=$realtime;qualified(0,1,since);
 @(negedge clk);pll_b_lock=1;
 #1500000.0;if(!phy_lock_reset)$fatal(1,"PHY reset released before late glitch");
 pll_b_lock=0;#0.001;
 if(!phy_lock_reset || !rst_usb)$fatal(1,"PLL_B late glitch not propagated");
 #0.731;pll_b_lock=1;since=$realtime;qualified(1,1,since);
 controller_released();

 // Independent 50 MHz reference continues while both PLL outputs stop.
 @(negedge phy_clk);run_outputs=0;
 #1.371;pll_f_lock=0;pll_b_lock=0;assert_resets();
 #17.219;pll_f_lock=1;since=$realtime;qualified(0,2,since);
 if(!rst_usb)$fatal(1,"controller released without its clock");
 @(negedge clk);pll_b_lock=1;since=$realtime;qualified(1,2,since);
 // 2.5 ms of wall-clock time must not substitute for the 64 PHY clock edges.
 #2500000.0;
 if(pll_b_reset || phy_lock_reset || !rst_usb || qualified_phy_lock || !combined_phy_reset)
  $fatal(1,"independent reference / stopped output-clock contract violated");
 run_outputs=1;controller_released();
 repeat(10)@(negedge clk);
 if(pll_b_reset || phy_lock_reset || rst_usb)$fatal(1,"restart not stable");
 $display("PASS PLL LOCK chain: %0d qualifications >=2 ms, two late glitches, LOCK loss without PLL output clocks, independent reference progress and 64-cycle safe restart",qualifiers);
 $finish;
end
initial begin #30000000;$fatal(1,"timeout");end
endmodule
