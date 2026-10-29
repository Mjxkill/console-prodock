// Shared native DDR3 UI: CPU adapter, scanout reads and blitter reads/writes.
// Addresses are 32-bit words, aligned to eight words (32 bytes).
// CPU upstream issues command+data pulses only when ready; capture them in a
// one-entry buffer to break the ready chain through the legacy CPU adapter.
// Scanout has priority for bounded line fetches; CPU/blitter alternate otherwise.
// Their grant is registered, so changing clients may insert an idle cycle.
`default_nettype none
module ddr_gpu_arb_equiv (
    input wire clk, rst_n,
    input wire c_en,
    input wire [2:0] c_cmd,
    input wire [28:0] c_addr,
    output wire c_ready,
    input wire c_wr_en, c_wr_end,
    input wire [255:0] c_wr_data,
    input wire [31:0] c_wr_mask,
    output wire c_wr_ready,
    output wire [255:0] c_rd_data,
    output wire c_rd_valid, c_rd_end,
    input wire g_valid,
    input wire [28:0] g_addr,
    output wire g_ready,
    output wire [255:0] g_data,
    output wire g_data_valid,
    input wire b_valid, b_write,
    input wire [28:0] b_addr,
    input wire [255:0] b_wr_data,
    input wire [31:0] b_wr_mask,
    output wire b_ready,
    output wire [255:0] b_rd_data,
    output wire b_rd_valid,
    output wire m_en,
    output wire [2:0] m_cmd,
    output wire [28:0] m_addr,
    input wire m_ready,
    output wire m_wr_en, m_wr_end,
    output wire [255:0] m_wr_data,
    output wire [31:0] m_wr_mask,
    input wire m_wr_ready,
    input wire [255:0] m_rd_data,
    input wire m_rd_valid, m_rd_end
);
    wire  ref_c_ready;
    wire  ref_c_wr_ready;
    wire [255:0] ref_c_rd_data;
    wire  ref_c_rd_valid;
    wire  ref_c_rd_end;
    wire  ref_g_ready;
    wire [255:0] ref_g_data;
    wire  ref_g_data_valid;
    wire  ref_b_ready;
    wire [255:0] ref_b_rd_data;
    wire  ref_b_rd_valid;
    wire  ref_m_en;
    wire [2:0] ref_m_cmd;
    wire [28:0] ref_m_addr;
    wire  ref_m_wr_en;
    wire  ref_m_wr_end;
    wire [255:0] ref_m_wr_data;
    wire [31:0] ref_m_wr_mask;
    ddr_gpu_arb u_ddr_gpu_arb (.clk(clk), .rst_n(rst_n), .c_en(c_en), .c_cmd(c_cmd), .c_addr(c_addr), .c_wr_en(c_wr_en), .c_wr_end(c_wr_end), .c_wr_data(c_wr_data), .c_wr_mask(c_wr_mask), .g_valid(g_valid), .g_addr(g_addr), .b_valid(b_valid), .b_write(b_write), .b_addr(b_addr), .b_wr_data(b_wr_data), .b_wr_mask(b_wr_mask), .m_ready(m_ready), .m_wr_ready(m_wr_ready), .m_rd_data(m_rd_data), .m_rd_valid(m_rd_valid), .m_rd_end(m_rd_end), .c_ready(c_ready), .c_wr_ready(c_wr_ready), .c_rd_data(c_rd_data), .c_rd_valid(c_rd_valid), .c_rd_end(c_rd_end), .g_ready(g_ready), .g_data(g_data), .g_data_valid(g_data_valid), .b_ready(b_ready), .b_rd_data(b_rd_data), .b_rd_valid(b_rd_valid), .m_en(m_en), .m_cmd(m_cmd), .m_addr(m_addr), .m_wr_en(m_wr_en), .m_wr_end(m_wr_end), .m_wr_data(m_wr_data), .m_wr_mask(m_wr_mask));
    ddr_gpu_arb_reference u_ddr_gpu_arb_reference (.clk(clk), .rst_n(rst_n), .c_en(c_en), .c_cmd(c_cmd), .c_addr(c_addr), .c_wr_en(c_wr_en), .c_wr_end(c_wr_end), .c_wr_data(c_wr_data), .c_wr_mask(c_wr_mask), .g_valid(g_valid), .g_addr(g_addr), .b_valid(b_valid), .b_write(b_write), .b_addr(b_addr), .b_wr_data(b_wr_data), .b_wr_mask(b_wr_mask), .m_ready(m_ready), .m_wr_ready(m_wr_ready), .m_rd_data(m_rd_data), .m_rd_valid(m_rd_valid), .m_rd_end(m_rd_end), .c_ready(ref_c_ready), .c_wr_ready(ref_c_wr_ready), .c_rd_data(ref_c_rd_data), .c_rd_valid(ref_c_rd_valid), .c_rd_end(ref_c_rd_end), .g_ready(ref_g_ready), .g_data(ref_g_data), .g_data_valid(ref_g_data_valid), .b_ready(ref_b_ready), .b_rd_data(ref_b_rd_data), .b_rd_valid(ref_b_rd_valid), .m_en(ref_m_en), .m_cmd(ref_m_cmd), .m_addr(ref_m_addr), .m_wr_en(ref_m_wr_en), .m_wr_end(ref_m_wr_end), .m_wr_data(ref_m_wr_data), .m_wr_mask(ref_m_wr_mask));
    integer compared_cycles=0;
    always @(posedge clk) if(rst_n)begin
        compared_cycles<=compared_cycles+1;
        if(1'b1 && c_ready !== ref_c_ready) $fatal(1,"Arbiter c_ready mismatch at %0d",compared_cycles);
        if(1'b1 && c_wr_ready !== ref_c_wr_ready) $fatal(1,"Arbiter c_wr_ready mismatch at %0d",compared_cycles);
        if(1'b1 && c_rd_data !== ref_c_rd_data) $fatal(1,"Arbiter c_rd_data mismatch at %0d",compared_cycles);
        if(1'b1 && c_rd_valid !== ref_c_rd_valid) $fatal(1,"Arbiter c_rd_valid mismatch at %0d",compared_cycles);
        if(1'b1 && c_rd_end !== ref_c_rd_end) $fatal(1,"Arbiter c_rd_end mismatch at %0d",compared_cycles);
        if(1'b1 && g_ready !== ref_g_ready) $fatal(1,"Arbiter g_ready mismatch at %0d",compared_cycles);
        if(1'b1 && g_data !== ref_g_data) $fatal(1,"Arbiter g_data mismatch at %0d",compared_cycles);
        if(1'b1 && g_data_valid !== ref_g_data_valid) $fatal(1,"Arbiter g_data_valid mismatch at %0d",compared_cycles);
        if(1'b1 && b_ready !== ref_b_ready) $fatal(1,"Arbiter b_ready mismatch at %0d",compared_cycles);
        if(1'b1 && b_rd_data !== ref_b_rd_data) $fatal(1,"Arbiter b_rd_data mismatch at %0d",compared_cycles);
        if(1'b1 && b_rd_valid !== ref_b_rd_valid) $fatal(1,"Arbiter b_rd_valid mismatch at %0d",compared_cycles);
        if(1'b1 && m_en !== ref_m_en) $fatal(1,"Arbiter m_en mismatch at %0d",compared_cycles);
        if(m_en && m_cmd !== ref_m_cmd) $fatal(1,"Arbiter m_cmd mismatch at %0d",compared_cycles);
        if(m_en && m_addr !== ref_m_addr) $fatal(1,"Arbiter m_addr mismatch at %0d",compared_cycles);
        if(1'b1 && m_wr_en !== ref_m_wr_en) $fatal(1,"Arbiter m_wr_en mismatch at %0d",compared_cycles);
        if(1'b1 && m_wr_end !== ref_m_wr_end) $fatal(1,"Arbiter m_wr_end mismatch at %0d",compared_cycles);
        if(m_wr_en && m_wr_data !== ref_m_wr_data) $fatal(1,"Arbiter m_wr_data mismatch at %0d",compared_cycles);
        if(m_wr_en && m_wr_mask !== ref_m_wr_mask) $fatal(1,"Arbiter m_wr_mask mismatch at %0d",compared_cycles);
        if(u_ddr_gpu_arb.wp !== u_ddr_gpu_arb_reference.wp) $fatal(1,"Arbiter wp mismatch at %0d",compared_cycles);
        if(u_ddr_gpu_arb.rp !== u_ddr_gpu_arb_reference.rp) $fatal(1,"Arbiter rp mismatch at %0d",compared_cycles);
        if(u_ddr_gpu_arb.full !== u_ddr_gpu_arb_reference.full) $fatal(1,"Arbiter full mismatch at %0d",compared_cycles);
    end
    final $display("ARBITER EQUIVALENCE: %0d cycles compared",compared_cycles);
endmodule
