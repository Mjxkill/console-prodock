// Shared native DDR3 UI: legacy CPU adapter + read-only 256-bit graphics port.
// Addresses are 32-bit words, aligned to eight words (32 bytes).
// CPU upstream issues pulses only when ready; GPU holds valid until ready.
// GPU has priority for bounded line fetches (25 bursts), CPU runs between lines.
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
    reg tags [0:15];
    reg [4:0] wp = 0, rp = 0;
    reg full = 0;
    wire empty = wp == rp;
    wire issue = rst_n && !full;
    assign g_ready = issue && m_ready;
    assign c_ready = issue && !g_valid && m_ready;
    assign c_wr_ready = issue && !g_valid && m_wr_ready;
    assign m_en = g_valid ? g_ready : c_en && issue;
    assign m_cmd = g_valid ? 3'b001 : c_cmd;
    assign m_addr = g_valid ? g_addr : c_addr;
    assign m_wr_en = c_wr_en && issue && !g_valid;
    assign m_wr_end = c_wr_end && issue && !g_valid;
    assign m_wr_data = c_wr_data;
    assign m_wr_mask = c_wr_mask;
    wire push = m_en && m_ready && m_cmd == 3'b001;
    wire pop = m_rd_valid && !empty;
    wire [4:0] next_wp = wp + {4'b0, push};
    wire [4:0] next_rp = rp + {4'b0, pop};
    always @(posedge clk) begin
        if (!rst_n) begin wp <= 0; rp <= 0; full <= 0; end
        else begin
            if (push) tags[wp[3:0]] <= g_valid;
            wp <= next_wp; rp <= next_rp;
            full <= (next_wp[4] != next_rp[4]) && (next_wp[3:0] == next_rp[3:0]);
        end
    end
    assign c_rd_data = m_rd_data;
    assign g_data = m_rd_data;
    assign c_rd_valid = pop && !tags[rp[3:0]];
    assign c_rd_end = c_rd_valid && m_rd_end;
    assign g_data_valid = pop && tags[rp[3:0]];
endmodule
`default_nettype wire
