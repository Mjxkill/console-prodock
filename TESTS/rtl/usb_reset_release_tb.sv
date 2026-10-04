`timescale 1ns/1ps
module usb_reset_release_tb;
    reg clk=0,run_clock=1,locked=0;
    always #5 if(run_clock)clk=~clk;
    wire reset;
    usb_reset_release #(.HOLD_CYCLES(4)) dut(.*);
    task release_lock;
        @(negedge clk);locked=1;
        // Two synchronizer clocks, then four stable qualification clocks.
        repeat(5)begin @(posedge clk);#1;if(!reset)$fatal(1,"early release");end
        @(posedge clk);#1;if(reset)$fatal(1,"no release");
        repeat(8)begin @(posedge clk);#1;if(reset)$fatal(1,"reset bounced");end
    endtask
    initial begin
        #1;if(!reset)$fatal(1,"unsafe initial reset");
        release_lock();
        // Losing lock must reset even when the generated clock has stopped.
        @(negedge clk);run_clock=0;#2;locked=0;#1;
        if(!reset)$fatal(1,"asynchronous assertion with stopped clock");
        #20;locked=1;#20;if(!reset)$fatal(1,"release without clock");
        locked=0;run_clock=1;
        release_lock();
        // A brief lock pulse must not accumulate toward the next release.
        @(negedge clk);locked=0;#1;if(!reset)$fatal(1,"lock loss");
        @(negedge clk);locked=1;repeat(4)@(negedge clk);
        locked=0;#1;if(!reset)$fatal(1,"short pulse released reset");
        release_lock();
        $display("PASS: synchronized delayed release, asynchronous lock loss, stopped clock, lock glitch and restart");
        $finish;
    end
    initial begin #10000;$fatal(1,"timeout");end
endmodule
