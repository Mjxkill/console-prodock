`timescale 1ns/1ps
module tb;
reg clk=0,rst=1,start=0;
always #5 clk=~clk;
wire [3:0] child_resetn={4{!rst}};
reg [255:0] command=0,rd_data=0,accepted_packet=0;
wire ready=1'b1,rd_valid=1'b0;
wire done,busy,target_config_valid,material_config_valid,valid,write;
wire ref_done,ref_busy,ref_target_config_valid,ref_material_config_valid,ref_valid,ref_write;
wire [31:0] rejected,fragments,passed,texture_hits,texture_misses,wr_mask;
wire [31:0] ref_rejected,ref_fragments,ref_passed,ref_texture_hits,ref_texture_misses,ref_wr_mask;
wire [28:0] addr,ref_addr;
wire [255:0] wr_data,ref_wr_data;
gpu_v1 dut(.*);
gpu_v1_reference reference(.clk(clk),.rst(rst),.start(start),.child_resetn(child_resetn),
.command(command),.ready(ready),.rd_valid(rd_valid),.rd_data(rd_data),
.done(ref_done),.busy(ref_busy),.target_config_valid(ref_target_config_valid),.material_config_valid(ref_material_config_valid),.rejected(ref_rejected),.fragments(ref_fragments),.passed(ref_passed),.texture_hits(ref_texture_hits),.texture_misses(ref_texture_misses),.valid(ref_valid),.write(ref_write),.addr(ref_addr),.wr_data(ref_wr_data),.wr_mask(ref_wr_mask));
integer cycles=0,busy_checks=0,idle_differences=0,resets=0,completed=0;
reg [31:0] noise=32'h139aec62;
always @(negedge clk)begin
 cycles=cycles+1;
 if(!rst)begin
  if({done,busy,target_config_valid,material_config_valid,rejected,fragments,passed,texture_hits,texture_misses,valid} !==
     {ref_done,ref_busy,ref_target_config_valid,ref_material_config_valid,ref_rejected,ref_fragments,ref_passed,ref_texture_hits,ref_texture_misses,ref_valid})
   $fatal(1,"Observable mismatch cycle=%0d",cycles);
  if(valid!==1'b0)$fatal(1,"Unexpected memory request from configuration/reset sequence");
  if(busy)begin
   busy_checks=busy_checks+1;
   if(dut.packet!==reference.packet || dut.packet!==accepted_packet)$fatal(1,"Packet changed while busy");
  end else if(dut.packet!==reference.packet)idle_differences=idle_differences+1;
 end
end
task tick;
 begin @(negedge clk);#1;noise={noise[30:0],noise[31]^noise[21]^noise[1]^noise[0]};command={8{noise}};end
endtask
task submit(input [255:0] data);
 begin
  if(busy)$fatal(1,"Submit while busy");
  repeat(3)tick();command=data;accepted_packet=data;start=1;tick();start=0;
 end
endtask
task finish_command;
 integer n;
 begin
  n=0;while(!done && n<100)begin tick();n=n+1;end
  if(!done)$fatal(1,"Command timeout, state=%h",dut.state);
  tick();completed=completed+1;
 end
endtask
task reset_during(input integer phase,input [255:0] data);
 integer n;
 begin
  submit(data);n=0;
  while(!dut.state[phase] && n<100)begin tick();n=n+1;end
  if(!dut.state[phase])$fatal(1,"Reset phase unreachable %0d",phase);
  rst=1;repeat(3)tick();rst=0;repeat(4)tick();resets=resets+1;
  if(target_config_valid!==0 || material_config_valid!==0 || busy!==0 || done!==0 || rejected!==0)
    $fatal(1,"Old descriptor/work survived reset");
  submit(256'h000000000000000000000000000000000000000000000000000000001b000000);finish_command();
  if(rejected!==1)$fatal(1,"Draw without reconfiguration was not rejected");
 end
endtask
initial begin
 repeat(4)tick();rst=0;repeat(3)tick();
 reset_during(48,256'h0000000000000000000000000040004000200040120010001200000016000000);
 reset_during(56,256'h0000000000000000000000000040004000200040120010001200000016000000);
 reset_during(45,256'h0000000000000000000000000040004000200040120010001200000016000000);
 reset_during(46,256'h0000000000000000000000000040004000200040120010001200000016000000);
 reset_during(3,256'h0000000000000000000000000040004000200040120010001200000016000000);
 reset_during(57,256'h0000000000000000000000000040004000200040120010001200000016000000);
 reset_during(49,256'h0000000000000000000000000040004000200040120010001200000016000000);
 reset_during(47,256'h0000000000000000000000000000000000000020000100010170000018000000);
 reset_during(4,256'h0000000000000000000000000000000000000020000100010170000018000000);
 reset_during(50,256'h0000000000000000000000000000000000000020000100010170000018000000);
 reset_during(2,256'h0000000000000000000000000040004000200040120010001200000016000000);
 reset_during(1,256'h0000000000000000000000000020002000000010000010000000000016000000);
 submit(256'h0000000000000000000000000040004000200040120010001200000016000000);finish_command();
 if(target_config_valid!==1'b1)$fatal(1,"TARGET verdict preflight");
 submit(256'h0000000000000000000000000800080004000200009000000080000016000000);finish_command();
 if(target_config_valid!==1'b1)$fatal(1,"TARGET verdict maximum");
 submit(256'h0000000000000000000000000020002000080010000010000000000016000000);finish_command();
 if(target_config_valid!==1'b1)$fatal(1,"TARGET verdict small");
 submit(256'h0000000000000000000000000020002000000010000010000000000016000000);finish_command();
 if(target_config_valid!==1'b0)$fatal(1,"TARGET verdict zero_width");
 submit(256'h0000000000000000000000000020002000080000000010000000000016000000);finish_command();
 if(target_config_valid!==1'b0)$fatal(1,"TARGET verdict zero_height");
 submit(256'h0000000000000000000000000020002000080010000010000000000116000000);finish_command();
 if(target_config_valid!==1'b0)$fatal(1,"TARGET verdict unaligned_color");
 submit(256'h0000000000000000000000000020002000080010000000030000000016000000);finish_command();
 if(target_config_valid!==1'b0)$fatal(1,"TARGET verdict unaligned_depth");
 submit(256'h0000000000000000000000000020002000080010000000000000000016000000);finish_command();
 if(target_config_valid!==1'b0)$fatal(1,"TARGET verdict overlap");
 submit(256'h0000000000000000000000000020002000200010000010000000000016000000);finish_command();
 if(target_config_valid!==1'b0)$fatal(1,"TARGET verdict short_stride");
 submit(256'h0000000000000000000000000020002000080010000010003fffffe016000000);finish_command();
 if(target_config_valid!==1'b0)$fatal(1,"TARGET verdict overflow");
 submit(256'h0000000000000000000000000020002000080010001000000000000016000000);finish_command();
 if(target_config_valid!==1'b1)$fatal(1,"TARGET verdict base_00000000_8x16");
 submit(256'h0000000000000000000000000040004000200040001000000000000016000000);finish_command();
 if(target_config_valid!==1'b1)$fatal(1,"TARGET verdict base_00000000_32x64");
 submit(256'h00000000000000000000000003200320019000f0001000000000000016000000);finish_command();
 if(target_config_valid!==1'b1)$fatal(1,"TARGET verdict base_00000000_400x240");
 submit(256'h0000000000000000000000000020002000080010009000000080000016000000);finish_command();
 if(target_config_valid!==1'b1)$fatal(1,"TARGET verdict base_00800000_8x16");
 submit(256'h0000000000000000000000000040004000200040009000000080000016000000);finish_command();
 if(target_config_valid!==1'b1)$fatal(1,"TARGET verdict base_00800000_32x64");
 submit(256'h00000000000000000000000003200320019000f0009000000080000016000000);finish_command();
 if(target_config_valid!==1'b1)$fatal(1,"TARGET verdict base_00800000_400x240");
 submit(256'h0000000000000000000000000020002000080010101000001000000016000000);finish_command();
 if(target_config_valid!==1'b1)$fatal(1,"TARGET verdict base_10000000_8x16");
 submit(256'h0000000000000000000000000040004000200040101000001000000016000000);finish_command();
 if(target_config_valid!==1'b1)$fatal(1,"TARGET verdict base_10000000_32x64");
 submit(256'h00000000000000000000000003200320019000f0101000001000000016000000);finish_command();
 if(target_config_valid!==1'b1)$fatal(1,"TARGET verdict base_10000000_400x240");
 submit(256'h0000000000000000000000000020002000080010121000001200000016000000);finish_command();
 if(target_config_valid!==1'b1)$fatal(1,"TARGET verdict base_12000000_8x16");
 submit(256'h0000000000000000000000000040004000200040121000001200000016000000);finish_command();
 if(target_config_valid!==1'b1)$fatal(1,"TARGET verdict base_12000000_32x64");
 submit(256'h00000000000000000000000003200320019000f0121000001200000016000000);finish_command();
 if(target_config_valid!==1'b1)$fatal(1,"TARGET verdict base_12000000_400x240");
 submit(256'h0000000000000000000000000020002000080010201000002000000016000000);finish_command();
 if(target_config_valid!==1'b1)$fatal(1,"TARGET verdict base_20000000_8x16");
 submit(256'h0000000000000000000000000040004000200040201000002000000016000000);finish_command();
 if(target_config_valid!==1'b1)$fatal(1,"TARGET verdict base_20000000_32x64");
 submit(256'h00000000000000000000000003200320019000f0201000002000000016000000);finish_command();
 if(target_config_valid!==1'b1)$fatal(1,"TARGET verdict base_20000000_400x240");
 submit(256'h0000000000000000000000000020002000080010301000003000000016000000);finish_command();
 if(target_config_valid!==1'b1)$fatal(1,"TARGET verdict base_30000000_8x16");
 submit(256'h0000000000000000000000000040004000200040301000003000000016000000);finish_command();
 if(target_config_valid!==1'b1)$fatal(1,"TARGET verdict base_30000000_32x64");
 submit(256'h00000000000000000000000003200320019000f0301000003000000016000000);finish_command();
 if(target_config_valid!==1'b1)$fatal(1,"TARGET verdict base_30000000_400x240");
 submit(256'h0000000000000000000000000040004000200040120010001200000016000000);finish_command();
 if(target_config_valid!==1'b1)$fatal(1,"TARGET verdict preflight_again");
 if(busy_checks<100 || idle_differences<30 || resets!=12)$fatal(1,"Insufficient coverage");
 $display("PACKET_RESET_PASS cycles=%0d busy_checks=%0d idle_differences=%0d resets=%0d completed=%0d",cycles,busy_checks,idle_differences,resets,completed);
 $finish;
end
initial begin #1000000;$fatal(1,"Watchdog");end
endmodule
