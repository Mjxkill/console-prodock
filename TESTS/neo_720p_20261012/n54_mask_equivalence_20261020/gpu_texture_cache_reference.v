// GPU V1: 32 KiB read-only texture cache, 1024 native DDR lines of 16 texels.
// Physical-address tags survive material/mipmap switches. Explicit invalidate
// follows CPU resource publication; target/texture overlap is rejected above.
`default_nettype none
module gpu_texture_cache_reference(
    input wire clk,rst,invalidate,start,
    input wire [29:0] byte_address,
    output wire busy,
    output reg done,
    output reg [15:0] texel,
    output reg [31:0] hits,misses,
    output reg valid,
    output reg [28:0] addr,
    input wire ready,rd_valid,
    input wire [255:0] rd_data
);
    localparam IDLE=0,LOOK=1,HIT=2,SEND=3,WAIT_DATA=4,FILL=5,FINISH=6;
    reg [2:0] state;
    // Keep a complete DDR burst per BRAM word. A miss publishes all sixteen
    // texels in one write instead of serializing the refill for sixteen clocks.
    // A complete 128x128 RGB565 surface fits, avoiding repeated DDR fetches
    // while perspective walks across a large tiled floor or close object.
    localparam LINE_BITS=10,LINES=1<<LINE_BITS;
    reg [255:0] pixels[0:LINES-1] /* synthesis syn_ramstyle="block_ram" */;
    reg [24:0] tags[0:LINES-1];
    reg [LINES-1:0] present;
    reg [LINE_BITS-1:0] set_index;
    reg [24:0] block_tag;
    reg [3:0] requested_lane;
    reg [255:0] refill /* synthesis syn_preserve=1 */;
    wire [LINE_BITS-1:0] input_set=byte_address[14:5]^byte_address[24:15];
    reg [255:0] pixel_q;
    reg [24:0] tag_q;
    reg present_q;
    assign busy=state!=IDLE;
    always @(posedge clk)begin
        // Capture the response bus every cycle. Only an accepted response
        // enters FILL, whose RAM write and texel selection consume the value
        // captured on that response edge. This removes the remote owner's
        // state/rd_valid/reset cone from 256 register enables, without adding
        // a cycle or publishing idle bus data. Control/present still reset.
        refill<=rd_data;
        pixel_q<=pixels[input_set];
        tag_q<=tags[input_set];present_q<=present[input_set];
        if(state==FILL)pixels[set_index]<=refill;
        if(state==FINISH)tags[set_index]<=block_tag;
    end
    always @(posedge clk)begin
        if(rst)begin
            state<=IDLE;present<=0;done<=0;valid<=0;addr<=0;
            hits<=0;misses<=0;texel<=0;set_index<=0;block_tag<=0;
            requested_lane<=0;
        end else begin
            done<=0;
            if(invalidate)present<=0;
            case(state)
            IDLE:if(start && !invalidate)begin
                set_index<=input_set;block_tag<=byte_address[29:5];
                requested_lane<=byte_address[4:1];state<=LOOK;
            end
            LOOK:begin
                if(present_q && tag_q==block_tag)begin
                    texel<=pixel_q[requested_lane*16+:16];hits<=hits+1'b1;done<=1;state<=IDLE;
                end else begin
                    addr<={1'b0,block_tag,3'b0};valid<=1;
                    misses<=misses+1'b1;state<=SEND;
                end
            end
            SEND:if(ready)begin
                valid<=0;
                // The registered arbiter acknowledgement may coincide with
                // the earliest legal response. Do not lose that first beat.
                if(rd_valid)state<=FILL;
                else state<=WAIT_DATA;
            end
            WAIT_DATA:if(rd_valid)state<=FILL;
            FILL:begin
                texel<=refill[requested_lane*16+:16];state<=FINISH;
            end
            FINISH:begin present[set_index]<=1;done<=1;state<=IDLE;end
            default:begin valid<=0;state<=IDLE;end
            endcase
        end
    end
endmodule
`default_nettype wire
