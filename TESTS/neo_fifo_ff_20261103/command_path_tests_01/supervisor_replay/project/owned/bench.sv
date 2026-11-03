// Real-source command-transport integration bench: AHB -> ddr_dcfifo(u_commands)
// -> blitter cmem -> ext_command -> gpu_geometry -> gpu_v1 -> gpu_copy565.
//
// DUT: snapshot/gpu_accel.v (all real R19 dependencies). The DDR ports are an
// explicit transaction test driver: it returns deterministic data, checks
// read/write addresses, payload and byte masks, and inserts real READY
// backpressure and finite pauses. It is not a DRAM/PHY/board model.
//
// Two additional instances of the qualified banked helper (neo_command_ff128)
// are driven from the exact real memory pins of u_commands and u_blitter.cmem.
// Their registered DO is compared with the word actually consumed by the RTL
// after each edge. This is a workload-pin shadow check, NOT a proof that the
// mapped application was substituted end-to-end.
//
// Test-only mutants alter the *bench command source* (never immutable RTL) so
// that the unchanged packet scoreboard must fail; run.py requires that failure.
`timescale 1ps/1ps
`default_nettype none
module tb;
    parameter FONT_FILE = "font8x16.hex";

    // Independent clocks: half periods in ps, overridden by plusargs.
    integer half_h = 6250;   // 80 MHz
    integer half_m = 6667;   // 75 MHz
    integer pause_h_ps = 18000;
    integer pause_m_ps = 30000;
    reg cfg_ready = 0, pause_h = 0, pause_m = 0;

    // Command packets. w0 op bits [31:24], words 1..7 as documented by blitter.
    // TARGET: colour/destination 0x13000020, depth 0x13000100, 16x2, strides 32.
    localparam [255:0] P_TARGET =
        {32'h0, 32'h0, 32'h0, 32'h00200020, 32'h00100002, 32'h13000100, 32'h13000020, 32'h16000000};
    // SCISSOR: 0,0 .. 16,2 over the accepted target.
    localparam [255:0] P_SCISSOR =
        {160'h0, 32'h00100002, 32'h0, 32'h17000000};
    // COPY: independent source 0x12000020, 16x2, source stride 32 bytes,
    // destination is the target colour base above, w7 reserved = 0.
    localparam [255:0] P_COPY =
        {32'h0, 32'h00100002, 32'h0, 32'h0, 32'h00000020, 32'h00100002, 32'h12000020, 32'h1d000000};
    // Expected-negative: reserved sentinel word7 = 1; copy565 must reject.
    localparam [255:0] P_COPY_BAD =
        {32'h1, 32'h00100002, 32'h0, 32'h0, 32'h00000020, 32'h00100002, 32'h12000020, 32'h1d000000};

    // Independent source and destination 32-byte blocks; both non-overlapping.
    localparam [28:0] RD0 = 29'h04800008; // 0x12000020
    localparam [28:0] RD1 = 29'h04800010; // 0x12000040
    localparam [28:0] WR0 = 29'h04C00008; // 0x13000020
    localparam [28:0] WR1 = 29'h04C00010; // 0x13000040

    reg hclk = 0, mem_clk = 0;
    reg hresetn = 0;
    reg hsel = 0, hwrite = 0;
    reg [1:0] htrans = 0;
    reg [31:0] haddr = 0, hwdata = 0;
    wire [31:0] hrdata;
    wire hready;

    wire valid, write;
    wire [28:0] addr;
    wire [255:0] wr_data;
    wire [31:0] wr_mask;
    reg ready = 0, rd_valid = 0;
    reg [255:0] rd_data = 0;
    wire [255:0] debug_state;
    wire debug_accept;
    wire [63:0] observe_packet_words;

    // Test controls (plusargs only; no force of application state).
    integer mutant_swap = 0, mutant_dup = 0, stress_mode = 0;
    reg [255:0] expected_packet = 0;
    reg start_m_pause = 0;

    // Queued command scoreboard: exp_pkt is filled before a run and indexed by
    // the actual ext_start count, so a single variable cannot silently change
    // while earlier queued commands are still executing.
    reg [255:0] exp_pkt [0:63];
    integer geom_done_idx = 0;

    // Accepted-word stream scoreboard (stress mode only). exp_stream holds the
    // words in the order the AHB producer must place them into u_commands.
    reg [31:0] exp_stream [0:511];
    integer stream_len = 0, accept_idx = 0, accepted_words = 0, beat_sent = 0;

    // Pressure instrumentation. hold_active is a test-side responder gate, not
    // an application force; it only controls the normal DDR transaction driver.
    reg hold_active = 0, gate_armed = 0, copy_seen = 0;
    integer ahb_full_stall_cycles = 0, queue_full_events = 0, command_full_events = 0;
    integer ddr_ready_stall_cycles = 0, gate_ready_stall_cycles = 0, gate_watchdog = 0;
    wire ddr_gate = hold_active;

    // AHB master hold self-check (address/data must be stable while hready=0).
    reg [31:0] mon_haddr = 0, mon_hwdata = 0;
    reg mon_active = 0;

    gpu_accel #(.FONT_FILE(FONT_FILE)) dut (
        .hclk(hclk), .hresetn(hresetn), .hsel(hsel), .hwrite(hwrite),
        .haddr(haddr), .hwdata(hwdata), .htrans(htrans), .hrdata(hrdata), .hready(hready),
        .mem_clk(mem_clk), .valid(valid), .write(write), .addr(addr),
        .wr_data(wr_data), .wr_mask(wr_mask), .ready(ready), .rd_data(rd_data),
        .rd_valid(rd_valid), .debug_state(debug_state), .debug_accept(debug_accept),
        .observe_packet_words(observe_packet_words));

    // ------------------------------------------------------------------ clocks
    initial begin
        if (!$value$plusargs("HALF_H=%d", half_h)) half_h = 6250;
        if (!$value$plusargs("HALF_M=%d", half_m)) half_m = 6667;
        if (!$value$plusargs("PAUSE_H_PS=%d", pause_h_ps)) pause_h_ps = 18000;
        if (!$value$plusargs("PAUSE_M_PS=%d", pause_m_ps)) pause_m_ps = 30000;
        if ($test$plusargs("MUT_SWAP")) mutant_swap = 1;
        if ($test$plusargs("MUT_DUP")) mutant_dup = 1;
        if ($test$plusargs("STRESS")) stress_mode = 1;
        cfg_ready = 1;
    end
    initial begin wait (cfg_ready); forever begin #(half_h); if (!pause_h) hclk = ~hclk; end end
    initial begin wait (cfg_ready); forever begin #(half_m); if (!pause_m) mem_clk = ~mem_clk; end end
    // One finite mem-clock pause, triggered by the first accepted COPY read.
    initial begin
        wait (cfg_ready); wait (start_m_pause);
        pause_m = 1; #(pause_m_ps); pause_m = 0;
    end

    // ------------------------------------------------------------------ shadows
    // Exact physical pin contract from bindings/MAPPING.json: 32/32, SYNC,
    // BLK 000, ADA[4:0]=01111 (bit 4 unused but part of the mapping; bits 3:0
    // are VCC so all four byte lanes are written), ADB low 5 bits zero,
    // 7-bit word address.
    wire [31:0] shadow_cmd_do, shadow_cmem_do;
    neo_command_ff128 shadow_cmd (
        .DO(shadow_cmd_do), .DI(hwdata), .BLKSELA(3'b000), .BLKSELB(3'b000),
        .ADA({2'b0, dut.u_commands.wr_bin[6:0], 5'b01111}),
        .ADB({2'b0, dut.u_commands.rd_bin[6:0], 5'b00000}),
        .CLKA(hclk), .CLKB(mem_clk),
        .CEA(dut.u_commands.accept && hresetn),
        .CEB(dut.u_commands.pop), .OCE(1'b0), .RESET(!dut.mrst[1]));
    neo_command_ff128 shadow_cmem (
        .DO(shadow_cmem_do), .DI(dut.u_blitter.cmd_data),
        .BLKSELA(3'b000), .BLKSELB(3'b000),
        .ADA({2'b0, dut.u_blitter.wp[6:0], 5'b01111}),
        .ADB({2'b0, dut.u_blitter.rp[6:0], 5'b00000}),
        .CLKA(mem_clk), .CLKB(mem_clk),
        // Actual successful memory write in blitter.v: a command word is only
        // stored when the 128-word cmem is not full (fill != 128).
        .CEA(dut.u_blitter.cmd_we && !dut.u_blitter.rst && dut.u_blitter.fill != 8'd128),
        .CEB(1'b1), .OCE(1'b0), .RESET(1'b0));

    // ------------------------------------------------------------------ scoreboard state
    integer n_reads = 0, n_writes = 0, max_queue = 0, ext_count = 0;
    integer cmd_shadow_checks = 0, cmem_shadow_checks = 0;
    integer resp_wait = 0, resp_pending = 0;
    reg [255:0] resp_data = 0, last_read_data = 0;
    integer rd_stall = 0, wr_stall = 0;
    reg pop_q = 0;
    integer shadow_errors = 0;

    function [255:0] ddr_word;
        input [28:0] a;
        integer k;
        begin
            for (k = 0; k < 8; k = k + 1)
                ddr_word[k*32 +: 32] = {3'b0, a} ^ (32'h9e3779b9 * (k + 1));
        end
    endfunction

    function [31:0] pword;
        input [255:0] p;
        input integer k;
        begin pword = p[k*32 +: 32]; end
    endfunction

    always @(posedge mem_clk) begin
        if (dut.queue_count > max_queue) max_queue = dut.queue_count;
        pop_q <= dut.u_commands.pop;
    end

    // u_commands shadow: after each real pop/head load, registered DO must equal
    // the head word the RTL will consume.
    always @(negedge mem_clk) begin
        if (pop_q && dut.mrst[1]) begin
            cmd_shadow_checks = cmd_shadow_checks + 1;
            if (shadow_cmd_do !== dut.u_commands.head) begin
                shadow_errors = shadow_errors + 1;
                $display("SHADOW_CMD_MISMATCH got=%h exp=%h at_check=%0d",
                    shadow_cmd_do, dut.u_commands.head, cmd_shadow_checks);
            end
        end
    end

    // blitter cmem shadow: compare registered DO with the field captured by the
    // real blitter exactly one edge earlier from cmem[rp].
    reg [63:0] prev_st = 0;
    always @(posedge mem_clk) begin
        if (dut.mrst[1]) begin
            case (prev_st)
                64'd1<<1: begin
                    cmem_shadow_checks = cmem_shadow_checks + 1;
                    if (shadow_cmem_do !== {dut.u_blitter.op, dut.u_blitter.dpage,
                        dut.u_blitter.spage, dut.u_blitter.c0, dut.u_blitter.c1}) begin
                        shadow_errors = shadow_errors + 1;
                        $display("SHADOW_CMEM_MISMATCH word=0 got=%h", shadow_cmem_do);
                    end
                end
                64'd1<<2: begin
                    cmem_shadow_checks = cmem_shadow_checks + 1;
                    if (shadow_cmem_do !== {dut.u_blitter.x0, dut.u_blitter.y0}) begin
                        shadow_errors = shadow_errors + 1;
                        $display("SHADOW_CMEM_MISMATCH word=1 got=%h", shadow_cmem_do);
                    end
                end
                64'd1<<3: begin
                    cmem_shadow_checks = cmem_shadow_checks + 1;
                    if (shadow_cmem_do !== {dut.u_blitter.x1, dut.u_blitter.y1}) begin
                        shadow_errors = shadow_errors + 1;
                        $display("SHADOW_CMEM_MISMATCH word=2 got=%h", shadow_cmem_do);
                    end
                end
                64'd1<<4: begin
                    cmem_shadow_checks = cmem_shadow_checks + 1;
                    if (shadow_cmem_do !== {dut.u_blitter.xs, dut.u_blitter.ys}) begin
                        shadow_errors = shadow_errors + 1;
                        $display("SHADOW_CMEM_MISMATCH word=3 got=%h", shadow_cmem_do);
                    end
                end
                64'd1<<28: begin
                    cmem_shadow_checks = cmem_shadow_checks + 1;
                    if (shadow_cmem_do !== dut.u_blitter.txt[31:0]) begin
                        shadow_errors = shadow_errors + 1;
                        $display("SHADOW_CMEM_MISMATCH word=4 got=%h", shadow_cmem_do);
                    end
                end
                64'd1<<29: begin
                    cmem_shadow_checks = cmem_shadow_checks + 1;
                    if (shadow_cmem_do !== dut.u_blitter.txt[63:32]) begin
                        shadow_errors = shadow_errors + 1;
                        $display("SHADOW_CMEM_MISMATCH word=5 got=%h", shadow_cmem_do);
                    end
                end
                64'd1<<30: begin
                    cmem_shadow_checks = cmem_shadow_checks + 1;
                    if (shadow_cmem_do !== dut.u_blitter.txt[95:64]) begin
                        shadow_errors = shadow_errors + 1;
                        $display("SHADOW_CMEM_MISMATCH word=6 got=%h", shadow_cmem_do);
                    end
                end
                64'd1<<31: begin
                    cmem_shadow_checks = cmem_shadow_checks + 1;
                    if (shadow_cmem_do !== dut.u_blitter.txt[127:96]) begin
                        shadow_errors = shadow_errors + 1;
                        $display("SHADOW_CMEM_MISMATCH word=7 got=%h", shadow_cmem_do);
                    end
                end
                default: ;
            endcase
        end
        prev_st <= dut.u_blitter.st;
    end

    // Exact ext_command transport check at ext_start, before the consumer.
    // The expected packet is selected by the observed command index.
    always @(posedge mem_clk) begin
        if (dut.ext_start && dut.mrst[1]) begin
            if (dut.ext_command !== exp_pkt[ext_count]) begin
                if (mutant_swap || mutant_dup)
                    $display("MUTANT_DETECTED ext_command mismatch index=%0d", ext_count);
                if (dut.ext_command[31:0] !== exp_pkt[ext_count][31:0])
                    $fatal(1, "EXT_CMD_WORD0 got=%h exp=%h idx=%0d", dut.ext_command[31:0], exp_pkt[ext_count][31:0], ext_count);
                if (dut.ext_command[63:32] !== exp_pkt[ext_count][63:32])
                    $fatal(1, "EXT_CMD_WORD1 got=%h exp=%h idx=%0d", dut.ext_command[63:32], exp_pkt[ext_count][63:32], ext_count);
                if (dut.ext_command[95:64] !== exp_pkt[ext_count][95:64])
                    $fatal(1, "EXT_CMD_WORD2 got=%h exp=%h idx=%0d", dut.ext_command[95:64], exp_pkt[ext_count][95:64], ext_count);
                if (dut.ext_command[127:96] !== exp_pkt[ext_count][127:96])
                    $fatal(1, "EXT_CMD_WORD3 got=%h exp=%h idx=%0d", dut.ext_command[127:96], exp_pkt[ext_count][127:96], ext_count);
                if (dut.ext_command[159:128] !== exp_pkt[ext_count][159:128])
                    $fatal(1, "EXT_CMD_WORD4 got=%h exp=%h idx=%0d", dut.ext_command[159:128], exp_pkt[ext_count][159:128], ext_count);
                if (dut.ext_command[191:160] !== exp_pkt[ext_count][191:160])
                    $fatal(1, "EXT_CMD_WORD5 got=%h exp=%h idx=%0d", dut.ext_command[191:160], exp_pkt[ext_count][191:160], ext_count);
                if (dut.ext_command[223:192] !== exp_pkt[ext_count][223:192])
                    $fatal(1, "EXT_CMD_WORD6 got=%h exp=%h idx=%0d", dut.ext_command[223:192], exp_pkt[ext_count][223:192], ext_count);
                $fatal(1, "EXT_CMD_WORD7 got=%h exp=%h idx=%0d", dut.ext_command[255:224], exp_pkt[ext_count][255:224], ext_count);
            end
            // Explicit named checks for the COPY dimension/reserved contract.
            // The expected packet selects the contract: the sentinel case
            // legitimately carries w7=1, so the reserved-zero check applies
            // only when exp_pkt says word7 must be zero.
            if (dut.ext_command[31:24] == 8'h1d) begin
                if (dut.ext_command[95:64] !== 32'h00100002)
                    $fatal(1, "COPY_EXT_DIMS_W2 got=%h exp=00100002", dut.ext_command[95:64]);
                if (dut.ext_command[223:192] !== 32'h00100002)
                    $fatal(1, "COPY_EXT_DIMS_W6 got=%h exp=00100002", dut.ext_command[223:192]);
                if (exp_pkt[ext_count][255:224] === 32'h00000000 &&
                    dut.ext_command[255:224] !== 32'h00000000)
                    $fatal(1, "COPY_EXT_RESERVED_W7 got=%h exp=0", dut.ext_command[255:224]);
            end
            ext_count = ext_count + 1;
        end
    end

    // Geometry completion scoreboard: verify the parent packet captured by the
    // real geometry engine, the child packet in gpu_v1 and, for COPY, the COPY
    // child packet with its rejection flag. exp_pkt is indexed by completion.
    always @(posedge mem_clk) begin
        if (dut.mrst[1] && dut.u_v1.done) begin
            if (dut.u_v1.captured_command !== exp_pkt[geom_done_idx]) begin
                if (mutant_swap || mutant_dup)
                    $display("MUTANT_DETECTED geom parent mismatch index=%0d", geom_done_idx);
                $fatal(1, "GEOM_PARENT_PACKET idx=%0d got=%h exp=%h", geom_done_idx,
                       dut.u_v1.captured_command, exp_pkt[geom_done_idx]);
            end
            if (dut.u_v1.u_pixels.packet !== exp_pkt[geom_done_idx]) begin
                if (mutant_swap || mutant_dup)
                    $display("MUTANT_DETECTED geom child mismatch index=%0d", geom_done_idx);
                $fatal(1, "GEOM_CHILD_PACKET idx=%0d got=%h exp=%h", geom_done_idx,
                       dut.u_v1.u_pixels.packet, exp_pkt[geom_done_idx]);
            end
            if (exp_pkt[geom_done_idx][31:24] == 8'h1d) begin
                if (dut.u_v1.u_pixels.u_copy.packet !== exp_pkt[geom_done_idx]) begin
                    if (mutant_swap || mutant_dup)
                        $display("MUTANT_DETECTED geom copy mismatch index=%0d", geom_done_idx);
                    $fatal(1, "GEOM_COPY_PACKET idx=%0d got=%h exp=%h", geom_done_idx,
                           dut.u_v1.u_pixels.u_copy.packet, exp_pkt[geom_done_idx]);
                end
                if (exp_pkt[geom_done_idx][255:224] == 32'h00000000) begin
                    if (dut.u_v1.u_pixels.u_copy.bad !== 0)
                        $fatal(1, "COPY_BAD_AT_COMPLETION idx=%0d bad=%0d", geom_done_idx,
                               dut.u_v1.u_pixels.u_copy.bad);
                end else if (dut.u_v1.u_pixels.u_copy.bad !== 1) begin
                    $fatal(1, "SENTINEL_NOT_REJECTED_AT_COMPLETION idx=%0d bad=%0d", geom_done_idx,
                           dut.u_v1.u_pixels.u_copy.bad);
                end
            end
            geom_done_idx = geom_done_idx + 1;
        end
    end

    // ------------------------------------------------------------------ pressure gate
    // Arm on the first COPY command that reaches the ordered engine. copy_seen
    // is held so the slower hclk block cannot miss a one-mem-cycle ext_start.
    always @(posedge mem_clk) begin
        if (!hresetn) copy_seen <= 1'b0;
        else if (stress_mode && !copy_seen && dut.ext_start && dut.ext_command[31:24] == 8'h1d)
            copy_seen <= 1'b1;
    end

    // Hold the normal DDR responder not-ready, then release only after a real
    // queue_full + !hready stall (>=10 hclk cycles) AND cmd_full was seen.
    // Watchdog is independent of the producer and of wait_done.
    always @(posedge hclk) begin
        if (!hresetn) begin
            hold_active <= 1'b0; gate_armed <= 1'b0; gate_watchdog <= 0;
            ahb_full_stall_cycles <= 0; queue_full_events <= 0; command_full_events <= 0;
        end else if (stress_mode) begin
            if (dut.queue_full) queue_full_events <= queue_full_events + 1;
            if (dut.command_full) command_full_events <= command_full_events + 1;
            if (copy_seen && !gate_armed) begin
                gate_armed <= 1'b1;
                hold_active <= 1'b1;
            end
            if (hold_active) begin
                if (dut.queue_full && !hready)
                    ahb_full_stall_cycles <= ahb_full_stall_cycles + 1;
                gate_watchdog <= gate_watchdog + 1;
                if (gate_watchdog > 200000)
                    $fatal(1, "STRESS_WATCHDOG gate not released stalls=%0d cmd_full=%0d",
                           ahb_full_stall_cycles, command_full_events);
                if (ahb_full_stall_cycles >= 10 && command_full_events != 0)
                    hold_active <= 1'b0;
            end
        end
    end

    // Accepted-word scoreboard: count at the real FIFO accept pin and compare
    // the accepted data with the staged stream. Packet-source mutants are
    // additionally detected by the independent expected-packet scoreboard.
    always @(posedge hclk) begin
        if (!hresetn) begin
            accepted_words <= 0; accept_idx <= 0;
        end else if (dut.u_commands.accept) begin
            accepted_words <= accepted_words + 1;
            if (stress_mode) begin
                if (hwdata !== exp_stream[accept_idx])
                    $fatal(1, "ACCEPT_WORD_MISMATCH idx=%0d got=%h exp=%h",
                           accept_idx, hwdata, exp_stream[accept_idx]);
                accept_idx <= accept_idx + 1;
            end
        end
    end

    // AHB master self-check: address and data must stay stable for every
    // *continued* stall cycle. The first stalled edge legitimately follows one
    // accepted beat, so only the second and later stalled edges are compared.
    reg mon_stalled = 0;
    always @(posedge hclk) begin
        if (!hresetn) begin
            mon_haddr <= 0; mon_hwdata <= 0; mon_active <= 1'b0; mon_stalled <= 1'b0;
        end else begin
            if (!hready && mon_active && mon_stalled) begin
                if (haddr !== mon_haddr)
                    $fatal(1, "AHB_HADDR_CHANGED_WHILE_STALLED got=%h prev=%h", haddr, mon_haddr);
                if (hwdata !== mon_hwdata)
                    $fatal(1, "AHB_HWDATA_CHANGED_WHILE_STALLED got=%h prev=%h", hwdata, mon_hwdata);
            end
            if (!hready && mon_active) begin
                mon_haddr <= haddr; mon_hwdata <= hwdata;
            end
            mon_stalled <= !hready && mon_active;
            mon_active <= stress_mode && (hsel || htrans[1]);
        end
    end

    // ------------------------------------------------------------------ DDR driver
    always @(negedge mem_clk) begin
        ready <= 1'b0;
        rd_valid <= 1'b0;
        if (!hresetn) begin
            n_reads <= 0; n_writes <= 0; resp_pending <= 0; resp_wait <= 0;
            rd_stall <= 0; wr_stall <= 0; last_read_data <= 0;
            ddr_ready_stall_cycles <= 0; gate_ready_stall_cycles <= 0;
        end else begin
            if (valid && !ready) ddr_ready_stall_cycles <= ddr_ready_stall_cycles + 1;
            if (ddr_gate) begin
                // Test-side gate: hold the first COPY transaction not-ready.
                if (valid) gate_ready_stall_cycles <= gate_ready_stall_cycles + 1;
            end else begin
                if (resp_pending) begin
                    if (resp_wait == 0) begin
                        rd_valid <= 1'b1;
                        rd_data <= resp_data;
                        resp_pending <= 0;
                    end else resp_wait <= resp_wait - 1;
                end
                if (!valid) begin
                    rd_stall <= 0; wr_stall <= 0;
                end else if (!ready) begin
                    // Real READY backpressure: hold the request for several mem clocks.
                    if (!write) begin
                        if (rd_stall < 3) rd_stall <= rd_stall + 1;
                        else begin
                            ready <= 1'b1; rd_stall <= 0;
                            if (addr !== ((n_reads % 2) == 0 ? RD0 : RD1))
                                $fatal(1, "READ_ADDR index=%0d got=%h exp=%h", n_reads, addr,
                                       (n_reads % 2) == 0 ? RD0 : RD1);
                            last_read_data <= ddr_word(addr);
                            resp_data <= ddr_word(addr);
                            resp_wait <= 4;
                            resp_pending <= 1;
                            if (n_reads == 0) start_m_pause <= 1'b1;
                            n_reads <= n_reads + 1;
                        end
                    end else begin
                        if (wr_stall < 5) wr_stall <= wr_stall + 1;
                        else begin
                            ready <= 1'b1; wr_stall <= 0;
                            if (addr !== ((n_writes % 2) == 0 ? WR0 : WR1))
                                $fatal(1, "WRITE_ADDR index=%0d got=%h exp=%h", n_writes, addr,
                                       (n_writes % 2) == 0 ? WR0 : WR1);
                            if (wr_data !== last_read_data)
                                $fatal(1, "WRITE_DATA index=%0d got=%h exp=%h", n_writes, wr_data, last_read_data);
                            if (wr_mask !== 32'h00000000)
                                $fatal(1, "WRITE_MASK index=%0d got=%h", n_writes, wr_mask);
                            n_writes <= n_writes + 1;
                        end
                    end
                end
            end
        end
    end

    // ------------------------------------------------------------------ AHB / packet source
    reg [31:0] words [0:7];
    task load_packet(input [255:0] p, input integer is_copy);
        integer k;
        begin
            for (k = 0; k < 8; k = k + 1) words[k] = p[k*32 +: 32];
            if (is_copy && mutant_swap) begin
                words[2] = 32'h00020010; // width/height transposed, test-only
                words[6] = 32'h00020010;
            end
            if (is_copy && mutant_dup) begin
                words[3] = words[2];     // duplicate word2, drop word3, test-only
            end
        end
    endtask

    // Eight words back-to-back. Address phase i overlaps data phase i-1.
    // AHB: the FIFO samples the registered bus_command one cycle after the
    // address phase, so each data word is presented for the cycle whose
    // ending posedge actually pushes it. This is the real gpu_accel AHB
    // timing, not a generic wishbone-style one-cycle push.
    task send_words;
        integer i;
        begin
            @(negedge hclk);
            hsel = 1; htrans = 2'b10; hwrite = 1; haddr = 32'h00000010;
            @(posedge hclk);              // address phase captured
            for (i = 0; i < 8; i = i + 1) begin
                @(negedge hclk);          // data phase i
                hwdata = words[i];
                if (i == 4) begin
                    pause_h = 1; #(pause_h_ps); pause_h = 0;
                end
                if (i == 7) begin hsel = 0; htrans = 0; hwrite = 0; end
                @(posedge hclk);          // u_commands pushes this word
            end
            @(negedge hclk);
        end
    endtask

    // Stress-mode AHB word sender. Unlike send_words it samples the DUT's
    // registered HREADY and holds address/data while a command write is
    // stalled, so the producer survives real FIFO-FULL backpressure.
    task send_words_stress;
        integer i;
        reg addr_captured;
        begin
            @(negedge hclk);
            hsel = 1; htrans = 2'b10; hwrite = 1; haddr = 32'h00000010;
            addr_captured = 0;
            while (!addr_captured) begin
                @(posedge hclk);
                if (hready) addr_captured = 1;
            end
            for (i = 0; i < 8; i = i + 1) begin
                @(negedge hclk);
                hwdata = words[i];
                if (i == 7) begin hsel = 0; htrans = 0; hwrite = 0; end
                @(posedge hclk);
                while (!hready) @(posedge hclk);
            end
            @(negedge hclk);
        end
    endtask

    // Append the eight words just staged by load_packet to the accepted-word
    // scoreboard stream. It is built from the actual staged words, so the
    // scoreboard checks FIFO transport rather than the intended packet.
    task fill_stream_packet;
        integer k;
        begin
            for (k = 0; k < 8; k = k + 1) begin
                exp_stream[stream_len] = words[k];
                stream_len = stream_len + 1;
            end
        end
    endtask

    task reset_all;
        integer n;
        begin
            hresetn = 0; hsel = 0; htrans = 0; hwrite = 0; haddr = 0; hwdata = 0;
            ready = 0; rd_valid = 0; rd_data = 0; expected_packet = 0;
            pause_h = 0; pause_m = 0; start_m_pause = 0;
            ext_count = 0; shadow_errors = 0; cmd_shadow_checks = 0; cmem_shadow_checks = 0;
            n_reads = 0; n_writes = 0; max_queue = 0;
            geom_done_idx = 0; accept_idx = 0; accepted_words = 0; beat_sent = 0;
            hold_active = 0; gate_armed = 0; copy_seen = 0; gate_watchdog = 0;
            ahb_full_stall_cycles = 0; queue_full_events = 0; command_full_events = 0;
            ddr_ready_stall_cycles = 0; gate_ready_stall_cycles = 0;
            mon_active = 0;
            #(200000);
            hresetn = 1;
            n = 0;
            while ((dut.engine_resetn !== 12'hfff || dut.mrst !== 2'b11) && n < 2000) begin
                @(posedge mem_clk); n = n + 1;
            end
            if (dut.engine_resetn !== 12'hfff) $fatal(1, "RESET_TIMEOUT mrst=%b engine=%h", dut.mrst, dut.engine_resetn);
            repeat (20) @(posedge mem_clk);
        end
    endtask

    task wait_done(input integer target, input [8*20-1:0] tag);
        integer n;
        begin
            n = 0;
            while (dut.done_count < target && n < 20000) begin
                @(posedge mem_clk); n = n + 1;
            end
            if (dut.done_count < target)
                $fatal(1, "NO_DONE tag=%0s done=%0d target=%0d", tag, dut.done_count, target);
            repeat (10) @(posedge mem_clk);
        end
    endtask

    task check_transport(input [255:0] exp, input [8*20-1:0] tag);
        begin
            if (dut.u_v1.captured_command !== exp)
                $fatal(1, "PARENT_PACKET tag=%0s got=%h exp=%h", tag, dut.u_v1.captured_command, exp);
            if (dut.u_v1.u_pixels.packet !== exp)
                $fatal(1, "CHILD_PACKET tag=%0s got=%h exp=%h", tag, dut.u_v1.u_pixels.packet, exp);
            if (exp[31:24] == 8'h1d) begin
                if (dut.u_v1.u_pixels.u_copy.packet !== exp)
                    $fatal(1, "COPY_PACKET tag=%0s got=%h exp=%h", tag, dut.u_v1.u_pixels.u_copy.packet, exp);
            end
        end
    endtask

    task send_target;
        begin
            expected_packet = P_TARGET; exp_pkt[0] = P_TARGET; load_packet(P_TARGET, 0);
            send_words; wait_done(1, "target"); check_transport(P_TARGET, "target");
            if (dut.u_v1.u_pixels.target_valid !== 1)
                $fatal(1, "TARGET_NOT_VALID");
            if (dut.u_v1.u_pixels.width !== 16 || dut.u_v1.u_pixels.height !== 2)
                $fatal(1, "TARGET_DIMS w=%0d h=%0d", dut.u_v1.u_pixels.width, dut.u_v1.u_pixels.height);
        end
    endtask

    task send_scissor;
        begin
            expected_packet = P_SCISSOR; exp_pkt[1] = P_SCISSOR; load_packet(P_SCISSOR, 0);
            send_words; wait_done(2, "scissor"); check_transport(P_SCISSOR, "scissor");
            if (dut.u_v1.u_pixels.left !== 0 || dut.u_v1.u_pixels.top !== 0 ||
                dut.u_v1.u_pixels.right !== 16 || dut.u_v1.u_pixels.bottom !== 2)
                $fatal(1, "SCISSOR_BOUNDS l=%0d t=%0d r=%0d b=%0d",
                    dut.u_v1.u_pixels.left, dut.u_v1.u_pixels.top,
                    dut.u_v1.u_pixels.right, dut.u_v1.u_pixels.bottom);
        end
    endtask

    // Bounded stress sequence: one TARGET, one SCISSOR, then 40 back-to-back
    // COPY commands with no per-packet wait. The first COPY arms a test-side
    // DDR not-ready gate; the resulting command/FIFO backlog must stall the
    // AHB producer (FIFO FULL -> HREADY low) until the gate releases.
    task stress_run;
        integer c;
        begin
            exp_pkt[0] = P_TARGET;
            exp_pkt[1] = P_SCISSOR;
            for (c = 0; c < 40; c = c + 1) exp_pkt[2 + c] = P_COPY;
            stream_len = 0;

            load_packet(P_TARGET, 0);  fill_stream_packet; send_words_stress;
            load_packet(P_SCISSOR, 0); fill_stream_packet; send_words_stress;
            for (c = 0; c < 40; c = c + 1) begin
                load_packet(P_COPY, 1); fill_stream_packet; send_words_stress;
            end

            wait_done(42, "stress");
            repeat (20) @(posedge mem_clk);

            // Supervisor checks the fault registers and final drain explicitly.
            // Exact data counts alone must not substitute for these observables.
            if (dut.done_count !== 42 || dut.queue_lost !== 0 ||
                dut.command_lost !== 0 || dut.command_bad !== 0 || dut.v1_rejected !== 0)
                $fatal(1, "STRESS_FAULT_COUNTER done=%0d queue_lost=%0d command_lost=%0d command_bad=%0d v1_rejected=%0d",
                    dut.done_count, dut.queue_lost, dut.command_lost, dut.command_bad, dut.v1_rejected);
            if (dut.queue_valid !== 0 || dut.command_word !== 0 || dut.u_blitter.fill !== 0)
                $fatal(1, "STRESS_NOT_DRAINED valid=%0d word=%0d fill=%0d",
                    dut.queue_valid, dut.command_word, dut.u_blitter.fill);
            $display("STRESS_FAULT_COUNTER_PASS done=%0d lost=%0d/%0d bad=%0d rejected=%0d drained=1",
                dut.done_count, dut.queue_lost, dut.command_lost, dut.command_bad, dut.v1_rejected);
            if (accepted_words !== 336)
                $fatal(1, "STRESS_ACCEPT_COUNT got=%0d exp=336", accepted_words);
            if (accept_idx !== 336)
                $fatal(1, "STRESS_ACCEPT_INDEX got=%0d exp=336", accept_idx);
            if (ext_count !== 42)
                $fatal(1, "STRESS_EXT_COUNT got=%0d exp=42", ext_count);
            if (geom_done_idx !== 42)
                $fatal(1, "STRESS_GEOM_DONE got=%0d exp=42", geom_done_idx);
            if (n_reads !== 80)
                $fatal(1, "STRESS_READ_COUNT got=%0d exp=80", n_reads);
            if (n_writes !== 80)
                $fatal(1, "STRESS_WRITE_COUNT got=%0d exp=80", n_writes);
            if (ahb_full_stall_cycles < 10)
                $fatal(1, "STRESS_NO_AHB_FULL_STALL cycles=%0d", ahb_full_stall_cycles);
            if (queue_full_events == 0)
                $fatal(1, "STRESS_NO_QUEUE_FULL");
            if (command_full_events == 0)
                $fatal(1, "STRESS_NO_COMMAND_FULL");
            if (gate_ready_stall_cycles == 0)
                $fatal(1, "STRESS_NO_GATE_STALL");
            if (shadow_errors !== 0)
                $fatal(1, "STRESS_SHADOW_ERRORS count=%0d", shadow_errors);
            if (cmd_shadow_checks < 336)
                $fatal(1, "STRESS_CMD_SHADOW checks=%0d", cmd_shadow_checks);
            if (cmem_shadow_checks < 336)
                $fatal(1, "STRESS_CMEM_SHADOW checks=%0d", cmem_shadow_checks);
        end
    endtask

    initial begin
        integer n;
        wait (cfg_ready);
        reset_all();
        if (stress_mode) begin
            stress_run();
            $display("STRESS_PASS done=%0d accepts=%0d reads=%0d writes=%0d max_queue=%0d ahb_stall=%0d qfull=%0d cmdfull=%0d gate_stall=%0d cmd_shadow=%0d cmem_shadow=%0d ext=%0d geom=%0d",
                dut.done_count, accepted_words, n_reads, n_writes, max_queue,
                ahb_full_stall_cycles, queue_full_events, command_full_events,
                gate_ready_stall_cycles, cmd_shadow_checks, cmem_shadow_checks,
                ext_count, geom_done_idx);
            $finish;
        end
        // ---- positive baseline: TARGET, SCISSOR, COPY 16x2
        send_target();
        send_scissor();
        expected_packet = P_COPY; exp_pkt[2] = P_COPY; load_packet(P_COPY, 1);
        send_words; wait_done(3, "copy"); check_transport(P_COPY, "copy");
        if (pword(P_COPY, 2) !== 32'h00100002 || pword(P_COPY, 6) !== 32'h00100002 ||
            pword(P_COPY, 7) !== 32'h00000000)
            $fatal(1, "COPY_DIM_SENTINEL_SCOREBOARD");
        if (dut.u_v1.u_pixels.u_copy.bad !== 0) $fatal(1, "COPY_BAD_POSITIVE");
        if (dut.u_v1.rejected !== 0) $fatal(1, "V1_REJECT_POSITIVE value=%0d", dut.u_v1.rejected);
        if (n_reads !== 2) $fatal(1, "READ_COUNT got=%0d exp=2", n_reads);
        if (n_writes !== 2) $fatal(1, "WRITE_COUNT got=%0d exp=2", n_writes);
        if (ext_count !== 3) $fatal(1, "EXT_COUNT got=%0d exp=3", ext_count);
        if (cmd_shadow_checks < 24) $fatal(1, "CMD_SHADOW_COVERAGE checks=%0d", cmd_shadow_checks);
        if (cmem_shadow_checks < 24) $fatal(1, "CMEM_SHADOW_COVERAGE checks=%0d", cmem_shadow_checks);
        if (shadow_errors !== 0) $fatal(1, "SHADOW_ERRORS count=%0d", shadow_errors);
        if (mutant_swap || mutant_dup) begin
            $display("MUTANT_SURVIVED swap=%0d dup=%0d", mutant_swap, mutant_dup);
            $finish;
        end
        $display("POSITIVE_PASS reads=%0d writes=%0d max_queue=%0d ext=%0d cmd_shadow=%0d cmem_shadow=%0d",
            n_reads, n_writes, max_queue, ext_count, cmd_shadow_checks, cmem_shadow_checks);

        // ---- expected-negative: reserved w7=1 must be transported exactly and rejected
        reset_all();
        send_target();
        send_scissor();
        expected_packet = P_COPY_BAD; exp_pkt[2] = P_COPY_BAD; load_packet(P_COPY_BAD, 1);
        send_words; wait_done(3, "copy_bad"); check_transport(P_COPY_BAD, "copy_bad");
        if (pword(P_COPY_BAD, 2) !== 32'h00100002 || pword(P_COPY_BAD, 6) !== 32'h00100002 ||
            pword(P_COPY_BAD, 7) !== 32'h00000001)
            $fatal(1, "COPY_BAD_DIM_SENTINEL_SCOREBOARD");
        if (dut.u_v1.u_pixels.u_copy.bad !== 1)
            $fatal(1, "SENTINEL_NOT_REJECTED bad=%0d", dut.u_v1.u_pixels.u_copy.bad);
        if (n_reads !== 0 || n_writes !== 0)
            $fatal(1, "SENTINEL_SIDE_EFFECT reads=%0d writes=%0d", n_reads, n_writes);
        if (dut.u_v1.rejected < 1) $fatal(1, "SENTINEL_NO_V1_REJECT");
        if (cmd_shadow_checks < 24 || cmem_shadow_checks < 24)
            $fatal(1, "SENTINEL_SHADOW_COVERAGE cmd=%0d cmem=%0d", cmd_shadow_checks, cmem_shadow_checks);
        if (shadow_errors !== 0) $fatal(1, "SENTINEL_SHADOW_ERRORS count=%0d", shadow_errors);
        $display("SENTINEL_REJECT_PASS reads=0 writes=0 rejected=%0d cmd_shadow=%0d cmem_shadow=%0d",
            dut.u_v1.rejected, cmd_shadow_checks, cmem_shadow_checks);
        $display("INTEGRATION_PASS");
        $finish;
    end
endmodule
`default_nettype wire
