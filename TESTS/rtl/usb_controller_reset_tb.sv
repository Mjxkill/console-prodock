// Exercise reset propagation through the original controller simulation model.
// No internal force: idle UTMI inputs, including the attach/J line state.
`timescale 1ns/1ps
module usb_controller_reset_tb;
    reg clk = 0, reset = 1, run_clock = 1;
    wire busreset;
`ifdef LEGACY_RESET
    wire app_reset = busreset;
`else
    wire app_reset = reset | busreset;
`endif
    reg write_byte = 0;
    wire empty;
    clk_cross_fifo fifo (
        .WrClock(clk), .RdClock(clk), .Reset(app_reset), .RPReset(app_reset),
        .WrEn(write_byte), .Data(8'h5a), .RdEn(1'b0), .Empty(empty)
    );
    always #8.333 if (run_clock) clk = ~clk;
    USB_Device_Controller_Top dut (
        .clk_i(clk),
        .reset_i(reset),
        .txdat_i('0),
        .txval_i('0),
        .txdat_len_i('0),
        .txiso_pid_i('0),
        .txcork_i(1'b1),
        .rxrdy_i(1'b1),
        .inf_alter_i('0),
        .descrom_rdata_i('0),
        .desc_dev_addr_i('0),
        .desc_dev_len_i('0),
        .desc_qual_addr_i('0),
        .desc_qual_len_i('0),
        .desc_fscfg_addr_i('0),
        .desc_fscfg_len_i('0),
        .desc_hscfg_addr_i('0),
        .desc_hscfg_len_i('0),
        .desc_oscfg_addr_i('0),
        .desc_hidrpt_addr_i('0),
        .desc_hidrpt_len_i('0),
        .desc_bos_addr_i('0),
        .desc_bos_len_i('0),
        .desc_strlang_addr_i('0),
        .desc_strvendor_addr_i('0),
        .desc_strvendor_len_i('0),
        .desc_strproduct_addr_i('0),
        .desc_strproduct_len_i('0),
        .desc_strserial_addr_i('0),
        .desc_strserial_len_i('0),
        .desc_have_strings_i('0),
        .utmi_txready_i(1'b1),
        .utmi_datain_i('0),
        .utmi_rxactive_i('0),
        .utmi_rxvalid_i('0),
        .utmi_rxerror_i('0),
        .utmi_linestate_i(2'b01),
        .usbrst_o(busreset)
    );
    initial begin
        #100.317;
        if (busreset !== 1) $fatal(1, "initial controller reset not propagated");
        reset = 0;
        wait (busreset === 0);
        $display("Controller bus reset released at %t", $realtime);
        for (integer n = 0; n < 8; n = n + 1) begin
            @(negedge clk); write_byte = 1;
            @(negedge clk); write_byte = 0;
            repeat (8) @(negedge clk);
            if (empty !== 0) $fatal(1, "FIFO did not contain the pre-reset byte");
            #(1.271 + n * 1.613);
            if (n[0]) run_clock = 0;
            reset = 1;
            #0.001;
            if (app_reset !== 1 || empty !== 1)
                $fatal(1, "FIFO reset does not follow system reset asynchronously");
            #33.719;
            if (app_reset !== 1 || empty !== 1)
                $fatal(1, "FIFO not reset while clock stopped");
            if (n[0]) begin
                #33.719;
                run_clock = 1;
            end
            repeat (4) @(negedge clk);
            if (busreset !== 1) $fatal(1, "controller reset not propagated with clock");
            #1.317 reset = 0;
            wait (busreset === 0);
            repeat (8) @(negedge clk);
            if (empty !== 1) $fatal(1, "stale byte survived common reset");
        end
        $display("PASS common application reset: 8 phases, 4 stopped clocks, no stale FIFO data");
        $finish;
    end
    initial begin #20000000; $fatal(1, "reset never released"); end
endmodule
