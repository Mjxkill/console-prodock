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
        .wr_data(bwd),.wr_mask(bm),.ready(br),.rd_data(brd),.rd_valid(brv));
    wire me,mwe,mend;
    wire [2:0] cmd;
    wire [28:0] ma;
    wire [255:0] md;
    wire [31:0] mm;
    reg mready=0, mwready=0;
    integer tick=0, mode=0;
    // mode1 independently blocks command acceptance, mode2 write-data
    // acceptance, mode3 both. Mode0 has bounded, distinct periodic stalls.
    always @(negedge mc)begin
        tick++;
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
        .m_wr_data(md),.m_wr_mask(mm),.m_wr_ready(mwready),.m_rd_data(256'd0),
        .m_rd_valid(1'b0),.m_rd_end(1'b0));
    localparam BASE=32'h00800000, COLOR=32'h00800020, DEPTH=32'h00810000, BYTES=32'h12000;
    reg [7:0] memory[0:BYTES-1],expected[0:BYTES-1];
    integer writes=0, native_grants=0, returned_acks=0, slot_loads=0;
    integer held_checks=0, command_only_blocked=0, data_only_blocked=0;
    integer aborted_slots=0,canceled_acks=0;
    reg old_native_issue;integer ack_drop_checks=0,native_rise_checks=0;
    reg previous_rst=0,old_pixel_ack,old_native_valid;
    integer negative=0;
    integer address_byte, completed_tests=0;
    reg old_pending,old_grant,old_active;
    reg [317:0] old_payload;
    always @(posedge mc) begin
        old_pending=dut.v1_pending;
        old_pixel_ack=dut.v1_accepted && dut.v1_select && !dut.u_v1.fetch_valid;
        old_native_valid=dut.u_v1.u_pixels.native_valid;
        old_native_issue=dut.u_v1.u_pixels.native_issue;
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
                if(!mready || cmd!==0 || !mwe || !mend || !mwready)
                    $fatal(1,"Unexpected/ungated DDR command: cmd=%h ready=%b/%b",cmd,mready,mwready);
                if(ma[2:0]!==0)$fatal(1,"DDR address alignment");
                address_byte=int'(ma)*4-BASE;
                if(address_byte<0 || address_byte+32>BYTES)$fatal(1,"Out of guarded region: %h",ma);
                for(integer b=0;b<32;b++)if(negative==1 ? mm[b]:!mm[b])memory[address_byte+b]=md[b*8+:8];
                writes++;
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
            if(!old_native_valid && dut.u_v1.u_pixels.native_valid)begin
                native_rise_checks++;
                if(!old_native_issue)$fatal(1,"Native VALID rose outside issue state");
            end
            if(old_pixel_ack && old_native_valid && !dut.u_v1.u_pixels.native_valid)ack_drop_checks++;
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
    integer before_writes,before_grants;
    initial begin
        if($value$plusargs("mem_half=%f",mem_half))begin end
        if($value$plusargs("negative=%d",negative))begin end
        for(integer k=0;k<BYTES;k++)begin memory[k]=8'(k*37+19);expected[k]=memory[k];end
        reset_all();target();fence(1);compare_memory();
        packet({160'd0,32'h00200001,32'h00200000,32'h0100a600},0);fence(2);
        for(integer k=32;k<64;k++)expected[k]=8'ha6;
        compare_memory();
        before_writes=writes;clear(0,0,0,16,1,16'h5aa5,16'h7bde);fence(3);compare_memory();
        clear(3,0,0,0,0,16'h5aa5,16'h7bde);fence(4);compare_memory();
        if(writes!=before_writes)$fatal(1,"No-op CLEAR issued memory write");
        clear(1,0,0,16,1,16'h5aa5,16'h7bde);fence(5);
        expected_clear(1,0,0,16,1,16'h5aa5,16'h7bde);compare_memory();
        if(writes!=before_writes+1)$fatal(1,"Same-address CLEAR burst duplication/loss");
        $display("SAME_ADDRESS_PASS writes=%0d native_grants=%0d",writes,native_grants);
        // Block each handshake input independently, then prove recovery.
        for(integer blocking=1;blocking<=2;blocking++)begin
            mode=blocking;repeat(4)@(negedge mc);before_writes=writes;
            clear(1,16*blocking,1,16,1,16'h1234+16'(blocking),16'h7bde);wait_pending();
            repeat(80)@(negedge mc);
            if(writes!=before_writes)$fatal(1,"Write escaped independent backpressure");
            compare_memory();mode=0;fence(5+blocking);
            expected_clear(1,16*blocking,1,16,1,16'h1234+16'(blocking),16'h7bde);compare_memory();
            if(writes!=before_writes+1)$fatal(1,"Released write duplicated/lost");
        end
        before_writes=writes;clear(3,3,2,19,2,16'h2345,16'h6789);fence(8);
        expected_clear(3,3,2,19,2,16'h2345,16'h6789);compare_memory();
        if(writes!=before_writes+8)$fatal(1,"Partial masks/burst count");
        // Stop only the AHB clock after pending is present; GPU/arbiter
        // must finish autonomously when DDR becomes ready.
        mode=3;clear(1,48,4,16,1,16'hbeef,16'h7bde);wait_pending();
        @(negedge hc);hc_run=0;repeat(20)@(negedge mc);mode=0;fence(9);
        hc_run=1;expected_clear(1,48,4,16,1,16'hbeef,16'h7bde);compare_memory();
        // Abort a held request. No stale write may replay after reset.
        mode=3;clear(1,64,5,16,1,16'hdead,16'h7bde);wait_pending();
        repeat(16)@(negedge mc);before_writes=writes;reset_all();mode=0;
        repeat(200)@(negedge mc);
        if(writes!=before_writes || dut.done_count!=0)$fatal(1,"Pre-reset transaction replay");
        compare_memory();target();fence(1);
        clear(1,64,5,16,1,16'hcafe,16'h7bde);fence(2);
        expected_clear(1,64,5,16,1,16'hcafe,16'h7bde);compare_memory();
        if(writes!=before_writes+1)$fatal(1,"Post-reset write count");
        if(native_grants!=returned_acks+canceled_acks || slot_loads!=native_grants+aborted_slots || aborted_slots!=1)
            $fatal(1,"Grant/ACK/slot conservation: loads=%0d grants=%0d ack=%0d",slot_loads,native_grants,returned_acks);
        if(ack_drop_checks!=returned_acks || native_rise_checks!=slot_loads)$fatal(1,"Native issue/ACK assertions vacuous");
        $display("NATIVE_INVARIANTS rises=%0d ack_drops=%0d",native_rise_checks,ack_drop_checks);
        if(held_checks<160 || command_only_blocked<50 || data_only_blocked<50)
            $fatal(1,"Missing independent stall coverage");
        $display("PASS R19 REAL SLOT CLEAR tests=%0d bytes_per_check=%0d writes=%0d loads=%0d grants=%0d acks=%0d held=%0d cmd_stall=%0d data_stall=%0d mem_half=%f",
            completed_tests,BYTES,writes,slot_loads,native_grants,returned_acks,held_checks,command_only_blocked,data_only_blocked,mem_half);
        $finish;
    end
    initial begin #10000000;$fatal(1,"Global bounded timeout");end

// Explicit four-state guards: no silent if(X) on these control/payload paths.
always @(negedge mc)if(rst && dut.mrst[1])begin
  if((^{dut.v1_pending,dut.v1_accepted,bv,br,me,mready,mwready})===1'bx)
    $fatal(1,"UNKNOWN memory control");
  if(dut.v1_pending && (^{dut.v1_tx_write,dut.v1_tx_addr,dut.v1_tx_data,dut.v1_tx_mask})===1'bx)
    $fatal(1,"UNKNOWN held slot payload");
  if(me && (^{cmd,ma,md,mm,mwe,mend})===1'bx)$fatal(1,"UNKNOWN DDR transaction");
end
always @(negedge hc)if(rst)begin
  if((^{hready,dut.queue_valid,dut.queue_full})===1'bx)$fatal(1,"UNKNOWN command control");
end

endmodule
