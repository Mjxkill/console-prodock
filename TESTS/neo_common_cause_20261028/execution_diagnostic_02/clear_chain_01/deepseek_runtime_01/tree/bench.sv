`timescale 1ns/1ps
// Exercise the two real AHB stages between AE350 EXTS and the Neo GPU.
// The hard AE350 macro is replaced by a protocol-correct, stalled master.
module bench;
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
    gpu_accel #(.FONT_FILE("font8x16.hex")) gpu(
        .hclk(hclk),.hresetn(resetn),.mem_clk(mem_clk),
        .hsel(bus_sel && bus_addr[14:12]==1),.hwrite(bus_write),.haddr(bus_addr),.hwdata(bus_wdata),.htrans(bus_trans),
        .hrdata(gpu_data),.hready(gpu_ready),.valid(valid),.write(write),.addr(addr),.wr_data(wr_data),.wr_mask(wr_mask),
        .ready(native_ready),.rd_data(256'd0),.rd_valid(1'b0),.debug_state(debug_state),.debug_accept(debug_accept));
    wire native_ready;
    neo_gpu_debug debug_port(.hclk(hclk),.resetn(resetn),.mem_clk(mem_clk),
        .hsel(bus_sel && bus_addr[14:12]==5),.hwrite(bus_write),.htrans(bus_trans),.haddr(bus_addr),.hwdata(bus_wdata),
        .hrdata(debug_data),.hready(debug_ready),.host_accept(debug_accept),.live(debug_state));

    integer tick=0,accepted=0,stalls=0;
    wire men,mwen,mwend;wire[2:0]mcmd;wire[28:0]maddr;
    wire[255:0]mdata;wire[31:0]mmask;
    wire mrdy=(tick%7!=0 && tick%7!=1),mwrdy=(tick%5!=0);
    ddr_gpu_arb arb(.clk(mem_clk),.rst_n(resetn),
      .c_en(1'b0),.c_cmd(3'd0),.c_addr(29'd0),.c_ready(),
      .c_wr_en(1'b0),.c_wr_end(1'b0),.c_wr_data(256'd0),.c_wr_mask(32'hffffffff),
      .c_wr_ready(),.c_rd_data(),.c_rd_valid(),.c_rd_end(),
      .g_valid(1'b0),.g_addr(29'd0),.g_ready(),.g_data(),.g_data_valid(),
      .b_valid(valid),.b_write(write),.b_addr(addr),.b_wr_data(wr_data),.b_wr_mask(wr_mask),
      .b_ready(native_ready),.b_rd_data(),.b_rd_valid(),.m_en(men),.m_cmd(mcmd),.m_addr(maddr),
      .m_ready(mrdy),.m_wr_en(mwen),.m_wr_end(mwend),.m_wr_data(mdata),.m_wr_mask(mmask),
      .m_wr_ready(mwrdy),.m_rd_data(256'd0),.m_rd_valid(1'b0),.m_rd_end(1'b0));
    always @(posedge mem_clk)begin
      tick<=tick+1;
      if(resetn && valid && !native_ready)stalls<=stalls+1;
      if(resetn && men && mrdy)begin
        if(mcmd!=0 || !mwen || !mwrdy || !mwend || maddr!==29'h04800008 ||
           mmask!==0 || mdata!=={16{16'h6b4d}})$fatal(1,"CHECK_FAIL FOOTPRINT");
        accepted<=accepted+1;
      end
    end
    task access(input bit wr,input [31:0] address,input [31:0] data,output [31:0] result);
        @(negedge hclk);while(!hready)@(negedge hclk);
        hsel=1;htrans=2;hwrite=wr;haddr=address;
        @(negedge hclk);hsel=0;htrans=0;hwdata=data;
        do @(negedge hclk);while(!hready);
        result=hrdata;hwdata=0;hwrite=0;
    endtask

    reg[31:0]value,words[0:15];integer received=0;
    always @(posedge mem_clk)if(resetn && gpu.command_we)begin
      if(received>=16 || gpu.queue_data!==words[received])$fatal(1,"CHECK_FAIL PAYLOAD");
      received=received+1;
    end
    task wait_done(input[31:0]wanted);
      integer polls;begin
       polls=0;value=0;
       while(value!=wanted && polls<400)begin
        access(0,32'he9001008,0,value);polls=polls+1;
       end
       if(value!=wanted)$fatal(1,"CHECK_FAIL COMPLETION done=%0d want=%0d",value,wanted);
      end
    endtask
    initial begin
      words[0]='h16000000;words[1]='h12000020;words[2]='h12000040;
      words[3]='h00100001;words[4]='h00200020;words[5]=0;words[6]=0;words[7]=0;
      words[8]='h1c000000;words[9]=1;words[10]='h6b4d;words[11]=0;
      words[12]=0;words[13]='h00100001;words[14]=0;words[15]=0;
      repeat(8)@(negedge hclk);resetn=1;repeat(20)@(negedge hclk);
      access(0,'he9001000,0,value);if(value!=='h424c5432)$fatal(1,"CHECK_FAIL ID");
      for(integer i=0;i<8;i++)access(1,'he9001010,words[i],value);
      wait_done(1);if(accepted!=0)$fatal(1,"CHECK_FAIL TARGET_DMA");
      for(integer i=8;i<16;i++)access(1,'he9001010,words[i],value);
      wait_done(2);repeat(40)@(negedge hclk);
      access(0,'he9001004,0,value);if(value!=0)$fatal(1,"CHECK_FAIL BUSY");
      access(0,'he9001034,0,value);if(value!=0)$fatal(1,"CHECK_FAIL REJECT");
      if(accepted!=1 || received!=16 || stalls==0)$fatal(1,"CHECK_FAIL COVERAGE");
      $display("BASELINE_PASS accepted=%0d words=%0d stalls=%0d",accepted,received,stalls);
      $finish;
    end
    initial begin #1000000;$fatal(1,"CHECK_FAIL WATCHDOG");end
endmodule
