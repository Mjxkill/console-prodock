// One UI-clock stage between the native DDR tag decoder and GPU consumers.
// There is no backpressure on DDR responses: accept one 256-bit beat each
// cycle, including consecutive beats. Only validity needs a reset; payload
// is private until VALID. This is not a clock-domain crossing.
`default_nettype none
module neo_gpu_response (
    input wire clk, resetn,
    input wire in_valid,
    input wire [255:0] in_data,
    output reg out_valid = 0,
    output reg [255:0] out_data
);
    reg [1:0] released /* synthesis syn_preserve=1 */ = 0;
    always @(posedge clk or negedge resetn)
        if (!resetn) begin released <= 0; out_valid <= 0; end
        else begin
            released <= {released[0], 1'b1};
            out_valid <= released[1] && in_valid;
        end
    always @(posedge clk) out_data <= in_data;
endmodule
`default_nettype wire
