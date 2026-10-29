module proof(input signed [48:0] transform_pair0, transform_pair1, output equal);
wire signed [63:0] sum64=transform_pair0+transform_pair1;
 wire signed [49:0] transform_sum=$signed(transform_pair0)+$signed(transform_pair1);
wire signed [63:0] extended=transform_sum;
wire ref_overflow=(sum64>2147483647||sum64< -64'sd2147483648);
wire actual_overflow=(transform_sum[49:32]!={18{transform_sum[31]}});
assign equal=(extended==sum64)&&(actual_overflow==ref_overflow);
endmodule
