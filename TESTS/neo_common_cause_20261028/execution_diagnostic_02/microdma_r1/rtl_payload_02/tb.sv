
`timescale 1ns/1ps
module tb;
 reg clk=0,rst=1,start=0;reg[3:0] child_resetn=0;reg[255:0] command=0;
 wire done,busy,valid,write,target_valid;wire[28:0]addr;
 wire[255:0]data;wire[31:0]mask,rejected;
 integer cycle=0,phase=0,requests=0,waits=0;wire ready=cycle%7==6;
 always #5 clk=~clk;
 gpu_v1 dut(.clk(clk),.rst(rst),.child_resetn(child_resetn),.start(start),.command(command),
 .done(done),.busy(busy),.observe_packet_word0(),.target_config_valid(target_valid),
 .material_config_valid(),.rejected(rejected),.fragments(),.passed(),.texture_hits(),.texture_misses(),
 .valid(valid),.write(write),.addr(addr),.wr_data(data),.wr_mask(mask),.ready(ready),
 .rd_valid(1'b0),.rd_data(256'd0));
 always @(posedge clk)begin
  cycle<=cycle+1;if(cycle>10000)$fatal(1,"RTL timeout");
  if(!rst && valid)begin
   if(phase!=3 && phase!=5)$fatal(1,"Unexpected DMA phase%0d",phase);
   if(!write || addr!==29'h04800008 || data!=={16{16'h6b4d}})
    $fatal(1,"Wrong native footprint");
   if(mask!==(phase==3 ? 32'hfffffffc:32'd0))$fatal(1,"Wrong byte mask");
   if(ready)requests<=requests+1;else waits<=waits+1;
  end
 end
 task send(input[255:0] packet);
  integer n;
  begin @(negedge clk);command=packet;start=1;@(negedge clk);start=0;n=0;
   while(!done && n<1000)begin @(negedge clk);n=n+1;end
   if(!done)$fatal(1,"Command completion timeout");@(negedge clk);
  end
 endtask
 task reset;
  begin @(negedge clk);rst=1;child_resetn=0;repeat(5)@(negedge clk);
   rst=0;child_resetn=15;repeat(5)@(negedge clk);end
 endtask
 initial begin
  reset();phase=1;send({32'h00000000,32'h00000000,32'h00000000,32'h00200020,32'h00010010,32'h12000040,32'h12000020,32'h16000000});
  if(target_valid || rejected!=1 || requests!=0)$fatal(1,"Old TARGET was not rejected");
  send({32'h00000000,32'h00000000,32'h00010010,32'h00000000,32'h00000000,32'h00006b4d,32'h00000001,32'h1c000000});
  if(rejected!=2 || requests!=0)$fatal(1,"CLEAR after invalid TARGET must reject");
  $display("PASS actualBIN01: TARGET rejected, CLEAR rejected, zero DMA");
  reset();phase=2;send({32'h00000000,32'h00000000,32'h00000000,32'h00200020,32'h00100001,32'h12000040,32'h12000020,32'h16000000});
  if(!target_valid || rejected!=0 || requests!=0)$fatal(1,"New TARGET invalid");
  phase=3;send({32'h00000000,32'h00000000,32'h00010010,32'h00000000,32'h00000000,32'h00006b4d,32'h00000001,32'h1c000000});
  if(rejected!=0 || requests!=1)$fatal(1,"Transposed CLEAR clip mismatch");
  $display("PASS transposedCLEAR: valid TARGET16x1 clips rectangle1x16 to1pixel/2bytes");
  reset();phase=4;send({32'h00000000,32'h00000000,32'h00000000,32'h00200020,32'h00100001,32'h12000040,32'h12000020,32'h16000000});
  if(!target_valid || rejected!=0 || requests!=1)$fatal(1,"New TARGET second control");
  phase=5;send({32'h00000000,32'h00000000,32'h00100001,32'h00000000,32'h00000000,32'h00006b4d,32'h00000001,32'h1c000000});
  if(rejected!=0 || requests!=2 || waits==0)$fatal(1,"New CLEAR footprint mismatch");
  phase=6;repeat(15)@(negedge clk);
  if(requests!=2)$fatal(1,"Late duplicate DMA");
  $display("PASS actualBIN02: TARGET valid, CLEAR1nativewrite32bytes, stalls%0d",waits);
  $finish;
 end
endmodule
