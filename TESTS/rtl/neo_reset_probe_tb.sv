`timescale 1ns/1ps
module neo_reset_probe_tb;
    reg clk=0,run_clock=1,resetn=0;
    always #10 if(run_clock)clk=~clk;
    wire [3:0] copies,seen;
    wire [1:0] reference_reset;
    wire [31:0] errors;
    wire [63:0] signatures;
    neo_reset_probe_core #(.BASE_WIDTH(32)) dut(.clk(clk),.resetn(resetn),
        .reset_copies(copies),.reference_reset(reference_reset),
        .mismatch_seen(seen),.mismatch_cycles(errors),.signatures(signatures));
    integer trials;
    initial begin
        #31;
        for(trials=0;trials<20;trials=trials+1)begin
            resetn=0;#(43+trials);
            if(copies!==0)$fatal(1,"Async assertion missing");
            resetn=1;repeat(400)@(negedge clk);
            if(copies!==15 || seen!==0 || errors!==0)$fatal(1,"Clean release failed");
            run_clock=0;#3;resetn=0;#7;
            if(copies!==0)$fatal(1,"Stopped-clock assertion failed");
            #19;resetn=1;#101;
            if(copies!==0)$fatal(1,"Release happened without a clock");
            run_clock=1;repeat(10)@(negedge clk);
        end
        // Check that the observation detects, and retains, an actual fault.
        force dut.reset_copies[2]=1'b0;
        repeat(4)@(negedge clk);
        if(seen!==4 || errors==0)$fatal(1,"Injected fault was not detected");
        release dut.reset_copies[2];
        resetn=0;repeat(4)@(negedge clk);resetn=1;
        repeat(10)@(negedge clk);
        if(seen!==4)$fatal(1,"Reset erased diagnostic evidence");
        $display("PASS: 20 asynchronous phases, stopped clock, injected fault retained");
        $finish;
    end
    initial begin #1000000;$fatal(1,"Timeout");end
endmodule
