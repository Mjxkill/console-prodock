`timescale 1ns/1ps
module ddr_gpu_arb_tb #(parameter NEO_SCAN_QUEUE=0);
    reg clk=0, rst=0, clock_running=1;
    always #5 if(clock_running)clk=~clk;
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
    wire ag_request,agr;
    wire [28:0] aga;
    generate if(NEO_SCAN_QUEUE)begin:g_local_queue
        neo_scan_queue q(.clk(clk),.resetn(rst),
            .in_valid(g_request),.in_addr(ga),.in_ready(gr),
            .out_valid(ag_request),.out_addr(aga),.out_ready(agr));
    end else begin:g_direct
        assign ag_request=g_request;assign aga=ga;assign gr=agr;
    end endgenerate
    localparam SCAN_SLOTS=2+2*NEO_SCAN_QUEUE;
    ddr_gpu_arb dut (
        .clk(clk),.rst_n(rst),.c_en(cfire),.c_cmd(write_mode ? 3'b000:3'b001),.c_addr(ca),.c_ready(cr),
        .c_wr_en(cfire && write_mode),.c_wr_end(cfire && write_mode),.c_wr_data(write_data),.c_wr_mask(32'h13579bdf),
        .c_wr_ready(cwr),.c_rd_data(cd),.c_rd_valid(cv),.c_rd_end(ce),
        .g_valid(ag_request),.g_addr(aga),.g_ready(agr),.g_data(gd),.g_data_valid(gv),
        .b_valid(b_request),.b_write(b_write),.b_addr(ba),.b_wr_data(~write_data),.b_wr_mask(32'hfedcba98),
        .b_ready(br),.b_rd_data(bd),.b_rd_valid(bv),
        .m_en(me),.m_cmd(cmd),.m_addr(ma),.m_ready(mr),.m_wr_en(mwe),.m_wr_end(mwend),.m_wr_data(mwd),.m_wr_mask(mwm),
        .m_wr_ready(mwr),.m_rd_data(rd),.m_rd_valid(rv),.m_rd_end(rv));
    integer owners[$];
    reg [28:0] addrs[$];
    reg [29:0] cpu_accepted[$];
    reg [28:0] scan_accepted[$];
    reg [29:0] expected_cpu;
    reg [28:0] expected_scan;
    integer reads=0, returns=0, writes=0, b_reads=0, b_writes=0, cpu_ops=0;
    integer owner;
    reg [28:0] expected_addr;
    always @(posedge clk) begin
        if(rst) begin
            // Scoreboard at the client acceptance boundary, independently of
            // the arbiter's internal state and its two scanout queue slots.
            if(cfire)cpu_accepted.push_back({write_mode,ca});
            if(g_request && gr)scan_accepted.push_back(ga);
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
                case(ma[17:16])
                    0:begin
                        if(cpu_accepted.size()==0)$fatal(1,"Unaccepted CPU command");
                        expected_cpu=cpu_accepted.pop_front();
                        if(ma!==expected_cpu[28:0] || (cmd==0)!==expected_cpu[29])$fatal(1,"CPU command order/payload");
                        owner=0;
                    end
                    1:begin
                        if(scan_accepted.size()==0)$fatal(1,"Unaccepted scanout command");
                        expected_scan=scan_accepted.pop_front();
                        if(ma!==expected_scan || cmd!=1)$fatal(1,"Scanout command order/payload");
                        owner=1;
                    end
                    2:begin
                        if(!b_request || !br || ma!==ba || (cmd==0)!==b_write)$fatal(1,"Blitter command acceptance");
                        owner=2;
                    end
                    default:$fatal(1,"Unknown native DDR address");
                endcase
                if(cmd==1) begin
                    owners.push_back(owner); addrs.push_back(ma); reads++;
                    if(b_request && br) b_reads++;
                    if(owners.size()>16) $fatal(1,"Tag FIFO overflow");
                end else begin
                    if(!mwe || !mwend || !mwr || owner==1)
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
        repeat(40) @(negedge clk);
        if(reads!=16 || cr || gr) $fatal(1,"Full tag queue did not backpressure");
        if(scan_accepted.size()!=SCAN_SLOTS)$fatal(1,"Scanout buffer capacity");
        // Drain under interleaved requests, independent stalls and writes.
        for(integer i=0;i<2000;i++) begin
            @(negedge clk);
            g_request=(i%4==0); c_request=(i%3!=0); write_mode=(i%5==0);
            b_request=(i%3!=1); b_write=(i%7<3);
            mr=(i%7!=0); mwr=(i%11!=0);
            rv=(i%3!=1) && owners.size()>0;
            if(rv) rd={227'b0,addrs[0]};
        end
        @(negedge clk); c_request=0; g_request=0; b_request=0; mr=1; mwr=1;
        while(owners.size()>0 || scan_accepted.size()>0 || cpu_accepted.size()>0) begin
            rv=owners.size()>0;
            if(rv)rd={227'b0,addrs[0]};
            @(negedge clk);
        end
        rv=0;
        if(reads!=returns || writes<10 || b_reads<10 || b_writes<10 || cpu_ops<20)
            $fatal(1,"Counts reads=%0d returns=%0d writes=%0d blitter=%0d/%0d CPU=%0d",reads,returns,writes,b_reads,b_writes,cpu_ops);
        // Reset with both request slots full and DDR held off. No accepted
        // pre-reset command may reach DDR after this shared controller reset.
        mr=0;g_request=1;
        repeat(8)@(negedge clk);
        if(scan_accepted.size()!=SCAN_SLOTS || gr)$fatal(1,"Reset setup did not fill queue");
        rst=0;g_request=0;scan_accepted.delete();
        repeat(4)@(negedge clk);rst=1;mr=1;
        repeat(24)begin @(negedge clk);if(me||gv||cv||bv)$fatal(1,"Reset replay");end
        // READY must withdraw on reset even when the DDR clock is stopped.
        // Keep reset asserted while the clock resumes so all shared queues
        // observe it, then check that new scanout requests still complete.
        if(!gr)$fatal(1,"Idle scanout is not ready");
        clock_running=0;#2;rst=0;#1;
        if(gr)$fatal(1,"Scanout READY survived reset with stopped clock");
        #30;
        if(gr)$fatal(1,"Scanout READY rose with stopped clock");
        clock_running=1;repeat(4)@(negedge clk);rst=1;
        // Pro Dock reference: READY follows the shared controller reset.
        // Acceptance still occurs only on a rising edge of the DDR UI clock.
        #1;
        if(NEO_SCAN_QUEUE)begin
            if(gr)$fatal(1,"Neo queue bypassed synchronous reset release");
            repeat(4)@(negedge clk);
        end else if(!gr)$fatal(1,"Scanout READY did not follow controller reset release");
        @(negedge clk);if(!gr)$fatal(1,"Scanout READY did not recover");
        g_request=1;@(negedge clk);g_request=0;
        while(owners.size()>0 || scan_accepted.size()>0)begin
            rv=owners.size()>0;
            if(rv)rd={227'b0,addrs[0]};
            @(negedge clk);
        end
        rv=0;
        if(reads!=returns)$fatal(1,"Post-reset response missing");
        $display("PASS: 3 DDR clients, full queue, stalls, simultaneous push/pop, reads=%0d writes=%0d blitter=%0d/%0d CPU=%0d",reads,writes,b_reads,b_writes,cpu_ops);
        $finish;
    end
    initial begin #100000; $fatal(1,"Timeout"); end
endmodule
