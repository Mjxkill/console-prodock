`timescale 1ns/1ps
module tb;
GSR GSR(.GSRI(1'b1));
reg hclk=0,clk=0,resetn=0,hwrite=0,htrans=0;
reg [14:0] haddr=0;reg [31:0] hwdata=0;
wire [31:0] gpu_read,debug_read;wire gpu_ready,debug_ready,request_any;
always #6.25 hclk=~hclk;
initial begin #0.371;forever #6.667 clk=~clk;end
mapped_gpu dut(.clock_model(clk),.*);
task write_reg(input [14:0] address,input [31:0] value);
 @(negedge hclk);htrans=1;hwrite=1;haddr=address;
 @(negedge hclk);htrans=0;hwdata=value;
 if(gpu_ready!==1)$fatal(1,"Unexpected configuration backpressure");
 @(negedge hclk);hwdata=0;hwrite=0;
endtask
task read_reg(input [14:0] address,output [31:0] value);
 @(negedge hclk);htrans=1;hwrite=0;haddr=address;
 @(negedge hclk);htrans=0;
 if((address[14:12]==1 ? gpu_ready:debug_ready)!==0)$fatal(1,"Expected read wait");
 @(negedge hclk);
 if((address[14:12]==1 ? gpu_ready:debug_ready)!==1)$fatal(1,"Read did not finish");
 value=address[14:12]==1 ? gpu_read:debug_read;
endtask
integer waits;integer checks=0;reg [31:0] value;
always @(negedge clk)if(resetn && request_any!==0)$fatal(1,"Unexpected GPU memory request: %b",request_any);
initial begin
 repeat(12)@(negedge hclk);resetn=1;repeat(30)@(negedge hclk);
 read_reg('h1000,value);if(value!==32'h424c5432)$fatal(1,"Wrong GPU ID %h",value);
 read_reg('h5000,value);if(value!==32'h4e474442)$fatal(1,"Wrong debug ID %h",value);
 // target_160x100_f80
 write_reg('h1010,32'h16000000);
 write_reg('h1010,32'h00800000);
 write_reg('h1010,32'h00900000);
 write_reg('h1010,32'h00a00064);
 write_reg('h1010,32'h01800180);
 write_reg('h1010,32'h00000000);
 write_reg('h1010,32'h00000000);
 write_reg('h1010,32'h00000000);
 waits=0;value=0;
 while(value!==32'd1 && waits<1000)begin
  read_reg('h1008,value);waits=waits+1;
 end
 if(value!==32'd1)$fatal(1,"target_160x100_f80 fence %h",value);
 read_reg('h1034,value);if(value!==32'd0)$fatal(1,"target_160x100_f80 rejected %h expected 0",value);
 read_reg('h104c,value);if(value!==32'd0)$fatal(1,"target_160x100_f80 geometry invalid %h expected 0",value);
 checks++;
 $display("Camera routed checks=%0d (target_160x100_f80)",checks);$fflush();
 // camera_160x100_f80_center0_repeat0
 write_reg('h1010,32'h20000000);
 write_reg('h1010,32'h00004000);
 write_reg('h1010,32'h00500000);
 write_reg('h1010,32'h00500000);
 write_reg('h1010,32'h00500000);
 write_reg('h1010,32'h00000000);
 write_reg('h1010,32'h00a00064);
 write_reg('h1010,32'h00000000);
 waits=0;value=0;
 while(value!==32'd2 && waits<1000)begin
  read_reg('h1008,value);waits=waits+1;
 end
 if(value!==32'd2)$fatal(1,"camera_160x100_f80_center0_repeat0 fence %h",value);
 read_reg('h1034,value);if(value!==32'd0)$fatal(1,"camera_160x100_f80_center0_repeat0 rejected %h expected 0",value);
 read_reg('h104c,value);if(value!==32'd0)$fatal(1,"camera_160x100_f80_center0_repeat0 geometry invalid %h expected 0",value);
 checks++;
 $display("Camera routed checks=%0d (camera_160x100_f80_center0_repeat0)",checks);$fflush();
 // camera_160x100_f80_center0_repeat1
 write_reg('h1010,32'h20000000);
 write_reg('h1010,32'h00004000);
 write_reg('h1010,32'h00500000);
 write_reg('h1010,32'h00500000);
 write_reg('h1010,32'h00500000);
 write_reg('h1010,32'h00000000);
 write_reg('h1010,32'h00a00064);
 write_reg('h1010,32'h00000000);
 waits=0;value=0;
 while(value!==32'd3 && waits<1000)begin
  read_reg('h1008,value);waits=waits+1;
 end
 if(value!==32'd3)$fatal(1,"camera_160x100_f80_center0_repeat1 fence %h",value);
 read_reg('h1034,value);if(value!==32'd0)$fatal(1,"camera_160x100_f80_center0_repeat1 rejected %h expected 0",value);
 read_reg('h104c,value);if(value!==32'd0)$fatal(1,"camera_160x100_f80_center0_repeat1 geometry invalid %h expected 0",value);
 checks++;
 $display("Camera routed checks=%0d (camera_160x100_f80_center0_repeat1)",checks);$fflush();
 // camera_160x100_f80_center1_repeat0
 write_reg('h1010,32'h20000000);
 write_reg('h1010,32'h00004000);
 write_reg('h1010,32'h00500000);
 write_reg('h1010,32'h00500000);
 write_reg('h1010,32'h00500000);
 write_reg('h1010,32'h00500032);
 write_reg('h1010,32'h00a00064);
 write_reg('h1010,32'h00000000);
 waits=0;value=0;
 while(value!==32'd4 && waits<1000)begin
  read_reg('h1008,value);waits=waits+1;
 end
 if(value!==32'd4)$fatal(1,"camera_160x100_f80_center1_repeat0 fence %h",value);
 read_reg('h1034,value);if(value!==32'd0)$fatal(1,"camera_160x100_f80_center1_repeat0 rejected %h expected 0",value);
 read_reg('h104c,value);if(value!==32'd0)$fatal(1,"camera_160x100_f80_center1_repeat0 geometry invalid %h expected 0",value);
 checks++;
 $display("Camera routed checks=%0d (camera_160x100_f80_center1_repeat0)",checks);$fflush();
 // camera_160x100_f80_center1_repeat1
 write_reg('h1010,32'h20000000);
 write_reg('h1010,32'h00004000);
 write_reg('h1010,32'h00500000);
 write_reg('h1010,32'h00500000);
 write_reg('h1010,32'h00500000);
 write_reg('h1010,32'h00500032);
 write_reg('h1010,32'h00a00064);
 write_reg('h1010,32'h00000000);
 waits=0;value=0;
 while(value!==32'd5 && waits<1000)begin
  read_reg('h1008,value);waits=waits+1;
 end
 if(value!==32'd5)$fatal(1,"camera_160x100_f80_center1_repeat1 fence %h",value);
 read_reg('h1034,value);if(value!==32'd0)$fatal(1,"camera_160x100_f80_center1_repeat1 rejected %h expected 0",value);
 read_reg('h104c,value);if(value!==32'd0)$fatal(1,"camera_160x100_f80_center1_repeat1 geometry invalid %h expected 0",value);
 checks++;
 $display("Camera routed checks=%0d (camera_160x100_f80_center1_repeat1)",checks);$fflush();
 // target_1x1_f1
 write_reg('h1010,32'h16000000);
 write_reg('h1010,32'h00800000);
 write_reg('h1010,32'h00900000);
 write_reg('h1010,32'h00010001);
 write_reg('h1010,32'h01800180);
 write_reg('h1010,32'h00000000);
 write_reg('h1010,32'h00000000);
 write_reg('h1010,32'h00000000);
 waits=0;value=0;
 while(value!==32'd6 && waits<1000)begin
  read_reg('h1008,value);waits=waits+1;
 end
 if(value!==32'd6)$fatal(1,"target_1x1_f1 fence %h",value);
 read_reg('h1034,value);if(value!==32'd0)$fatal(1,"target_1x1_f1 rejected %h expected 0",value);
 read_reg('h104c,value);if(value!==32'd0)$fatal(1,"target_1x1_f1 geometry invalid %h expected 0",value);
 checks++;
 $display("Camera routed checks=%0d (target_1x1_f1)",checks);$fflush();
 // camera_1x1_f1_center0_repeat0
 write_reg('h1010,32'h20000000);
 write_reg('h1010,32'h00004000);
 write_reg('h1010,32'h00500000);
 write_reg('h1010,32'h00010000);
 write_reg('h1010,32'h00010000);
 write_reg('h1010,32'h00000000);
 write_reg('h1010,32'h00010001);
 write_reg('h1010,32'h00000000);
 waits=0;value=0;
 while(value!==32'd7 && waits<1000)begin
  read_reg('h1008,value);waits=waits+1;
 end
 if(value!==32'd7)$fatal(1,"camera_1x1_f1_center0_repeat0 fence %h",value);
 read_reg('h1034,value);if(value!==32'd0)$fatal(1,"camera_1x1_f1_center0_repeat0 rejected %h expected 0",value);
 read_reg('h104c,value);if(value!==32'd0)$fatal(1,"camera_1x1_f1_center0_repeat0 geometry invalid %h expected 0",value);
 checks++;
 $display("Camera routed checks=%0d (camera_1x1_f1_center0_repeat0)",checks);$fflush();
 // camera_1x1_f1_center0_repeat1
 write_reg('h1010,32'h20000000);
 write_reg('h1010,32'h00004000);
 write_reg('h1010,32'h00500000);
 write_reg('h1010,32'h00010000);
 write_reg('h1010,32'h00010000);
 write_reg('h1010,32'h00000000);
 write_reg('h1010,32'h00010001);
 write_reg('h1010,32'h00000000);
 waits=0;value=0;
 while(value!==32'd8 && waits<1000)begin
  read_reg('h1008,value);waits=waits+1;
 end
 if(value!==32'd8)$fatal(1,"camera_1x1_f1_center0_repeat1 fence %h",value);
 read_reg('h1034,value);if(value!==32'd0)$fatal(1,"camera_1x1_f1_center0_repeat1 rejected %h expected 0",value);
 read_reg('h104c,value);if(value!==32'd0)$fatal(1,"camera_1x1_f1_center0_repeat1 geometry invalid %h expected 0",value);
 checks++;
 $display("Camera routed checks=%0d (camera_1x1_f1_center0_repeat1)",checks);$fflush();
 // camera_1x1_f1_center1_repeat0
 write_reg('h1010,32'h20000000);
 write_reg('h1010,32'h00004000);
 write_reg('h1010,32'h00500000);
 write_reg('h1010,32'h00010000);
 write_reg('h1010,32'h00010000);
 write_reg('h1010,32'h00000000);
 write_reg('h1010,32'h00010001);
 write_reg('h1010,32'h00000000);
 waits=0;value=0;
 while(value!==32'd9 && waits<1000)begin
  read_reg('h1008,value);waits=waits+1;
 end
 if(value!==32'd9)$fatal(1,"camera_1x1_f1_center1_repeat0 fence %h",value);
 read_reg('h1034,value);if(value!==32'd0)$fatal(1,"camera_1x1_f1_center1_repeat0 rejected %h expected 0",value);
 read_reg('h104c,value);if(value!==32'd0)$fatal(1,"camera_1x1_f1_center1_repeat0 geometry invalid %h expected 0",value);
 checks++;
 $display("Camera routed checks=%0d (camera_1x1_f1_center1_repeat0)",checks);$fflush();
 // camera_1x1_f1_center1_repeat1
 write_reg('h1010,32'h20000000);
 write_reg('h1010,32'h00004000);
 write_reg('h1010,32'h00500000);
 write_reg('h1010,32'h00010000);
 write_reg('h1010,32'h00010000);
 write_reg('h1010,32'h00000000);
 write_reg('h1010,32'h00010001);
 write_reg('h1010,32'h00000000);
 waits=0;value=0;
 while(value!==32'd10 && waits<1000)begin
  read_reg('h1008,value);waits=waits+1;
 end
 if(value!==32'd10)$fatal(1,"camera_1x1_f1_center1_repeat1 fence %h",value);
 read_reg('h1034,value);if(value!==32'd0)$fatal(1,"camera_1x1_f1_center1_repeat1 rejected %h expected 0",value);
 read_reg('h104c,value);if(value!==32'd0)$fatal(1,"camera_1x1_f1_center1_repeat1 geometry invalid %h expected 0",value);
 checks++;
 $display("Camera routed checks=%0d (camera_1x1_f1_center1_repeat1)",checks);$fflush();
 // target_32x32_f32
 write_reg('h1010,32'h16000000);
 write_reg('h1010,32'h00800000);
 write_reg('h1010,32'h00900000);
 write_reg('h1010,32'h00200020);
 write_reg('h1010,32'h01800180);
 write_reg('h1010,32'h00000000);
 write_reg('h1010,32'h00000000);
 write_reg('h1010,32'h00000000);
 waits=0;value=0;
 while(value!==32'd11 && waits<1000)begin
  read_reg('h1008,value);waits=waits+1;
 end
 if(value!==32'd11)$fatal(1,"target_32x32_f32 fence %h",value);
 read_reg('h1034,value);if(value!==32'd0)$fatal(1,"target_32x32_f32 rejected %h expected 0",value);
 read_reg('h104c,value);if(value!==32'd0)$fatal(1,"target_32x32_f32 geometry invalid %h expected 0",value);
 checks++;
 $display("Camera routed checks=%0d (target_32x32_f32)",checks);$fflush();
 // camera_32x32_f32_center0_repeat0
 write_reg('h1010,32'h20000000);
 write_reg('h1010,32'h00004000);
 write_reg('h1010,32'h00500000);
 write_reg('h1010,32'h00200000);
 write_reg('h1010,32'h00200000);
 write_reg('h1010,32'h00000000);
 write_reg('h1010,32'h00200020);
 write_reg('h1010,32'h00000000);
 waits=0;value=0;
 while(value!==32'd12 && waits<1000)begin
  read_reg('h1008,value);waits=waits+1;
 end
 if(value!==32'd12)$fatal(1,"camera_32x32_f32_center0_repeat0 fence %h",value);
 read_reg('h1034,value);if(value!==32'd0)$fatal(1,"camera_32x32_f32_center0_repeat0 rejected %h expected 0",value);
 read_reg('h104c,value);if(value!==32'd0)$fatal(1,"camera_32x32_f32_center0_repeat0 geometry invalid %h expected 0",value);
 checks++;
 $display("Camera routed checks=%0d (camera_32x32_f32_center0_repeat0)",checks);$fflush();
 // camera_32x32_f32_center0_repeat1
 write_reg('h1010,32'h20000000);
 write_reg('h1010,32'h00004000);
 write_reg('h1010,32'h00500000);
 write_reg('h1010,32'h00200000);
 write_reg('h1010,32'h00200000);
 write_reg('h1010,32'h00000000);
 write_reg('h1010,32'h00200020);
 write_reg('h1010,32'h00000000);
 waits=0;value=0;
 while(value!==32'd13 && waits<1000)begin
  read_reg('h1008,value);waits=waits+1;
 end
 if(value!==32'd13)$fatal(1,"camera_32x32_f32_center0_repeat1 fence %h",value);
 read_reg('h1034,value);if(value!==32'd0)$fatal(1,"camera_32x32_f32_center0_repeat1 rejected %h expected 0",value);
 read_reg('h104c,value);if(value!==32'd0)$fatal(1,"camera_32x32_f32_center0_repeat1 geometry invalid %h expected 0",value);
 checks++;
 $display("Camera routed checks=%0d (camera_32x32_f32_center0_repeat1)",checks);$fflush();
 // camera_32x32_f32_center1_repeat0
 write_reg('h1010,32'h20000000);
 write_reg('h1010,32'h00004000);
 write_reg('h1010,32'h00500000);
 write_reg('h1010,32'h00200000);
 write_reg('h1010,32'h00200000);
 write_reg('h1010,32'h00100010);
 write_reg('h1010,32'h00200020);
 write_reg('h1010,32'h00000000);
 waits=0;value=0;
 while(value!==32'd14 && waits<1000)begin
  read_reg('h1008,value);waits=waits+1;
 end
 if(value!==32'd14)$fatal(1,"camera_32x32_f32_center1_repeat0 fence %h",value);
 read_reg('h1034,value);if(value!==32'd0)$fatal(1,"camera_32x32_f32_center1_repeat0 rejected %h expected 0",value);
 read_reg('h104c,value);if(value!==32'd0)$fatal(1,"camera_32x32_f32_center1_repeat0 geometry invalid %h expected 0",value);
 checks++;
 $display("Camera routed checks=%0d (camera_32x32_f32_center1_repeat0)",checks);$fflush();
 // camera_32x32_f32_center1_repeat1
 write_reg('h1010,32'h20000000);
 write_reg('h1010,32'h00004000);
 write_reg('h1010,32'h00500000);
 write_reg('h1010,32'h00200000);
 write_reg('h1010,32'h00200000);
 write_reg('h1010,32'h00100010);
 write_reg('h1010,32'h00200020);
 write_reg('h1010,32'h00000000);
 waits=0;value=0;
 while(value!==32'd15 && waits<1000)begin
  read_reg('h1008,value);waits=waits+1;
 end
 if(value!==32'd15)$fatal(1,"camera_32x32_f32_center1_repeat1 fence %h",value);
 read_reg('h1034,value);if(value!==32'd0)$fatal(1,"camera_32x32_f32_center1_repeat1 rejected %h expected 0",value);
 read_reg('h104c,value);if(value!==32'd0)$fatal(1,"camera_32x32_f32_center1_repeat1 geometry invalid %h expected 0",value);
 checks++;
 $display("Camera routed checks=%0d (camera_32x32_f32_center1_repeat1)",checks);$fflush();
 // target_160x100_f160
 write_reg('h1010,32'h16000000);
 write_reg('h1010,32'h00800000);
 write_reg('h1010,32'h00900000);
 write_reg('h1010,32'h00a00064);
 write_reg('h1010,32'h01800180);
 write_reg('h1010,32'h00000000);
 write_reg('h1010,32'h00000000);
 write_reg('h1010,32'h00000000);
 waits=0;value=0;
 while(value!==32'd16 && waits<1000)begin
  read_reg('h1008,value);waits=waits+1;
 end
 if(value!==32'd16)$fatal(1,"target_160x100_f160 fence %h",value);
 read_reg('h1034,value);if(value!==32'd0)$fatal(1,"target_160x100_f160 rejected %h expected 0",value);
 read_reg('h104c,value);if(value!==32'd0)$fatal(1,"target_160x100_f160 geometry invalid %h expected 0",value);
 checks++;
 $display("Camera routed checks=%0d (target_160x100_f160)",checks);$fflush();
 // camera_160x100_f160_center0_repeat0
 write_reg('h1010,32'h20000000);
 write_reg('h1010,32'h00004000);
 write_reg('h1010,32'h00500000);
 write_reg('h1010,32'h00a00000);
 write_reg('h1010,32'h00a00000);
 write_reg('h1010,32'h00000000);
 write_reg('h1010,32'h00a00064);
 write_reg('h1010,32'h00000000);
 waits=0;value=0;
 while(value!==32'd17 && waits<1000)begin
  read_reg('h1008,value);waits=waits+1;
 end
 if(value!==32'd17)$fatal(1,"camera_160x100_f160_center0_repeat0 fence %h",value);
 read_reg('h1034,value);if(value!==32'd0)$fatal(1,"camera_160x100_f160_center0_repeat0 rejected %h expected 0",value);
 read_reg('h104c,value);if(value!==32'd0)$fatal(1,"camera_160x100_f160_center0_repeat0 geometry invalid %h expected 0",value);
 checks++;
 $display("Camera routed checks=%0d (camera_160x100_f160_center0_repeat0)",checks);$fflush();
 // camera_160x100_f160_center0_repeat1
 write_reg('h1010,32'h20000000);
 write_reg('h1010,32'h00004000);
 write_reg('h1010,32'h00500000);
 write_reg('h1010,32'h00a00000);
 write_reg('h1010,32'h00a00000);
 write_reg('h1010,32'h00000000);
 write_reg('h1010,32'h00a00064);
 write_reg('h1010,32'h00000000);
 waits=0;value=0;
 while(value!==32'd18 && waits<1000)begin
  read_reg('h1008,value);waits=waits+1;
 end
 if(value!==32'd18)$fatal(1,"camera_160x100_f160_center0_repeat1 fence %h",value);
 read_reg('h1034,value);if(value!==32'd0)$fatal(1,"camera_160x100_f160_center0_repeat1 rejected %h expected 0",value);
 read_reg('h104c,value);if(value!==32'd0)$fatal(1,"camera_160x100_f160_center0_repeat1 geometry invalid %h expected 0",value);
 checks++;
 $display("Camera routed checks=%0d (camera_160x100_f160_center0_repeat1)",checks);$fflush();
 // camera_160x100_f160_center1_repeat0
 write_reg('h1010,32'h20000000);
 write_reg('h1010,32'h00004000);
 write_reg('h1010,32'h00500000);
 write_reg('h1010,32'h00a00000);
 write_reg('h1010,32'h00a00000);
 write_reg('h1010,32'h00500032);
 write_reg('h1010,32'h00a00064);
 write_reg('h1010,32'h00000000);
 waits=0;value=0;
 while(value!==32'd19 && waits<1000)begin
  read_reg('h1008,value);waits=waits+1;
 end
 if(value!==32'd19)$fatal(1,"camera_160x100_f160_center1_repeat0 fence %h",value);
 read_reg('h1034,value);if(value!==32'd0)$fatal(1,"camera_160x100_f160_center1_repeat0 rejected %h expected 0",value);
 read_reg('h104c,value);if(value!==32'd0)$fatal(1,"camera_160x100_f160_center1_repeat0 geometry invalid %h expected 0",value);
 checks++;
 $display("Camera routed checks=%0d (camera_160x100_f160_center1_repeat0)",checks);$fflush();
 // camera_160x100_f160_center1_repeat1
 write_reg('h1010,32'h20000000);
 write_reg('h1010,32'h00004000);
 write_reg('h1010,32'h00500000);
 write_reg('h1010,32'h00a00000);
 write_reg('h1010,32'h00a00000);
 write_reg('h1010,32'h00500032);
 write_reg('h1010,32'h00a00064);
 write_reg('h1010,32'h00000000);
 waits=0;value=0;
 while(value!==32'd20 && waits<1000)begin
  read_reg('h1008,value);waits=waits+1;
 end
 if(value!==32'd20)$fatal(1,"camera_160x100_f160_center1_repeat1 fence %h",value);
 read_reg('h1034,value);if(value!==32'd0)$fatal(1,"camera_160x100_f160_center1_repeat1 rejected %h expected 0",value);
 read_reg('h104c,value);if(value!==32'd0)$fatal(1,"camera_160x100_f160_center1_repeat1 geometry invalid %h expected 0",value);
 checks++;
 $display("Camera routed checks=%0d (camera_160x100_f160_center1_repeat1)",checks);$fflush();
 // camera_invalid_near_zero
 write_reg('h1010,32'h20000000);
 write_reg('h1010,32'h00000000);
 write_reg('h1010,32'h00500000);
 write_reg('h1010,32'h00a00000);
 write_reg('h1010,32'h00a00000);
 write_reg('h1010,32'h00500032);
 write_reg('h1010,32'h00a00064);
 write_reg('h1010,32'h00000000);
 waits=0;value=0;
 while(value!==32'd21 && waits<1000)begin
  read_reg('h1008,value);waits=waits+1;
 end
 if(value!==32'd21)$fatal(1,"camera_invalid_near_zero fence %h",value);
 read_reg('h1034,value);if(value!==32'd1)$fatal(1,"camera_invalid_near_zero rejected %h expected 1",value);
 read_reg('h104c,value);if(value!==32'd1)$fatal(1,"camera_invalid_near_zero geometry invalid %h expected 1",value);
 checks++;
 $display("Camera routed checks=%0d (camera_invalid_near_zero)",checks);$fflush();
 $display("PASS routed CAMERA: 21 configurations, zero DMA, exact rejection counters");$finish;
end
initial begin #1000000;$fatal(1,"Watchdog");end
endmodule
