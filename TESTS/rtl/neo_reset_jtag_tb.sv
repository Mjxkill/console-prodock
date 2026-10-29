`timescale 1ns/1ps
module neo_reset_jtag_tb;
    reg clk=0,run_clock=1,tck=0,tms=1,tdi=0;
    wire tdo,led_n;
    neo_reset_jtag #(.BASE_WIDTH(32),.TICK_WIDTH(12)) dut(.*);
    always #10 if(run_clock)clk=~clk;
    integer half=499,i,k;
    reg dummy;
    reg [162:0] value,again;
    reg [159:0] expected;
    always @(posedge clk)
        if(dut.request_sync[1]!=dut.response_toggle)
            expected<={16'h5251,dut.mismatch_seen,dut.reset_copies,6'd0,dut.reference_reset,
                       dut.epoch,dut.mismatch_cycles,dut.signatures};
    task tick(input reg tm,input reg di,output reg result);
        begin
            tck=0;tms=tm;tdi=di;#(half);result=tdo;tck=1;#(half);tck=0;#1;
        end
    endtask
    task tap_reset;
        begin repeat(8)tick(1,0,dummy);tick(0,0,dummy);end
    endtask
    task select_ir(input reg [4:0] ir);
        integer j;
        begin
            tick(1,0,dummy);tick(1,0,dummy);tick(0,0,dummy);tick(0,0,dummy);
            for(j=0;j<5;j=j+1)tick(j==4,ir[j],dummy);
            tick(1,0,dummy);tick(0,0,dummy);
        end
    endtask
    task scan(input integer width,output reg [162:0] result);
        integer j;
        begin
            result=0;
            tick(1,0,dummy);tick(0,0,dummy);tick(0,0,dummy);
            for(j=0;j<width;j=j+1)tick(j==width-1,0,result[j]);
            tick(1,0,dummy);tick(0,0,dummy);
        end
    endtask
    task snapshot;
        begin
            select_ir(2);repeat(12)tick(0,0,dummy);scan(163,value);
            if(value[162]!==value[161] || value[160]!==1 || value[159:0]!==expected)
                $fatal(1,"Torn or stale snapshot %h expected %h",value,expected);
        end
    endtask
    initial begin
        #37;tap_reset();scan(32,value);
        if(value[31:0]!==32'h1000563d)$fatal(1,"IDCODE %h",value);
        for(k=0;k<12;k=k+1)begin
            half=401+k*17;
            snapshot();
            if(value[143:140]!==0 || value[95:64]!==0)$fatal(1,"Unexpected reset mismatch");
            scan(163,again);
            if(again!==value)$fatal(1,"Snapshot changed without request");
        end
        @(negedge clk);run_clock=0;
        select_ir(2);repeat(12)tick(0,0,dummy);scan(163,value);
        if(value[160]!==0)$fatal(1,"Acknowledged while source clock stopped");
        tap_reset(); // Outstanding request survives host TAP reset.
        run_clock=1;
        repeat(12)tick(0,0,dummy);
        snapshot();
        // Pause TCK after request, then resume: held data must remain coherent.
        select_ir(2);#25197;
        repeat(12)tick(0,0,dummy);scan(163,value);
        if(value[159:0]!==expected || value[160]!==1)$fatal(1,"Stopped TCK mailbox");
        force dut.u_probe.reset_copies[2]=1'b0;
        #200;snapshot();
        if(!value[142] || value[95:64]==0)$fatal(1,"Injected fault missed");
        release dut.u_probe.reset_copies[2];
        #200000;snapshot();
        if(!value[142])$fatal(1,"Fault history lost");
        $display("PASS: JTAG ID, 12 clock phases/rates, held coherent data, stopped clocks, TAP reset and injected fault");
        $finish;
    end
    initial begin #30000000;$fatal(1,"Timeout");end
endmodule
