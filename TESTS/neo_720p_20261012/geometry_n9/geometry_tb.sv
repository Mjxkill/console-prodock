`timescale 1ns/1ps
module gpu_accel_tb #(parameter DEPTH_SLOT=1, READ_MIN=3);
    reg hc=0, mc=0, rst=0, memory_resetn=0, checking=0;
    always #6.25 hc=~hc;
    always #6.666 mc=~mc;
    reg sel=0, wr=0;
    reg [31:0] address=0, data=0;
    reg [1:0] trans=0;
    wire hready;
    wire [31:0] result;
    wire valid, write;
    wire [28:0] addr;
    wire [255:0] wd;
    wire [31:0] mask;
    reg ready=0, rv=0;
    reg [255:0] rd=0;
    wire bv,bw,br,brv;
    wire [28:0] ba;
    wire [255:0] bwd,brd;
    wire [31:0] bm;
    gpu_accel #(.FONT_FILE("font8x16.hex")) dut (
        .hclk(hc),.hresetn(rst),.hsel(sel),.hwrite(wr),.haddr(address),.hwdata(data),.htrans(trans),
        .hrdata(result),.hready(hready),.mem_clk(mc),.valid(bv),.write(bw),.addr(ba),
        .wr_data(bwd),.wr_mask(bm),.ready(br),.rd_data(brd),.rd_valid(brv));
    reg cpu_pending=0, scan_pending=0;
    wire cr, cv, gr, gv;
    wire [255:0] cd,gd;
    wire [2:0] cmd;
    wire unused_we,unused_end;
    wire c_request=rst && !cpu_pending;
    wire g_request=rst && !scan_pending && cycle%64<25;
    localparam [28:0] CPU_ADDR=(32'h1780000>>2), SCAN_ADDR=(32'h17e0000>>2);
    ddr_gpu_arb arb (
        .clk(mc),.rst_n(memory_resetn),.c_en(c_request && cr),.c_cmd(3'b001),.c_addr(CPU_ADDR),.c_ready(cr),
        .c_wr_en(1'b0),.c_wr_end(1'b0),.c_wr_data(256'd0),.c_wr_mask(32'hffffffff),
        .c_wr_ready(),.c_rd_data(cd),.c_rd_valid(cv),.c_rd_end(),
        .g_valid(g_request),.g_addr(SCAN_ADDR),.g_ready(gr),.g_data(gd),.g_data_valid(gv),
        .b_valid(bv),.b_write(bw),.b_addr(ba),.b_wr_data(bwd),.b_wr_mask(bm),.b_ready(br),.b_rd_data(brd),.b_rd_valid(brv),
        .m_en(valid),.m_cmd(cmd),.m_addr(addr),.m_ready(ready),.m_wr_en(unused_we),.m_wr_end(unused_end),
        .m_wr_data(wd),.m_wr_mask(mask),.m_wr_ready(ready),.m_rd_data(rd),.m_rd_valid(rv),.m_rd_end(rv));
    assign write=cmd==0;
    integer cpu_reads=0,scan_reads=0;
    always @(posedge mc) if(memory_resetn) begin
        if(c_request && cr) cpu_pending<=1;
        if(g_request && gr) scan_pending<=1;
        if(cv) begin
            if(!cpu_pending) $fatal(1,"CPU unsolicited response");
            for(integer i=0;i<32;i++) if(cd[i*8+:8]!==memory[index(int'(CPU_ADDR)*4+i)]) $fatal(1,"CPU read data");
            cpu_pending<=0; cpu_reads++;
        end
        if(gv) begin
            if(!scan_pending) $fatal(1,"Scan unsolicited response");
            for(integer i=0;i<32;i++) if(gd[i*8+:8]!==memory[index(int'(SCAN_ADDR)*4+i)]) $fatal(1,"Scan read data");
            scan_pending<=0; scan_reads++;
        end
    end

    localparam BYTES=3*1048576;
    reg [7:0] memory [0:BYTES-1];
    reg [7:0] expected [0:BYTES-1];
    reg [31:0] commands [0:65535];
    integer ncmd, bad_expected, raster_bad_expected, v1_bad_expected, v1_pass_expected, rgbinit, cycle=0;
    integer due[$], addresses[$], last_due=0, next_due, response_address;
    integer writes=0, reads=0, full_writes=0, stalls=0;
    integer at;
    function automatic integer index(input integer byte_addr);
        integer slot, offset;
        slot=(byte_addr-'h800000)>>20; offset=byte_addr & 'hfffff;
        if(slot==0) return offset;
        if(slot==DEPTH_SLOT) return 1048576+offset;
        if(slot==15) return 2097152+offset;
        $fatal(1,"Out-of-surface DDR access @%h",byte_addr);
        return 0;
    endfunction
    always @(negedge mc) begin
        cycle++;
        ready=memory_resetn && cycle%5!=0 && cycle%13!=0;
        rv=0;
        if(due.size()>0 && due[0]==cycle) begin
            next_due=due.pop_front(); response_address=addresses.pop_front();
            rv=1;
            for(integer i=0;i<32;i++) rd[i*8+:8]=memory[index(response_address+i)];
        end
    end
    always @(posedge mc) if(valid && ready) begin
        if(addr[2:0]!=0) $fatal(1,"Unaligned DDR command");
        at=int'(addr)*4;
        if(write) begin
            for(integer i=0;i<32;i++) if(!mask[i]) memory[index(at+i)]=wd[i*8+:8];
            writes++;
            if(mask==0) full_writes++;
        end else begin
            next_due=cycle+READ_MIN+cycle%8;
            if(next_due<=last_due) next_due=last_due+1;
            due.push_back(next_due); addresses.push_back(at); last_due=next_due; reads++;
        end
    end
    task automatic write_reg(input [31:0] a, input [31:0] d);
        @(negedge hc); sel=1; wr=1; trans=2; address=a;
        do @(posedge hc); while(!hready);
        @(negedge hc); sel=0; trans=0; data=d;
        do begin @(posedge hc); if(!hready) stalls++; end while(!hready);
        @(negedge hc); wr=0;
    endtask
    task automatic read_reg(input [31:0] a, output [31:0] d);
        @(negedge hc); sel=1; wr=0; trans=2; address=a;
        do @(posedge hc); while(!hready);
        @(negedge hc); sel=0; trans=0;
        do @(posedge hc); while(!hready);
        d=result;
    endtask
    reg [31:0] shader_expected [0:65535];integer shader_index=0;
    initial $readmemh("shader.hex",shader_expected,0,3088-1);
    always @(posedge mc)if(rst && checking && dut.u_v1.shader_start)begin
        for(integer w=0;w<8;w++)begin
            if(dut.u_v1.shader_command[w*32+:32]!==shader_expected[shader_index])
                $fatal(1,"Geometry command %0d word %0d = %h expected %h state=%0d",shader_index/8,w,dut.u_v1.shader_command[w*32+:32],shader_expected[shader_index],dut.u_v1.state);
            shader_index++;
        end
    end
    integer shared_edge_checks=0;
    always @(posedge mc)if(rst && checking && dut.u_v1.state[dut.u_v1.CL_STORE] && dut.u_v1.vb==32'h1770000 && dut.u_v1.plane==0 && dut.u_v1.iy==0)begin
        if(dut.u_v1.ix!=2 || dut.u_v1.iz!=16384)
            $fatal(1,"Shared edge depends on winding: x=%0d z=%0d",dut.u_v1.ix,dut.u_v1.iz);
        shared_edge_checks++;
    end
    reg [31:0] value;
    integer errors=0;
    initial begin
        if(!$value$plusargs("ncmd=%d",ncmd)) $fatal(1,"Need ncmd");
        if(!$value$plusargs("bad=%d",bad_expected)) bad_expected=0;
        if(!$value$plusargs("raster_bad=%d",raster_bad_expected)) raster_bad_expected=-1;
        if(!$value$plusargs("rgbinit=%d",rgbinit)) rgbinit=0;
        if(!$value$plusargs("v1_bad=%d",v1_bad_expected)) v1_bad_expected=-1;
        if(!$value$plusargs("v1_pass=%d",v1_pass_expected)) v1_pass_expected=-1;
        $readmemh("commands.hex",commands,0,ncmd*8-1);
        $readmemh("expected.hex",expected);
        for(integer i=0;i<BYTES;i++) memory[i]=8'((i*29)+(i>>11));
        if(rgbinit==1)for(integer y=0;y<480;y++)for(integer x=0;x<800;x++)begin
            automatic integer color=((x/4+y/4)%5==0) ? 0:
                (((x*3+y)&31)<<11)|(((x+y*2)&63)<<5)|((x^y)&31);
            memory[2097152+2*(y*800+x)]=8'(color);
            memory[2097152+2*(y*800+x)+1]=8'(color>>8);
        end
        if(rgbinit==2)for(integer y=0;y<64;y++)for(integer x=0;x<64;x++)begin
            automatic integer color=(x<2 || x>=62 || y<2 || y>=62) ? 65535:((x/8+y/8)%5==0) ? 0:
                (((x*31)/63)<<11)|(y<<5)|(((x^y)&63)/2);
            memory[2097152+2*((y+19)*800+x+17)]=8'(color);
            memory[2097152+2*((y+19)*800+x+17)+1]=8'(color>>8);
        end
        if(rgbinit==3)$readmemh("initial.hex",memory);
        #200; rst=1; memory_resetn=1;
        for(integer trial=0;trial<7;trial++)begin
            automatic integer phase;
            case(trial)
              0:phase=7;
              1:phase=8;
              2:phase=21;
              3:phase=27;
              4:phase=37;
              5:phase=42;
              6:phase=46;

            endcase
            for(integer i=0;i<11*8;i++)write_reg('h10,commands[i]);
            wait(dut.u_v1.state[phase]);
            @(negedge hc);rst=0;
            repeat(32)@(negedge hc);
            rst=1;
            repeat(1000)@(negedge mc);
            if(dut.done_count!=0 || dut.u_blitter.busy || dut.u_v1.busy || bv || dut.queue_valid)
                $fatal(1,"Old work replayed after reset phase %0d",phase);
            // A fresh DRAW cannot reuse the pre-reset matrix/camera/material.
            for(integer i=10*8;i<11*8;i++)write_reg('h10,commands[i]);
            wait(dut.done_count==1);repeat(100)@(negedge mc);
            if(dut.u_v1.geom_errors!=1 || dut.u_v1.vertices!=0)
                $fatal(1,"Pre-reset descriptors survived phase %0d",phase);
            @(negedge hc);rst=0;repeat(32)@(negedge hc);rst=1;
            repeat(1000)@(negedge mc);
            $display("RESET PASS phase=%0d",phase);
        end
        $readmemh("initial.hex",memory);
        checking=1;

        read_reg(0,value); if(value!='h424c5432) $fatal(1,"BLT2 ID");
        // Rewrite glyph 0x80 to exercise the programmable font's second clock.
        write_reg('h14,'h800);
        for(integer row=0;row<16;row++) write_reg('h18,(row%2) ? 'ha5:'h5a);
        for(integer i=0;i<ncmd*8;i++) write_reg('h10,commands[i]);
        do begin
            repeat(100) @(posedge hc);
            read_reg(8,value);
        end while(value!=ncmd);
        if(shared_edge_checks!=2)$fatal(1,"Shared edge coverage %0d",shared_edge_checks);
        if(shader_index!=3088)$fatal(1,"Missing geometry commands");
        read_reg('h4c,value);if(value!=21)$fatal(1,"Geometry errors %0d",value);
        read_reg('h50,value);if(value!=393)$fatal(1,"Vertex count %0d",value);
        read_reg('h54,value);if(value!=56)$fatal(1,"Triangle count %0d",value);
        read_reg('h58,value);if(value!=12)$fatal(1,"Cull count %0d",value);
        read_reg('h5c,value);if(value!=99)$fatal(1,"Clip count %0d",value);
        read_reg('h60,value);if(value!=2)$fatal(1,"Sliver count %0d",value);
        read_reg('hc,value);
        if(value != (bad_expected<<16)) $fatal(1,"Command error counters %h",value);
        read_reg('h1c,value); if(value!=0) $fatal(1,"CDC queue overflow");
        if(raster_bad_expected>=0)begin
            read_reg('h24,value);
            if(value!=raster_bad_expected) $fatal(1,"Raster rejected %0d expected %0d",value,raster_bad_expected);
        end
        if(v1_bad_expected>=0)begin
            read_reg('h34,value);if(value!=v1_bad_expected)$fatal(1,"V1 rejected %0d expected %0d",value,v1_bad_expected);
            read_reg('h3c,value);if(value!=v1_pass_expected)$fatal(1,"V1 passed %0d expected %0d",value,v1_pass_expected);
            read_reg('h40,value);$display("V1 cache hits=%0d",value);if(!value)$fatal(1,"No texture reuse");
            read_reg('h44,value);$display("V1 cache misses=%0d",value);if(!value)$fatal(1,"No texture refill");
        end
        for(integer i=0;i<BYTES;i++) if(memory[i]!==expected[i]) begin
            if(errors<8) $display("Mismatch @%h: got=%h expected=%h",i,memory[i],expected[i]);
            errors++;
        end
        if(errors) $fatal(1,"%0d wrong bytes",errors);
        if(stalls==0 || full_writes<100 || cpu_reads<100 || scan_reads<100) $fatal(1,"Missing queue/burst/read coverage");
        $display("PASS: %0d commands, entire pages+guards exact, DDR writes=%0d full=%0d reads=%0d AHB stalls=%0d CPU=%0d scan=%0d",ncmd,writes,full_writes,reads,stalls,cpu_reads,scan_reads);
        $finish;
    end
    initial begin
        #1000000000;
        $display("done=%0d st=%0d op=%0d dma=%0d xy=%0d,%0d end=%0d,%0d err=%0d dxy=%0d,%0d", dut.done_count,dut.u_blitter.st,dut.u_blitter.op,dut.u_dma.state,dut.u_blitter.lx,dut.u_blitter.ly,dut.u_blitter.x1,dut.u_blitter.y1,dut.u_blitter.lerr,dut.u_blitter.ldx,dut.u_blitter.ldy);
        $fatal(1,"Timeout");
    end
endmodule
