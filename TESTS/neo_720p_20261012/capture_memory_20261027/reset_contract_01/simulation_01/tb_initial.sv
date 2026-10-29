`timescale 1ns/1ps
module tb;
 reg clk=0,bus80=0,rtc=0,locked=0,ready=0,rx=1;
 wire por,done,holding;
 exact_chain dut(.clk(clk),.bus80_clk(bus80),.rtc_clk(rtc),.pll_ae350_lock(locked),.ddr_init(ready),.uart_rx(rx),.por_n(por),.trial_done_o(done),.trial_holding_o(holding));
 integer phase_ps=1000, quick=0, trace_fd, result_fd, case_id=0;
 integer release_count=0, bad_2ms=0,bad_50ms=0;
 integer trace_enable=0;
 realtime last_lock_rise=0,last_ready_rise=0,last_por_rise=0,latest_available=0,anchor=0;
 realtime last_delta_lock=0,last_delta_available=0;
 initial begin if($value$plusargs("PHASE_PS=%d",phase_ps)) begin end
   #(phase_ps/1000.0); bus80=1; forever #6.25 bus80=~bus80; end
 initial begin #20;clk=1;forever #10 clk=~clk;end
 always #50 rtc=~rtc;
 always @(posedge locked) last_lock_rise=$realtime;
 always @(posedge ready) last_ready_rise=$realtime;
 always @(posedge por) begin
   last_por_rise=$realtime; release_count=release_count+1;
   last_delta_lock=$realtime-last_lock_rise;
   latest_available=last_lock_rise>last_ready_rise?last_lock_rise:last_ready_rise;
   last_delta_available=$realtime-latest_available;
   if(last_delta_lock<2000000.0)bad_2ms=bad_2ms+1;
   if(last_delta_available<50000000.0)bad_50ms=bad_50ms+1;
   $fwrite(result_fd,"RELEASE,%0d,%0.3f,%0.3f,%0.3f,%0d,%0d,%0d,%0d\n",case_id,$realtime,last_delta_lock,last_delta_available,done,dut.u_reset_trial.ready_meta,dut.u_reset_trial.wait_count,holding);
 end
 // Record after NBA, not a pre-edge monitor mistaken for settled state.
 always @(posedge clk or posedge bus80 or negedge locked or posedge locked or posedge por or negedge por) begin
   if(trace_enable)begin #0.001;
    $fwrite(trace_fd,"%0d,%0.3f,%0.3f,%b,%b,%b,%b,%b,%b,%b,%0d,%b\n",case_id,$realtime,$realtime-anchor,clk,bus80,locked,ready,dut.ae350_rst_sync,dut.u_soc.init_sync,dut.u_reset_trial.ready_meta,dut.u_reset_trial.wait_count,done);
   end
 end
 task settle_and_check(input integer want_2ms_bad,input integer want_50ms_bad);
  begin
   wait(por===1'b1);#0.1;
   if((last_delta_lock<2000000.0)!=(want_2ms_bad!=0))$fatal(1,"2ms outcome mismatch case%0d delta%0.3f",case_id,last_delta_lock);
   if((last_delta_available<50000000.0)!=(want_50ms_bad!=0))$fatal(1,"50ms outcome mismatch case%0d delta%0.3f",case_id,last_delta_available);
   if(!done||holding||dut.u_reset_trial.delay_mode!==1'b1)$fatal(1,"Unexpected qualification state case%0d",case_id);
  end
 endtask
 task align_reference;
  begin @(posedge clk); while(($time%100)!=0)@(posedge clk);anchor=$realtime;end
 endtask
 task settled_pulse(input integer ident,input realtime off_ns,input realtime width_ns,input integer sampled);
  integer old_rel;realtime delta;
  begin
   case_id=ident;old_rel=release_count;
   align_reference();trace_enable=1;
   #(off_ns);locked=0;#(width_ns);locked=1;
   #200;trace_enable=0;
   if(sampled)begin
    if(done||por||dut.u_reset_trial.wait_count>20)$fatal(1,"Sampled pulse did not restart qualifier case%0d",case_id);
    settle_and_check(0,0);
   end else begin
    if(!done||!por||release_count!=old_rel+1)$fatal(1,"Unseen pulse did not reproduce stale qualification case%0d",case_id);
    if(last_delta_lock>=2000000.0||last_delta_available>=50000000.0)$fatal(1,"Expected recorded property failure case%0d",case_id);
    if(ident==1&&phase_ps==1000&&((last_por_rise-anchor)<63.499||(last_por_rise-anchor)>63.501))$fatal(1,"Canonical edge mismatch %0.3f",last_por_rise-anchor);
   end
   $fwrite(result_fd,"CASE,%0d,%0.3f,%0.3f,%0d,%0.3f,%0.3f,%0d\n",case_id,off_ns,width_ns,sampled,last_delta_lock,last_delta_available,done);
  end
 endtask
 task rearm_by_ddr;
  begin
   ready=0;#200;
   if(por||done)$fatal(1,"Legal DDR loss did not rearm");
   ready=1;
  end
 endtask
 initial begin
  trace_fd=$fopen("trace.csv","w");result_fd=$fopen("events.csv","w");
  if(!trace_fd||!result_fd)$fatal(1,"Output open failed");
  $fwrite(trace_fd,"case,time_ns,relative_ns,clk50,bus80,lock,ddr_ready,rst_sync,init_sync,ready_meta,wait_count,done\n");
  if($value$plusargs("QUICK=%d",quick))begin end
  #211;locked=1;#177;ready=1;
  settle_and_check(0,0);
  if($bits(dut.u_reset_trial.wait_count)!=22)$fatal(1,"Wrong real 50ms counter width");
  $fwrite(result_fd,"BASELINE,0,%0.3f,%0.3f\n",last_delta_lock,last_delta_available);
  settled_pulse(1,6,8,0);
  settled_pulse(2,16,8,1);
  if(!quick)begin
   settled_pulse(3,2,1,0);
   settled_pulse(4,4,4,0);
   settled_pulse(5,12,6,0);
   settled_pulse(6,3,30,1);
   case_id=7;rearm_by_ddr();#500000;align_reference();trace_enable=1;
   #6;locked=0;#8;locked=1;#200;trace_enable=0;
   if(done||por||dut.u_reset_trial.wait_count<24000)$fatal(1,"Early-wait pulse unexpectedly rearmed qualifier");
   settle_and_check(0,1);
   $fwrite(result_fd,"WAITCASE,7,%0.3f,%0.3f\n",last_delta_lock,last_delta_available);
   case_id=8;rearm_by_ddr();
   wait(dut.u_reset_trial.wait_count==2499990);align_reference();trace_enable=1;
   #6;locked=0;#8;locked=1;
   settle_and_check(1,1);#50;trace_enable=0;
   $fwrite(result_fd,"WAITCASE,8,%0.3f,%0.3f\n",last_delta_lock,last_delta_available);
  end
  if(quick)begin
   if(release_count!=3||bad_2ms!=1||bad_50ms!=1)$fatal(1,"Quick coverage mismatch");
  end else begin
   if(release_count!=9||bad_2ms!=5||bad_50ms!=6)$fatal(1,"Full coverage mismatch releases%0d two%0d fifty%0d",release_count,bad_2ms,bad_50ms);
  end
  $fwrite(result_fd,"SUMMARY,%0d,%0d,%0d,%0d,%0d\n",phase_ps,quick,release_count,bad_2ms,bad_50ms);
  $display("REPRODUCTION_PASS phase_ps=%0d quick=%0d releases=%0d observed_2ms_property_failures=%0d observed_50ms_property_failures=%0d",phase_ps,quick,release_count,bad_2ms,bad_50ms);
  $fclose(trace_fd);$fclose(result_fd);$finish;
 end
 initial begin #500000000;$fatal(1,"Global 500ms timeout");end
endmodule
