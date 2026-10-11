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
    output wire w_ready,
    output reg w_done,
    input wire f_req,
    input wire [24:0] f_addr,
    input wire [10:0] f_len,
    input wire [7:0] f_color,
    output reg f_done,
    input wire c_req,
    input wire [23:0] c_addr,
    input wire [15:0] c_wdata,
    input wire [1:0] c_wmask,
    output reg c_ack,
    output reg valid=0,
    output wire write,
    output reg [28:0] addr,
    output reg [255:0] wr_data,
    output reg [31:0] wr_mask,
    input wire ready,
    input wire [255:0] rd_data,
    input wire rd_valid
);
    localparam IDLE=0, W_PACK=1, W_SEND=2, R_SEND=3, R_WAIT=4, R_UNPACK=5, F_PREP=6, F_MASK=7;
    reg [2:0] state;
    reg [23:0] position;
    reg [9:0] remaining;
    reg pixel_write,fill_write;
    reg [10:0] fill_left;
    reg [4:0] fill_offset;
    reg [5:0] fill_low,fill_high;
    wire [5:0] fill_room=6'd32-{1'b0,fill_offset};
    wire [5:0] fill_take=fill_left>{5'd0,fill_room} ? fill_room:fill_left[5:0];
    integer byte_lane;
    reg [255:0] read_buffer;
    reg [28:0] write_follow_addr;
    reg write_accepted;
    wire [3:0] lane = position[3:0];
    // Keep the global reset/state decode off the arbiter's ready/tag paths.
    // This register changes on the same edges as entry/exit of SEND states.
    assign write = state == W_SEND;
    // Predict W_PACK on the same edge as the state transition. The blitter
    // shares this synchronous reset, so it never consumes READY during reset.
    // Do not put the high-fanout reset net back into the line-RAM address path.
    reg write_active /* synthesis syn_preserve=1 */;
    always @(posedge clk)begin
        if(rst)write_active<=0;
        else write_active<=
            (state==IDLE && !c_req && !(f_req && f_len!=0) && w_req && w_len!=0) ||
            (state==W_PACK && lane!=15 && remaining!=1) ||
            (state==W_SEND && ready && !fill_write && remaining!=0);
    end
    assign w_ready = write_active;
    // Acknowledge on the cycle AFTER native acceptance. This cuts the long
    // scanout valid -> DDR ready -> blitter next-state path. Completion still
    // means the final DDR write was accepted; no buffered write is hidden.
    always @(posedge clk) begin
        write_accepted <= !rst && state == W_SEND && ready;
        w_done <= !rst && state == W_SEND && ready && !pixel_write && !fill_write && remaining == 0;
        f_done <= !rst && state == W_SEND && ready && fill_write && fill_left == 0;
        c_ack <= !rst && state == W_SEND && ready && pixel_write;
    end
    // Predict entry/exit of UNPACK and its last halfword on the same edge
    // as the state/counter updates. No extra transfer cycle: this removes
    // binary state and remaining-count decoding from the blitter's inputs.
    reg read_active /* synthesis syn_preserve=1 */;
    reg read_last /* synthesis syn_preserve=1 */;
    always @(posedge clk) begin
        if(rst)begin read_active<=0;read_last<=0;end
        else begin
            read_active<=(state==R_WAIT && rd_valid) ||
                         (state==R_UNPACK && remaining!=1 && lane!=15);
            read_last<=(state==R_WAIT && rd_valid && remaining==1) ||
                       (state==R_UNPACK && remaining==2 && lane!=15);
        end
    end
    assign s_valid = !rst && read_active;
    assign s_data = read_buffer[lane * 16 +: 16];
    assign s_done = !rst && read_last;
    always @(posedge clk) begin
        if (rst) begin
            state <= IDLE; valid<=0; position <= 0; remaining <= 0; pixel_write <= 0;fill_write<=0;fill_left<=0;fill_offset<=0;fill_low<=0;fill_high<=0;
            addr <= 0; write_follow_addr<=0; wr_data <= 0; wr_mask <= 32'hffffffff; read_buffer <= 0;
        end else begin
          // After acceptance, valid is low while PACK/PREP prepares the
          // next command. Advance the address in that existing cycle so the
          // arbiter's combinational READY cannot drive this wide enable.
          // A new IDLE request below takes priority over this deferred update.
          if (write_accepted) addr <= write_follow_addr;
          case (state)
            IDLE: begin
                wr_mask <= 32'hffffffff;fill_write<=0;
                if (c_req) begin
                    addr <= {6'b0, c_addr[23:4], 3'b0};
                    write_follow_addr <= {6'b0, c_addr[23:4], 3'b0};
                    wr_data <= {16{c_wdata}};
                    wr_mask <= ~( {30'b0, c_wmask} << (c_addr[3:0] * 2));
                    pixel_write <= 1; remaining <= 0; state <= W_SEND;valid<=1;
                end else if(f_req && f_len!=0)begin
                    addr<={6'b0,f_addr[24:5],3'b0};wr_data<={32{f_color}};
                    fill_write<=1;pixel_write<=0;fill_offset<=f_addr[4:0];fill_left<=f_len;
                    state<=F_PREP;
                end else if (w_req && w_len != 0) begin
                    addr <= {6'b0, w_addr[23:4], 3'b0};
                    position <= w_addr; remaining <= w_len;
                    pixel_write <= 0; state <= W_PACK;
                end else if (s_req && s_len != 0) begin
                    addr <= {6'b0, s_addr[23:4], 3'b0};
                    position <= s_addr; remaining <= s_len; state <= R_SEND;valid<=1;
                end
            end
            F_PREP:begin
                fill_low<={1'b0,fill_offset};fill_high<={1'b0,fill_offset}+fill_take;
                fill_left<=fill_left-{5'd0,fill_take};fill_offset<=0;state<=F_MASK;
            end
            F_MASK:begin
                write_follow_addr<=fill_left==0 ? addr:addr+29'd8;
                for(byte_lane=0;byte_lane<32;byte_lane=byte_lane+1)
                    wr_mask[byte_lane]<=!(byte_lane>=fill_low && byte_lane<fill_high);
                state<=W_SEND;valid<=1;
            end
            W_PACK: begin
                // The final packed lane is either the last halfword or a
                // native-word boundary. Decide the following address before
                // W_SEND so DDR READY does not drive this branch/mux tree.
                write_follow_addr<=remaining==1 ? addr:addr+29'd8;
                wr_data[lane * 16 +: 16] <= w_data;
                wr_mask[lane * 2 +: 2] <= ~w_mask;
                position <= position + 1'b1;
                remaining <= remaining - 1'b1;
                if (lane == 15 || remaining == 1) begin state <= W_SEND;valid<=1;end
            end
            W_SEND: if (ready) begin
                valid<=0;
                wr_mask <= 32'hffffffff;
                if(fill_write)begin
                    if(fill_left==0)state<=IDLE;
                    else begin state<=F_PREP;end
                end else if (remaining == 0) state <= IDLE;
                else begin
                    state <= W_PACK;
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
    end
endmodule
`default_nettype wire
