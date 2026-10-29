`timescale 1ns/1ps
// Compare the *mapped* four-slot FIFOs to RTL and an independent data queue.
// No SDF: this cannot model silicon metastability or routing delays.
module fifo_check #(parameter RESPONSE=0, W=RESPONSE ? 64 : 100)(
    input hclk, uclk, rst, input [1:0] mode,
    output integer sent=0, received=0, full_cycles=0
);
    wire wc=RESPONSE ? uclk : hclk;
    wire rc=RESPONSE ? hclk : uclk;
    reg writer=0, reader=0;
    reg [W-1:0] data=0;
    reg [31:0] rngw=32'h12345678, rngr=32'hcafe1380;
    wire [2:0] hs=RESPONSE ? (reader ? 3'd2 : 3'd0) : (writer ? 3'd1 : 3'd0);
    wire [1:0] us=RESPONSE ? (writer ? 2'd3 : 2'd2) : (reader ? 2'd0 : 2'd1);
    wire [2:0] full, valid;
    wire [W-1:0] q[0:2];
    wire ref_ready;
    ddr_dcfifo reference(.wr_clk(wc),.wr_rst(rst),
        .wr_valid(writer && !full[0] && !rst),.wr_data(data),.wr_ready(ref_ready),
        .wr_full(full[0]),.wr_lost(),.wr_count(),
        .rd_clk(rc),.rd_rst(rst),.rd_valid(valid[0]),.rd_data(q[0]),
        .rd_ready(reader && valid[0] && !rst),.rd_count());
    defparam reference.WIDTH=W, reference.DEPTH_LOG2=2;

    generate if (!RESPONSE) begin
        baseline_request baseline(.clk_d(hclk),.gpu_clk(uclk),.h_reset(rst),.u_reset(rst),
            .hs(hs),.us(us),.write_q(data[99]),.address_q(data[98:72]),
            .mask_q(data[71:64]),.ddr_hwdata(data[63:0]),
            .full(full[1]),.request_valid(valid[1]),.request(q[1]));
        candidate_request candidate(.clk_d(hclk),.gpu_clk(uclk),.h_reset(rst),.u_reset(rst),
            .hs(hs),.us(us),.write_q(data[99]),.address_q(data[98:72]),
            .mask_q(data[71:64]),.ddr_hwdata(data[63:0]),
            .full(full[2]),.request_valid(valid[2]),.request(q[2]));
    end else begin
        baseline_response baseline(.clk_d(hclk),.gpu_clk(uclk),.h_reset(rst),.u_reset(rst),
            .hs(hs),.us(us),.result(data),.full(full[1]),.response_valid(valid[1]),.response(q[1]));
        candidate_response candidate(.clk_d(hclk),.gpu_clk(uclk),.h_reset(rst),.u_reset(rst),
            .hs(hs),.us(us),.result(data),.full(full[2]),.response_valid(valid[2]),.response(q[2]));
    end endgenerate

    reg [W-1:0] expected[0:65535];
    integer put=0, take=0;
    always @(posedge rst) begin put=0; take=0; end
    always @(posedge wc) if (!rst) begin
        if (full[0]) full_cycles++;
        if (writer && ref_ready) begin
            if (put>=65536) $fatal(1,"Test queue overflow");
            expected[put]=data; put++; sent++;
        end
    end
    always @(posedge rc) if (!rst && reader && valid[0]) begin
        if (take>=put || q[0]!==expected[take] || q[1]!==expected[take] || q[2]!==expected[take])
            $fatal(1,"Data/order mismatch response=%0d take=%0d put=%0d rtl=%h N32=%h N33=%h expected=%h",
                   RESPONSE,take,put,q[0],q[1],q[2],expected[take]);
        take++; received++;
    end
    always @(negedge wc) begin
        if (!rst && $isunknown(full))
            $fatal(1,"Unknown/high-impedance full flag response=%0d",RESPONSE);
        if (!rst && (full[0]!==full[1] || full[0]!==full[2]))
            $fatal(1,"Full timing mismatch response=%0d",RESPONSE);
        rngw=(rngw>>1)^(rngw[0] ? 32'h80200003 : 0);
        writer=!rst && (mode==0 || (mode==1 && rngw[0]));
        data={rngw ^ 32'h13800000,~rngw,rngw ^ 32'h55aa55aa,rngw};
    end
    always @(negedge rc) begin
        if (!rst && $isunknown(valid))
            $fatal(1,"Unknown/high-impedance valid flag response=%0d",RESPONSE);
        if (!rst && (valid[0]!==valid[1] || valid[0]!==valid[2]))
            $fatal(1,"Valid timing mismatch response=%0d",RESPONSE);
        if (!rst && valid[0] && (q[0]!==q[1] || q[0]!==q[2]))
            $fatal(1,"Head/latency mismatch response=%0d",RESPONSE);
        rngr=(rngr>>1)^(rngr[0] ? 32'h80200003 : 0);
        reader=!rst && (mode==2 || (mode==1 && rngr[2]));
    end
endmodule

module tb;
    real hp=10, up=6.667, phase=3.127;
    reg hclk=0,uclk=0,hrunning=1,urunning=1,rst=1;
    reg [1:0] mode=0;
    wire [31:0] sent0,sent1,read0,read1,full0,full1;
    GSR GSR(.GSRI(1'b1));
    initial begin
        if ($value$plusargs("hp=%f",hp)) begin end
        forever begin #(hp); if (hrunning) hclk=~hclk; end
    end
    initial begin
        if ($value$plusargs("up=%f",up)) begin end
        if ($value$plusargs("phase=%f",phase)) begin end
        #(phase); forever begin #(up); if (urunning) uclk=~uclk; end
    end
    fifo_check request(.hclk(hclk),.uclk(uclk),.rst(rst),.mode(mode),
        .sent(sent0),.received(read0),.full_cycles(full0));
    fifo_check #(.RESPONSE(1)) response(.hclk(hclk),.uclk(uclk),.rst(rst),.mode(mode),
        .sent(sent1),.received(read1),.full_cycles(full1));
    initial begin
        #301; rst=0;
        #1000; mode=1;
        #100000;
        @(negedge hclk); #0.1; hrunning=0;
        #1000; hrunning=1;
        #100000;
        @(negedge uclk); #0.1; urunning=0;
        #1000; urunning=1;
        #100000;
        // Both clocks observe the reset before either domain uses pointers.
        #0.231; rst=1; #400; rst=0;
        #100000; mode=2;
        #3000;
        if (request.take!=request.put || response.take!=response.put ||
            read0<1000 || read1<1000 || full0<10 || full1<10)
            $fatal(1,"Insufficient traffic/full/drain coverage");
        $display("PASS hp=%f up=%f phase=%f request_sent=%0d read=%0d full=%0d response_sent=%0d read=%0d full=%0d",
                 hp,up,phase,sent0,read0,full0,sent1,read1,full1);
        $finish;
    end
    initial begin #1000000; $fatal(1,"Watchdog"); end
endmodule
