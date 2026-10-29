`timescale 1ns/1ps
// Exact-chain bench for the R19 CLEAR path.
//
// The two real AHB stages, gpu_accel, its async command FIFO, the blitter,
// geometry/pixel engines and ddr_gpu_arb are used unmodified.  Only the
// external CPU master and the external DDR readiness model live here.
//
// Fault injection is done exclusively on bench connections/inputs:
//   fault 0 : healthy model (seed 1/8 select different clock periods,
//             relative phase and stall phase)
//   fault 1 : hold m_ready low after TARGET completes
//   fault 2 : hold m_wr_ready low after TARGET completes
//   fault 3 : split the arbiter b_ready from the GPU ready input, so the
//             arbiter still accepts native writes while the GPU never sees
//             acceptance feedback
//   fault 4 : TB-driven reset while a CLEAR native write is pending with
//             native readiness withheld; then fresh TARGET/CLEAR recovery
//   fault 5 : the protected native_monitor changes only its observation of
//             the first accepted write into a READ.  Bench stimuli are
//             unchanged; this proves monitor sensitivity, not DUT behaviour.
//
// No RTL file is edited.  All prints are simulation observations only.
module bench;
    // ------------------------------------------------------------------
    // Run configuration and seed-dependent clocks
    // ------------------------------------------------------------------
    integer seed = 1;
    integer fault = 0;
    integer hclk_half = 6;       // ns, half period
    integer memclk_half = 7;     // ns, half period
    integer memclk_phase = 1;    // ns before the first mem_clk edge
    integer stall_offset = 0;    // mem_clk stall-pattern phase

    initial begin
        $value$plusargs("seed=%d", seed);
        $value$plusargs("fault=%d", fault);
        // Seed 1 and seed 8 deliberately use different periods, relative
        // phase and DDR stall phase; both are legal timing models.
        case (seed)
            8: begin
                hclk_half    = 5;
                memclk_half  = 8;
                memclk_phase = 3;
                stall_offset = 3;
            end
            default: begin
                hclk_half    = 6;
                memclk_half  = 7;
                memclk_phase = 1;
                stall_offset = 0;
            end
        endcase
    end

    reg hclk = 0, mem_clk = 0, resetn = 0;

    // The 1 ps settle delay lets the plusarg/period decode above happen
    // before the first generator delay is evaluated.
    initial begin
        #0.001;
        forever #(hclk_half) hclk = ~hclk;
    end
    initial begin
        #0.001;
        #(memclk_phase);
        forever #(memclk_half) mem_clk = ~mem_clk;
    end

    // ------------------------------------------------------------------
    // AHB master and the two real bus stages
    // ------------------------------------------------------------------
    reg hsel = 0, hwrite = 0;
    reg [31:0] haddr = 0, hwdata = 0;
    reg [1:0] htrans = 0;
    wire hready;
    wire [31:0] hrdata;

    wire [1:0] leg_sel, leg_trans;
    wire leg_write, leg_ready;
    wire [31:0] leg_addr, leg_wdata, leg_rdata;

    ahb_exts_bridge bridge(
        .hclk(hclk), .hresetn(resetn),
        .m_hsel(hsel), .m_haddr(haddr), .m_htrans(htrans),
        .m_hwrite(hwrite), .m_hwdata(hwdata),
        .m_hrdata(hrdata), .m_hready(hready),
        .s_hsel(leg_sel), .s_htrans(leg_trans), .s_hwrite(leg_write),
        .s_haddr(leg_addr), .s_hwdata(leg_wdata),
        .s0_hrdata(32'hbad00000), .s0_hready(1'b1),
        .s1_hrdata(leg_rdata), .s1_hready(leg_ready));

    wire bus_sel, bus_write, bus_ready;
    wire [1:0] bus_trans;
    wire [31:0] bus_addr, bus_wdata, bus_rdata;

    video_bus_stage stage(
        .clk(hclk), .resetn(resetn),
        .s_hsel(leg_sel[1]), .s_hwrite(leg_write), .s_htrans(leg_trans),
        .s_haddr(leg_addr), .s_hwdata(leg_wdata),
        .s_hready(leg_ready), .s_hrdata(leg_rdata),
        .m_hsel(bus_sel), .m_hwrite(bus_write), .m_htrans(bus_trans),
        .m_haddr(bus_addr), .m_hwdata(bus_wdata),
        .m_hready(bus_ready), .m_hrdata(bus_rdata));

    reg [2:0] selected = 0;
    always @(posedge hclk)
        if (!resetn) selected <= 0;
        else if (bus_sel) selected <= bus_addr[14:12];

    wire [31:0] gpu_data, debug_data;
    wire gpu_ready, debug_ready, debug_accept;
    wire valid, write;
    wire [28:0] addr;
    wire [255:0] wr_data, debug_state;
    wire [31:0] wr_mask;
    wire [63:0] packet_words;

    assign bus_ready = selected == 1 ? gpu_ready :
                       selected == 5 ? debug_ready : 1'b1;
    assign bus_rdata = selected == 1 ? gpu_data :
                       selected == 5 ? debug_data : 32'hbad00001;

    // ------------------------------------------------------------------
    // Native DDR readiness model and fault switches
    // ------------------------------------------------------------------
    reg arm_m = 0;          // fault 1: withhold m_ready
    reg arm_wr = 0;         // fault 2: withhold m_wr_ready
    reg hold_all = 0;       // fault 4: withhold both before/through reset
    reg suppress_feedback = 0; // fault 3: cut arbiter acceptance -> GPU

    reg [31:0] tick = 0;
    wire [31:0] phase_tick = tick + stall_offset;
    wire mrdy_base = ((phase_tick % 7) != 0) && ((phase_tick % 7) != 1);
    wire mwrdy_base = ((phase_tick % 5) != 0);
    wire mrdy = (hold_all || ((fault == 1) && arm_m)) ? 1'b0 : mrdy_base;
    wire mwrdy = (hold_all || ((fault == 2) && arm_wr)) ? 1'b0 : mwrdy_base;

    wire arb_b_ready;
    // Fault 3 intercepts only this connection.  The arbiter keeps seeing its
    // own b_ready and can accept the native write; the GPU does not.
    wire gpu_native_ready =
        ((fault == 3) && suppress_feedback) ? 1'b0 : arb_b_ready;

    wire men, mwen, mwend;
    wire [2:0] mcmd;
    wire [28:0] maddr;
    wire [255:0] mdata;
    wire [31:0] mmask;


    reg [255:0] native_response_data=0;
    reg native_response_valid=0;
    wire [255:0] blit_response_data;
    wire blit_response_valid;
    integer read_accepts=0,read_returns=0,read_delay=0;
    reg [255:0] source_line;
    initial begin
        for(integer k=0;k<8;k=k+1)
            source_line[k*32+:32]=(32'h12000000+4*k)^32'ha5396c17;
    end
    always @(posedge mem_clk)begin
        native_response_valid<=0;
        if(!resetn)begin read_accepts<=0;read_returns<=0;read_delay<=0;end
        else begin
            if(read_delay>0)begin
                read_delay<=read_delay-1;
                if(read_delay==1)begin
                    native_response_data<=source_line;
                    native_response_valid<=1;
                    read_returns<=read_returns+1;
                end
            end
            if(men && mrdy && mcmd==1)begin
                if(read_accepts!=0 || maddr!==29'h04800000 || mwen)
                    $fatal(1,"COPY_BAD_READ_OR_DUPLICATE");
                read_accepts<=read_accepts+1;read_delay<=5;
            end
            if(men && mrdy && mcmd!=0 && mcmd!=1)$fatal(1,"COPY_BAD_COMMAND");
            if(mwen && !(men && mrdy && mwrdy && mcmd==0))
                $fatal(1,"COPY_UNPAIRED_WRITE");
        end
    end

    gpu_accel #(.FONT_FILE("font8x16.hex")) gpu(
        .hclk(hclk), .hresetn(resetn), .mem_clk(mem_clk),
        .hsel(bus_sel && bus_addr[14:12] == 1), .hwrite(bus_write),
        .haddr(bus_addr), .hwdata(bus_wdata), .htrans(bus_trans),
        .hrdata(gpu_data), .hready(gpu_ready),
        .valid(valid), .write(write), .addr(addr),
        .wr_data(wr_data), .wr_mask(wr_mask),
        .ready(gpu_native_ready), .rd_data(blit_response_data), .rd_valid(blit_response_valid),
        .debug_state(debug_state), .debug_accept(debug_accept),
        .observe_packet_words(packet_words));

    neo_gpu_debug debug_port(
        .hclk(hclk), .resetn(resetn), .mem_clk(mem_clk),
        .hsel(bus_sel && bus_addr[14:12] == 5), .hwrite(bus_write),
        .htrans(bus_trans), .haddr(bus_addr), .hwdata(bus_wdata),
        .hrdata(debug_data), .hready(debug_ready),
        .host_accept(debug_accept), .live(debug_state),
        .observe_packet_words(packet_words));

    ddr_gpu_arb arb(
        .clk(mem_clk), .rst_n(resetn),
        .c_en(1'b0), .c_cmd(3'd0), .c_addr(29'd0), .c_ready(),
        .c_wr_en(1'b0), .c_wr_end(1'b0), .c_wr_data(256'd0),
        .c_wr_mask(32'hffffffff), .c_wr_ready(), .c_rd_data(),
        .c_rd_valid(), .c_rd_end(),
        .g_valid(1'b0), .g_addr(29'd0), .g_ready(), .g_data(),
        .g_data_valid(),
        .b_valid(valid), .b_write(write), .b_addr(addr),
        .b_wr_data(wr_data), .b_wr_mask(wr_mask),
        .b_ready(arb_b_ready), .b_rd_data(blit_response_data), .b_rd_valid(blit_response_valid),
        .m_en(men), .m_cmd(mcmd), .m_addr(maddr),
        .m_ready(mrdy), .m_wr_en(mwen), .m_wr_end(mwend),
        .m_wr_data(mdata), .m_wr_mask(mmask),
        .m_wr_ready(mwrdy), .m_rd_data(native_response_data), .m_rd_valid(native_response_valid),
        .m_rd_end(native_response_valid));

    // ------------------------------------------------------------------
    // External counters and diagnostics
    // ------------------------------------------------------------------
    integer accepted = 0;   // accepted native writes at the DDR boundary
    integer received = 0;   // command words observed on internal command_we
    integer stalls = 0;     // native-valid cycles without GPU acceptance
    reg [31:0] value;
    reg [31:0] words [0:15];

    // A native command is accepted when the arbiter presents m_en and the
    // readiness model returns m_ready.  Only a write whose write-data
    // channel is also ready is a complete write acceptance.
    wire native_accept = resetn && men && mrdy;
    wire write_accept  = native_accept && (mcmd == 3'b000) && mwrdy;

    // Coherent simulation-side snapshot used on every failure path.
    // Hierarchical reads are simulation only, never hardware observations.
    task automatic dump_state;
        begin
            $display("FAULT_STATE time=%0t seed=%0d fault=%0d accepted=%0d words=%0d stalls=%0d",
                     $time, seed, fault, accepted, received, stalls);
            $display("FAULT_STATE packet_word0=%08x pixel_word0=%08x ext_command0=%08x",
                     packet_words[31:0], packet_words[63:32],
                     debug_state[255:224]);
            $display("FAULT_STATE blitter_ext_active=%0b v1_pending=%0b arb_take_blitter=%0b arb_full=%0b",
                     debug_state[32], gpu.v1_pending, arb.take_blitter,
                     arb.full);
            $display("FAULT_STATE m_ready=%0b m_wr_ready=%0b arb_b_ready=%0b gpu_native_ready=%0b",
                     mrdy, mwrdy, arb_b_ready, gpu_native_ready);
            $display("FAULT_STATE done=%0d busy=%0b command_we=%0b queue_valid=%0b queue_data=%08x",
                     debug_state[15:0], debug_state[34], debug_state[36],
                     debug_state[38], debug_state[223:192]);
        end
    endtask

    // Accepted native writes must match the exact CLEAR footprint.  A second
    // acceptance of the same still-pending write is also a failure.
    always @(posedge mem_clk) begin
        tick <= tick + 1'b1;
        if (resetn && valid && !gpu_native_ready) stalls <= stalls + 1;

        // Scoreboard completeness: every accepted native command must be the
        // expected CLEAR write.  Previously an accepted READ (mcmd=1) or any
        // illegal command was silently ignored by the write-only counter.
        if (native_accept && mcmd !== 3'b000 && mcmd !== 3'b001) begin
            dump_state();
            $fatal(1, "CHECK_FAIL NATIVE_COMMAND mcmd=%0d accepted=%0d words=%0d stalls=%0d",
                   mcmd, accepted, received, stalls);
        end

        if (write_accept) begin
            if (mwen !== 1'b1 || mwend !== 1'b1 ||
                maddr !== 29'h04800008 || mmask !== 32'd0 ||
                mdata !== source_line) begin
                $display("FOOTPRINT_OBSERVED addr=%08x mask=%08x data0=%04x mcmd=%0d",
                         {3'b0, maddr}, mmask, mdata[15:0], mcmd);
                dump_state();
                $fatal(1, "CHECK_FAIL FOOTPRINT accepted=%0d", accepted);
            end
            if (accepted >= 1) begin
                dump_state();
                $fatal(1, "CHECK_FAIL COMPLETION duplicate_native_write accepted=%0d",
                       accepted + 1);
            end
            accepted <= accepted + 1;
        end
    end

    // Command-word order/payload check.  The trigger and data are internal
    // gpu.command_we/queue_data in simulation; the expected payload is
    // independently specified by the bench, so this is not an external bus
    // measurement of the hardware command words.
    always @(posedge mem_clk)
        if (resetn && gpu.command_we) begin
            if (received >= 16 || gpu.queue_data !== words[received]) begin
                $display("PAYLOAD_OBSERVED index=%0d got=%08x want=%08x",
                         received, gpu.queue_data,
                         (received < 16) ? words[received] : 32'h0);
                dump_state();
                $fatal(1, "CHECK_FAIL PAYLOAD accepted=%0d words=%0d",
                       accepted, received);
            end
            received = received + 1;
        end

    // ------------------------------------------------------------------
    // Bounded AHB access and completion helpers
    // ------------------------------------------------------------------
    task automatic access(input bit wr, input [31:0] address,
                          input [31:0] data, output [31:0] result);
        integer guard;
        begin
            guard = 0;
            @(negedge hclk);
            while (!hready) begin
                guard = guard + 1;
                if (guard > 256) begin
                    dump_state();
                    $fatal(1, "CHECK_FAIL WATCHDOG AHB_READY accepted=%0d",
                           accepted);
                end
                @(negedge hclk);
            end
            hsel = 1; htrans = 2; hwrite = wr; haddr = address;
            @(negedge hclk);
            hsel = 0; htrans = 0; hwdata = data;
            guard = 0;
            do begin
                @(negedge hclk);
                guard = guard + 1;
                if (guard > 256) begin
                    dump_state();
                    $fatal(1, "CHECK_FAIL WATCHDOG AHB_RESPONSE accepted=%0d",
                           accepted);
                end
            end while (!hready);
            result = hrdata;
            hwdata = 0;
            hwrite = 0;
        end
    endtask

    task automatic wait_done(input [31:0] wanted);
        integer polls;
        begin
            polls = 0;
            value = 0;
            while (value != wanted && polls < 400) begin
                access(0, 32'he9001008, 0, value);
                polls = polls + 1;
            end
            if (value != wanted) begin
                dump_state();
                $fatal(1, "CHECK_FAIL COMPLETION done=%0d want=%0d accepted=%0d words=%0d",
                       value, wanted, accepted, received);
            end
        end
    endtask

    // Post-CLEAR idle/footprint/late-duplicate checks (healthy and fault 4).
    task automatic check_idle;
        begin
            repeat (40) @(negedge hclk);
            access(0, 32'he9001004, 0, value);
            if (value != 0) begin
                dump_state();
                $fatal(1, "CHECK_FAIL BUSY value=%0d accepted=%0d", value,
                       accepted);
            end
            access(0, 32'he9001034, 0, value);
            if (value != 0) begin
                dump_state();
                $fatal(1, "CHECK_FAIL REJECT value=%0d accepted=%0d", value,
                       accepted);
            end
            if (accepted != 0 || received != 16 || read_accepts != 0 || read_returns != 0) begin
                dump_state();
                $fatal(1, "CHECK_FAIL COVERAGE accepted=%0d words=%0d stalls=%0d",
                       accepted, received, stalls);
            end
            // Late-duplicate window: no replay after the fence and idle.
            repeat (40) @(negedge hclk);
            if (accepted != 0 || received != 16) begin
                dump_state();
                $fatal(1, "CHECK_FAIL LATE_DUPLICATE accepted=%0d words=%0d",
                       accepted, received);
            end
        end
    endtask

    task automatic submit_target;
        begin
            for (integer i = 0; i < 8; i = i + 1)
                access(1, 32'he9001010, words[i], value);
        end
    endtask

    task automatic submit_clear;
        begin
            for (integer i = 8; i < 16; i = i + 1)
                access(1, 32'he9001010, words[i], value);
        end
    endtask

    // ------------------------------------------------------------------
    // Fault 4: reset while CLEAR is pending with native ready withheld
    // ------------------------------------------------------------------
    task automatic run_reset_recovery;
        integer guard;
        reg pending_seen;
        begin
            hold_all = 1;
            submit_clear();

            // CLEAR reaches the extended engine and presents exactly one
            // native write.  With mrdy/m_wr_ready low it cannot be accepted.
            guard = 0;
            while (guard < 2000 && !(valid && !gpu_native_ready)) begin
                @(negedge hclk);
                guard = guard + 1;
            end
            pending_seen = (valid && !gpu_native_ready);
            if (!pending_seen) begin
                dump_state();
                $fatal(1, "CHECK_FAIL RESET_PENDING accepted=%0d words=%0d",
                       accepted, received);
            end
            if (accepted != 0) begin
                dump_state();
                $fatal(1, "CHECK_FAIL RESET_PRESTATE accepted=%0d", accepted);
            end
            $display("RESET_EXERCISE pending=%0b ext_active=%0b accepted=%0d words=%0d",
                     valid, debug_state[32], accepted, received);

            // TB-driven synchronous reset pulse while the write is pending.
            @(negedge hclk);
            resetn = 0;
            accepted = 0; received = 0; stalls = 0;
            repeat (8) @(negedge hclk);
            resetn = 1;

            // Quarantine with readiness still withheld: no stale command,
            // payload or native write may appear.
            repeat (80) @(negedge hclk);
            if (accepted != 0 || received != 0 || valid !== 1'b0 ||
                debug_state[32] !== 1'b0 || debug_state[15:0] !== 16'd0) begin
                dump_state();
                $fatal(1, "CHECK_FAIL RESET_STALE accepted=%0d words=%0d valid=%0b ext_active=%0b done=%0d",
                       accepted, received, valid, debug_state[32],
                       debug_state[15:0]);
            end
            $display("RESET_QUARANTINE_CLEAR accepted=%0d words=%0d",
                     accepted, received);

            // Restore readiness and run a completely fresh TARGET/CLEAR.
            hold_all = 0;
            repeat (8) @(negedge hclk);
            submit_target();
            wait_done(1);
            if (accepted != 0) begin
                dump_state();
                $fatal(1, "CHECK_FAIL RESET_FRESH_TARGET accepted=%0d",
                       accepted);
            end
            submit_clear();
            wait_done(2);
            check_idle();
            $display("RESET_RECOVERY_PASS accepted=%0d words=%0d stalls=%0d seed=%0d",
                     accepted, received, stalls, seed);
        end
    endtask

    // ------------------------------------------------------------------
    // Main sequence
    // ------------------------------------------------------------------
    initial begin
        words[0]  = 32'h16000000;
        words[1]  = 32'h12000020;
        words[2]  = 32'h12000040;
        words[3]  = 32'h00100001;
        words[4]  = 32'h00200020;
        words[5]  = 32'h00000000;
        words[6]  = 32'h00000000;
        words[7]  = 32'h00000000;
        words[8]  = 32'h1d000000;
        words[9]  = 32'h12000020;
        words[10] = 32'h00100001;
        words[11] = 32'h00000020;
        words[12] = 32'h00000000;
        words[13] = 32'h00000000;
        words[14] = 32'h00000000;
        words[15] = 32'h00000000;

        repeat (8) @(negedge hclk);
        resetn = 1;
        repeat (20) @(negedge hclk);

        $display("CLOCK_CONFIG seed=%0d hclk_half_ns=%0d memclk_half_ns=%0d memclk_phase_ns=%0d stall_offset=%0d fault=%0d",
                 seed, hclk_half, memclk_half, memclk_phase, stall_offset,
                 fault);

        access(0, 32'he9001000, 0, value);
        if (value !== 32'h424c5432) begin
            dump_state();
            $fatal(1, "CHECK_FAIL ID value=%08x", value);
        end

        // TARGET must complete without any native write.
        submit_target();
        wait_done(1);
        if (accepted != 0) begin
            dump_state();
            $fatal(1, "CHECK_FAIL TARGET_DMA accepted=%0d", accepted);
        end

        // Fault 4 owns its own reset/recovery sequence and finish.
        if (fault == 4) begin
            run_reset_recovery();
            $finish;
        end

        if (fault == 1) arm_m = 1;
        if (fault == 2) arm_wr = 1;
        if (fault == 3) suppress_feedback = 1;

        submit_clear();
        wait_done(2);              // faults 1/2 terminate here, bounded
        check_idle();
        $display("BASELINE_PASS accepted=%0d words=%0d stalls=%0d seed=%0d",
                 accepted, received, stalls, seed);
        $display("COPY_RESULT reads=%0d returns=%0d writes=%0d words=%0d",read_accepts,read_returns,accepted,received);
        $finish;
    end

    always @(posedge mem_clk) if(resetn && (valid || men || mwen))
        $fatal(1,"EMPTY_NATIVE_REQUEST");

    // Global bounded watchdog for the whole scenario.
    initial begin
        #400000;
        $display("FAULT_STATE global_watchdog");
        $fatal(1, "CHECK_FAIL WATCHDOG global accepted=%0d words=%0d",
               accepted, received);
    end
endmodule
