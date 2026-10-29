// Independent byte-addressed endpoint. This models an ordered native DDR UI,
// not a physical Gowin controller. The native byte address is word_addr*4.
`timescale 1ns/1ps
module native_memory(
 input wire clk, resetn, en, input wire [2:0] cmd,
 input wire [28:0] addr, output wire ready,
 input wire wr_en, wr_end, input wire [255:0] wr_data,
 input wire [31:0] wr_mask, output wire wr_ready,
 output reg [255:0] rd_data=0, output reg rd_valid=0,rd_end=0
);
 reg [7:0] bytes[0:4095];
 reg [255:0] replies[0:511];
 integer due[0:511];
 integer cycle=0, wp=0,rp=0,delay_seed=1,fault=0,reads=0,writes=0;
 integer i,base;
 reg dropped=0;
 initial begin
  for(i=0;i<4096;i=i+1)bytes[i]=0;
  i=$value$plusargs("seed=%d",delay_seed);
  i=$value$plusargs("fault=%d",fault);
 end
 assign ready=resetn && cycle%7!=2 && cycle%11!=4;
 assign wr_ready=resetn && cycle%5!=1 && cycle%13!=3;
 always @(posedge clk)begin
  if(!resetn)begin cycle<=0;wp=0;rp=0;rd_valid<=0;rd_end<=0;dropped=0;end
  else begin
   cycle<=cycle+1;rd_valid<=0;rd_end<=0;
   // Latency is positive, variable and ordered. No internal DUT tags used.
   if(rp<wp && cycle>=due[rp] && fault!=3)begin
    if(fault==2 && !dropped)begin
     dropped=1;$display("INJECT dropped_response=%0d",rp);
    end else begin
     rd_data<=replies[rp] ^ (fault==1 ? {32{8'h01}} : 256'd0);
     rd_valid<=1;rd_end<=1;
    end
    rp=rp+1;
   end
   if(en)begin
    if(!ready)$fatal(1,"ENDPOINT illegal command without ready");
    base=addr*4;
    if(addr[2:0]!=0 || base<0 || base+31>=4096)
     $fatal(1,"ENDPOINT address out of model range or alignment");
    if(cmd==0)begin
     if(!wr_en || !wr_end || !wr_ready)$fatal(1,"ENDPOINT missing write handshake");
     for(i=0;i<32;i=i+1)if(!wr_mask[i])bytes[base+i]=wr_data[8*i+:8];
     writes=writes+1;
    end else if(cmd==1)begin
     if(wp>=512)$fatal(1,"ENDPOINT bounded queue exceeded");
     for(i=0;i<32;i=i+1)replies[wp][8*i+:8]=bytes[base+i];
     due[wp]=cycle+3+(reads*5+delay_seed)%12;
     wp=wp+1;reads=reads+1;
    end else $fatal(1,"ENDPOINT unsupported command");
   end
   if(wr_en && !(en && cmd==0))$fatal(1,"ENDPOINT unmatched write data");
  end
 end
endmodule
