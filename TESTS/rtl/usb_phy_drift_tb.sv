// Digital USB HS receive test against the UNMODIFIED Gowin simulation netlist.
// clk_i/fclk_i share the card oscillator. The serial host has its own timebase.
// This does not model the RC network, analog thresholds or metastability.
`timescale 1ns/1fs
module usb_phy_drift_tb;
    reg clk = 0, fclk = 0, reset = 1, locked = 0;
    // Begin in attach/J so the vendor differential comparator has a defined
    // previous value before entering HS SE0 (its 00 input deliberately holds).
    reg host_dp = 1, host_dn = 0;
    tri dp, dn, term_dp, term_dn;
    assign dp = host_dp;
    assign dn = host_dn;
    wire [7:0] rxdata;
    wire rxvalid, rxactive, rxerror, txready, pullup_en;
    wire [1:0] linestate;
    real host_ppm = 0, card_ppm = 0, phase_ns = 0.317;
    real bit_ns, card_half_ns;
    integer received = 0, errors = 0;
    reg [7:0] expected [0:1023];
    integer expected_count = 0;
    reg checking = 0, nrzi = 1;
    integer ones = 0;
    integer packets = 0, total_received = 0;
    real next_host_edge;

    USB2_0_SoftPHY_Top dut (
        .clk_i(clk), .fclk_i(fclk), .rst_i(reset), .pll_locked_i(locked),
        .utmi_data_out_i(8'b0), .utmi_txvalid_i(1'b0),
        .utmi_op_mode_i(2'b00), .utmi_xcvrselect_i(2'b00),
        .utmi_termselect_i(1'b0), .usb_rxdp_i(host_dp), .usb_rxdn_i(host_dn),
        .utmi_data_in_o(rxdata), .utmi_txready_o(txready),
        .utmi_rxvalid_o(rxvalid), .utmi_rxactive_o(rxactive),
        .utmi_rxerror_o(rxerror), .utmi_linestate_o(linestate),
        .usb_pullup_en_o(pullup_en), .usb_dxp_io(dp), .usb_dxn_io(dn),
        .usb_term_dp_io(term_dp), .usb_term_dn_io(term_dn)
    );

    initial begin : clocks
        real next_edge;
        integer half_edges;
        if ($value$plusargs("HOST_PPM=%f", host_ppm)) begin end
        if ($value$plusargs("CARD_PPM=%f", card_ppm)) begin end
        if ($value$plusargs("PHASE_NS=%f", phase_ns)) begin end
        bit_ns = (1000.0 / 480.0) / (1.0 + host_ppm / 1e6);
        card_half_ns = (1000.0 / 1920.0) / (1.0 + card_ppm / 1e6);
        next_edge = 0;
        half_edges = 0;
        // Absolute deadlines prevent a rounded delay accumulating ppm error.
        forever begin
            next_edge = next_edge + card_half_ns;
            #(next_edge - $realtime);
            fclk = ~fclk;
            half_edges = half_edges + 1;
            if ((half_edges % 16) == 0) clk = ~clk;
        end
    end

    always @(posedge clk) if (checking) begin
        if (rxerror === 1'b1) errors = errors + 1;
        if (rxvalid === 1'b1) begin
            if (rxactive !== 1'b1) $fatal(1, "RXVALID without RXACTIVE");
            if (received >= expected_count)
                $fatal(1, "Unexpected RX byte %02x at %t", rxdata, $realtime);
            if (rxdata !== expected[received])
                $fatal(1, "RX[%0d]=%02x expected %02x at %t", received,
                       rxdata, expected[received], $realtime);
            received = received + 1;
        end
    end

    task automatic raw_bit(input reg b);
        begin
            if (!b) nrzi = ~nrzi;
            host_dp = nrzi;
            host_dn = ~nrzi;
            next_host_edge = next_host_edge + bit_ns;
            #(next_host_edge - $realtime);
        end
    endtask

    task automatic stuffed_byte(input reg [7:0] b);
        integer k;
        begin
            for (k = 0; k < 8; k = k + 1) begin
                raw_bit(b[k]);
                if (b[k]) ones = ones + 1; else ones = 0;
                if (ones == 6) begin
                    raw_bit(0);
                    ones = 0;
                end
            end
        end
    endtask

    task automatic packet;
        integer k;
        begin
            next_host_edge = $realtime;
            nrzi = 1;
            // HS SYNC: 15 KJ pairs followed by KK, NRZI 31 zeros then one.
            for (k = 0; k < 31; k = k + 1) raw_bit(0);
            raw_bit(1);
            ones = 1;
            for (k = 0; k < expected_count; k = k + 1)
                stuffed_byte(expected[k]);
            // Non-SOF HS EOP: deliberately unstuffed 0 followed by seven ones.
            raw_bit(0);
            for (k = 0; k < 7; k = k + 1) raw_bit(1);
            host_dp = 0;
            host_dn = 0;
        end
    endtask

    task automatic check_packet;
        begin
            received = 0;
            errors = 0;
            checking = 1;
            packet();
            #600;
            if (received != expected_count || errors != 0 || rxactive !== 0 || rxvalid !== 0)
                $fatal(1, "packet=%0d RX count=%0d/%0d errors=%0d active=%b valid=%b",
                       packets, received, expected_count, errors, rxactive, rxvalid);
            packets = packets + 1;
            total_received = total_received + received;
            checking = 0;
        end
    endtask

    task automatic data_packet(input integer length, input integer pattern);
        integer k, j;
        reg [15:0] crc;
        reg [7:0] b;
        begin
            expected[0] = packets[0] ? 8'h4b : 8'hc3;
            crc = 16'hffff;
            for (k = 0; k < length; k = k + 1) begin
                case (pattern)
                    0: b = 8'h00;
                    1: b = 8'hff;
                    default: b = ((k * 73) ^ (k >> 3) ^ (packets * 17)) & 255;
                endcase
                expected[k + 1] = b;
                for (j = 0; j < 8; j = j + 1)
                    if (crc[0] ^ b[j]) crc = (crc >> 1) ^ 16'ha001;
                    else crc = crc >> 1;
            end
            crc = ~crc;
            expected[length + 1] = crc[7:0];
            expected[length + 2] = crc[15:8];
            expected_count = length + 3;
            check_packet();
        end
    endtask

    task automatic rx_suite;
        integer p;
        begin
            expected[0] = 8'hd2;
            expected_count = 1;
            check_packet();
            data_packet(0, 0);
            data_packet(1, 1);
            data_packet(2, 2);
            data_packet(63, 2);
            data_packet(64, 2);
            data_packet(511, 2);
            for (p = 0; p < 3; p = p + 1) data_packet(512, p);
        end
    endtask

    initial begin
        if ($test$plusargs("VCD")) begin
            $dumpfile("/tmp/console_usb_phy_drift.vcd");
            $dumpvars(0, usb_phy_drift_tb);
        end
        #100 host_dp = 0;
        #100 locked = 1;
        #813.271 reset = 0;
        #20000;
        #(phase_ns);
        rx_suite();
        // Assert reset partway through an incoming packet; discard that packet,
        // and require the next complete packet to work without a stale byte.
        expected_count = 67;
        fork
            packet();
            begin #173.193; reset = 1; #501.117; reset = 0; end
        join
        #3000;
        rx_suite();
        // Simulate a PLL lock loss followed by the external reset sequence.
        #3.271 locked = 0;
        reset = 1;
        #503.337 locked = 1;
        #817.113 reset = 0;
        #10000;
        rx_suite();
        $display("RESULT host_ppm=%0.1f card_ppm=%0.1f phase_ns=%0.6f packets=%0d bytes=%0d",
                 host_ppm, card_ppm, phase_ns, packets, total_received);
        $display("PASS USB PHY independent serial clock");
        $finish;
    end
    initial begin #1000000; $fatal(1, "Timeout"); end
endmodule
