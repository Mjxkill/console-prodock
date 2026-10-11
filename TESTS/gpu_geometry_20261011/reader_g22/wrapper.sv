// G3 line compositor: 16 indexed surfaces, 16 in-flight native DDR reads,
// 32 pixels merged per cycle. Descriptor commits and the palette are external.
// L11: a layer may instead be a tile map. gpu_tile_row then supplies the
// source words of the line; clipping, alignment, masks, colour key, sprites
// and priorities are those of a surface layer, which keeps its cycle count.
`default_nettype none
module gpu_line_reader_equiv #(parameter WIDTH=800, HEIGHT=480) (
    input wire clk, resetn, start, layers, config_bank, sprites,
    input wire clear_maxima,
    input wire [31:0] base,
    input wire [8:0] line_y,
    output wire busy,
    output reg done,
    output wire [7:0] config_address,
    input wire [31:0] config_data,
    output wire fetch_valid,
    output wire [28:0] fetch_addr,
    input wire fetch_ready,
    input wire [255:0] fetch_data,
    input wire fetch_data_valid,
    output wire block_valid,
    output wire [4:0] block_index,
    output wire [255:0] block_data,
    output wire [31:0] block_coverage,
    output reg [31:0] max_cycles, invalid_layers,
    output wire [3:0] sprite_head_layer,
    input wire [6:0] sprite_head_index,
    output reg [5:0] sprite_index,
    input wire [63:0] sprite_metadata,
    output reg [10:0] sprite_row_address,
    input wire [255:0] sprite_row_data,
    output reg [31:0] max_sprites,max_sprite_pixels
);
    wire [0:0] ref_busy;
    wire [0:0] ref_done;
    wire [7:0] ref_config_address;
    wire [0:0] ref_fetch_valid;
    wire [28:0] ref_fetch_addr;
    wire [0:0] ref_block_valid;
    wire [4:0] ref_block_index;
    wire [255:0] ref_block_data;
    wire [31:0] ref_block_coverage;
    wire [31:0] ref_max_cycles;
    wire [31:0] ref_invalid_layers;
    wire [3:0] ref_sprite_head_layer;
    wire [5:0] ref_sprite_index;
    wire [10:0] ref_sprite_row_address;
    wire [31:0] ref_max_sprites;
    wire [31:0] ref_max_sprite_pixels;
    gpu_line_reader #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) u_gpu_line_reader (.clk(clk), .resetn(resetn), .start(start), .layers(layers), .config_bank(config_bank), .sprites(sprites), .clear_maxima(clear_maxima), .base(base), .line_y(line_y), .config_data(config_data), .fetch_ready(fetch_ready), .fetch_data(fetch_data), .fetch_data_valid(fetch_data_valid), .sprite_head_index(sprite_head_index), .sprite_metadata(sprite_metadata), .sprite_row_data(sprite_row_data), .busy(busy), .done(done), .config_address(config_address), .fetch_valid(fetch_valid), .fetch_addr(fetch_addr), .block_valid(block_valid), .block_index(block_index), .block_data(block_data), .block_coverage(block_coverage), .max_cycles(max_cycles), .invalid_layers(invalid_layers), .sprite_head_layer(sprite_head_layer), .sprite_index(sprite_index), .sprite_row_address(sprite_row_address), .max_sprites(max_sprites), .max_sprite_pixels(max_sprite_pixels));
    gpu_line_reader_reference #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) u_gpu_line_reader_reference (.clk(clk), .resetn(resetn), .start(start), .layers(layers), .config_bank(config_bank), .sprites(sprites), .clear_maxima(clear_maxima), .base(base), .line_y(line_y), .config_data(config_data), .fetch_ready(fetch_ready), .fetch_data(fetch_data), .fetch_data_valid(fetch_data_valid), .sprite_head_index(sprite_head_index), .sprite_metadata(sprite_metadata), .sprite_row_data(sprite_row_data), .busy(ref_busy), .done(ref_done), .config_address(ref_config_address), .fetch_valid(ref_fetch_valid), .fetch_addr(ref_fetch_addr), .block_valid(ref_block_valid), .block_index(ref_block_index), .block_data(ref_block_data), .block_coverage(ref_block_coverage), .max_cycles(ref_max_cycles), .invalid_layers(ref_invalid_layers), .sprite_head_layer(ref_sprite_head_layer), .sprite_index(ref_sprite_index), .sprite_row_address(ref_sprite_row_address), .max_sprites(ref_max_sprites), .max_sprite_pixels(ref_max_sprite_pixels));
    wire [31:0] elapsed=u_gpu_line_reader.elapsed;
    integer compared_cycles=0;
    always @(posedge clk) if(resetn)begin
        compared_cycles<=compared_cycles+1;
        if (busy !== ref_busy) $fatal(1,"Reader busy mismatch at %0d: current=%h reference=%h",compared_cycles,busy,ref_busy);
        if (done !== ref_done) $fatal(1,"Reader done mismatch at %0d: current=%h reference=%h",compared_cycles,done,ref_done);
        if (config_address !== ref_config_address) $fatal(1,"Reader config_address mismatch at %0d: current=%h reference=%h",compared_cycles,config_address,ref_config_address);
        if (fetch_valid !== ref_fetch_valid) $fatal(1,"Reader fetch_valid mismatch at %0d: current=%h reference=%h",compared_cycles,fetch_valid,ref_fetch_valid);
        if (fetch_addr !== ref_fetch_addr) $fatal(1,"Reader fetch_addr mismatch at %0d: current=%h reference=%h",compared_cycles,fetch_addr,ref_fetch_addr);
        if (block_valid !== ref_block_valid) $fatal(1,"Reader block_valid mismatch at %0d: current=%h reference=%h",compared_cycles,block_valid,ref_block_valid);
        if (max_cycles !== ref_max_cycles) $fatal(1,"Reader max_cycles mismatch at %0d: current=%h reference=%h",compared_cycles,max_cycles,ref_max_cycles);
        if (invalid_layers !== ref_invalid_layers) $fatal(1,"Reader invalid_layers mismatch at %0d: current=%h reference=%h",compared_cycles,invalid_layers,ref_invalid_layers);
        if (sprite_head_layer !== ref_sprite_head_layer) $fatal(1,"Reader sprite_head_layer mismatch at %0d: current=%h reference=%h",compared_cycles,sprite_head_layer,ref_sprite_head_layer);
        if (sprite_index !== ref_sprite_index) $fatal(1,"Reader sprite_index mismatch at %0d: current=%h reference=%h",compared_cycles,sprite_index,ref_sprite_index);
        if (sprite_row_address !== ref_sprite_row_address) $fatal(1,"Reader sprite_row_address mismatch at %0d: current=%h reference=%h",compared_cycles,sprite_row_address,ref_sprite_row_address);
        if (max_sprites !== ref_max_sprites) $fatal(1,"Reader max_sprites mismatch at %0d: current=%h reference=%h",compared_cycles,max_sprites,ref_max_sprites);
        if (max_sprite_pixels !== ref_max_sprite_pixels) $fatal(1,"Reader max_sprite_pixels mismatch at %0d: current=%h reference=%h",compared_cycles,max_sprite_pixels,ref_max_sprite_pixels);
        if(block_valid && {block_index,block_data,block_coverage} !==
            {ref_block_index,ref_block_data,ref_block_coverage})
            $fatal(1,"Reader block mismatch at %0d",compared_cycles);
    end
    final $display("READER EQUIVALENCE: %0d cycles compared",compared_cycles);
endmodule
`default_nettype wire
