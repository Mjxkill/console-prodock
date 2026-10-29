// RGB565 rectangular memmove, native 32-byte blocks, arbitrary halfword alignment.
// Source and destination may overlap only with an identical base/stride layout.
`default_nettype none
module gpu_copy565(
    input wire clk,rst,start,
    input wire [255:0] command,
    input wire [29:0] dst_base,
    input wire [15:0] dst_stride,dst_height,clip_l,clip_t,clip_r,clip_b,
    output reg done,bad,
    output reg valid,write,
    output reg [28:0] addr,
    output reg [255:0] wr_data,
    output reg [31:0] wr_mask,
    input wire ready,rd_valid,
    input wire [255:0] rd_data
);
    localparam IDLE=0,CHECK=1,CLIP=2,ROW=3,CHUNK=4,ADDRESS=5,READ0=6,WAIT0=7,
      READ1=8,WAIT1=9,ALIGN=10,WRITE=11,SENT=12,NEXT=13,FINISH=14,
      BOUNDS=15,SOURCE_CLIP=16,VALIDATE=17,CAPTURE_WAIT=18;
    reg [4:0] state;
    // Keep COPY's descriptor near its arithmetic rather than driving its DSPs
    // from the shared shader packet. Preserve this fabric boundary: absorbing
    // independently enabled command registers into a DSP can reorder enables.
    // Only IDLE/start writes it; reset clears control, so an old payload cannot
    // issue a transaction. CAPTURE_WAIT lets the registered range settle.
    reg [255:0] packet /* synthesis syn_preserve=1 */;
    wire [31:0] w1=packet[63:32],w2=packet[95:64],w3=packet[127:96],
        w4=packet[159:128],w5=packet[191:160],w6=packet[223:192],w7=packet[255:224];
    wire signed [31:0] sx={{16{w4[31]}},w4[31:16]},sy={{16{w4[15]}},w4[15:0]},
        dx={{16{w5[31]}},w5[31:16]},dy={{16{w5[15]}},w5[15:0]};
    reg [32:0] src_end,dst_end;
    always @(posedge clk)begin
        src_end<={1'b0,w1}+{17'd0,w3[15:0]}*{17'd0,w2[15:0]};
        dst_end<={3'b0,dst_base}+{17'd0,dst_stride}*{17'd0,dst_height};
    end
    wire overlap=w1<dst_end && dst_base<src_end;
    reg [2:0] descriptor_bad;
    reg reverse;
    reg signed [31:0] l,t,r,b;
    reg signed [31:0] source_l,source_t,source_r,source_b;
    function signed [31:0] max2;
        input signed [31:0] a,b;begin max2=a>b?a:b;end
    endfunction
    function signed [31:0] min2;
        input signed [31:0] a,b;begin min2=a<b?a:b;end
    endfunction
    reg [15:0] row_y,cursor,px,count;
    // row_y and the clipped bounds are stable throughout the chunk transfer.
    // Decide whether another row exists before NEXT, so the 32-bit comparison
    // is not in the row counter's clock-enable path.
    reg row_has_next;
    always @(posedge clk)
        if(rst)row_has_next<=0;
        else row_has_next<=reverse ? row_y>t:row_y+1<b;
    reg [31:0] source_row,destination_row,source_address,destination_address;
    reg [255:0] first,second;
    reg [255:0] aligned;
    wire [4:0] source_lane={1'b0,source_address[4:1]};
    wire [4:0] dst_lane={1'b0,destination_address[4:1]};
    wire [511:0] shifted={second,first}>>(source_lane*16);
    // During WRITE/SENT, aligned and destination_address are stable. Computing
    // this register every cycle removes the wide state-dependent clock enable
    // without adding a cycle or changing any accepted DDR payload.
    always @(posedge clk)
        if(rst)wr_data<=0;else wr_data<=aligned<<(dst_lane*16);
    always @(posedge clk)begin
        if(rst)begin
            state<=IDLE;done<=0;bad<=0;valid<=0;write<=0;addr<=0;wr_mask<=-1;
            reverse<=0;l<=0;t<=0;r<=0;b<=0;row_y<=0;cursor<=0;px<=0;count<=0;descriptor_bad<=0;
            source_l<=0;source_t<=0;source_r<=0;source_b<=0;
            source_row<=0;destination_row<=0;source_address<=0;destination_address<=0;
            first<=0;second<=0;aligned<=0;
        end else begin
            done<=0;
            case(state)
            IDLE:if(start)begin packet<=command;bad<=0;state<=CAPTURE_WAIT;end
            CAPTURE_WAIT:state<=CHECK;
            CHECK:begin
                // Validation only chooses the next state. Invalid descriptors
                // never reach ROW, so private bounds can be captured regardless
                // of validity without a long comparator driving all enables.
                l<=dx;t<=dy;r<=dx+$signed({16'd0,w6[31:16]});b<=dy+$signed({16'd0,w6[15:0]});
                source_l<=dx-sx;source_t<=dy-sy;
                reverse<=overlap && (dy>sy || (dy==sy && dx>sx));
                descriptor_bad[0]<=w1[31:30]!=0 || w1[4:0]!=0 || w2[31:16]==0 || w2[31:16]>1024;
                descriptor_bad[1]<=w2[15:0]==0 || w2[15:0]>512 || w3[31:16]!=0 || w3[4:0]!=0 ||
                   w3[15:0]<({1'b0,w2[31:16]}<<1);
                descriptor_bad[2]<=src_end>33'h040000000 || w7!=0 ||
                   (overlap && (w1!={2'b0,dst_base} || w3[15:0]!=dst_stride));
                state<=VALIDATE;
            end
            VALIDATE:begin
                if(|descriptor_bad)begin bad<=1;state<=FINISH;end
                else state<=BOUNDS;
            end
            BOUNDS:begin
                l<=max2(l,$signed({16'd0,clip_l}));t<=max2(t,$signed({16'd0,clip_t}));
                r<=min2(r,$signed({16'd0,clip_r}));b<=min2(b,$signed({16'd0,clip_b}));
                source_r<=source_l+$signed({16'd0,w2[31:16]});
                source_b<=source_t+$signed({16'd0,w2[15:0]});state<=SOURCE_CLIP;
            end
            SOURCE_CLIP:begin
                l<=max2(l,source_l);t<=max2(t,source_t);
                r<=min2(r,source_r);b<=min2(b,source_b);state<=CLIP;
            end
            CLIP:if(l>=r || t>=b)state<=FINISH;
                 else begin row_y<=reverse ? b[15:0]-1'b1:t[15:0];state<=ROW;end
            ROW:begin
                // source_t/l already hold dy-sy/dx-sx. Reuse these local
                // differences instead of routing packet coordinates into DSPs.
                source_row<=w1+($signed({16'd0,row_y})-source_t)*$signed({16'd0,w3[15:0]});
                destination_row<={2'b0,dst_base}+row_y*dst_stride;
                cursor<=reverse ? r[15:0]:l[15:0];state<=CHUNK;
            end
            CHUNK:begin
                if(reverse)begin
                    count<=cursor-l < (cursor[3:0]==0 ? 16:cursor[3:0]) ? cursor-l:(cursor[3:0]==0 ? 16:cursor[3:0]);
                    px<=cursor-l < (cursor[3:0]==0 ? 16:cursor[3:0]) ? l[15:0]:(cursor-1'b1)&16'hfff0;
                end else begin
                    count<=r-cursor < 16-cursor[3:0] ? r-cursor:16-cursor[3:0];px<=cursor;
                end
                state<=ADDRESS;
            end
            ADDRESS:begin
                source_address<=source_row+(($signed({16'd0,px})-source_l)<<1);
                destination_address<=destination_row+{15'd0,px,1'b0};second<=0;state<=READ0;
            end
            READ0:begin addr<={source_address[30:5],3'b0};valid<=1;write<=0;state<=WAIT0;end
            WAIT0:begin
                if(valid && ready)valid<=0;
                if(rd_valid)begin first<=rd_data;state<=source_lane+count>16 ? READ1:ALIGN;end
            end
            READ1:begin addr<=addr+29'd8;valid<=1;state<=WAIT1;end
            WAIT1:begin
                if(valid && ready)valid<=0;
                if(rd_valid)begin second<=rd_data;state<=ALIGN;end
            end
            ALIGN:begin aligned<=shifted[255:0];state<=WRITE;end
            WRITE:begin
                addr<={destination_address[30:5],3'b0};
                for(integer p=0;p<16;p=p+1)wr_mask[p*2+:2]<=(p>=dst_lane && p<dst_lane+count) ? 2'b00:2'b11;
                valid<=1;write<=1;state<=SENT;
            end
            SENT:if(ready)begin valid<=0;state<=NEXT;end
            NEXT:begin
                if(reverse ? px>l:px+count<r)begin cursor<=reverse ? px:px+count;state<=CHUNK;end
                else if(row_has_next)begin row_y<=reverse ? row_y-1'b1:row_y+1'b1;state<=ROW;end
                else state<=FINISH;
            end
            FINISH:begin done<=1;state<=IDLE;end
            default:begin valid<=0;bad<=1;state<=FINISH;end
            endcase
        end
    end
endmodule
`default_nettype wire
