`timescale 1ns/1ps
// Independent byte-lane oracle: both halves, all rotations, full/wrapped
// queues, simultaneous issue/return, empty-queue bypass and reset flush.
module neo_ddr_adapter_tb #(parameter TAG_LOG2=4);
    localparam DEPTH=1<<TAG_LOG2;
    reg clk=0, rst_n=0;
    always #5 clk=~clk;
    reg u_cmd_en=0;
    reg [2:0] u_cmd=0;
    reg [28:0] u_addr=0;
    wire u_cmd_ready;
    reg u_wr_data_en=0, u_wr_data_end=0;
    reg [127:0] u_wr_data=0;
    reg [15:0] u_wr_data_mask=0;
    wire u_wr_data_rdy;
    wire [127:0] u_rd_data;
    wire u_rd_data_valid,u_rd_data_end;
    wire ip_cmd_en;
    wire [2:0] ip_cmd;
    wire [28:0] ip_addr;
    reg ip_cmd_ready=0,ip_wr_data_rdy=0;
    wire ip_wr_data_en,ip_wr_data_end;
    wire [255:0] ip_wr_data;
    wire [31:0] ip_wr_data_mask;
    reg [255:0] ip_rd_data=0;
    reg ip_rd_data_valid=0,ip_rd_data_end=0;
    ddr_ui_adapt #(.TAG_LOG2(TAG_LOG2)) dut(.*);
    int outstanding[$];
    int sent=0, received=0, writes=0, simultaneous=0, empty_returns=0;
    int full_cycles=0, resets=0, discarded=0;
    reg [15:0] lanes_seen=0;
    int seed=138;
    task automatic cycle(input bit send, input bit write_cmd, input bit answer,
                         input bit stall, input bit reset);
        bit accepted, expect_valid;
        reg [127:0] expected;
        int address, tag, lane, ignored;
        @(negedge clk);
        rst_n=!reset;
        ip_cmd_ready=!stall;ip_wr_data_rdy=!stall;
        u_addr=29'($urandom); u_cmd=write_cmd ? 0:1;
        u_wr_data={$urandom,$urandom,$urandom,$urandom};u_wr_data_mask=16'($urandom);
        ip_rd_data={$urandom,$urandom,$urandom,$urandom,$urandom,$urandom,$urandom,$urandom};
        #1;
        if(!reset && u_cmd_ready !== (!stall && outstanding.size()<DEPTH))
            $fatal(1,"READY disagrees with independent queue occupancy before edge");
        u_cmd_en=send && u_cmd_ready && !reset;
        u_wr_data_en=u_cmd_en && write_cmd;u_wr_data_end=u_wr_data_en;
        ip_rd_data_valid=answer && !reset;ip_rd_data_end=ip_rd_data_valid;
        #1;
        accepted=u_cmd_en && u_cmd_ready;
        if(reset)begin outstanding.delete();resets++;end
        if(!reset && !u_cmd_ready && !stall)full_cycles++;
        if(accepted)begin
            if(!ip_cmd_en || ip_cmd!=u_cmd || ip_addr*4 != ((u_addr*2)&32'hffffffe0))
                $fatal(1,"Command address/handshake mismatch");
            if(write_cmd)begin
                writes++;
                if(!ip_wr_data_en || !ip_wr_data_end)$fatal(1,"Missing write");
                for(int b=0;b<32;b++)begin
                    lane=((b%16)+16-2*int'(u_addr[2:0]))%16;
                    if(ip_wr_data[b*8+:8]!==u_wr_data[lane*8+:8])$fatal(1,"Write rotation");
                    if(ip_wr_data_mask[b] !== ((b/16)!=int'(u_addr[3]) ? 1'b1:u_wr_data_mask[lane]))
                        $fatal(1,"Write mask");
                end
            end else begin outstanding.push_back(int'(u_addr));sent++;lanes_seen[u_addr[3:0]]=1;end
        end
        expect_valid=ip_rd_data_valid && outstanding.size()!=0;
        if(expect_valid)begin
            tag=outstanding.pop_front();received++;
            for(int b=0;b<16;b++)begin
                lane=((tag>>3)&1)*16+((b+2*(tag&7))%16);
                expected[b*8+:8]=ip_rd_data[lane*8+:8];
            end
            if(accepted && !write_cmd)simultaneous++;
        end else if(ip_rd_data_valid)begin discarded++;end
        @(posedge clk);#1;
        if(u_cmd_ready !== (!stall && outstanding.size()<DEPTH))
            $fatal(1,"Full/empty update disagrees with independent queue occupancy");
        if(u_rd_data_valid!==expect_valid || u_rd_data_end!==expect_valid)$fatal(1,"Reply validity/reset mismatch");
        if(expect_valid && u_rd_data!==expected)$fatal(1,"Wrong half/rotation or tag order");
    endtask
    initial begin
        void'($value$plusargs("seed=%d",seed));void'($urandom(seed));
        cycle(0,0,0,0,1);
        // No pending tag: unsolicited response is dropped, same-cycle read works.
        cycle(0,0,1,0,0);
        repeat(32)begin cycle(1,0,1,0,0);empty_returns++;end
        repeat(DEPTH)cycle(1,0,0,0,0);
        repeat(5)cycle(1,0,0,0,0);
        // A full queue rejects this command even when a response frees a slot.
        cycle(1,0,1,0,0);
        repeat(DEPTH-1)cycle(0,0,1,0,0);
        cycle(1,0,0,0,0);
        repeat(128)cycle(1,0,1,0,0);
        cycle(0,0,1,0,0);
        for(int i=0;i<12000;i++)begin
            cycle($urandom_range(0,3)!=0,$urandom_range(0,4)==0,
                  (outstanding.size()>0 && $urandom_range(0,3)!=0),
                  $urandom_range(0,4)==0,i%503==502);
        end
        while(outstanding.size()!=0)cycle(0,0,1,0,0);
        cycle(0,0,1,0,0);cycle(0,0,0,0,0);
        if(lanes_seen!=16'hffff || full_cycles==0 || simultaneous<100 || discarded<2 || writes<500)
            $fatal(1,"Missing coverage");
        $display("PASS reads=%0d responses=%0d writes=%0d simultaneous=%0d empty_bypass=%0d full=%0d resets=%0d discarded=%0d rotations=%h",sent,received,writes,simultaneous,empty_returns,full_cycles,resets,discarded,lanes_seen);
        $finish;
    end
    initial begin #1000000;$fatal(1,"Watchdog");end
endmodule
