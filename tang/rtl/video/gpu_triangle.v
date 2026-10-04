// Exact scanline triangle rasterizer: pixel centres, top-left ownership.
// Three edge intersections are seeded by signed floor division, then advanced
// by quotient/remainder DDAs. Work per line is independent of triangle width.
`default_nettype none
module gpu_triangle #(parameter WIDTH=800, HEIGHT=480) (
    input wire clk, rst, start,
    input wire signed [15:0] x0,y0,x1,y1,x2,y2,
    output wire busy, valid,
    input wire ready,
    output reg [10:0] span_x, span_width,
    output reg [9:0] span_y
);
    // Preserve the existing cycles with a shallow one-bit state decode.
    localparam [14:0] IDLE=(15'd1 << 0), BOUNDS=(15'd1 << 1), ORIENT=(15'd1 << 2), EDGES=(15'd1 << 3), PRODUCTS=(15'd1 << 4),
        SEEDS=(15'd1 << 5), DIV_FIRST=(15'd1 << 6), WAIT_FIRST=(15'd1 << 7), DIV_STEP=(15'd1 << 8), WAIT_STEP=(15'd1 << 9),
        CLAMP=(15'd1 << 10), SPAN=(15'd1 << 11), EMIT=(15'd1 << 12), ADVANCE=(15'd1 << 13), CARRY=(15'd1 << 14);
    reg [14:0] state;
    reg signed [15:0] vx[0:2],vy[0:2];
    reg signed [16:0] dx[0:2],dy[0:2];
    reg signed [17:0] ox[0:2],oy[0:2];
    reg signed [34:0] prod_a[0:2],prod_b[0:2];
    reg signed [35:0] edge_row[0:2],numerator[0:2],boundary[0:2],increment[0:2];
    reg signed [17:0] step_y[0:2];
    reg [16:0] divisor[0:2],fraction[0:2],fraction_step[0:2];
    reg [2:0] inclusive,lower,horizontal,carry;
    wire [2:0] div_done;
    wire signed [35:0] quotient[0:2];
    wire [16:0] remainder[0:2];
    reg signed [33:0] area_a,area_b;
    wire signed [34:0] area=$signed(area_a)-$signed(area_b);
    reg signed [15:0] left,right,top,bottom;
    reg [9:0] py;
    reg signed [11:0] edge_left[0:2],edge_right[0:2];
    reg [2:0] row_allowed;
    // Compare all edge pairs in parallel. Cascading max/min through another
    // comparator before the span subtraction creates a long serial path.
    // Ties select the lowest edge index; the numeric bounds are unchanged.
    wire l01=edge_left[0]>=edge_left[1],l02=edge_left[0]>=edge_left[2],l12=edge_left[1]>=edge_left[2];
    wire r01=edge_right[0]<=edge_right[1],r02=edge_right[0]<=edge_right[2],r12=edge_right[1]<=edge_right[2];
    // max(lefts) <= min(rights) iff every left <= every right. Parallel
    // comparisons avoid feeding the state through min/max selection first.
    wire span_nonempty=(edge_left[0]<=edge_right[0]) && (edge_left[0]<=edge_right[1]) && (edge_left[0]<=edge_right[2]) &&
                       (edge_left[1]<=edge_right[0]) && (edge_left[1]<=edge_right[1]) && (edge_left[1]<=edge_right[2]) &&
                       (edge_left[2]<=edge_right[0]) && (edge_left[2]<=edge_right[1]) && (edge_left[2]<=edge_right[2]);
    wire signed [11:0] line_left=({12{l01 && l02}} & edge_left[0]) |
                                ({12{!l01 && l12}} & edge_left[1]) |
                                ({12{!l02 && !l12}} & edge_left[2]);
    wire signed [11:0] line_right=({12{r01 && r02}} & edge_right[0]) |
                                 ({12{!r01 && r12}} & edge_right[1]) |
                                 ({12{!r02 && !r12}} & edge_right[2]);
    assign busy=!state[$clog2(IDLE)];
    assign valid=state[$clog2(EMIT)];
    function signed [15:0] min3;
        input signed [15:0] a,b,c;
        begin min3=a<b ? (a<c ? a:c) : (b<c ? b:c); end
    endfunction
    function signed [15:0] max3;
        input signed [15:0] a,b,c;
        begin max3=a>b ? (a>c ? a:c) : (b>c ? b:c); end
    endfunction
    genvar g;
    generate for(g=0;g<3;g=g+1) begin:edge_dividers
        wire signed [35:0] delta=lower[g] ? -$signed(step_y[g]):$signed(step_y[g]);
        gpu_triangle_floor_div u_div (
            .clk(clk),.rst(rst),.start(state[$clog2(DIV_FIRST)] || state[$clog2(DIV_STEP)]),
            .numerator(state[$clog2(DIV_FIRST)] ? numerator[g]:delta),
            .denominator(divisor[g]),.done(div_done[g]),
            .quotient(quotient[g]),.remainder(remainder[g]));
    end endgenerate
    integer i;
    // Arithmetic initialized before use; only the controlling state resets.
    always @(posedge clk) begin
        if(state[$clog2(BOUNDS)]) begin
            area_a<=($signed({vx[1][15],vx[1]})-$signed({vx[0][15],vx[0]}))*
                    ($signed({vy[2][15],vy[2]})-$signed({vy[0][15],vy[0]}));
            area_b<=($signed({vy[1][15],vy[1]})-$signed({vy[0][15],vy[0]}))*
                    ($signed({vx[2][15],vx[2]})-$signed({vx[0][15],vx[0]}));
        end
        for(i=0;i<3;i=i+1) begin
            if(state[$clog2(EDGES)]) begin
                dx[i]<=$signed({vx[(i+1)%3][15],vx[(i+1)%3]})-$signed({vx[i][15],vx[i]});
                dy[i]<=$signed({vy[(i+1)%3][15],vy[(i+1)%3]})-$signed({vy[i][15],vy[i]});
                ox[i]<=18'sd1-$signed(vx[i])*18'sd2;
                oy[i]<=($signed({top[15],top})-$signed({vy[i][15],vy[i]}))*18'sd2+18'sd1;
            end
            if(state[$clog2(PRODUCTS)]) begin
                prod_a[i]<=dx[i]*oy[i];prod_b[i]<=dy[i]*ox[i];
                step_y[i]<=$signed({dx[i],1'b0});
                inclusive[i]<=dy[i]<0 || (dy[i]==0 && dx[i]>0);
                lower[i]<=dy[i]<0;horizontal[i]<=dy[i]==0;
                divisor[i]<=dy[i]==0 ? 17'd1 : dy[i]<0 ? -{dy[i][15:0],1'b0}:{dy[i][15:0],1'b0};
            end
            if(state[$clog2(SEEDS)]) begin
                edge_row[i]<=$signed(prod_a[i])-$signed(prod_b[i]);
                // For increasing edges: ceil((threshold-E)/D), expressed as
                // floor((threshold-E+D-1)/D). Decreasing edges: floor((E-T)/D).
                numerator[i]<=lower[i] ?
                    $signed(prod_b[i])-$signed(prod_a[i])+$signed({19'd0,divisor[i]})-(inclusive[i]?36'sd1:36'sd0) :
                    $signed(prod_a[i])-$signed(prod_b[i])-(inclusive[i]?36'sd0:36'sd1);
            end
            if(state[$clog2(WAIT_FIRST)] && &div_done) begin
                boundary[i]<=quotient[i];fraction[i]<=remainder[i];
            end
            if(state[$clog2(WAIT_STEP)] && &div_done) begin
                increment[i]<=quotient[i];fraction_step[i]<=remainder[i];
            end
            if(state[$clog2(CLAMP)]) begin
                edge_left[i]<=!lower[i] ? 12'sd0 : boundary[i]<0 ? 12'sd0 : boundary[i]>WIDTH ? WIDTH : boundary[i][11:0];
                edge_right[i]<=lower[i] || horizontal[i] ? WIDTH-1 : boundary[i]<0 ? -12'sd1 : boundary[i]>=WIDTH ? WIDTH-1 : boundary[i][11:0];
                row_allowed[i]<=!horizontal[i] || edge_row[i]>0 || (edge_row[i]==0 && inclusive[i]);
            end
            if(state[$clog2(ADVANCE)]) begin:advance_edge
                reg [17:0] sum;
                sum={1'b0,fraction[i]}+{1'b0,fraction_step[i]};
                carry[i]<=sum>={1'b0,divisor[i]};
                fraction[i]<=sum>={1'b0,divisor[i]} ? sum-{1'b0,divisor[i]}:sum;
                boundary[i]<=boundary[i]+increment[i];
                edge_row[i]<=edge_row[i]+step_y[i];
            end
            if(state[$clog2(CARRY)]) boundary[i]<=boundary[i]+$signed({35'd0,carry[i]});
        end
    end
    always @(posedge clk) begin
        if(rst) state<=IDLE;
        else case (1'b1) // synthesis parallel_case
            state[$clog2(IDLE)]:if(start)begin
                vx[0]<=x0;vy[0]<=y0;vx[1]<=x1;vy[1]<=y1;vx[2]<=x2;vy[2]<=y2;state<=BOUNDS;
            end
            state[$clog2(BOUNDS)]:begin
                left<=min3(vx[0],vx[1],vx[2])<0 ? 16'sd0:min3(vx[0],vx[1],vx[2]);
                top<=min3(vy[0],vy[1],vy[2])<0 ? 16'sd0:min3(vy[0],vy[1],vy[2]);
                right<=max3(vx[0],vx[1],vx[2])>=WIDTH ? WIDTH-1:max3(vx[0],vx[1],vx[2]);
                bottom<=max3(vy[0],vy[1],vy[2])>=HEIGHT ? HEIGHT-1:max3(vy[0],vy[1],vy[2]);state<=ORIENT;
            end
            state[$clog2(ORIENT)]:begin
                if(area<0)begin vx[1]<=vx[2];vy[1]<=vy[2];vx[2]<=vx[1];vy[2]<=vy[1];end
                state<=area==0 || left>right || top>bottom ? IDLE:EDGES;
            end
            state[$clog2(EDGES)]:state<=PRODUCTS;
            state[$clog2(PRODUCTS)]:state<=SEEDS;
            state[$clog2(SEEDS)]:begin py<=top[9:0];state<=DIV_FIRST;end
            state[$clog2(DIV_FIRST)]:state<=WAIT_FIRST;
            state[$clog2(WAIT_FIRST)]:if(&div_done)state<=DIV_STEP;
            state[$clog2(DIV_STEP)]:state<=WAIT_STEP;
            state[$clog2(WAIT_STEP)]:if(&div_done)state<=CLAMP;
            state[$clog2(CLAMP)]:state<=SPAN;
            state[$clog2(SPAN)]:begin
                span_x<=line_left[10:0];span_width<=line_right-line_left+12'sd1;span_y<=py;
                state<=(&row_allowed) && span_nonempty ? EMIT : py==bottom[9:0] ? IDLE:ADVANCE;
            end
            state[$clog2(EMIT)]:if(ready)state<=py==bottom[9:0] ? IDLE:ADVANCE;
            state[$clog2(ADVANCE)]:begin py<=py+1'b1;state<=CARRY;end
            state[$clog2(CARRY)]:state<=CLAMP;
            default:state<=IDLE;
        endcase
    end
endmodule

// Euclidean division: N = Q*D+R, 0<=R<D, including negative N.
// Fixed 36 iterations; invoked twice per triangle, never per pixel/line.
module gpu_triangle_floor_div(
    input wire clk,rst,start,
    input wire signed [35:0] numerator,
    input wire [16:0] denominator,
    output reg done,
    output reg signed [35:0] quotient,
    output reg [16:0] remainder
);
    reg active,negative;
    reg [5:0] count;
    reg [35:0] dividend,q;
    reg [16:0] divisor,r;
    wire [17:0] shifted={r,dividend[35]};
    wire subtract=shifted>={1'b0,divisor};
    wire [17:0] next_r=subtract ? shifted-{1'b0,divisor}:shifted;
    wire [35:0] next_q={q[34:0],subtract};
    // Compute rounding without waiting for the remainder subtraction, and
    // precompute the only possible carry through the negative high word.
    // This is exactly -next_q - (next_r != 0), modulo 36 bits.
    wire next_r_zero = shifted == 0 || shifted == {1'b0,divisor};
    wire [34:0] neg_high_incremented = ~q[34:0] + 35'd1;
    wire [35:0] negative_q = {
        (!subtract && next_r_zero) ? neg_high_incremented : ~q[34:0],
        subtract ^ !next_r_zero};
    always @(posedge clk)begin
        if(rst)begin active<=0;done<=0;end
        else begin
            done<=0;
            if(start)begin
                active<=1;negative<=numerator[35];dividend<=numerator[35] ? -numerator:numerator;
                divisor<=denominator;q<=0;r<=0;count<=0;
            end else if(active)begin
                dividend<={dividend[34:0],1'b0};q<=next_q;r<=next_r[16:0];count<=count+1'b1;
                if(count==35)begin
                    quotient<=negative ? $signed(negative_q):$signed(next_q);
                    remainder<=negative && next_r!=0 ? divisor-next_r[16:0]:next_r[16:0];
                    active<=0;done<=1;
                end
            end
        end
    end
endmodule
`default_nettype wire
