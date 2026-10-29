// L13/L14/L15 RGB565 fragment engine. Ordered by the legacy command FIFO.
// Native DDR addresses are 32-bit words, bursts 256 bits. No new clock.
// See ARCHI/GPU_L13_L15_RGB_DEPTH.md for fixed-point and memory contracts.
`default_nettype none
module gpu_raster_equiv #(
    parameter WIDTH=800, HEIGHT=480
) (
    input wire clk, rst, start,
    input wire [255:0] command,
    output wire busy,
    output reg done,
    output reg [31:0] rejected, fragments, passed,
    output reg valid, write,
    output reg [28:0] addr,
    output reg [255:0] wr_data,
    output reg [31:0] wr_mask,
    input wire ready,
    input wire [255:0] rd_data,
    input wire rd_valid
);
    wire [0:0] ref_busy;
    wire [0:0] ref_done;
    wire [31:0] ref_rejected;
    wire [31:0] ref_fragments;
    wire [31:0] ref_passed;
    wire [0:0] ref_valid;
    wire [0:0] ref_write;
    wire [28:0] ref_addr;
    wire [255:0] ref_wr_data;
    wire [31:0] ref_wr_mask;
    gpu_raster #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) u_gpu_raster (.clk(clk), .rst(rst), .start(start), .command(command), .ready(ready), .rd_data(rd_data), .rd_valid(rd_valid), .busy(busy), .done(done), .rejected(rejected), .fragments(fragments), .passed(passed), .valid(valid), .write(write), .addr(addr), .wr_data(wr_data), .wr_mask(wr_mask));
    gpu_raster_reference #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) u_gpu_raster_reference (.clk(clk), .rst(rst), .start(start), .command(command), .ready(ready), .rd_data(rd_data), .rd_valid(rd_valid), .busy(ref_busy), .done(ref_done), .rejected(ref_rejected), .fragments(ref_fragments), .passed(ref_passed), .valid(ref_valid), .write(ref_write), .addr(ref_addr), .wr_data(ref_wr_data), .wr_mask(ref_wr_mask));
    integer compared_cycles=0;
    always @(posedge clk) if(!rst)begin
        compared_cycles<=compared_cycles+1;
        if ({busy,done,rejected,fragments,passed,valid,write,addr,wr_data,wr_mask} !== {ref_busy,ref_done,ref_rejected,ref_fragments,ref_passed,ref_valid,ref_write,ref_addr,ref_wr_data,ref_wr_mask}) $fatal(1,"Raster cycle mismatch at %0d",compared_cycles);
    end
    final $display("RASTER EQUIVALENCE: %0d cycles compared",compared_cycles);
endmodule
`default_nettype wire
