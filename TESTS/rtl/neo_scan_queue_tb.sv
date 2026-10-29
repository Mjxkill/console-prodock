`timescale 1ns/1ps
module neo_scan_queue_tb;
    reg clk=0,resetn=0,in_valid=0,out_ready=0;
    reg [28:0] in_addr=0;
    wire in_ready,out_valid;
    wire [28:0] out_addr;
    neo_scan_queue dut(.*);
    bit [28:0] expected[$];
    bit held=0,producer_pending=0;
    bit [28:0] held_addr,producer_addr;
    int accepted=0,delivered=0,cancelled=0,simultaneous=0,full=0,resets=0;
    int unsigned random_state=138;
    function automatic int unsigned random_word();
        random_state^=random_state<<13;
        random_state^=random_state>>17;
        random_state^=random_state<<5;
        return random_state;
    endfunction
    task automatic cycle(input bit send,input bit consume);
        bit push,pop;
        bit [28:0] wanted;
        if(send && !producer_pending)begin
            producer_pending=1;producer_addr=29'(random_word());
        end
        in_valid=producer_pending;in_addr=producer_addr;out_ready=consume;
        #5;
        if(held && (!out_valid || out_addr!==held_addr))$fatal(1,"Stalled request changed");
        push=in_valid && in_ready;pop=out_valid && out_ready;
        if(out_valid && expected.size()==0)$fatal(1,"Spurious request");
        if(out_valid && out_addr!==expected[0])$fatal(1,"Request order/data mismatch actual=%h expected=%h accepted=%0d delivered=%0d queued=%0d",out_addr,expected[0],accepted,delivered,expected.size());
        if(pop)begin
            wanted=expected.pop_front();
            if(out_addr!==wanted)$fatal(1,"Accepted request mismatch");
            delivered++;
        end
        if(push)begin expected.push_back(in_addr);producer_pending=0;accepted++;end
        if(push && pop)simultaneous++;
        if(in_valid && !in_ready)full++;
        if(expected.size()>2)$fatal(1,"Queue overflow");
        held=out_valid && !out_ready;held_addr=out_addr;
        clk=1;#5;clk=0;
    endtask
    task automatic reset_stopped;
        // Assert/deassert reset without any memory-clock edge. No queued
        // request may escape, including before the clock starts again.
        resetn=0;#3;
        if(out_valid || in_ready)$fatal(1,"Reset did not gate handshake");
        cancelled+=expected.size();expected.delete();held=0;producer_pending=0;
        in_valid=0;out_ready=1;#31;resetn=1;#19;
        if(out_valid || in_ready)$fatal(1,"Reset released without clock");
        repeat(4)cycle(0,1);
        if(out_valid)$fatal(1,"Pre-reset request replayed");
        resets++;
    endtask
    initial begin
        void'($value$plusargs("seed=%d",random_state));
        reset_stopped();
        // Full and stalled, drain, continuous one-per-cycle replacement.
        repeat(10)cycle(1,0);
        repeat(12)cycle(0,1);
        repeat(100)cycle(1,1);
        for(int i=0;i<24000;i++)begin
            if(i%503==0)reset_stopped();
            cycle((random_word()%4)!=0,(random_word()%5)!=0);
        end
        repeat(10)cycle(0,1);
        if(expected.size()!=0 || producer_pending || accepted!=delivered+cancelled)
            $fatal(1,"Unaccounted request");
        if(simultaneous<1000 || full<100 || resets<40)$fatal(1,"Insufficient coverage");
        $display("PASS accepted=%0d delivered=%0d cancelled=%0d simultaneous=%0d stalled=%0d resets=%0d",accepted,delivered,cancelled,simultaneous,full,resets);
        $finish;
    end
endmodule
