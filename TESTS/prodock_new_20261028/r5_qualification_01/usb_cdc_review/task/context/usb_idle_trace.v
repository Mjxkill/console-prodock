// Passive IN/NAK observer. No output feeds the USB datapath.
// Commands and coherent snapshots use two dual-clock FIFOs, independent of EP0.
// AHB window: +00 ID, +04 status (bit0 busy, bit1 rejected command),
// +08 completed snapshot count, +0c command, +40..bc snapshot (32 words).
// Command: bit0 clear+arm, bit1 snapshot, bit2 disarm, bits14:8 USB address.
// Use one command at a time; clear+snapshot returns the PRE-clear state.
// USB bus reset is observed, not used to erase this diagnostic.
`default_nettype none
module usb_idle_trace (
 input wire clk, reset_n, bus_reset, sof,
 input wire rx_active, rx_valid, rx_error,
 input wire [7:0] rx_data,
 input wire tx_valid, tx_ready,
 input wire [7:0] tx_data,
 input wire [3:0] endpoint,
 input wire cork,
 input wire hclk, hsel, hwrite,
 input wire [1:0] htrans,
 input wire [31:0] haddr, hwdata,
 output reg [31:0] hrdata,
 output wire hready
);
 // Hold both FIFO ends in reset until each clock has actually restarted.
 (* ASYNC_REG="TRUE" *) reg [2:0] hr=0, ur=0;
 (* ASYNC_REG="TRUE" *) reg [1:0] hu=0, uh=0;
 always @(posedge hclk or negedge reset_n)
  if(!reset_n)begin hr<=0;uh<=0;end
  else begin hr<={hr[1:0],1'b1};uh<={uh[0],ur[2]};end
 always @(posedge clk or negedge reset_n)
  if(!reset_n)begin ur<=0;hu<=0;end
  else begin ur<={ur[1:0],1'b1};hu<={hu[0],hr[2]};end
 wire hreset=!hr[2] || !uh[1], ureset=!ur[2] || !hu[1];
 wire cmd_ready, cmd_valid, cmd_pop, reply_ready, reply_valid;
 wire [31:0] command, reply;
 reg write_pending, read_pending;
 reg [7:0] address;
 reg busy, rejected;
 reg [31:0] snapshot_count;
 reg [4:0] receive_index;
 reg [31:0] bank[0:31];
 wire [4:0] bank_index=address[6:2]-5'd16;
 wire push_command=write_pending && address==8'h0c && !busy && cmd_ready && !hreset;
 assign hready=!read_pending; // one local wait; never wait on the USB clock
 ddr_dcfifo #(.WIDTH(32),.DEPTH_LOG2(2)) u_commands (
  .wr_clk(hclk),.wr_rst(hreset),.wr_valid(push_command),.wr_data(hwdata),
  .wr_ready(cmd_ready),.wr_full(),.wr_lost(),.wr_count(),
  .rd_clk(clk),.rd_rst(ureset),.rd_valid(cmd_valid),.rd_data(command),
  .rd_ready(cmd_pop),.rd_count());
 ddr_dcfifo #(.WIDTH(32),.DEPTH_LOG2(5)) u_replies (
  .wr_clk(clk),.wr_rst(ureset),.wr_valid(sending && reply_ready && !ureset),
  .wr_data(snapshot[send_index*32+:32]),.wr_ready(reply_ready),
  .wr_full(),.wr_lost(),.wr_count(),
  .rd_clk(hclk),.rd_rst(hreset),.rd_valid(reply_valid),.rd_data(reply),
  .rd_ready(!hreset),.rd_count());
 integer b;
 always @(posedge hclk)begin
  if(hreset)begin
   hrdata<=0;write_pending<=0;read_pending<=0;address<=0;
   busy<=0;rejected<=0;snapshot_count<=0;receive_index<=0;
   for(b=0;b<32;b=b+1)bank[b]<=0;
  end else begin
   write_pending<=hsel && htrans[1] && hwrite && hready;
   read_pending<=hsel && htrans[1] && !hwrite && hready;
   if(hready)address<=haddr[7:0];
   if(write_pending && address==8'h0c)begin
    if(push_command)begin busy<=1;rejected<=0;end
    else rejected<=1;
   end
   if(reply_valid)begin
    bank[receive_index]<=reply;receive_index<=receive_index+1'b1;
    if(receive_index==31)begin snapshot_count<=snapshot_count+1'b1;busy<=0;end
   end
   if(read_pending)begin
    case(address)
     8'h00:hrdata<=32'h55544e41; // UTNA
     8'h04:hrdata<={30'd0,rejected,busy};
     8'h08:hrdata<=snapshot_count;
     default:hrdata<=address>=8'h40 && address<8'hc0 ? bank[bank_index] : 32'd0;
    endcase
   end
  end
 end

 // Sample the entire UTMI tuple together before decoding it. In particular,
 // TXREADY already contains the controller->PHY combinational return path;
 // adding counter/enable logic directly there exceeded the 60 MHz budget.
 // This one-cycle delay is passive and identical for RX/TX/context, so
 // response time differences are preserved.
 (* syn_preserve=1 *) reg [27:0] tap;
 always @(posedge clk)tap<={bus_reset,sof,rx_active,rx_valid,rx_error,rx_data,
                           tx_valid,tx_ready,tx_data,endpoint,cork};
 wire bus_reset_sample,sof_sample,rx_active_sample,rx_valid_sample,rx_error_sample;
 wire [7:0] rx_data_sample,tx_data_sample;
 wire tx_valid_sample,tx_ready_sample,cork_sample;
 wire [3:0] endpoint_sample;
 assign {bus_reset_sample,sof_sample,rx_active_sample,rx_valid_sample,rx_error_sample,rx_data_sample,
         tx_valid_sample,tx_ready_sample,tx_data_sample,endpoint_sample,cork_sample}=tap;

 function [4:0] crc5;
  input [10:0] token;
  integer i;reg [4:0] c;
  begin
   c=5'h1f;
   for(i=0;i<11;i=i+1)
    c=(c[0]^token[i]) ? ((c>>1)^5'h14) : (c>>1);
   crc5=~c;
  end
 endfunction
 reg armed;
 reg [6:0] target;
 reg [31:0] ticks,in2,in3,nak2,nak3,data2,data3,miss2,miss3;
 reg [31:0] bad_response,rx_errors,bad_token,resets,sofs,stalls,last_token,last_response;
 reg [7:0] max_offer,max_accept;
 reg bus_reset_q;
 reg [2:0] rx_count;
 reg [7:0] rx_pid,token0,token1;
 reg rx_bad;
 wire token_end=!rx_active_sample && rx_count!=0;
 wire token_in=token_end && rx_pid==8'h69;
 wire token_good=rx_count==3 && !rx_bad && !rx_error_sample &&
                 token1[7:3]==crc5({token1[2:0],token0});
 wire [3:0] token_ep={token1[2:0],token0[7]};
 wire selected_in=token_in && token_good && token0[6:0]==target &&
                  (token_ep==2 || token_ep==3);
 // Any subsequent valid token ends the old transaction context, including
 // SOF, OUT/SETUP/IN for EP0 or another address. Never attribute its reply
 // to an unanswered EP2/EP3 IN.
 wire next_token=token_end && token_good &&
                  (rx_pid==8'h69 || rx_pid==8'he1 || rx_pid==8'h2d ||
                   rx_pid==8'ha5 || rx_pid==8'hb4);
 reg pending;
 reg [3:0] pending_ep;
 reg [31:0] pending_time;
 reg [9:0] age;
 wire [7:0] short_age=|age[9:8] ? 8'hff : age[7:0];
 reg tx_busy,tx_cork;
 reg [3:0] tx_endpoint;
 reg [7:0] tx_pid,tx_count,offer_age,accept_age;
 wire finish=tx_busy && !tx_valid_sample && pending && tx_endpoint==pending_ep;
 wire expired=pending && ((age==127 && (!tx_busy || tx_count==0)) || age==1023);
 wire displaced=next_token && pending && !finish;
 wire missing=expired || displaced;
 wire event_valid=armed && (finish || missing);
 wire malformed=finish && !((tx_pid==8'h5a && tx_count==1) ||
                   (pending_ep==2 && (tx_pid==8'hc3 || tx_pid==8'h4b) && tx_count>=3));
 wire [63:0] event_record={pending_time,1'b1,missing,malformed,tx_cork,
                           pending_ep,tx_pid,accept_age,tx_count};
 reg [255:0] history;
 reg [63:0] first_fault;
 reg [1023:0] snapshot;
 reg sending;
 reg [4:0] send_index;
 assign cmd_pop=cmd_valid && !sending && !ureset;
 wire clear=cmd_pop && command[0];
 wire [1023:0] live={
  {21'd0,armed,pending,2'd0,target},first_fault,history,
  {16'd0,max_accept,max_offer},last_response,last_token,stalls,sofs,resets,
  bad_token,rx_errors,bad_response,miss3,miss2,data3,data2,nak3,nak2,in3,in2,ticks,
  command,32'd1,32'h55544e41};
 always @(posedge clk)begin
  if(ureset)begin sending<=0;send_index<=0;snapshot<=0;end
  else begin
   // Every command returns a complete bank, including clear/disarm, so the
   // CPU can acknowledge execution without sampling an asynchronous flag.
   if(cmd_pop)begin snapshot<=live;sending<=1;send_index<=0;end
   else if(sending && reply_ready)begin
    send_index<=send_index+1'b1;
    if(send_index==31)sending<=0;
   end
  end
 end
 always @(posedge clk)begin
  if(ureset || clear)begin
   armed<=!ureset;target<=ureset ? 7'd0 : command[14:8];
   ticks<=0;in2<=0;in3<=0;nak2<=0;nak3<=0;data2<=0;data3<=0;miss2<=0;miss3<=0;
   bad_response<=0;rx_errors<=0;bad_token<=0;resets<=0;sofs<=0;stalls<=0;
   last_token<=0;last_response<=0;max_offer<=0;max_accept<=0;
   history<=0;first_fault<=0;bus_reset_q<=bus_reset_sample;
   rx_count<=0;rx_pid<=0;token0<=0;token1<=0;rx_bad<=0;
   pending<=0;pending_ep<=0;pending_time<=0;age<=0;
   tx_busy<=0;tx_cork<=0;tx_endpoint<=0;tx_pid<=0;tx_count<=0;offer_age<=0;accept_age<=0;
  end else begin
   if(cmd_pop && command[2])armed<=0;
   bus_reset_q<=bus_reset_sample;
   if(armed)begin
    ticks<=ticks+1'b1;
    if(bus_reset_sample && !bus_reset_q)resets<=resets+1'b1;
    if(sof_sample)sofs<=sofs+1'b1;
    if(rx_error_sample)rx_errors<=rx_errors+1'b1;
    if(tx_valid_sample && !tx_ready_sample)stalls<=stalls+1'b1;
    if(token_in && !token_good)bad_token<=bad_token+1'b1;
   end
   if(rx_active_sample)begin
    if(rx_error_sample)rx_bad<=1;
    if(rx_valid_sample)begin
     case(rx_count)
      0:rx_pid<=rx_data_sample;
      1:token0<=rx_data_sample;
      2:token1<=rx_data_sample;
      default:;
     endcase
     if(rx_count!=4)rx_count<=rx_count+1'b1;
    end
   end else begin rx_count<=0;rx_bad<=0;end
   if(pending && age!=1023)age<=age+1'b1;
   if(event_valid)begin
    history<={history[191:0],event_record};
    if((missing || malformed) && !first_fault[31])first_fault<=event_record;
    pending<=0;
    last_response<={4'd0,endpoint_sample,pending_ep,tx_cork,3'd0,tx_count,tx_pid};
    if(missing)begin
     if(pending_ep==2)miss2<=miss2+1'b1;else miss3<=miss3+1'b1;
    end else begin
     if(tx_pid==8'h5a && tx_count==1)begin
      if(pending_ep==2)nak2<=nak2+1'b1;else nak3<=nak3+1'b1;
      if(offer_age>max_offer)max_offer<=offer_age;
      if(accept_age>max_accept)max_accept<=accept_age;
     end
     if(tx_pid==8'hc3 || tx_pid==8'h4b)begin
      if(pending_ep==2)data2<=data2+1'b1;else data3<=data3+1'b1;
     end
     if(malformed)bad_response<=bad_response+1'b1;
    end
   end
   if(armed && selected_in)begin
    pending<=1;pending_ep<=token_ep;pending_time<=ticks;age<=1;
    tx_count<=0;tx_pid<=0;offer_age<=0;accept_age<=0;
    last_token<={8'd0,token1,token0,rx_pid};
    if(token_ep==2)in2<=in2+1'b1;else in3<=in3+1'b1;
   end
   // TX sampling follows token initialization so acceptance on the very
   // token_end edge is retained (delay zero), rather than overwritten.
   if(tx_valid_sample && !tx_busy)begin
    tx_busy<=1;tx_pid<=tx_data_sample;tx_count<=0;tx_cork<=cork_sample;
    tx_endpoint<=endpoint_sample;offer_age<=selected_in ? 8'd0 : short_age;
   end
   if(tx_valid_sample && tx_ready_sample)begin
    if(!tx_busy || tx_count==0)begin
     tx_pid<=tx_data_sample;accept_age<=selected_in ? 8'd0 : short_age;
    end
    if(!tx_busy)tx_count<=1;
    else if(tx_count!=255)tx_count<=tx_count+1'b1;
   end
   if(!tx_valid_sample)tx_busy<=0;
   if(bus_reset_sample)pending<=0;
  end
 end
endmodule
`default_nettype wire
