`timescale 1ns/1ps
module neo_ddr_startup_tb;
`ifdef MAPPED
    GSR GSR(.GSRI(1'b1));
`endif
    reg ref_clk=0, cpu_clk=0, run_ref=1, run_cpu=1;
    real cpu_half=6.25;
    initial begin
        if ($value$plusargs("CPU_HALF=%f", cpu_half)) begin end
        forever begin #(cpu_half); if(run_cpu)cpu_clk=~cpu_clk; end
    end
    always #10 if(run_ref)ref_clk=~ref_clk;
    reg resetn=0, pll_locked=0, calib_complete=0;
    wire ip_resetn,cpu_resetn;
    neo_ddr_startup dut(.*);
    integer checks=0;
    task check(input bit ok,input string message);
        begin if(!ok)$fatal(1,"%s at %t",message,$time);checks=checks+1;end
    endtask
    task wait_ip;
        integer n;
        begin
            n=0;
            while(!ip_resetn && n<1100)begin @(posedge ref_clk);#1;n=n+1;end
            check(ip_resetn,"IP reset never released");
            check(n>=1024,"IP reset hold too short");
        end
    endtask
    initial begin
        // Startup may release off either clock edge. DDR memory/UI clocks
        // are intentionally absent: they cannot be a startup dependency.
        #3;check(!ip_resetn && !cpu_resetn,"power-up reset missing");
        #34;resetn=1;
        repeat(1100)@(posedge ref_clk);#1;
        check(!ip_resetn,"controller released without PLL lock");
        pll_locked=1;wait_ip();
        repeat(5)@(posedge cpu_clk);#1;
        check(!cpu_resetn,"CPU released before calibration");
        @(negedge cpu_clk);#1;calib_complete=1;
        @(posedge cpu_clk);#1;check(!cpu_resetn,"CPU release lacks two stages");
        @(posedge cpu_clk);#1;check(cpu_resetn,"CPU release failed");
        @(negedge cpu_clk);run_cpu=0;#3;pll_locked=0;#1;
        check(!cpu_resetn,"CPU reset needs running CPU clock on lock loss");
        check(!ip_resetn,"PLL loss does not restart controller calibration");
        pll_locked=1;wait_ip();#100;
        check(!cpu_resetn,"CPU release occurred with stopped CPU clock");
        run_cpu=1;repeat(3)@(posedge cpu_clk);#1;check(cpu_resetn,"CPU recovery failed");
        #2;calib_complete=0;#1;check(!cpu_resetn,"stale calibration leaves CPU running");
        calib_complete=1;repeat(3)@(posedge cpu_clk);#1;
        check(cpu_resetn,"calibration recovery failed");
        @(negedge ref_clk);run_ref=0;
        #3;resetn=0;#1;check(!ip_resetn && !cpu_resetn,"reset assertion needs reference clock");
        #7;resetn=1;#100;
        check(!ip_resetn && !cpu_resetn,"reset released while reference clock stopped");
        run_ref=1;wait_ip();repeat(3)@(posedge cpu_clk);#1;
        check(cpu_resetn,"restart after stopped reference failed");
        // A short reset between reference edges must restart the full hold.
        @(negedge ref_clk);#2;resetn=0;#2;resetn=1;#1;
        check(!ip_resetn && !cpu_resetn,"short external reset lost");
        wait_ip();repeat(3)@(posedge cpu_clk);#1;
        check(cpu_resetn,"restart after short reset failed");
        $display("PASS DDR startup: %0d checks CPU_HALF=%f",checks,cpu_half);$finish;
    end
    initial begin #200000;$fatal(1,"timeout");end
endmodule
