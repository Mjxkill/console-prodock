// Console CPU memory path, with acquisition/video request inputs idle.
// Native DDR is modeled by the caller; the real arbiters/adapter are used.
`default_nettype none
module neo_ddr_cpu_path (
    input wire clk,rst_n,c_en,c_wr_en,
    input wire [2:0] c_cmd,
    input wire [28:0] c_addr,
    input wire [127:0] c_wr_data,
    input wire [15:0] c_wr_mask,
    output wire c_ready,c_wr_ready,c_rd_valid,
    output wire [127:0] c_rd_data,
    output wire m_en,m_wr_en,
    output wire [2:0] m_cmd,
    output wire [28:0] m_addr,
    output wire [255:0] m_wr_data,
    output wire [31:0] m_wr_mask,
    input wire m_ready,m_wr_ready,m_rd_valid,
    input wire [255:0] m_rd_data
);
    wire a_en,a_ready,a_we,a_wend,a_wr_ready,a_rv,a_rend;
    wire [2:0] a_cmd;
    wire [28:0] a_addr;
    wire [127:0] a_wdata,a_rdata;
    wire [15:0] a_mask;
    wire n_en,n_ready,n_we,n_wend,n_wr_ready,n_rv,n_rend;
    wire [2:0] n_cmd;
    wire [28:0] n_addr;
    wire [255:0] n_wdata,n_rdata;
    wire [31:0] n_mask;
    ddr_arb arb(
        .clk(clk),.rst_n(rst_n),
        .m0_cmd_en(c_en),.m0_cmd(c_cmd),.m0_addr(c_addr),.m0_cmd_ready(c_ready),
        .m0_wr_en(c_wr_en),.m0_wr_data(c_wr_data),.m0_wr_mask(c_wr_mask),.m0_wr_rdy(c_wr_ready),
        .m0_rd_data(c_rd_data),.m0_rd_valid(c_rd_valid),.m0_rd_end(),
        .m1_cmd_en(1'b0),.m1_addr(29'd0),.m1_wr_data(128'd0),.m1_wr_mask(16'hffff),.m1_urgent(1'b0),.m1_ready(),
        .m2_cmd_en(1'b0),.m2_addr(29'd0),.m2_ready(),.m2_rd_data(),.m2_rd_valid(),.dbg(),
        .ui_cmd_en(a_en),.ui_cmd(a_cmd),.ui_addr(a_addr),.ui_cmd_ready(a_ready),
        .ui_wr_data_en(a_we),.ui_wr_data_end(a_wend),.ui_wr_data(a_wdata),.ui_wr_data_mask(a_mask),.ui_wr_data_rdy(a_wr_ready),
        .ui_rd_data(a_rdata),.ui_rd_data_valid(a_rv),.ui_rd_data_end(a_rend));
    ddr_ui_adapt adapt(
        .clk(clk),.rst_n(rst_n),.u_cmd_en(a_en),.u_cmd(a_cmd),.u_addr(a_addr),.u_cmd_ready(a_ready),
        .u_wr_data_en(a_we),.u_wr_data_end(a_wend),.u_wr_data(a_wdata),.u_wr_data_mask(a_mask),.u_wr_data_rdy(a_wr_ready),
        .u_rd_data(a_rdata),.u_rd_data_valid(a_rv),.u_rd_data_end(a_rend),
        .ip_cmd_en(n_en),.ip_cmd(n_cmd),.ip_addr(n_addr),.ip_cmd_ready(n_ready),
        .ip_wr_data_en(n_we),.ip_wr_data_end(n_wend),.ip_wr_data(n_wdata),.ip_wr_data_mask(n_mask),.ip_wr_data_rdy(n_wr_ready),
        .ip_rd_data(n_rdata),.ip_rd_data_valid(n_rv),.ip_rd_data_end(n_rend));
    ddr_gpu_arb gpu_arb(
        .clk(clk),.rst_n(rst_n),.c_en(n_en),.c_cmd(n_cmd),.c_addr(n_addr),.c_ready(n_ready),
        .c_wr_en(n_we),.c_wr_end(n_wend),.c_wr_data(n_wdata),.c_wr_mask(n_mask),.c_wr_ready(n_wr_ready),
        .c_rd_data(n_rdata),.c_rd_valid(n_rv),.c_rd_end(n_rend),
        .g_valid(1'b0),.g_addr(29'd0),.g_ready(),.g_data(),.g_data_valid(),
        .b_valid(1'b0),.b_write(1'b0),.b_addr(29'd0),.b_wr_data(256'd0),.b_wr_mask(32'hffffffff),
        .b_ready(),.b_rd_data(),.b_rd_valid(),
        .m_en(m_en),.m_cmd(m_cmd),.m_addr(m_addr),.m_ready(m_ready),
        .m_wr_en(m_wr_en),.m_wr_end(),.m_wr_data(m_wr_data),.m_wr_mask(m_wr_mask),.m_wr_ready(m_wr_ready),
        .m_rd_data(m_rd_data),.m_rd_valid(m_rd_valid),.m_rd_end(m_rd_valid));
endmodule
`default_nettype wire
