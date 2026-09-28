// Integer triangle rasterizer, pixel centres and top-left edge ownership.
// Full signed-16 vertices; clip the bounding box BEFORE scanning, so even
// extreme off-screen vertices take at most WIDTH*HEIGHT pixel tests.
// Produces inclusive horizontal spans; valid/data remain stable until ready.
`default_nettype none
module gpu_triangle #(parameter WIDTH=800, HEIGHT=480) (
    input wire clk, rst, start,
    input wire signed [15:0] x0,y0,x1,y1,x2,y2,
    output wire busy,
    output wire valid,
    input wire ready,
    output reg [10:0] span_x, span_width,
    output reg [9:0] span_y
);
    localparam IDLE=0, BOUNDS=1, ORIENT=2, EDGES=3, PRODUCTS=4,
               SEEDS=5, SCAN=6, EMIT=7, NEXT=8;
    reg [3:0] state;
    reg signed [15:0] vx[0:2],vy[0:2];
    reg signed [16:0] dx[0:2],dy[0:2];
    reg signed [17:0] ox[0:2],oy[0:2];
    reg signed [34:0] prod_a[0:2],prod_b[0:2];
    reg signed [35:0] edge_value[0:2],row_value[0:2];
    reg signed [17:0] step_x[0:2],step_y[0:2];
    reg [2:0] inclusive;
    reg signed [33:0] area_a,area_b;
    wire signed [34:0] area=$signed(area_a)-$signed(area_b);
    reg signed [15:0] left,right,top,bottom;
    reg [10:0] px,first,last;
    reg [9:0] py;
    reg found;
    wire inside_pixel=(edge_value[0]>0 || (edge_value[0]==0 && inclusive[0])) &&
                      (edge_value[1]>0 || (edge_value[1]==0 && inclusive[1])) &&
                      (edge_value[2]>0 || (edge_value[2]==0 && inclusive[2]));
    assign busy=state!=IDLE;
    assign valid=state==EMIT;
    function signed [15:0] min3;
        input signed [15:0] a,b,c;
        begin min3=a<b ? (a<c ? a:c) : (b<c ? b:c); end
    endfunction
    function signed [15:0] max3;
        input signed [15:0] a,b,c;
        begin max3=a>b ? (a>c ? a:c) : (b>c ? b:c); end
    endfunction
    integer i;
    // Wide arithmetic data needs no reset: every input is seeded before use.
    always @(posedge clk) begin
        if(state==BOUNDS) begin
            area_a<=($signed({vx[1][15],vx[1]})-$signed({vx[0][15],vx[0]}))*
                    ($signed({vy[2][15],vy[2]})-$signed({vy[0][15],vy[0]}));
            area_b<=($signed({vy[1][15],vy[1]})-$signed({vy[0][15],vy[0]}))*
                    ($signed({vx[2][15],vx[2]})-$signed({vx[0][15],vx[0]}));
        end
        for(i=0;i<3;i=i+1) begin
            if(state==EDGES) begin
                dx[i]<=$signed({vx[(i+1)%3][15],vx[(i+1)%3]})-$signed({vx[i][15],vx[i]});
                dy[i]<=$signed({vy[(i+1)%3][15],vy[(i+1)%3]})-$signed({vy[i][15],vy[i]});
                ox[i]<=($signed({left[15],left})-$signed({vx[i][15],vx[i]}))*18'sd2+18'sd1;
                oy[i]<=($signed({top[15],top})-$signed({vy[i][15],vy[i]}))*18'sd2+18'sd1;
            end
            if(state==PRODUCTS) begin
                prod_a[i]<=dx[i]*oy[i]; prod_b[i]<=dy[i]*ox[i];
                step_x[i]<=-$signed({dy[i],1'b0}); step_y[i]<=$signed({dx[i],1'b0});
                inclusive[i]<=dy[i]<0 || (dy[i]==0 && dx[i]>0);
            end
            if(state==SEEDS) begin
                row_value[i]<=$signed(prod_a[i])-$signed(prod_b[i]);
                edge_value[i]<=$signed(prod_a[i])-$signed(prod_b[i]);
            end
            if(state==SCAN) edge_value[i]<=edge_value[i]+step_x[i];
            if(state==NEXT) begin
                row_value[i]<=row_value[i]+step_y[i];
                edge_value[i]<=row_value[i]+step_y[i];
            end
        end
    end
    always @(posedge clk) begin
        if(rst) state<=IDLE;
        else case(state)
            IDLE: if(start) begin
                vx[0]<=x0;vy[0]<=y0;vx[1]<=x1;vy[1]<=y1;vx[2]<=x2;vy[2]<=y2;
                state<=BOUNDS;
            end
            BOUNDS: begin
                left<=min3(vx[0],vx[1],vx[2])<0 ? 16'sd0 : min3(vx[0],vx[1],vx[2]);
                top<=min3(vy[0],vy[1],vy[2])<0 ? 16'sd0 : min3(vy[0],vy[1],vy[2]);
                right<=max3(vx[0],vx[1],vx[2])>=WIDTH ? WIDTH-1 : max3(vx[0],vx[1],vx[2]);
                bottom<=max3(vy[0],vy[1],vy[2])>=HEIGHT ? HEIGHT-1 : max3(vy[0],vy[1],vy[2]);
                state<=ORIENT;
            end
            ORIENT: begin
                if(area<0) begin vx[1]<=vx[2];vy[1]<=vy[2];vx[2]<=vx[1];vy[2]<=vy[1];end
                state<=(area==0 || left>right || top>bottom) ? IDLE:EDGES;
            end
            EDGES: state<=PRODUCTS;
            PRODUCTS: state<=SEEDS;
            SEEDS: begin px<=left[10:0];py<=top[9:0];found<=0;state<=SCAN;end
            SCAN: begin
                if(inside_pixel) begin
                    if(!found) first<=px;
                    found<=1;last<=px;
                end
                px<=px+1'b1;
                if(px==right[10:0] || (found && !inside_pixel)) begin
                    span_x<=found ? first:px;
                    span_width<=(inside_pixel ? px:last)-(found ? first:px)+11'd1;
                    span_y<=py;
                    state<=(found || inside_pixel) ? EMIT:NEXT;
                end
            end
            EMIT: if(ready) state<=NEXT;
            NEXT: begin
                py<=py+1'b1;px<=left[10:0];found<=0;
                state<=py==bottom[9:0] ? IDLE:SCAN;
            end
            default: state<=IDLE;
        endcase
    end
endmodule
`default_nettype wire
