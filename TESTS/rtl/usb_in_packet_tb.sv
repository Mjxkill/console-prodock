`timescale 1ns/1ps
// A lost USB ACK must replay the same bytes and length, even if more UART
// bytes arrive before the host retries. Otherwise the host discards NEW
// bytes as part of the duplicate packet and acknowledges their removal.
module usb_in_packet_tb;
    reg clk=0;
    always #5 clk=~clk;
    reg reset=1,active=0,pop=0,ack=0,valid=0;
    reg [3:0] endpoint=2;
    reg [7:0] data=0;
    wire cork;
    wire [11:0] length;
    wire [7:0] out;
    usb_fifo dut(.i_clk(clk),.i_reset(reset),.i_usb_endpt(endpoint),
        .i_usb_rxact(1'b0),.i_usb_rxval(1'b0),.i_usb_rxpktval(1'b0),.i_usb_rxdat(8'd0),
        .i_usb_txact(active),.i_usb_txpop(pop),.i_usb_txpktfin(ack),
        .o_usb_txcork(cork),.o_usb_txlen(length),.o_usb_txdat(out),
        .i_ep2_tx_clk(clk),.i_ep2_tx_max(12'd64),.i_ep2_tx_dval(valid),.i_ep2_tx_data(data),
        .i_ep2_rx_clk(clk),.i_ep2_rx_rdy(1'b1));
    task append(input integer first,input integer n);
        for(integer i=0;i<n;i++) begin
            @(negedge clk);valid=1;data=8'(first+i);
        end
        @(negedge clk);valid=0;
        repeat(20) @(negedge clk);
    endtask
    task packet(input integer first,input integer n,input bit accepted);
        if(cork || length!=n) $fatal(1,"Packet length changed: got=%0d expected=%0d cork=%b",length,n,cork);
        active=1;
        repeat(4) @(negedge clk);
        for(integer i=0;i<n;i++) begin
            pop=1;
            if(out!==8'(first+i)) $fatal(1,"Packet byte %0d got=%02x expected=%02x",i,out,8'(first+i));
            @(negedge clk);
        end
        pop=0;
        repeat(3) @(negedge clk);
        if(accepted) begin ack=1;@(negedge clk);ack=0;end
        active=0;
        repeat(8) @(negedge clk);
    endtask
    initial begin
        repeat(5) @(negedge clk);reset=0;
        // The controller may keep txact high while waiting for data. A late
        // byte must open CORK together with its nonzero length, then both
        // must stay frozen while more bytes arrive.
        repeat(8) @(negedge clk);
        active=1;
        // A controller read strobe while no payload is available consumes
        // nothing in the FIFO and must not reserve an empty retry forever.
        pop=1; @(negedge clk); pop=0;
        append(200,1);
        if(cork || length!=1) $fatal(1,"Late UART byte must open a coherent IN: cork=%b length=%0d",cork,length);
        append(201,1);
        if(cork || length!=1) $fatal(1,"Open packet changed while another byte arrived");
        packet(200,1,1);
        packet(201,1,1);
        append(0,4);
        packet(0,4,0);
        append(4,7);
        endpoint=0; // intervening control transaction must not forget EP2
        repeat(8) @(negedge clk);
        endpoint=2;
        repeat(8) @(negedge clk);
        packet(0,4,1); // duplicate: must not include the 7 new bytes
        packet(4,7,1);
        if(!cork || length!=0) $fatal(1,"FIFO not empty after ACK");
        append(11,70);
        packet(11,64,0); // maximum packet; six bytes already queued behind it
        append(81,5);
        packet(11,64,0);
        append(86,3);
        packet(11,64,1);
        packet(75,14,1);
        append(89,1);
        packet(89,1,0);
        append(90,3);
        packet(89,1,1);
        packet(90,3,1);
        if(!cork || length!=0) $fatal(1,"FIFO not empty after repeated retries");
        append(93,2);
        packet(93,2,0);
        reset=1;repeat(5) @(negedge clk);reset=0;
        repeat(8) @(negedge clk);
        if(!cork || length!=0) $fatal(1,"USB reset retained a pending packet");
        append(100,5);
        endpoint=0;
        repeat(8) @(negedge clk);
        endpoint=2;active=1; // selection may arrive with the IN transaction
        repeat(4) @(negedge clk);
        packet(100,5,1);
        $display("PASS: USB retry retains its packet length while new UART data arrives");
        $finish;
    end
    initial begin #100000; $fatal(1,"timeout");end
endmodule
