`timescale 1ns/1ps
module tb;
 reg hclk=0,hreset=0,reply_valid=0,busy=0;
 reg [4:0] receive_index=0;
 reg [31:0] reply=0,completed_count=0;
 reg [7:0] address=0;
 wire read_hit; wire [31:0] read_data;
 GSR GSR(.GSRI(1'b1));
 neo_usb_reply_witness dut(.*);
 always #5 hclk=~hclk;
 integer fd,got,n=0,er,ev,eb,ei,ew,es,ea,eh,ed;
 string file;
 initial begin
  if(!$value$plusargs("vectors=%s",file))$fatal(1,"missing vectors");
  fd=$fopen(file,"r");if(!fd)$fatal(1,"open vectors");
  while(!$feof(fd))begin
   got=$fscanf(fd,"%h %h %h %h %h %h %h %h %h\n",er,ev,eb,ei,ew,es,ea,eh,ed);
   if(got!=9)$fatal(1,"bad vector %0d got%0d",n,got);
   @(negedge hclk);hreset=er[0];reply_valid=ev[0];busy=eb[0];receive_index=ei[4:0];reply=ew;completed_count=es;address=ea[7:0];
   @(posedge hclk);#1;
   if(read_hit!==eh[0] || read_data!==ed)$fatal(1,"vector%0d addr%02h hit%b/%b data%08h/%08h",n,address,read_hit,eh[0],read_data,ed);
   n=n+1;
  end
  $fclose(fd);$display("PASS WITNESS SCOREBOARD cycles=%0d",n);$finish;
 end
 initial begin #2000000;$fatal(1,"deadline");end
endmodule
