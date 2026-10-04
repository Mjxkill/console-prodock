`timescale 1ns/1ps
module usb_control_diag_tb;
reg clk=0;always #5 clk=~clk;
reg reset=1,setup=0,rxval=0,txact=0,pop=0,finish=0;
reg [7:0] rxdata=0;
reg [511:0] diagnostic=0;
wire [11:0] length;
wire [7:0] data;
wire send;
usb_uart_config dut(.PHY_CLKOUT(clk),.RESET_IN(reset),.setup_active(setup),
 .endpt_sel(4'd0),.usb_rxval(rxval),.usb_rxact(1'b0),.usb_rxdat(rxdata),
 .usb_txact(txact),.usb_txpop(pop),.usb_txpktfin(finish),.diagnostic_data(diagnostic),
 .usb_txdat_len_o(length),.endpt0_dat_o(data),.endpt0_send_o(send));
task get(input integer debug_mode);
 reg [63:0] request;
 reg [255:0] expected;
 integer n;
 begin
  n=debug_mode?32:7;
  request={16'(n),16'd0,(debug_mode==2?16'hd1a7:debug_mode==1?16'hd1a6:16'd0),8'h21,(debug_mode?8'ha0:8'ha1)};
  expected=debug_mode==2?diagnostic[511:256]:debug_mode==1?diagnostic[255:0]:256'h0800000001c200;
  setup=1;
  for(integer i=0;i<8;i++)begin rxval=1;rxdata=request[i*8+:8];@(negedge clk);end
  setup=0;rxval=0;txact=1;diagnostic=~diagnostic;
  repeat(4)@(negedge clk);
  if(!send || length!=n)$fatal(1,"reply length/send");
  for(integer i=0;i<n;i++)begin
   if(data!==expected[i*8+:8])$fatal(1,"byte %0d got=%x expected=%x",i,data,expected[i*8+:8]);
   pop=1;@(negedge clk);pop=0;@(negedge clk);
  end
  if(send || !dut.endpt0_pending)$fatal(1,"attempt end/pending contract");
  // Lost ACK: the same snapshot must be offered again, despite live changes.
  txact=0;repeat(3)@(negedge clk);txact=1;
  for(integer i=0;i<n;i++)begin
   if(data!==expected[i*8+:8])$fatal(1,"retry byte %0d got=%x expected=%x",i,data,expected[i*8+:8]);
   pop=1;@(negedge clk);pop=0;@(negedge clk);
  end
  finish=1;@(negedge clk);finish=0;
  if(send)$fatal(1,"reply did not retire after ACK");
  txact=0;repeat(5)@(negedge clk);
 end
endtask
initial begin
 repeat(5)@(negedge clk);reset=0;repeat(5)@(negedge clk);
 get(0);
 for(integer i=0;i<64;i++)diagnostic[i*8+:8]=8'(i*7);
 get(1);get(2);get(0);
 $display("PASS: standard CDC 7 bytes, two diagnostic snapshots of 32 bytes, standard CDC restored");$finish;
end
initial begin #100000;$fatal(1,"timeout");end
endmodule
