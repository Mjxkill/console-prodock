`timescale 1ns/1ps
module gpu_texture_refill_tb;
    reg clk=0;
    always #5 clk=~clk;
    reg rst=1,invalidate=0,start=0,ready=0,rd_valid=0;
    reg [29:0] byte_address=0;
    reg [255:0] rd_data=0;
    wire busy,done,valid;
    wire [15:0] texel;
    wire [31:0] hits,misses;
    wire [28:0] addr;
    gpu_texture_cache dut(.*);
    integer checks=0;
    integer issued=0;
    function automatic [15:0] expected(input [29:0] address);
        expected=16'h53ac ^ address[16:1] ^ {address[24:17],address[29:22]};
    endfunction
    function automatic [255:0] burst(input [29:0] address);
        reg [255:0] result;
        for(integer lane=0;lane<16;lane=lane+1)
            result[lane*16+:16]=expected({address[29:5],5'b0}+30'(lane*2));
        return result;
    endfunction
    // All nonresponse cycles deliberately change the bus, including the
    // cycle immediately after RD_VALID. The oracle depends only on address.
    task automatic idle_bus;
        rd_data={rd_data[254:0],~rd_data[255]};
    endtask
    task automatic request(input [29:0] address,input bit miss,input integer latency);
        integer waits;
        reg [31:0] old_hits,old_misses;
        old_hits=hits;old_misses=misses;
        @(negedge clk);byte_address=address;start=1;idle_bus();
        @(negedge clk);start=0;
        waits=0;
        while(!valid && !done)begin
            idle_bus();@(negedge clk);waits++;
            if(waits>12)$fatal(1,"No cache response/request");
        end
        if(miss)begin
            if(!valid || done || addr!={1'b0,address[29:5],3'b0})$fatal(1,"Miss request/address");
            // READY stalls must not cause duplicate requests or consume data.
            repeat(3)begin
                idle_bus();@(negedge clk);
                if(!valid || done)$fatal(1,"Request lost while stalled");
            end
            ready=1;rd_valid=(latency==0);rd_data=burst(address);issued++;
            @(negedge clk);ready=0;rd_valid=0;idle_bus();
            if(latency>0)begin
                repeat(latency)begin idle_bus();@(negedge clk);end
                rd_valid=1;rd_data=burst(address);
                @(negedge clk);rd_valid=0;idle_bus();
            end
            waits=0;
            while(!done)begin
                idle_bus();@(negedge clk);waits++;
                if(waits>8)$fatal(1,"Refill did not finish");
            end
            if(misses!=old_misses+1 || hits!=old_hits)$fatal(1,"Miss counters");
        end else begin
            if(valid || !done || hits!=old_hits+1 || misses!=old_misses)$fatal(1,"Expected hit");
        end
        if(texel!==expected(address))$fatal(1,"Texel %h expected %h at %h",texel,expected(address),address);
        checks++;
        @(negedge clk);idle_bus();
        if(done || busy || valid)$fatal(1,"Cache did not become idle");
    endtask
    initial begin
        repeat(4)@(negedge clk);rst=0;
        // Earliest response (same edge as READY), then delayed responses;
        // inspect all 16 lanes after each fill, including XOR-index aliases.
        for(integer testno=0;testno<32;testno++)begin
            request(30'h1700000+30'(testno*32),1,testno%4);
            for(integer lane=0;lane<16;lane++)
                request(30'h1700000+30'(testno*32+lane*2),0,0);
        end
        @(negedge clk);invalidate=1;
        @(negedge clk);invalidate=0;
        request(30'h170000e,1,0);
        request(30'h170001c,0,0);
        // Reset cancels an outstanding request. An unrelated response after
        // reset may update the private bus capture but cannot publish a line.
        @(negedge clk);byte_address=30'h1720200;start=1;
        @(negedge clk);start=0;
        wait(valid);@(negedge clk);rst=1;ready=1;rd_valid=1;rd_data='1;
        repeat(3)@(negedge clk);rst=0;ready=0;
        repeat(3)begin idle_bus();@(negedge clk);if(done || valid || busy)$fatal(1,"Reset replay");end
        rd_valid=0;
        request(30'h1720200,1,1);
        request(30'h172021e,0,0);
        $display("PASS texture refill: checks=%0d misses_issued=%0d earliest/delayed responses, changing idle data, invalidate, reset",checks,issued);
        $finish;
    end
    initial begin #1000000;$fatal(1,"Timeout");end
endmodule
