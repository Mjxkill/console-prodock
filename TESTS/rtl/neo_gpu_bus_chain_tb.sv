`timescale 1ns/1ps
// Exercise the two real AHB stages between AE350 EXTS and the Neo GPU.
// The hard AE350 macro is replaced by a protocol-correct, stalled master.
module neo_gpu_bus_chain_tb;
    reg hclk=0,mem_clk=0,resetn=0;
    always #6.25 hclk=~hclk;
    initial begin #0.371;forever #6.667 mem_clk=~mem_clk;end
    reg hsel=0,hwrite=0;
    reg [31:0] haddr=0,hwdata=0;
    reg [1:0] htrans=0;
    wire hready;wire [31:0] hrdata;
    wire [1:0] leg_sel,leg_trans;
    wire leg_write,leg_ready;wire [31:0] leg_addr,leg_wdata,leg_rdata;
    ahb_exts_bridge bridge(.hclk(hclk),.hresetn(resetn),
        .m_hsel(hsel),.m_haddr(haddr),.m_htrans(htrans),.m_hwrite(hwrite),.m_hwdata(hwdata),
        .m_hrdata(hrdata),.m_hready(hready),
        .s_hsel(leg_sel),.s_htrans(leg_trans),.s_hwrite(leg_write),.s_haddr(leg_addr),.s_hwdata(leg_wdata),
        .s0_hrdata(32'hbad00000),.s0_hready(1'b1),.s1_hrdata(leg_rdata),.s1_hready(leg_ready));
    wire bus_sel,bus_write,bus_ready;wire [1:0] bus_trans;
    wire [31:0] bus_addr,bus_wdata,bus_rdata;
    video_bus_stage stage(.clk(hclk),.resetn(resetn),
        .s_hsel(leg_sel[1]),.s_hwrite(leg_write),.s_htrans(leg_trans),.s_haddr(leg_addr),.s_hwdata(leg_wdata),
        .s_hready(leg_ready),.s_hrdata(leg_rdata),
        .m_hsel(bus_sel),.m_hwrite(bus_write),.m_htrans(bus_trans),.m_haddr(bus_addr),.m_hwdata(bus_wdata),
        .m_hready(bus_ready),.m_hrdata(bus_rdata));
    reg [2:0] selected=0;
    always @(posedge hclk)
        if(!resetn)selected<=0;else if(bus_sel)selected<=bus_addr[14:12];
    wire [31:0] gpu_data,debug_data;
    wire gpu_ready,debug_ready,valid,write,debug_accept;
    wire [28:0] addr;
    wire [255:0] wr_data,debug_state;wire [31:0] wr_mask;
    assign bus_ready=selected==1 ? gpu_ready:selected==5 ? debug_ready:1'b1;
    assign bus_rdata=selected==1 ? gpu_data:selected==5 ? debug_data:32'hbad00001;
    gpu_accel #(.FONT_FILE("tang/rtl/video/font8x16.hex")) gpu(
        .hclk(hclk),.hresetn(resetn),.mem_clk(mem_clk),
        .hsel(bus_sel && bus_addr[14:12]==1),.hwrite(bus_write),.haddr(bus_addr),.hwdata(bus_wdata),.htrans(bus_trans),
        .hrdata(gpu_data),.hready(gpu_ready),.valid(valid),.write(write),.addr(addr),.wr_data(wr_data),.wr_mask(wr_mask),
        .ready(1'b1),.rd_data(256'd0),.rd_valid(1'b0),.debug_state(debug_state),.debug_accept(debug_accept));
    neo_gpu_debug debug_port(.hclk(hclk),.resetn(resetn),.mem_clk(mem_clk),
        .hsel(bus_sel && bus_addr[14:12]==5),.hwrite(bus_write),.htrans(bus_trans),.haddr(bus_addr),.hwdata(bus_wdata),
        .hrdata(debug_data),.hready(debug_ready),.host_accept(debug_accept),.live(debug_state));
    task access(input bit wr,input [31:0] address,input [31:0] data,output [31:0] result);
        @(negedge hclk);while(!hready)@(negedge hclk);
        hsel=1;htrans=2;hwrite=wr;haddr=address;
        @(negedge hclk);hsel=0;htrans=0;hwdata=data;
        do @(negedge hclk);while(!hready);
        result=hrdata;hwdata=0;hwrite=0;
    endtask
    reg [31:0] value,words[0:7];
    integer received=0;
    always @(posedge mem_clk)if(resetn)begin
        if(valid)$fatal(1,"TARGET unexpectedly requested DDR");
        if(gpu.command_we)begin
            if(received>=8 || gpu.queue_data!==words[received])
                $fatal(1,"Command payload mismatch at word %0d: %h",received,gpu.queue_data);
            received=received+1;
        end
    end
    initial begin
        words[0]='h16000000;words[1]='h12000000;words[2]='h12001000;
        words[3]='h00200040;words[4]='h00400040;words[5]=0;words[6]=0;words[7]=0;
        repeat(8)@(negedge hclk);resetn=1;
        repeat(20)@(negedge hclk);
        access(0,'he9001000,0,value);if(value!=='h424c5432)$fatal(1,"GPU ID");
        for(integer i=0;i<8;i++)access(1,'he9001010,words[i],value);
        repeat(100)@(negedge hclk);
        access(0,'he9001008,0,value);if(value!==1)$fatal(1,"Public done count %h",value);
        access(1,'he9005004,1,value);
        repeat(20)@(negedge hclk);
        access(0,'he9005004,0,value);if(value!==6)$fatal(1,"Snapshot not ready");
        access(0,'he9005008,0,value);if(value!==8)$fatal(1,"Host words %h",value);
        access(0,'he9005010,0,value);if(value!==8)$fatal(1,"Received words %h",value);
        access(0,'he9005020,0,value);if(value!==1)$fatal(1,"Captured done %h",value);
        access(0,'he900502c,0,value);if((value & 'hffffff80)!=='h08081600)$fatal(1,"Pointers/op/reset %h",value);
        access(0,'he9005030,0,value);if(value!==1)$fatal(1,"Blitter state");
        if(received!=8)$fatal(1,"Incomplete independent scoreboard");
        $display("PASS: full AHB bridge + video bus stage + GPU + debug; 8 exact command words, TARGET done=1, no DMA");
        $finish;
    end
    initial begin #1000000;$fatal(1,"Timeout");end
endmodule
