`timescale 1ns/1ps
module usb_gamepad_host_tb (
    input wire rst, dev_drive, dev_dp, dev_dm,
    output wire dp, dm, host_oe,
    output wire [7:0] buttons,
    output wire [31:0] status, identity, report_count,
    output wire [63:0] report_data
);
    reg clk = 0;
    always #6.25 clk = ~clk;
    tri usb_dp, usb_dm;
    pulldown(usb_dp);
    pullup(usb_dm); // low-speed device attached
    assign usb_dp = dev_drive ? dev_dp : 1'bz;
    assign usb_dm = dev_drive ? dev_dm : 1'bz;
    assign dp = usb_dp;
    assign dm = usb_dm;
    usb_gamepad #(.ROM_FILE("usb_hid_host_rom.hex")) u (
        .clk(clk), .rst(rst), .usb_dp(usb_dp), .usb_dm(usb_dm),
        .buttons(buttons), .status(status), .identity(identity),
        .report_count(report_count), .report_data(report_data));
    assign host_oe = u.u_host.usb_oe;

    // The ROM pipeline must preserve exactly the instruction seen at CE.
    // Two CE pulses are separated by at least six bus80 cycles.
    integer cycle_number = 0, last_enable = 0;
    reg seen_enable = 0, previous_reset = 1, previous_enable = 0;
    reg [13:0] previous_pc;
    reg [23:0] previous_watchdog;
    reg [3:0] previous_instruction;
    always @(posedge clk) begin
        cycle_number <= cycle_number + 1;
        if (rst) seen_enable <= 0;
        else if (u.ce) begin
            if (seen_enable && cycle_number - last_enable < 6)
                $fatal(1, "gamepad CE separation below six cycles");
            seen_enable <= 1;
            last_enable <= cycle_number;
        end
        if (!previous_reset && !previous_enable) begin
            if (u.u_host.pc !== previous_pc || u.u_host.conct !== previous_watchdog ||
                u.u_host.rom_inst !== previous_instruction)
                $fatal(1, "ROM/PC/watchdog changed outside the common CE");
        end
        if (!rst && !u.session_reset && u.ce && u.u_host.inst !== u.u_host.rom_inst)
            $fatal(1, "Pipelined instruction differs at the consumer CE");
        previous_reset <= rst || u.session_reset;
        previous_enable <= u.ce;
        previous_pc <= u.u_host.pc;
        previous_watchdog <= u.u_host.conct;
        previous_instruction <= u.u_host.rom_inst;
    end
endmodule
