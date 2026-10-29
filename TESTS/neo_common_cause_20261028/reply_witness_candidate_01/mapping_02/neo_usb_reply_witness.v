// Isolated Neo/R19 diagnostic. All inputs except address are observed HCLK
// signals already used by usb_idle_trace. No output feeds its capture logic.
// The bank accepts reply_valid even outside busy: preserve that event and
// report it, rather than silently masking it. Reads have no side effects.
`default_nettype none
module neo_usb_reply_witness (
 input wire hclk, hreset, reply_valid, busy,
 input wire [4:0] receive_index,
 input wire [31:0] reply, completed_count,
 input wire [7:0] address,
 output wire read_hit,
 output reg [31:0] read_data
);
 wire event_word=reply_valid && !hreset;
 wire e0=event_word && receive_index==0;
 wire e1=event_word && receive_index==1;
 wire e2=event_word && receive_index==2;
 wire e31=event_word && receive_index==31;
 wire outside=event_word && !busy;
 wire [31:0] raw0,raw1,raw2,tag0,tag1,tag2;
 wire [31:0] count0,count1,count2,total,frames,outside_count;
 wire [2:0] seen;
 wire [4:0] expected_index,last_index;
 wire last_busy,in_frame,order_error,duplicate,overflow;
 wire [2:0] next_seen=receive_index==0 ? 3'b001 :
                            receive_index==1 ? seen|3'b010 :
                            receive_index==2 ? seen|3'b100 : seen;
 wire overflow_now=(e0 && &count0) || (e1 && &count1) ||
                   (e2 && &count2) || (event_word && &total) ||
                   (e31 && &frames) || (outside && &outside_count);
 wire duplicate_now=(e0 && in_frame) || (e1 && seen[1]) || (e2 && seen[2]);
 utw_register #(.W(32)) r_raw0(hclk,hreset,e0,reply,raw0);
 utw_register #(.W(32)) r_raw1(hclk,hreset,e1,reply,raw1);
 utw_register #(.W(32)) r_raw2(hclk,hreset,e2,reply,raw2);
 utw_register #(.W(32)) r_tag0(hclk,hreset,e0,completed_count,tag0);
 utw_register #(.W(32)) r_tag1(hclk,hreset,e1,completed_count,tag1);
 utw_register #(.W(32)) r_tag2(hclk,hreset,e2,completed_count,tag2);
 utw_register #(.W(32)) r_count0(hclk,hreset,e0,count0+32'd1,count0);
 utw_register #(.W(32)) r_count1(hclk,hreset,e1,count1+32'd1,count1);
 utw_register #(.W(32)) r_count2(hclk,hreset,e2,count2+32'd1,count2);
 utw_register #(.W(32)) r_total(hclk,hreset,event_word,total+32'd1,total);
 utw_register #(.W(32)) r_frames(hclk,hreset,e31,frames+32'd1,frames);
 utw_register #(.W(32)) r_outside(hclk,hreset,outside,outside_count+32'd1,outside_count);
 utw_register #(.W(3)) r_seen(hclk,hreset,event_word,next_seen,seen);
 utw_register #(.W(5)) r_expected(hclk,hreset,event_word,receive_index+5'd1,expected_index);
 utw_register #(.W(5)) r_last(hclk,hreset,event_word,receive_index,last_index);
 utw_register r_last_busy(hclk,hreset,event_word,busy,last_busy);
 utw_register r_in_frame(hclk,hreset,event_word,receive_index!=31,in_frame);
 utw_register r_order(hclk,hreset,event_word,order_error || receive_index!=expected_index,order_error);
 utw_register r_duplicate(hclk,hreset,event_word,duplicate || duplicate_now,duplicate);
 utw_register r_overflow(hclk,hreset,event_word,overflow || overflow_now,overflow);

 assign read_hit=address[7:6]==2'b11 && address[1:0]==0;
 always @* begin
  read_data=0;
  case(address)
   8'hc0:read_data=32'h55545731; // UTW1, independent constant witness
   8'hc4:read_data=32'h00010001; // ABI1/layout1, nonzero at address class1
   8'hc8:read_data=raw0;
   8'hcc:read_data=raw1;
   8'hd0:read_data=raw2;
   8'hd4:read_data=raw1; // alias avoids trusting only one read address
   8'hd8:read_data=count0;
   8'hdc:read_data=count1;
   8'he0:read_data=count2;
   8'he4:read_data=total;
   8'he8:read_data=frames;
   8'hec:read_data=outside_count;
   8'hf0:read_data={10'd0,last_busy,last_index,3'd0,expected_index,
                    1'b0,overflow,duplicate,order_error,in_frame,seen};
   8'hf4:read_data=tag0;
   8'hf8:read_data=tag1;
   8'hfc:read_data=tag2;
   default:read_data=0;
  endcase
 end
endmodule

// Explicit primitive per bit: never infer a memory/validity RAM for witnesses.
// DFFRE reset is synchronous, has priority over CE, and uses the same HCLK
// and hreset as the bank being observed. No additional clock or CDC path.
module utw_register #(parameter W=1)(
 input wire clk,reset,enable,
 input wire [W-1:0] d,
 output wire [W-1:0] q
);
 genvar i;
 generate for(i=0;i<W;i=i+1)begin: bit_reg
  (* keep=1 *) DFFRE value(.Q(q[i]),.D(d[i]),.CLK(clk),.CE(enable),.RESET(reset));
 end endgenerate
endmodule
`default_nettype wire
