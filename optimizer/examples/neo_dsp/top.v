// Compile-only hard-resource probe. Explicit DSP because current Yosys
// synth_gowin does not automatically map GW5A multiplication to a DSP.
module top(input wire clk, output reg led_n);
    reg [23:0] tick = 0;
    reg [31:0] random_bits = 32'h1928aef1;
    wire [23:0] product;
    MULT12X12 #(.AREG_CLK("CLK0"), .BREG_CLK("CLK0"),
                .PREG_CLK("CLK0"), .OREG_CLK("CLK0")) u_dsp (
        .A(random_bits[11:0]), .B(random_bits[23:12]),
        .CLK({1'b0,clk}), .CE(2'b01), .RESET(2'b00), .DOUT(product));
    reg [31:0] memory [0:1023];
    reg [31:0] read_value;
    always @(posedge clk) begin
        tick <= tick + 1'b1;
        random_bits <= {random_bits[30:0],random_bits[31]^random_bits[21]^random_bits[1]^random_bits[0]};
        memory[tick[9:0]] <= {random_bits[31:24],product};
        read_value <= memory[tick[19:10]];
        led_n <= tick[23] ^ (^read_value);
    end
endmodule
