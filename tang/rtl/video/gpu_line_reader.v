// G3 line compositor: 16 indexed surfaces, 16 in-flight native DDR reads,
// 32 pixels merged per cycle. Descriptor commits and the palette are external.
`default_nettype none
module gpu_line_reader #(parameter WIDTH=800, HEIGHT=480) (
    input wire clk, resetn, start, layers, config_bank,
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
    output reg [31:0] max_cycles, invalid_layers
);
    localparam BLOCKS=WIDTH/32;
    localparam IDLE=0, CLEAR=1, DESC=2, CLIP=3, COORD=4, MUL=5,
               ADDRESS=6, PREPARE=7, FETCH=8, MERGE=9, DRAIN=10,
               NEXT=11, EMIT=12, FINISH=13, SIZE=14;
    reg [3:0] state=IDLE;
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
    wire signed [17:0] available_h=$signed({2'b0,source_h})-$signed({2'b0,scroll_y});
    reg signed [17:0] window_w;
    wire signed [17:0] right_edge=$signed(pos_x)+window_w-18'sd1;
    reg [15:0] source_x,source_y;
    reg [31:0] row_offset;
    reg [32:0] byte_address;
    reg [10:0] visible_width;
    reg [5:0] issued,received,burst_count;
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

    // Adjacent source words always belong to opposite banks. Two synchronous
    // reads and one incoming DDR write therefore need only dual-port RAMs.
    reg [255:0] source_even[0:15],source_odd[0:15];
    reg [255:0] composed[0:31];
    reg [255:0] even_q,odd_q,old_q;
    reg signed [6:0] pair;
    reg [4:0] current_block,first_block,last_block,clear_block,emit_block;
    reg [4:0] shift_bytes;
    reg [31:0] first_mask,last_mask;
    wire [6:0] even_pair=pair[0] ? pair+7'd1 : pair;
    wire [6:0] odd_pair=pair[0] ? pair : pair+7'd1;
    wire [4:0] ram_read_block=state==EMIT ? emit_block : current_block;
    always @(posedge clk) begin
        if(state==FETCH && mode && fetch_data_valid) begin
            if(received[0]) source_odd[received[4:1]]<=fetch_data;
            else source_even[received[4:1]]<=fetch_data;
        end
        even_q<=source_even[even_pair[4:1]];
        odd_q<=source_odd[odd_pair[4:1]];
        old_q<=composed[ram_read_block];
    end
    reg p1_valid,p1_odd;
    reg [4:0] p1_block,p2_block;
    reg [31:0] p1_mask,p2_mask;
    reg p2_valid;
    reg [255:0] p2_pixels,p2_old;
    // The first/last destination byte masks discard every byte outside the
    // fetched source interval, including the unused neighbor of an edge word.
    wire [255:0] low_word=p1_odd ? odd_q : even_q;
    wire [255:0] high_word=p1_odd ? even_q : odd_q;
    wire [511:0] aligned_pair={high_word,low_word}>>(shift_bytes*8);
    reg [255:0] merged;
    integer lane;
    always @* begin
        merged=p2_old;
        for(lane=0;lane<32;lane=lane+1)
            if(p2_mask[lane] && (!flags[1] || p2_pixels[lane*8+:8]!=0))
                merged[lane*8+:8]=p2_pixels[lane*8+:8];
    end
    // Unconditional data registers avoid distributing reset/enables across
    // 512 datapath bits. Their contents only matter when p2_valid is asserted.
    always @(posedge clk) begin p2_pixels<=aligned_pair[255:0];p2_old<=old_q;end
    reg write_valid=0;
    reg [4:0] write_block;
    reg [255:0] write_pixels;
    always @(posedge clk) begin
        write_valid<=resetn && (state==CLEAR || p2_valid);
        write_block<=state==CLEAR ? clear_block : p2_block;
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
            pos_x<=0;pos_y<=0;flags<=0;left_x<=0;right_x<=0;relative_y<=0;window_w<=0;
            source_x<=0;source_y<=0;row_offset<=0;byte_address<=0;visible_width<=0;
            issued<=0;received<=0;burst_count<=0;outstanding<=0;more_requests<=0;request_valid<=0;fetch_addr<=0;elapsed<=0;max_cycles<=0;invalid_layers<=0;
            pair<=0;current_block<=0;first_block<=0;last_block<=0;clear_block<=0;emit_block<=0;
            shift_bytes<=0;first_mask<=0;last_mask<=0;
            p1_valid<=0;p1_odd<=0;p1_block<=0;p1_mask<=0;
            p2_valid<=0;p2_block<=0;p2_mask<=0;emit_valid<=0;emit_index<=0;
        end else begin
            done<=0;
            if(busy) elapsed<=elapsed+1'b1;
            p1_valid<=state==MERGE;
            if(state==MERGE) begin
                p1_odd<=pair[0];
                p1_block<=current_block;
                p1_mask<=(current_block==first_block ? first_mask : 32'hffffffff)
                       & (current_block==last_block ? last_mask : 32'hffffffff);
            end
            p2_valid<=p1_valid;
            if(p1_valid) begin
                p2_block<=p1_block;p2_mask<=p1_mask;
            end
            emit_valid<=state==EMIT;
            if(state==EMIT) emit_index<=emit_block;
            case(state)
                IDLE: if(start) begin
                    mode<=layers;bank<=config_bank;y<=line_y;elapsed<=0;layer<=0;
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
                    if(!flags[0] || view_w==0 || view_h==0 || scroll_x>=source_w || scroll_y>=source_h
                            || left_x>right_x || relative_y<0 || relative_y>=$signed({2'b0,view_h}) || relative_y>=available_h)
                        state<=NEXT;
                    else if(stride<source_w) begin invalid_layers<=invalid_layers+1'b1;state<=NEXT;end
                    else begin
                        source_x<=scroll_x+left_x-$signed(pos_x);source_y<=scroll_y+relative_y;
                        visible_width<=right_x-left_x+18'd1;
                        first_block<=left_x[9:5];last_block<=right_x[9:5];
                        first_mask<=32'hffffffff<<left_x[4:0];last_mask<=32'hffffffff>>(31-right_x[4:0]);
                        state<=MUL;
                    end
                end
                MUL: begin row_offset<=source_y*stride;state<=ADDRESS;end
                ADDRESS: begin byte_address<={1'b0,surface_base}+{1'b0,row_offset}+{17'b0,source_x};state<=PREPARE;end
                PREPARE: begin
                    if(byte_address[32:30]!=0 || byte_address+visible_width>33'h040000000) begin
                        invalid_layers<=invalid_layers+1'b1;state<=NEXT;
                    end else begin
                        fetch_addr<={byte_address[30:5],3'b0};
                        burst_count<=({6'b0,byte_address[4:0]}+visible_width+11'd31)>>5;
                        shift_bytes<=byte_address[4:0]-left_x[4:0];
                        pair<=byte_address[4:0]<left_x[4:0] ? -7'sd1 : 7'sd0;
                        current_block<=first_block;issued<=0;received<=0;outstanding<=0;more_requests<=1;request_valid<=1;state<=FETCH;
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
                        if(received+6'd1==burst_count) state<=mode ? MERGE : FINISH;
                    end
                end
                MERGE: if(current_block==last_block) state<=DRAIN;
                       else begin current_block<=current_block+1'b1;pair<=pair+7'sd1;end
                DRAIN: if(!p1_valid && !p2_valid && !write_valid) state<=NEXT;
                NEXT: if(layer==15) begin emit_block<=0;state<=EMIT;end
                      else begin layer<=layer+1'b1;descriptor_word<=0;state<=DESC;end
                EMIT: if(emit_block==BLOCKS-1) state<=FINISH;
                      else emit_block<=emit_block+1'b1;
                FINISH: if(!emit_valid) begin
                    done<=1;state<=IDLE;if(elapsed>max_cycles) max_cycles<=elapsed;
                end
                default:state<=IDLE;
            endcase
        end
    end
endmodule
`default_nettype wire
