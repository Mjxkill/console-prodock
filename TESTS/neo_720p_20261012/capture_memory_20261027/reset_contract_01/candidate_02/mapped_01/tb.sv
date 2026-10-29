`timescale 1ns/1ps
module tb;
 reg clk=0,bus80=0,rtc=0,locked=0,ready=0,rx=1;
 reg ref_run=1,bus_run=1;
 wire por,done,holding;wire available=locked&&ready;
 exact_chain dut(.clk(clk),.bus80_clk(bus80),.rtc_clk(rtc),.pll_ae350_lock(locked),.ddr_init(ready),.uart_rx(rx),.por_n(por),.trial_done_o(done),.trial_holding_o(holding));
 GSR GSR(.GSRI(1'b1));
 wire rp,rd,rh;
 exact_chain_rtl reference(.clk(clk),.bus80_clk(bus80),.rtc_clk(rtc),.pll_ae350_lock(locked),.ddr_init(ready),.uart_rx(rx),.por_n(rp),.trial_done_o(rd),.trial_holding_o(rh));
 always @(posedge clk or posedge bus80 or negedge locked or negedge ready) begin
  #0.002;
  if({por,done,holding,dut.trial_request,dut.trial_epoch,dut.trial_mode} !==
     {rp,rd,rh,reference.trial_request,reference.trial_epoch,reference.trial_mode})
   $fatal(1,"Mapped/RTL reset cone mismatch at %0t",$time);
 end
 integer phase_ps=1000,quick=0,case_id=0,result_fd,releases=0;
 realtime last_lock_rise=0,last_available_rise=0,last_hold_end=0;
 realtime last_por_rise=0,last_policy_elapsed=0,anchor=0;
 initial begin if($value$plusargs("PHASE_PS=%d",phase_ps))begin end
  #(phase_ps/1000.0);bus80=1;forever begin #6.25;if(bus_run)bus80=~bus80;else bus80=0;end end
 initial begin #20;clk=1;forever begin #10;if(ref_run)clk=~clk;else clk=0;end end
 always #50 rtc=~rtc;
 always @(posedge locked)last_lock_rise=$realtime;
 always @(posedge available)last_available_rise=$realtime;
 always @(negedge holding)last_hold_end=$realtime;
 always @(posedge por) begin : release_check
  realtime origin,window,rise_time;
  rise_time=$realtime;#0.001;
  if(!por)$fatal(1,"Zero-delta release observed case%0d",case_id);
  if(!available||!done||holding||!dut.trial_request)$fatal(1,"Unqualified POR release case%0d",case_id);
  if(rise_time-last_lock_rise<2000000.0)$fatal(1,"LOCK_2MS_VIOLATION case%0d delta_ns=%0.3f",case_id,rise_time-last_lock_rise);
  origin=last_available_rise>last_hold_end?last_available_rise:last_hold_end;
  window=dut.u_reset_trial.delay_mode?50000000.0:2080000.0;
  if(rise_time-origin<window)$fatal(1,"MODE_WINDOW_VIOLATION case%0d delta_ns=%0.3f required=%0.3f",case_id,rise_time-origin,window);
  releases=releases+1;last_por_rise=rise_time;last_policy_elapsed=rise_time-origin;
  $fwrite(result_fd,"RELEASE,%0d,%0.3f,%0.3f,%0.3f,%0d,%0d\n",case_id,rise_time,rise_time-last_lock_rise,last_policy_elapsed,dut.u_reset_trial.delay_mode,done);$fflush(result_fd);
 end
 task await_release;
  begin wait(por===1'b1);#0.01;if(!done||holding||!available)$fatal(1,"Bad release state");end
 endtask
 task align_reference;
  begin @(posedge clk);anchor=$realtime;end
 endtask
 task loss(input integer id,input realtime offset_ns,input realtime width_ns,input integer ddr);
  integer old_releases;
  begin
   case_id=id;old_releases=releases;align_reference();
   #(offset_ns);if(ddr)ready=0;else locked=0;
   #0.002;if(por)$fatal(1,"Loss failed to assert reset case%0d",id);
   #(width_ns-0.002);if(ddr)ready=1;else locked=1;
   #200;if(por||dut.trial_request)$fatal(1,"Premature post-loss permission case%0d",id);
   await_release();
   if(releases!=old_releases+1)$fatal(1,"Extra or missing POR pulse case%0d",id);
   $fwrite(result_fd,"CASE,%0d,%0.3f,%0.3f,%0d\n",id,offset_ns,width_ns,ddr);$fflush(result_fd);
  end
 endtask
 task ddr_rearm;
  begin ready=0;#200;if(por||done)$fatal(1,"DDR rearm failed");ready=1;end
 endtask
 task byte_tx(input [7:0]b);
  integer k;
  begin
   @(negedge clk);rx=0;repeat(25)@(negedge clk);
   for(k=0;k<8;k=k+1)begin rx=b[k];repeat(25)@(negedge clk);end
   rx=1;repeat(25)@(negedge clk);
  end
 endtask
 task command(input [7:0]mode,input [7:0]check);
  begin byte_tx('ha5);byte_tx('h5a);byte_tx('h52);byte_tx('h31);byte_tx('h35);byte_tx(mode);byte_tx(check);byte_tx('h0d);repeat(10)@(negedge clk);end
 endtask
 initial begin
  result_fd=$fopen("events.csv","w");if(!result_fd)$fatal(1,"Output open failed");
  if($value$plusargs("QUICK=%d",quick))begin end
  #211;locked=1;#177;ready=1;await_release();
  loss(1,6,8,0);loss(2,16,8,0);
  if(!quick)begin
   loss(3,2,1,0);loss(4,4,4,0);loss(5,12,6,0);loss(6,3,30,0);
   case_id=7;ddr_rearm();#500000;align_reference();#6;locked=0;#8;locked=1;await_release();
   case_id=8;ddr_rearm();wait(dut.u_reset_trial.wait_count==2499990);align_reference();#6;locked=0;#8;locked=1;await_release();
   // Invalid complement and expired parser prefix must not reset or change mode.
   case_id=9;command(0,8'hfe);
   if(dut.u_reset_trial.command_epoch!=0||!por||holding||!dut.u_reset_trial.delay_mode)$fatal(1,"Invalid command accepted");
   byte_tx('ha5);byte_tx('h5a);repeat(100100)@(negedge clk);
   byte_tx('h52);byte_tx('h31);byte_tx('h35);byte_tx(0);byte_tx('hff);byte_tx('h0d);repeat(10)@(negedge clk);
   if(dut.u_reset_trial.command_epoch!=0||!por||holding)$fatal(1,"Expired command accepted");
   case_id=10;command(0,8'hff);
   if(dut.u_reset_trial.command_epoch!=1||dut.u_reset_trial.delay_mode||por)$fatal(1,"Mode0 command failed");
   await_release();if(last_policy_elapsed>2100000.0)$fatal(1,"Mode0 no longer short diagnostic interval");
   loss(11,6,8,0);if(last_policy_elapsed>2100000.0)$fatal(1,"Mode0 recovery interval too long");
   case_id=12;command(1,8'hfe);
   if(dut.u_reset_trial.command_epoch!=2||!dut.u_reset_trial.delay_mode||por)$fatal(1,"Mode1 command failed");await_release();
   // An AHB stop cannot prevent reset assertion or release the CPU without edges.
   case_id=13;@(negedge bus80);bus_run=0;command(1,8'hfe);
   if(dut.u_reset_trial.command_epoch!=3||por)$fatal(1,"Stopped AHB lost warm reset");
   #50200000;if(por||!done)$fatal(1,"Stopped AHB release/qualification invalid");bus_run=1;await_release();
   // Capture a LOCK loss even while the reference clock and qualifier are stopped.
   case_id=14;@(negedge clk);ref_run=0;#6;locked=0;#8;locked=1;#2000;
   if(por||dut.trial_request)$fatal(1,"Stopped reference lost asynchronous invalidation");ref_run=1;await_release();
   loss(15,6,8,1);
  end
  if(releases!=(quick?3:15))$fatal(1,"Coverage release count mismatch %0d",releases);
  $fwrite(result_fd,"PASS,%0d,%0d,%0d\n",phase_ps,quick,releases);$fflush(result_fd);
  $display("INVARIANTS_PASS phase_ps=%0d quick=%0d releases=%0d",phase_ps,quick,releases);$fclose(result_fd);$finish;
 end
 initial begin #1200000000;$fatal(1,"Global1.2s timeout");end
endmodule
