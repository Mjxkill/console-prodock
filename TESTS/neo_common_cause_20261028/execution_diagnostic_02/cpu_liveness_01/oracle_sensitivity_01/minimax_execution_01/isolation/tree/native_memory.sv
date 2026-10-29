`timescale 1ns/1ps
// Independent byte-addressed, in-order terminal. Not a model of PHY/calibration.
// Scratch range is checked before indexing; no truncation/alias of upper bits.
module native_memory(
 input wire clk, resetn, hold_command, hold_write, hold_returns,
 input wire en, input wire [2:0] cmd, input wire [28:0] addr,
 output wire ready, input wire wr_en,wr_end,
 input wire [255:0] wr_data, input wire [31:0] wr_mask,
 output wire wr_ready, output reg [255:0] rd_data=0,
 output reg rd_valid=0,rd_end=0
);
 localparam [31:0] BASE=32'h12000000;
 reg[7:0] bytes[0:127];
 reg[255:0] replies[0:255];
 integer due[0:255];
 integer tick=0,wp=0,rp=0,reads=0,writes=0,returned=0;
 integer i,base; reg[31:0] value;
 initial begin
  for(i=0;i<32;i=i+1) begin
   value=(BASE+4*i)^32'ha5396c17;
   bytes[4*i]=value[7:0];bytes[4*i+1]=value[15:8];
   bytes[4*i+2]=value[23:16];bytes[4*i+3]=value[31:24];
  end
 end
 assign ready=resetn && !hold_command && tick%7!=2;
 assign wr_ready=resetn && !hold_write && tick%5!=1;
 always @(posedge clk) begin
  if(!resetn) begin tick<=0;wp=0;rp=0;reads=0;writes=0;returned=0;rd_valid<=0;rd_end<=0;end
  else begin
   tick<=tick+1;rd_valid<=0;rd_end<=0;
   if(!hold_returns && rp<wp && tick>=due[rp])begin
    rd_data<=replies[rp];rd_valid<=1;rd_end<=1;rp=rp+1;returned=returned+1;
   end
   if(en)begin
    if(!ready)$fatal(1,"ENDPOINT command without ready");
    if(addr[2:0]!=0 || addr*4<BASE || addr*4>BASE+96)
     $fatal(1,"ENDPOINT address outside scratch128B");
    base=addr*4-BASE;
    if(cmd==0)begin
     if(!wr_en || !wr_end || !wr_ready)$fatal(1,"ENDPOINT missing write handshake");
     if(base!=32 || wr_mask!=0 || wr_data!={16{16'h6b4d}})
      $fatal(1,"ENDPOINT unexpected CLEAR footprint");
     for(i=0;i<32;i=i+1)bytes[base+i]=wr_data[i*8+:8];
     writes=writes+1;
    end else if(cmd==1)begin
     if(wp>=256)$fatal(1,"ENDPOINT queue bound");
     for(i=0;i<32;i=i+1)replies[wp][i*8+:8]=bytes[base+i];
     due[wp]=tick+4+(reads%4);wp=wp+1;reads=reads+1;
    end else $fatal(1,"ENDPOINT unknown command");
   end
   if(wr_en && !(en && cmd==0))$fatal(1,"ENDPOINT unmatched write data");
  end
 end
endmodule
