// Packs the blitter's halfwords/byte enables into aligned DDR3 BL8 transfers.
// One transaction at a time. DDR write command and data are accepted together;
// the caller acknowledges only after the final native write is accepted.
`default_nettype none
module gpu_blit_dma (
    input wire clk, rst,
    input wire s_req,
    input wire [23:0] s_addr,
    input wire [9:0] s_len,
    output wire s_valid,
    output wire [15:0] s_data,
    output wire s_done,
    input wire w_req,
    input wire [23:0] w_addr,
    input wire [9:0] w_len,
    input wire [15:0] w_data,
    input wire [1:0] w_mask,
    output wire w_ready, w_done,
    input wire c_req,
    input wire [23:0] c_addr,
    input wire [15:0] c_wdata,
    input wire [1:0] c_wmask,
    output wire c_ack,
    output reg valid=0,
    output wire write,
    output reg [28:0] addr,
    output reg [255:0] wr_data,
    output reg [31:0] wr_mask,
    input wire ready,
    input wire [255:0] rd_data,
    input wire rd_valid
);
    localparam IDLE=0, W_PACK=1, W_SEND=2, R_SEND=3, R_WAIT=4, R_UNPACK=5;
    reg [2:0] state;
    reg [23:0] position;
    reg [9:0] remaining;
    reg pixel_write;
    reg [255:0] read_buffer;
    wire [3:0] lane = position[3:0];
    // Keep the global reset/state decode off the arbiter's ready/tag paths.
    // This register changes on the same edges as entry/exit of SEND states.
    assign write = state == W_SEND;
    assign w_ready = !rst && state == W_PACK;
    assign w_done = !rst && state == W_SEND && ready && !pixel_write && remaining == 0;
    assign c_ack = !rst && state == W_SEND && ready && pixel_write;
    assign s_valid = !rst && state == R_UNPACK;
    assign s_data = read_buffer[lane * 16 +: 16];
    assign s_done = s_valid && remaining == 1;
    always @(posedge clk) begin
        if (rst) begin
            state <= IDLE; valid<=0; position <= 0; remaining <= 0; pixel_write <= 0;
            addr <= 0; wr_data <= 0; wr_mask <= 32'hffffffff; read_buffer <= 0;
        end else case (state)
            IDLE: begin
                wr_mask <= 32'hffffffff;
                if (c_req) begin
                    addr <= {6'b0, c_addr[23:4], 3'b0};
                    wr_data <= {16{c_wdata}};
                    wr_mask <= ~( {30'b0, c_wmask} << (c_addr[3:0] * 2));
                    pixel_write <= 1; remaining <= 0; state <= W_SEND;valid<=1;
                end else if (w_req && w_len != 0) begin
                    addr <= {6'b0, w_addr[23:4], 3'b0};
                    position <= w_addr; remaining <= w_len;
                    pixel_write <= 0; state <= W_PACK;
                end else if (s_req && s_len != 0) begin
                    addr <= {6'b0, s_addr[23:4], 3'b0};
                    position <= s_addr; remaining <= s_len; state <= R_SEND;valid<=1;
                end
            end
            W_PACK: begin
                wr_data[lane * 16 +: 16] <= w_data;
                wr_mask[lane * 2 +: 2] <= ~w_mask;
                position <= position + 1'b1;
                remaining <= remaining - 1'b1;
                if (lane == 15 || remaining == 1) begin state <= W_SEND;valid<=1;end
            end
            W_SEND: if (ready) begin
                valid<=0;
                wr_mask <= 32'hffffffff;
                if (remaining == 0) state <= IDLE;
                else begin
                    addr <= {6'b0, position[23:4], 3'b0}; state <= W_PACK;
                end
            end
            R_SEND: if (ready) begin state <= R_WAIT;valid<=0;end
            R_WAIT: if (rd_valid) begin read_buffer <= rd_data; state <= R_UNPACK; end
            R_UNPACK: begin
                position <= position + 1'b1; remaining <= remaining - 1'b1;
                if (remaining == 1) state <= IDLE;
                else if (lane == 15) begin
                    addr <= addr + 29'd8; state <= R_SEND;valid<=1;
                end
            end
            default: begin state <= IDLE;valid<=0;end
        endcase
    end
endmodule
`default_nettype wire
