// Exercise LUT/FF, a signed DSP multiplier and synchronous block RAM.
// Compile-only benchmark: does not access DDR, SD, AE350 or USB.
module top(input wire clk, output reg led_n);
    reg [23:0] tick = 0;
    reg [31:0] random_bits = 32'h1928aef1;
    reg signed [17:0] a, b;
    reg signed [35:0] product;
    reg [31:0] memory [0:1023];
    reg [31:0] read_value;
    always @(posedge clk) begin
        tick <= tick + 1'b1;
        random_bits <= {random_bits[30:0],random_bits[31]^random_bits[21]^random_bits[1]^random_bits[0]};
        a <= random_bits[17:0];
        b <= random_bits[31:14];
        product <= a * b;
        memory[tick[9:0]] <= product[31:0];
        read_value <= memory[tick[19:10]];
        led_n <= tick[23] ^ (^read_value);
    end
endmodule
