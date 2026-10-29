// Adapt measured HID fields to the existing PMOD button register.
// Settings survive release/disconnect; momentary controls are released on loss.
`default_nettype none
module usb_gamepad_controls (
    input wire clk, rst, online, report,
    input wire [63:0] report_data,
    output wire [7:0] buttons
);
    wire [7:0] x = report_data[7:0], y = report_data[15:8];
    wire [9:0] keys = report_data[53:44];
    reg [9:0] keys_q;
    reg armed, start, select_key, left, right;
    reg source_ext, falling;
    reg [1:0] mode;
    assign buttons = {source_ext, start, right, falling, left,
                      mode == 2, mode == 1, select_key};
    always @(posedge clk) begin
        if (rst) begin
            keys_q <= 0; armed <= 0; start <= 0; select_key <= 0;
            left <= 0; right <= 0; source_ext <= 0; falling <= 0; mode <= 0;
        end else if (!online) begin
            keys_q <= 0; armed <= 0; start <= 0; select_key <= 0;
            left <= 0; right <= 0;
        end else if (report) begin
            keys_q <= keys;
            if (!armed) begin
                // Do not turn a button held during insertion into an action.
                if (keys == 0 && x >= 64 && x < 192 && y >= 64 && y < 192)
                    armed <= 1;
            end else begin
                start <= keys[9]; select_key <= keys[8];
                left <= x < 64; right <= x >= 192;
                if (keys[0] && !keys_q[0]) source_ext <= !source_ext;
                if (keys[1] && !keys_q[1]) mode <= mode == 2 ? 0 : mode + 1'b1;
                if (keys[2] && !keys_q[2]) falling <= !falling;
            end
        end
    end
endmodule
`default_nettype wire
