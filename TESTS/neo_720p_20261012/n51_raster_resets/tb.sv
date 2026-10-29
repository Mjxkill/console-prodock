`timescale 1ns/1ps
module tb;
reg clk=0,rst=1,start=0;
always #5 clk=~clk;
wire [1:0] child_resetn={2{!rst}};
reg [255:0] command=0,rd_data=0;
reg ready=0,rd_valid=0;
wire busy,done,valid,write;
wire [31:0] rejected,fragments,passed,wr_mask;
wire [28:0] addr;
wire [255:0] wr_data;
wire ref_busy,ref_done,ref_valid,ref_write;
wire [31:0] ref_rejected,ref_fragments,ref_passed,ref_wr_mask;
wire [28:0] ref_addr;
wire [255:0] ref_wr_data;
gpu_raster #(.WIDTH(32),.HEIGHT(16)) dut(.*);
gpu_raster_reference #(.WIDTH(32),.HEIGHT(16)) reference(
 .clk(clk),.rst(rst),.child_resetn(child_resetn),.start(start),.command(command),
 .ready(ready),.rd_valid(rd_valid),.rd_data(rd_data),
 .busy(ref_busy),.done(ref_done),.valid(ref_valid),.write(ref_write),
 .rejected(ref_rejected),.fragments(ref_fragments),.passed(ref_passed),
 .wr_mask(ref_wr_mask),.addr(ref_addr),.wr_data(ref_wr_data));
integer cycles=0,delay_left=0,transactions=0,resets=0,checks=0;
reg read_pending=0;
// One outstanding raster read, deterministic stalls and variable latency.
// Every input is shared by both implementations; the current one drives
// acceptance, so mismatched command timing is caught immediately.
always @(posedge clk)begin
 cycles<=cycles+1;
 if(rst)begin read_pending<=0;delay_left<=0;end
 else if(valid && ready)begin
  transactions<=transactions+1;
  if(!write)begin
   if(read_pending)$fatal(1,"Overlapping native reads");
   read_pending<=1;delay_left<=2+(cycles%7);
  end
 end else if(read_pending)begin
  if(delay_left==0)read_pending<=0;
  else delay_left<=delay_left-1;
 end
end
always @(negedge clk)begin
 ready=!rst && cycles%7!=3;
 rd_valid=!rst && read_pending && delay_left==0;
 rd_data={16{16'hffff}};
 if(!rst)begin
  checks++;
  if({busy,done,valid,rejected,fragments,passed}!==
     {ref_busy,ref_done,ref_valid,ref_rejected,ref_fragments,ref_passed})
   $fatal(1,"Control/counter mismatch at %0d",cycles);
  if(valid && {write,addr,wr_data,wr_mask}!==
              {ref_write,ref_addr,ref_wr_data,ref_wr_mask})
   $fatal(1,"Native transaction mismatch at %0d",cycles);
 end
end
task begin_command(input [255:0] words);
 begin
  @(negedge clk);command=words;
  repeat(2)@(negedge clk);
  start=1;@(negedge clk);start=0;
 end
endtask
task complete_command;
 integer timeout;
 begin
  timeout=0;
  while(!done && timeout<100000)begin @(negedge clk);timeout++;end
  if(!done)$fatal(1,"Command timeout, state=%h",dut.state);
  repeat(3)@(negedge clk);
 end
endtask
task configure;
 begin
  begin_command({96'd0,32'hf800,32'd128,32'd6,32'h10,32'h0e000000});
  complete_command();
  begin_command({160'd0,32'd0,32'h00640000,32'h12000000});
  complete_command();
 end
endtask
task triangle;
 begin begin_command({128'd0,32'h0006000c,32'h001a0002,32'h00020002,32'h13000000});end
endtask
integer phases[0:9]='{5,6,14,16,19,21,24,26,28,31};
integer target,timeout;
initial begin
 repeat(4)@(negedge clk);rst=0;
 for(integer scenario=0;scenario<10;scenario++)begin
  target=phases[scenario];configure();
  if(target==5 || target==6)
   begin_command({96'd0,32'd0,32'h00080008,32'd0,32'd15,32'h0f000000});
  else if(target==31)
   begin_command({128'd0,32'hffff,32'h1234,32'd3,32'h14000000});
  else triangle();
  timeout=0;
  while(!dut.state[target] && timeout<100000)begin @(negedge clk);timeout++;end
  if(!dut.state[target])$fatal(1,"Reset phase %0d not reached",target);
  // Assertion off-clock, held over several active edges.
  #1;rst=1;start=0;repeat(3)@(negedge clk);#1;rst=0;resets++;
  repeat(10)begin
   @(negedge clk);
   if(valid || done || busy || rejected || fragments || passed)
    $fatal(1,"Stale raster work after reset in phase %0d",target);
  end
  configure();triangle();complete_command();
  if(passed==0 || rejected!=0)$fatal(1,"Fresh rendering failed after phase %0d",target);
 end
 if(resets!=10 || transactions<100 || checks<1000)$fatal(1,"Insufficient coverage");
 $display("PASS: resets=%0d compared_cycles=%0d transactions=%0d",resets,checks,transactions);
 $finish;
end
initial begin #100000000;$fatal(1,"Global watchdog");end
endmodule
