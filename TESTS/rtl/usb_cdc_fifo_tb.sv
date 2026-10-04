// The actual open RTL dual-clock FIFO, including wrap, full/empty and reset.
// Digital simulation cannot model metastability or prove Gray-bus routing skew.
`timescale 1ns/1fs
module usb_cdc_fifo_tb;
    reg wclk = 0, rclk = 0, reset = 1, run_w = 1, run_r = 1;
    real write_mhz = 125, read_mhz = 124.5, phase_ns = 0.317;
    reg wr = 0, rd = 0;
    reg [7:0] data = 0;
    wire [7:0] q;
    wire full, empty, afull, aempty;
    integer written = 0, read_count = 0, total_read = 0, discarded = 0;
    integer epoch = 0, mode = 0, full_cycles = 0, empty_cycles = 0;
    reg [31:0] wr_rng = 32'h6a813947, rd_rng = 32'h598ba753;
    reg [7:0] scoreboard [0:65535];

    clk_cross_fifo #(.DSIZE(8), .ASIZE(6), .AEMPT(1), .AFULL(32)) dut (
        .WrClock(wclk), .RdClock(rclk), .Reset(reset), .RPReset(reset),
        .WrEn(wr), .RdEn(rd), .Data(data), .Q(q),
        .Full(full), .Empty(empty), .AlmostFull(afull), .AlmostEmpty(aempty)
    );

    initial begin : writer_clock
        real next_edge, half_period;
        if ($value$plusargs("WRITE_MHZ=%f", write_mhz)) begin end
        half_period = 500.0 / write_mhz;
        next_edge = 0;
        forever begin
            next_edge = next_edge + half_period;
            #(next_edge - $realtime);
            if (run_w) wclk = ~wclk;
        end
    end
    initial begin : reader_clock
        real next_edge, half_period;
        if ($value$plusargs("READ_MHZ=%f", read_mhz)) begin end
        if ($value$plusargs("PHASE_NS=%f", phase_ns)) begin end
        half_period = 500.0 / read_mhz;
        next_edge = phase_ns;
        forever begin
            next_edge = next_edge + half_period;
            #(next_edge - $realtime);
            if (run_r) rclk = ~rclk;
        end
    end

    always @(negedge wclk) begin
        wr_rng = (wr_rng << 1) ^ (wr_rng[31] ? 32'h04c11db7 : 0);
        // Deliberately request operations even at full/empty to check gating.
        wr = !reset && (mode == 1 || (mode == 3 && wr_rng[3:0] != 0));
        data = ((written * 73) ^ (written >> 8) ^ (epoch * 29)) & 255;
    end
    always @(negedge rclk) begin
        rd_rng = (rd_rng << 1) ^ (rd_rng[31] ? 32'h04c11db7 : 0);
        rd = !reset && (mode == 2 || (mode == 3 && rd_rng[3:0] < 10));
    end
    always @(posedge wclk) if (!reset) begin
        if (full) full_cycles = full_cycles + 1;
        if (wr && !full) begin
            scoreboard[written] = data;
            written = written + 1;
            if (written >= 65535) $fatal(1, "scoreboard overflow");
        end
    end
    always @(posedge rclk) if (!reset) begin
        if (empty) empty_cycles = empty_cycles + 1;
        if (rd && !empty) begin
            if (read_count >= written) $fatal(1, "read before write");
            #0.001;
            if (q !== scoreboard[read_count])
                $fatal(1, "epoch=%0d byte=%0d got=%h expected=%h", epoch,
                       read_count, q, scoreboard[read_count]);
            read_count = read_count + 1;
            total_read = total_read + 1;
        end
    end

    task automatic restart(input reg stop_clocks);
        begin
            mode = 0;
            #17.139;
            if (stop_clocks) begin run_w = 0; run_r = 0; end
            #1.271 reset = 1;
            #0.003;
            if (full !== 0 || empty !== 1) $fatal(1, "asynchronous reset flags");
            discarded = discarded + written - read_count;
            written = 0;
            read_count = 0;
            epoch = epoch + 1;
            #137.219;
            run_w = 1; run_r = 1;
            #33.117 reset = 0;
            #100;
            if (full !== 0 || empty !== 1) $fatal(1, "stale data after reset");
        end
    endtask

    initial begin : test
        integer n;
        restart(0);
        for (n = 0; n < 3; n = n + 1) begin
            mode = 1;
            #3000;
            if (written != 64 || !full || !afull) $fatal(1, "full capacity/flags");
            mode = 2;
            #3000;
            if (read_count != 64 || !empty || !aempty) $fatal(1, "drain/flags");
            mode = 3;
            wait (written >= 20000);
            if (n == 2) begin
                mode = 2;
                #3000;
                if (read_count != written || !empty) $fatal(1, "final drain");
            end
            restart(n == 1);
        end
        if (!full_cycles || !empty_cycles || total_read < 59000)
            $fatal(1, "insufficient coverage");
        $display("PASS dual-clock FIFO wr=%0.6f MHz rd=%0.6f MHz phase=%0.6f ns checked=%0d discarded_on_reset=%0d full_cycles=%0d empty_cycles=%0d",
                 write_mhz, read_mhz, phase_ns, total_read, discarded, full_cycles, empty_cycles);
        $finish;
    end
    initial begin #10000000; $fatal(1, "timeout"); end
endmodule
