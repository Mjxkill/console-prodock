`timescale 1ns/1ps
module reset_trial_tb;
    reg clk=0, ahb=0, rtc=0, ahb_run=1, rtc_run=1, rx=1;
    always #10 clk=~clk;
    always #6.25 if(ahb_run) ahb=~ahb; else ahb=0;
    always #50 if(rtc_run) rtc=~rtc; else rtc=0;
    reg ready=0, locked=1;
    wire release_request,mode,holding,done,ahb_tick,rtc_tick;
    wire [3:0] epoch;
    reg [1:0] cpu_sync=0;
    always @(posedge ahb or negedge locked)
        if(!locked) cpu_sync<=0; else cpu_sync<={cpu_sync[0],release_request};
    neo_reset_trial dut(.clk_ref(clk),.ahb_clk(ahb),.rtc_clk(rtc),.serial_rx(rx),
        .ddr_ready(ready),.pll_ready(locked),.cpu_reset_n(cpu_sync[1]),
        .release_request(release_request),.delay_mode(mode),.command_epoch(epoch),
        .holding(holding),.delay_done(done),.ahb_tick(ahb_tick),.rtc_tick(rtc_tick));
    task byte_tx(input [7:0] b);
        integer k;
        begin
            @(negedge clk); rx=0; repeat(25) @(negedge clk);
            for(k=0;k<8;k=k+1) begin rx=b[k];repeat(25) @(negedge clk);end
            rx=1;repeat(25) @(negedge clk);
        end
    endtask
    task command(input [7:0] m,input [7:0] complement);
        begin
            byte_tx('ha5);byte_tx('h5a);byte_tx('h52);byte_tx('h31);
            byte_tx('h35);byte_tx(m);byte_tx(complement);byte_tx('h0d);
            repeat(10) @(negedge clk);
        end
    endtask
    integer count;
    reg a0,r0;
    initial begin
        #400000000; $fatal(1,"global timeout");
    end
    initial begin
        repeat(20) @(negedge clk);
        if(release_request||cpu_sync!=0) $fatal(1,"release before DDR ready");
        ready=1;
        // Count from the first cycle on which the synchronized ready is used.
        wait(dut.ready_meta[1]);
        if($bits(dut.wait_count)!=22) $fatal(1,"50 ms needs a 22-bit counter");
        for(count=0;count<2500000;count=count+1) begin
            @(negedge clk);
            if(done||release_request) $fatal(1,"50 ms delay released early at %0d",count);
        end
        @(negedge clk);
        if(!done||!release_request) $fatal(1,"50 ms delay failed to release");
        repeat(10) @(negedge clk);
        if(cpu_sync!=3) $fatal(1,"existing reset flops failed to release");

        command(0,8'hfe); // invalid complement, no reset allowed
        if(epoch!=0||holding||!mode) $fatal(1,"malformed command accepted");
        byte_tx('ha5);byte_tx('h5a);repeat(100100) @(negedge clk);
        byte_tx('h52);byte_tx('h31);byte_tx('h35);byte_tx(0);byte_tx('hff);byte_tx('h0d);
        repeat(10) @(negedge clk);
        if(epoch!=0) $fatal(1,"stale partial command accepted");

        command(0,8'hff);
        if(epoch!=1||mode||!holding) $fatal(1,"short command missing");
        wait(!holding);repeat(10) @(negedge clk);
        if(cpu_sync!=3||!release_request) $fatal(1,"short warm reset not released");
        // Stop AHB with reset already released. The command must stay pending.
        ahb_run=0; command(1,8'hfe);
        repeat(2000) @(negedge clk);
        if(epoch!=2||!holding||release_request) $fatal(1,"reset lost with stopped AHB");
        ahb_run=1;wait(!holding);
        repeat(2499999) @(negedge clk);
        if(release_request) $fatal(1,"long warm reset released early");
        wait(release_request);repeat(10) @(negedge clk);
        if(cpu_sync!=3) $fatal(1,"long warm reset not released");

        ready=0; #1;
        if(release_request) $fatal(1,"calibration loss ignored");
        repeat(10) @(negedge clk);
        if(cpu_sync!=0||done) $fatal(1,"reset not reasserted after DDR loss");
        ready=1;
        wait(dut.ready_meta[1]);
        for(count=0;count<2500000;count=count+1) begin
            @(negedge clk);
            if(done||release_request) $fatal(1,"DDR loss did not restart full 50 ms wait at %0d",count);
        end
        wait(release_request);repeat(100) @(negedge clk);locked=0;
        repeat(10) @(negedge clk);
        if(cpu_sync!=0||done) $fatal(1,"PLL loss ignored");
        locked=1;
        wait(dut.ready_meta[1]);
        for(count=0;count<2500000;count=count+1) begin
            @(negedge clk);
            if(done||release_request) $fatal(1,"PLL loss did not restart full 50 ms wait at %0d",count);
        end
        wait(release_request);
        rtc_run=0;ahb_run=0;repeat(20) @(negedge clk);
        a0=ahb_tick;r0=rtc_tick;repeat(1000) @(negedge clk);
        if(ahb_tick!=a0||rtc_tick!=r0) $fatal(1,"false activity on stopped clocks");
        $display("PASS reset trial: real 50 ms, 22-bit counter, both modes, invalid/expired packets, stopped AHB, PLL/DDR loss restarts wait, independent clock witnesses");
        $finish;
    end
endmodule
