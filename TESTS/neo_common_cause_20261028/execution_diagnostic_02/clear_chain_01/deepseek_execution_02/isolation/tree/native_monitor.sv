// Independent, protected endpoint monitor. No edits or feedback into DUT.
module native_monitor(input wire clk,resetn,men,mready,mwen,mwend,mwrready,
                      input wire[2:0]mcmd,input wire[28:0]addr,
                      input wire[255:0]data,input wire[31:0]mask);
 integer fault=0;
 initial void'($value$plusargs("fault=%d",fault));
 wire[2:0]observed_command=fault==5 ? 3'd1:mcmd;
 always @(posedge clk)if(resetn)begin
  if(mwen && (!men || !mready || !mwrready || mcmd!=0))
    $fatal(1,"CHECK_FAIL NATIVE_WRITE_WITHOUT_COMMAND");
  if(men && mready)begin
   if(observed_command!=0)$fatal(1,"CHECK_FAIL NATIVE_COMMAND type=%0d",observed_command);
   if(!mwen || !mwend || !mwrready)$fatal(1,"CHECK_FAIL NATIVE_WRITE_HANDSHAKE");
   if(addr!==29'h04800008 || mask!==0 || data!=={16{16'h6b4d}})
    $fatal(1,"CHECK_FAIL NATIVE_FOOTPRINT");
  end
 end
endmodule
bind bench native_monitor endpoint_monitor(.clk(mem_clk),.resetn(resetn),
 .men(men),.mready(mrdy),.mwen(mwen),.mwend(mwend),.mwrready(mwrdy),
 .mcmd(mcmd),.addr(maddr),.data(mdata),.mask(mmask));
