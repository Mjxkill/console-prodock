// G4: framebuffer or 16 layers + 64 cached sprites, two display lines.
// Three existing clocks only: AHB 80 MHz, DDR UI 75 MHz, LCD 35 MHz.
// Mailboxes hold multi-bit data stable until a synchronized acknowledgement.
`default_nettype none
module gpu_scanout #(
    parameter WIDTH = 800, HEIGHT = 480,
    parameter H_TOTAL = 1193, V_TOTAL = 533,
    parameter H_START = 182, V_START = 8,
    parameter H_SYNC = 210, V_SYNC = 45,
    parameter X_BITS = (WIDTH > 1024 ? 11 : 10),
    parameter Y_BITS = (HEIGHT > 512 ? 10 : 9)
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
    output wire [5:0] lcd_r, lcd_g, lcd_b,
    output wire [95:0] scan_debug_state
);
    localparam BURSTS = WIDTH / 32;
    // Supported boards: 800x480 and 1280x720; WIDTH is divisible by 32.
    localparam BLOCK_BITS = X_BITS-5;
    localparam RGB_BITS = X_BITS-4;
    localparam TAG_BITS = 32+Y_BITS;
    // syn_preserve : le même synchroniseur de reset existe dans gpu_accel ; fusionnés, l'un des deux
    // modules recevrait son reset de l'autre bout de la puce.
    reg [1:0] prst = 0;
    reg [1:0] mrst /* synthesis syn_preserve=1 */ = 0;
    always @(posedge pixel_clk or negedge hresetn)
        if (!hresetn) prst <= 0; else prst <= {prst[0], 1'b1};
    always @(posedge mem_clk or negedge hresetn)
        if (!hresetn) mrst <= 0; else mrst <= {mrst[0], 1'b1};

    reg [31:0] shadow_base, mailbox_base;
    reg shadow_enable, mailbox_enable, commit_toggle;
    reg shadow_rgb565,mailbox_rgb565;
    reg shadow_half,mailbox_half;
    reg [15:0] shadow_stride,mailbox_stride;
    reg active_half=0,request_half=0;
    reg [15:0] active_stride=0;
    reg [31:0] row_pointer=0;
    reg shadow_layers,mailbox_layers,mailbox_bank,write_bank;
    reg shadow_sprites,mailbox_sprites;
    reg clear_toggle; // L11: a write to 0x02c restarts the load maxima
    reg applied_toggle = 0;
    reg [1:0] applied_sync;
    reg [11:0] bus_addr;
    reg bus_write,guarded_write;
    wire busy = commit_toggle != applied_sync[1];
    wire layer_table_access=bus_addr[11:9]==3'b100;
    wire sprite_table_access=bus_addr[11:10]==2'b11;
    wire table_access=layer_table_access || sprite_table_access;
    // Decode the addresses that wait for a commit during the address phase.
    // HREADY then avoids a full address comparator on the CPU return path.
    assign hready = !(guarded_write && busy);
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
            shadow_rgb565<=0;mailbox_rgb565<=0;shadow_half<=0;mailbox_half<=0;shadow_stride<=0;mailbox_stride<=0;
            commit_toggle <= 0; applied_sync <= 0;
            shadow_layers<=0;mailbox_layers<=0;mailbox_bank<=0;write_bank<=1;
            shadow_sprites<=0;mailbox_sprites<=0;clear_toggle<=0;
            bus_addr <= 0; bus_write <= 0;guarded_write<=0;
        end else begin
            applied_sync <= {applied_sync[0], applied_toggle};
            if (hready) begin
                bus_addr <= haddr[11:0];
                bus_write <= hsel && htrans[1] && hwrite;
                guarded_write <= hsel && htrans[1] && hwrite &&
                    (haddr[11:0]==12'h00c || haddr[11:9]==3'b100 || haddr[11:10]==2'b11);
            end
            if (write_fire) case (bus_addr)
                12'h004: shadow_base <= {2'b0, hwdata[29:5], 5'b0};
                12'h008:begin shadow_enable <= hwdata[0];shadow_rgb565<=hwdata[1];shadow_half<=hwdata[2] && hwdata[1];end
                12'h00c: if (hwdata[0]) begin
                    mailbox_base <= shadow_base;
                    mailbox_enable <= shadow_enable;
                    mailbox_layers<=shadow_layers;mailbox_bank<=write_bank;
                    mailbox_sprites<=shadow_sprites;
                    mailbox_rgb565<=shadow_rgb565;mailbox_half<=shadow_half;mailbox_stride<=shadow_stride;
                    if(shadow_layers) write_bank<=~write_bank;
                    commit_toggle <= ~commit_toggle;
                end
                12'h06c:shadow_stride<={hwdata[15:5],5'b0};
                12'h02c: clear_toggle<=~clear_toggle;
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
    reg underflow_pending = 0;
    reg active_enable = 0;
    reg active_rgb565=0,request_rgb565=0;
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
    reg [31:0] display_checksum=0,display_sum=0,total_cycles=0,line_elapsed=0;
    wire [31:0] r_display_checksum,r_total_cycles;
    cdc_word u_display_checksum (.src_clk(pixel_clk),.src_data(display_checksum),.dst_clk(hclk),.dst_data(r_display_checksum));
    cdc_word u_total_cycles (.src_clk(mem_clk),.src_data(total_cycles),.dst_clk(hclk),.dst_data(r_total_cycles));
    always @(posedge mem_clk)begin
        if(!mrst[1])begin total_cycles<=0;line_elapsed<=0;end
        else begin
            if(!line_pending)line_elapsed<=0;else line_elapsed<=line_elapsed+1'b1;
            if(clear_maxima)total_cycles<=0;
            else if(done_pending && tag[Y_BITS-1:0]!=0 && line_elapsed>total_cycles)total_cycles<=line_elapsed;
        end
    end
    reg [1:0] enabled_sync;
    reg [1:0] layers_sync;
    reg [1:0] sprites_sync;
    always @(posedge hclk) begin
        if (!hresetn) begin enabled_sync <= 0;layers_sync<=0;sprites_sync<=0;end
        else begin enabled_sync <= {enabled_sync[0], active_enable};layers_sync<={layers_sync[0],active_layers};sprites_sync<={sprites_sync[0],active_sprites};end
    end
    // Decode read addresses in the existing AHB address phase. The data
    // phase only gates/ORs register values; read latency is unchanged.
    reg [29:0] read_select;
    genvar reg_index;
    generate for (reg_index=0; reg_index<30; reg_index=reg_index+1) begin: read_decode
        always @(posedge hclk)
            if (!hresetn) read_select[reg_index] <= (reg_index == 0);
            else if (hready) read_select[reg_index] <= (haddr[11:0] == reg_index*4);
    end endgenerate
    always @* begin
        hrdata =
            ({32{read_select[0]}} & (32'h47505531)) |
            ({32{read_select[1]}} & (shadow_base)) |
            ({32{read_select[2]}} & ({29'b0,shadow_half,shadow_rgb565,shadow_enable})) |
            ({32{read_select[3]}} & ({31'b0, busy})) |
            ({32{read_select[4]}} & (r_base)) |
            ({32{read_select[5]}} & ({31'b0, enabled_sync[1]})) |
            ({32{read_select[6]}} & (r_frames)) |
            ({32{read_select[7]}} & (r_underflows)) |
            ({32{read_select[8]}} & (r_checksum)) |
            ({32{read_select[9]}} & (r_fetch_frames)) |
            ({32{read_select[10]}} & (16)) |
            ({32{read_select[11]}} & (r_max_cycles)) |
            ({32{read_select[12]}} & ({31'b0,shadow_layers})) |
            ({32{read_select[13]}} & ({31'b0,layers_sync[1]})) |
            ({32{read_select[14]}} & (r_invalid_layers)) |
            ({32{read_select[15]}} & (64)) |
            ({32{read_select[16]}} & ({31'b0,shadow_sprites})) |
            ({32{read_select[17]}} & ({31'b0,sprites_sync[1]})) |
            ({32{read_select[18]}} & (r_invalid_sprites)) |
            ({32{read_select[19]}} & (r_max_sprites)) |
            ({32{read_select[20]}} & (r_cache_cycles)) |
            ({32{read_select[21]}} & (r_max_sprite_pixels)) |
            ({32{read_select[22]}} & (r_cache_loads)) |
            ({32{read_select[23]}} & (32'h00000d07)) |
            ({32{read_select[24]}} & (r_display_checksum)) |
            ({32{read_select[25]}} & (r_total_cycles)) |
            ({32{read_select[26]}} & (32'h00000007)) | // overlays, x2, stride
            ({32{read_select[27]}} & {16'd0,shadow_stride}) |
            ({32{read_select[28]}} & ((HEIGHT << 16) | WIDTH)) |
            ({32{read_select[29]}} & ((V_TOTAL << 16) | H_TOTAL));
    end

    // Pixel domain: line requests sent during blanking, one line ahead.
    reg [10:0] hx = 0;
    reg [9:0] vy = 0;
    wire visible_y = vy >= V_START && vy < V_START + HEIGHT;
    wire visible = visible_y && hx >= H_START && hx < H_START + WIDTH;
    wire [X_BITS-1:0] x = hx[X_BITS-1:0] - H_START[X_BITS-1:0];
    wire [Y_BITS-1:0] y = vy[Y_BITS-1:0] - V_START[Y_BITS-1:0];
    wire vblank_start = hx == 0 && vy == V_START + HEIGHT;
    reg [1:0] commit_sync = 0, ack_sync = 0;
    reg request_toggle = 0, acknowledge = 0, ack_seen = 0;
    reg [31:0] request_base = 0;
    reg request_layers=0,request_bank=0;
    reg request_sprites=0;
    reg [TAG_BITS-1:0] request_tag = 0;
    reg [TAG_BITS-1:0] ready_tag [0:1];
    reg [1:0] ready_valid = 0;
    reg line_good = 0;
    wire request_idle = request_toggle == ack_sync[1];
    wire commit_pending = commit_sync[1] != applied_toggle;
    wire [31:0] next_base = commit_pending ? mailbox_base : active_base;
    wire next_enable = commit_pending ? mailbox_enable : active_enable;
    wire next_rgb565=commit_pending ? mailbox_rgb565:active_rgb565;
    wire next_half=commit_pending ? mailbox_half:active_half;
    wire next_layers = commit_pending ? mailbox_layers : active_layers;
    wire next_bank = commit_pending ? mailbox_bank : active_bank;
    wire next_sprites = commit_pending ? mailbox_sprites : active_sprites;
    wire [31:0] next_frame = frames + 1'b1;
    // Select the byte stride with wiring, not a variable multiplication.
    // Keep the pixel-domain address adder separate from the format select;
    // a multiply-add lets synthesis absorb mailbox registers from hclk into
    // the same DSP as pixel-domain registers.
    wire [31:0] indexed_row_offset = ({{(32-Y_BITS){1'b0}}, y} + 32'd1) * WIDTH;
    wire [31:0] row_byte_offset = active_rgb565 ?
        {indexed_row_offset[30:0],1'b0} : indexed_row_offset;
    // Increment a row pointer instead of multiplying a cross-domain stride.
    // Both operands are pixel-clock registers; no mixed-clock DSP inference.
    wire [15:0] effective_stride=active_stride!=0 ? active_stride:
        active_rgb565 && !active_half ? WIDTH*2:WIDTH;
    wire [31:0] following_row=row_pointer+(active_half && !y[0] ? 16'd0:effective_stride);
    always @(posedge pixel_clk) begin
        if (!prst[1]) begin
            hx <= 0; vy <= 0; frames <= 0; underflows <= 0;
            underflow_pending <= 0;
            commit_sync <= 0; applied_toggle <= 0;
            active_base <= 0; active_enable <= 0;
            active_rgb565<=0;request_rgb565<=0;active_half<=0;request_half<=0;active_stride<=0;row_pointer<=0;
            active_layers<=0;active_bank<=0;request_layers<=0;request_bank<=0;
            active_sprites<=0;request_sprites<=0;
            request_toggle <= 0; request_base <= 0; request_tag <= 0;
            ack_sync <= 0; ack_seen <= 0; ready_valid <= 0; line_good <= 0;
        end else begin
            commit_sync <= {commit_sync[0], commit_toggle};
            // Neo: separate the wide line-tag comparison from the counter
            // enable. The event is counted one pixel later, still once/line.
            if (WIDTH > 1024) begin
                underflow_pending <= 0;
                if (underflow_pending) underflows <= underflows + 1'b1;
            end
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
                    active_rgb565<=mailbox_rgb565;active_half<=mailbox_half;active_stride<=mailbox_stride;
                    active_layers<=mailbox_layers;active_bank<=mailbox_bank;
                    active_sprites<=mailbox_sprites;
                    applied_toggle <= commit_sync[1];
                end
                if (next_enable && request_idle) begin
                    request_base <= next_base;row_pointer<=next_base;
                    request_rgb565<=next_rgb565;request_half<=next_half;
                    request_layers<=next_layers;request_bank<=next_bank;
                    request_sprites<=next_sprites;
                    request_tag <= {next_frame, {Y_BITS{1'b0}}};
                    request_toggle <= ~request_toggle;
                end
            end
            if (hx == 0 && visible_y) begin
                row_pointer<=following_row;
                line_good <= ready_valid[y[0]] && ready_tag[y[0]] == {frames, y};
                if (active_enable && !(ready_valid[y[0]] && ready_tag[y[0]] == {frames, y})) begin
                    if (WIDTH > 1024) underflow_pending <= 1;
                    else underflows <= underflows + 1'b1;
                end
                if (active_enable && y < HEIGHT - 1 && request_idle) begin
                    request_base <= active_rgb565 && (active_half || active_stride!=0) ? following_row:active_base + row_byte_offset;
                    request_rgb565<=active_rgb565;request_half<=active_half;
                    request_layers<=active_layers;request_bank<=active_bank;
                    request_sprites<=active_sprites;
                    request_tag <= {frames, y + {{(Y_BITS-1){1'b0}},1'b1}};
                    request_toggle <= ~request_toggle;
                end
            end
        end
    end

    // Memory domain: whole lines are composed before becoming visible.
    // Capture the held mailbox payload before it fans out to the 720p
    // engines. The source retains it until the completed-line ack returns.
    wire [31:0] line_base;
    wire line_rgb565,line_half,line_layers,line_bank,line_sprites;
    wire [Y_BITS-1:0] line_y;
    generate if(WIDTH>1024)begin:g_line_mailbox
        reg [31:0] base=0;
        reg rgb565=0,halfres=0,layers=0,bank=0,sprites=0;
        reg [Y_BITS-1:0] row=0;
        always @(posedge mem_clk)begin
            if(!mrst[1])begin base<=0;rgb565<=0;halfres<=0;layers<=0;bank<=0;sprites<=0;row<=0;end
            else if(!line_pending && request_sync[1]!=acknowledge)begin
                base<=request_base;rgb565<=request_rgb565;halfres<=request_half;
                layers<=request_layers;bank<=request_bank;sprites<=request_sprites;
                row<=request_tag[Y_BITS-1:0];
            end
        end
        assign line_base=base;assign line_rgb565=rgb565;assign line_half=halfres;
        assign line_layers=layers;assign line_bank=bank;assign line_sprites=sprites;assign line_y=row;
    end else begin:g_line_direct
        assign line_base=request_base;assign line_rgb565=request_rgb565;assign line_half=request_half;
        assign line_layers=request_layers;assign line_bank=request_bank;
        assign line_sprites=request_sprites;assign line_y=request_tag[Y_BITS-1:0];
    end endgenerate
    reg dispatch_line=0;
    reg [255:0] lines [0:(2<<RGB_BITS)-1];
    reg [255:0] overlay_lines [0:(2<<BLOCK_BITS)-1];
    reg [31:0] overlay_coverage [0:(2<<BLOCK_BITS)-1];
    reg rgb_start=0,rgb_phase=0;
    wire [31:0] block_coverage;
    reg [1:0] request_sync = 0;
    reg [TAG_BITS-1:0] tag = 0;
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
    wire rgb_fetch_valid,rgb_done,rgb_block_valid;
    wire [28:0] rgb_fetch_addr;
    wire [255:0] rgb_block_data;
    wire [RGB_BITS-1:0] rgb_block_index;
    // Each engine drains before the next starts; inactive engines have no
    // outstanding request. Keep the owner mux off the DDR arbitration path.
    assign fetch_valid=rgb_fetch_valid || cache_fetch_valid || reader_fetch_valid;
    assign fetch_addr=rgb_phase ? rgb_fetch_addr : prefetch_active ? cache_fetch_addr : reader_fetch_addr;
    wire reader_busy,reader_done,block_valid;
    wire [BLOCK_BITS-1:0] block_index;
    wire [255:0] block_data;
    // Cut the DDR arbiter's tag decode from the high-fanout line RAM enables.
    // Data runs continuously so the tag decode only drives one valid register.
    // (syn_preserve : voir gpu_raster.v, copie locale du bus de lecture DDR)
    reg [255:0] returned_data /* synthesis syn_preserve=1 */;
    reg returned_valid=0;
    reg [2:0] clear_sync=0;
    wire clear_maxima=clear_sync[2]!=clear_sync[1];
    always @(posedge mem_clk) begin
        returned_data<=fetch_data;
        returned_valid<=mrst[1] && fetch_data_valid;
        clear_sync<={clear_sync[1:0],clear_toggle};
    end
    gpu_line_reader #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) u_reader (
        .clk(mem_clk),.resetn(mrst[1]),.start(reader_start && (!line_rgb565 || line_layers)),.layers(line_layers),.config_bank(line_bank),
        .clear_maxima(clear_maxima),
        .sprites(line_sprites && line_layers),
        .base(line_base),.line_y(line_y),.busy(reader_busy),.done(reader_done),
        .config_address(config_address),.config_data(config_data),
        .fetch_valid(reader_fetch_valid),.fetch_addr(reader_fetch_addr),.fetch_ready(fetch_ready && !prefetch_active && !rgb_phase),.fetch_data(returned_data),.fetch_data_valid(returned_valid && !prefetch_active && !rgb_phase),
        .block_valid(block_valid),.block_index(block_index),.block_data(block_data),.block_coverage(block_coverage),.max_cycles(max_cycles),.invalid_layers(invalid_layers),
        .sprite_head_layer(sprite_head_layer),.sprite_head_index(sprite_head_index),.sprite_index(sprite_index),.sprite_metadata(sprite_metadata),
        .sprite_row_address(sprite_row_address),.sprite_row_data(sprite_row_data),.max_sprites(max_sprites),.max_sprite_pixels(max_sprite_pixels));
    gpu_rgb_reader #(.WIDTH(WIDTH)) u_rgb_reader (
        .clk(mem_clk),.resetn(mrst[1]),.start(rgb_start),.pipelined(line_layers || WIDTH>1024),.halfres(line_half),.base(line_base),
        .done(rgb_done),.fetch_valid(rgb_fetch_valid),.fetch_addr(rgb_fetch_addr),
        .fetch_ready(fetch_ready && rgb_phase),.fetch_data(returned_data),
        .fetch_data_valid(returned_valid && rgb_phase),
        .block_valid(rgb_block_valid),.block_index(rgb_block_index),.block_data(rgb_block_data),
        .scan_debug_state(scan_debug_state[95:64]));
    wire raw_block_valid=line_rgb565 ? rgb_block_valid:block_valid;
    wire [RGB_BITS-1:0] raw_block_index=line_rgb565 ? rgb_block_index:{1'b0,block_index};
    wire [255:0] raw_block_data=line_rgb565 ? rgb_block_data:block_data;
    // Neo's wider line RAM spans many physical banks. Register its write
    // enable and payload together, also cutting BRAM -> checksum arithmetic.
    reg staged_valid=0,staged_done=0;
    reg [RGB_BITS-1:0] staged_index;
    reg [255:0] staged_data;
    always @(posedge mem_clk)begin
        staged_valid<=mrst[1] && raw_block_valid;
        staged_done<=mrst[1] && (line_rgb565 ? rgb_done:reader_done);
        staged_index<=raw_block_index;staged_data<=raw_block_data;
    end
    wire output_block_valid=WIDTH>1024 ? staged_valid:raw_block_valid;
    wire [RGB_BITS-1:0] output_block_index=WIDTH>1024 ? staged_index:raw_block_index;
    wire [255:0] output_block_data=WIDTH>1024 ? staged_data:raw_block_data;
    gpu_sprite_cache u_sprites (
        .clk(mem_clk),.resetn(mrst[1]),.start(cache_start),.config_bank(line_bank),.busy(cache_busy),.done(cache_done),
        .clear_maxima(clear_maxima),
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
        check_valid1<=mrst[1] && output_block_valid;check_valid2<=mrst[1] && check_valid1;
        if(output_block_valid) begin
            pair0<=output_block_data[31:0]+output_block_data[63:32];pair1<=output_block_data[95:64]+output_block_data[127:96];
            pair2<=output_block_data[159:128]+output_block_data[191:160];pair3<=output_block_data[223:192]+output_block_data[255:224];
            hash0<=output_block_data[31:0]^rotate(output_block_data[63:32],4)^rotate(output_block_data[95:64],8)^rotate(output_block_data[127:96],12);
            hash1<=rotate(output_block_data[159:128],16)^rotate(output_block_data[191:160],20)^rotate(output_block_data[223:192],24)^rotate(output_block_data[255:224],28);
        end
        if(check_valid1) begin burst_sum<=pair0+pair1+pair2+pair3;burst_hash<=hash0^hash1;end
    end
    always @(posedge mem_clk) begin
        if (!mrst[1]) begin
            dispatch_line<=0;request_sync <= 0; acknowledge <= 0;reader_start<=0;current_layers<=0;done_pending<=0;tag <= 0;
            cache_start<=0;prefetch_active<=0;line_pending<=0;rgb_start<=0;rgb_phase<=0;
            checksum <= 0; frame_checksum <= 0; fetch_frames <= 0;
        end else begin
            request_sync <= {request_sync[0], request_toggle};
            reader_start<=0;cache_start<=0;rgb_start<=0;
            if(cache_done) begin prefetch_active<=0;reader_start<=1;end
            if(reader_done && line_rgb565)begin rgb_start<=1;rgb_phase<=1;end
            done_pending<=WIDTH>1024 ? staged_done:(line_rgb565 ? rgb_done:reader_done);
            if (done_pending) begin
                acknowledge<=request_sync[1];
                line_pending<=0;
                if(tag[Y_BITS-1:0]==HEIGHT-1) begin frame_checksum<=checksum;fetch_frames<=fetch_frames+1'b1;end
            end else if(!line_pending && request_sync[1]!=acknowledge) begin
                tag<=request_tag;line_pending<=1;
                if(WIDTH>1024)dispatch_line<=1;
                else begin
                    current_layers<=line_layers && !line_rgb565;
                    rgb_phase<=line_rgb565 && !line_layers;
                    if(line_layers && line_sprites && line_y==0) begin cache_start<=1;prefetch_active<=1;end
                    else if(line_rgb565 && !line_layers)rgb_start<=1;
                    else reader_start<=1;
                    if(line_y==0)checksum<=0;
                end
            end
            if(dispatch_line)begin
                dispatch_line<=0;current_layers<=line_layers && !line_rgb565;
                rgb_phase<=line_rgb565 && !line_layers;
                if(line_layers && line_sprites && line_y==0)begin cache_start<=1;prefetch_active<=1;end
                else if(line_rgb565 && !line_layers)rgb_start<=1;
                else reader_start<=1;
                if(line_y==0)checksum<=0;
            end
            if(check_valid2) checksum<=current_layers ? rotate(checksum,5)^burst_hash : checksum+burst_sum;
        end
    end
    always @(posedge mem_clk)
        if (mrst[1] && output_block_valid) lines[{tag[0], output_block_index}] <= output_block_data;

    always @(posedge mem_clk) begin
        if(mrst[1] && block_valid && line_rgb565 && line_layers)begin
            overlay_lines[{tag[0],block_index}]<=block_data;
            overlay_coverage[{tag[0],block_index}]<=block_coverage;
        end
    end

    // Synchronous line RAM -> byte selection -> synchronous palette RAM.
    // Control signals take the same two cycles as RGB. DE stays stable across
    // the rising LCD clock edge (no combinational clock gating).
    reg [255:0] pixel_word,overlay_word;
    reg [31:0] coverage_word;
    reg overlay1=0,overlay2=0,covered2=0;
    reg [4:0] byte_index;
    reg de1 = 0, de2 = 0, hs1 = 1, hs2 = 1, vs1 = 1, vs2 = 1;
    reg good1 = 0, good2 = 0, en1 = 0, en2 = 0;
    reg [17:0] rgb, fallback1, fallback2;
    reg [17:0] direct_rgb;
    reg format1=0,format2=0;
    wire [X_BITS-1:0] rgb_x=active_half ? {1'b0,x[X_BITS-1:1]}:x;
    reg [3:0] direct_index;
    wire [15:0] direct_pixel=pixel_word[direct_index*16+:16];
    wire [7:0] palette_address=overlay1 ? overlay_word[byte_index*8+:8]:pixel_word[byte_index*8+:8];
    reg [7:0] palette_address2;
    reg [31:0] palette_group2;
    reg [1:0] palette_byte2;
    // At 720p split the 32:1 byte selector into 8:1 and 4:1 stages,
    // followed by the palette RAM. Direct RGB and controls match all four
    // pixel cycles. The Pro Dock keeps its original two-cycle path.
    reg de3=0,hs3=1,vs3=1,good3=0,en3=0,format3=0,overlay3=0,covered3=0;
    reg [17:0] direct_rgb3,fallback3;
    reg de4=0,hs4=1,vs4=1,good4=0,en4=0,format4=0,overlay4=0,covered4=0;
    reg [17:0] direct_rgb4,fallback4;
    always @(posedge pixel_clk) begin
        pixel_word <= lines[{y[0], active_rgb565 ? rgb_x[X_BITS-1:4]:{1'b0,x[X_BITS-1:5]}}];
        overlay_word<=overlay_lines[{y[0],x[X_BITS-1:5]}];
        coverage_word<=overlay_coverage[{y[0],x[X_BITS-1:5]}];
        overlay1<=active_rgb565 && active_layers;overlay2<=overlay1;
        covered2<=coverage_word[byte_index];
        byte_index <= x[4:0];direct_index<=rgb_x[3:0];
        palette_group2<=overlay1 ? overlay_word[byte_index[4:2]*32+:32]:pixel_word[byte_index[4:2]*32+:32];
        palette_byte2<=byte_index[1:0];
        palette_address2<=palette_group2[palette_byte2*8+:8];
        rgb <= palette[WIDTH>1024 ? palette_address2:palette_address];
        direct_rgb<={direct_pixel[15:11],direct_pixel[15],direct_pixel[10:5],direct_pixel[4:0],direct_pixel[4]};
        format1<=active_rgb565;format2<=format1;
        de1 <= visible && prst[1]; de2 <= de1;
        hs1 <= hx >= H_SYNC; hs2 <= hs1;
        vs1 <= vy >= V_SYNC; vs2 <= vs1;
        good1 <= line_good; good2 <= good1;
        en1 <= active_enable; en2 <= en1;
        fallback1 <= {6{x[7:5]}}; fallback2 <= fallback1;
        de3<=de2;hs3<=hs2;vs3<=vs2;good3<=good2;en3<=en2;
        format3<=format2;overlay3<=overlay2;covered3<=covered2;
        direct_rgb3<=direct_rgb;fallback3<=fallback2;
        de4<=de3;hs4<=hs3;vs4<=vs3;good4<=good3;en4<=en3;
        format4<=format3;overlay4<=overlay3;covered4<=covered3;
        direct_rgb4<=direct_rgb3;fallback4<=fallback3;
    end
    wire out_de=WIDTH>1024 ? de4:de2;
    wire out_hs=WIDTH>1024 ? hs4:hs2;
    wire out_vs=WIDTH>1024 ? vs4:vs2;
    wire [17:0] out_rgb = WIDTH>1024 ?
        (!en4 ? fallback4 : good4 ? (format4 && !(overlay4 && covered4) ? direct_rgb4:rgb) : 18'b0):
        (!en2 ? fallback2 : good2 ? (format2 && !(overlay2 && covered2) ? direct_rgb:rgb) : 18'b0);
    reg was_vs=1;
    always @(posedge pixel_clk)begin
        if(!prst[1])begin display_checksum<=0;display_sum<=0;was_vs<=1;end
        else begin
            was_vs<=out_vs;
            if(was_vs && !out_vs)begin display_checksum<=display_sum;display_sum<=0;end
            else if(out_de)display_sum<=display_sum+{14'd0,out_rgb};
        end
    end
    assign lcd_en = out_de;
    assign lcd_hs = out_hs;
    assign lcd_vs = out_vs;
    assign {lcd_r, lcd_g, lcd_b} = out_de ? out_rgb : 18'b0;
    // Every observed state below belongs to mem_clk. No feedback to GPU.
    assign scan_debug_state[31:22]=line_y;
    assign scan_debug_state[21:0]={fetch_valid,returned_valid,line_sprites,line_layers,
        line_half,line_rgb565,prefetch_active,cache_busy,done_pending,reader_done,
        reader_start,rgb_done,rgb_start,rgb_phase,dispatch_line,line_pending,
        acknowledge,1'b0,request_sync,mrst};
    assign scan_debug_state[63:32]=line_base;
endmodule
`default_nettype wire
