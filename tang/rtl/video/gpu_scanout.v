// G1: one 800x480 indexed framebuffer, native DDR3 reads, two line buffers.
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
    reg applied_toggle = 0;
    reg [1:0] applied_sync;
    reg [11:0] bus_addr;
    reg bus_write;
    wire busy = commit_toggle != applied_sync[1];
    assign hready = !(bus_write && bus_addr == 12'h00c && busy);
    wire write_fire = bus_write && hready;
    reg [17:0] palette [0:255];
    always @(posedge hclk) begin
        if (!hresetn) begin
            shadow_base <= 0; shadow_enable <= 0;
            mailbox_base <= 0; mailbox_enable <= 0;
            commit_toggle <= 0; applied_sync <= 0;
            bus_addr <= 0; bus_write <= 0;
        end else begin
            applied_sync <= {applied_sync[0], applied_toggle};
            if (hready) begin
                bus_addr <= haddr[11:0];
                bus_write <= hsel && htrans[1] && hwrite;
            end
            if (write_fire) case (bus_addr)
                12'h004: shadow_base <= {2'b0, hwdata[29:5], 5'b0};
                12'h008: shadow_enable <= hwdata[0];
                12'h00c: if (hwdata[0]) begin
                    mailbox_base <= shadow_base;
                    mailbox_enable <= shadow_enable;
                    commit_toggle <= ~commit_toggle;
                end
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
    wire [31:0] r_base, r_frames, r_underflows, r_checksum, r_fetch_frames;
    reg [31:0] frame_checksum = 0, fetch_frames = 0;
    cdc_word u_base (.src_clk(pixel_clk), .src_data(active_base), .dst_clk(hclk), .dst_data(r_base));
    cdc_word u_frames (.src_clk(pixel_clk), .src_data(frames), .dst_clk(hclk), .dst_data(r_frames));
    cdc_word u_underflows (.src_clk(pixel_clk), .src_data(underflows), .dst_clk(hclk), .dst_data(r_underflows));
    cdc_word u_checksum (.src_clk(mem_clk), .src_data(frame_checksum), .dst_clk(hclk), .dst_data(r_checksum));
    cdc_word u_fetch_frames (.src_clk(mem_clk), .src_data(fetch_frames), .dst_clk(hclk), .dst_data(r_fetch_frames));
    reg [1:0] enabled_sync;
    always @(posedge hclk) begin
        if (!hresetn) enabled_sync <= 0;
        else enabled_sync <= {enabled_sync[0], active_enable};
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
    reg [40:0] request_tag = 0;
    reg [40:0] ready_tag [0:1];
    reg [1:0] ready_valid = 0;
    reg line_good = 0;
    wire request_idle = request_toggle == ack_sync[1];
    wire commit_pending = commit_sync[1] != applied_toggle;
    wire [31:0] next_base = commit_pending ? mailbox_base : active_base;
    wire next_enable = commit_pending ? mailbox_enable : active_enable;
    wire [31:0] next_frame = frames + 1'b1;
    always @(posedge pixel_clk) begin
        if (!prst[1]) begin
            hx <= 0; vy <= 0; frames <= 0; underflows <= 0;
            commit_sync <= 0; applied_toggle <= 0;
            active_base <= 0; active_enable <= 0;
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
                if (commit_pending) begin
                    active_base <= mailbox_base; active_enable <= mailbox_enable;
                    applied_toggle <= commit_sync[1];
                end
                if (next_enable && request_idle) begin
                    request_base <= next_base;
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
                    request_tag <= {frames, y + 9'd1};
                    request_toggle <= ~request_toggle;
                end
            end
        end
    end

    // Memory domain: one outstanding read suffices for G1. Each response writes
    // 32 pixels at once. Bank bit is Y[0]; no concurrent writer to a displayed line.
    reg [255:0] lines [0:63];
    reg [1:0] request_sync = 0;
    reg [1:0] state = 0;
    reg [4:0] burst_index = 0;
    reg [28:0] address = 0;
    reg [40:0] tag = 0;
    reg [31:0] checksum = 0;
    wire [31:0] burst_sum = fetch_data[31:0] + fetch_data[63:32] + fetch_data[95:64] + fetch_data[127:96]
                         + fetch_data[159:128] + fetch_data[191:160] + fetch_data[223:192] + fetch_data[255:224];
    assign fetch_valid = state == 1 && mrst[1];
    assign fetch_addr = address;
    always @(posedge mem_clk) begin
        if (!mrst[1]) begin
            request_sync <= 0; acknowledge <= 0; state <= 0;
            burst_index <= 0; address <= 0; tag <= 0;
            checksum <= 0; frame_checksum <= 0; fetch_frames <= 0;
        end else begin
            request_sync <= {request_sync[0], request_toggle};
            case (state)
                0: if (request_sync[1] != acknowledge) begin
                    address <= request_base[30:2]; tag <= request_tag; burst_index <= 0;
                    if (request_tag[8:0] == 0) checksum <= 0;
                    state <= 1;
                end
                1: if (fetch_ready) state <= 2;
                2: if (fetch_data_valid) begin
                    checksum <= checksum + burst_sum;
                    if ({27'b0, burst_index} == BURSTS - 1) begin
                        acknowledge <= request_sync[1]; state <= 0;
                        if (tag[8:0] == HEIGHT - 1) begin
                            frame_checksum <= checksum + burst_sum;
                            fetch_frames <= fetch_frames + 1'b1;
                        end
                    end else begin
                        burst_index <= burst_index + 1'b1; address <= address + 29'd8;
                        state <= 1;
                    end
                end
                default: state <= 0;
            endcase
        end
    end
    always @(posedge mem_clk)
        if (mrst[1] && state == 2 && fetch_data_valid)
            lines[{tag[0], burst_index}] <= fetch_data;

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
