// Qualify a PLL lock in the clock domain being released. Assertion is
// asynchronous (also works with a stopped clock); release is registered and
// follows two synchronizer clocks plus HOLD_CYCLES stable clocks.
module usb_reset_release #(
    parameter HOLD_CYCLES = 1024
)(
    input wire clk,
    input wire locked,
    output reg reset = 1'b1
);
    localparam CW = HOLD_CYCLES <= 1 ? 1 : $clog2(HOLD_CYCLES);
    (* syn_preserve = 1 *) reg [1:0] lock_sync = 0;
    reg [CW-1:0] count = 0;
    always @(posedge clk or negedge locked) begin
        if (!locked) begin
            lock_sync <= 0;
            count <= 0;
            reset <= 1;
        end else begin
            lock_sync <= {lock_sync[0],1'b1};
            if (!lock_sync[1]) begin
                count <= 0;
                reset <= 1;
            end else if (reset) begin
                if (count == HOLD_CYCLES-1) reset <= 0;
                else count <= count+1'b1;
            end
        end
    end
endmodule
