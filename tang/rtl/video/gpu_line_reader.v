// G3 line compositor: 16 indexed surfaces, 16 in-flight native DDR reads,
// 32 pixels merged per cycle. Descriptor commits and the palette are external.
`default_nettype none
module gpu_line_reader #(parameter WIDTH=800, HEIGHT=480) (
    input wire clk, resetn, start, layers, config_bank, sprites,
    input wire [31:0] base,
    input wire [8:0] line_y,
    output wire busy,
    output reg done,
    output wire [7:0] config_address,
    input wire [31:0] config_data,
    output wire fetch_valid,
    output reg [28:0] fetch_addr,
    input wire fetch_ready,
    input wire [255:0] fetch_data,
    input wire fetch_data_valid,
    output wire block_valid,
    output wire [4:0] block_index,
    output wire [255:0] block_data,
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
               S_HEAD=15,S_META=16,S_INFO=17,S_CHECK=18,S_CACHE=19,S_STORE=20,S_NEXT=21,L_NEXT=22,S_BARRIER=23;
    reg [4:0] state=IDLE;
    reg mode, bank;
    reg [8:0] y;
    reg [3:0] layer;
    reg [3:0] descriptor_word;
    reg [31:0] surface_base;
    reg [15:0] source_w,source_h,view_w,view_h,scroll_x,scroll_y,stride;
    reg signed [15:0] pos_x,pos_y;
    reg [1:0] flags;
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
    reg [5:0] buffered;
    reg [4:0] outstanding;
    reg more_requests,request_valid;
    assign busy=state!=IDLE;
    assign config_address={bank,layer,descriptor_word[2:0]};
    // Register the complete request enable: it feeds DDR arbitration and the
    // other clients' ready paths, so keep the state/count decode off that path.
    // request_valid itself is cleared by the synchronous reset. Re-gating it
    // with reset would put the large reset net back on the arbitration path.
    assign fetch_valid=request_valid;
    wire accept=fetch_valid && fetch_ready;
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
    reg [255:0] even_q,odd_q,old_q;
    reg signed [6:0] pair;
    reg [4:0] current_block,first_block,last_block,clear_block,emit_block;
    reg [4:0] shift_bytes;
    reg [31:0] first_mask,last_mask;
    // Merge each block as soon as its last source word has arrived. Waiting
    // until the complete DDR line was buffered wasted one cycle per block.
    wire signed [6:0] required_pair=pair+7'sd1;
    wire [5:0] required_word=required_pair>= $signed({1'b0,burst_count}) ? burst_count-6'd1 : required_pair[5:0];
    wire merge_issue=state==MERGE || (state==FETCH && mode && buffered>required_word);
    wire [6:0] even_pair=pair[0] ? pair+7'd1 : pair;
    wire [6:0] odd_pair=pair[0] ? pair : pair+7'd1;
    wire [4:0] ram_read_block=state==EMIT ? emit_block : current_block;
    reg source_write_valid=0;
    reg [4:0] source_write_address;
    reg [255:0] source_write_data;
    always @(posedge clk) begin
        source_write_valid<=resetn && ((state==FETCH && mode && fetch_data_valid) || state==S_STORE);
        source_write_address<=state==S_STORE ? 5'd0 : received[4:0];
        source_write_data<=state==S_STORE ? sprite_row_data : fetch_data;
        if(source_write_valid) begin
            if(source_write_address[0]) source_odd[source_write_address[4:1]]<=source_write_data;
            else source_even[source_write_address[4:1]]<=source_write_data;
        end
        even_q<=source_even[even_pair[4:1]];
        odd_q<=source_odd[odd_pair[4:1]];
        old_q<=composed[ram_read_block];
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
    wire [511:0] aligned_pair=p2_pair>>(shift_bytes*8);
    reg [255:0] merged;
    integer lane;
    always @* begin
        merged=p3_old;
        for(lane=0;lane<32;lane=lane+1)
            if(p3_mask[lane] && (!flags[1] || p3_pixels[lane*8+:8]!=0))
                merged[lane*8+:8]=p3_pixels[lane*8+:8];
    end
    // Separate bank selection from byte alignment. Wide data registers have
    // no reset/enable tree; only their associated valid bits carry meaning.
    always @(posedge clk) begin
        p2_pair<={high_word,low_word};p2_old<=old_q;
        p3_pixels<=aligned_pair[255:0];p3_old<=p2_old;
    end
    reg write_valid=0;
    reg [4:0] write_block;
    reg [255:0] write_pixels;
    always @(posedge clk) begin
        write_valid<=resetn && (state==CLEAR || p3_valid);
        write_block<=state==CLEAR ? clear_block : p3_block;
        write_pixels<=state==CLEAR ? 256'd0 : merged;
        if(write_valid) composed[write_block]<=write_pixels;
    end
    reg emit_valid;
    reg [4:0] emit_index;
    assign block_valid=resetn && (mode ? emit_valid : state==FETCH && fetch_data_valid);
    assign block_index=mode ? emit_index : received[4:0];
    assign block_data=mode ? old_q : fetch_data;

    always @(posedge clk) begin
        if(!resetn) begin
            state<=IDLE;done<=0;mode<=0;bank<=0;y<=0;layer<=0;descriptor_word<=0;
            surface_base<=0;source_w<=0;source_h<=0;view_w<=0;view_h<=0;scroll_x<=0;scroll_y<=0;stride<=0;
            pos_x<=0;pos_y<=0;flags<=0;left_x<=0;right_x<=0;relative_y<=0;window_w<=0;available_h<=0;
            source_x<=0;source_y<=0;row_offset<=0;byte_address<=0;visible_width<=0;
            issued<=0;received<=0;buffered<=0;burst_count<=0;outstanding<=0;more_requests<=0;request_valid<=0;fetch_addr<=0;elapsed<=0;max_cycles<=0;invalid_layers<=0;
            pair<=0;current_block<=0;first_block<=0;last_block<=0;clear_block<=0;emit_block<=0;
            shift_bytes<=0;first_mask<=0;last_mask<=0;
            p1_valid<=0;p1_odd<=0;p1_block<=0;p1_mask<=0;
            p2_valid<=0;p2_block<=0;p2_mask<=0;emit_valid<=0;emit_index<=0;
            p3_valid<=0;p3_block<=0;p3_mask<=0;
            sprite_mode<=0;is_sprite<=0;sprite_flip_y<=0;sprite_next<=64;sprite_index<=0;sprite_row_address<=0;
            line_sprites<=0;line_sprite_pixels<=0;max_sprites<=0;max_sprite_pixels<=0;
        end else begin
            done<=0;
            buffered<=received;
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
                    mode<=layers;bank<=config_bank;y<=line_y;elapsed<=0;layer<=0;
                    sprite_mode<=sprites;is_sprite<=0;line_sprites<=0;line_sprite_pixels<=0;
                    if(layers) begin clear_block<=0;state<=CLEAR;end
                    else begin
                        fetch_addr<=base[30:2];issued<=0;received<=0;burst_count<=BLOCKS;outstanding<=0;more_requests<=1;request_valid<=1;state<=FETCH;
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
                        7:flags<=config_data[1:0];
                    endcase
                    if(descriptor_word==7) state<=SIZE;
                    else descriptor_word<=descriptor_word+1'b1;
                end
                SIZE: begin
                    available_h<=$signed({2'b0,source_h})-$signed({2'b0,scroll_y});
                    window_w<=available_w<$signed({2'b0,view_w}) ? available_w : $signed({2'b0,view_w});
                    state<=CLIP;
                end
                CLIP: begin
                    left_x<=pos_x<0 ? 18'sd0 : $signed(pos_x);
                    right_x<=right_edge>WIDTH-1 ? WIDTH-1 : right_edge;
                    relative_y<=$signed({9'b0,y})-$signed(pos_y);
                    state<=COORD;
                end
                COORD: begin
                    // Unused on rejected layers; remove the clipping predicate
                    // from the wide mask/coordinate register enables.
                        source_x<=scroll_x+left_x-$signed(pos_x);source_y<=scroll_y+relative_y;
                        visible_width<=right_x-left_x+18'd1;
                        first_block<=left_x[9:5];last_block<=right_x[9:5];
                        first_mask<=32'hffffffff<<left_x[4:0];last_mask<=32'hffffffff>>(31-right_x[4:0]);

                    if(!flags[0] || view_w==0 || view_h==0 || scroll_x>=source_w || scroll_y>=source_h
                            || left_x>right_x || relative_y<0 || relative_y>=$signed({2'b0,view_h}) || relative_y>=available_h)
                        state<=NEXT;
                    else if(stride<source_w) begin invalid_layers<=invalid_layers+1'b1;state<=NEXT;end
                    else begin
                        state<=MUL;
                    end
                end
                MUL: begin row_offset<=source_y*stride;state<=ADDRESS;end
                ADDRESS: begin byte_address<={1'b0,surface_base}+{1'b0,row_offset}+{17'b0,source_x};state<=PREPARE;end
                PREPARE: begin
                    if(byte_address[32:30]!=0 || row_crosses_ddr_end) begin
                        invalid_layers<=invalid_layers+1'b1;state<=NEXT;
                    end else begin
                        fetch_addr<={byte_address[30:5],3'b0};
                        burst_count<=({6'b0,byte_address[4:0]}+visible_width+11'd31)>>5;
                        shift_bytes<=byte_address[4:0]-left_x[4:0];
                        pair<=byte_address[4:0]<left_x[4:0] ? -7'sd1 : 7'sd0;
                        current_block<=first_block;issued<=0;received<=0;buffered<=0;outstanding<=0;more_requests<=1;request_valid<=1;state<=FETCH;
                    end
                end
                FETCH: begin
                    outstanding<=next_outstanding;
                    request_valid<=more_requests && !next_outstanding[4];
                    if(accept) begin
                        issued<=issued+1'b1;fetch_addr<=fetch_addr+29'd8;
                        if(issued+6'd1==burst_count) begin more_requests<=0;request_valid<=0;end
                    end
                    if(fetch_data_valid) begin
                        received<=received+1'b1;
                        if(received+6'd1==burst_count && !mode) state<=FINISH;
                    end
                    if(merge_issue) begin
                        if(current_block==last_block) state<=DRAIN;
                        else begin current_block<=current_block+1'b1;pair<=pair+7'sd1;end
                    end
                end
                MERGE: if(current_block==last_block) state<=DRAIN;
                       else begin current_block<=current_block+1'b1;pair<=pair+7'sd1;end
                DRAIN: if(!p1_valid && !p2_valid && !p3_valid && !write_valid) state<=is_sprite ? S_NEXT : NEXT;
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
                    relative_y<=$signed({9'b0,y})-$signed(sprite_metadata[31:16]);
                    flags<=2'b11;is_sprite<=1;state<=S_CHECK;
                end
                S_CHECK: begin
                    if(left_x>right_x || relative_y<0 || relative_y>=$signed({2'b0,source_h})) state<=S_NEXT;
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
                    is_sprite<=0;
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
        end
    end
endmodule
`default_nettype wire
