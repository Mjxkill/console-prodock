`timescale 1ns/1ps
// Real frozen R19 gpu_accel + ddr_gpu_arb. Only the external DDR endpoint
// is modeled here. No force/deposit, no replacement pending/accepted logic.
module tb;
    reg hc=0, mc=0, rst=0, hc_run=1, mc_run=1;
    realtime mem_half=6.666;
    always #6.25 if(hc_run) hc=~hc;
    always #(mem_half) if(mc_run) mc=~mc;
    reg sel=0, wr=0;
    reg [31:0] address=0, data=0;
    reg [1:0] trans=0;
    wire hready;
    wire [31:0] result;
    wire bv,bw,br,brv;
    wire [28:0] ba;
    wire [255:0] bwd,brd;
    wire [31:0] bm;
    gpu_accel #(.FONT_FILE("font8x16.hex")) dut (
        .hclk(hc),.hresetn(rst),.hsel(sel),.hwrite(wr),.haddr(address),.hwdata(data),.htrans(trans),
        .hrdata(result),.hready(hready),.mem_clk(mc),.valid(bv),.write(bw),.addr(ba),
        .wr_data(bwd),.wr_mask(bm),.ready(br),.rd_data(brd),.rd_valid(brv),
        .debug_state(),.debug_accept(),.observe_packet_words());
    wire me,mwe,mend;
    wire [2:0] cmd;
    wire [28:0] ma;
    wire [255:0] md;
    wire [31:0] mm;
    reg mready=0, mwready=0;
    integer tick=0, mode=0;
    reg model_rv=0;reg [255:0] model_rd=0;
    integer read_due=-1,read_address=0,reads=0;
    // mode1 independently blocks command acceptance, mode2 write-data
    // acceptance, mode3 both. Mode0 has bounded, distinct periodic stalls.
    always @(negedge mc)begin
        tick++;
        model_rv=0;
        if(read_due==tick)begin
            model_rv=1;read_due=-1;
            for(integer k=0;k<32;k++)model_rd[k*8+:8]=memory[read_address+k];
        end
        mready=rst && mode!=1 && mode!=3 && tick%7!=0;
        mwready=rst && mode!=2 && mode!=3 && tick%11>2;
    end
    ddr_gpu_arb arb (
        .clk(mc),.rst_n(rst),.c_en(1'b0),.c_cmd(3'b001),.c_addr(29'd0),.c_ready(),
        .c_wr_en(1'b0),.c_wr_end(1'b0),.c_wr_data(256'd0),.c_wr_mask(32'hffffffff),
        .c_wr_ready(),.c_rd_data(),.c_rd_valid(),.c_rd_end(),
        .g_valid(1'b0),.g_addr(29'd0),.g_ready(),.g_data(),.g_data_valid(),
        .b_valid(bv),.b_write(bw),.b_addr(ba),.b_wr_data(bwd),.b_wr_mask(bm),
        .b_ready(br),.b_rd_data(brd),.b_rd_valid(brv),
        .m_en(me),.m_cmd(cmd),.m_addr(ma),.m_ready(mready),.m_wr_en(mwe),.m_wr_end(mend),
        .m_wr_data(md),.m_wr_mask(mm),.m_wr_ready(mwready),.m_rd_data(model_rd),
        .m_rd_valid(model_rv),.m_rd_end(model_rv));
    localparam BASE=32'h00800000, COLOR=32'h00800020, DEPTH=32'h00810000, BYTES=32'h12000;
    reg [7:0] memory[0:BYTES-1],expected[0:BYTES-1];
    integer writes=0, native_grants=0, returned_acks=0, slot_loads=0;
    integer held_checks=0, command_only_blocked=0, data_only_blocked=0;
    integer aborted_slots=0,canceled_acks=0;
    reg previous_rst=0,old_pixel_ack,old_native_valid;
    integer negative=0;
    integer address_byte, completed_tests=0;
    reg old_pending,old_grant,old_active;
    reg [317:0] old_payload;
    always @(posedge mc) begin
        old_pending=dut.v1_pending;
        old_pixel_ack=dut.v1_accepted && dut.v1_select && !dut.u_v1.fetch_valid;
        old_native_valid=dut.u_v1.u_pixels.native_valid;
        if(!rst && previous_rst)begin
            if(dut.v1_pending)aborted_slots++;
            if(dut.v1_accepted)canceled_acks++;
        end
        previous_rst=rst;
        old_grant=dut.v1_pending && br;
        old_active=rst && dut.mrst[1];
        old_payload={dut.v1_tx_write,dut.v1_tx_addr,dut.v1_tx_data,dut.v1_tx_mask};
        if(negative==2 && old_pending && mode!=0)old_payload[0]=!old_payload[0];
        if(rst)begin
            if(me)begin
                if(!mready || (cmd!==0 && cmd!==1) || (cmd==0 && (!mwe || !mend || !mwready)) || (cmd==1 && mwe))
                    $fatal(1,"Unexpected/ungated DDR command: cmd=%h ready=%b/%b",cmd,mready,mwready);
                if(ma[2:0]!==0)$fatal(1,"DDR address alignment");
                address_byte=int'(ma)*4-BASE;
                if(address_byte<0 || address_byte+32>BYTES)$fatal(1,"Out of guarded region: %h",ma);
                if(cmd==0)begin
                    for(integer b=0;b<32;b++)if(!mm[b])memory[address_byte+b]=md[b*8+:8];
                    writes++;
                end else begin
                    if(read_due!=-1)$fatal(1,"Read model queue overrun");
                    read_address=address_byte;read_due=tick+5;reads++;
                end
            end
            if(dut.mrst[1])begin
                if(!dut.v1_pending && dut.extended_request && !dut.v1_accepted)slot_loads++;
                if(old_grant)native_grants++;
                if(dut.v1_accepted)returned_acks++;
                if(dut.v1_pending && !mready && mwready)command_only_blocked++;
                if(dut.v1_pending && mready && !mwready)data_only_blocked++;
                if(dut.v1_pending && dut.legacy_valid)$fatal(1,"Simultaneous legacy/native owner");
                if(dut.v1_pending && (!dut.ext_active || !dut.v1_select))$fatal(1,"Pending native transaction lost owner");
            end
        end
        #1;
        if(rst && dut.mrst[1])begin
            if(slot_loads-native_grants-aborted_slots!=int'(dut.v1_pending))$fatal(1,"Slot conservation per cycle");
            if(native_grants-returned_acks-canceled_acks!=int'(dut.v1_accepted))$fatal(1,"ACK conservation per cycle");
        end
        if(old_active && rst && dut.mrst[1])begin
            if(old_pixel_ack && old_native_valid && dut.u_v1.u_pixels.native_valid)$fatal(1,"Native producer retained VALID after ACK");
            if(dut.v1_accepted!==old_grant)$fatal(1,"Acceptance pulse is not delayed DDR grant");
            if(old_pending)begin
                held_checks++;
                if({dut.v1_tx_write,dut.v1_tx_addr,dut.v1_tx_data,dut.v1_tx_mask}!==old_payload)
                    $fatal(1,"Payload changed while slot held");
            end
        end
    end
    task automatic write_reg(input [31:0] a,input [31:0] d);
        integer deadline;
        @(negedge hc);sel=1;wr=1;trans=2;address=a;deadline=0;
        do begin @(posedge hc);deadline++;if(deadline>20000)$fatal(1,"AHB address timeout");end while(!hready);
        @(negedge hc);sel=0;trans=0;data=d;deadline=0;
        do begin @(posedge hc);deadline++;if(deadline>20000)$fatal(1,"AHB data timeout");end while(!hready);
        @(negedge hc);wr=0;
    endtask
    task automatic packet(input [255:0] words,input integer gap);
        for(integer k=0;k<8;k++)begin
            write_reg('h10,words[k*32+:32]);
            repeat(gap+(k%3))@(negedge hc);
        end
    endtask
    task automatic fence(input integer count);
        integer deadline,fenced_writes;
        deadline=0;
        while(dut.done_count!=count && deadline<30000)begin @(negedge mc);deadline++;end
        if(dut.done_count!=count)$fatal(1,"Fence timeout done=%0d expected=%0d pixel=%h pending=%b valid=%b ready=%b take=%b",
            dut.done_count,count,dut.u_v1.u_pixels.state,dut.v1_pending,dut.u_v1.u_pixels.native_valid,br,arb.take_blitter);
        fenced_writes=writes;
        repeat(24)@(negedge mc);
        if(writes!=fenced_writes)$fatal(1,"Late write after completion fence");
        if(dut.v1_pending || dut.v1_accepted || dut.u_v1.u_pixels.native_valid || bv)
            $fatal(1,"Transaction survived completion");
        if(dut.v1_rejected || dut.command_bad || dut.command_lost || dut.queue_lost)
            $fatal(1,"Unexpected error/rejection");
    endtask
    task automatic compare_memory;
        for(integer k=0;k<BYTES;k++)if(memory[k]!==expected[k])
            $fatal(1,"Memory/guard mismatch @%h got=%h expected=%h",BASE+k,memory[k],expected[k]);
        completed_tests++;
    endtask
    task automatic target;
        packet({96'd0,32'h01000100,32'h00800010,32'(DEPTH),32'(COLOR),32'h16000000},1);
    endtask
    task automatic clear(input integer flags,x,y,w,h,input [15:0] color,depth);
        packet({64'd0,32'((w<<16)|h),32'((x<<16)|y),16'd0,depth,16'd0,color,32'(flags),32'h1c000000},2);
    endtask
    task automatic expected_clear(input integer flags,x,y,w,h,input [15:0] color,depth);
        integer p;
        for(integer yy=y;yy<y+h;yy++)for(integer xx=x;xx<x+w;xx++)begin
            if(flags&1)begin p=COLOR-BASE+yy*256+xx*2;expected[p]=color[7:0];expected[p+1]=color[15:8];end
            if(flags&2)begin p=DEPTH-BASE+yy*256+xx*2;expected[p]=depth[7:0];expected[p+1]=depth[15:8];end
        end
    endtask
    task automatic wait_pending;
        integer deadline;
        deadline=0;
        while(!dut.v1_pending && deadline<10000)begin @(negedge mc);deadline++;end
        if(!dut.v1_pending)$fatal(1,"No pending request to exercise backpressure/reset");
    endtask
    task automatic reset_all;
        @(negedge hc);rst=0;sel=0;wr=0;trans=0;
        repeat(12)@(negedge mc);
        if(dut.v1_pending || dut.v1_accepted || bv)$fatal(1,"Reset did not flush native request");
        @(negedge hc);rst=1;
        repeat(40)@(negedge mc);
    endtask
    task automatic copy(input integer sx,dx,w);
        packet({32'd0,32'((w<<16)|1),32'(dx<<16),32'(sx<<16),32'h00000020,32'h00100001,32'h00808000,32'h1d000000},1);
    endtask
    task automatic expect_copy(input integer sx,dx,w);
        for(integer k=0;k<w*2;k++)expected[COLOR-BASE+dx*2+k]=memory['h8000+sx*2+k];
    endtask
    integer limit;
    initial begin
        for(integer k=0;k<BYTES;k++)begin memory[k]=8'(k*37+19);expected[k]=memory[k];end
        reset_all();target();fence(1);compare_memory();
        copy(0,0,16);fence(2);expect_copy(0,0,16);compare_memory();
        if(reads!=1 || writes!=1 || native_grants!=2)$fatal(1,"COPY16 expected one read and one write");
        // Data-only backpressure must allow the source read, then hold write.
        for(integer k=0;k<32;k++)begin memory['h8000+k]=8'(k*53+41);expected['h8000+k]=memory['h8000+k];end
        mode=2;repeat(4)@(negedge mc);copy(5,3,7);limit=0;
        while(!(dut.v1_pending && dut.v1_tx_write) && limit<10000)begin @(negedge mc);limit++;end
        if(limit==10000)$fatal(1,"COPY never reached held write after read");
        repeat(60)@(negedge mc);compare_memory();
        if(reads!=2 || writes!=1)$fatal(1,"Read/write independent backpressure");
        mode=0;fence(3);expect_copy(5,3,7);compare_memory();
        if(reads!=2 || writes!=2 || slot_loads!=4 || native_grants!=4 || returned_acks!=4)$fatal(1,"COPY conservation");
        if(dut.u_v1.u_pixels.native_valid)$fatal(1,"COPY accidentally uses native_valid");
        $display("PASS R19 REAL SLOT COPY reads=%0d writes=%0d loads=%0d acks=%0d bytes_per_check=%0d data_stall=%0d",reads,writes,slot_loads,returned_acks,BYTES,data_only_blocked);
        $finish;
    end
    initial begin #10000000;$fatal(1,"Global bounded timeout");end
endmodule
