// Original Gowin PHY UTMI -> serial path, checked with a host timebase/CDR.
// Expected symbols are generated independently (NRZI, stuffing, HS SYNC/EOP).
// The host phase tracks physical edges, as a receiver must over long packets.
`timescale 1ns/1fs
module usb_phy_tx_drift_tb;
    reg clk = 0, fclk = 0, reset = 1, locked = 0;
    reg attach = 1, txvalid = 0;
    reg [7:0] txdata = 0;
    tri dp, dn, term_dp, term_dn;
    assign dp = attach ? 1'b1 : 1'bz;
    assign dn = attach ? 1'b0 : 1'bz;
    pulldown(dp, dn);
    wire ready;
    real host_ppm = 0, card_ppm = 0, phase_ns = 0.317;
    real bit_ns, card_half_ns, last_edge = 0;
    reg [7:0] payload [0:514];
    reg levels [0:4999];
    integer byte_count, bit_count, ones, packets = 0, bytes_checked = 0;
    integer framing_differences = 0;
    reg nrzi;

    USB2_0_SoftPHY_Top dut (
        .clk_i(clk), .fclk_i(fclk), .rst_i(reset), .pll_locked_i(locked),
        .utmi_data_out_i(txdata), .utmi_txvalid_i(txvalid),
        .utmi_op_mode_i(2'b00), .utmi_xcvrselect_i(2'b00),
        .utmi_termselect_i(1'b0), .usb_rxdp_i(dp), .usb_rxdn_i(dn),
        .utmi_txready_o(ready), .usb_dxp_io(dp), .usb_dxn_io(dn),
        .usb_term_dp_io(term_dp), .usb_term_dn_io(term_dn)
    );

    initial begin : clocks
        real deadline;
        integer n;
        if ($value$plusargs("HOST_PPM=%f", host_ppm)) begin end
        if ($value$plusargs("CARD_PPM=%f", card_ppm)) begin end
        if ($value$plusargs("PHASE_NS=%f", phase_ns)) begin end
        bit_ns = (1000.0 / 480.0) / (1.0 + host_ppm / 1e6);
        card_half_ns = (1000.0 / 1920.0) / (1.0 + card_ppm / 1e6);
        deadline = 0;
        n = 0;
        forever begin
            deadline = deadline + card_half_ns;
            #(deadline - $realtime);
            fclk = ~fclk;
            n = n + 1;
            if ((n % 16) == 0) clk = ~clk;
        end
    end
    // Allow the two primitive output assignments to settle before recording
    // the edge. This is an ideal digital CDR, with no analog/jitter model.
    always @(dp or dn) begin
        #0.001;
        if ((dp === 0 && dn === 1) || (dp === 1 && dn === 0))
            last_edge = $realtime;
    end

    task automatic append_bit(input reg b);
        begin
            if (!b) nrzi = ~nrzi;
            levels[bit_count] = nrzi;
            bit_count = bit_count + 1;
        end
    endtask
    task automatic prepare(input integer length, input integer pattern);
        integer i, j;
        reg [7:0] b;
        reg [15:0] crc;
        begin
            payload[0] = packets[0] ? 8'h4b : 8'hc3;
            crc = 16'hffff;
            for (i = 0; i < length; i = i + 1) begin
                case (pattern)
                    0: b = 0;
                    1: b = 8'hff;
                    default: b = ((i * 73) ^ (i >> 3) ^ (packets * 17)) & 255;
                endcase
                payload[i + 1] = b;
                for (j = 0; j < 8; j = j + 1)
                    if (crc[0] ^ b[j]) crc = (crc >> 1) ^ 16'ha001;
                    else crc = crc >> 1;
            end
            crc = ~crc;
            payload[length + 1] = crc[7:0];
            payload[length + 2] = crc[15:8];
            byte_count = length + 3;
            nrzi = 1;
            bit_count = 0;
            for (i = 0; i < 31; i = i + 1) append_bit(0);
            append_bit(1);
            ones = 1;
            for (i = 0; i < byte_count; i = i + 1)
                for (j = 0; j < 8; j = j + 1) begin
                    append_bit(payload[i][j]);
                    if (payload[i][j]) ones = ones + 1; else ones = 0;
                    if (ones == 6) begin append_bit(0); ones = 0; end
                end
            append_bit(0);
            for (i = 0; i < 7; i = i + 1) append_bit(1);
        end
    endtask

    task automatic send;
        integer i;
        begin
            @(negedge clk); txvalid = 1; txdata = payload[0];
            for (i = 0; i < byte_count; i = i + 1) begin
                @(posedge clk);
                while (ready !== 1) @(posedge clk);
                @(negedge clk);
                if (i + 1 < byte_count) txdata = payload[i + 1];
                else txvalid = 0;
            end
        end
    endtask
    task automatic receive;
        integer i, sync_symbols;
        real sample_time, previous_sample, first_k, after_eop;
        reg previous_level, sync_found;
        begin
            wait (dp === 0 && dn === 1);
            first_k = $realtime;
            // Acquire phase on the first K->J edge, instead of assuming that
            // analog transmitter enable is aligned with the first data bit.
            // Keep any first-symbol extension visible as a separate failure.
            wait (dp === 1 && dn === 0);
            if (($realtime - first_k) > 1.55 * bit_ns || ($realtime - first_k) < 0.45 * bit_ns) begin
                $display("FRAMING packet=%0d first_K=%0.6f host_bits", packets,
                         ($realtime - first_k) / bit_ns);
                framing_differences = framing_differences + 1;
            end
            sample_time = $realtime + bit_ns / 2;
            previous_sample = $realtime;
            previous_level = 0;
            sync_found = 0;
            sync_symbols = 0;
            // Detect the final KK of SYNC after clock acquisition. Counting
            // from output-enable instead would confuse an initial driven
            // symbol with the serial data boundary in this primitive model.
            while (!sync_found) begin
                #(sample_time - $realtime);
                if (sync_symbols >= 12 && previous_level === 0 && dp === 0)
                    sync_found = 1;
                if (dp !== !dn) $fatal(1, "Invalid differential SYNC symbol");
                previous_level = dp;
                sync_symbols = sync_symbols + 1;
                if (sync_symbols > 40) $fatal(1, "SYNC end missing");
                if (last_edge > previous_sample)
                    sample_time = last_edge + bit_ns / 2;
                previous_sample = $realtime;
                sample_time = sample_time + bit_ns;
            end
            for (i = 32; i < bit_count; i = i + 1) begin
                #(sample_time - $realtime);
                if (dp !== levels[i] || dn !== !levels[i])
                    $fatal(1, "TX packet=%0d symbol=%0d/%0d got=%b%b expected=%b%b at %t",
                           packets, i, bit_count, dp, dn, levels[i], !levels[i], $realtime);
                if (last_edge > previous_sample)
                    sample_time = last_edge + bit_ns / 2;
                previous_sample = $realtime;
                sample_time = sample_time + bit_ns;
            end
            after_eop = $realtime + bit_ns / 2;
            wait (dp === 0 && dn === 0);
            if ($realtime - after_eop > bit_ns) begin
                $display("FRAMING packet=%0d post_EOP=%0.6f host_bits", packets,
                         ($realtime - after_eop) / bit_ns);
                framing_differences = framing_differences + 1;
            end
            #(20 * bit_ns);
            if (dp !== 0 || dn !== 0) $fatal(1, "TX did not return to HS idle");
        end
    endtask
    task automatic transaction(input integer length, input integer pattern);
        begin
            prepare(length, pattern);
            fork send(); receive(); join
            packets = packets + 1;
            bytes_checked = bytes_checked + byte_count;
            #517.139;
        end
    endtask
    task automatic suite;
        begin
            transaction(0, 0);
            transaction(1, 1);
            transaction(63, 2);
            transaction(64, 2);
            transaction(511, 2);
            transaction(512, 0);
            transaction(512, 1);
            transaction(512, 2);
        end
    endtask
    initial begin
        #100 attach = 0;
        #100 locked = 1;
        #813.271 reset = 0;
        #20000;
        #(phase_ns);
        suite();
        #3.713 reset = 1;
        #509.311 reset = 0;
        #3000;
        suite();
        $display("RESULT host_ppm=%0.1f card_ppm=%0.1f phase_ns=%0.6f packets=%0d bytes=%0d",
                 host_ppm, card_ppm, phase_ns, packets, bytes_checked);
        if (framing_differences)
            $fatal(1, "Payload symbols match; %0d framing differences require model/hardware investigation", framing_differences);
        $display("PASS USB PHY TX independent host CDR");
        $finish;
    end
    initial begin #1000000; $fatal(1, "TX timeout"); end
endmodule
