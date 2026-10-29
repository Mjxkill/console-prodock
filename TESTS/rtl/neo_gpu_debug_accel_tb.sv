`timescale 1ns/1ps
module neo_gpu_debug_accel_tb;
    reg hclk=0,mem_clk=0,resetn=0;
    always #6.25 hclk=~hclk;
    initial begin #0.371;forever #6.667 mem_clk=~mem_clk;end
    reg hsel=0,hwrite=0;
    reg [31:0] haddr=0,hwdata=0;
    reg [1:0] htrans=0;
    wire [31:0] gpu_data,debug_data;
    wire gpu_ready,debug_ready,valid,write,debug_accept;
    wire [28:0] addr;
    wire [255:0] wr_data,debug_state;
    wire [31:0] wr_mask;
    gpu_accel #(.FONT_FILE("tang/rtl/video/font8x16.hex")) gpu(
        .hclk(hclk),.hresetn(resetn),.mem_clk(mem_clk),
        .hsel(hsel && haddr[14:12]==1),.hwrite(hwrite),.haddr(haddr),.hwdata(hwdata),.htrans(htrans),
        .hrdata(gpu_data),.hready(gpu_ready),.valid(valid),.write(write),.addr(addr),.wr_data(wr_data),.wr_mask(wr_mask),
        .ready(1'b1),.rd_data(256'd0),.rd_valid(1'b0),.debug_state(debug_state),.debug_accept(debug_accept));
    neo_gpu_debug debug_port(.hclk(hclk),.resetn(resetn),.mem_clk(mem_clk),
        .hsel(hsel && haddr[14:12]==5),.hwrite(hwrite),.htrans(htrans),.haddr(haddr),.hwdata(hwdata),
        .hrdata(debug_data),.hready(debug_ready),.host_accept(debug_accept),.live(debug_state));
    task write_reg(input [31:0] address,input [31:0] value);
        @(negedge hclk);hsel=1;htrans=2;hwrite=1;haddr=address;
        @(negedge hclk);hsel=0;htrans=0;hwdata=value;
        @(negedge hclk);hwdata=0;hwrite=0;
    endtask
    task read_debug(input [7:0] address,output [31:0] value);
        @(negedge hclk);hsel=1;htrans=2;hwrite=0;haddr=32'h5000+address;
        @(negedge hclk);hsel=0;htrans=0;
        if(debug_ready!==0)$fatal(1,"Debug read missing wait state");
        @(negedge hclk);
        if(debug_ready!==1)$fatal(1,"Debug read still waiting");
        value=debug_data;
    endtask
    reg [31:0] value;
    initial begin
        repeat(8)@(negedge hclk);resetn=1;
        repeat(20)@(negedge hclk);
        write_reg('h1010,'h16000000);
        write_reg('h1010,'h12000000);
        write_reg('h1010,'h12001000);
        write_reg('h1010,'h00200040);
        write_reg('h1010,'h00400040);
        repeat(3)write_reg('h1010,0);
        repeat(100)@(negedge hclk);
        write_reg('h5004,1);
        repeat(20)@(negedge hclk);
        read_debug(4,value);if(value!==6)$fatal(1,"Snapshot not ready");
        read_debug(8,value);if(value!==8)$fatal(1,"Wrong host word count %h",value);
        read_debug('h10,value);if(value!==8)$fatal(1,"Wrong received word count %h",value);
        read_debug('h20,value);if(value!==1)$fatal(1,"TARGET did not complete %h",value);
        read_debug('h24,value);if((value & 'hfc00)!=='hfc00)$fatal(1,"Reset taps wrong %h",value);
        read_debug('h28,value);if(value!==0)$fatal(1,"Command error");
        read_debug('h2c,value);if((value & 'hffffff80)!=='h08081600)$fatal(1,"Wrong blitter pointers/op/reset %h",value);
        read_debug('h30,value);if(value!==1)$fatal(1,"Blitter not IDLE");
        read_debug('h34,value);if(value!==0)$fatal(1,"Unexpected high state bit");
        read_debug('h3c,value);if(value!=='h16000000)$fatal(1,"Wrong extended opcode");
        $display("PASS: actual GPU TARGET, 8 host/8 received words, done=1, wp=rp=8, opcode=22, state=IDLE");
        $finish;
    end
    always @(posedge mem_clk)if(resetn && valid)$fatal(1,"TARGET unexpectedly requested DDR");
    initial begin #1000000;$fatal(1,"Timeout");end
endmodule
