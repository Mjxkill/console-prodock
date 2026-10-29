`timescale 1ns/1ps
module tb;
reg [103:0] read_select=0;
reg [31:0] response_data;
wire [31:0] register_value[0:25];
assign register_value[0]=32'h424c5432;
genvar v;generate for(v=1;v<26;v=v+1)begin:values assign register_value[v]=32'd0;end endgenerate
initial begin #6.25;read_select=(104'd1<<78)|(104'd1<<52)|(104'd1<<26)|104'd1;#20;
if(response_data!==32'h424c5432)$fatal(1,"Wrong CSR result");$display("PASS MUX time=%t result=%h",$time,response_data);$finish;end
genvar response_byte;
generate for(response_byte=0;response_byte<4;response_byte=response_byte+1)begin:read_response
integer k;
always @*begin
response_data[response_byte*8+:8]=8'd0;
for(k=0;k<26;k=k+1)
response_data[response_byte*8+:8]=response_data[response_byte*8+:8] |
({8{read_select[response_byte*26+k]}} & register_value[k][response_byte*8+:8]);
end
end endgenerate

endmodule
