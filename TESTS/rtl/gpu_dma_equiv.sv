// Historical L11 comparison used a one-clock completion delay. Newer
// snapshots already register completion and must compare without a delay.
`ifndef DMA_COMPLETION_DELAY
`define DMA_COMPLETION_DELAY 1
`endif
module gpu_dma_equiv (
    input wire  clk,
    input wire  rst,
    input wire  s_req,
    input wire [23:0] s_addr,
    input wire [9:0] s_len,
    input wire  s_valid,
    input wire [15:0] s_data,
    input wire  s_done,
    input wire  w_req,
    input wire [23:0] w_addr,
    input wire [9:0] w_len,
    input wire [15:0] w_data,
    input wire [1:0] w_mask,
    input wire  w_ready,
    input wire  w_done,
    input wire  f_req,
    input wire [24:0] f_addr,
    input wire [10:0] f_len,
    input wire [7:0] f_color,
    input wire  f_done,
    input wire  c_req,
    input wire [23:0] c_addr,
    input wire [15:0] c_wdata,
    input wire [1:0] c_wmask,
    input wire  c_ack,
    input wire  valid,
    input wire  write,
    input wire [28:0] addr,
    input wire [255:0] wr_data,
    input wire [31:0] wr_mask,
    input wire  ready,
    input wire [255:0] rd_data,
    input wire  rd_valid
);
    wire  ref_s_valid;
    wire [15:0] ref_s_data;
    wire  ref_s_done;
    wire  ref_w_ready;
    wire  ref_w_done;
    wire  ref_f_done;
    wire  ref_c_ack;
    wire  ref_valid;
    wire  ref_write;
    wire [28:0] ref_addr;
    wire [255:0] ref_wr_data;
    wire [31:0] ref_wr_mask;
    gpu_blit_dma_reference reference (
        .clk(clk),
        .rst(rst),
        .s_req(s_req),
        .s_addr(s_addr),
        .s_len(s_len),
        .s_valid(ref_s_valid),
        .s_data(ref_s_data),
        .s_done(ref_s_done),
        .w_req(w_req),
        .w_addr(w_addr),
        .w_len(w_len),
        .w_data(w_data),
        .w_mask(w_mask),
        .w_ready(ref_w_ready),
        .w_done(ref_w_done),
        .f_req(f_req),
        .f_addr(f_addr),
        .f_len(f_len),
        .f_color(f_color),
        .f_done(ref_f_done),
        .c_req(c_req),
        .c_addr(c_addr),
        .c_wdata(c_wdata),
        .c_wmask(c_wmask),
        .c_ack(ref_c_ack),
        .valid(ref_valid),
        .write(ref_write),
        .addr(ref_addr),
        .wr_data(ref_wr_data),
        .wr_mask(ref_wr_mask),
        .ready(ready),
        .rd_data(rd_data),
        .rd_valid(rd_valid)
    );
    reg previous_w_done=0,previous_f_done=0,previous_c_ack=0;
    always @(posedge clk) begin
        previous_w_done<=ref_w_done;previous_f_done<=ref_f_done;previous_c_ack<=ref_c_ack;
    end
    integer cycles=0;
    always @(negedge clk) if(!rst) begin
        cycles++;
        if(s_valid !== ref_s_valid) $fatal(1,"DMA equivalence: s_valid");
        if(s_data !== ref_s_data) $fatal(1,"DMA equivalence: s_data");
        if(s_done !== ref_s_done) $fatal(1,"DMA equivalence: s_done");
        if(w_ready !== ref_w_ready) $fatal(1,"DMA equivalence: w_ready");
        if(w_done !== (`DMA_COMPLETION_DELAY ? previous_w_done:ref_w_done)) $fatal(1,"DMA equivalence: w_done");
        if(f_done !== (`DMA_COMPLETION_DELAY ? previous_f_done:ref_f_done)) $fatal(1,"DMA equivalence: f_done");
        if(c_ack !== (`DMA_COMPLETION_DELAY ? previous_c_ack:ref_c_ack)) $fatal(1,"DMA equivalence: c_ack");
        if(valid !== ref_valid) $fatal(1,"DMA equivalence: valid");
        if(write !== ref_write) $fatal(1,"DMA equivalence: write");
        // Address may advance during the idle cycle after an accepted write.
        // Every offered command, including every stalled cycle, must match.
        if(valid && addr !== ref_addr) $fatal(1,"DMA equivalence: offered addr");
        if(wr_data !== ref_wr_data) $fatal(1,"DMA equivalence: wr_data");
        if(wr_mask !== ref_wr_mask) $fatal(1,"DMA equivalence: wr_mask");
    end
    final $display("PASS DMA equivalence: %0d cycles, native commands identical, completion delay=%0d",cycles,`DMA_COMPLETION_DELAY);
endmodule
bind gpu_blit_dma gpu_dma_equiv proof (.*);
