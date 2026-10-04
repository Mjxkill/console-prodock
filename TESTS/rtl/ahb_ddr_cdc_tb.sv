`timescale 1ns/1ps
module ahb_ddr_cdc_tb;
    real hp=10.0, up=6.667, phase=0.0;
    bit hclk=0, uclk=0, hrunning=1, urunning=1, rst_n=0;
    initial begin void'($value$plusargs("hp=%f",hp)); forever begin #(hp); if(hrunning) hclk=~hclk; end end
    initial begin
        void'($value$plusargs("up=%f",up)); void'($value$plusargs("phase=%f",phase));
        #(phase); forever begin #(up); if(urunning) uclk=~uclk; end
    end
    reg [31:0] ha=0;
    reg [2:0] size=0;
    reg write=0;
    reg [1:0] trans=0;
    reg [63:0] wd=0;
    wire ready;
    wire [1:0] resp;
    wire [63:0] data;
    wire ce,we;
    wire [2:0] cmd;
    wire [28:0] addr;
    wire [127:0] uwd;
    wire [15:0] mask;
    reg cr=0,wr=0,rv=0;
    reg [127:0] rd=0;
    wire [15:0] dbg;
    ahb_ddr_cdc dut(.hclk(hclk),.ui_clk(uclk),.rst_n(rst_n),
        .haddr(ha),.hsize(size),.hwrite(write),.htrans(trans),.hwdata(wd),
        .hready(ready),.hresp(resp),.hrdata(data),.cmd_ready(cr),.wr_ready(wr),
        .cmd_en(ce),.wr_en(we),.cmd(cmd),.addr(addr),.wr_data(uwd),.wr_mask(mask),
        .rd_data(rd),.rd_valid(rv),.dbg(dbg));
    byte unsigned mem[0:65535], expected[0:65535];
    int ui_cycles=0, countdown=0, pending_addr=0, commands=0, reads=0,writes=0,checked=0;
    reg [31:0] rng=32'h0badf00d;
    always @(negedge uclk) begin
        rng=(rng>>1)^(rng[0] ? 32'h80200003:0);
        cr=rst_n && rng[0]; wr=rst_n && rng[3];
    end
    // A native 128-bit DDR model with unrelated command/data stalls and
    // variable read latency. Addresses are 16-bit words, not byte offsets.
    always @(posedge uclk) begin
        rv<=0;
        if(!rst_n) countdown=0;
        else begin
            ui_cycles++;
            if(countdown>0) begin
                countdown--;
                if(countdown==0) begin
                    for(int j=0;j<16;j++) rd[j*8+:8]<=mem[pending_addr+j];
                    rv<=1;
                end
            end
            if(ce) begin
                if(!cr || addr[2:0]!=0 || (we && !wr)) $fatal(1,"UI handshake/alignment");
                if(countdown!=0) $fatal(1,"More than one pending read");
                commands++;
                if(cmd==0) begin
                    if(!we) $fatal(1,"Missing write data");
                    for(int j=0;j<16;j++) if(!mask[j]) mem[(addr*2+j)&65535]=uwd[j*8+:8];
                    writes++;
                end else if(cmd==1) begin
                    if(we) $fatal(1,"Read with write data");
                    pending_addr=(addr*2)&65535; countdown=2+int'(rng[7:4]); reads++;
                end else $fatal(1,"Invalid command");
            end
        end
    end
    task automatic wait_ready;
        int n=0;
        while(!ready) begin @(negedge hclk); n++; if(n>300) $fatal(1,"AHB deadlock hs=%0d us=%0d",dut.hs,dut.us); end
    endtask
    task automatic check_data(input int a,input int sz);
        for(int j=0;j<(1<<sz);j++)
            if(data[((a+j)&7)*8+:8]!==expected[(a+j)&65535])
                $fatal(1,"READ @%h lane%0d expected=%h got=%h",a,j,expected[(a+j)&65535],data[((a+j)&7)*8+:8]);
        checked++;
    endtask
    task automatic transfer(input int a,input int sz,input bit w,input reg[63:0] value,input bit bad=0);
        int before_commands;
        @(negedge hclk); wait_ready();
        ha=a; size=3'(sz); write=w; trans=2; wd=~value; before_commands=commands;
        @(posedge hclk); // address phase
        @(negedge hclk); trans=0; ha=32'hfedcba98; wd=value; // DATA, deliberately different from address phase
        if(bad) begin
            if(resp!=1 || ready) $fatal(1,"First ERROR cycle");
            @(negedge hclk);
            if(resp!=1 || !ready) $fatal(1,"Second ERROR cycle");
            @(posedge hclk);
            if(commands!=before_commands) $fatal(1,"Invalid AHB reached DDR");
        end else begin
            wait_ready();
            if(resp!=0) $fatal(1,"Unexpected ERROR");
            if(w) for(int j=0;j<(1<<sz);j++) expected[(a+j)&65535]=value[((a+j)&7)*8+:8];
            else check_data(a,sz);
            @(posedge hclk);
            if(commands!=before_commands+1) $fatal(1,"Lost/duplicate native command");
        end
    endtask
    // No idle cycle between beats. The next address overlaps the current
    // data phase, and remains held across all inserted wait states.
    task automatic burst(input bit w,input int count);
        reg[63:0] value;
        @(negedge hclk); wait_ready(); ha=32'h4000; size=3; write=w; trans=2;
        @(posedge hclk);
        for(int i=0;i<count;i++) begin
            @(negedge hclk);
            value=64'h1928374655aa0000+64'(i);
            wd=value; ha=32'h4000+32'((i+1)*8); trans=(i==count-1)?0:3;
            wait_ready();
            if(resp!=0) $fatal(1,"Burst ERROR");
            if(w) for(int j=0;j<8;j++) expected[32'h4000+i*8+j]=value[j*8+:8];
            else check_data(32'h4000+i*8,3);
            @(posedge hclk);
        end
    endtask
    task automatic reset_both;
        rst_n=0; trans=0; wd=0; countdown=0; rv=0;
        repeat(8) @(negedge hclk);
        rst_n=1; wait_ready();
    endtask
    initial begin
        for(int i=0;i<65536;i++) begin mem[i]=8'(i^32'h5a); expected[i]=mem[i]; end
        reset_both();
        // Byte masks in every lane, then halfword, word and doubleword.
        for(int sz=0;sz<4;sz++) for(int a=0;a<128;a+=(1<<sz)) begin
            transfer(a,sz,1,64'h0123456789abcdef^64'(a*1234567));
            transfer(a,sz,0,0);
        end
        for(int a=0;a<128;a+=8) transfer(a,3,0,0);
        burst(1,256); burst(0,256);
        for(int i=0;i<600;i++) begin
            int a,sz; reg[63:0] v;
            sz=i%4; a=(int'($urandom_range(0,65535))>>sz)<<sz; v={$urandom,$urandom};
            transfer(a,sz,1,v); transfer(a,sz,0,0);
        end
        transfer(1,1,0,0,1); transfer(2,2,1,0,1);
        transfer(4,3,1,0,1); transfer(0,4,0,0,1); transfer(32'h40000000,2,0,0,1);
        // Clock pauses without reset must preserve the pending transaction.
        fork
            transfer(32'h6100,3,1,64'h9988776655443322);
            begin @(negedge uclk); urunning=0; repeat(30) @(negedge hclk); urunning=1; end
        join
        fork
            transfer(32'h6100,3,0,0);
            begin
                wait(dut.us==dut.U_READ); @(negedge hclk); hrunning=0;
                repeat(80) @(negedge uclk); hrunning=1;
            end
        join
        // A common DDR reset also cancels a read already accepted downstream.
        @(negedge hclk); wait_ready(); ha=32'h6200; size=3; write=0; trans=2;
        @(posedge hclk); @(negedge hclk); trans=0;
        wait(dut.us==dut.U_READ); reset_both();
        transfer(32'h6210,3,0,0);
        // Stop UI after queuing an AHB write, then reset while it is stopped.
        // On restart neither this command nor an old reply may be replayed.
        @(negedge uclk); urunning=0;
        @(negedge hclk); wait_ready(); ha=32'h6000; size=3; write=1; trans=2;
        @(posedge hclk); @(negedge hclk); trans=0; wd=64'hdeadbeef01234567;
        repeat(12) @(negedge hclk);
        rst_n=0; repeat(8) @(negedge hclk); rst_n=1;
        repeat(8) @(negedge hclk);
        if(ready) $fatal(1,"Ready before stopped peer reset");
        urunning=1; wait_ready();
        transfer(32'h6000,3,0,0);
        // Stop the AHB clock with a completion queued, reset, and restart.
        @(negedge hclk); wait_ready(); ha=32'h6008; size=3; write=0; trans=2;
        @(posedge hclk); @(negedge hclk); trans=0;
        repeat(3) @(negedge hclk); hrunning=0;
        repeat(80) @(negedge uclk);
        rst_n=0; countdown=0; rv=0; repeat(8) @(negedge uclk); rst_n=1;
        repeat(8) @(negedge uclk); hrunning=1; wait_ready();
        transfer(32'h6010,3,1,64'ha1b2c3d456789012); transfer(32'h6010,3,0,0);
        repeat(30) @(negedge hclk);
        if(dut.u_requests.wr_lost!=0 || dut.u_responses.wr_lost!=0) $fatal(1,"FIFO overflow");
        $display("PASS hp=%0f up=%0f phase=%0f commands=%0d writes=%0d reads=%0d checks=%0d",hp,up,phase,commands,writes,reads,checked);
        $finish;
    end
    initial begin #10000000; $fatal(1,"Global timeout"); end
endmodule
