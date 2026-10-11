`timescale 1ns/1ps
module video_bus_stage_tb;
 reg clk=0,resetn=0;
 always #6.25 clk=~clk;
 reg sel=0,wr=0;reg [1:0] trans=0;reg [31:0] addr=0,data=0;
 wire ready;wire [31:0] result;
 wire ms,mw;wire [1:0] mt;wire [31:0] ma,md;wire mr;
 reg [31:0] memory[0:255],reference[0:255];
 reg pending=0,pwrite;reg [7:0] slot;
 integer delay_count=0,accepted=0,completed=0;
 wire [31:0] rd=memory[slot];
 video_bus_stage dut(.clk(clk),.resetn(resetn),.s_hsel(sel),.s_hwrite(wr),.s_htrans(trans),.s_haddr(addr),.s_hwdata(data),.s_hready(ready),.s_hrdata(result),
  .m_hsel(ms),.m_hwrite(mw),.m_htrans(mt),.m_haddr(ma),.m_hwdata(md),.m_hready(mr),.m_hrdata(rd));
 assign mr=!pending||delay_count==0;
 wire [7:0] new_slot={ma[13:12],ma[7:2]};
 always @(posedge clk)begin
  if(!resetn)begin pending<=0;accepted<=0;completed<=0;delay_count<=0;end
  else begin
   if(ms&&mt[1])begin
    if(pending)$fatal(1,"Overlapping backend transactions");
    pending<=1;pwrite<=mw;slot<=new_slot;delay_count<=int'(ma[7:2])%17;
    accepted<=accepted+1;
   end
   if(pending)begin
    if(delay_count!=0)delay_count<=delay_count-1;
    else begin
     if(pwrite)memory[slot]<=md;
     pending<=0;completed<=completed+1;
    end
   end
  end
 end
 function automatic [31:0] address_for(input integer n);
  return 32'(((n*13)%4)*4096+((n*37)%64)*4);
 endfunction
 function automatic [31:0] payload_for(input integer n);
  return 32'(n*32'h19731+32'hfedc4321);
 endfunction
 task automatic drive_address(input integer n,input integer count);
  if(n<count)begin sel=1;trans=2;addr=address_for(n);wr=(n%3)!=1;end
  else begin sel=0;trans=0;end
 endtask
 task automatic run_stream(input integer count);
  integer a;reg [31:0] expected;
  @(negedge clk);drive_address(0,count);
  @(posedge clk);if(!ready)$fatal(1,"Initial upstream state");
  for(integer n=0;n<count;n++)begin
   @(negedge clk);drive_address(n+1,count);data=payload_for(n);
   a=int'(address_for(n));a=((a>>12)&3)*64+((a>>2)&63);
   expected=reference[a];
   do @(posedge clk);while(!ready);
   if(n%3==1 && result!==expected)$fatal(1,"Read %0d got %h expected %h",n,result,expected);
   if(n%3!=1)reference[a]=payload_for(n);
  end
  @(negedge clk);sel=0;trans=0;
  repeat(12)@(posedge clk);
  if(accepted!=count||completed!=count)$fatal(1,"Lost/duplicate transfer: %0d %0d expected %0d",accepted,completed,count);
  for(integer n=0;n<256;n++)if(memory[n]!==reference[n])$fatal(1,"Write corruption %0d",n);
 endtask
 initial begin
  for(integer n=0;n<256;n++)begin memory[n]=32'(n*17);reference[n]=32'(n*17);end
  repeat(5)@(negedge clk);resetn=1;
  run_stream(2000);
  // Reset during address capture, backend issue, wait and response. No replay
  // is allowed after the shared reset, including an upstream next address.
  for(integer cut=1;cut<=5;cut++)begin
   @(negedge clk);resetn=0;sel=0;trans=0;
   repeat(3)@(negedge clk);resetn=1;
   @(negedge clk);sel=1;trans=2;wr=1;addr=32'h30fc;
   @(posedge clk);
   @(negedge clk);sel=1;trans=2;addr=32'h1008;data=32'h01234567;
   while(dut.state!=cut)@(negedge clk);
   resetn=0;sel=0;trans=0;data=32'hbad0bad0;
   repeat(3)@(negedge clk);resetn=1;
   repeat(30)@(posedge clk);
   if(ms||pending||accepted||completed||!ready)$fatal(1,"Reset replay at phase %0d",cut);
   for(integer n=0;n<256;n++)reference[n]=memory[n];
   run_stream(32);
  end
  $display("PASS: 2160 pipelined reads/writes, four windows, 0..16 wait states, reset at five phases, no replay");
  $finish;
 end
 initial begin #10000000;$fatal(1,"Timeout");end
endmodule
