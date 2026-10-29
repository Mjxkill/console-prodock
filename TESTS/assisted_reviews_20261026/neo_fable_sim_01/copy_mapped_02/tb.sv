`timescale 1ns/1ps
module tb;
reg clk=0,resetn=0,child_resetn=0,start=0;
reg [255:0] command=0;
reg cap_arm=0,cap_snap=0;
wire arm_ack,snap_ack,cap_ready,cap_beat;wire [63:0] cap_held;
wire [31:0] geometry_header,pixel_header,rejected;
wire done,native_valid,copy_valid,cache_valid,fetch_valid;
realtime half_period=6.6665,clock_phase=0,reset_offset=0;
initial begin
 if($value$plusargs("half=%f",half_period))begin end
 if($value$plusargs("phase=%f",clock_phase))begin end
 if($value$plusargs("reset_offset=%f",reset_offset))begin end
 #(clock_phase);forever #(half_period)clk=~clk;
end
GSR GSR(.GSRI(1'b1));
gpu_geometry dut(
.trace_resetn(resetn),
.trace_arm_req(cap_arm),
.trace_snap_req(cap_snap),
.gpu_clk(clk),
.v1_select(1'b1),
.v1_rx_valid(1'b0),
.v1_accepted(1'b1),
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
.v1_done(done),.v1_rejected(rejected),.native_valid(native_valid),.copy_valid(copy_valid),.cache_valid(cache_valid),.fetch_valid(fetch_valid));

integer captures=0,checks=0,drop_capture=0,strict=0,rounds=0;
reg capture_expected;reg [223:0] expected_payload;
always @(posedge clk)begin
    capture_expected=child_resetn && dut.u_pixels.state[41] && dut.u_pixels.u_copy.state_0==0;
    expected_payload=dut.u_pixels.packet[255:32];
    if(capture_expected && strict && dut.u_pixels.u_copy.n7630_6!==1)
        $fatal(1,"COPY packet capture disabled");
    #1;
    if(capture_expected)begin
        captures=captures+1;
        if(!drop_capture && dut.u_pixels.u_copy.packet_0[255:32]!==expected_payload)
            $fatal(1,"COPY stored packet differs from actual input");
    end
end
task send(input [255:0] words);
 begin
    @(negedge clk);command=words;start=1;
    @(negedge clk);start=0;
    // The accepted words must be private, not sampled again later.
    command={8{32'hbaddcafe}};
 end
endtask
task reset_target;
 integer deadline;
 begin
    resetn=0;child_resetn=0;start=0;
    repeat(10)@(negedge clk);resetn=1;
    repeat(3)@(negedge clk);#(reset_offset);child_resetn=1;
    repeat(8)@(negedge clk);
    send(256'h0000000000000000000000000100010000800010008100000080002016000000);
    deadline=0;
    while(done!==1 && deadline<200)begin @(negedge clk);deadline++;end
    if(done!==1 || rejected!==0 || dut.shader_target_valid!==1)$fatal(1,"Real mapped TARGET failed");
    if(dut.u_pixels.u_copy.color_base!==30'h00800020 || dut.u_pixels.u_copy.color_end!==33'h00801020 ||
       dut.u_pixels.u_copy.color_stride!==256 || dut.u_pixels.u_copy.right!==128 || dut.u_pixels.u_copy.bottom!==16)
        $fatal(1,"Real mapped TARGET fields differ");
    repeat(8)@(negedge clk);
 end
endtask
task check_copy(input [255:0] words,input [2:0] bad,input empty);
 integer deadline,before_capture;
 begin
    before_capture=captures;
    send(words);deadline=0;
    while(done!==1 && copy_valid!==1 && deadline<300)begin @(negedge clk);deadline++;end
    if(deadline==300)$fatal(1,"COPY descriptor progress timeout");
    if(captures!=before_capture+1)$fatal(1,"COPY capture count");
    if(dut.u_pixels.u_copy.descriptor_bad!==bad)$fatal(1,"descriptor_bad actual=%b expected=%b case=%0d",dut.u_pixels.u_copy.descriptor_bad,bad,checks);
    if(bad!=0 || empty)begin
        if(done!==1 || rejected!==(bad!=0) || copy_valid || native_valid || cache_valid || fetch_valid)
            $fatal(1,"Rejected/empty COPY result differs case=%0d",checks);
    end else begin
        if(copy_valid!==1 || rejected!==0 || dut.u_pixels.u_copy.copy_bad || dut.u_pixels.u_copy.copy_write)
            $fatal(1,"Valid COPY did not issue first read case=%0d",checks);
        if(dut.u_pixels.u_copy.copy_addr!==words[61:37])$fatal(1,"First COPY read address differs");
    end
    checks++;
    $display("COPY_DESCRIPTOR case=%0d bad=%b empty=%b captures=%0d",checks,bad,empty,captures);
 end
endtask
initial begin
    if($value$plusargs("drop_capture=%d",drop_capture))begin end
    if($value$plusargs("strict=%d",strict))begin end
    if(drop_capture==2)begin
        // Populate packet storage, then reset controls: private descriptor
        // is deliberately not reset (mapped FF RESET=GND, INIT only at load).
        drop_capture=0;reset_target();
        check_copy(256'h000000000010000100000000000000000000002000100001008080001d000000,3'b000,0);
        reset_target();drop_capture=2;
        if(dut.u_pixels.u_copy.packet_0[255:32]!==224'h00000000001000010000000000000000000000200010000100808000)
            $fatal(1,"Control reset unexpectedly changed stored COPY descriptor");
        force dut.u_pixels.u_copy.n7630_6=1'b0;
        // New command has reserved word7=1 (normally rejected); suppressed
        // capture instead reuses the old valid descriptor and emits a read.
        check_copy(256'h000000010010000100000000000000000000002000100001008080001d000000,3'b000,0);
        release dut.u_pixels.u_copy.n7630_6;
        $display("PASS MAPPED COPY STALE: control reset preserves packet and dropped capture replays old valid descriptor");
        $finish;
    end
    if(drop_capture==1)begin
        reset_target();
        force dut.u_pixels.u_copy.n7630_6=1'b0;
        check_copy(256'h000000000010000100000000000000000000002000100001008080001d000000,3'b011,0);
        release dut.u_pixels.u_copy.n7630_6;
        $display("PASS MAPPED COPY NEGATIVE: missing first capture gives bad011 without memory request");
        $finish;
    end
    for(rounds=0;rounds<2;rounds++)begin
 reset_target(); check_copy(256'h000000000010000100000000000000000000002000100001008080001d000000,3'd0,1'b0);
 reset_target(); check_copy(256'h000000000010000100000000000000000000002000100001008080021d000000,3'd1,1'b0);
 reset_target(); check_copy(256'h000000000010000100000000000000000000002000000001008080001d000000,3'd1,1'b0);
 reset_target(); check_copy(256'h000000000010000100000000000000000000082004010001008080001d000000,3'd1,1'b0);
 reset_target(); check_copy(256'h000000000010000100000000000000000000002000100000008080001d000000,3'd2,1'b0);
 reset_target(); check_copy(256'h000000000010000100000000000000000000002000100201008080001d000000,3'd2,1'b0);
 reset_target(); check_copy(256'h000000000010000100000000000000000000001000100001008080001d000000,3'd2,1'b0);
 reset_target(); check_copy(256'h000000000010000100000000000000000001002000100001008080001d000000,3'd2,1'b0);
 reset_target(); check_copy(256'h000000010010000100000000000000000000002000100001008080001d000000,3'd4,1'b0);
 reset_target(); check_copy(256'h0000000000100001000000000000000000000020001000023fffffe01d000000,3'd4,1'b0);
 reset_target(); check_copy(256'h000000000010000100000000000000000000002000100001008000401d000000,3'd4,1'b0);
 reset_target(); check_copy(256'h000000000010000100000000000000000000010000800010008000201d000000,3'd0,1'b0);
 reset_target(); check_copy(256'h000000000010000100000000000000000000080004000200008080001d000000,3'd0,1'b0);
 reset_target(); check_copy(256'h000000000000000000000000000000000000002000100001008080001d000000,3'd0,1'b1);

    end
    $display("PASS MAPPED COPY DESCRIPTORS checks=%0d captures=%0d",checks,captures);$finish;
end
initial begin #2000000;$fatal(1,"Bounded watchdog");end
endmodule
