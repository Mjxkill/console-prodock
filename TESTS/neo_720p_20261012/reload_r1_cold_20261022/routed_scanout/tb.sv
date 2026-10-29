`timescale 1ns/1ps
module tb;
GSR GSR(.GSRI(1'b1));
reg hclk=0,clock_model=0,pclk=0,resetn=0,hwrite=0,htrans=0,response_valid=0;
reg [14:0] haddr=0;
reg [31:0] hwdata=0;
reg [255:0] response_data={16{16'hffff}};
wire request_valid_out,ack,pending,mem_up;
wire [27:0] request_address;
always #6.25 hclk=~hclk;
initial begin #0.371; forever #6.666667 clock_model=~clock_model; end
initial begin #1.123; forever #6.722689 pclk=~pclk; end
mapped_gpu dut(.*);
integer requested=0,returned=0,completed=0;
reg [15:0] pipeline=0;
always @(posedge clock_model)begin
 if(!resetn)begin pipeline<=0;requested<=0;returned<=0;end
 else begin
  pipeline<={pipeline[14:0],request_valid_out};
  if(request_valid_out)begin
   if(request_address!==28'h05c0000+requested*8)
    $fatal(1,"Wrong DDR address %h number %d",request_address,requested);
   requested<=requested+1;
  end
  if(response_valid)returned<=returned+1;
 end
end
always @(negedge clock_model)response_valid=resetn && pipeline[15];
task write_reg(input [14:0] address,input [31:0] value);
 @(negedge hclk);htrans=1;hwrite=1;haddr=address;
 @(negedge hclk);htrans=0;hwdata=value;
 @(negedge hclk);hwdata=0;hwrite=0;
endtask
integer waits;
initial begin
 repeat(16)@(negedge hclk);resetn=1;
 repeat(30)@(negedge hclk);
 if(mem_up!==1)$fatal(1,"Memory reset did not release");
 write_reg('h0004,'h01700000);
 write_reg('h006c,2560);
 write_reg('h0030,0);
 write_reg('h0040,0);
 write_reg('h0008,3);
 write_reg('h000c,1);
 repeat(30)@(negedge pclk);
 // Exercise genuine decode by placing counters immediately before vblank.
 // The request/ACK, readers, queue and their resets remain unmodified.
 force dut.\u_gpu/hx =11'd0;
 force dut.\u_gpu/vy =10'd745;
 @(posedge pclk); #1;
 release dut.\u_gpu/hx ;release dut.\u_gpu/vy ;
 waits=0;
 while(ack!==1 && waits<2000)begin @(negedge clock_model);waits=waits+1;end
 $display("SCANOUT requested=%0d returned=%0d ack=%b pending=%b reset=%b",requested,returned,ack,pending,mem_up);
 if(ack!==1 || pending!==0 || requested!==80 || returned!==80)
  $fatal(1,"First RGB line did not complete exactly");
 $display("PASS routed scanout first line: 80 ordered DDR bursts, request/ACK completed");
 $finish;
end
initial begin #1000000;$fatal(1,"Watchdog");end
endmodule
