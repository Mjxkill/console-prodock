// Application-level edge cases complementing the integrated HS/CRC tests.
`timescale 1ns/1ps
module usb_uart_config_recovery_tb;
reg clk=0,run_clock=1,reset=1,setup=0,rxval=0,txact=0,pop=0,finish=0;
reg [3:0] endpoint=0;
reg [7:0] rxdata=0;
reg [511:0] diagnostic=0;
wire [11:0] length;
wire [7:0] data;
wire send;
always #5 if(run_clock)clk=~clk;
usb_uart_config dut(.PHY_CLKOUT(clk),.RESET_IN(reset),.setup_active(setup),
 .endpt_sel(endpoint),.usb_rxval(rxval),.usb_rxact(1'b0),.usb_rxdat(rxdata),
 .usb_txact(txact),.usb_txpop(pop),.usb_txpktfin(finish),
 .diagnostic_data(diagnostic),.usb_txdat_len_o(length),
 .endpt0_dat_o(data),.endpt0_send_o(send));
integer checked=0;
task request(input bit debug_mode);
 reg [63:0] bytes;
 begin
  endpoint=0;txact=0;pop=0;finish=0;setup=1;
  bytes={16'(debug_mode?32:7),16'd0,debug_mode?16'hd1a6:16'd0,8'h21,8'ha1};
  for(integer i=0;i<8;i++)begin rxval=1;rxdata=bytes[i*8+:8];@(negedge clk);end
  setup=0;rxval=0;repeat(3)@(negedge clk);
  if(!send || length!=(debug_mode?32:7))$fatal(1,"request offer missing");
 end
endtask
task take(input [255:0] expected,input integer count);
 begin
  endpoint=0;txact=1;
  for(integer i=0;i<count;i++)begin
   if(!send || data!==expected[i*8+:8])
    $fatal(1,"byte %0d got=%02x expected=%02x send=%b",i,data,expected[i*8+:8],send);
   pop=1;@(negedge clk);pop=0;@(negedge clk);checked++;
  end
 end
endtask
task accept;
 begin
  finish=1;@(negedge clk);finish=0;
  if(send)$fatal(1,"EP0 FIN did not retire response");
  txact=0;repeat(3)@(negedge clk);
 end
endtask
reg [255:0] saved;
initial begin
 repeat(5)@(negedge clk);reset=0;repeat(3)@(negedge clk);
 for(integer i=0;i<64;i++)diagnostic[i*8+:8]=8'(i*7+3);
 saved=diagnostic[255:0];request(1);diagnostic=~diagnostic;
 // Partial attempt, another endpoint and its FIN, then retransmission.
 take(saved,3);txact=0;repeat(3)@(negedge clk);
 endpoint=2;txact=1;finish=1;@(negedge clk);finish=0;
 if(!dut.endpt0_pending)$fatal(1,"foreign endpoint FIN retired EP0");
 txact=0;endpoint=0;repeat(3)@(negedge clk);
 take(saved,32);
 // End each attempt, then request three further complete retries.
 repeat(3)begin txact=0;repeat(3)@(negedge clk);take(saved,32);end
 accept();
 // New SETUP discards a partially consumed diagnostic response.
 request(1);saved=diagnostic[255:0];take(saved,4);txact=0;
 request(0);take(256'h0800000001c200,7);accept();
 // New SETUP also discards a complete but unacknowledged ordinary response.
 request(0);take(256'h0800000001c200,7);txact=0;
 request(1);saved=diagnostic[255:0];take(saved,32);
 // Common reset must discard the pending response even with no clock.
 txact=0;@(negedge clk);run_clock=0;#2;reset=1;#1;
 if(send || dut.sub_stage!=0 || dut.diagnostic_snapshot!=0)
  $fatal(1,"stale EP0 state survives reset with stopped clock");
 #23;run_clock=1;repeat(3)@(negedge clk);reset=0;repeat(3)@(negedge clk);
 if(send)$fatal(1,"stale EP0 offer reappeared after reset");
 request(0);take(256'h0800000001c200,7);accept();
 $display("PASS EP0 application recovery: %0d bytes, partial/full repeated retries, frozen snapshot, foreign FIN, SETUP preemption and stopped-clock reset",checked);
 $finish;
end
initial begin #100000;$fatal(1,"timeout");end
endmodule
