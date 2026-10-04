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
    wire [31:0] raster_rejected,raster_fragments,raster_passed;
    wire [31:0] r_rejected,r_fragments,r_passed;
    wire [31:0] v1_rejected,v1_fragments,v1_passed,v1_hits,v1_misses;
    wire [31:0] v1r_rejected,v1r_fragments,v1r_passed,v1r_hits,v1r_misses;
    cdc_word u_v1_bad(.src_clk(mem_clk),.src_data(v1_rejected),.dst_clk(hclk),.dst_data(v1r_rejected));
    cdc_word u_v1_frag(.src_clk(mem_clk),.src_data(v1_fragments),.dst_clk(hclk),.dst_data(v1r_fragments));
    cdc_word u_v1_pass(.src_clk(mem_clk),.src_data(v1_passed),.dst_clk(hclk),.dst_data(v1r_passed));
    cdc_word u_v1_hits(.src_clk(mem_clk),.src_data(v1_hits),.dst_clk(hclk),.dst_data(v1r_hits));
    cdc_word u_v1_miss(.src_clk(mem_clk),.src_data(v1_misses),.dst_clk(hclk),.dst_data(v1r_misses));
    cdc_word u_raster_rejected (.src_clk(mem_clk),.src_data(raster_rejected),.dst_clk(hclk),.dst_data(r_rejected));
    cdc_word u_raster_fragments (.src_clk(mem_clk),.src_data(raster_fragments),.dst_clk(hclk),.dst_data(r_fragments));
    cdc_word u_raster_passed (.src_clk(mem_clk),.src_data(raster_passed),.dst_clk(hclk),.dst_data(r_passed));
    cdc_word #(.WIDTH(16)) u_done (.src_clk(mem_clk), .src_data(done_count), .dst_clk(hclk), .dst_data(r_done));
    cdc_word u_errors (.src_clk(mem_clk), .src_data({command_bad,command_lost}), .dst_clk(hclk), .dst_data(r_errors));
    reg [1:0] busy_sync;
    always @(posedge hclk) begin
        if (!hresetn) busy_sync <= 0;
        else busy_sync <= {busy_sync[0], blitter_busy || queue_valid || command_word != 0};
    end
    // Decode in the existing AHB address phase, keeping the return-data
    // path to the CPU bridge to an AND/OR selection with unchanged latency.
    reg [17:0] read_select;
    genvar reg_index;
    generate for(reg_index=0;reg_index<18;reg_index=reg_index+1)begin: read_decode
        always @(posedge hclk)
            if(!hresetn)read_select[reg_index]<=(reg_index==0);
            else if(hready)read_select[reg_index]<=(haddr[7:0]==reg_index*4);
    end endgenerate
    always @* hrdata=
        ({32{read_select[0]}} & 32'h424c5432) |
        ({32{read_select[1]}} & {30'b0,!queue_ready,busy_sync[1]}) |
        ({32{read_select[2]}} & {16'b0,r_done}) |
        ({32{read_select[3]}} & r_errors) |
        ({32{read_select[5]}} & {20'b0,font_write_addr}) |
        ({32{read_select[7]}} & queue_lost) |
        ({32{read_select[8]}} & 32'h0000001f) |
        ({32{read_select[9]}} & r_rejected) |
        ({32{read_select[10]}} & r_fragments) |
        ({32{read_select[11]}} & r_passed) |
        ({32{read_select[12]}} & 32'h000001ff) |
        ({32{read_select[13]}} & v1r_rejected) |
        ({32{read_select[14]}} & v1r_fragments) |
        ({32{read_select[15]}} & v1r_passed) |
        ({32{read_select[16]}} & v1r_hits) |
        ({32{read_select[17]}} & v1r_misses);
    wire [11:0] font_addr;
    wire [7:0] font_q;
    font_ram #(.FONT_FILE(FONT_FILE)) u_font (
        .wclk(hclk), .rclk(mem_clk), .we(write_fire && bus_addr == 8'h18),
        .waddr(font_write_addr), .wdata(hwdata[7:0]), .raddr(font_addr), .q(font_q));
    wire f_req,f_done;
    wire [24:0] f_addr;
    wire [10:0] f_len;
    wire [7:0] f_color;
    wire s_req, s_valid, s_done, w_req, w_ready, w_done, c_req, c_ack;
    wire [23:0] s_addr, w_addr, c_addr;
    wire [9:0] s_len, w_len;
    wire [15:0] s_data, w_data, c_data;
    wire [1:0] w_mask, c_mask;
    wire ext_start,ext_active,ext_done;
    wire [255:0] ext_command;
    wire legacy_valid,legacy_write,raster_valid,raster_write;
    wire [28:0] legacy_addr,raster_addr;
    wire [255:0] legacy_data,raster_data;
    wire [31:0] legacy_mask,raster_mask;
    // The opcode is stable before ext_start; latch ownership outside a command.
    // This keeps opcode decode off the arbiter READY feedback path.
    reg v1_select;
    always @(posedge mem_clk)
        if(!mrst[1])v1_select<=0;
        else if(!ext_active)v1_select<=ext_command[31:24]>=22;
    wire old_done,v1_done,v1_valid,v1_write,v1_request;
    reg v1_accepted,v1_pending,v1_tx_write,v1_rx_valid;
    reg [28:0] v1_tx_addr;
    reg [255:0] v1_tx_data,v1_rx_data;
    reg [31:0] v1_tx_mask;
    wire [28:0] v1_addr;
    wire [255:0] v1_data;
    wire [31:0] v1_mask;
    // Isolate the extended shader's request multiplexers and wide reply loads
    // from the shared DDR arbiter. Hold one complete transaction until accepted.
    // The acknowledgement guard prevents recapturing the engine's old VALID
    // on the cycle in which it observes the registered acceptance pulse.
    always @(posedge mem_clk)begin
        v1_rx_data<=rd_data;
        if(!mrst[1])begin
            v1_accepted<=0;v1_pending<=0;v1_rx_valid<=0;
            v1_tx_addr<=0;v1_tx_data<=0;v1_tx_mask<=-1;v1_tx_write<=0;
        end else begin
            v1_accepted<=v1_pending && ready;
            v1_rx_valid<=rd_valid && ext_active && v1_select;
            if(v1_pending)begin
                if(ready)v1_pending<=0;
            end else if(v1_request && !v1_accepted)begin
                v1_pending<=1;v1_tx_addr<=v1_addr;v1_tx_data<=v1_data;
                v1_tx_mask<=v1_mask;v1_tx_write<=v1_write;
            end
        end
    end
    assign v1_valid=v1_pending;
    assign ext_done=v1_select ? v1_done:old_done;
    gpu_v1 u_v1(.clk(mem_clk),.rst(!mrst[1]),.start(ext_start && v1_select),.command(ext_command),
        .busy(),.done(v1_done),.rejected(v1_rejected),.fragments(v1_fragments),.passed(v1_passed),
        .texture_hits(v1_hits),.texture_misses(v1_misses),.valid(v1_request),.write(v1_write),
        .addr(v1_addr),.wr_data(v1_data),.wr_mask(v1_mask),
        .ready(v1_accepted),.rd_valid(v1_rx_valid),.rd_data(v1_rx_data));
    // The ordered command queue starts only one engine at a time; each engine
    // drops VALID before completion. Use those registered request flags for
    // transaction control. The wide payload's owner mux must not feed WRITE
    // and then loop through arbiter READY into the engine state machines.
    assign valid=legacy_valid || raster_valid || v1_valid;
    assign write=(legacy_valid && legacy_write) || (raster_valid && raster_write) ||
                 (v1_valid && v1_tx_write);
    assign addr=ext_active ? (v1_select ? v1_tx_addr:raster_addr):legacy_addr;
    assign wr_data=ext_active ? (v1_select ? v1_tx_data:raster_data):legacy_data;
    assign wr_mask=ext_active ? (v1_select ? v1_tx_mask:raster_mask):legacy_mask;
    gpu_raster u_raster (
        .clk(mem_clk),.rst(!mrst[1]),.start(ext_start && !v1_select),.command(ext_command),.busy(),.done(old_done),
        .rejected(raster_rejected),.fragments(raster_fragments),.passed(raster_passed),
        .valid(raster_valid),.write(raster_write),.addr(raster_addr),.wr_data(raster_data),.wr_mask(raster_mask),
        .ready(ready),.rd_data(rd_data),.rd_valid(rd_valid && ext_active && !v1_select));
    blitter u_blitter (
        .clk(mem_clk), .rst(!mrst[1]), .cmd_we(command_we), .cmd_data(queue_data), .cmd_full(command_full),
        .err_cmd_lost(command_lost), .err_cmd_bad(command_bad), .cmd_done(done_count), .busy(blitter_busy),
        .ext_start(ext_start),.ext_active(ext_active),.ext_command(ext_command),.ext_done(ext_done),
        .s_req(s_req), .s_addr(s_addr), .s_len(s_len), .s_valid(s_valid), .s_data(s_data), .s_done(s_done),
        .w_req(w_req), .w_addr(w_addr), .w_len(w_len), .w_data(w_data), .w_mask(w_mask), .w_ready(w_ready), .w_done(w_done),
        .f_req(f_req),.f_addr(f_addr),.f_len(f_len),.f_color(f_color),.f_done(f_done),
        .c_req(c_req), .c_addr(c_addr), .c_wdata(c_data), .c_wmask(c_mask), .c_ack(c_ack),
        .font_addr(font_addr), .font_q(font_q));
    gpu_blit_dma u_dma (
        .clk(mem_clk), .rst(!mrst[1]),
        .s_req(s_req), .s_addr(s_addr), .s_len(s_len), .s_valid(s_valid), .s_data(s_data), .s_done(s_done),
        .w_req(w_req), .w_addr(w_addr), .w_len(w_len), .w_data(w_data), .w_mask(w_mask), .w_ready(w_ready), .w_done(w_done),
        .f_req(f_req),.f_addr(f_addr),.f_len(f_len),.f_color(f_color),.f_done(f_done),
        .c_req(c_req), .c_addr(c_addr), .c_wdata(c_data), .c_wmask(c_mask), .c_ack(c_ack),
        .valid(legacy_valid), .write(legacy_write), .addr(legacy_addr), .wr_data(legacy_data), .wr_mask(legacy_mask),
        .ready(ready), .rd_data(rd_data), .rd_valid(rd_valid && !ext_active));
endmodule
`default_nettype wire
