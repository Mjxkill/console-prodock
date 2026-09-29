// Bind alongside the real L11 reader in the pixel/DDR regression.
module gpu_reader_equiv #(parameter WIDTH=800,HEIGHT=480) (
    input wire  clk,
    input wire  resetn,
    input wire  start,
    input wire  layers,
    input wire  config_bank,
    input wire  sprites,
    input wire  clear_maxima,
    input wire [31:0] base,
    input wire [8:0] line_y,
    input wire  busy,
    input wire  done,
    input wire [7:0] config_address,
    input wire [31:0] config_data,
    input wire  fetch_valid,
    input wire [28:0] fetch_addr,
    input wire  fetch_ready,
    input wire [255:0] fetch_data,
    input wire  fetch_data_valid,
    input wire  block_valid,
    input wire [4:0] block_index,
    input wire [255:0] block_data,
    input wire [31:0] max_cycles,
    input wire [31:0] invalid_layers,
    input wire [3:0] sprite_head_layer,
    input wire [6:0] sprite_head_index,
    input wire [5:0] sprite_index,
    input wire [63:0] sprite_metadata,
    input wire [10:0] sprite_row_address,
    input wire [255:0] sprite_row_data,
    input wire [31:0] max_sprites,
    input wire [31:0] max_sprite_pixels
);
    wire  ref_busy;
    wire  ref_done;
    wire [7:0] ref_config_address;
    wire  ref_fetch_valid;
    wire [28:0] ref_fetch_addr;
    wire  ref_block_valid;
    wire [4:0] ref_block_index;
    wire [255:0] ref_block_data;
    wire [31:0] ref_max_cycles;
    wire [31:0] ref_invalid_layers;
    wire [3:0] ref_sprite_head_layer;
    wire [5:0] ref_sprite_index;
    wire [10:0] ref_sprite_row_address;
    wire [31:0] ref_max_sprites;
    wire [31:0] ref_max_sprite_pixels;
    gpu_line_reader_reference #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) reference (
        .clk(clk),
        .resetn(resetn),
        .start(start),
        .layers(layers),
        .config_bank(config_bank),
        .sprites(sprites),
        .clear_maxima(clear_maxima),
        .base(base),
        .line_y(line_y),
        .busy(ref_busy),
        .done(ref_done),
        .config_address(ref_config_address),
        .config_data(config_data),
        .fetch_valid(ref_fetch_valid),
        .fetch_addr(ref_fetch_addr),
        .fetch_ready(fetch_ready),
        .fetch_data(fetch_data),
        .fetch_data_valid(fetch_data_valid),
        .block_valid(ref_block_valid),
        .block_index(ref_block_index),
        .block_data(ref_block_data),
        .max_cycles(ref_max_cycles),
        .invalid_layers(ref_invalid_layers),
        .sprite_head_layer(ref_sprite_head_layer),
        .sprite_head_index(sprite_head_index),
        .sprite_index(ref_sprite_index),
        .sprite_metadata(sprite_metadata),
        .sprite_row_address(ref_sprite_row_address),
        .sprite_row_data(sprite_row_data),
        .max_sprites(ref_max_sprites),
        .max_sprite_pixels(ref_max_sprite_pixels)
    );
    integer cycles=0,words=0,requests=0;
    always @(posedge clk) if(resetn) begin
        cycles++;
        if(busy !== ref_busy) $fatal(1,"Reader equivalence: busy");
        if(done !== ref_done) $fatal(1,"Reader equivalence: done");
        if(config_address !== ref_config_address) $fatal(1,"Reader equivalence: config_address");
        if(fetch_valid !== ref_fetch_valid) $fatal(1,"Reader equivalence: fetch_valid");
        if(block_valid !== ref_block_valid) $fatal(1,"Reader equivalence: block_valid");
        if(max_cycles !== ref_max_cycles) $fatal(1,"Reader equivalence: max_cycles");
        if(invalid_layers !== ref_invalid_layers) $fatal(1,"Reader equivalence: invalid_layers");
        if(sprite_head_layer !== ref_sprite_head_layer) $fatal(1,"Reader equivalence: sprite_head_layer");
        if(sprite_index !== ref_sprite_index) $fatal(1,"Reader equivalence: sprite_index");
        if(sprite_row_address !== ref_sprite_row_address) $fatal(1,"Reader equivalence: sprite_row_address");
        if(max_sprites !== ref_max_sprites) $fatal(1,"Reader equivalence: max_sprites");
        if(max_sprite_pixels !== ref_max_sprite_pixels) $fatal(1,"Reader equivalence: max_sprite_pixels");
        if(fetch_valid) begin
            requests++;
            if(fetch_addr !== ref_fetch_addr) $fatal(1,"Reader equivalence: DDR address");
        end
        if(block_valid) begin
            words++;
            if({block_index,block_data} !== {ref_block_index,ref_block_data}) $fatal(1,"Reader equivalence: pixels");
        end
    end
    final $display("PASS reader equivalence: %0d cycles, %0d valid requests, %0d blocks",cycles,requests,words);
endmodule
bind gpu_line_reader gpu_reader_equiv #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) proof (.*);
