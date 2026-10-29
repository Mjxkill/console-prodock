// Cross-client DDR composition bench.
// CPU128 -> ddr_ui_adapt -> ddr_gpu_arb <- scanout/blitter -> native_memory.
// The scoreboard builds its byte image only from high-level operations and
// compares each client response with an independently computed request value.
`timescale 1ns/1ps
module bench;

    // ---------------------------------------------------------------------
    // Clock/reset and public DUT ports
    // ---------------------------------------------------------------------
    reg clk = 1'b0;
    always #5 clk = ~clk;

    reg rst_n = 1'b0;

    // 128-bit CPU side of the adapter.
    reg         u_cmd_en = 0;
    reg  [2:0]  u_cmd = 0;
    reg  [28:0] u_addr = 0;
    wire        u_cmd_ready;
    reg         u_wr_data_en = 0;
    reg         u_wr_data_end = 0;
    reg  [127:0] u_wr_data = 0;
    reg  [15:0]  u_wr_data_mask = 0;
    wire        u_wr_data_rdy;
    wire [127:0] u_rd_data;
    wire        u_rd_data_valid;
    wire        u_rd_data_end;

    // Adapter 256-bit IP side, wired to the arbiter CPU port.
    wire        ip_cmd_en;
    wire [2:0]  ip_cmd;
    wire [28:0] ip_addr;
    wire        ip_cmd_ready;
    wire        ip_wr_data_en;
    wire        ip_wr_data_end;
    wire [255:0] ip_wr_data;
    wire [31:0]  ip_wr_data_mask;
    wire         ip_wr_data_rdy;
    wire [255:0] ip_rd_data;
    wire         ip_rd_data_valid;
    wire         ip_rd_data_end;

    // Scanout producer.
    reg         g_valid = 0;
    reg  [28:0] g_addr = 0;
    wire        g_ready;
    wire [255:0] g_data;
    wire        g_data_valid;

    // Blitter/GPU producer.
    reg         b_valid = 0;
    reg         b_write = 0;
    reg  [28:0] b_addr = 0;
    reg  [255:0] b_wr_data = 0;
    reg  [31:0]  b_wr_mask = 0;
    wire        b_ready;
    wire [255:0] b_rd_data;
    wire        b_rd_valid;

    // Ordered native terminal.
    wire        m_en;
    wire [2:0]  m_cmd;
    wire [28:0] m_addr;
    wire        m_ready;
    wire        m_wr_en;
    wire        m_wr_end;
    wire [255:0] m_wr_data;
    wire [31:0]  m_wr_mask;
    wire        m_wr_ready;
    wire [255:0] m_rd_data;
    wire        m_rd_valid;
    wire        m_rd_end;

    // ---------------------------------------------------------------------
    // DUT composition.
    // ---------------------------------------------------------------------
    ddr_ui_adapt u_adapter (
        .clk(clk), .rst_n(rst_n),
        .u_cmd_en(u_cmd_en), .u_cmd(u_cmd), .u_addr(u_addr),
        .u_cmd_ready(u_cmd_ready),
        .u_wr_data_en(u_wr_data_en), .u_wr_data_end(u_wr_data_end),
        .u_wr_data(u_wr_data), .u_wr_data_mask(u_wr_data_mask),
        .u_wr_data_rdy(u_wr_data_rdy),
        .u_rd_data(u_rd_data), .u_rd_data_valid(u_rd_data_valid),
        .u_rd_data_end(u_rd_data_end),
        .ip_cmd_en(ip_cmd_en), .ip_cmd(ip_cmd), .ip_addr(ip_addr),
        .ip_cmd_ready(ip_cmd_ready),
        .ip_wr_data_en(ip_wr_data_en), .ip_wr_data_end(ip_wr_data_end),
        .ip_wr_data(ip_wr_data), .ip_wr_data_mask(ip_wr_data_mask),
        .ip_wr_data_rdy(ip_wr_data_rdy),
        .ip_rd_data(ip_rd_data), .ip_rd_data_valid(ip_rd_data_valid),
        .ip_rd_data_end(ip_rd_data_end)
    );

    ddr_gpu_arb u_arb (
        .clk(clk), .rst_n(rst_n),
        .c_en(ip_cmd_en), .c_cmd(ip_cmd), .c_addr(ip_addr),
        .c_ready(ip_cmd_ready),
        .c_wr_en(ip_wr_data_en), .c_wr_end(ip_wr_data_end),
        .c_wr_data(ip_wr_data), .c_wr_mask(ip_wr_data_mask),
        .c_wr_ready(ip_wr_data_rdy),
        .c_rd_data(ip_rd_data), .c_rd_valid(ip_rd_data_valid),
        .c_rd_end(ip_rd_data_end),
        .g_valid(g_valid), .g_addr(g_addr), .g_ready(g_ready),
        .g_data(g_data), .g_data_valid(g_data_valid),
        .b_valid(b_valid), .b_write(b_write), .b_addr(b_addr),
        .b_wr_data(b_wr_data), .b_wr_mask(b_wr_mask), .b_ready(b_ready),
        .b_rd_data(b_rd_data), .b_rd_valid(b_rd_valid),
        .m_en(m_en), .m_cmd(m_cmd), .m_addr(m_addr), .m_ready(m_ready),
        .m_wr_en(m_wr_en), .m_wr_end(m_wr_end), .m_wr_data(m_wr_data),
        .m_wr_mask(m_wr_mask), .m_wr_ready(m_wr_ready),
        .m_rd_data(m_rd_data), .m_rd_valid(m_rd_valid), .m_rd_end(m_rd_end)
    );

    native_memory u_native (
        .clk(clk), .resetn(rst_n), .en(m_en), .cmd(m_cmd), .addr(m_addr),
        .ready(m_ready), .wr_en(m_wr_en), .wr_end(m_wr_end),
        .wr_data(m_wr_data), .wr_mask(m_wr_mask), .wr_ready(m_wr_ready),
        .rd_data(m_rd_data), .rd_valid(m_rd_valid), .rd_end(m_rd_end)
    );

    // ---------------------------------------------------------------------
    // Independent byte model and per-client expected-response queues.
    // exp_mem is never sourced from the DUT or from native_memory.bytes.
    // ---------------------------------------------------------------------
    reg [7:0] exp_mem [0:4095];

    reg [127:0] cpu_q  [0:255];
    reg [3:0]   cpu_rot [0:255];
    reg [255:0] scan_q [0:255];
    reg [255:0] blit_q [0:255];

    integer cpu_w = 0, cpu_r = 0, scan_w = 0, scan_r = 0;
    integer blit_w = 0, blit_r = 0;
    integer cpu_got = 0, scan_got = 0, blit_got = 0;
    integer outstanding_native = 0, outstanding_peak = 0;
    integer rotations = 0;
    reg [15:0] rot_cov = 16'h0000;

    // Producer acceptance and terminal acceptance are deliberately separate.
    // Producer counters are written by their own driver process only.
    integer cpu_wr_issued = 0, gpu_wr_issued = 0;
    integer native_wr_accepted = 0;

    // Set only after every checked response and write has completed.
    reg bench_done = 1'b0;

    integer i, j, b, h, rot;
    integer rr_cpu, rr_scan, rr_blit;
    reg [127:0] wd;
    reg [255:0] wd256;

    // CPU read expectation: select the 16-byte half addressed by U, then
    // rotate so that the 16-bit word at offset (U & 7) appears first.
    function automatic [127:0] cpu_expect(input [28:0] u);
        integer hb, n, m, q, src;
        begin
            hb = (u & ~29'd7) * 2;
            n  = u[2:0];
            for (m = 0; m < 8; m = m + 1) begin
                src = hb + (((m + n) % 8) * 2);
                for (q = 0; q < 2; q = q + 1)
                    cpu_expect[8*(2*m+q) +: 8] = exp_mem[src + q];
            end
        end
    endfunction

    // Native 32-byte line expectation, increasing byte order.
    function automatic [255:0] line_expect(input [28:0] a);
        integer base, q;
        begin
            base = a * 4;
            for (q = 0; q < 32; q = q + 1)
                line_expect[8*q +: 8] = exp_mem[base + q];
        end
    endfunction

    // ---------------------------------------------------------------------
    // External-port scoreboard and real coverage counters.
    // ---------------------------------------------------------------------
    always @(posedge clk) begin
        if (rst_n) begin
            if (u_rd_data_valid) begin
                if (cpu_r >= cpu_w)
                    $fatal(1, "CHECK_FAIL ROUTE cpu valid without request");
                if (u_rd_data !== cpu_q[cpu_r])
                    $fatal(1, "CHECK_FAIL DATA cpu got=%h exp=%h",
                           u_rd_data, cpu_q[cpu_r]);
                rot_cov[cpu_rot[cpu_r][3:0]] = 1'b1;
                cpu_r = cpu_r + 1;
                cpu_got = cpu_got + 1;
            end

            if (g_data_valid) begin
                if (scan_r >= scan_w)
                    $fatal(1, "CHECK_FAIL ROUTE scanout valid without request");
                if (g_data !== scan_q[scan_r])
                    $fatal(1, "CHECK_FAIL DATA scanout got=%h exp=%h",
                           g_data, scan_q[scan_r]);
                scan_r = scan_r + 1;
                scan_got = scan_got + 1;
            end

            if (b_rd_valid) begin
                if (blit_r >= blit_w)
                    $fatal(1, "CHECK_FAIL ROUTE blitter valid without request");
                if (b_rd_data !== blit_q[blit_r])
                    $fatal(1, "CHECK_FAIL DATA blitter got=%h exp=%h",
                           b_rd_data, blit_q[blit_r]);
                blit_r = blit_r + 1;
                blit_got = blit_got + 1;
            end

            // Native reads in flight, sampled only at the arbiter's m_* port.
            if (m_en && (m_cmd == 3'b001)) begin
                outstanding_native = outstanding_native + 1;
                if (outstanding_native > outstanding_peak)
                    outstanding_peak = outstanding_native;
            end
            if (m_rd_valid && (outstanding_native > 0))
                outstanding_native = outstanding_native - 1;

            // External write acceptance, including the ordered terminal's
            // data-ready handshake.  The producer ready signals (adapter c/IP
            // or blitter b) are intentionally not counted as completion.
            if (m_en && m_ready && (m_cmd == 3'b000) &&
                m_wr_en && m_wr_end && m_wr_ready)
                native_wr_accepted = native_wr_accepted + 1;
        end
    end

    // ---------------------------------------------------------------------
    // Bounded global completion watchdog.  It is independent of every driver
    // timeout and fails if the stimulus as a whole never reaches its end.
    // ---------------------------------------------------------------------
    integer watchdog_cycles = 0;
    initial begin : GLOBAL_WATCHDOG
        while (!bench_done && (watchdog_cycles < 20000)) begin
            @(negedge clk);
            watchdog_cycles = watchdog_cycles + 1;
        end
        if (!bench_done)
            $fatal(1, "CHECK_FAIL TIMEOUT global completion watchdog after %0d cycles",
                   watchdog_cycles);
    end

    // ---------------------------------------------------------------------
    // CPU128 command/data driver.  Command and write data are presented
    // together and only after u_cmd_ready (and u_wr_data_rdy for writes).
    // ---------------------------------------------------------------------
    task automatic cpu_write(input [28:0] u, input [127:0] d,
                             input [15:0] mask);
        integer guard, k, by, hb, n;
        begin
            guard = 0;
            @(negedge clk);
            while ((u_cmd_ready !== 1'b1) || (u_wr_data_rdy !== 1'b1)) begin
                @(negedge clk);
                guard = guard + 1;
                if (guard > 2000)
                    $fatal(1, "CHECK_FAIL TIMEOUT cpu write ready");
            end
            u_cmd_en = 1'b1; u_cmd = 3'b000; u_addr = u;
            u_wr_data_en = 1'b1; u_wr_data_end = 1'b1;
            u_wr_data = d; u_wr_data_mask = mask;
            // High-level operation -> byte oracle.  Upstream word k lands at
            // native half-word (k+n) mod 8 because the adapter rotates left.
            hb = (u & ~29'd7) * 2;
            n  = u[2:0];
            for (k = 0; k < 8; k = k + 1)
                for (by = 0; by < 2; by = by + 1)
                    if (!mask[2*k + by])
                        exp_mem[hb + (((k + n) % 8) * 2) + by] =
                            d[8*(2*k + by) +: 8];
            @(posedge clk);
            if (!(u_cmd_en && u_cmd_ready && u_wr_data_rdy))
                $fatal(1, "CHECK_FAIL ROUTE cpu write handshake");
            cpu_wr_issued = cpu_wr_issued + 1;
            @(negedge clk);
            u_cmd_en = 1'b0; u_wr_data_en = 1'b0; u_wr_data_end = 1'b0;
        end
    endtask

    task automatic cpu_read(input [28:0] u);
        integer guard;
        begin
            guard = 0;
            @(negedge clk);
            while (u_cmd_ready !== 1'b1) begin
                @(negedge clk);
                guard = guard + 1;
                if (guard > 2000)
                    $fatal(1, "CHECK_FAIL TIMEOUT cpu read ready");
            end
            u_cmd_en = 1'b1; u_cmd = 3'b001; u_addr = u;
            u_wr_data_en = 1'b0; u_wr_data_end = 1'b0;
            cpu_q[cpu_w]   = cpu_expect(u);
            cpu_rot[cpu_w] = {u[3], u[2:0]};
            cpu_w = cpu_w + 1;
            @(posedge clk);
            if (!(u_cmd_en && u_cmd_ready))
                $fatal(1, "CHECK_FAIL ROUTE cpu read handshake");
            @(negedge clk);
            u_cmd_en = 1'b0;
        end
    endtask

    // ---------------------------------------------------------------------
    // Scanout read driver: valid/payload remain stable until g_ready.
    // ---------------------------------------------------------------------
    task automatic scan_read(input [28:0] a);
        integer guard;
        begin
            guard = 0;
            @(negedge clk);
            g_valid = 1'b1; g_addr = a;
            scan_q[scan_w] = line_expect(a);
            scan_w = scan_w + 1;
            @(posedge clk);
            while (!g_ready) begin
                guard = guard + 1;
                if (guard > 2000)
                    $fatal(1, "CHECK_FAIL TIMEOUT scanout ready");
                @(posedge clk);
            end
            @(negedge clk);
            g_valid = 1'b0;
        end
    endtask

    // ---------------------------------------------------------------------
    // Blitter read/write driver: valid/payload remain stable until b_ready.
    // ---------------------------------------------------------------------
    task automatic blit_read(input [28:0] a);
        integer guard;
        begin
            guard = 0;
            @(negedge clk);
            b_valid = 1'b1; b_write = 1'b0; b_addr = a;
            blit_q[blit_w] = line_expect(a);
            blit_w = blit_w + 1;
            @(posedge clk);
            while (!b_ready) begin
                guard = guard + 1;
                if (guard > 2000)
                    $fatal(1, "CHECK_FAIL TIMEOUT blitter read ready");
                @(posedge clk);
            end
            @(negedge clk);
            b_valid = 1'b0;
        end
    endtask

    task automatic gpu_write(input [28:0] a, input [255:0] d,
                             input [31:0] mask);
        integer guard, q, by;
        begin
            guard = 0;
            @(negedge clk);
            b_valid = 1'b1; b_write = 1'b1; b_addr = a;
            b_wr_data = d; b_wr_mask = mask;
            @(posedge clk);
            while (!b_ready) begin
                guard = guard + 1;
                if (guard > 2000)
                    $fatal(1, "CHECK_FAIL TIMEOUT blitter write ready");
                @(posedge clk);
            end
            // Mask bit 1 means the corresponding byte is not written.
            for (q = 0; q < 32; q = q + 1)
                if (!mask[q])
                    exp_mem[a*4 + q] = d[8*q +: 8];
            gpu_wr_issued = gpu_wr_issued + 1;
            @(negedge clk);
            b_valid = 1'b0;
        end
    endtask

    // Bounded wait for all issued reads to produce a checked response.
    task automatic wait_drained(input integer limit);
        integer guard;
        begin
            guard = 0;
            while ((cpu_r != cpu_w) || (scan_r != scan_w) || (blit_r != blit_w)) begin
                @(negedge clk);
                guard = guard + 1;
                if (guard > limit)
                    $fatal(1, "CHECK_FAIL TIMEOUT drain cpu=%0d/%0d scan=%0d/%0d blit=%0d/%0d",
                           cpu_r, cpu_w, scan_r, scan_w, blit_r, blit_w);
            end
        end
    endtask

    // Bounded wait for the external ordered terminal to accept every write
    // already accepted by its producer.  This replaces fixed drain delays.
    task automatic wait_native_writes(input integer target, input integer limit);
        integer guard;
        begin
            guard = 0;
            while (native_wr_accepted < target) begin
                @(negedge clk);
                guard = guard + 1;
                if (guard > limit)
                    $fatal(1, "CHECK_FAIL TIMEOUT native writes %0d/%0d",
                           native_wr_accepted, target);
            end
        end
    endtask

    // ---------------------------------------------------------------------
    // Stimulus.
    // ---------------------------------------------------------------------
    initial begin
        for (i = 0; i < 4096; i = i + 1)
            exp_mem[i] = 8'h00;
        for (i = 0; i < 256; i = i + 1) begin
            cpu_q[i] = 0; cpu_rot[i] = 0; scan_q[i] = 0; blit_q[i] = 0;
        end

        rst_n = 1'b0;
        repeat (8) @(negedge clk);
        rst_n = 1'b1;
        repeat (4) @(negedge clk);

        // Four native bursts, both CPU halves, non-trivial write masks.
        for (b = 0; b < 4; b = b + 1) begin
            for (h = 0; h < 2; h = h + 1) begin
                rot = (b*3 + h*5) & 7;
                for (j = 0; j < 16; j = j + 1)
                    wd[8*j +: 8] = 8'h31 + b*8'h13 + h*8'h29
                                   + rot*8'h07 + j*8'h05;
                if (h == 0)
                    cpu_write(b*16 + 8*h + rot, wd, 16'hA5C3);
                else
                    cpu_write(b*16 + 8*h + rot, wd, 16'h5A3C);
            end
        end

        // GPU256 partially masked writes to the same bursts.
        for (b = 0; b < 4; b = b + 1) begin
            for (j = 0; j < 32; j = j + 1)
                wd256[8*j +: 8] = 8'h80 + b*8'h0B + j*8'h03;
            if ((b % 2) == 0)
                gpu_write(b*8, wd256, 32'h0F0F0F0F);
            else
                gpu_write(b*8, wd256, 32'hF0F0F0F0);
        end

        // Wait for terminal write acceptance, not merely producer readiness.
        wait_native_writes(cpu_wr_issued + gpu_wr_issued, 4000);

        // Three client processes run together.  Each producer uses private
        // loop/payload locals so the concurrent branches share no j or data.
        // The CPU process inserts a CPU write among its reads; the blitter
        // process inserts a GPU write among its reads.  Both target ranges
        // are disjoint from B=0..3 and from each other.
        fork
            begin : CPU_MIX
                integer cj;
                reg [127:0] cwd;
                for (rr_cpu = 0; rr_cpu < 16; rr_cpu = rr_cpu + 1) begin
                    cpu_read(8*(rr_cpu/8) + (rr_cpu%8));
                    if (rr_cpu == 5) begin
                        for (cj = 0; cj < 16; cj = cj + 1)
                            cwd[8*cj +: 8] = 8'hC1 + cj*8'h09;
                        cpu_write(1600, cwd, 16'h0FF0);
                    end
                end
            end
            begin : SCAN_MIX
                for (rr_scan = 0; rr_scan < 8; rr_scan = rr_scan + 1)
                    scan_read(8*(rr_scan % 4));
            end
            begin : BLIT_MIX
                integer bj;
                reg [255:0] bwd;
                for (rr_blit = 0; rr_blit < 8; rr_blit = rr_blit + 1) begin
                    blit_read(8*(rr_blit % 4));
                    if (rr_blit == 3) begin
                        for (bj = 0; bj < 32; bj = bj + 1)
                            bwd[8*bj +: 8] = 8'hD1 + bj*8'h07;
                        gpu_write(880, bwd, 32'h00FF00FF);
                    end
                end
            end
        join

        wait_drained(4000);
        // The injected writes were acknowledged by their producers; require
        // external terminal acceptance before reading those ranges back.
        wait_native_writes(cpu_wr_issued + gpu_wr_issued, 4000);

        // Read back both disjoint write ranges and an untouched canary.
        scan_read(800);  blit_read(800);
        scan_read(880);  blit_read(880);
        scan_read(1008); blit_read(1008);

        wait_drained(4000);

        rotations = 0;
        for (i = 0; i < 16; i = i + 1)
            if (rot_cov[i]) rotations = rotations + 1;

        if ((rotations != 16) || (cpu_got < 16) || (scan_got < 8) ||
            (blit_got < 8) || (outstanding_peak < 3))
            $fatal(1, "CHECK_FAIL TIMEOUT coverage cpu=%0d scan=%0d blit=%0d rot=%0d out=%0d",
                   cpu_got, scan_got, blit_got, rotations, outstanding_peak);

        bench_done = 1'b1;
        $display("PASS cpu=%0d scan=%0d blit=%0d rotations=%0d outstanding=%0d",
                 cpu_got, scan_got, blit_got, rotations, outstanding_peak);
        $finish;
    end

endmodule
