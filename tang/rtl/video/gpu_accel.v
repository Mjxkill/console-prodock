// G2 AHB command queue + rasterizer + native DDR3 DMA, at 0xE9001000.
// A command contains eight words. Completion counter is the software fence;
// BUSY is a synchronized status indication, not a substitute for that fence.
`default_nettype none
module gpu_accel #(
    parameter FONT_FILE = "rtl/video/font8x16.hex"
) (
    input wire hclk, hresetn, hsel, hwrite,
    input wire [31:0] haddr, hwdata,
    input wire [1:0] htrans,
    output reg [31:0] hrdata,
    output wire hready,
    input wire mem_clk,
    output wire valid, write,
    output wire [28:0] addr,
    output wire [255:0] wr_data,
    output wire [31:0] wr_mask,
    input wire ready,
    input wire [255:0] rd_data,
    input wire rd_valid
);
    reg [1:0] mrst = 0;
    always @(posedge mem_clk or negedge hresetn)
        if (!hresetn) mrst <= 0; else mrst <= {mrst[0], 1'b1};
    reg [7:0] bus_addr;
    reg bus_write,bus_command;
    wire queue_ready,queue_full;
    // Register command-port decode during the AHB address phase, keeping
    // the address comparator off the CPU's HREADY feedback path.
    // AHB master and this FIFO share reset. Use registered fullness here:
    // the generic FIFO's reset-gated READY must not enter CPU feedback.
    assign hready = !(bus_command && queue_full);
    wire write_fire = bus_write && hready && hresetn;
    reg [11:0] font_write_addr;
    always @(posedge hclk) begin
        if (!hresetn) begin bus_addr <= 0; bus_write <= 0; bus_command<=0; font_write_addr <= 0; end
        else begin
            if (hready) begin
                bus_addr <= haddr[7:0]; bus_write <= hsel && htrans[1] && hwrite;
                bus_command<=hsel && htrans[1] && hwrite && haddr[7:0]==8'h10;
            end
            if (write_fire && bus_addr == 8'h14) font_write_addr <= hwdata[11:0];
            if (write_fire && bus_addr == 8'h18) font_write_addr <= font_write_addr + 1'b1;
        end
    end
    wire queue_valid, queue_pop;
    wire [31:0] queue_data, queue_lost;
    wire [7:0] queue_count, queue_rd_count;
    ddr_dcfifo #(.WIDTH(32), .DEPTH_LOG2(7)) u_commands (
        .wr_clk(hclk), .wr_rst(!hresetn), .wr_valid(bus_command && !queue_full),
        .wr_data(hwdata), .wr_ready(queue_ready), .wr_full(queue_full), .wr_lost(queue_lost), .wr_count(queue_count),
        .rd_clk(mem_clk), .rd_rst(!mrst[1]), .rd_valid(queue_valid), .rd_data(queue_data),
        .rd_ready(queue_pop), .rd_count(queue_rd_count));
    wire command_full, blitter_busy;
    reg [2:0] command_word;
    // Reserve a whole command in the rasterizer FIFO, then send all eight words.
    assign queue_pop = mrst[1] && (command_word != 0 || !command_full);
    wire command_we = queue_valid && queue_pop;
    always @(posedge mem_clk) begin
        if (!mrst[1]) command_word <= 0;
        else if (command_we) command_word <= command_word + 1'b1;
    end
    wire [15:0] done_count, command_lost, command_bad, r_done;
    wire [31:0] r_errors;
    cdc_word #(.WIDTH(16)) u_done (.src_clk(mem_clk), .src_data(done_count), .dst_clk(hclk), .dst_data(r_done));
    cdc_word u_errors (.src_clk(mem_clk), .src_data({command_bad,command_lost}), .dst_clk(hclk), .dst_data(r_errors));
    reg [1:0] busy_sync;
    always @(posedge hclk) begin
        if (!hresetn) busy_sync <= 0;
        else busy_sync <= {busy_sync[0], blitter_busy || queue_valid || command_word != 0};
    end
    always @* case (bus_addr)
        8'h00: hrdata = 32'h424c5432; // BLT2
        8'h04: hrdata = {30'b0, !queue_ready, busy_sync[1]};
        8'h08: hrdata = {16'b0, r_done};
        8'h0c: hrdata = r_errors;
        8'h14: hrdata = {20'b0, font_write_addr};
        8'h1c: hrdata = queue_lost;
        default: hrdata = 0;
    endcase
    wire [11:0] font_addr;
    wire [7:0] font_q;
    font_ram #(.FONT_FILE(FONT_FILE)) u_font (
        .wclk(hclk), .rclk(mem_clk), .we(write_fire && bus_addr == 8'h18),
        .waddr(font_write_addr), .wdata(hwdata[7:0]), .raddr(font_addr), .q(font_q));
    wire s_req, s_valid, s_done, w_req, w_ready, w_done, c_req, c_ack;
    wire [23:0] s_addr, w_addr, c_addr;
    wire [9:0] s_len, w_len;
    wire [15:0] s_data, w_data, c_data;
    wire [1:0] w_mask, c_mask;
    blitter u_blitter (
        .clk(mem_clk), .rst(!mrst[1]), .cmd_we(command_we), .cmd_data(queue_data), .cmd_full(command_full),
        .err_cmd_lost(command_lost), .err_cmd_bad(command_bad), .cmd_done(done_count), .busy(blitter_busy),
        .s_req(s_req), .s_addr(s_addr), .s_len(s_len), .s_valid(s_valid), .s_data(s_data), .s_done(s_done),
        .w_req(w_req), .w_addr(w_addr), .w_len(w_len), .w_data(w_data), .w_mask(w_mask), .w_ready(w_ready), .w_done(w_done),
        .c_req(c_req), .c_addr(c_addr), .c_wdata(c_data), .c_wmask(c_mask), .c_ack(c_ack),
        .font_addr(font_addr), .font_q(font_q));
    gpu_blit_dma u_dma (
        .clk(mem_clk), .rst(!mrst[1]),
        .s_req(s_req), .s_addr(s_addr), .s_len(s_len), .s_valid(s_valid), .s_data(s_data), .s_done(s_done),
        .w_req(w_req), .w_addr(w_addr), .w_len(w_len), .w_data(w_data), .w_mask(w_mask), .w_ready(w_ready), .w_done(w_done),
        .c_req(c_req), .c_addr(c_addr), .c_wdata(c_data), .c_wmask(c_mask), .c_ack(c_ack),
        .valid(valid), .write(write), .addr(addr), .wr_data(wr_data), .wr_mask(wr_mask),
        .ready(ready), .rd_data(rd_data), .rd_valid(rd_valid));
endmodule
`default_nettype wire
