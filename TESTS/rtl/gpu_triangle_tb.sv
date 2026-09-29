`timescale 1ns/1ps
module gpu_triangle_tb;
    reg clk=0,rst=1,start=0,ready=0;
    always #5 clk=~clk;
    reg signed [15:0] x0,y0,x1,y1,x2,y2;
    wire busy,valid;
    wire [10:0] sx,sw;
    wire [9:0] sy;
    gpu_triangle dut(.clk(clk),.rst(rst),.start(start),.x0(x0),.y0(y0),
        .x1(x1),.y1(y1),.x2(x2),.y2(y2),.busy(busy),.valid(valid),
        .ready(ready),.span_x(sx),.span_y(sy),.span_width(sw));
    bit pixels[0:383999];
    integer cycle=0,total=0,spans=0,stalls=0,total_cycles=0,max_cycles=0;
    reg held=0;reg [31:0] previous;
    always @(negedge clk) begin cycle++;ready=cycle%7!=0 && cycle%11!=0;end
    always @(posedge clk) if(!rst) begin
        if(held && (!valid || {sx,sy,sw}!==previous)) $fatal(1,"Span changed while stalled");
        held<=valid && !ready;previous<={sx,sy,sw};
        if(valid && !ready) stalls++;
        if(valid && ready) begin
            if(sw==0 || sx+sw>800 || sy>=480) $fatal(1,"Out-of-bounds span");
            for(integer i=0;i<sw;i++) begin
                if(pixels[sy*800+sx+i]) $fatal(1,"Duplicate pixel");
                pixels[sy*800+sx+i]=1;
            end
            spans++;
        end
    end
    function automatic bit edge_inside(input longint ax,ay,bx,by,x,y,orientation);
        longint e,dx,dy;
        dx=bx-ax;dy=by-ay;e=dx*(2*y+1-2*ay)-dy*(2*x+1-2*ax);
        // Reverse inequalities for clockwise input, without swapping vertices.
        e*=orientation;dx*=orientation;dy*=orientation;
        return e>0 || (e==0 && (dy<0 || (dy==0 && dx>0)));
    endfunction
    task automatic triangle(input integer ax,ay,bx,by,cx,cy);
        longint area,orientation;integer began;bit expected;
        for(integer i=0;i<384000;i++) pixels[i]=0;
        @(negedge clk);x0=16'(ax);y0=16'(ay);x1=16'(bx);y1=16'(by);x2=16'(cx);y2=16'(cy);start=1;
        @(negedge clk);start=0;began=cycle;
        while(busy) begin @(negedge clk);if(cycle-began>400000) $fatal(1,"Unbounded triangle");end
        area=(64'(bx)-ax)*(64'(cy)-ay)-(64'(by)-ay)*(64'(cx)-ax);orientation=area>0 ? 1:-1;
        for(integer y=0;y<480;y++) for(integer x=0;x<800;x++) begin
            expected=area!=0 && edge_inside(ax,ay,bx,by,x,y,orientation) &&
                edge_inside(bx,by,cx,cy,x,y,orientation) && edge_inside(cx,cy,ax,ay,x,y,orientation);
            if(pixels[y*800+x]!=expected) $fatal(1,"Triangle %0d mismatch at %0d,%0d",total,x,y);
        end
        total_cycles+=cycle-began;if(cycle-began>max_cycles)max_cycles=cycle-began;
        if(cycle-began>5000)$fatal(1,"Scanline work must not depend on triangle width");
        total++;
    endtask
    integer seed=15920,unused;
    initial begin
        repeat(5) @(negedge clk);rst=0;unused=$urandom(seed);
        triangle(0,0,800,0,800,480);triangle(0,0,800,480,0,480);
        triangle(0,0,1,0,0,1);triangle(0,1,1,0,1,1);
        triangle(0,0,0,0,0,0);triangle(-32768,0,32767,0,0,0);
        triangle(-32768,-32768,32767,-32768,0,32767);
        triangle(32767,32767,-32768,32767,0,-32768);
        triangle(-32768,-32768,32767,32767,32766,32767);
        triangle(32767,32767,32767,32766,32766,32767);
        triangle(-2,400,800,-3,32767,32767);
        for(integer i=0;i<90;i++) begin
            triangle(int'($urandom_range(0,999))-100,int'($urandom_range(0,679))-100,
                int'($urandom_range(0,999))-100,int'($urandom_range(0,679))-100,
                int'($urandom_range(0,999))-100,int'($urandom_range(0,679))-100);
        end
        // Large slopes and signed intersections far beyond the screen.
        triangle(-32768,-1,32767,0,0,480);
        triangle(32767,1,-32768,0,0,479);
        triangle(0,-32768,1,32767,799,0);
        triangle(32766,-32768,32767,32767,-32768,32766);
        for(integer i=0;i<150;i++)begin
            triangle(int'($urandom_range(0,65535))-32768,int'($urandom_range(0,65535))-32768,
                int'($urandom_range(0,65535))-32768,int'($urandom_range(0,65535))-32768,
                int'($urandom_range(0,65535))-32768,int'($urandom_range(0,65535))-32768);
        end
        if(stalls==0) $fatal(1,"No backpressure");
        $display("PASS: %0d triangles, every pixel exact, %0d spans, %0d stalls; winding, shared edges, clipping, signed extremes, zero area",total,spans,stalls);
        $display("Scanline cycles: total=%0d max_triangle=%0d",total_cycles,max_cycles);
        $finish;
    end
    initial begin #600000000;$fatal(1,"Timeout");end
endmodule
