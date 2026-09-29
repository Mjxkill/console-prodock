`timescale 1ns/1ps
// Deterministic concurrent UART producer/USB consumer, including lost ACKs.
// 30,000 bytes cover multiple complete wraps of the 13-bit packet pointers.
module usb_stream_tb;
 reg clk=0; always #5 clk=~clk;
 reg reset=1,active=0,pop=0,ack=0,valid=0;
 reg [3:0] endpoint=2;
 reg [7:0] data=0;
 wire cork; wire [11:0] length; wire [7:0] out;
 integer produced=0,committed=0,packets=0,retries=0;
 reg [31:0] rng=32'h12345678;
 function automatic [7:0] pattern(input integer n); return 8'((n*73)^(n>>8)); endfunction
 usb_fifo dut(.i_clk(clk),.i_reset(reset),.i_usb_endpt(endpoint),
  .i_usb_rxact(1'b0),.i_usb_rxval(1'b0),.i_usb_rxpktval(1'b0),.i_usb_rxdat(8'd0),
  .i_usb_txact(active),.i_usb_txpop(pop),.i_usb_txpktfin(ack),
  .o_usb_txcork(cork),.o_usb_txlen(length),.o_usb_txdat(out),
  .i_ep2_tx_clk(clk),.i_ep2_tx_max(12'd64),.i_ep2_tx_dval(valid),.i_ep2_tx_data(data),
  .i_ep2_rx_clk(clk),.i_ep2_rx_rdy(1'b1));
 always @(posedge clk) if(!reset && valid)produced++;
 always @(negedge clk) begin
  rng=(rng<<1)^ (rng[31]?32'h04c11db7:0);
  valid=!reset && produced<30000 && produced-committed<128 && rng[3:0]==0;
  data=pattern(produced);
 end
 task tick(input integer n); repeat(n) @(negedge clk); #1; endtask
 initial begin
  integer n,waiting_len; bit accept;
  tick(5);reset=0;waiting_len=0;
  while(committed<30000)begin
   tick(8+int'(rng[2:0]));
   if(cork)continue;
   n=length;
   if(waiting_len && n!=waiting_len)$fatal(1,"retry len %0d/%0d",n,waiting_len);
   active=1;tick(4);
   for(integer i=0;i<n;i++)begin
    if(out!==pattern(committed+i))$fatal(1,"byte got=%h expected=%h committed=%0d i=%0d n=%0d produced=%0d",out,pattern(committed+i),committed,i,n,produced);
    pop=1;tick(1);pop=0;
    if(rng[4])tick(1);
   end
   tick(4);
   accept=rng[5:4]!=0;
   if(accept)begin ack=1;tick(1);ack=0;committed+=n;waiting_len=0;end
   else begin waiting_len=n;retries++;end
   active=0;packets++;
  end
  $display("PASS concurrent USB stream %0d bytes %0d packets %0d retries",committed,packets,retries);$finish;
 end
 initial begin #100000000; $fatal(1,"timeout"); end
endmodule
