// RGB565 direct scanout; one bounded line of native DDR bursts.
`default_nettype none
module gpu_rgb_reader #(parameter WIDTH=800, parameter BLOCK_BITS=(WIDTH>1024 ? 7:6))(
    input wire clk,resetn,start,pipelined,halfres,
    input wire [31:0] base,
    output reg done,fetch_valid,
    output reg [28:0] fetch_addr,
    input wire fetch_ready,
    input wire [255:0] fetch_data,
    input wire fetch_data_valid,
    output reg block_valid,
    output reg [BLOCK_BITS-1:0] block_index,
    output reg [255:0] block_data
);
    localparam IDLE=0,SEND=1,WAIT=2,NEXT=3,FINISH=4,PIPE=5;
    reg [2:0] state;
    reg [BLOCK_BITS-1:0] position;
    reg [BLOCK_BITS-1:0] issued,last;
    always @(posedge clk)begin
        if(!resetn)begin
            state<=IDLE;done<=0;fetch_valid<=0;fetch_addr<=0;
            block_valid<=0;block_index<=0;block_data<=0;position<=0;issued<=0;last<=WIDTH/16-1;
        end else begin
            done<=0;block_valid<=0;
            case(state)
            IDLE:if(start)begin
                fetch_addr<=base[30:2];position<=0;issued<=0;fetch_valid<=1;last<=halfres ? WIDTH/32-1:WIDTH/16-1;
                state<=pipelined ? PIPE:SEND;
            end
            // The shared arbiter bounds its read tags to 16 outstanding.
            // Responses remain ordered; every accepted read is stored once.
            PIPE:begin
                if(fetch_valid && fetch_ready)begin
                    issued<=issued+1'b1;fetch_addr<=fetch_addr+29'd8;
                    if(issued==last)fetch_valid<=0;
                end
                if(fetch_data_valid)begin
                    block_valid<=1;block_index<=position;block_data<=fetch_data;
                    position<=position+1'b1;
                    if(position==last)state<=FINISH;
                end
            end
            SEND:if(fetch_ready)begin fetch_valid<=0;state<=WAIT;end
            WAIT:if(fetch_data_valid)begin
                block_valid<=1;block_index<=position;block_data<=fetch_data;
                state<=position==last ? FINISH:NEXT;
            end
            NEXT:begin position<=position+1'b1;fetch_addr<=fetch_addr+29'd8;fetch_valid<=1;state<=SEND;end
            FINISH:if(!block_valid)begin done<=1;state<=IDLE;end
            default:begin fetch_valid<=0;state<=IDLE;end
            endcase
        end
    end
endmodule
`default_nettype wire
