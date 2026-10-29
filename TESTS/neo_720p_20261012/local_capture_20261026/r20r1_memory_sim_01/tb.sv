`timescale 1ns/1ps
module tb;
reg clk=0,resetn=0,child_resetn=0,start=0;
reg [255:0] command=0;
reg accepted=0;wire [63:0] diag_pixels;
reg cap_arm=0,cap_snap=0;
wire arm_ack,snap_ack,cap_ready,cap_beat;wire [63:0] cap_held;
wire [31:0] geometry_header,pixel_header,rejected;
wire done,native_valid,copy_valid,cache_valid,fetch_valid;
always #6.6665 clk=~clk;
GSR GSR(.GSRI(1'b1));
gpu_geometry dut(
.trace_resetn(resetn),
.trace_arm_req(cap_arm),
.trace_snap_req(cap_snap),
.gpu_clk(clk),
.v1_select(1'b1),
.v1_rx_valid(1'b0),
.v1_accepted(accepted),
.ext_command(command[255:32]),
.gpu_debug_state_98(start),
.gpu_debug_state_104(command[24]),
.gpu_debug_state_105(command[25]),
.gpu_debug_state_106(command[26]),
.gpu_debug_state_107(command[27]),
.gpu_debug_state_108(command[28]),
.gpu_debug_state_109(command[29]),
.gpu_debug_state_110(command[30]),
.gpu_debug_state_111(command[31]),
.gpu_debug_state_224(command[0]),
.gpu_debug_state_225(command[1]),
.gpu_debug_state_226(command[2]),
.gpu_debug_state_227(command[3]),
.gpu_debug_state_228(command[4]),
.gpu_debug_state_229(command[5]),
.gpu_debug_state_230(command[6]),
.gpu_debug_state_231(command[7]),
.gpu_debug_state_232(command[8]),
.gpu_debug_state_233(command[9]),
.gpu_debug_state_234(command[10]),
.gpu_debug_state_235(command[11]),
.gpu_debug_state_236(command[12]),
.gpu_debug_state_237(command[13]),
.gpu_debug_state_238(command[14]),
.gpu_debug_state_239(command[15]),
.gpu_debug_state_240(command[16]),
.gpu_debug_state_241(command[17]),
.gpu_debug_state_242(command[18]),
.gpu_debug_state_243(command[19]),
.gpu_debug_state_244(command[20]),
.gpu_debug_state_245(command[21]),
.gpu_debug_state_246(command[22]),
.gpu_debug_state_247(command[23]),
.v1_rx_data(256'd0),
.gpu_debug_state_46(resetn),
.gpu_debug_state_48(child_resetn),
.gpu_debug_state_49(child_resetn),
.gpu_debug_state_50(child_resetn),
.gpu_debug_state_51(child_resetn),
.gpu_debug_state_52(child_resetn),
.gpu_debug_state_53(child_resetn),
.trace_arm_ack(arm_ack),.trace_snap_ack(snap_ack),.trace_ready(cap_ready),.trace_heartbeat(cap_beat),.trace_held(cap_held),
.gpu_observe_packet_words(geometry_header),.gpu_observe_packet_words_113(pixel_header),
.v1_done(done),.v1_rejected(rejected),.native_valid(native_valid),.copy_valid(copy_valid),.cache_valid(cache_valid),.fetch_valid(fetch_valid),.diag_pixels(diag_pixels));

reg pending=0;
reg [27:0] slot_addr;
reg [255:0] slot_data;
reg [31:0] slot_mask;
reg slot_write;
integer tick=0,hold_cycles=0,stall_cycles=0,bursts=0,total_bursts=0,checks=0;
wire grant=hold_cycles==0 && tick%7>=2;
reg [7:0] mem_color[0:4095],mem_depth[0:4095];
integer k,offset;
always @(posedge clk) begin
    tick<=tick+1;
    if(hold_cycles>0)hold_cycles<=hold_cycles-1;
    if(!resetn || !child_resetn)begin accepted<=0;pending<=0;end
    else begin
        accepted<=pending && grant;
        if(pending)begin
            if(grant)begin
                if(slot_write!==1 || slot_addr[2:0]!==0)$fatal(1,"Invalid native write");
                for(k=0;k<32;k=k+1)if(!slot_mask[k])begin
                    if(slot_addr>=28'h4800000 && slot_addr<28'h4800400)begin
                        offset=(slot_addr-28'h4800000)*4+k;mem_color[offset]=slot_data[k*8+:8];
                    end else if(slot_addr>=28'h4804000 && slot_addr<28'h4804400)begin
                        offset=(slot_addr-28'h4804000)*4+k;mem_depth[offset]=slot_data[k*8+:8];
                    end else $fatal(1,"Native address outside guarded model: %h",slot_addr);
                end
                pending<=0;bursts=bursts+1;total_bursts=total_bursts+1;
            end else stall_cycles=stall_cycles+1;
        end else if(native_valid && !accepted)pending<=1;
        if(!pending)begin
            slot_addr<={dut.u_pixels.native_addr[27:3],3'b0};
            slot_data<=dut.u_pixels.native_data;slot_mask<=dut.u_pixels.native_mask;
            slot_write<=dut.u_pixels.native_write;
        end
    end
    #1;
    if(resetn && child_resetn)begin
        if((^diag_pixels)===1'bx)$fatal(1,"Unknown diagnostic field");
        if(diag_pixels[57:0]!==dut.u_pixels.state)$fatal(1,"FSM wiring");
        if(diag_pixels[58]!==dut.u_pixels.native_valid_s1.D ||
           diag_pixels[59]!==dut.u_pixels.native_valid_s1.CE ||
           diag_pixels[60]!==dut.u_pixels.native_valid_s1.RESET)$fatal(1,"Actual native FF pin mapping");
        if(copy_valid || cache_valid || fetch_valid)$fatal(1,"Unexpected reader in CLEAR replay");
    end
end
task packet(input [255:0] words);
    integer deadline;
    reg [31:0] before_bad;
    begin
        before_bad=rejected;
        @(negedge clk);command=words;start=1;
        @(negedge clk);start=0;deadline=0;
        while(done!==1 && deadline<4000)begin @(negedge clk);deadline=deadline+1;end
        if(done!==1)$fatal(1,"CLEAR replay timeout, opcode=%h state=%h",words[31:0],diag_pixels);
        if(rejected!==before_bad)$fatal(1,"Unexpected reject");
        repeat(8)@(negedge clk);
        if(pending || accepted || native_valid)$fatal(1,"Pending or duplicate write after completion");
    end
endtask
task clear_test(input integer flags,x,y,w,h,expected_bursts);
    integer i,px,py;reg [255:0] words;reg [15:0] c,z;
    begin
        for(i=0;i<4096;i=i+1)begin mem_color[i]=(i*37+19)&255;mem_depth[i]=(i*53+41)&255;end
        bursts=0;hold_cycles=60;
        words=0;words[31:0]=32'h1c000000;words[63:32]=flags;
        words[95:64]=32'h5aa5;words[127:96]=32'h7bde;
        words[159:128]=(x<<16)|y;words[191:160]=(w<<16)|h;
        packet(words);
        if(bursts!=expected_bursts)$fatal(1,"Wrong burst count flags=%0d got=%0d expected=%0d",flags,bursts,expected_bursts);
        for(py=0;py<16;py=py+1)for(px=0;px<128;px=px+1)begin
            i=py*256+px*2;
            c=(((i+1)*37+19)&255)<<8 | ((i*37+19)&255);
            z=(((i+1)*53+41)&255)<<8 | ((i*53+41)&255);
            if(px>=x && px<x+w && py>=y && py<y+h)begin
                if(flags&1)c=16'h5aa5;if(flags&2)z=16'h7bde;
            end
            if({mem_color[i+1],mem_color[i]}!==c || {mem_depth[i+1],mem_depth[i]}!==z)
                $fatal(1,"Pixel/mask mismatch xy=%0d,%0d flags=%0d",px,py,flags);
            checks=checks+2;
        end
        $display("CLEAR flags=%0d xy=%0d,%0d wh=%0d,%0d bursts=%0d",flags,x,y,w,h,bursts);
    end
endtask
integer repeat_index;
initial begin
    for(repeat_index=0;repeat_index<2;repeat_index=repeat_index+1)begin
        resetn=0;child_resetn=0;
        repeat(8)@(negedge clk);resetn=1;
        repeat(6)@(negedge clk);child_resetn=1;
        repeat(8)@(negedge clk);
        packet({96'd0,32'h01000100,32'h00800010,32'h12010000,32'h12000000,32'h16000000});
        clear_test(0,0,0,16,1,0);
        clear_test(3,0,0,0,0,0);
        clear_test(1,0,0,16,1,1);
        clear_test(2,0,0,16,1,1);
        clear_test(3,3,2,19,2,8);
        clear_test(3,0,0,128,16,256);
    end
    if(stall_cycles<50 || total_bursts!=532)$fatal(1,"Insufficient backpressure coverage");
    $display("PASS mapped CLEAR observer checks=%0d bursts=%0d stalls=%0d",checks,total_bursts,stall_cycles);
    $finish;
end
initial begin #1000000;$fatal(1,"Global timeout");end
endmodule
