`timescale 1ns/1ps
// Exhaustive arbitration/ready equivalence against the unchanged module.
// State is fixed to each possible grant condition; data are distinct per master.
module ddr_arb_equiv;
    reg  clk=0;
    reg  rst_n=0;
    reg  m0_cmd_en=0;
    reg [2:0] m0_cmd=0;
    reg [28:0] m0_addr=0;
    wire  m0_cmd_ready;
    wire  ref_m0_cmd_ready;
    reg  m0_wr_en=0;
    reg [127:0] m0_wr_data=0;
    reg [15:0] m0_wr_mask=0;
    wire  m0_wr_rdy;
    wire  ref_m0_wr_rdy;
    wire [127:0] m0_rd_data;
    wire [127:0] ref_m0_rd_data;
    wire  m0_rd_valid;
    wire  ref_m0_rd_valid;
    wire  m0_rd_end;
    wire  ref_m0_rd_end;
    reg  m1_cmd_en=0;
    reg [28:0] m1_addr=0;
    reg [127:0] m1_wr_data=0;
    reg [15:0] m1_wr_mask=0;
    reg  m1_urgent=0;
    wire  m1_ready;
    wire  ref_m1_ready;
    reg  m2_cmd_en=0;
    reg [28:0] m2_addr=0;
    wire  m2_ready;
    wire  ref_m2_ready;
    wire [127:0] m2_rd_data;
    wire [127:0] ref_m2_rd_data;
    wire  m2_rd_valid;
    wire  ref_m2_rd_valid;
    wire  ui_cmd_en;
    wire  ref_ui_cmd_en;
    wire [2:0] ui_cmd;
    wire [2:0] ref_ui_cmd;
    wire [28:0] ui_addr;
    wire [28:0] ref_ui_addr;
    reg  ui_cmd_ready=0;
    wire  ui_wr_data_en;
    wire  ref_ui_wr_data_en;
    wire  ui_wr_data_end;
    wire  ref_ui_wr_data_end;
    wire [127:0] ui_wr_data;
    wire [127:0] ref_ui_wr_data;
    wire [15:0] ui_wr_data_mask;
    wire [15:0] ref_ui_wr_data_mask;
    reg  ui_wr_data_rdy=0;
    reg [127:0] ui_rd_data=0;
    reg  ui_rd_data_valid=0;
    reg  ui_rd_data_end=0;
    wire [3:0] dbg;
    wire [3:0] ref_dbg;
    ddr_arb dut (
        .clk(clk),
        .rst_n(rst_n),
        .m0_cmd_en(m0_cmd_en),
        .m0_cmd(m0_cmd),
        .m0_addr(m0_addr),
        .m0_cmd_ready(m0_cmd_ready),
        .m0_wr_en(m0_wr_en),
        .m0_wr_data(m0_wr_data),
        .m0_wr_mask(m0_wr_mask),
        .m0_wr_rdy(m0_wr_rdy),
        .m0_rd_data(m0_rd_data),
        .m0_rd_valid(m0_rd_valid),
        .m0_rd_end(m0_rd_end),
        .m1_cmd_en(m1_cmd_en),
        .m1_addr(m1_addr),
        .m1_wr_data(m1_wr_data),
        .m1_wr_mask(m1_wr_mask),
        .m1_urgent(m1_urgent),
        .m1_ready(m1_ready),
        .m2_cmd_en(m2_cmd_en),
        .m2_addr(m2_addr),
        .m2_ready(m2_ready),
        .m2_rd_data(m2_rd_data),
        .m2_rd_valid(m2_rd_valid),
        .ui_cmd_en(ui_cmd_en),
        .ui_cmd(ui_cmd),
        .ui_addr(ui_addr),
        .ui_cmd_ready(ui_cmd_ready),
        .ui_wr_data_en(ui_wr_data_en),
        .ui_wr_data_end(ui_wr_data_end),
        .ui_wr_data(ui_wr_data),
        .ui_wr_data_mask(ui_wr_data_mask),
        .ui_wr_data_rdy(ui_wr_data_rdy),
        .ui_rd_data(ui_rd_data),
        .ui_rd_data_valid(ui_rd_data_valid),
        .ui_rd_data_end(ui_rd_data_end),
        .dbg(dbg)
    );
    ddr_arb_reference reference (
        .clk(clk),
        .rst_n(rst_n),
        .m0_cmd_en(m0_cmd_en),
        .m0_cmd(m0_cmd),
        .m0_addr(m0_addr),
        .m0_cmd_ready(ref_m0_cmd_ready),
        .m0_wr_en(m0_wr_en),
        .m0_wr_data(m0_wr_data),
        .m0_wr_mask(m0_wr_mask),
        .m0_wr_rdy(ref_m0_wr_rdy),
        .m0_rd_data(ref_m0_rd_data),
        .m0_rd_valid(ref_m0_rd_valid),
        .m0_rd_end(ref_m0_rd_end),
        .m1_cmd_en(m1_cmd_en),
        .m1_addr(m1_addr),
        .m1_wr_data(m1_wr_data),
        .m1_wr_mask(m1_wr_mask),
        .m1_urgent(m1_urgent),
        .m1_ready(ref_m1_ready),
        .m2_cmd_en(m2_cmd_en),
        .m2_addr(m2_addr),
        .m2_ready(ref_m2_ready),
        .m2_rd_data(ref_m2_rd_data),
        .m2_rd_valid(ref_m2_rd_valid),
        .ui_cmd_en(ref_ui_cmd_en),
        .ui_cmd(ref_ui_cmd),
        .ui_addr(ref_ui_addr),
        .ui_cmd_ready(ui_cmd_ready),
        .ui_wr_data_en(ref_ui_wr_data_en),
        .ui_wr_data_end(ref_ui_wr_data_end),
        .ui_wr_data(ref_ui_wr_data),
        .ui_wr_data_mask(ref_ui_wr_data_mask),
        .ui_wr_data_rdy(ui_wr_data_rdy),
        .ui_rd_data(ui_rd_data),
        .ui_rd_data_valid(ui_rd_data_valid),
        .ui_rd_data_end(ui_rd_data_end),
        .dbg(ref_dbg)
    );
    integer cases=0;
    initial begin
        force dut.b_addr=29'h1234560;
        force dut.b_data=128'h00112233445566778899aabbccddeeff;
        force dut.b_mask=16'h5a3c;
        force reference.b_addr=29'h1234560;
        force reference.b_data=128'h00112233445566778899aabbccddeeff;
        force reference.b_mask=16'h5a3c;
        m1_addr=29'h2468130; m2_addr=29'h3579120;
        m1_wr_data=128'hfedcba98765432100123456789abcdef; m1_wr_mask=16'ha5c3;
        for(integer code=0;code<4096;code++) begin
            {ui_cmd_ready,ui_wr_data_rdy,m1_cmd_en,m2_cmd_en,m1_urgent}=code[4:0];
            force dut.b_full=code[5];
            force dut.tq_full=code[6];
            force dut.b_wr=code[7];
            force dut.b_cmd=code[10:8];
            force reference.b_full=code[5];
            force reference.tq_full=code[6];
            force reference.b_wr=code[7];
            force reference.b_cmd=code[10:8];
            rst_n=code[11]; #1;
            if (m0_cmd_ready !== ref_m0_cmd_ready) $fatal(1,"m0_cmd_ready code=%0d",code);
            if (m0_wr_rdy !== ref_m0_wr_rdy) $fatal(1,"m0_wr_rdy code=%0d",code);
            if (m1_ready !== ref_m1_ready) $fatal(1,"m1_ready code=%0d",code);
            if (m2_ready !== ref_m2_ready) $fatal(1,"m2_ready code=%0d",code);
            if (ui_cmd_en !== ref_ui_cmd_en) $fatal(1,"ui_cmd_en code=%0d",code);
            if (ui_wr_data_en !== ref_ui_wr_data_en) $fatal(1,"ui_wr_data_en code=%0d",code);
            if (ui_wr_data_end !== ref_ui_wr_data_end) $fatal(1,"ui_wr_data_end code=%0d",code);
            if (dbg !== ref_dbg) $fatal(1,"dbg code=%0d",code);
            if(ui_cmd_en && {ui_cmd,ui_addr} !== {ref_ui_cmd,ref_ui_addr})
                $fatal(1,"Accepted command differs code=%0d",code);
            if(ui_wr_data_en && {ui_wr_data,ui_wr_data_mask} !== {ref_ui_wr_data,ref_ui_wr_data_mask})
                $fatal(1,"Accepted write differs code=%0d",code);
            if({dut.push,dut.serve_m2} !== {reference.push,reference.serve_m2})
                $fatal(1,"Read tag differs code=%0d",code);
            cases++;
        end
        $display("PASS DDR arbitration equivalence: %0d cases, grants, commands, masks and read tags",cases);
        $finish;
    end
endmodule
