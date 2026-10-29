// USB-A2: low-speed host using bus80, without another clock tree or CDC.
`default_nettype none
module usb_gamepad #(
    parameter ROM_FILE = "rtl/usbhost/usb_hid_host_rom.hex"
) (
    input wire clk, rst,
    inout wire usb_dp, usb_dm,
    output wire [7:0] buttons,
    output reg [31:0] status,
    output wire [31:0] identity, report_count,
    output wire [63:0] report_data
);
    // 3 enables per 20 bus80 cycles: 12 MHz average; 6/7 cycles per tick.
    reg [4:0] phase;
    wire ce /* synthesis syn_keep=1 */ = phase >= 17;
    always @(posedge clk) begin
        if (rst) phase <= 0;
        else phase <= ce ? phase - 5'd17 : phase + 5'd3;
    end
    wire packet_done,packet_good;wire [7:0] packet_pid;
    wire connected, conerr, ready, strobe, save, report, online, supported, session_reset;
    // Named and retained for the LOCAL_CLOCK constraint: this reset must not
    // be promoted to an LW resource (G57 r1 mapping audit).
    wire session_rst /* synthesis syn_keep=1 */ = rst || session_reset;
    wire [7:0] data_byte;
    wire [3:0] save_r, save_b;
    wire [27:0] engine_debug;
    la16_usb_ls_engine #(.ROM_FILE(ROM_FILE)) u_host (
        .usbclk(clk), .usb_ce(ce), .usbrst_n(~rst), .usb_dp(usb_dp), .usb_dm(usb_dm), .usb_oe(),
        .ukprdy(ready), .ukpstb(strobe), .ukpdat(data_byte), .save(save), .save_r(save_r), .save_b(save_b),
        .connected(connected), .conerr(conerr), .session_reset(session_reset),
        .packet_done(packet_done),.packet_good(packet_good),.packet_pid(packet_pid), .debug(engine_debug));
    usb_gamepad_reports u_reports (
        .clk(clk), .rst(session_rst), .ce(ce),
        .packet_done(packet_done),.packet_good(packet_good),.packet_pid(packet_pid), .connected(connected), .data_rdy(ready), .data_strobe(strobe),
        .data_byte(data_byte), .save(save), .save_r(save_r), .save_b(save_b),
        .report(report), .report_data(report_data), .online(online), .supported(supported),
        .identity(identity), .report_count(report_count));
    usb_gamepad_controls u_controls (.clk(clk), .rst(rst), .online(online), .report(report),
        .report_data(report_data), .buttons(buttons));
    // Registered diagnostic snapshot keeps ROM/state decode off the AHB path.
    // [31:22] PC, [21:12] return PC, [11:8] state, [7:6] D+/D-,
    // [5:4] TX enable/NAK, [3:0] link status (ROM currently below 1024 nibbles).
    always @(posedge clk) begin
        if (rst) status <= 0;
        else status <= {engine_debug, supported, conerr, connected, online};
    end
endmodule
`default_nettype wire
