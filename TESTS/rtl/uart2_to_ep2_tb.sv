`timescale 1ns/1ps
module uart2_to_ep2_tb;
    reg clk=0;
    always #5 clk=~clk; // temps relatif : cycles/bit du domaine réel 60 MHz
    reg reset=1, uart_tx=1;
    wire uart_rx, rx_valid, ready, ep_valid;
    wire [7:0] rx_data, ep_data;
    reg usb_active=0, usb_valid=0, usb_packet=0;
    reg [7:0] usb_data=0;
    wire usb_ready;
    uart2_to_ep2 dut(.phy_clk(clk), .reset(reset), .uart2_txd(uart_tx),
        .uart2_rxd(uart_rx), .uart_rx_data_val(rx_valid), .uart_rx_data(rx_data),
        .ep2_rx_dval(ep_valid), .ep2_rx_data(ep_data), .ep2_rx_rdy(ready));
    usb_rx_buf #(.P_ENDPOINT(2), .P_AFULL(400), .P_ASIZE(9)) usb (
        .i_clk(clk), .i_reset(reset), .i_usb_endpt(4'd2),
        .i_usb_rxact(usb_active), .i_usb_rxpktval(usb_packet),
        .i_usb_rxval(usb_valid), .i_usb_rxdat(usb_data), .o_usb_rxrdy(usb_ready),
        .i_ep_clk(clk), .i_ep_rx_rdy(ready), .o_ep_rx_dval(ep_valid), .o_ep_rx_data(ep_data));
    integer received=0, transmitted=0;
    reg [7:0] expected_rx[$];
    reg [7:0] tx_byte;
    always @(posedge clk) if (!reset) begin
        if (rx_valid) begin
            if (expected_rx.size()==0) $fatal(1,"RX octet parasite %02x",rx_data);
            if (rx_data !== expected_rx.pop_front()) $fatal(1,"RX octet incorrect #%0d",received);
            received++;
        end
        if (dut.tx_count > 8) $fatal(1,"FIFO TX débordée");
    end
    initial forever begin
        @(negedge uart_rx);
        if (!reset) begin
            repeat(260) @(negedge clk);
            if (uart_rx !== 0) $fatal(1,"TX start");
            for (integer b=0;b<8;b++) begin
                repeat(521) @(negedge clk);
                tx_byte[b]=uart_rx;
            end
            repeat(521) @(negedge clk);
            if (uart_rx !== 1) $fatal(1,"TX stop");
            if (tx_byte !== 8'(transmitted)) $fatal(1,"TX #%0d reçu %02x",transmitted,tx_byte);
            transmitted++;
        end
    end
    task send_uart(input byte value, input integer cycles);
        expected_rx.push_back(value);
        @(negedge clk); uart_tx=0;
        repeat(cycles) @(negedge clk);
        for(integer b=0;b<8;b++) begin
            uart_tx=value[b];
            repeat(cycles) @(negedge clk);
        end
        uart_tx=1;
        repeat(cycles) @(negedge clk);
    endtask
    initial begin
        repeat(8) @(negedge clk); reset=0;
        // Faux départ, break et récupération ne doivent pas produire d'octet.
        uart_tx=0; repeat(60) @(negedge clk); uart_tx=1;
        repeat(600) @(negedge clk);
        uart_tx=0; repeat(12000) @(negedge clk); uart_tx=1;
        repeat(600) @(negedge clk);
        fork
            begin
                // Rafales USB : 256 octets en 4 paquets, sérialisation ~22 ms.
                for(integer p=0;p<4;p++) begin
                    usb_active=1;
                    repeat(8) @(negedge clk);
                    for(integer b=0;b<64;b++) begin
                        usb_valid=1; usb_data=8'(p*64+b);
                        @(negedge clk);
                    end
                    usb_valid=0;
                    repeat(4) @(negedge clk);
                    usb_packet=1; @(negedge clk); usb_packet=0;
                    usb_active=0;
                    repeat(8) @(negedge clk);
                end
            end
            begin
                for(integer n=0;n<256;n++) send_uart(8'(n),521);
                // UART AE350 APB 80 MHz / (16 * 43) : 516 cycles USB / bit.
                for(integer n=0;n<256;n++) send_uart(8'(n),516);
                for(integer n=0;n<32;n++) send_uart(8'(n),531);
            end
        join
        wait(transmitted==256);
        repeat(6000) @(negedge clk);
        if(received!=544 || expected_rx.size()!=0) $fatal(1,"RX manquant");
        $display("PASS : RX 544 octets, TX 256 octets en rafales via usb_rx_buf, aucun octet perdu/dupliqué; faux départ/break rejetés.");
        $finish;
    end
    initial begin #40000000; $fatal(1,"timeout"); end
endmodule
