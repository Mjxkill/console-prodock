`timescale 1ns/1ps
module neo_gpu_response_tb;
 GSR GSR(.GSRI(1'b1));
    reg clk=0, running=1, resetn=0, in_valid=0;
    reg [255:0] in_data=0;
    wire out_valid;
    wire [255:0] out_data;
    always #5 if(running)clk=~clk;
    neo_gpu_response dut(.*);
    integer received=0, holes=0, seed=138, sequence_number=0;
    reg [255:0] expected;
    task beat(input bit valid);
        @(negedge clk);
        in_valid=valid;
        for(integer i=0;i<8;i++)in_data[i*32+:32]=$urandom();
        expected=in_data;
        @(posedge clk);#1;
        if(out_valid!==valid)$fatal(1,"Lost or unsolicited beat %0d",sequence_number);
        if(valid && out_data!==expected)$fatal(1,"Payload shifted or corrupt");
        received+=valid;holes+=!valid;sequence_number++;
    endtask
    initial begin
        repeat(3)@(negedge clk);resetn=1;
        repeat(3)@(negedge clk);
        for(integer epoch=0;epoch<5;epoch++)begin
            // Full-rate bursts, holes, and every data bit exercised.
            repeat(256)beat(1);
            repeat(2000)beat(sequence_number%4!=0);
            // Invalidate a resident response asynchronously with no clocks.
            @(negedge clk);running=0;#2;resetn=0;#1;
            if(out_valid)$fatal(1,"Valid survived reset while clock stopped");
            in_valid=0;#21;resetn=1;#21;
            if(out_valid)$fatal(1,"Old response replayed before clock restart");
            running=1;
            repeat(4)begin @(posedge clk);#1;if(out_valid)$fatal(1,"Old response replayed after reset");end
        end
        if(received!=8780 || holes!=2500)$fatal(1,"Missing burst/bubble coverage");
        $display("PASS GPU response: %0d beats, %0d bubbles, 5 stopped-clock resets",received,holes);
        $finish;
    end
    initial begin #500000;$fatal(1,"Timeout");end
endmodule
