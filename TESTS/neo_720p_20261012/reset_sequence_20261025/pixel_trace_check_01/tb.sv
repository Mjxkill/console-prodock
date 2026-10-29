`timescale 1ns/1ps
module tb;
reg clk=0,resetn=0,child_resetn=0,start=0;
reg [255:0] command=0;
wire [31:0] geometry_header,pixel_header,rejected;
wire done,native_valid,copy_valid,cache_valid,fetch_valid;
always #6.6665 clk=~clk;
GSR GSR(.GSRI(1'b1));
gpu_geometry dut(
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
.gpu_observe_packet_words(geometry_header),.gpu_observe_packet_words_113(pixel_header),
.v1_done(done),.v1_rejected(rejected),.native_valid(native_valid),.copy_valid(copy_valid),.cache_valid(cache_valid),.fetch_valid(fetch_valid));
integer trace, sample_index=0;
initial begin
    trace=$fopen("mapped_trace.csv", "w");
    if(!trace)$fatal(1,"Trace open failed");
    $fwrite(trace, "Data:\ntime unit: us, u_accel/u_v1/shader_start, gpu_observe_packet_words[0], gpu_observe_packet_words[1], gpu_observe_packet_words[2], gpu_observe_packet_words[3], gpu_observe_packet_words[4], gpu_observe_packet_words[5], gpu_observe_packet_words[6], gpu_observe_packet_words[7], gpu_observe_packet_words[8], gpu_observe_packet_words[9], gpu_observe_packet_words[10], gpu_observe_packet_words[11], gpu_observe_packet_words[12], gpu_observe_packet_words[13], gpu_observe_packet_words[14], gpu_observe_packet_words[15], gpu_observe_packet_words[16], gpu_observe_packet_words[17], gpu_observe_packet_words[18], gpu_observe_packet_words[19], gpu_observe_packet_words[20], gpu_observe_packet_words[21], gpu_observe_packet_words[22], gpu_observe_packet_words[23], gpu_observe_packet_words[24], gpu_observe_packet_words[25], gpu_observe_packet_words[26], gpu_observe_packet_words[27], gpu_observe_packet_words[28], gpu_observe_packet_words[29], gpu_observe_packet_words[30], gpu_observe_packet_words[31], u_accel/u_v1/shader_command[0], u_accel/u_v1/shader_command[1], u_accel/u_v1/shader_command[2], u_accel/u_v1/shader_command[3], u_accel/u_v1/shader_command[4], u_accel/u_v1/shader_command[5], u_accel/u_v1/shader_command[6], u_accel/u_v1/shader_command[7], u_accel/u_v1/shader_command[8], u_accel/u_v1/shader_command[9], u_accel/u_v1/shader_command[10], u_accel/u_v1/shader_command[11], u_accel/u_v1/shader_command[12], u_accel/u_v1/shader_command[13], u_accel/u_v1/shader_command[14], u_accel/u_v1/shader_command[15], u_accel/u_v1/shader_command[16], u_accel/u_v1/shader_command[17], u_accel/u_v1/shader_command[18], u_accel/u_v1/shader_command[19], u_accel/u_v1/shader_command[20], u_accel/u_v1/shader_command[21], u_accel/u_v1/shader_command[22], u_accel/u_v1/shader_command[23], u_accel/u_v1/shader_command[24], u_accel/u_v1/shader_command[25], u_accel/u_v1/shader_command[26], u_accel/u_v1/shader_command[27], u_accel/u_v1/shader_command[28], u_accel/u_v1/shader_command[31], gpu_observe_packet_words_177[32], gpu_observe_packet_words_177[33], gpu_observe_packet_words_177[34], gpu_observe_packet_words_177[35], gpu_observe_packet_words_177[36], gpu_observe_packet_words_177[37], gpu_observe_packet_words_177[38], gpu_observe_packet_words_177[39], gpu_observe_packet_words_177[40], gpu_observe_packet_words_177[41], gpu_observe_packet_words_177[42], gpu_observe_packet_words_177[43], gpu_observe_packet_words_177[44], gpu_observe_packet_words_177[45], gpu_observe_packet_words_177[46], gpu_observe_packet_words_177[47], gpu_observe_packet_words_177[48], gpu_observe_packet_words_177[49], gpu_observe_packet_words_177[50], gpu_observe_packet_words_177[51], gpu_observe_packet_words_177[52], gpu_observe_packet_words_177[53], gpu_observe_packet_words_177[54], gpu_observe_packet_words_177[55], gpu_observe_packet_words_177[56], gpu_observe_packet_words_177[57], gpu_observe_packet_words_177[58], gpu_observe_packet_words_177[59], gpu_observe_packet_words_177[60], gpu_observe_packet_words_177[61], gpu_observe_packet_words_177[62], gpu_observe_packet_words_177[63], u_accel/u_v1/u_pixels/n37565_3, u_accel/u_v1/u_pixels/n1617_5, u_accel/u_v1/shader_start, u_accel/u_v1/shader_done, u_accel/u_v1/u_pixels/state[0], u_accel/u_v1/u_pixels/state[1], u_accel/u_v1/u_pixels/state[2], u_accel/u_v1/u_pixels/state[48], u_accel/u_v1/u_pixels/state[45], u_accel/u_v1/state[0], u_accel/u_v1/state[67], u_accel/u_v1/state[1], u_accel/u_v1/n56220_6, u_accel/u_v1/n22253_18, gpu_debug_state[46], gpu_debug_state[48], vid_hrstn, ddr_init, trial_request,\n");
end
always @(posedge clk) begin
    $fwrite(trace, "%0d, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b, %b,\n", sample_index, dut.shader_start, geometry_header[0], geometry_header[1], geometry_header[2], geometry_header[3], geometry_header[4], geometry_header[5], geometry_header[6], geometry_header[7], geometry_header[8], geometry_header[9], geometry_header[10], geometry_header[11], geometry_header[12], geometry_header[13], geometry_header[14], geometry_header[15], geometry_header[16], geometry_header[17], geometry_header[18], geometry_header[19], geometry_header[20], geometry_header[21], geometry_header[22], geometry_header[23], geometry_header[24], geometry_header[25], geometry_header[26], geometry_header[27], geometry_header[28], geometry_header[29], geometry_header[30], geometry_header[31], dut.shader_command[0], dut.shader_command[1], dut.shader_command[2], dut.shader_command[3], dut.shader_command[4], dut.shader_command[5], dut.shader_command[6], dut.shader_command[7], dut.shader_command[8], dut.shader_command[9], dut.shader_command[10], dut.shader_command[11], dut.shader_command[12], dut.shader_command[13], dut.shader_command[14], dut.shader_command[15], dut.shader_command[16], dut.shader_command[17], dut.shader_command[18], dut.shader_command[19], dut.shader_command[20], dut.shader_command[21], dut.shader_command[22], dut.shader_command[23], dut.shader_command[24], dut.shader_command[25], dut.shader_command[26], dut.shader_command[27], dut.shader_command[28], dut.shader_command[31], pixel_header[0], pixel_header[1], pixel_header[2], pixel_header[3], pixel_header[4], pixel_header[5], pixel_header[6], pixel_header[7], pixel_header[8], pixel_header[9], pixel_header[10], pixel_header[11], pixel_header[12], pixel_header[13], pixel_header[14], pixel_header[15], pixel_header[16], pixel_header[17], pixel_header[18], pixel_header[19], pixel_header[20], pixel_header[21], pixel_header[22], pixel_header[23], pixel_header[24], pixel_header[25], pixel_header[26], pixel_header[27], pixel_header[28], pixel_header[29], pixel_header[30], pixel_header[31], dut.u_pixels.n37565_3, dut.u_pixels.n1617_5, dut.shader_start, dut.shader_done, dut.u_pixels.state[0], dut.u_pixels.state[1], dut.u_pixels.state[2], dut.u_pixels.state[48], dut.u_pixels.state[45], dut.state[0], dut.state[67], dut.state[1], dut.n56220_6, dut.n22253_18, resetn, child_resetn, 1'b1, 1'b1, 1'b1);
    sample_index=sample_index+1;
end
integer captures=0;
reg [31:0] expected_header;
reg capture;
always @(posedge clk) begin
    capture=child_resetn && dut.shader_start && dut.u_pixels.state[0];
    expected_header={dut.u_pixels.shader_command_31,dut.u_pixels.shader_command_31,dut.u_pixels.shader_command_31,dut.u_pixels.shader_command_28,dut.u_pixels.shader_command_27,dut.u_pixels.shader_command_26,dut.u_pixels.shader_command_25,dut.u_pixels.shader_command_24,dut.u_pixels.shader_command_23,dut.u_pixels.shader_command_22,dut.u_pixels.shader_command_21,dut.u_pixels.shader_command_20,dut.u_pixels.shader_command_19,dut.u_pixels.shader_command_18,dut.u_pixels.shader_command_17,dut.u_pixels.shader_command_16,dut.u_pixels.shader_command_15,dut.u_pixels.shader_command_14,dut.u_pixels.shader_command_13,dut.u_pixels.shader_command_12,dut.u_pixels.shader_command_11,dut.u_pixels.shader_command_10,dut.u_pixels.shader_command_9,dut.u_pixels.shader_command_8,dut.u_pixels.shader_command_7,dut.u_pixels.shader_command_6,dut.u_pixels.shader_command_5,dut.u_pixels.shader_command_4,dut.u_pixels.shader_command_3,dut.u_pixels.shader_command_2,dut.u_pixels.shader_command_1,dut.u_pixels.shader_command_0};
    #1;
    if(capture) begin
        captures=captures+1;
        if(pixel_header!==expected_header)$fatal(1,"Mapped pixel capture failed expected=%h got=%h",expected_header,pixel_header);
        $display("CAPTURE cycle_time=%0t source=%h pixel=%h",$time,expected_header,pixel_header);
    end
    if(resetn && child_resetn && (native_valid || copy_valid || cache_valid || fetch_valid))$fatal(1,"Unexpected DDR command in config-only replay");
end
task run_packet(input [255:0] words,input integer expected_reject,input integer forwards);
    reg [31:0] before_bad;integer deadline;integer old_captures;
    begin
        before_bad=rejected;old_captures=captures;
        @(negedge clk);command=words;start=1;
        @(negedge clk);start=0;
        deadline=0;
        while(done!==1 && deadline<400)begin @(negedge clk);deadline=deadline+1;end
        if(done!==1)$fatal(1,"Mapped command timeout opcode=%h",words[31:0]);
        if(geometry_header!==words[31:0])$fatal(1,"Geometry header differs");
        if(forwards && pixel_header!==words[31:0])$fatal(1,"Pixel header differs");
        if(rejected-before_bad!==expected_reject)$fatal(1,"Rejection differs opcode=%h before=%0d after=%0d expected_delta=%0d",words[31:0],before_bad,rejected,expected_reject);
        if(captures-old_captures!=forwards)$fatal(1,"Unexpected number of captures");
        repeat(5)@(negedge clk);
    end
endtask
initial begin
    repeat(8)@(negedge clk);resetn=1;
    repeat(6)@(negedge clk);child_resetn=1;
    repeat(8)@(negedge clk);
    run_packet(256'h0000000000000000000000000040004000200040120010001200000016000000,0,1); // preflight
    run_packet(256'h0000000000000000000000000020002000000010000010000000000016000000,1,1); // zero_width
    run_packet(256'h0000000000000000000000000040004000200040120010001200000016000000,0,1); // preflight_again
    run_packet(256'h000000000000000000000000000000000000000000010000000000001f000000,0,0); // matrix_row0
    run_packet(256'h000000000000000000000000000000000000000000000000000000031f000000,1,0); // matrix_invalid_row
    run_packet(256'h0000000000000000000000000000000000000100000000000000000021000000,0,0); // light
    run_packet(256'h000000000000000000000000040201000000ffff000001000000000019000000,0,1); // material
    run_packet(256'h0000000000000000000000000000000000000020000100010170000018000000,0,1); // texture
    run_packet(256'h000000000000000000000000000000000000000000000000000100001a000000,0,1); // plane
    run_packet(256'h000000000000000000000000000000000000000000000000000000001e000000,0,1); // invalidate
    run_packet(256'h000000000000000000000000000000000000000000000000000000001e000000,0,1); // invalidate_repeat
    @(negedge clk);resetn=0;child_resetn=0;
    repeat(8)@(negedge clk);
    resetn=1;child_resetn=1;
    repeat(8)@(negedge clk);
    run_packet(256'h0000000000000000000000000040004000200040120010001200000016000000,0,1); // preflight
    run_packet(256'h0000000000000000000000000020002000000010000010000000000016000000,1,1); // zero_width
    run_packet(256'h0000000000000000000000000040004000200040120010001200000016000000,0,1); // preflight_again
    run_packet(256'h000000000000000000000000000000000000000000010000000000001f000000,0,0); // matrix_row0
    run_packet(256'h000000000000000000000000000000000000000000000000000000031f000000,1,0); // matrix_invalid_row
    run_packet(256'h0000000000000000000000000000000000000100000000000000000021000000,0,0); // light
    run_packet(256'h000000000000000000000000040201000000ffff000001000000000019000000,0,1); // material
    run_packet(256'h0000000000000000000000000000000000000020000100010170000018000000,0,1); // texture
    run_packet(256'h000000000000000000000000000000000000000000000000000100001a000000,0,1); // plane
    run_packet(256'h000000000000000000000000000000000000000000000000000000001e000000,0,1); // invalidate
    run_packet(256'h000000000000000000000000000000000000000000000000000000001e000000,0,1); // invalidate_repeat
    $display("PASS mapped command replay including warm reset, captures=%0d",captures);
    $finish;
end
initial begin #1000000;$fatal(1,"Global timeout");end
endmodule
