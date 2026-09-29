// Bound into the real blitter during the 541-command AHB/DDR regression.
// blitter_reference is an unchanged earlier source, renamed by the runner.
// Check control every cycle and data exactly when the DMA consumes it.
module blitter_equiv #(parameter WIDTH=800, HEIGHT=480,
    parameter [23:0] PAGE_BASE_WORDS=24'h400000) (
    input wire  clk,
    input wire  rst,
    input wire  cmd_we,
    input wire [31:0] cmd_data,
    input wire  cmd_full,
    input wire [15:0] err_cmd_lost,
    input wire [15:0] err_cmd_bad,
    input wire [15:0] cmd_done,
    input wire  busy,
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
    input wire [11:0] font_addr,
    input wire [7:0] font_q
);
    wire  ref_cmd_full;
    wire [15:0] ref_err_cmd_lost;
    wire [15:0] ref_err_cmd_bad;
    wire [15:0] ref_cmd_done;
    wire  ref_busy;
    wire  ref_s_req;
    wire [23:0] ref_s_addr;
    wire [9:0] ref_s_len;
    wire  ref_w_req;
    wire [23:0] ref_w_addr;
    wire [9:0] ref_w_len;
    wire [15:0] ref_w_data;
    wire [1:0] ref_w_mask;
    wire  ref_f_req;
    wire [24:0] ref_f_addr;
    wire [10:0] ref_f_len;
    wire [7:0] ref_f_color;
    wire  ref_c_req;
    wire [23:0] ref_c_addr;
    wire [15:0] ref_c_wdata;
    wire [1:0] ref_c_wmask;
    wire [11:0] ref_font_addr;
    blitter_reference #(.WIDTH(WIDTH), .HEIGHT(HEIGHT),
        .PAGE_BASE_WORDS(PAGE_BASE_WORDS)) reference (
        .clk(clk),
        .rst(rst),
        .cmd_we(cmd_we),
        .cmd_data(cmd_data),
        .cmd_full(ref_cmd_full),
        .err_cmd_lost(ref_err_cmd_lost),
        .err_cmd_bad(ref_err_cmd_bad),
        .cmd_done(ref_cmd_done),
        .busy(ref_busy),
        .s_req(ref_s_req),
        .s_addr(ref_s_addr),
        .s_len(ref_s_len),
        .s_valid(s_valid),
        .s_data(s_data),
        .s_done(s_done),
        .w_req(ref_w_req),
        .w_addr(ref_w_addr),
        .w_len(ref_w_len),
        .w_data(ref_w_data),
        .w_mask(ref_w_mask),
        .w_ready(w_ready),
        .w_done(w_done),
        .f_req(ref_f_req),
        .f_addr(ref_f_addr),
        .f_len(ref_f_len),
        .f_color(ref_f_color),
        .f_done(f_done),
        .c_req(ref_c_req),
        .c_addr(ref_c_addr),
        .c_wdata(ref_c_wdata),
        .c_wmask(ref_c_wmask),
        .c_ack(c_ack),
        .font_addr(ref_font_addr),
        .font_q(font_q)
    );
    integer checked_cycles=0, checked_words=0;
    always @(posedge clk) if (!rst) begin
        checked_cycles++;
        if (cmd_full !== ref_cmd_full) $fatal(1, "Blitter equivalence: cmd_full");
        if (err_cmd_lost !== ref_err_cmd_lost) $fatal(1, "Blitter equivalence: err_cmd_lost");
        if (err_cmd_bad !== ref_err_cmd_bad) $fatal(1, "Blitter equivalence: err_cmd_bad");
        if (cmd_done !== ref_cmd_done) $fatal(1, "Blitter equivalence: cmd_done");
        if (busy !== ref_busy) $fatal(1, "Blitter equivalence: busy");
        if (s_req !== ref_s_req) $fatal(1, "Blitter equivalence: s_req");
        if (s_addr !== ref_s_addr) $fatal(1, "Blitter equivalence: s_addr");
        if (s_len !== ref_s_len) $fatal(1, "Blitter equivalence: s_len");
        if (w_req !== ref_w_req) $fatal(1, "Blitter equivalence: w_req");
        if (w_addr !== ref_w_addr) $fatal(1, "Blitter equivalence: w_addr");
        if (w_len !== ref_w_len) $fatal(1, "Blitter equivalence: w_len");
        if (f_req !== ref_f_req) $fatal(1, "Blitter equivalence: f_req");
        if (f_addr !== ref_f_addr) $fatal(1, "Blitter equivalence: f_addr");
        if (f_len !== ref_f_len) $fatal(1, "Blitter equivalence: f_len");
        if (f_color !== ref_f_color) $fatal(1, "Blitter equivalence: f_color");
        if (c_req !== ref_c_req) $fatal(1, "Blitter equivalence: c_req");
        if (c_addr !== ref_c_addr) $fatal(1, "Blitter equivalence: c_addr");
        if (c_wdata !== ref_c_wdata) $fatal(1, "Blitter equivalence: c_wdata");
        if (c_wmask !== ref_c_wmask) $fatal(1, "Blitter equivalence: c_wmask");
        if (font_addr !== ref_font_addr) $fatal(1, "Blitter equivalence: font_addr");
        if (w_ready) begin
            checked_words++;
            if (w_mask !== ref_w_mask) $fatal(1, "Blitter equivalence: w_mask");
            for (integer byte_lane=0; byte_lane<2; byte_lane++)
                if (w_mask[byte_lane] && w_data[byte_lane*8+:8] !== ref_w_data[byte_lane*8+:8])
                    $fatal(1, "Blitter equivalence: consumed pixel");
        end
    end
    final $display("PASS blitter equivalence: %0d cycles, %0d words", checked_cycles, checked_words);
endmodule
bind blitter blitter_equiv #(.WIDTH(WIDTH), .HEIGHT(HEIGHT),
    .PAGE_BASE_WORDS(PAGE_BASE_WORDS)) proof (.*);
