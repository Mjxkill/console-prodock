// G2 AHB command queue + rasterizer + native DDR3 DMA, at 0xE9001000.
// A command contains eight words. Completion counter is the software fence;
// BUSY is a synchronized status indication, not a substitute for that fence.
`default_nettype none
module gpu_accel #(
    parameter FONT_FILE = "rtl/video/font8x16.hex"
) (
    input wire hclk, hresetn, hsel, hwrite,
    input wire [31:0] haddr, hwdata,
    input wire [1:0] htrans,
    output reg [31:0] hrdata,
    output wire hready,
    input wire mem_clk,
    output wire valid, write,
    output wire [28:0] addr,
    output wire [255:0] wr_data,
    output wire [31:0] wr_mask,
    input wire ready,
    input wire [255:0] rd_data,
    input wire rd_valid,
    output wire [255:0] debug_state,
    output wire debug_accept
);
    wire [31:0] ref_hrdata;
    wire [0:0] ref_hready;
    wire [0:0] ref_valid;
    wire [0:0] ref_write;
    wire [28:0] ref_addr;
    wire [255:0] ref_wr_data;
    wire [31:0] ref_wr_mask;
    gpu_accel_current #(.FONT_FILE(FONT_FILE)) u_current (.hclk(hclk), .hresetn(hresetn), .hsel(hsel), .hwrite(hwrite), .haddr(haddr), .hwdata(hwdata), .htrans(htrans), .mem_clk(mem_clk), .ready(ready), .rd_data(rd_data), .rd_valid(rd_valid), .hrdata(hrdata), .hready(hready), .valid(valid), .write(write), .addr(addr), .wr_data(wr_data), .wr_mask(wr_mask));
    gpu_accel_reference #(.FONT_FILE(FONT_FILE)) u_reference (.hclk(hclk), .hresetn(hresetn), .hsel(hsel), .hwrite(hwrite), .haddr(haddr), .hwdata(hwdata), .htrans(htrans), .mem_clk(mem_clk), .ready(ready), .rd_data(rd_data), .rd_valid(rd_valid), .hrdata(ref_hrdata), .hready(ref_hready), .valid(ref_valid), .write(ref_write), .addr(ref_addr), .wr_data(ref_wr_data), .wr_mask(ref_wr_mask));

    integer ahb_cycles=0,ddr_cycles=0,transactions=0,self_stalls=0;
    reg [255:0] previous_raster_command;
    always @(posedge mem_clk) previous_raster_command<=u_current.ext_command;
    always @(posedge hclk) if(hresetn)begin
        ahb_cycles<=ahb_cycles+1;
        if(!hready)self_stalls<=self_stalls+1;
        if({hready,hrdata} !== {ref_hready,ref_hrdata})
            $fatal(1,"AHB integration mismatch at %0d",ahb_cycles);
    end
    always @(posedge mem_clk) if(u_current.mrst[1])begin
        ddr_cycles<=ddr_cycles+1;
        if(!u_current.u_v1.state[0] &&
           {u_current.u_v1.captured_command,u_current.u_v1.mesh_vertex_end,u_current.u_v1.mesh_face_end} !==
           {u_reference.u_v1.captured_command,u_reference.u_v1.mesh_vertex_end,u_reference.u_v1.mesh_face_end})
            $fatal(1,"Prefetched command changed during a busy geometry cycle");
        if(!$onehot(u_current.u_raster.state))
            $fatal(1,"Raster state is not one-hot");
        if(!$onehot0({u_current.u_blitter.rectangle_opcode,u_current.u_blitter.line_opcode,
                      u_current.u_blitter.circle_opcode,u_current.u_blitter.triangle_opcode,
                      u_current.u_blitter.affine_setup_opcode,u_current.u_blitter.extended_opcode}))
            $fatal(1,"Blitter command classes overlap");
        if(u_current.u_raster.start && u_current.ext_command !== previous_raster_command)
            $fatal(1,"Raster command changed without a predecode cycle");
        if(valid !== ref_valid)$fatal(1,"DDR request cycle mismatch at %0d",ddr_cycles);
        if(valid)begin
            if({write,addr} !== {ref_write,ref_addr})
                $fatal(1,"DDR request mismatch at %0d",ddr_cycles);
            if(write && {wr_data,wr_mask} !== {ref_wr_data,ref_wr_mask})
                $fatal(1,"DDR write payload mismatch at %0d",ddr_cycles);
            if(ready)transactions<=transactions+1;
        end
        // v1_valid is the shared extended-engine transaction buffer, so it
        // may overlap the raster request that fills it. Compare the two
        // actual engine requests, and separately the two native DMA owners.
        if(!$onehot0({u_current.legacy_valid,u_current.raster_valid,u_current.v1_request}) ||
           !$onehot0({u_current.legacy_valid,u_current.v1_valid}))
            $fatal(1,"Concurrent graphics engines at %0d",ddr_cycles);
    end
    final $display("ACCEL EQUIVALENCE: AHB=%0d DDR=%0d transactions=%0d",ahb_cycles,ddr_cycles,transactions);
    final $display("ACCEL SELF STALLS: %0d",self_stalls);
endmodule
`default_nettype wire
