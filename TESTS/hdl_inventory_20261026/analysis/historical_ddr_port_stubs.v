// Interface-only stubs for compilation warnings, NOT a behavioral DDR model.
module DDR3_Memory_Interface_Top (
  clk,
  pll_stop,
  memory_clk,
  pll_lock,
  rst_n,
  clk_out,
  ddr_rst,
  init_calib_complete,
  cmd_ready,
  cmd,
  cmd_en,
  addr,
  wr_data_rdy,
  wr_data,
  wr_data_en,
  wr_data_end,
  wr_data_mask,
  rd_data,
  rd_data_valid,
  rd_data_end,
  sr_req,
  ref_req,
  sr_ack,
  ref_ack,
  burst,
  O_ddr_addr,
  O_ddr_ba,
  O_ddr_cs_n,
  O_ddr_ras_n,
  O_ddr_cas_n,
  O_ddr_we_n,
  O_ddr_clk,
  O_ddr_clk_n,
  O_ddr_cke,
  O_ddr_odt,
  O_ddr_reset_n,
  O_ddr_dqm,
  IO_ddr_dq,
  IO_ddr_dqs,
  IO_ddr_dqs_n
)
;
input clk;
output pll_stop;
input memory_clk;
input pll_lock;
input rst_n;
output clk_out;
output ddr_rst;
output init_calib_complete;
output cmd_ready;
input [2:0] cmd;
input cmd_en;
input [28:0] addr;
output wr_data_rdy;
input [255:0] wr_data;
input wr_data_en;
input wr_data_end;
input [31:0] wr_data_mask;
output [255:0] rd_data;
output rd_data_valid;
output rd_data_end;
input sr_req;
input ref_req;
output sr_ack;
output ref_ack;
input burst;
output [14:0] O_ddr_addr;
output [2:0] O_ddr_ba;
output O_ddr_cs_n;
output O_ddr_ras_n;
output O_ddr_cas_n;
output O_ddr_we_n;
output O_ddr_clk;
output O_ddr_clk_n;
output O_ddr_cke;
output O_ddr_odt;
output O_ddr_reset_n;
output [3:0] O_ddr_dqm;
inout [31:0] IO_ddr_dq;
inout [3:0] IO_ddr_dqs;
inout [3:0] IO_ddr_dqs_n;
endmodule
module ddr3_memory_wrfifo(input RdClk,WrClk,WrEn,RdEn,Reset,input [127:0] Data,output Empty,Full,Almost_Full,Almost_Empty,output [127:0] Q); endmodule
module ddr3_memory_rdfifo(input RdClk,WrClk,WrEn,RdEn,Reset,input [127:0] Data,output Empty,Full,Almost_Full,Almost_Empty,output [127:0] Q); endmodule
