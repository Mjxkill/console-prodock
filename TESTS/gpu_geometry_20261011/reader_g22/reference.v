// G3 line compositor: 16 indexed surfaces, 16 in-flight native DDR reads,
// 32 pixels merged per cycle. Descriptor commits and the palette are external.
// L11: a layer may instead be a tile map. gpu_tile_row then supplies the
// source words of the line; clipping, alignment, masks, colour key, sprites
// and priorities are those of a surface layer, which keeps its cycle count.
`default_nettype none
module gpu_line_reader_reference #(parameter WIDTH=800, HEIGHT=480) (
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
    localparam BLOCKS=WIDTH/32;
    localparam IDLE=0, CLEAR=1, DESC=2, CLIP=3, COORD=4, MUL=5,
               ADDRESS=6, PREPARE=7, FETCH=8, MERGE=9, DRAIN=10,
               NEXT=11, EMIT=12, FINISH=13, SIZE=14,
               S_HEAD=15,S_META=16,S_INFO=17,S_CHECK=18,S_CACHE=19,S_STORE=20,S_NEXT=21,L_NEXT=22,S_BARRIER=23,
               TILE=27;
    // The state is binary coded and codes 24..31 were free: each state of
    // 8..15 was decoded from four bits. One more code keeps that for all of
    // them but NEXT, which only selects a successor. The steps of a tile
    // layer have their own register.
    reg [4:0] state=IDLE;
    localparam T_SETUP=0,T_SIZE=1,T_END=2,T_CHECK=3,T_APPLY=4,T_ROW=5,T_START=6;
    reg [2:0] tile_step;
    reg mode, bank;
    // Copie de mode réservée au multiplexeur de données de 256 bits (syn_preserve : la synthèse ne doit
    // pas la refondre avec mode). mode seul alimentait 256 entrées de LUT plus la commande : les fils
    // s'allongeaient d'une compilation à l'autre (r601 : 0,74 ns en défaut vers les sommes de l'affichage).
    reg mode_data /* synthesis syn_preserve=1 */;
    reg [8:0] y;
    reg [3:0] layer;
    reg [3:0] descriptor_word;
    reg [31:0] surface_base;
    reg [15:0] source_w,source_h,view_w,view_h,scroll_x,scroll_y,stride;
    reg signed [15:0] pos_x,pos_y;
    reg [4:0] flags; // 0 enable, 1 key zero, 2 tile map, 3 wrap X, 4 wrap Y
    reg signed [17:0] left_x,right_x,relative_y;
    wire signed [17:0] available_w=$signed({2'b0,source_w})-$signed({2'b0,scroll_x});
    reg signed [17:0] available_h; // computed in SIZE, before vertical clipping
    reg signed [17:0] window_w;
    wire signed [17:0] right_edge=$signed(pos_x)+window_w-18'sd1;
    reg [15:0] source_x,source_y;
    reg [31:0] row_offset;
    reg [32:0] byte_address;
    reg [10:0] visible_width;
    // A clipped row is at most 1024 bytes. Only the final KiB can cross
    // the 1-GiB DDR limit; avoid a 33-bit add/compare on request enables.
    wire row_crosses_ddr_end=byte_address[29:10]==20'hfffff &&
        ({1'b0,byte_address[9:0]}+visible_width)>11'd1024;
    reg [5:0] issued,received,burst_count;
    reg [4:0] outstanding;
    reg more_requests,request_valid;
    assign busy=state!=IDLE;
    assign config_address={bank,layer,descriptor_word[2:0]};
    // Register the complete request enable: it feeds DDR arbitration and the
    // other clients' ready paths, so keep the state/count decode off that path.
    // request_valid itself is cleared by the synchronous reset. Re-gating it
    // with reset would put the large reset net back on the arbitration path.
    reg [28:0] request_addr;
    wire accept=request_valid && fetch_ready;

    // Tile map layers. Descriptor words 1 and 5 carry the atlas base and the
    // map geometry instead of the surface size and stride.
    reg tile_layer,tile_fetch,tile_start;
    reg [31:0] atlas_base;
    reg [3:0] tile_w_log2,tile_h_log2;
    reg [1:0] tile_code;
    reg [4:0] tile_w_px_log2,tile_h_px_log2,tile_map_log2,tile_atlas_log2;
    reg [32:0] tile_map_end,tile_atlas_end;
    wire [16:0] tile_w_px=17'd1<<tile_w_px_log2,tile_h_px=17'd1<<tile_h_px_log2;
    // Every reachable map entry and tile row lies inside the first GiB, so
    // the per-tile requests need no address check of their own.
    reg tile_accepted;
    wire tile_valid=tile_code!=2'd3 && tile_w_log2>=4'd4
        && tile_w_px_log2<=5'd15 && tile_h_px_log2<=5'd15
        && surface_base[4:0]==0 && atlas_base[4:0]==0
        && tile_map_end<=33'h040000000 && tile_atlas_end<=33'h040000000;
    wire tile_busy,tile_request_valid,tile_word_valid;
    wire [28:0] tile_request_addr;
    wire [255:0] tile_word;
    gpu_tile_row u_tiles (
        .clk(clk),.resetn(resetn),.start(tile_start),.busy(tile_busy),
        .map_base(surface_base),.atlas_base(atlas_base),
        .first_x({source_x[15:5],5'd0}),.source_y(source_y),
        .map_w_log2(tile_w_log2),.map_h_log2(tile_h_log2),.tile_code(tile_code),
        .words(burst_count),
        .fetch_valid(tile_request_valid),.fetch_addr(tile_request_addr),.fetch_ready(fetch_ready),
        .fetch_data(fetch_data),.fetch_data_valid(fetch_data_valid && tile_fetch),
        .word_valid(tile_word_valid),.word_data(tile_word));
    // Only one of the two request registers is ever set: the OR adds no
    // logic level in front of the DDR arbitration.
    assign fetch_valid=request_valid || tile_request_valid;
    assign fetch_addr=tile_fetch ? tile_request_addr : request_addr;
    wire source_word_valid=tile_fetch ? tile_word_valid : fetch_data_valid;
    // L11: the rejection tests set one register; the 32-bit counter follows a
    // cycle later. Its clock enable no longer hangs on the clipping compares.
    reg invalid_layer;
    // The rejection of a layer or sprite is decided one state before it is
    // used, together with the values it tests: same decision, same cycle,
    // without the comparisons in front of the state register.
    // reject_x is left_x>right_x of the next state: a window that starts left
    // of the screen is empty when it also ends there; any other window when
    // it starts beyond the last column or has no width.
    reg reject_y,reject_x,reject_layer,narrow_stride;
    wire signed [17:0] sprite_x=$signed(sprite_metadata[15:0]);
    wire signed [17:0] layer_relative_y=$signed({9'b0,y})-$signed(pos_y);
    wire signed [17:0] sprite_relative_y=$signed({9'b0,y})-$signed(sprite_metadata[31:16]);
    wire [4:0] next_outstanding=outstanding+{4'b0,accept}-{4'b0,fetch_data_valid};
    reg [31:0] elapsed;
    reg sprite_mode,is_sprite,sprite_flip_y;
    reg [6:0] sprite_next;
    reg [6:0] line_sprites;
    reg [11:0] line_sprite_pixels;
    assign sprite_head_layer=layer;
    wire signed [17:0] sprite_right=$signed(sprite_metadata[15:0])+$signed({12'b0,sprite_metadata[37:32]})-18'sd1;
    wire signed [17:0] clipped_source_x=left_x-$signed(pos_x);

    // Adjacent source words always belong to opposite banks. Two synchronous
    // reads and one incoming DDR write therefore need only dual-port RAMs.
    reg [255:0] source_even[0:15],source_odd[0:15];
    reg [255:0] composed[0:31];
    reg [31:0] covered[0:31];
    reg [31:0] old_coverage,p2_coverage,p3_coverage,merged_coverage,write_coverage;
    reg [255:0] even_q,odd_q,old_q;
    reg signed [6:0] pair;
    reg [4:0] current_block,first_block,last_block,clear_block,emit_block;
    reg [4:0] shift_bytes;
    reg [31:0] first_mask,last_mask;
    // Merge each block as soon as its last source word has arrived. Waiting
    // until the complete DDR line was buffered wasted one cycle per block.
    // A block needs source words pair and pair+1, or all words of the row
    // when pair+1 lies beyond the last one. A received word is readable two
    // cycles later (registered RAM write, then its read). The comparison is
    // prepared from `received` and from the value `pair` takes next, then
    // registered: merge_ready is received(previous cycle) >
    // min(pair+1,burst_count-1), the decision made before L11 through the
    // `buffered` copy of `received`, without the compare on the enable path.
    reg merge_ready;
    wire merge_issue=state==MERGE || (state==FETCH && mode && merge_ready);
    wire signed [7:0] needed_same=$signed({pair[6],pair})+8'sd1;
    wire signed [7:0] needed_advanced=$signed({pair[6],pair})+8'sd2;
    wire signed [7:0] words_received={2'b0,received};
    wire merge_ready_next=state==FETCH && (received>=burst_count
        || (merge_issue ? words_received>needed_advanced : words_received>needed_same));
    wire [6:0] even_pair=pair[0] ? pair+7'd1 : pair;
    wire [6:0] odd_pair=pair[0] ? pair : pair+7'd1;
    wire [4:0] ram_read_block=state==EMIT ? emit_block : current_block;
    reg source_write_valid=0;
    reg [4:0] source_write_address;
    reg [255:0] source_write_data;
    always @(posedge clk) begin
        source_write_valid<=resetn && ((state==FETCH && mode && source_word_valid) || state==S_STORE);
        source_write_address<=state==S_STORE ? 5'd0 : received[4:0];
        source_write_data<=state==S_STORE ? sprite_row_data : tile_fetch ? tile_word : fetch_data;
        if(source_write_valid) begin
            if(source_write_address[0]) source_odd[source_write_address[4:1]]<=source_write_data;
            else source_even[source_write_address[4:1]]<=source_write_data;
        end
        even_q<=source_even[even_pair[4:1]];
        odd_q<=source_odd[odd_pair[4:1]];
        old_q<=composed[ram_read_block];
        old_coverage<=covered[ram_read_block];
    end
    reg p1_valid,p1_odd;
    reg [4:0] p1_block,p2_block,p3_block;
    reg [31:0] p1_mask,p2_mask,p3_mask;
    reg p2_valid,p3_valid;
    reg [511:0] p2_pair;
    reg [255:0] p2_old,p3_pixels,p3_old;
    // The first/last destination byte masks discard every byte outside the
    // fetched source interval, including the unused neighbor of an edge word.
    wire [255:0] low_word=p1_odd ? odd_q : even_q;
    wire [255:0] high_word=p1_odd ? even_q : odd_q;
    wire [511:0] aligned_pair=p2_pair>>({shift_bytes[4:1],4'b0});
    reg [255:0] merged;
    integer lane;
    always @* begin
        merged=p3_old;merged_coverage=p3_coverage;
        for(lane=0;lane<32;lane=lane+1)
            if(p3_mask[lane] && (!flags[1] || p3_pixels[lane*8+:8]!=0)) begin
                merged[lane*8+:8]=p3_pixels[lane*8+:8];
                merged_coverage[lane]=1;
            end
    end
    // RAM clock-to-Q precedes the bank selection: put only the low shift bit
    // in that stage, then the high four bits after a logic register.
    // shift_bytes is stable until DRAIN empties
    // the pipeline. No extra merge cycle or reset/enable tree is introduced.
    always @(posedge clk) begin
        p2_pair<=({high_word,low_word}>>{shift_bytes[0],3'b0});p2_old<=old_q;p2_coverage<=old_coverage;
        p3_pixels<=aligned_pair[255:0];p3_old<=p2_old;p3_coverage<=p2_coverage;
    end
    reg write_valid=0;
    reg [4:0] write_block;
    reg [255:0] write_pixels;
    // Anticiper CLEAR depuis ses deux prédécesseurs : ces copies locales
    // valent state==CLEAR sans cycle supplémentaire. La remise à zéro des
    // 288 bits ne dépend plus d'un décodage d'état à 293 destinations
    // (r622 : 9,60 ns de routage vers write_coverage).
    reg [2:0] clear_payload /* synthesis syn_preserve=1 */ =0;
    always @(posedge clk)
        clear_payload<={3{resetn && ((state==IDLE && start && layers) ||
            (state==CLEAR && clear_block!=BLOCKS-1))}};
    always @(posedge clk) begin
        write_valid<=resetn && (state==CLEAR || p3_valid);
        write_block<=state==CLEAR ? clear_block : p3_block;
        write_pixels<={clear_payload[1] ? 128'd0 : merged[255:128],
                       clear_payload[0] ? 128'd0 : merged[127:0]};
        write_coverage<=clear_payload[2] ? 32'd0:merged_coverage;
        if(write_valid) begin composed[write_block]<=write_pixels;covered[write_block]<=write_coverage;end
    end
    reg emit_valid;
    reg [4:0] emit_index;
    // framebuffer_fetch is state==FETCH && !mode, kept as a register: the
    // block strobe enables the line RAM and the checksum registers.
    reg framebuffer_fetch;
    assign block_valid=resetn && (mode ? emit_valid : framebuffer_fetch && fetch_data_valid);
    assign block_index=mode ? emit_index : received[4:0];
    assign block_data=mode_data ? old_q : fetch_data;
    assign block_coverage=mode ? old_coverage:32'hffffffff;

    always @(posedge clk) begin
        if(!resetn) begin
            state<=IDLE;done<=0;mode<=0;mode_data<=0;bank<=0;y<=0;layer<=0;descriptor_word<=0;
            surface_base<=0;source_w<=0;source_h<=0;view_w<=0;view_h<=0;scroll_x<=0;scroll_y<=0;stride<=0;
            pos_x<=0;pos_y<=0;flags<=0;left_x<=0;right_x<=0;relative_y<=0;window_w<=0;available_h<=0;
            source_x<=0;source_y<=0;row_offset<=0;byte_address<=0;visible_width<=0;
            issued<=0;received<=0;burst_count<=0;outstanding<=0;more_requests<=0;request_valid<=0;request_addr<=0;elapsed<=0;max_cycles<=0;invalid_layers<=0;
            pair<=0;current_block<=0;first_block<=0;last_block<=0;clear_block<=0;emit_block<=0;
            shift_bytes<=0;first_mask<=0;last_mask<=0;
            p1_valid<=0;p1_odd<=0;p1_block<=0;p1_mask<=0;
            p2_valid<=0;p2_block<=0;p2_mask<=0;emit_valid<=0;emit_index<=0;
            p3_valid<=0;p3_block<=0;p3_mask<=0;
            sprite_mode<=0;is_sprite<=0;sprite_flip_y<=0;sprite_next<=64;sprite_index<=0;sprite_row_address<=0;
            line_sprites<=0;line_sprite_pixels<=0;max_sprites<=0;max_sprite_pixels<=0;
            invalid_layer<=0;merge_ready<=0;framebuffer_fetch<=0;
            reject_y<=0;reject_x<=0;reject_layer<=0;narrow_stride<=0;
            tile_layer<=0;tile_fetch<=0;tile_start<=0;tile_step<=0;tile_accepted<=0;atlas_base<=0;tile_w_log2<=0;tile_h_log2<=0;tile_code<=0;
            tile_w_px_log2<=0;tile_h_px_log2<=0;tile_map_log2<=0;tile_atlas_log2<=0;tile_map_end<=0;tile_atlas_end<=0;
        end else begin
            done<=0;
            tile_start<=0;
            invalid_layer<=0;
            if(invalid_layer) invalid_layers<=invalid_layers+1'b1;
            merge_ready<=merge_ready_next;
            if(busy) elapsed<=elapsed+1'b1;
            p1_valid<=merge_issue;
            if(merge_issue) begin
                p1_odd<=pair[0];
                p1_block<=current_block;
                p1_mask<=(current_block==first_block ? first_mask : 32'hffffffff)
                       & (current_block==last_block ? last_mask : 32'hffffffff);
            end
            p2_valid<=p1_valid;
            if(p1_valid) begin
                p2_block<=p1_block;p2_mask<=p1_mask;
            end
            p3_valid<=p2_valid;
            if(p2_valid) begin p3_block<=p2_block;p3_mask<=p2_mask;end
            emit_valid<=state==EMIT;
            if(state==EMIT) emit_index<=emit_block;
            case(state)
                IDLE: if(start) begin
                    mode<=layers;mode_data<=layers;bank<=config_bank;y<=line_y;elapsed<=0;layer<=0;
                    sprite_mode<=sprites;is_sprite<=0;line_sprites<=0;line_sprite_pixels<=0;
                    tile_layer<=0;tile_fetch<=0;
                    if(layers) begin clear_block<=0;state<=CLEAR;end
                    else begin
                        request_addr<=base[30:2];issued<=0;received<=0;burst_count<=BLOCKS;outstanding<=0;more_requests<=1;request_valid<=1;state<=FETCH;
                        framebuffer_fetch<=1;
                    end
                end
                CLEAR: if(clear_block==BLOCKS-1) begin descriptor_word<=0;state<=DESC;end
                       else clear_block<=clear_block+1'b1;
                DESC: begin
                    if(descriptor_word!=0) case(descriptor_word)
                        1:surface_base<=config_data;
                        2:{source_h,source_w}<=config_data;
                        3:{pos_y,pos_x}<=config_data;
                        4:{view_h,view_w}<=config_data;
                        5:{scroll_y,scroll_x}<=config_data;
                        6:stride<=config_data[15:0];
                        7:flags<=config_data[4:0];
                    endcase
                    // Surface layers go straight to SIZE, as before L11.
                    if(descriptor_word==7) begin
                        state<=config_data[2] && config_data[0] ? TILE : SIZE;tile_step<=T_SETUP;
                    end
                    else descriptor_word<=descriptor_word+1'b1;
                end
                TILE: case(tile_step)
                    T_SETUP: begin
                        atlas_base<={source_h,source_w};
                        tile_w_log2<=stride[3:0];tile_h_log2<=stride[7:4];tile_code<=stride[9:8];
                        tile_step<=T_SIZE;
                    end
                    T_SIZE: begin
                        tile_w_px_log2<={1'b0,tile_w_log2}+{3'b0,tile_code}+5'd3;
                        tile_h_px_log2<={1'b0,tile_h_log2}+{3'b0,tile_code}+5'd3;
                        tile_map_log2<={1'b0,tile_w_log2}+{1'b0,tile_h_log2}+5'd1;
                        tile_atlas_log2<=5'd19+{2'b0,tile_code,1'b0}; // 8192 tiles of T*T bytes
                        tile_step<=T_END;
                    end
                    T_END: begin
                        tile_map_end<={1'b0,surface_base}+(33'd1<<tile_map_log2);
                        tile_atlas_end<={1'b0,atlas_base}+(33'd1<<tile_atlas_log2);
                        tile_step<=T_CHECK;
                    end
                    T_CHECK: begin tile_accepted<=tile_valid;tile_step<=T_APPLY;end
                    T_APPLY: begin
                        if(!tile_accepted) begin invalid_layer<=1;state<=NEXT;end
                        else begin
                            // From here the map is clipped like a surface of its
                            // pixel size; a wrapped axis has no edge to clip.
                            source_w<=flags[3] ? 16'hffff : tile_w_px[15:0];
                            source_h<=flags[4] ? 16'hffff : tile_h_px[15:0];
                            if(flags[3]) scroll_x<=scroll_x&(tile_w_px[15:0]-16'd1);
                            if(flags[4]) scroll_y<=scroll_y&(tile_h_px[15:0]-16'd1);
                            stride<=16'hffff;tile_layer<=1;state<=SIZE;
                        end
                    end
                    T_ROW: begin
                        burst_count<=({6'b0,source_x[4:0]}+visible_width+11'd31)>>5;
                        shift_bytes<=source_x[4:0]-left_x[4:0];
                        pair<=source_x[4:0]<left_x[4:0] ? -7'sd1 : 7'sd0;
                        current_block<=first_block;issued<=0;received<=0;outstanding<=0;more_requests<=0;request_valid<=0;
                        tile_step<=T_START;
                    end
                    T_START: if(!tile_busy) begin tile_start<=1;tile_fetch<=1;state<=FETCH;end
                    default: state<=NEXT;
                endcase
                SIZE: begin
                    available_h<=$signed({2'b0,source_h})-$signed({2'b0,scroll_y});
                    window_w<=available_w<$signed({2'b0,view_w}) ? available_w : $signed({2'b0,view_w});
                    state<=CLIP;
                end
                CLIP: begin
                    left_x<=pos_x<0 ? 18'sd0 : $signed(pos_x);
                    right_x<=right_edge>WIDTH-1 ? WIDTH-1 : right_edge;
                    relative_y<=layer_relative_y;
                    reject_y<=layer_relative_y<0 || layer_relative_y>=$signed({2'b0,view_h}) || layer_relative_y>=available_h;
                    reject_x<=pos_x<0 ? right_edge<0 : ($signed(pos_x)>WIDTH-1 || window_w<=0);
                    reject_layer<=!flags[0] || view_w==0 || view_h==0 || scroll_x>=source_w || scroll_y>=source_h;
                    narrow_stride<=stride<source_w;
                    state<=COORD;
                end
                COORD: begin
                    // Unused on rejected layers; remove the clipping predicate
                    // from the wide mask/coordinate register enables.
                        source_x<=scroll_x+left_x-$signed(pos_x);source_y<=scroll_y+relative_y;
                        visible_width<=right_x-left_x+18'd1;
                        first_block<=left_x[9:5];last_block<=right_x[9:5];
                        first_mask<=32'hffffffff<<left_x[4:0];last_mask<=32'hffffffff>>(31-right_x[4:0]);

                    if(reject_layer || reject_x || reject_y) state<=NEXT;
                    else if(narrow_stride) begin invalid_layer<=1;state<=NEXT;end
                    else begin
                        state<=MUL;
                    end
                end
                // A tile layer leaves the surface path here, where the next
                // state depends on nothing else; its product is not used.
                MUL: begin row_offset<=source_y*stride;state<=tile_layer ? TILE : ADDRESS;tile_step<=T_ROW;end
                ADDRESS: begin byte_address<={1'b0,surface_base}+{1'b0,row_offset}+{17'b0,source_x};state<=PREPARE;end
                PREPARE: begin
                    // Payload is unused when the DDR range check rejects this
                    // row. Keep that check off the wide register enables; only
                    // request_valid and the state authorize any DDR access.
                    request_addr<={byte_address[30:5],3'b0};
                    burst_count<=({6'b0,byte_address[4:0]}+visible_width+11'd31)>>5;
                    shift_bytes<=byte_address[4:0]-left_x[4:0];
                    pair<=byte_address[4:0]<left_x[4:0] ? -7'sd1 : 7'sd0;
                    current_block<=first_block;issued<=0;received<=0;outstanding<=0;
                    if(byte_address[32:30]!=0 || row_crosses_ddr_end) begin
                        invalid_layer<=1;state<=NEXT;
                    end else begin
                        more_requests<=1;request_valid<=1;state<=FETCH;
                    end
                end
                FETCH: begin
                    outstanding<=next_outstanding;
                    request_valid<=more_requests && !next_outstanding[4];
                    if(accept) begin
                        issued<=issued+1'b1;request_addr<=request_addr+29'd8;
                        if(issued+6'd1==burst_count) begin more_requests<=0;request_valid<=0;end
                    end
                    if(source_word_valid) begin
                        received<=received+1'b1;
                        if(received+6'd1==burst_count && !mode) begin state<=FINISH;framebuffer_fetch<=0;end
                    end
                    if(merge_issue) begin
                        if(current_block==last_block) state<=DRAIN;
                        else begin current_block<=current_block+1'b1;pair<=pair+7'sd1;end
                    end
                end
                MERGE: if(current_block==last_block) state<=DRAIN;
                       else begin current_block<=current_block+1'b1;pair<=pair+7'sd1;end
                DRAIN: if(!p1_valid && !p2_valid && !p3_valid && !write_valid) begin
                    tile_fetch<=0;state<=is_sprite ? S_NEXT : NEXT;
                end
                NEXT: state<=sprite_mode ? S_HEAD : L_NEXT;
                S_HEAD: begin
                    sprite_index<=sprite_head_index[5:0];
                    state<=sprite_head_index[6] ? L_NEXT : S_META;
                end
                S_META: state<=S_INFO; // synchronous descriptor RAM
                S_INFO: begin
                    {pos_y,pos_x}<=sprite_metadata[31:0];
                    source_w<={10'b0,sprite_metadata[37:32]};source_h<={10'b0,sprite_metadata[43:38]};
                    sprite_flip_y<=sprite_metadata[45];sprite_next<=sprite_metadata[52:46];
                    left_x<=$signed(sprite_metadata[15:0])<0 ? 18'sd0 : $signed(sprite_metadata[15:0]);
                    right_x<=sprite_right>WIDTH-1 ? WIDTH-1 : sprite_right;
                    relative_y<=sprite_relative_y;
                    reject_y<=sprite_relative_y<0 || sprite_relative_y>=$signed({12'b0,sprite_metadata[43:38]});
                    reject_x<=sprite_x<0 ? sprite_right<0 : (sprite_x>WIDTH-1 || sprite_metadata[37:32]==0);
                    flags<=5'b00011;is_sprite<=1;state<=S_CHECK;
                end
                S_CHECK: begin
                    if(reject_x || reject_y) state<=S_NEXT;
                    else begin
                        sprite_row_address<={sprite_index,sprite_flip_y ? source_h[4:0]-5'd1-relative_y[4:0] : relative_y[4:0]};
                        first_block<=left_x[9:5];current_block<=left_x[9:5];last_block<=right_x[9:5];
                        first_mask<=32'hffffffff<<left_x[4:0];last_mask<=32'hffffffff>>(31-right_x[4:0]);
                        shift_bytes<=clipped_source_x[4:0]-left_x[4:0];
                        pair<=clipped_source_x[4:0]<left_x[4:0] ? -7'sd1 : 7'sd0;
                        line_sprites<=line_sprites+1'b1;line_sprite_pixels<=line_sprite_pixels+right_x-left_x+18'd1;
                        state<=S_CACHE;
                    end
                end
                S_CACHE: state<=S_STORE;
                S_STORE: state<=S_BARRIER;
                S_BARRIER: state<=MERGE;
                S_NEXT: begin sprite_index<=sprite_next[5:0];state<=sprite_next[6] ? L_NEXT : S_META;end
                L_NEXT: begin
                    is_sprite<=0;tile_layer<=0;
                    if(layer==15) begin emit_block<=0;state<=EMIT;end
                    else begin layer<=layer+1'b1;descriptor_word<=0;state<=DESC;end
                end
                EMIT: if(emit_block==BLOCKS-1) state<=FINISH;
                      else emit_block<=emit_block+1'b1;
                FINISH: if(!emit_valid) begin
                    done<=1;state<=IDLE;if(elapsed>max_cycles) max_cycles<=elapsed;
                    if(line_sprites>max_sprites) max_sprites<=line_sprites;
                    if(line_sprite_pixels>max_sprite_pixels) max_sprite_pixels<=line_sprite_pixels;
                end
                default:state<=IDLE;
            endcase
            // Software restarts a measurement; a line finishing in this
            // same cycle belongs to the previous one.
            if(clear_maxima) begin max_cycles<=0;max_sprites<=0;max_sprite_pixels<=0;end
        end
    end
endmodule
`default_nettype wire
