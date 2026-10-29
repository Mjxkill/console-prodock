// Simulation only. Direct GPU V1 boundary, not a hardware payload or DDR test.
// Exact frozen RTL must discriminate an empty CLEAR from one 32-byte write.
`timescale 1ns/1ps
module tb_clear_footprint;
  reg clk=0, rst=1, start=0;
  reg [255:0] command=0;
  reg [3:0] child_resetn=0;
  wire done, busy, valid, write, target_valid;
  wire [28:0] addr;
  wire [255:0] wr_data;
  wire [31:0] wr_mask, rejected;
  integer cycle=0, requests=0, phase=0, waits=0;
  wire ready=(cycle%7==6); // exercise VALID hold across several blocked cycles
  always #5 clk=~clk;
  gpu_v1 dut(.clk(clk),.rst(rst),.child_resetn(child_resetn),
    .start(start),.command(command),.done(done),.busy(busy),
    .observe_packet_word0(),.target_config_valid(target_valid),
    .material_config_valid(),.rejected(rejected),.fragments(),.passed(),
    .texture_hits(),.texture_misses(),.valid(valid),.write(write),.addr(addr),
    .wr_data(wr_data),.wr_mask(wr_mask),.ready(ready),
    .rd_valid(1'b0),.rd_data(256'd0));

  always @(posedge clk) begin
    cycle<=cycle+1;
    if(cycle>10000)$fatal(1,"bounded simulation timeout");
    if(!rst && valid)begin
      if(phase!=3)$fatal(1,"DMA during TARGET or zero-area CLEAR");
      if(!write || addr!==29'h04800000 || wr_mask!==0 || wr_data!=={16{16'h35c7}})
        $fatal(1,"unexpected native footprint/address/data/mask");
      if(ready)requests<=requests+1;
      else waits<=waits+1;
    end
  end

  task send;
    input [255:0] packet;
    integer count;
    begin
      @(negedge clk); command=packet; start=1;
      @(negedge clk); start=0;
      count=0;
      while(!done && count<1000)begin @(negedge clk); count=count+1; end
      if(!done)$fatal(1,"command did not finish");
      @(negedge clk);
    end
  endtask

  initial begin
    repeat(5)@(negedge clk);
    rst=0;child_resetn=15;
    repeat(5)@(negedge clk);
    phase=1;
    // TARGET color S, Z S+64, dimensions 16x1, strides 32 bytes.
    send({32'd0,32'd0,32'd0,32'h00200020,32'h00100001,
          32'h12000040,32'h12000000,32'h16000000});
    if(!target_valid || rejected!=0 || requests!=0)$fatal(1,"TARGET control failed");
    $display("PASS TARGET: done, no native request");
    phase=2;
    // The proposed w4..w7=0 CLEAR is legal but empty: it must issue no DMA.
    send({32'd0,32'd0,32'd0,32'd0,32'd0,32'h35c7,32'd1,32'h1c000000});
    if(rejected!=0 || requests!=0)$fatal(1,"empty CLEAR control failed");
    $display("PASS empty CLEAR: done, no native request");
    phase=3;
    send({32'd0,32'd0,32'h00100001,32'd0,32'd0,32'h35c7,32'd1,32'h1c000000});
    if(rejected!=0 || requests!=1 || waits==0)$fatal(1,"16x1 CLEAR footprint failed");
    $display("PASS 16x1 CLEAR: one native write, 32 bytes, stalls=%0d",waits);
    phase=4;
    repeat(10)@(negedge clk);
    if(requests!=1)$fatal(1,"late duplicate request");
    $display("PASS exact frozen RTL footprint; no hardware accessed");
    $finish;
  end
endmodule
