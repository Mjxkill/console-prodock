// USB2 CDC and BL616 maintenance input -> AE350 UART2, 115200 8N1.
// All byte queues use phy_clk (60 MHz); serial inputs have 2-FF receivers.
// USB backpressure reserves room for the packet FIFO's delayed valid pulse.
// BL616 has no flow control: host pastes are bounded to 4096 bytes, then drain.
`default_nettype none
module neo_console_input #(
    parameter integer DEBUG_LOG2 = 12,
    parameter [15:0] DEBUG_DIV = 16'd30
) (
    input wire clk, reset, debug_rx, cpu_tx,
    input wire usb_valid,
    input wire [7:0] usb_data,
    output wire usb_ready, cpu_rx, cpu_valid,
    output wire [7:0] cpu_data,
    output reg overflow
);
    localparam DEPTH = 1 << DEBUG_LOG2;
    wire [7:0] debug_data;
    wire debug_valid, bridge_ready;
    reg [7:0] fifo [0:DEPTH-1];
    reg [DEBUG_LOG2-1:0] wp, rp;
    reg [DEBUG_LOG2:0] count;
    reg [7:0] head;
    reg head_valid;
    // USB valid can arrive after ready drops. It always takes priority over
    // a BL616 byte, which stays pending until the bridge has space again.
    wire debug_take = !reset && bridge_ready && head_valid && !usb_valid;
    wire pop = !reset && count != 0 && (!head_valid || debug_take);
    wire push = !reset && debug_valid && count != (DEBUG_LOG2+1)'(DEPTH);
    assign usb_ready = bridge_ready;

    uart_rx #(.DIV_WIDTH(16)) u_debug_rx(.clk(clk),.rst(reset),
        .clk_div(DEBUG_DIV),.rx(debug_rx),.data(debug_data),.valid(debug_valid));
    uart2_to_ep2 u_bridge(.phy_clk(clk),.reset(reset),.uart2_txd(cpu_tx),
        .uart2_rxd(cpu_rx),.uart_rx_data_val(cpu_valid),.uart_rx_data(cpu_data),
        .ep2_rx_dval(usb_valid || debug_take),
        .ep2_rx_data(usb_valid ? usb_data:head),.ep2_rx_rdy(bridge_ready));

    // Registered RAM read; never read and write the same full FIFO slot.
    // RAM is deliberately unreset: pointers/valids invalidate every old byte.
    always @(posedge clk) begin
        if (push) fifo[wp] <= debug_data;
        if (pop) head <= fifo[rp];
    end
    always @(posedge clk or posedge reset) begin
        if (reset) begin
            wp<=0;rp<=0;count<=0;head_valid<=0;overflow<=0;
        end else begin
            if (push) wp<=wp+1'b1;
            if (pop) begin rp<=rp+1'b1;head_valid<=1;end
            else if (debug_take) head_valid<=0;
            case ({push,pop})
                2'b10: count<=count+1'b1;
                2'b01: count<=count-1'b1;
                default: ;
            endcase
            if (debug_valid && !push) overflow<=1;
        end
    end
endmodule
`default_nettype wire
