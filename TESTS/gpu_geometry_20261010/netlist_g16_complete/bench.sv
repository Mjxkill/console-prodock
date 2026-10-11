`timescale 1ns/1ps
module tb;
reg clk=0,resetn=0,start=0,accepted=0,rv=0;
reg [255:0] packet=0,rd=0;
wire done,fetch;
wire [28:0] fetch_address;
wire [31:0] errors,vertices,triangles,culled,clipped,slivers;
GSR GSR(.GSRI(1'b1));
always #6.666 clk=~clk;
gpu_geometry dut(.gpu_clk(clk),.engine_resetn(resetn),.v1_select(1'b1),.ext_start_Z(start),
 .v1_accepted(accepted),.v1_rx_valid(rv),.ext_command(packet),.v1_rx_data(rd),
 .v1_done(done),.fetch_valid(fetch),.fetch_addr_0(fetch_address[0]),.fetch_addr_1(fetch_address[1]),.fetch_addr_2(fetch_address[2]),.fetch_addr_24(fetch_address[24]),.fetch_addr_25(fetch_address[25]),.fetch_addr_26(fetch_address[26]),.fetch_addr_27(fetch_address[27]),
 .\geometry_stat[0] (errors),.\geometry_stat[1] (vertices),.\geometry_stat[2] (triangles),
 .\geometry_stat[3] (culled),.\geometry_stat[4] (clipped),.\geometry_stat[5] (slivers));
assign fetch_address[23:3]=dut.fetch_addr_3;
assign fetch_address[28]=0;
reg [7:0] memory[0:3145727];
reg [31:0] commands[0:7416-1],shader[0:43080-1];
integer word_index=0,reads=0,cycle=0,pending=0,byte_address=0;
function automatic integer index(input integer address);
 if(address>='h1700000 && address<'h1800000)return 2097152+address-'h1700000;
 $fatal(1,"Unexpected mesh read %h",address);return 0;
endfunction
always @(negedge clk)begin
 cycle++;accepted=0;rv=0;
 if(resetn)begin
  if(pending!=0)begin
   pending--;
   if(pending==0)begin rv=1;for(integer b=0;b<32;b++)rd[b*8+:8]=memory[index(byte_address+b)];end
  end else if(fetch && cycle%5!=0)begin
   accepted=1;byte_address=int'(fetch_address)*4;pending=11+cycle%13;reads++;
  end
 end
end
always @(posedge clk)if(resetn && dut.shader_start)begin
 for(integer w=0;w<8;w++)begin
  if(word_index>=43080 || dut.shader_command[w*32+:32]!==shader[word_index])
   $fatal(1,"Mapped shader command %0d word %0d got=%h expected=%h",word_index/8,w,dut.shader_command[w*32+:32],shader[word_index]);
  word_index++;
 end
end
initial begin
 $readmemh("/home/michael/console/TESTS/gpu_geometry_20261010/rtl_world_onehot/initial.hex",memory);
 $readmemh("/home/michael/console/TESTS/gpu_geometry_20261010/rtl_world_onehot/commands.hex",commands);
 $readmemh("/home/michael/console/TESTS/gpu_geometry_20261010/rtl_world_onehot/shader.hex",shader);
 repeat(8)@(negedge clk);resetn=1;repeat(4)@(negedge clk);
 for(integer c=0;c<7416/8;c++)begin
  for(integer w=0;w<8;w++)packet[w*32+:32]=commands[c*8+w];
  start=1;@(negedge clk);start=0;
  wait(done);@(negedge clk);repeat(3)@(negedge clk);
  if(c%64==0)$display("MAPPED command=%0d shader=%0d cycles=%0d",c,word_index/8,cycle);
 end
 if(word_index!=43080 || errors!=0 || vertices!=2676 || triangles!=834 || culled!=1715 || clipped!=482 || slivers!=0)
  $fatal(1,"Mapped counters words=%0d err=%0d v=%0d t=%0d c=%0d clip=%0d sliver=%0d",word_index,errors,vertices,triangles,culled,clipped,slivers);
 $display("PASS: synthesized geometry 7416/8 commands, 43080/8 shader commands exact, %0d mesh reads",reads);$finish;
end
initial begin #1000000000;$fatal(1,"Mapped geometry timeout state=%h",dut.state);end
endmodule
