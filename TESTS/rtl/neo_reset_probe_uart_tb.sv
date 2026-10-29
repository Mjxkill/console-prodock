`timescale 1ns/1ps
module neo_reset_probe_uart_tb;
    reg clk=0;
    always #10 clk=~clk;
    wire tx,led;
    neo_reset_probe dut(.clk(clk),.uart_tx(tx),.led_n(led));
    defparam dut.u_probe.BASE_WIDTH=32;
    task read_byte(output reg [7:0] data);
        begin
            @(negedge tx);
            #750; // 1.5 bit periods; 50 MHz / 25 = 2 Mbaud.
            for(integer i=0;i<8;i++)begin data[i]=tx;#500;end
            if(tx!==1)$fatal(1,"Invalid stop bit");
        end
    endtask
    reg [7:0] data;
    reg [159:0] expected,decoded=0;
    reg [3:0] digit;
    task read_frame;
        @(negedge clk);expected=dut.snapshot;decoded=0;
        read_byte(data);
        if(data!="R")$fatal(1,"Bad frame marker");
        for(integer i=0;i<40;i++)begin
            read_byte(data);
            if(data>="0" && data<="9")digit=data-"0";
            else if(data>="a" && data<="f")digit=data-"a"+10;
            else $fatal(1,"Non-hex UART payload");
            decoded={decoded[155:0],digit};
        end
        read_byte(data);
        if(data!=10 || decoded!==expected || decoded[159:144]!=16'h5251 ||
           decoded[143:140]!=0 || decoded[139:136]!=15 || decoded[129:128]!=3 ||
           decoded[95:64]!=0)$fatal(1,"Invalid/changed diagnostic frame %h expected %h",decoded,expected);
        $display("PASS: atomic 42-byte UART frame %h",decoded);
    endtask
    initial begin
        repeat(1024)@(negedge clk);
        // Skip the reporting timer only; exercise the actual serializer.
        dut.ticks=24'h080000;
        read_frame();
        // Lose the UART and partial frame state after the startup window.
        // A later reset must recover both without erasing the monitor.
        @(negedge clk);
        dut.u_uart.busy=1'bx;dut.u_uart.tx=1'bx;
        dut.sending=1'bx;dut.position=6'bx;
        dut.ticks=24'hfffffe;
        repeat(1024)@(negedge clk);
        if(dut.epoch!=1 || dut.u_uart.ready!==1 || tx!==1 || dut.sending!==0)
            $fatal(1,"UART did not recover at the periodic reset");
        dut.ticks=24'h080000;
        read_frame();
        $display("PASS: telemetry recovers from lost UART/frame state after startup");
        $finish;
    end
    initial begin #1000000;$fatal(1,"Timeout");end
endmodule
