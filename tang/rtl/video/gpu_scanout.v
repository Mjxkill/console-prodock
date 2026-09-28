// G4: framebuffer or 16 layers + 64 cached sprites, two display lines.
// Three existing clocks only: AHB 80 MHz, DDR UI 75 MHz, LCD 35 MHz.
// Mailboxes hold multi-bit data stable until a synchronized acknowledgement.
`default_nettype none
module gpu_scanout #(
    parameter WIDTH = 800, HEIGHT = 480,
    parameter H_TOTAL = 1193, V_TOTAL = 533,
    parameter H_START = 182, V_START = 8,
    parameter H_SYNC = 210, V_SYNC = 45
) (
    input wire hclk, hresetn, hsel, hwrite,
    input wire [31:0] haddr, hwdata,
    input wire [1:0] htrans,
    output reg [31:0] hrdata,
    output wire hready,
    input wire pixel_clk, mem_clk,
    output wire fetch_valid,
    output wire [28:0] fetch_addr,
    input wire fetch_ready,
    input wire [255:0] fetch_data,
    input wire fetch_data_valid,
    output wire lcd_en, lcd_hs, lcd_vs,
    output wire [5:0] lcd_r, lcd_g, lcd_b
);
    localparam BURSTS = WIDTH / 32;
    // G1 requires WIDTH divisible by 32 and <=1024; pitch equals WIDTH.
    reg [1:0] prst = 0, mrst = 0;
    always @(posedge pixel_clk or negedge hresetn)
        if (!hresetn) prst <= 0; else prst <= {prst[0], 1'b1};
    always @(posedge mem_clk or negedge hresetn)
        if (!hresetn) mrst <= 0; else mrst <= {mrst[0], 1'b1};

    reg [31:0] shadow_base, mailbox_base;
    reg shadow_enable, mailbox_enable, commit_toggle;
    reg shadow_layers,mailbox_layers,mailbox_bank,write_bank;
    reg shadow_sprites,mailbox_sprites;
    reg applied_toggle = 0;
    reg [1:0] applied_sync;
    reg [11:0] bus_addr;
    reg bus_write,bus_guarded;
    wire busy = commit_toggle != applied_sync[1];
    wire layer_table_access=bus_addr[11:9]==3'b100;
    wire sprite_table_access=bus_addr[11:10]==2'b11;
    wire table_access=layer_table_access || sprite_table_access;
    // Decode the addresses that wait for a commit during the address phase.
    // HREADY then avoids a full address comparator on the CPU return path.
    assign hready = !(bus_write && busy && bus_guarded);
    wire write_fire = bus_write && hready;
    reg [17:0] palette [0:255];
    reg [31:0] descriptors [0:255];
    reg [31:0] sprite_descriptors [0:511];
    wire [8:0] sprite_config_address;
    reg [31:0] sprite_config_data;
    wire [7:0] config_address;
    reg [31:0] config_data;
    always @(posedge hclk)
        if(hresetn && write_fire && layer_table_access) descriptors[{write_bank,bus_addr[8:2]}]<=hwdata;
    always @(posedge mem_clk) config_data<=descriptors[config_address];
    always @(posedge hclk)
        if(hresetn && write_fire && sprite_table_access) sprite_descriptors[{write_bank,bus_addr[9:2]}]<=hwdata;
    always @(posedge mem_clk) sprite_config_data<=sprite_descriptors[sprite_config_address];
    always @(posedge hclk) begin
        if (!hresetn) begin
            shadow_base <= 0; shadow_enable <= 0;
            mailbox_base <= 0; mailbox_enable <= 0;
            commit_toggle <= 0; applied_sync <= 0;
            shadow_layers<=0;mailbox_layers<=0;mailbox_bank<=0;write_bank<=1;
            shadow_sprites<=0;mailbox_sprites<=0;
            bus_addr <= 0; bus_write <= 0;bus_guarded<=0;
        end else begin
            applied_sync <= {applied_sync[0], applied_toggle};
            if (hready) begin
                bus_addr <= haddr[11:0];
                bus_write <= hsel && htrans[1] && hwrite;
                bus_guarded <= haddr[11:0]==12'h00c || haddr[11:9]==3'b100 || haddr[11:10]==2'b11;
            end
            if (write_fire) case (bus_addr)
                12'h004: shadow_base <= {2'b0, hwdata[29:5], 5'b0};
                12'h008: shadow_enable <= hwdata[0];
                12'h00c: if (hwdata[0]) begin
                    mailbox_base <= shadow_base;
                    mailbox_enable <= shadow_enable;
                    mailbox_layers<=shadow_layers;mailbox_bank<=write_bank;
                    mailbox_sprites<=shadow_sprites;
                    if(shadow_layers) write_bank<=~write_bank;
                    commit_toggle <= ~commit_toggle;
                end
                12'h030: shadow_layers<=hwdata[0];
                12'h040: shadow_sprites<=hwdata[0];
                default: begin end
            endcase
        end
    end
    // Keep the RAM write process free of reset for BSRAM inference.
    always @(posedge hclk)
        if (hresetn && write_fire && bus_addr[11:10] == 2'b01)
            palette[bus_addr[9:2]] <= hwdata[17:0];

    reg [31:0] active_base = 0, frames = 0, underflows = 0;
    reg active_enable = 0;
    reg active_layers=0,active_bank=0;
    reg active_sprites=0;
    wire [31:0] r_base, r_frames, r_underflows, r_checksum, r_fetch_frames;
    reg [31:0] frame_checksum = 0, fetch_frames = 0;
    wire [31:0] max_cycles,invalid_layers,r_max_cycles,r_invalid_layers;
    wire [31:0] invalid_sprites,cache_cycles,cache_loads,max_sprites,max_sprite_pixels;
    wire [31:0] r_invalid_sprites,r_cache_cycles,r_cache_loads,r_max_sprites,r_max_sprite_pixels;
    cdc_word u_invalid_sprites (.src_clk(mem_clk),.src_data(invalid_sprites),.dst_clk(hclk),.dst_data(r_invalid_sprites));
    cdc_word u_cache_cycles (.src_clk(mem_clk),.src_data(cache_cycles),.dst_clk(hclk),.dst_data(r_cache_cycles));
    cdc_word u_cache_loads (.src_clk(mem_clk),.src_data(cache_loads),.dst_clk(hclk),.dst_data(r_cache_loads));
    cdc_word u_max_sprites (.src_clk(mem_clk),.src_data(max_sprites),.dst_clk(hclk),.dst_data(r_max_sprites));
    cdc_word u_max_sprite_pixels (.src_clk(mem_clk),.src_data(max_sprite_pixels),.dst_clk(hclk),.dst_data(r_max_sprite_pixels));
    cdc_word u_max_cycles (.src_clk(mem_clk),.src_data(max_cycles),.dst_clk(hclk),.dst_data(r_max_cycles));
    cdc_word u_invalid_layers (.src_clk(mem_clk),.src_data(invalid_layers),.dst_clk(hclk),.dst_data(r_invalid_layers));
    cdc_word u_base (.src_clk(pixel_clk), .src_data(active_base), .dst_clk(hclk), .dst_data(r_base));
    cdc_word u_frames (.src_clk(pixel_clk), .src_data(frames), .dst_clk(hclk), .dst_data(r_frames));
    cdc_word u_underflows (.src_clk(pixel_clk), .src_data(underflows), .dst_clk(hclk), .dst_data(r_underflows));
    cdc_word u_checksum (.src_clk(mem_clk), .src_data(frame_checksum), .dst_clk(hclk), .dst_data(r_checksum));
    cdc_word u_fetch_frames (.src_clk(mem_clk), .src_data(fetch_frames), .dst_clk(hclk), .dst_data(r_fetch_frames));
    reg [1:0] enabled_sync;
    reg [1:0] layers_sync;
    reg [1:0] sprites_sync;
    always @(posedge hclk) begin
        if (!hresetn) begin enabled_sync <= 0;layers_sync<=0;sprites_sync<=0;end
        else begin enabled_sync <= {enabled_sync[0], active_enable};layers_sync<={layers_sync[0],active_layers};sprites_sync<={sprites_sync[0],active_sprites};end
    end
    always @* begin
        case (bus_addr)
            12'h000: hrdata = 32'h47505531; // GPU1
            12'h004: hrdata = shadow_base;
            12'h008: hrdata = {31'b0, shadow_enable};
            12'h00c: hrdata = {31'b0, busy};
            12'h010: hrdata = r_base;
            12'h014: hrdata = {31'b0, enabled_sync[1]};
            12'h018: hrdata = r_frames;
            12'h01c: hrdata = r_underflows;
            12'h020: hrdata = r_checksum;
            12'h024: hrdata = r_fetch_frames;
            12'h028: hrdata = 16;
            12'h02c: hrdata = r_max_cycles;
            12'h030: hrdata = {31'b0,shadow_layers};
            12'h034: hrdata = {31'b0,layers_sync[1]};
            12'h038: hrdata = r_invalid_layers;
            12'h03c: hrdata = 64;
            12'h040: hrdata = {31'b0,shadow_sprites};
            12'h044: hrdata = {31'b0,sprites_sync[1]};
            12'h048: hrdata = r_invalid_sprites;
            12'h04c: hrdata = r_max_sprites;
            12'h050: hrdata = r_cache_cycles;
            12'h054: hrdata = r_max_sprite_pixels;
            12'h058: hrdata = r_cache_loads;
            default: hrdata = 0;
        endcase
    end

    // Pixel domain: line requests sent during blanking, one line ahead.
    reg [10:0] hx = 0;
    reg [9:0] vy = 0;
    wire visible_y = vy >= V_START && vy < V_START + HEIGHT;
    wire visible = visible_y && hx >= H_START && hx < H_START + WIDTH;
    wire [9:0] x = hx[9:0] - H_START[9:0];
    wire [8:0] y = vy[8:0] - V_START[8:0];
    wire vblank_start = hx == 0 && vy == V_START + HEIGHT;
    reg [1:0] commit_sync = 0, ack_sync = 0;
    reg request_toggle = 0, acknowledge = 0, ack_seen = 0;
    reg [31:0] request_base = 0;
    reg request_layers=0,request_bank=0;
    reg request_sprites=0;
    reg [40:0] request_tag = 0;
    reg [40:0] ready_tag [0:1];
    reg [1:0] ready_valid = 0;
    reg line_good = 0;
    wire request_idle = request_toggle == ack_sync[1];
    wire commit_pending = commit_sync[1] != applied_toggle;
    wire [31:0] next_base = commit_pending ? mailbox_base : active_base;
    wire next_enable = commit_pending ? mailbox_enable : active_enable;
    wire next_layers = commit_pending ? mailbox_layers : active_layers;
    wire next_bank = commit_pending ? mailbox_bank : active_bank;
    wire next_sprites = commit_pending ? mailbox_sprites : active_sprites;
    wire [31:0] next_frame = frames + 1'b1;
    always @(posedge pixel_clk) begin
        if (!prst[1]) begin
            hx <= 0; vy <= 0; frames <= 0; underflows <= 0;
            commit_sync <= 0; applied_toggle <= 0;
            active_base <= 0; active_enable <= 0;
            active_layers<=0;active_bank<=0;request_layers<=0;request_bank<=0;
            active_sprites<=0;request_sprites<=0;
            request_toggle <= 0; request_base <= 0; request_tag <= 0;
            ack_sync <= 0; ack_seen <= 0; ready_valid <= 0; line_good <= 0;
        end else begin
            commit_sync <= {commit_sync[0], commit_toggle};
            ack_sync <= {ack_sync[0], acknowledge};
            if (hx == H_TOTAL - 1) begin
                hx <= 0;
                if (vy == V_TOTAL - 1) vy <= 0; else vy <= vy + 1'b1;
            end else hx <= hx + 1'b1;
            if (ack_seen != ack_sync[1]) begin
                ready_tag[request_tag[0]] <= request_tag;
                ready_valid[request_tag[0]] <= 1;
                ack_seen <= ack_sync[1];
            end
            if (vblank_start) begin
                frames <= frames + 1'b1;
                ready_valid <= 0;
                // Wait for old work before recycling its descriptor bank.
                if (commit_pending && request_idle) begin
                    active_base <= mailbox_base; active_enable <= mailbox_enable;
                    active_layers<=mailbox_layers;active_bank<=mailbox_bank;
                    active_sprites<=mailbox_sprites;
                    applied_toggle <= commit_sync[1];
                end
                if (next_enable && request_idle) begin
                    request_base <= next_base;
                    request_layers<=next_layers;request_bank<=next_bank;
                    request_sprites<=next_sprites;
                    request_tag <= {next_frame, 9'd0};
                    request_toggle <= ~request_toggle;
                end
            end
            if (hx == 0 && visible_y) begin
                line_good <= ready_valid[y[0]] && ready_tag[y[0]] == {frames, y};
                if (active_enable && !(ready_valid[y[0]] && ready_tag[y[0]] == {frames, y}))
                    underflows <= underflows + 1'b1;
                if (active_enable && y < HEIGHT - 1 && request_idle) begin
                    request_base <= active_base + ({23'b0, y} + 32'd1) * WIDTH;
                    request_layers<=active_layers;request_bank<=active_bank;
                    request_sprites<=active_sprites;
                    request_tag <= {frames, y + 9'd1};
                    request_toggle <= ~request_toggle;
                end
            end
        end
    end

    // Memory domain: whole lines are composed before becoming visible.
    reg [255:0] lines [0:63];
    reg [1:0] request_sync = 0;
    reg [40:0] tag = 0;
    reg reader_start=0,current_layers=0,done_pending=0;
    reg cache_start=0,prefetch_active=0,line_pending=0;
    wire cache_done,cache_busy,cache_fetch_valid,reader_fetch_valid;
    wire [28:0] cache_fetch_addr,reader_fetch_addr;
    wire [3:0] sprite_head_layer;
    wire [6:0] sprite_head_index;
    wire [5:0] sprite_index;
    wire [63:0] sprite_metadata;
    wire [10:0] sprite_row_address;
    wire [255:0] sprite_row_data;
    assign fetch_valid=prefetch_active ? cache_fetch_valid : reader_fetch_valid;
    assign fetch_addr=prefetch_active ? cache_fetch_addr : reader_fetch_addr;
    wire reader_busy,reader_done,block_valid;
    wire [4:0] block_index;
    wire [255:0] block_data;
    // Cut the DDR arbiter's tag decode from the high-fanout line RAM enables.
    // Data runs continuously so the tag decode only drives one valid register.
    reg [255:0] returned_data;
    reg returned_valid=0;
    always @(posedge mem_clk) begin
        returned_data<=fetch_data;
        returned_valid<=mrst[1] && fetch_data_valid;
    end
    gpu_line_reader #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) u_reader (
        .clk(mem_clk),.resetn(mrst[1]),.start(reader_start),.layers(request_layers),.config_bank(request_bank),
        .sprites(request_sprites && request_layers),
        .base(request_base),.line_y(request_tag[8:0]),.busy(reader_busy),.done(reader_done),
        .config_address(config_address),.config_data(config_data),
        .fetch_valid(reader_fetch_valid),.fetch_addr(reader_fetch_addr),.fetch_ready(fetch_ready && !prefetch_active),.fetch_data(returned_data),.fetch_data_valid(returned_valid && !prefetch_active),
        .block_valid(block_valid),.block_index(block_index),.block_data(block_data),.max_cycles(max_cycles),.invalid_layers(invalid_layers),
        .sprite_head_layer(sprite_head_layer),.sprite_head_index(sprite_head_index),.sprite_index(sprite_index),.sprite_metadata(sprite_metadata),
        .sprite_row_address(sprite_row_address),.sprite_row_data(sprite_row_data),.max_sprites(max_sprites),.max_sprite_pixels(max_sprite_pixels));
    gpu_sprite_cache u_sprites (
        .clk(mem_clk),.resetn(mrst[1]),.start(cache_start),.config_bank(request_bank),.busy(cache_busy),.done(cache_done),
        .config_address(sprite_config_address),.config_data(sprite_config_data),
        .fetch_valid(cache_fetch_valid),.fetch_addr(cache_fetch_addr),.fetch_ready(fetch_ready && prefetch_active),
        .fetch_data(returned_data),.fetch_data_valid(returned_valid && prefetch_active),
        .head_layer(sprite_head_layer),.head_index(sprite_head_index),.meta_index(sprite_index),.meta_data(sprite_metadata),
        .row_address(sprite_row_address),.row_data(sprite_row_data),.invalid_sprites(invalid_sprites),.max_cycles(cache_cycles),.loads(cache_loads));
    reg [31:0] checksum = 0;
    function [31:0] rotate; input [31:0] v;input integer n;
        rotate=(v<<n)|(v>>(32-n));
    endfunction
    reg [31:0] pair0,pair1,pair2,pair3,hash0,hash1,burst_sum,burst_hash;
    reg check_valid1=0,check_valid2=0;
    always @(posedge mem_clk) begin
        check_valid1<=mrst[1] && block_valid;check_valid2<=mrst[1] && check_valid1;
        if(block_valid) begin
            pair0<=block_data[31:0]+block_data[63:32];pair1<=block_data[95:64]+block_data[127:96];
            pair2<=block_data[159:128]+block_data[191:160];pair3<=block_data[223:192]+block_data[255:224];
            hash0<=block_data[31:0]^rotate(block_data[63:32],4)^rotate(block_data[95:64],8)^rotate(block_data[127:96],12);
            hash1<=rotate(block_data[159:128],16)^rotate(block_data[191:160],20)^rotate(block_data[223:192],24)^rotate(block_data[255:224],28);
        end
        if(check_valid1) begin burst_sum<=pair0+pair1+pair2+pair3;burst_hash<=hash0^hash1;end
    end
    always @(posedge mem_clk) begin
        if (!mrst[1]) begin
            request_sync <= 0; acknowledge <= 0;reader_start<=0;current_layers<=0;done_pending<=0;tag <= 0;
            cache_start<=0;prefetch_active<=0;line_pending<=0;
            checksum <= 0; frame_checksum <= 0; fetch_frames <= 0;
        end else begin
            request_sync <= {request_sync[0], request_toggle};
            reader_start<=0;cache_start<=0;
            if(cache_done) begin prefetch_active<=0;reader_start<=1;end
            done_pending<=reader_done;
            if (done_pending) begin
                acknowledge<=request_sync[1];
                line_pending<=0;
                if(tag[8:0]==HEIGHT-1) begin frame_checksum<=checksum;fetch_frames<=fetch_frames+1'b1;end
            end else if(!line_pending && request_sync[1]!=acknowledge) begin
                tag<=request_tag;current_layers<=request_layers;line_pending<=1;
                if(request_layers && request_sprites && request_tag[8:0]==0) begin cache_start<=1;prefetch_active<=1;end
                else reader_start<=1;
                if(request_tag[8:0]==0) checksum<=0;
            end
            if(check_valid2) checksum<=current_layers ? rotate(checksum,5)^burst_hash : checksum+burst_sum;
        end
    end
    always @(posedge mem_clk)
        if (mrst[1] && block_valid) lines[{tag[0], block_index}] <= block_data;

    // Synchronous line RAM -> byte selection -> synchronous palette RAM.
    // Control signals take the same two cycles as RGB. DE stays stable across
    // the rising LCD clock edge (no combinational clock gating).
    reg [255:0] pixel_word;
    reg [4:0] byte_index;
    reg de1 = 0, de2 = 0, hs1 = 1, hs2 = 1, vs1 = 1, vs2 = 1;
    reg good1 = 0, good2 = 0, en1 = 0, en2 = 0;
    reg [17:0] rgb, fallback1, fallback2;
    always @(posedge pixel_clk) begin
        pixel_word <= lines[{y[0], x[9:5]}];
        byte_index <= x[4:0];
        rgb <= palette[pixel_word[byte_index * 8 +: 8]];
        de1 <= visible && prst[1]; de2 <= de1;
        hs1 <= hx >= H_SYNC; hs2 <= hs1;
        vs1 <= vy >= V_SYNC; vs2 <= vs1;
        good1 <= line_good; good2 <= good1;
        en1 <= active_enable; en2 <= en1;
        fallback1 <= {6{x[7:5]}}; fallback2 <= fallback1;
    end
    wire [17:0] out_rgb = !en2 ? fallback2 : good2 ? rgb : 18'b0;
    assign lcd_en = de2;
    assign lcd_hs = hs2;
    assign lcd_vs = vs2;
    assign {lcd_r, lcd_g, lcd_b} = de2 ? out_rgb : 18'b0;
endmodule
`default_nettype wire
