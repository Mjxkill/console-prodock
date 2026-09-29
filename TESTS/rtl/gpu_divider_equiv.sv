`timescale 1ns/1ps
// Reference: unchanged gpu_triangle_floor_div from gpu_l11_r14/source,
// renamed gpu_triangle_floor_div_reference (no arithmetic edits).
module gpu_divider_equiv;
    reg clk=0,rst=1,start=0;
    always #5 clk=~clk;
    reg signed [35:0] numerator=0;
    reg [16:0] denominator=1;
    wire done,reference_done;
    wire signed [35:0] quotient,reference_quotient;
    wire [16:0] remainder,reference_remainder;
    reg [63:0] rng=64'hc01150e120260929;
    integer n,cycles=0,completed=0;
    gpu_triangle_floor_div dut(.*);
    gpu_triangle_floor_div_reference ref_div(.clk(clk),.rst(rst),.start(start),
        .numerator(numerator),.denominator(denominator),.done(reference_done),
        .quotient(reference_quotient),.remainder(reference_remainder));
    always @(negedge clk) if(!rst) begin
        cycles=cycles+1;
        if(done!==reference_done) $fatal(1,"Divider completion timing changed");
        if(done) begin
            if(quotient!==reference_quotient || remainder!==reference_remainder)
                $fatal(1,"Divider mismatch N=%d D=%d",numerator,denominator);
            completed=completed+1;
        end
    end
    task divide(input signed [35:0] num,input [16:0] den);
        @(posedge clk); #1; numerator=num;denominator=den;start=1;
        @(posedge clk); #1;start=0;
        wait(done); @(posedge clk); #1;
    endtask
    initial begin
        repeat(4) @(posedge clk); #1; rst=0;
        for(n=0;n<12000;n=n+1) begin
            rng=rng^(rng<<13);rng=rng^(rng>>7);rng=rng^(rng<<17);
            case(n%8)
                0: divide(36'sh800000000,rng[16:0]);
                1: divide(36'sh7ffffffff,rng[16:0]);
                2: divide(-36'sd1,rng[16:0]);
                3: divide(0,rng[16:0]);
                4: divide(rng[35:0],1);
                5: divide(rng[35:0],17'h1ffff);
                6: divide(rng[35:0],0); // Even the old undefined-input behavior is preserved.
                7: divide(rng[35:0],rng[63:47]);
            endcase
        end
        if(completed!=12000) $fatal(1,"Missing division results");
        $display("Divider equivalence PASS: %0d divisions, %0d cycles",completed,cycles);
        $finish;
    end
endmodule
