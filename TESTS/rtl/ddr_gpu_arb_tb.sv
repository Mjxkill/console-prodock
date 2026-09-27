`timescale 1ns/1ps
module ddr_gpu_arb_tb;
    reg clk=0, rst=0;
    always #5 clk=~clk;
    reg c_request=0, g_request=0, write_mode=0, b_request=0, b_write=0;
    reg [28:0] ba=29'h20000;
    wire br,bv;
    wire [255:0] bd;
    reg [28:0] ca=0, ga=29'h10000;
    wire cr,cwr,cv,ce,gr,gv,me,mwe,mwend;
    wire [2:0] cmd;
    wire [28:0] ma;
    wire [255:0] cd,gd,mwd;
    wire [31:0] mwm;
    reg mr=1,mwr=1,rv=0;
    reg [255:0] rd=0;
    wire cfire=c_request && cr && (!write_mode || cwr);
    wire [255:0] write_data={8{32'h89abcdef}};
    ddr_gpu_arb dut (
        .clk(clk),.rst_n(rst),.c_en(cfire),.c_cmd(write_mode ? 3'b000:3'b001),.c_addr(ca),.c_ready(cr),
        .c_wr_en(cfire && write_mode),.c_wr_end(cfire && write_mode),.c_wr_data(write_data),.c_wr_mask(32'h13579bdf),
        .c_wr_ready(cwr),.c_rd_data(cd),.c_rd_valid(cv),.c_rd_end(ce),
        .g_valid(g_request),.g_addr(ga),.g_ready(gr),.g_data(gd),.g_data_valid(gv),
        .b_valid(b_request),.b_write(b_write),.b_addr(ba),.b_wr_data(~write_data),.b_wr_mask(32'hfedcba98),
        .b_ready(br),.b_rd_data(bd),.b_rd_valid(bv),
        .m_en(me),.m_cmd(cmd),.m_addr(ma),.m_ready(mr),.m_wr_en(mwe),.m_wr_end(mwend),.m_wr_data(mwd),.m_wr_mask(mwm),
        .m_wr_ready(mwr),.m_rd_data(rd),.m_rd_valid(rv),.m_rd_end(rv));
    integer owners[$];
    reg [28:0] addrs[$];
    integer reads=0, returns=0, writes=0, b_reads=0, b_writes=0, cpu_ops=0;
    integer owner;
    reg [28:0] expected_addr;
    always @(posedge clk) begin
        if(rst) begin
            if(rv) begin
                if(owners.size()==0) $fatal(1,"Unexpected response");
                owner=owners.pop_front(); expected_addr=addrs.pop_front();
                if(owner==2) begin
                    if(!bv || gv || cv || bd!=={227'b0,expected_addr}) $fatal(1,"Blitter tag");
                end else if(owner==1) begin
                    if(!gv || cv || bv || gd!=={227'b0,expected_addr}) $fatal(1,"GPU tag");
                end else if(!cv || gv || bv || !ce || cd!=={227'b0,expected_addr}) $fatal(1,"CPU tag");
                returns++;
            end
            if(me && mr) begin
                if(cmd==1) begin
                    owners.push_back(g_request ? 1 : (b_request && br ? 2 : 0)); addrs.push_back(ma); reads++;
                    if(b_request && br) b_reads++;
                    if(owners.size()>16) $fatal(1,"Tag FIFO overflow");
                end else begin
                    if(!mwe || !mwend || !mwr || g_request)
                        $fatal(1,"Write data/mask corrupted");
                    if(b_request && br) begin
                        if(mwd!==~write_data || mwm!==32'hfedcba98) $fatal(1,"Blitter write corruption");
                        b_writes++;
                    end else if(mwd!==write_data || mwm!==32'h13579bdf) $fatal(1,"CPU write corruption");
                    writes++;
                end
            end
            if(cfire) begin ca<=ca+8; cpu_ops++; end
            if(b_request && br) ba<=ba+8;
            if(g_request && gr) ga<=ga+8;
        end
    end
    initial begin
        repeat(3) @(negedge clk); rst=1; c_request=1;
        repeat(8) @(negedge clk); g_request=1;
        repeat(12) @(negedge clk);
        if(reads!=16 || cr || gr) $fatal(1,"Full tag queue did not backpressure");
        // Drain under interleaved requests, independent stalls and writes.
        for(integer i=0;i<250;i++) begin
            @(negedge clk);
            g_request=(i%4==0); c_request=(i%3!=0); write_mode=(i%5==0);
            b_request=(i%3!=1); b_write=(i%7<3);
            mr=(i%7!=0); mwr=(i%11!=0);
            rv=(i%3!=1) && owners.size()>0;
            if(rv) rd={227'b0,addrs[0]};
        end
        @(negedge clk); c_request=0; g_request=0; b_request=0; mr=1; mwr=1;
        while(owners.size()>0) begin
            rv=1; rd={227'b0,addrs[0]}; @(negedge clk);
        end
        rv=0;
        if(reads!=returns || writes<10 || b_reads<10 || b_writes<10 || cpu_ops<20)
            $fatal(1,"Counts reads=%0d returns=%0d writes=%0d",reads,returns,writes);
        $display("PASS: 3 DDR clients, full queue, stalls, simultaneous push/pop, reads=%0d writes=%0d blitter=%0d/%0d CPU=%0d",reads,writes,b_reads,b_writes,cpu_ops);
        $finish;
    end
    initial begin #100000; $fatal(1,"Timeout"); end
endmodule
