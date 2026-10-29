`timescale 1ns/1ps
// Exact public engine, no memory transactions expected for any empty case.
module bench;
  reg clk=0,rst=1,start=0;always #5 clk=~clk;
  reg[255:0] command=0;reg[29:0] dst_base=30'h12000020;
  reg[15:0] dst_stride=32,dst_height=1;
  wire done,bad,valid,write;wire[28:0] addr;wire[255:0] wr_data;wire[31:0] wr_mask;
  gpu_copy565 dut(.clk(clk),.rst(rst),.start(start),.command(command),
    .dst_base(dst_base),.dst_stride(dst_stride),.dst_height(dst_height),
    .clip_l(16'd0),.clip_t(16'd0),.clip_r(16'd16),.clip_b(16'd1),
    .done(done),.bad(bad),.valid(valid),.write(write),.addr(addr),
    .wr_data(wr_data),.wr_mask(wr_mask),.ready(1'b0),.rd_valid(1'b0),.rd_data(256'd0));
  reg[31:0] words[0:7];integer force_end=0,requests=0,pulses=0;
  always @(posedge clk)if(!rst && valid)requests<=requests+1;
  initial begin
    integer cycles,seen,obs_bad;
    $value$plusargs("force_end=%d",force_end);
    $readmemh("packet.hex",words);
    for(integer i=0;i<8;i=i+1)command[i*32+:32]=words[i];
    if(force_end)force dut.src_end=33'h012000060;
    repeat(4)@(negedge clk);rst=0;@(negedge clk);start=1;
    @(negedge clk);start=0;cycles=0;seen=0;obs_bad=0;
    while(!seen && cycles<200)begin
      @(posedge clk);#1;cycles=cycles+1;
      if(done)begin seen=1;pulses=pulses+1;obs_bad=bad;end
    end
    repeat(20)begin @(posedge clk);#1;if(done)pulses=pulses+1;end
    $display("RESULT done=%0d bad=%0d requests=%0d cycles=%0d",pulses,obs_bad,requests,cycles);
    $finish;
  end
  initial begin #5000;$fatal(1,"watchdog");end
endmodule
