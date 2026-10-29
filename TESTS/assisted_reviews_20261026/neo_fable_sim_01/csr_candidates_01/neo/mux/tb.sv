`timescale 1ns/1ps
module tb;
reg [103:0] read_select=0;
reg [31:0] register_value[0:25];
reg [31:0] response_data;
reg [31:0] expected;
reg acc;
integer checks=0,seed=32'h7412a9;
    genvar response_byte;
    generate for(response_byte=0;response_byte<4;response_byte=response_byte+1)begin: read_response
        integer k;
        reg [7:0] accumulator;
        always @* begin
            accumulator=8'd0;
            for(k=0;k<26;k=k+1)
                accumulator=accumulator |
                    ({8{read_select[response_byte*26+k]}} & register_value[k][response_byte*8+:8]);
            response_data[response_byte*8+:8]=accumulator;
        end
    end endgenerate
task automatic verify;
  #1;
  for(integer b=0;b<32;b++)begin
    acc=0;
    for(integer k=0;k<26;k++)acc=acc | (read_select[(b/8)*26+k] & register_value[k][b]);
    expected[b]=acc;
  end
  if(response_data !== expected)$fatal(1,"CSR mismatch got=%h expected=%h",response_data,expected);
  checks++;
endtask
initial begin
  // Every byte address, including unaligned and unmapped addresses, for
  // deterministic, random and X/Z register payloads.
  for(integer pattern=0;pattern<12;pattern++)begin
    for(integer k=0;k<26;k++)begin
      case(pattern)
        0:register_value[k]=0;
        1:register_value[k]=32'hffffffff;
        2:register_value[k]=32'h424c5432 ^ (32'h1020304*k);
        3:register_value[k]=32'hxxxxxxxx;
        4:register_value[k]=32'hzzzzzzzz;
        5:register_value[k]={8'hxx,8'hzz,8'h0,8'hff};
        default:register_value[k]=$random(seed);
      endcase
    end
    for(integer a=0;a<256;a++)begin
      for(integer i=0;i<104;i++)read_select[i]=(a==(i%26)*4);
      verify();
    end
  end
  // This includes states not reachable from a decoded CSR read: multiple
  // selects, unknown and high-impedance selectors across individual bytes.
  for(integer test=0;test<512;test++)begin
    for(integer k=0;k<26;k++)register_value[k]=$random(seed);
    for(integer i=0;i<104;i++)begin
      case(($unsigned($random(seed)))%4)
        0:read_select[i]=0;1:read_select[i]=1;
        2:read_select[i]=1'bx;3:read_select[i]=1'bz;
      endcase
    end
    verify();
  end
  $display("PASS CSR FOUR STATE checks=%0d addresses=256 patterns=12 arbitrary_selectors=512",checks);
  $finish;
end
initial begin #100000;$fatal(1,"CSR bounded timeout");end
endmodule
