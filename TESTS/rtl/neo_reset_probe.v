// Standalone reset distribution experiment. No CPU, DDR, USB, SD or GPU.
// A failure here would narrow the investigation; a pass cannot clear the GPU.
`default_nettype none
module neo_reset_probe_core #(
    parameter BASE_WIDTH=512
) (
    input wire clk, resetn,
    output wire [3:0] reset_copies,
    output wire [1:0] reference_reset,
    output wire [3:0] mismatch_seen,
    output wire [31:0] mismatch_cycles,
    output wire [63:0] signatures
);
    reg [1:0] mrst /* synthesis syn_preserve=1 */ = 0;
    reg [3:0] copies /* synthesis syn_preserve=1 */ = 0;
    reg [3:0] seen=0;
    reg [31:0] error_count=0;
    assign reset_copies=copies;
    assign mismatch_seen=seen;
    assign mismatch_cycles=error_count;
    always @(posedge clk or negedge resetn)
        if(!resetn)mrst<=0;else mrst<={mrst[0],1'b1};
    always @(posedge clk or negedge resetn)
        if(!resetn)copies<=0;else copies<={4{mrst[0]}};
    assign reference_reset=mrst;
    // The monitor is deliberately independent of the reset copies under test.
    // Keep errors across internal reset cycles; reload clears the observation.
    always @(posedge clk)begin
        if(reset_copies!={4{mrst[1]}})begin
            seen<=seen | (reset_copies^{4{mrst[1]}});
            if(error_count!=32'hffffffff)error_count<=error_count+1'b1;
        end
    end
    genvar i;
    generate for(i=0;i<4;i=i+1)begin: banks
        localparam WIDTH=BASE_WIDTH<<i;
        reg [WIDTH-1:0] state /* synthesis syn_preserve=1 */;
        always @(posedge clk)begin
            if(!reset_copies[i])state<={{(WIDTH-1){1'b0}},1'b1};
            else state<={state[WIDTH-2:0],state[WIDTH-1]^state[WIDTH-3]^state[WIDTH-7]^state[WIDTH-8]};
        end
        assign signatures[i*16+:16]={state[WIDTH-1-:8],state[7:0]};
    end endgenerate
endmodule

module neo_reset_probe(input wire clk, output wire uart_tx, led_n);
    // 50 MHz reference only. Internal assertion lasts 256 cycles every 2^24
    // clocks. It tests repeated reset release without any PLL/DDR dependency.
    reg [23:0] ticks=0;
    reg [31:0] epoch=0;
    always @(posedge clk)begin
        ticks<=ticks+1'b1;
        if(&ticks)epoch<=epoch+1'b1;
    end
    wire resetn=|ticks[23:8];
    wire [3:0] reset_copies, mismatch_seen;
    wire [1:0] reference_reset;
    wire [31:0] mismatch_cycles;
    wire [63:0] signatures;
    neo_reset_probe_core u_probe(.clk(clk),.resetn(resetn),.reset_copies(reset_copies),
        .reference_reset(reference_reset),.mismatch_seen(mismatch_seen),
        .mismatch_cycles(mismatch_cycles),.signatures(signatures));
    assign led_n=!(|mismatch_seen);
    // Atomic ASCII snapshot: R + 40 hexadecimal digits + LF, at 2 Mbaud.
    // The word 0x5251 identifies this standalone diagnostic, version 1.
    reg [159:0] snapshot=0;
    reg [5:0] position=0;
    reg sending=0;
    reg [7:0] byte_data;
    wire ready;
    wire [3:0] digit=snapshot[159:156];
    always @*begin
        if(position==0)byte_data="R";
        else if(position==41)byte_data=8'h0a;
        else byte_data=(digit<10 ? "0":"a"-10)+digit;
    end
    // Recover telemetry after every internal reset, rather than relying on
    // a single 320 ns initialization window just after SRAM configuration.
    // This reset is independent of the four routing copies under test.
    uart_tx #(.DIV_WIDTH(16)) u_uart(.clk(clk),.rst(!resetn),
        .clk_div(16'd25),.data(byte_data),.valid(sending),.ready(ready),.tx(uart_tx));
    always @(posedge clk)begin
        if(!resetn)begin sending<=0;position<=0;snapshot<=0;end
        else if(!sending)begin
            if(ticks[19:0]==20'h80000)begin
                snapshot<={16'h5251,mismatch_seen,reset_copies,6'b0,reference_reset,
                           epoch,mismatch_cycles,signatures};
                sending<=1;position<=0;
            end
        end else if(ready)begin
            if(position==41)sending<=0;
            else begin
                position<=position+1'b1;
                if(position!=0)snapshot<={snapshot[155:0],4'b0};
            end
        end
    end
endmodule
`default_nettype wire
