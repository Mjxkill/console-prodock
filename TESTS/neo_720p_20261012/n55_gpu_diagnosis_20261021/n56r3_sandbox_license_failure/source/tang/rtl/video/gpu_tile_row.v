// L11 tile layers: builds one line of a tile map as 32-pixel words, in the
// same word/lane layout as a DDR surface row. gpu_line_reader then merges
// these words with its unchanged alignment, mask and colour-key pipeline.
//
// Map: 16-bit entries, row-major, width and height powers of two.
//   entry[12:0] tile index, [13] reserved, [14] flip X, [15] flip Y.
// Atlas: tile i occupies T*T bytes at atlas_base + i*T*T, rows of T bytes.
// Both bases are 32-byte aligned, so a tile row never straddles a DDR burst
// and a map burst always holds 16 consecutive entries of one map row.
//
// Requests: first the map bursts of this line, then one burst per tile, in
// screen order. Responses return in request order (ddr_gpu_arb tags).
//
// fetch_valid is a register that is zero outside a tile row: the line
// reader ORs it with its own request register. The request valid that feeds
// the DDR arbitration keeps the logic depth it had before tile layers.
`default_nettype none
module gpu_tile_row (
    input wire clk, resetn,
    input wire start,                  // one cycle; parameters stay stable while busy
    output wire busy,
    input wire [31:0] map_base, atlas_base,
    input wire [15:0] first_x,         // map pixel x of word 0, multiple of 32
    input wire [15:0] source_y,        // map pixel y of this line
    input wire [3:0] map_w_log2, map_h_log2,
    input wire [1:0] tile_code,        // 0: 8x8, 1: 16x16, 2: 32x32
    input wire [5:0] words,            // 32-pixel words to produce, 1..32
    output wire fetch_valid,
    output reg [28:0] fetch_addr,
    input wire fetch_ready,
    input wire [255:0] fetch_data,
    input wire fetch_data_valid,
    output reg word_valid,
    output reg [255:0] word_data
);
    localparam IDLE=0, ROW=1, BASE=2, RUN=3;
    reg [1:0] state=IDLE;
    assign busy=state!=IDLE;

    // ---- Line constants, registered over ROW and BASE ----
    wire [2:0] tile_log2=3'd3+{1'b0,tile_code};
    wire [15:0] column0=first_x>>tile_log2;
    wire [15:0] map_row_index=source_y>>tile_log2;
    wire [15:0] width_mask=(16'd1<<map_w_log2)-16'd1;
    wire [15:0] height_mask=(16'd1<<map_h_log2)-16'd1;
    reg [4:0] tile_row;                // row inside the tile, before flip Y
    reg [4:0] tile_last;               // T-1
    reg [3:0] first_lane;              // entry lane of tile 0 in its map burst
    reg [7:0] map_burst, map_burst_mask;
    reg [31:0] row_offset, row_base;
    reg [7:0] tiles;                   // words * tiles per word, at most 128
    reg [3:0] map_bursts;              // at most 9
    reg [1:0] slot_last;               // tiles per word - 1

    // ---- Map bursts of this line ----
    reg [255:0] map_words [0:15]; // block RAM: this device has no distributed RAM
    reg [255:0] map_word;
    reg [3:0] map_issued, map_received;
    // Returned data is registered here first: the 256-bit bus then only
    // has to reach this one register from the line reader.
    reg [255:0] returned_data;
    reg returned_valid=0;
    always @(posedge clk) begin returned_data<=fetch_data;returned_valid<=resetn && fetch_data_valid;end
    wire map_response=returned_valid && map_received!=map_bursts;
    wire tile_response=returned_valid && map_received==map_bursts;
    always @(posedge clk) if(state==RUN && map_response) map_words[map_received]<=returned_data;

    // ---- Tile request generator: never stalls, launches are credit-limited ----
    reg [7:0] launched;
    reg [3:0] occupancy;               // launched, not yet taken by the issuer
    wire [7:0] entry_index={4'd0,first_lane}+launched;
    wire launch=state==RUN && launched!=tiles && map_received>entry_index[7:4] && occupancy<4'd8;
    reg g1_valid=0,g2_valid=0,g3_valid=0,g4_valid=0;
    reg [3:0] g1_lane;
    reg [1:0] g1_slot,g2_slot,g3_slot,g4_slot;
    reg [1:0] slot;
    reg [15:0] g2_entry;
    reg [23:0] g3_offset;
    reg g3_flip,g4_flip;
    reg [31:0] g4_address;
    wire [4:0] entry_row=g2_entry[15] ? tile_last-tile_row : tile_row;
    always @(posedge clk) begin
        map_word<=map_words[entry_index[7:4]];
        g1_lane<=entry_index[3:0];g1_slot<=slot;
        g2_entry<=map_word[g1_lane*16+:16];g2_slot<=g1_slot;
        case(tile_code)
            2'd0:g3_offset<={5'd0,g2_entry[12:0],6'd0}+{19'd0,entry_row[2:0],3'd0};
            2'd1:g3_offset<={3'd0,g2_entry[12:0],8'd0}+{16'd0,entry_row[3:0],4'd0};
            default:g3_offset<={1'd0,g2_entry[12:0],10'd0}+{14'd0,entry_row,5'd0};
        endcase
        g3_flip<=g2_entry[14];g3_slot<=g2_slot;
        g4_address<=atlas_base+{8'd0,g3_offset};g4_flip<=g3_flip;g4_slot<=g3_slot;
    end

    // ---- Requests waiting for the DDR port, and metadata of pending reads ----
    reg [35:0] pending [0:7];          // [35:5] byte address, [4] flip X, [3:2] slot
    reg [2:0] pending_write, pending_read;
    reg [3:0] pending_count;
    wire [35:0] pending_head=pending[pending_read];
    reg [7:0] metadata [0:15];         // [7:3] lane offset in the burst, [2] flip X, [1:0] slot
    reg [3:0] metadata_write, metadata_read;
    reg [4:0] metadata_count;
    wire [7:0] metadata_head=metadata[metadata_read];
    // The next request waits in `staged`. The late DDR ready only enables
    // registers: no address is computed or selected behind it.
    reg request_valid=0;
    assign fetch_valid=request_valid;
    reg staged_valid=0,staged_map;
    reg [28:0] staged_addr;
    reg [7:0] staged_metadata;
    wire accept=request_valid && fetch_ready;
    wire port_free=!request_valid || accept;
    wire issue=state==RUN && port_free && staged_valid && (staged_map || !metadata_count[4]);
    wire issue_tile=issue && !staged_map;
    wire mapping=map_issued!=map_bursts;
    wire stage=state==RUN && (!staged_valid || issue) && (mapping || pending_count!=0);
    wire stage_tile=stage && !mapping;
    wire [31:0] map_address=row_base+{19'd0,map_burst,5'd0};
    always @(posedge clk) begin
        if(g4_valid) pending[pending_write]<={g4_address[30:0],g4_flip,g4_slot,2'd0};
        if(issue_tile) metadata[metadata_write]<=staged_metadata;
        if(stage) begin
            staged_map<=mapping;
            staged_addr<=mapping ? map_address[30:2] : {pending_head[35:10],3'b0};
            staged_metadata<={pending_head[9:5],pending_head[4:2]};
        end
    end

    // ---- Returned tile rows: select, mirror, place in the output word ----
    reg r1_valid=0,r2_valid=0;
    reg r1_flip;
    reg [1:0] r1_slot,r2_slot;
    reg [255:0] r1_data,r2_data,assembled;
    reg [5:0] emitted;
    wire [255:0] mirrored,placed;
    genvar lane;
    generate for(lane=0;lane<32;lane=lane+1) begin:lanes
        // Bytes above the tile width are never placed.
        assign mirrored[lane*8+:8]=
            tile_code==2'd0 ? r1_data[(lane<8 ? 7-lane : lane)*8+:8] :
            tile_code==2'd1 ? r1_data[(lane<16 ? 15-lane : lane)*8+:8] :
                              r1_data[(31-lane)*8+:8];
        wire selected=tile_code==2'd0 ? r2_slot==(lane>>3) :
                      tile_code==2'd1 ? r2_slot==(lane>>4) : 1'b1;
        wire [255:0] source=r2_data;
        assign placed[lane*8+:8]=!selected ? assembled[lane*8+:8] :
            tile_code==2'd0 ? source[(lane&7)*8+:8] :
            tile_code==2'd1 ? source[(lane&15)*8+:8] : source[lane*8+:8];
    end endgenerate
    // Wide data registers carry no reset; their valid bits do.
    always @(posedge clk) begin
        r1_data<=returned_data>>{metadata_head[7:6],6'd0};
        r1_flip<=metadata_head[2];r1_slot<=metadata_head[1:0];
        r2_data<=r1_flip ? mirrored : r1_data;r2_slot<=r1_slot;
        if(r2_valid) assembled<=placed;
        word_data<=placed;
    end

    always @(posedge clk) begin
        if(!resetn) begin
            state<=IDLE;word_valid<=0;staged_valid<=0;request_valid<=0;fetch_addr<=0;
            g1_valid<=0;g2_valid<=0;g3_valid<=0;g4_valid<=0;r1_valid<=0;r2_valid<=0;
            launched<=0;occupancy<=0;slot<=0;map_issued<=0;map_received<=0;
            pending_write<=0;pending_read<=0;pending_count<=0;
            metadata_write<=0;metadata_read<=0;metadata_count<=0;emitted<=0;
            tile_row<=0;tile_last<=0;first_lane<=0;map_burst<=0;map_burst_mask<=0;
            row_offset<=0;row_base<=0;tiles<=0;map_bursts<=0;slot_last<=0;
        end else begin
            g1_valid<=launch;g2_valid<=g1_valid;g3_valid<=g2_valid;g4_valid<=g3_valid;
            r1_valid<=tile_response;r2_valid<=r1_valid;
            word_valid<=r2_valid && r2_slot==slot_last;
            case(state)
                IDLE: if(start) begin
                    tile_last<=(5'd1<<tile_log2)-5'd1;
                    tile_row<=source_y[4:0]&((5'd1<<tile_log2)-5'd1);
                    first_lane<=column0[3:0];
                    map_burst_mask<=width_mask[11:4];
                    map_burst<=column0[11:4]&width_mask[11:4];
                    row_offset<={16'd0,map_row_index&height_mask}<<(map_w_log2+4'd1);
                    slot_last<=tile_code==2'd0 ? 2'd3 : tile_code==2'd1 ? 2'd1 : 2'd0;
                    tiles<=tile_code==2'd0 ? {words,2'd0} : tile_code==2'd1 ? {1'd0,words,1'd0} : {2'd0,words};
                    launched<=0;occupancy<=0;slot<=0;map_issued<=0;map_received<=0;staged_valid<=0;
                    pending_write<=0;pending_read<=0;pending_count<=0;
                    metadata_write<=0;metadata_read<=0;metadata_count<=0;emitted<=0;
                    state<=ROW;
                end
                ROW: begin
                    row_base<=map_base+row_offset;
                    map_bursts<=({4'd0,first_lane}+tiles+8'd15)>>4;
                    state<=BASE;
                end
                BASE: state<=RUN;
                RUN: begin
                    if(port_free) request_valid<=issue;
                    if(issue) fetch_addr<=staged_addr;
                    if(stage) staged_valid<=1;
                    else if(issue) staged_valid<=0;
                    if(stage && mapping) begin
                        map_issued<=map_issued+1'b1;
                        map_burst<=(map_burst+1'b1)&map_burst_mask;
                    end
                    if(stage_tile) pending_read<=pending_read+1'b1;
                    if(issue_tile) metadata_write<=metadata_write+1'b1;
                    if(map_response) map_received<=map_received+1'b1;
                    if(tile_response) metadata_read<=metadata_read+1'b1;
                    if(launch) begin
                        launched<=launched+1'b1;
                        slot<=slot==slot_last ? 2'd0 : slot+1'b1;
                    end
                    if(g4_valid) pending_write<=pending_write+1'b1;
                    occupancy<=occupancy+{3'd0,launch}-{3'd0,stage_tile};
                    pending_count<=pending_count+{3'd0,g4_valid}-{3'd0,stage_tile};
                    metadata_count<=metadata_count+{4'd0,issue_tile}-{4'd0,tile_response};
                    if(word_valid) begin
                        emitted<=emitted+1'b1;
                        if(emitted+6'd1==words) state<=IDLE;
                    end
                end
            endcase
        end
    end
endmodule
`default_nettype wire
