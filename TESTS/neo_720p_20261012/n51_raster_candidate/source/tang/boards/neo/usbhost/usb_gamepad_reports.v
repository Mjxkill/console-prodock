// Only complete 8-byte input reports from the measured 081f:e401 are accepted.
`default_nettype none
module usb_gamepad_reports #(
    parameter integer TIMEOUT_TICKS = 6000000 // 500 ms at the 12 MHz enable
) (
    input wire clk, rst, ce,
    input wire packet_done,packet_good,
    input wire [7:0] packet_pid,
    input wire connected, data_rdy, data_strobe,
    input wire [7:0] data_byte,
    input wire save,
    input wire [3:0] save_r, save_b,
    output reg report,
    output reg [63:0] report_data,
    output reg online,
    output wire supported,
    output wire [31:0] identity,
    output reg [31:0] report_count
);
    reg [7:0] data [0:7];
    reg [63:0] pending_data;
    reg pending_valid,last_pid_valid;
    reg [7:0] last_pid;
    reg [7:0] descriptor [0:6];
    reg [3:0] count;
    reg ready_q, strobe_q, connected_q;
    reg [$clog2(TIMEOUT_TICKS + 1)-1:0] age;
    localparam [$clog2(TIMEOUT_TICKS + 1)-1:0] LAST_TICK = TIMEOUT_TICKS - 1;
    assign identity = {descriptor[3], descriptor[2], descriptor[1], descriptor[0]};
    assign supported = identity == 32'he401081f && descriptor[4] == 8'd3;
    integer i;
    always @(posedge clk) begin
        report <= 1'b0;
        if (rst) begin
            count <= 0; ready_q <= 0; strobe_q <= 0; connected_q <= 0;
            online <= 0; age <= 0; report_data <= 0; report_count <= 0;
            pending_valid<=0;pending_data<=0;last_pid<=0;last_pid_valid<=0;
            for (i = 0; i < 8; i = i + 1) data[i] <= 0;
            for (i = 0; i < 7; i = i + 1) descriptor[i] <= 0;
        end else if (ce) begin
            ready_q <= data_rdy; strobe_q <= data_strobe; connected_q <= connected;
            if (!data_rdy) count <= 0;
            else if (data_strobe && !strobe_q) begin
                if (count < 8) data[count[2:0]] <= data_byte;
                if (count < 15) count <= count + 1'b1;
            end
            if (save && save_r < 7 && save_b < 8)
                descriptor[save_r[2:0]] <= data[save_b[2:0]];
            if (connected_q && !connected)
                for (i = 0; i < 7; i = i + 1) descriptor[i] <= 0;
            if (!data_rdy && ready_q) begin
                pending_data <= {data[7],data[6],data[5],data[4],data[3],data[2],data[1],data[0]};
                pending_valid <= count == 8;
            end
            if (packet_done) pending_valid<=0;
            if (!connected || !supported) begin
                online <= 0; age <= 0;last_pid_valid<=0;
            end else if (packet_done && packet_good && pending_valid &&
                         (!last_pid_valid || packet_pid != last_pid)) begin
                report_data <= pending_data;
                last_pid<=packet_pid;last_pid_valid<=1;
                report <= 1;
                report_count <= report_count + 1'b1;
                online <= 1; age <= 0;
            end else if (age == LAST_TICK) begin
                online <= 0;
            end else age <= age + 1'b1;
        end
    end
endmodule
`default_nettype wire
