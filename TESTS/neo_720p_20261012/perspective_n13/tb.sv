`timescale 1ns/1ps
module tb;
reg clk=0,rst=1,start=0;
always #6.666 clk=~clk;
reg signed [48:0] uq,vq,q;
wire done,valid;
wire signed [48:0] tu,tv;
gpu_perspective dut(.*);
wire ref_done,ref_valid;wire signed [48:0] ref_tu,ref_tv;
perspective_reference ref_dut(.clk(clk),.rst(rst),.start(start),.uq(uq),.vq(vq),.q(q),
 .done(ref_done),.valid(ref_valid),.tu(ref_tu),.tv(ref_tv));
always @(negedge clk)if(!rst && {done,valid,tu,tv}!=={ref_done,ref_valid,ref_tu,ref_tv})
 $fatal(1,"Perspective cycle equivalence mismatch");

reg [245:0] vectors[0:2467];
integer count,cycles,max_cycles=0,fast12_count=0;
initial begin
    $readmemh("vectors.hex",vectors);
    repeat(3)@(negedge clk);rst=0;
    for(integer i=0;i<2468;i++)begin
        @(negedge clk);{uq,vq,q}=vectors[i][244:98];start=1;
        @(negedge clk);start=0;cycles=0;
        while(!done && cycles<32)begin @(negedge clk);cycles++;end
        if(!done || valid!==vectors[i][245])$fatal(1,"Validity/timeout case=%0d",i);
        if(valid && {tu,tv}!==vectors[i][97:0])$fatal(1,"Quotient case=%0d U=%0d V=%0d Q=%0d got=%0d,%0d",i,uq,vq,q,tu,tv);
        if(valid && !dut.fast && dut.fast12)begin
            if(cycles!=9)$fatal(1,"12-bit path latency %0d",cycles);
            fast12_count++;
        end
        if(cycles>max_cycles)max_cycles=cycles;
        if(i%100==0)begin
            @(negedge clk);uq=49'sh0ffffffffffff;vq=-uq;q=1;start=1;
            @(negedge clk);start=0;
            repeat(3)@(negedge clk);rst=1;
            repeat(2)@(negedge clk);rst=0;
            repeat(30)begin @(negedge clk);if(done)$fatal(1,"Old result replayed after reset");end
        end
    end
    if(fast12_count==0)$fatal(1,"12-bit path not covered");
    $display("PASS: 2468 signed rational pairs, extrema, zero/negative Q, reset during division; max latency=%0d cycles, 12-bit cases=%0d",max_cycles,fast12_count);
    $finish;
end
endmodule
