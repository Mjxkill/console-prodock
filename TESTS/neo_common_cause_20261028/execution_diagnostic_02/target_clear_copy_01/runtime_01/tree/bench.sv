`timescale 1ns/1ps
// Exact-chain bench for the R19 CLEAR path.
//
// The two real AHB stages, gpu_accel, its async command FIFO, the blitter,
// geometry/pixel engines and ddr_gpu_arb are used unmodified.  Only the
// external CPU master and the external DDR readiness model live here.
//
// Fault injection is done exclusively on bench connections/inputs:
//   fault 0 : healthy model (seed 1/8 select different clock periods,
//             relative phase and stall phase)
//   fault 1 : hold m_ready low after TARGET completes
//   fault 2 : hold m_wr_ready low after TARGET completes
//   fault 3 : split the arbiter b_ready from the GPU ready input, so the
//             arbiter still accepts native writes while the GPU never sees
//             acceptance feedback
//   fault 4 : TB-driven reset while a CLEAR native write is pending with
//             native readiness withheld; then fresh TARGET/CLEAR recovery
//   fault 5 : the protected native_monitor changes only its observation of
//             the first accepted write into a READ.  Bench stimuli are
//             unchanged; this proves monitor sensitivity, not DUT behaviour.
//
// No RTL file is edited.  All prints are simulation observations only.
module bench;
    // ------------------------------------------------------------------
    // Run configuration and seed-dependent clocks
    // ------------------------------------------------------------------
    integer seed = 1;
    integer fault = 0;
    integer hclk_half = 6;       // ns, half period
    integer memclk_half = 7;     // ns, half period
    integer memclk_phase = 1;    // ns before the first mem_clk edge
    integer stall_offset = 0;    // mem_clk stall-pattern phase

    initial begin
        $value$plusargs("seed=%d", seed);
        $value$plusargs("fault=%d", fault);
        // Seed 1 and seed 8 deliberately use different periods, relative
        // phase and DDR stall phase; both are legal timing models.
        case (seed)
            8: begin
                hclk_half    = 5;
                memclk_half  = 8;
                memclk_phase = 3;
                stall_offset = 3;
            end
            default: begin
                hclk_half    = 6;
                memclk_half  = 7;
                memclk_phase = 1;
                stall_offset = 0;
            end
        endcase
    end

    reg hclk = 0, mem_clk = 0, resetn = 0;

    // The 1 ps settle delay lets the plusarg/period decode above happen
    // before the first generator delay is evaluated.
    initial begin
        #0.001;
        forever #(hclk_half) hclk = ~hclk;
    end
    initial begin
        #0.001;
        #(memclk_phase);
        forever #(memclk_half) mem_clk = ~mem_clk;
    end

    // ------------------------------------------------------------------
    // AHB master and the two real bus stages
    // ------------------------------------------------------------------
    reg hsel = 0, hwrite = 0;
    reg [31:0] haddr = 0, hwdata = 0;
    reg [1:0] htrans = 0;
    wire hready;
    wire [31:0] hrdata;

    wire [1:0] leg_sel, leg_trans;
    wire leg_write, leg_ready;
    wire [31:0] leg_addr, leg_wdata, leg_rdata;

    ahb_exts_bridge bridge(
        .hclk(hclk), .hresetn(resetn),
        .m_hsel(hsel), .m_haddr(haddr), .m_htrans(htrans),
        .m_hwrite(hwrite), .m_hwdata(hwdata),
        .m_hrdata(hrdata), .m_hready(hready),
        .s_hsel(leg_sel), .s_htrans(leg_trans), .s_hwrite(leg_write),
        .s_haddr(leg_addr), .s_hwdata(leg_wdata),
        .s0_hrdata(32'hbad00000), .s0_hready(1'b1),
        .s1_hrdata(leg_rdata), .s1_hready(leg_ready));

    wire bus_sel, bus_write, bus_ready;
    wire [1:0] bus_trans;
    wire [31:0] bus_addr, bus_wdata, bus_rdata;

    video_bus_stage stage(
        .clk(hclk), .resetn(resetn),
        .s_hsel(leg_sel[1]), .s_hwrite(leg_write), .s_htrans(leg_trans),
        .s_haddr(leg_addr), .s_hwdata(leg_wdata),
        .s_hready(leg_ready), .s_hrdata(leg_rdata),
        .m_hsel(bus_sel), .m_hwrite(bus_write), .m_htrans(bus_trans),
        .m_haddr(bus_addr), .m_hwdata(bus_wdata),
        .m_hready(bus_ready), .m_hrdata(bus_rdata));

    reg [2:0] selected = 0;
    always @(posedge hclk)
        if (!resetn) selected <= 0;
        else if (bus_sel) selected <= bus_addr[14:12];

    wire [31:0] gpu_data, debug_data;
    wire gpu_ready, debug_ready, debug_accept;
    wire valid, write;
    wire [28:0] addr;
    wire [255:0] wr_data, debug_state;
    wire [31:0] wr_mask;
    wire [63:0] packet_words;

    assign bus_ready = selected == 1 ? gpu_ready :
                       selected == 5 ? debug_ready : 1'b1;
    assign bus_rdata = selected == 1 ? gpu_data :
                       selected == 5 ? debug_data : 32'hbad00001;

    // ------------------------------------------------------------------
    // Native DDR readiness model and fault switches
    // ------------------------------------------------------------------
    reg arm_m = 0;          // fault 1: withhold m_ready
    reg arm_wr = 0;         // fault 2: withhold m_wr_ready
    reg hold_all = 0;       // fault 4: withhold both before/through reset
    reg suppress_feedback = 0; // fault 3: cut arbiter acceptance -> GPU

    reg [31:0] tick = 0;
    wire [31:0] phase_tick = tick + stall_offset;
    wire mrdy_base = ((phase_tick % 7) != 0) && ((phase_tick % 7) != 1);
    wire mwrdy_base = ((phase_tick % 5) != 0);
    wire mrdy = (hold_all || ((fault == 1) && arm_m)) ? 1'b0 : mrdy_base;
    wire mwrdy = (hold_all || ((fault == 2) && arm_wr)) ? 1'b0 : mwrdy_base;

    wire arb_b_ready;
    // Fault 3 intercepts only this connection.  The arbiter keeps seeing its
    // own b_ready and can accept the native write; the GPU does not.
    wire gpu_native_ready =
        ((fault == 3) && suppress_feedback) ? 1'b0 : arb_b_ready;

    wire men, mwen, mwend;
    wire [2:0] mcmd;
    wire [28:0] maddr;
    wire [255:0] mdata;
    wire [31:0] mmask;


    reg [255:0] native_response_data=0;
    reg native_response_valid=0;
    wire [255:0] blit_response_data;
    wire blit_response_valid;
    integer read_accepts=0,read_returns=0,read_delay=0;
    reg [255:0] source_line;
    initial begin
        for(integer k=0;k<8;k=k+1)
            source_line[k*32+:32]=(32'h12000000+4*k)^32'ha5396c17;
    end
    always @(posedge mem_clk)begin
        native_response_valid<=0;
        if(!resetn)begin read_accepts<=0;read_returns<=0;read_delay<=0;end
        else begin
            if(read_delay>0)begin
                read_delay<=read_delay-1;
                if(read_delay==1)begin
                    native_response_data<=source_line;
                    native_response_valid<=1;
                    read_returns<=read_returns+1;
                end
            end
            if(men && mrdy && mcmd==1)begin
                if(read_accepts!=0 || maddr!==29'h04800000 || mwen)
                    $fatal(1,"COPY_BAD_READ_OR_DUPLICATE");
                read_accepts<=read_accepts+1;read_delay<=5;
            end
            if(men && mrdy && mcmd!=0 && mcmd!=1)$fatal(1,"COPY_BAD_COMMAND");
            if(mwen && !(men && mrdy && mwrdy && mcmd==0))
                $fatal(1,"COPY_UNPAIRED_WRITE");
        end
    end

    gpu_accel #(.FONT_FILE("font8x16.hex")) gpu(
        .hclk(hclk), .hresetn(resetn), .mem_clk(mem_clk),
        .hsel(bus_sel && bus_addr[14:12] == 1), .hwrite(bus_write),
        .haddr(bus_addr), .hwdata(bus_wdata), .htrans(bus_trans),
        .hrdata(gpu_data), .hready(gpu_ready),
        .valid(valid), .write(write), .addr(addr),
        .wr_data(wr_data), .wr_mask(wr_mask),
        .ready(gpu_native_ready), .rd_data(blit_response_data), .rd_valid(blit_response_valid),
        .debug_state(debug_state), .debug_accept(debug_accept),
        .observe_packet_words(packet_words));

    neo_gpu_debug debug_port(
        .hclk(hclk), .resetn(resetn), .mem_clk(mem_clk),
        .hsel(bus_sel && bus_addr[14:12] == 5), .hwrite(bus_write),
        .htrans(bus_trans), .haddr(bus_addr), .hwdata(bus_wdata),
        .hrdata(debug_data), .hready(debug_ready),
        .host_accept(debug_accept), .live(debug_state),
        .observe_packet_words(packet_words));

    ddr_gpu_arb arb(
        .clk(mem_clk), .rst_n(resetn),
        .c_en(1'b0), .c_cmd(3'd0), .c_addr(29'd0), .c_ready(),
        .c_wr_en(1'b0), .c_wr_end(1'b0), .c_wr_data(256'd0),
        .c_wr_mask(32'hffffffff), .c_wr_ready(), .c_rd_data(),
        .c_rd_valid(), .c_rd_end(),
        .g_valid(1'b0), .g_addr(29'd0), .g_ready(), .g_data(),
        .g_data_valid(),
        .b_valid(valid), .b_write(write), .b_addr(addr),
        .b_wr_data(wr_data), .b_wr_mask(wr_mask),
        .b_ready(arb_b_ready), .b_rd_data(blit_response_data), .b_rd_valid(blit_response_valid),
        .m_en(men), .m_cmd(mcmd), .m_addr(maddr),
        .m_ready(mrdy), .m_wr_en(mwen), .m_wr_end(mwend),
        .m_wr_data(mdata), .m_wr_mask(mmask),
        .m_wr_ready(mwrdy), .m_rd_data(native_response_data), .m_rd_valid(native_response_valid),
        .m_rd_end(native_response_valid));


    integer received=0, native_requests=0;
    reg [31:0] value;
    reg [31:0] words[0:23];
    integer injection=0;
    initial $value$plusargs("injection=%d",injection);
    // Protected expected stream, independent of model-owned stimulus.
    initial begin
      words[0]=32'h16000000; words[1]=32'h12000020;
      words[2]=32'h12000040; words[3]=32'h00100001;
      words[4]=32'h00200020; words[5]=0; words[6]=0; words[7]=0;
      words[8]=32'h1c000000; words[9]=0; words[10]=32'h6b4d;
      words[11]=0; words[12]=0; words[13]=32'h00100001; words[14]=0; words[15]=0;
      words[16]=32'h1d000000; words[17]=32'h12000000; words[18]=32'h00100001;
      words[19]=32'h20; words[20]=0; words[21]=0; words[22]=0; words[23]=0;
    end
    always @(posedge mem_clk) if(resetn)begin
      if(valid || men || mwen) native_requests<=native_requests+1;
      if(gpu.command_we)begin
        if(received>=24 || gpu.queue_data!==words[received])$fatal(1,"payload order");
        received<=received+1;
      end
    end
    // Deliberate logical counterexamples, not inferred hardware causes.
    // Inject after stable completion, before the next command reaches pixel.
    task automatic inject_after_target;
      if(injection==1)force gpu.u_v1.u_pixels.target_valid=1'b0;
    endtask
    task automatic inject_after_clear;
      if(injection==2)force gpu.u_v1.u_pixels.copy_bad=1'b1;
      if(injection==3)force gpu.u_v1.u_pixels.target_valid=1'b0;
    endtask
    task automatic access(input bit wr,input[31:0] address,input[31:0] data,output[31:0] result);
      integer guard;
      begin
        guard=0;@(negedge hclk);
        while(!hready)begin
          if(guard++>256)$fatal(1,"AHB ready deadline");@(negedge hclk);
        end
        hsel=1;htrans=2;hwrite=wr;haddr=address;
        @(negedge hclk);hsel=0;htrans=0;hwdata=data;guard=0;
        do begin
          @(negedge hclk);if(guard++>256)$fatal(1,"AHB response deadline");
        end while(!hready);
        result=hrdata;hwdata=0;hwrite=0;
      end
    endtask
    task automatic send_packet(input integer first);
      for(integer i=first;i<first+8;i++)access(1,32'he9001010,words[i],value);
    endtask
    task automatic observe(input integer want, output integer rejects);
      integer polls;reg[31:0] done_count,status;
      begin
        polls=0;done_count=0;status=1;
        while((done_count!=want || status!=0) && polls<400)begin
          access(0,32'he9001008,0,done_count);
          access(0,32'he9001004,0,status);polls++;
        end
        if(done_count!=want || status!=0)$fatal(1,"completion deadline");
        access(0,32'he9001034,0,value);rejects=value;
        if(native_requests!=0)$fatal(1,"unexpected native request");
      end
    endtask
    integer observed_clear=-1,observed_copy=-1;
    task automatic finish_check;
      integer rejects,want_done,want_words;
      begin
        want_done=injection==1?2:3;want_words=injection==1?16:24;
        observe(want_done,rejects);
        repeat(40)@(negedge hclk);
        if(received!=want_words || native_requests!=0)$fatal(1,"final footprint");
        if(observed_clear!=(injection==1?1:0))$fatal(1,"clear observation");
        if(observed_copy!=(injection==1?-1:(injection==0?0:1)))$fatal(1,"copy observation");
        $display("SEQUENCE_RESULT injection=%0d clear_reject=%0d copy_reject=%0d done=%0d words=%0d native=%0d",
          injection,observed_clear,observed_copy,want_done,received,native_requests);
        $finish;
      end
    endtask
    `include "scenario.svh"
    initial begin #400000;$fatal(1,"global deadline");end
endmodule
