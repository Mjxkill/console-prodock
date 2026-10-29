module reset_equivalence(input exts_hclk,input exts_hrstn);
wire [5:0] vid_reset_branches;
    reg reference_reset = 1'b0; always @(posedge exts_hclk) reference_reset <= exts_hrstn;
    reg vid_hrstn_r /* synthesis syn_preserve=1 syn_keep=1 */ = 1'b0;
    always @(posedge exts_hclk) vid_hrstn_r <= exts_hrstn;
    reg vid_hrstn_scanout /* synthesis syn_preserve=1 syn_keep=1 */ = 1'b0;
    always @(posedge exts_hclk) vid_hrstn_scanout <= exts_hrstn;
    reg vid_hrstn_accel /* synthesis syn_preserve=1 syn_keep=1 */ = 1'b0;
    always @(posedge exts_hclk) vid_hrstn_accel <= exts_hrstn;
    reg vid_hrstn_gamepads /* synthesis syn_preserve=1 syn_keep=1 */ = 1'b0;
    always @(posedge exts_hclk) vid_hrstn_gamepads <= exts_hrstn;
    reg vid_hrstn_scan_queue /* synthesis syn_preserve=1 syn_keep=1 */ = 1'b0;
    always @(posedge exts_hclk) vid_hrstn_scan_queue <= exts_hrstn;
    reg vid_hrstn_usb_trace /* synthesis syn_preserve=1 syn_keep=1 */ = 1'b0;
    always @(posedge exts_hclk) vid_hrstn_usb_trace <= exts_hrstn;
    reg vid_hrstn_usb_msc /* synthesis syn_preserve=1 syn_keep=1 */ = 1'b0;
    always @(posedge exts_hclk) vid_hrstn_usb_msc <= exts_hrstn;
    assign vid_reset_branches[0] = vid_hrstn_scanout;
    assign vid_reset_branches[1] = vid_hrstn_accel;
    assign vid_reset_branches[2] = vid_hrstn_gamepads;
    assign vid_reset_branches[3] = vid_hrstn_scan_queue;
    assign vid_reset_branches[4] = vid_hrstn_usb_trace;
    assign vid_reset_branches[5] = vid_hrstn_usb_msc;

always @* assert({vid_hrstn_r,vid_reset_branches} == {7{reference_reset}});
endmodule
