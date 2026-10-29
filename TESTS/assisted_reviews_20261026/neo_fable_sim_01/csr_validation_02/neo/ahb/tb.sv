`timescale 1ns/1ps
module tb;
reg hc=0,mc=0,rst=0,hc_run=1;
always #6.25 if(hc_run)hc=~hc;
always #6.666 mc=~mc;
reg sel=0,wr=0;reg[31:0]address=0,data=0;reg[1:0]trans=0;
wire[31:0]result;wire hready,bv,bw;wire[28:0]ba;wire[255:0]bwd;wire[31:0]bm;
gpu_accel #(.FONT_FILE("font8x16.hex"))dut(.hclk(hc),.hresetn(rst),.hsel(sel),.hwrite(wr),
.haddr(address),.hwdata(data),.htrans(trans),.hrdata(result),.hready(hready),
.mem_clk(mc),.valid(bv),.write(bw),.addr(ba),.wr_data(bwd),.wr_mask(bm),
.ready(1'b0),.rd_data(256'd0),.rd_valid(1'b0),.debug_state(),.debug_accept(),.observe_packet_words());
integer reads=0,waits=0,checks=0;
reg[31:0] sampled_response;
reg sampled_rst;
always @(posedge hc)begin
  sampled_rst=rst;sampled_response=dut.response_data;
  #1;
  if(sampled_rst)begin
    if(result !== sampled_response)$fatal(1,"CSR output pipeline mismatch");
    if((^result)===1'bx)$fatal(1,"Unknown CSR output after reset");
    checks++;
  end else if(result!==0)$fatal(1,"CSR reset result");
end
task automatic read_csr(input[7:0]a,input integer pause);
 integer count;reg[31:0]expected;
 @(negedge hc);address=a;sel=1;trans=2;wr=0;
 @(posedge hc);if(hready!==1)$fatal(1,"CSR address not ready");
 @(negedge hc);sel=0;trans=0;
 if(pause)begin hc_run=0;#97;hc_run=1;end
 count=0;
 do begin
   @(posedge hc);if(hready===0)begin count++;waits++;end
   else if(hready!==1)$fatal(1,"Unknown CSR HREADY");
   if(count>3)$fatal(1,"Unbounded CSR read");
 end while(!hready);
 #2;
 expected=0;
 for(integer k=0;k<26;k++)if(a==k*4)expected=dut.register_value[k];
 if(result!==expected)$fatal(1,"CSR address %h got=%h expected=%h",a,result,expected);
 if(count!=1)$fatal(1,"CSR wait states got=%0d",count);
 reads++;
 @(negedge hc);
endtask
initial begin
 repeat(8)@(negedge hc);rst=1;repeat(20)@(negedge hc);
 for(integer round=0;round<2;round++)begin
   for(integer a=0;a<256;a++)read_csr(a,round==1 && a%17==0);
   @(negedge hc);rst=0;#73;@(negedge hc);rst=1;repeat(20)@(negedge hc);
 end
 if(reads!=512 || waits!=512 || checks<1024)$fatal(1,"Vacuous CSR test");
 if(bv!==0)$fatal(1,"CSR reads emitted a DDR request");
 $display("PASS AHB CSR reads=%0d waits=%0d pipeline_checks=%0d",reads,waits,checks);$finish;
end
initial begin #1000000;$fatal(1,"Global CSR timeout");end
endmodule
