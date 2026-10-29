// Signed 64/64 division, truncation toward zero, two quotient bits per cycle.
// 32 radix-4 iterations plus preparation/sign stages. Three parallel subtractors
// avoid the two cascaded compare/subtract chains of a serial two-bit divider.
`default_nettype none
module gpu_geom_div(
    input wire clk,rst,start,
    input wire signed [63:0] numerator,denominator,
    output reg busy,done,invalid,
    output reg signed [63:0] quotient
);
    reg [63:0] divisor,q;
    reg [63:0] remainder;
    reg [65:0] divisor2,divisor3;
    reg negative,bad;
    reg [5:0] steps;
    reg [1:0] stage,digit;
    wire [65:0] shifted={remainder,q[63:62]};
    wire [66:0] sub1={1'b0,shifted}-{3'b0,divisor};
    wire [66:0] sub2={1'b0,shifted}-{1'b0,divisor2};
    wire [66:0] sub3={1'b0,shifted}-{1'b0,divisor3};
    reg [63:0] remainder_next;
    always @* begin
        if(!sub3[66])begin remainder_next=sub3[63:0];digit=3;end
        else if(!sub2[66])begin remainder_next=sub2[63:0];digit=2;end
        else if(!sub1[66])begin remainder_next=sub1[63:0];digit=1;end
        else begin remainder_next=shifted[63:0];digit=0;end
    end
    always @(posedge clk)begin
        done<=0;
        if(rst)begin busy<=0;done<=0;invalid<=0;quotient<=0;divisor<=0;divisor2<=0;divisor3<=0;q<=0;remainder<=0;negative<=0;bad<=0;steps<=0;stage<=0;end
        else if(start && !busy)begin
            divisor<=denominator[63] ? -denominator:denominator;
            q<=numerator[63] ? -numerator:numerator;
            negative<=numerator[63]^denominator[63];remainder<=0;steps<=0;busy<=1;stage<=0;
            bad<=denominator==0 || (numerator==64'h8000000000000000 && denominator==-64'sd1);
            invalid<=0;
        end else if(busy)case(stage)
            0:begin divisor2<={1'b0,divisor,1'b0};divisor3<={2'b0,divisor}+{1'b0,divisor,1'b0};stage<=1;end
            1:begin
                q<={q[61:0],digit};remainder<=remainder_next;steps<=steps+1'b1;
                if(steps==31)stage<=2;
            end
            default:begin busy<=0;done<=1;invalid<=bad;quotient<=bad ? 64'sd0:negative ? -$signed(q):$signed(q);end
        endcase
    end
endmodule
`default_nettype wire
