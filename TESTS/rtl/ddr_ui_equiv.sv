`timescale 1ns/1ps
// Compare actual width adapters under full queues, simultaneous issue/return,
// address rotations, both half-bursts, arbitrary data and backpressure.
module ddr_ui_equiv;
    reg  clk=0;
    reg  rst_n=0;
    reg  u_cmd_en=0;
    reg [2:0] u_cmd=0;
    reg [28:0] u_addr=0;
    wire  u_cmd_ready;
    wire  ref_u_cmd_ready;
    reg  u_wr_data_en=0;
    reg  u_wr_data_end=0;
    reg [127:0] u_wr_data=0;
    reg [15:0] u_wr_data_mask=0;
    wire  u_wr_data_rdy;
    wire  ref_u_wr_data_rdy;
    wire [127:0] u_rd_data;
    wire [127:0] ref_u_rd_data;
    wire  u_rd_data_valid;
    wire  ref_u_rd_data_valid;
    wire  u_rd_data_end;
    wire  ref_u_rd_data_end;
    wire  ip_cmd_en;
    wire  ref_ip_cmd_en;
    wire [2:0] ip_cmd;
    wire [2:0] ref_ip_cmd;
    wire [28:0] ip_addr;
    wire [28:0] ref_ip_addr;
    reg  ip_cmd_ready=0;
    wire  ip_wr_data_en;
    wire  ref_ip_wr_data_en;
    wire  ip_wr_data_end;
    wire  ref_ip_wr_data_end;
    wire [255:0] ip_wr_data;
    wire [255:0] ref_ip_wr_data;
    wire [31:0] ip_wr_data_mask;
    wire [31:0] ref_ip_wr_data_mask;
    reg  ip_wr_data_rdy=0;
    reg [255:0] ip_rd_data=0;
    reg  ip_rd_data_valid=0;
    reg  ip_rd_data_end=0;
    ddr_ui_adapt dut (
        .clk(clk),
        .rst_n(rst_n),
        .u_cmd_en(u_cmd_en),
        .u_cmd(u_cmd),
        .u_addr(u_addr),
        .u_cmd_ready(u_cmd_ready),
        .u_wr_data_en(u_wr_data_en),
        .u_wr_data_end(u_wr_data_end),
        .u_wr_data(u_wr_data),
        .u_wr_data_mask(u_wr_data_mask),
        .u_wr_data_rdy(u_wr_data_rdy),
        .u_rd_data(u_rd_data),
        .u_rd_data_valid(u_rd_data_valid),
        .u_rd_data_end(u_rd_data_end),
        .ip_cmd_en(ip_cmd_en),
        .ip_cmd(ip_cmd),
        .ip_addr(ip_addr),
        .ip_cmd_ready(ip_cmd_ready),
        .ip_wr_data_en(ip_wr_data_en),
        .ip_wr_data_end(ip_wr_data_end),
        .ip_wr_data(ip_wr_data),
        .ip_wr_data_mask(ip_wr_data_mask),
        .ip_wr_data_rdy(ip_wr_data_rdy),
        .ip_rd_data(ip_rd_data),
        .ip_rd_data_valid(ip_rd_data_valid),
        .ip_rd_data_end(ip_rd_data_end)
    );
    ddr_ui_reference reference (
        .clk(clk),
        .rst_n(rst_n),
        .u_cmd_en(u_cmd_en),
        .u_cmd(u_cmd),
        .u_addr(u_addr),
        .u_cmd_ready(ref_u_cmd_ready),
        .u_wr_data_en(u_wr_data_en),
        .u_wr_data_end(u_wr_data_end),
        .u_wr_data(u_wr_data),
        .u_wr_data_mask(u_wr_data_mask),
        .u_wr_data_rdy(ref_u_wr_data_rdy),
        .u_rd_data(ref_u_rd_data),
        .u_rd_data_valid(ref_u_rd_data_valid),
        .u_rd_data_end(ref_u_rd_data_end),
        .ip_cmd_en(ref_ip_cmd_en),
        .ip_cmd(ref_ip_cmd),
        .ip_addr(ref_ip_addr),
        .ip_cmd_ready(ip_cmd_ready),
        .ip_wr_data_en(ref_ip_wr_data_en),
        .ip_wr_data_end(ref_ip_wr_data_end),
        .ip_wr_data(ref_ip_wr_data),
        .ip_wr_data_mask(ref_ip_wr_data_mask),
        .ip_wr_data_rdy(ip_wr_data_rdy),
        .ip_rd_data(ip_rd_data),
        .ip_rd_data_valid(ip_rd_data_valid),
        .ip_rd_data_end(ip_rd_data_end)
    );
    always #5 clk=~clk;
    reg [31:0] rng=32'h9123abcd;
    integer pending=0,reads=0,writes=0,full_cycles=0,both=0;
    always @(posedge clk) if(rst_n) begin
        if(u_cmd_en && u_cmd_ready && u_cmd==3'b001)begin pending++;reads++;end
        if(ip_rd_data_valid)pending--;
        if(dut.tq_full)full_cycles++;
        if(ip_wr_data_en)writes++;
        if(dut.push && dut.pop)both++;
    end
    initial begin
        repeat(5) @(negedge clk);rst_n=1;
        for(integer cycle=0;cycle<20000;cycle++)begin
            @(negedge clk);
            rng=(rng<<1)^(rng[31]?32'h04c11db7:0);
            ip_cmd_ready=cycle<40 || rng[0];ip_wr_data_rdy=rng[1];
            ip_rd_data_valid=cycle>=40 && pending>0 && rng[2];ip_rd_data_end=ip_rd_data_valid;
            for(integer word_index=0;word_index<8;word_index++)ip_rd_data[word_index*32+:32]=rng^(cycle+word_index*73);
            u_addr={rng[28:4],4'(cycle)};u_wr_data={rng,~rng,rng^32'(cycle),32'(cycle)};u_wr_data_mask=rng[15:0];
            u_cmd=cycle<40 || rng[3] ? 3'b001:3'b000;
            #1;
            u_cmd_en=u_cmd_ready && (u_cmd==1 || ip_wr_data_rdy);
            u_wr_data_en=u_cmd_en && u_cmd==0;u_wr_data_end=u_wr_data_en;
            #1;
            if(u_cmd_ready !== ref_u_cmd_ready)$fatal(1,"DDR adapter equivalence: u_cmd_ready cycle=%0d",cycle);
            if(u_wr_data_rdy !== ref_u_wr_data_rdy)$fatal(1,"DDR adapter equivalence: u_wr_data_rdy cycle=%0d",cycle);
            if(u_rd_data_valid && u_rd_data !== ref_u_rd_data)$fatal(1,"DDR adapter equivalence: u_rd_data cycle=%0d",cycle);
            if(u_rd_data_valid !== ref_u_rd_data_valid)$fatal(1,"DDR adapter equivalence: u_rd_data_valid cycle=%0d",cycle);
            if(u_rd_data_end !== ref_u_rd_data_end)$fatal(1,"DDR adapter equivalence: u_rd_data_end cycle=%0d",cycle);
            if(ip_cmd_en !== ref_ip_cmd_en)$fatal(1,"DDR adapter equivalence: ip_cmd_en cycle=%0d",cycle);
            if(ip_cmd !== ref_ip_cmd)$fatal(1,"DDR adapter equivalence: ip_cmd cycle=%0d",cycle);
            if(ip_addr !== ref_ip_addr)$fatal(1,"DDR adapter equivalence: ip_addr cycle=%0d",cycle);
            if(ip_wr_data_en !== ref_ip_wr_data_en)$fatal(1,"DDR adapter equivalence: ip_wr_data_en cycle=%0d",cycle);
            if(ip_wr_data_end !== ref_ip_wr_data_end)$fatal(1,"DDR adapter equivalence: ip_wr_data_end cycle=%0d",cycle);
            if(ip_wr_data !== ref_ip_wr_data)$fatal(1,"DDR adapter equivalence: ip_wr_data cycle=%0d",cycle);
            if(ip_wr_data_mask !== ref_ip_wr_data_mask)$fatal(1,"DDR adapter equivalence: ip_wr_data_mask cycle=%0d",cycle);
        end
        if(full_cycles==0 || both<100 || reads<100 || writes<100)$fatal(1,"Missing coverage");
        $display("PASS DDR adapter equivalence: 20000 cycles, %0d reads, %0d writes, %0d full cycles, %0d simultaneous push/pop",reads,writes,full_cycles,both);
        $finish;
    end
endmodule
