`timescale 1ns/1ps
// Review probe: a locally flushed, unacknowledged EP1 packet must not be
// offered again when the flush occurred while another endpoint was selected.
module ep1_flush_review_tb;
reg clk=0, reset=1, flush=0;
always #8.333 clk=~clk;
reg [3:0] endpoint=1;
reg txact=0, txpop=0, txpktfin=0, dval=0;
reg [7:0] data=0;
reg [15:0] committed=0;
wire [15:0] sent;
wire [11:0] txlen;
wire cork;
wire [7:0] txdata;
integer selected=0, i;
usb_fifo dut(
 .i_clk(clk), .i_reset(reset), .i_usb_endpt(endpoint),
 .i_usb_txact(txact), .i_usb_txpop(txpop), .i_usb_txpktfin(txpktfin),
 .o_usb_txdat(txdata), .o_usb_txcork(cork), .o_usb_txlen(txlen),
 .i_usb_rxact(1'b0), .i_usb_rxval(1'b0), .i_usb_rxdat(8'b0), .i_usb_rxpktval(1'b0), .o_usb_rxrdy(),
 .i_ep1_tx_clk(clk), .i_ep1_tx_max(12'd512), .i_ep1_tx_dval(dval), .i_ep1_tx_data(data),
 .i_ep1_flush(flush), .i_ep1_tx_committed(committed), .o_ep1_tx_sent(sent),
 .i_ep1_rx_clk(clk), .i_ep1_rx_rdy(1'b1), .o_ep1_rx_dval(), .o_ep1_rx_data(),
 .i_ep2_tx_clk(clk), .i_ep2_tx_max(12'd512), .i_ep2_tx_dval(1'b0), .i_ep2_tx_data(8'b0),
 .i_ep2_rx_clk(clk), .i_ep2_rx_rdy(1'b1), .o_ep2_rx_dval(), .o_ep2_rx_data(), .diagnostic_data()
);
initial begin
 if($value$plusargs("FLUSH_ENDPOINT=%d",selected))begin end
 repeat(6) @(negedge clk); reset=0;
 for(i=0;i<13;i=i+1)begin @(negedge clk);dval=1;data=8'ha0+i;end
 @(negedge clk);dval=0;committed=13;
 repeat(12) @(negedge clk);
 if(cork || txlen!=13)$fatal(1,"initial packet not offered");
 txact=1;txpop=1;
 @(negedge clk);txpop=0;
 repeat(5) @(negedge clk);txact=0;
 repeat(5) @(negedge clk);
 if(!dut.tx_pending[1])$fatal(1,"no unacknowledged packet created");
 endpoint=selected;
 repeat(3) @(negedge clk); flush=1;committed=0;
 repeat(64) @(negedge clk);flush=0;
 repeat(5) @(negedge clk);endpoint=1;
 repeat(8) @(negedge clk);
 $display("FLUSH_ENDPOINT=%0d pending=%0b packet_ram_count=%0d offered=%0d cork=%0b retained_data=%h",selected,dut.tx_pending[1],dut.ep1_txlen,txlen,cork,txdata);
 if(!cork || txlen!=0 || dut.tx_pending[1])
   $fatal(1,"STALE_EP1_AFTER_FLUSH: an empty flushed FIFO still advertises the old packet");
 $display("PASS flushed packet not offered");$finish;
end
initial begin #100000;$fatal(1,"timeout");end
endmodule
