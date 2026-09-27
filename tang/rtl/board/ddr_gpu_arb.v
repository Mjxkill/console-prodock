// Shared native DDR3 UI: CPU adapter, scanout reads and blitter reads/writes.
// Addresses are 32-bit words, aligned to eight words (32 bytes).
// CPU upstream issues command+data pulses only when ready; capture them in a
// one-entry buffer to break the ready chain through the legacy CPU adapter.
// Scanout has priority for bounded line fetches; CPU/blitter alternate otherwise.
`default_nettype none
module ddr_gpu_arb (
    input wire clk, rst_n,
    input wire c_en,
    input wire [2:0] c_cmd,
    input wire [28:0] c_addr,
    output wire c_ready,
    input wire c_wr_en, c_wr_end,
    input wire [255:0] c_wr_data,
    input wire [31:0] c_wr_mask,
    output wire c_wr_ready,
    output wire [255:0] c_rd_data,
    output wire c_rd_valid, c_rd_end,
    input wire g_valid,
    input wire [28:0] g_addr,
    output wire g_ready,
    output wire [255:0] g_data,
    output wire g_data_valid,
    input wire b_valid, b_write,
    input wire [28:0] b_addr,
    input wire [255:0] b_wr_data,
    input wire [31:0] b_wr_mask,
    output wire b_ready,
    output wire [255:0] b_rd_data,
    output wire b_rd_valid,
    output wire m_en,
    output wire [2:0] m_cmd,
    output wire [28:0] m_addr,
    input wire m_ready,
    output wire m_wr_en, m_wr_end,
    output wire [255:0] m_wr_data,
    output wire [31:0] m_wr_mask,
    input wire m_wr_ready,
    input wire [255:0] m_rd_data,
    input wire m_rd_valid, m_rd_end
);
    reg [1:0] tags [0:15]; // 0 CPU, 1 scanout, 2 blitter
    reg [4:0] wp = 0, rp = 0;
    reg full = 0;
    wire empty = wp == rp;
    wire issue = rst_n && !full;
    reg cpu_pending = 0;
    reg [2:0] cpu_cmd;
    reg [28:0] cpu_addr;
    reg [255:0] cpu_data;
    reg [31:0] cpu_mask;
    reg prefer_blitter = 1;
    wire take_blitter = b_valid && (prefer_blitter || !cpu_pending);
    assign g_ready = issue && m_ready;
    assign b_ready = issue && !g_valid && take_blitter && m_ready && (!b_write || m_wr_ready);
    assign c_ready = rst_n && !cpu_pending;
    assign c_wr_ready = c_ready;
    wire cpu_fire = issue && !g_valid && !take_blitter && cpu_pending && m_ready && (cpu_cmd != 0 || m_wr_ready);
    assign m_en = (g_valid && g_ready) || (b_valid && b_ready) || cpu_fire;
    assign m_cmd = g_valid ? 3'b001 : take_blitter ? {2'b0,!b_write} : cpu_cmd;
    assign m_addr = g_valid ? g_addr : take_blitter ? b_addr : cpu_addr;
    assign m_wr_en = (b_valid && b_ready && b_write) || (cpu_fire && cpu_cmd == 0);
    assign m_wr_end = m_wr_en;
    assign m_wr_data = take_blitter ? b_wr_data : cpu_data;
    assign m_wr_mask = take_blitter ? b_wr_mask : cpu_mask;
    wire push = (g_valid && g_ready) || (b_valid && b_ready && !b_write) || (cpu_fire && cpu_cmd == 1);
    wire pop = m_rd_valid && !empty;
    wire [4:0] next_wp = wp + {4'b0, push};
    wire [4:0] next_rp = rp + {4'b0, pop};
    always @(posedge clk) begin
        if (!rst_n) begin
            wp <= 0; rp <= 0; full <= 0; prefer_blitter <= 1;
            cpu_pending <= 0; cpu_cmd <= 0; cpu_addr <= 0; cpu_data <= 0; cpu_mask <= 32'hffffffff;
        end
        else begin
            if (c_en && c_ready) begin
                cpu_pending <= 1; cpu_cmd <= c_cmd; cpu_addr <= c_addr;
                cpu_data <= c_wr_data; cpu_mask <= c_wr_mask;
            end else if (cpu_fire) cpu_pending <= 0;
            if (!g_valid) begin
                if (b_valid && b_ready) prefer_blitter <= 0;
                else if (cpu_fire) prefer_blitter <= 1;
            end
            if (push) tags[wp[3:0]] <= g_valid ? 2'd1 : take_blitter ? 2'd2 : 2'd0;
            wp <= next_wp; rp <= next_rp;
            full <= (next_wp[4] != next_rp[4]) && (next_wp[3:0] == next_rp[3:0]);
        end
    end
    assign c_rd_data = m_rd_data;
    assign g_data = m_rd_data;
    assign c_rd_valid = pop && tags[rp[3:0]] == 0;
    assign c_rd_end = c_rd_valid && m_rd_end;
    assign g_data_valid = pop && tags[rp[3:0]] == 1;
    assign b_rd_data = m_rd_data;
    assign b_rd_valid = pop && tags[rp[3:0]] == 2;
endmodule
`default_nettype wire
