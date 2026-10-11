// Serialize the video peripheral leg of the AE350 AHB bus.
// Register both directions, removing combinational slave-HREADY -> HSEL
// chains between distant graphics and USB register blocks. Backend transfers
// have one address pulse, a stable data phase, and an idle gap. No clock CDC.
`default_nettype none
module video_bus_stage(
 input wire clk,resetn,
 input wire s_hsel,s_hwrite,input wire [1:0] s_htrans,
 input wire [31:0] s_haddr,s_hwdata,
 output wire s_hready,output reg [31:0] s_hrdata,
 output wire m_hsel,output reg m_hwrite,output wire [1:0] m_htrans,
 output reg [31:0] m_haddr,m_hwdata,
 input wire m_hready,input wire [31:0] m_hrdata
);
 localparam IDLE=0,CAPTURE=1,WAIT_IDLE=2,ADDRESS=3,DATA=4,RESPONSE=5;
 reg [2:0] state;
 assign s_hready=state==IDLE||state==RESPONSE;
 assign m_hsel=state==ADDRESS;
 assign m_htrans=state==ADDRESS ? 2'b10:2'b00;
 always @(posedge clk)begin
  if(!resetn)begin state<=IDLE;s_hrdata<=0;m_hwrite<=0;m_haddr<=0;m_hwdata<=0;end
  else case(state)
   IDLE,RESPONSE:begin
    if(s_hsel&&s_htrans[1])begin m_haddr<=s_haddr;m_hwrite<=s_hwrite;state<=CAPTURE;end
    else state<=IDLE;
   end
   CAPTURE:begin m_hwdata<=s_hwdata;state<=WAIT_IDLE;end
   WAIT_IDLE:if(m_hready)state<=ADDRESS;
   ADDRESS:state<=DATA;
   DATA:if(m_hready)begin s_hrdata<=m_hrdata;state<=RESPONSE;end
   default:state<=IDLE;
  endcase
 end
endmodule
`default_nettype wire
