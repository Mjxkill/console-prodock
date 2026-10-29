// Cross-client DDR composition bench.
// CPU128 -> ddr_ui_adapt -> ddr_gpu_arb <- scanout/blitter -> native_memory.
// The scoreboard builds its byte image only from high-level operations and
// compares each client response with an independently computed request value.
`timescale 1ns/1ps
module bench;

    // ---------------------------------------------------------------------
    // Clock/reset and public DUT ports
    // ---------------------------------------------------------------------
    reg clk = 1'b0;
    always #5 clk = ~clk;

    reg rst_n = 1'b0;

    // 128-bit CPU side of the adapter.
    reg         u_cmd_en = 0;
    reg  [2:0]  u_cmd = 0;
    reg  [28:0] u_addr = 0;
    wire        u_cmd_ready;
    reg         u_wr_data_en = 0;
    reg         u_wr_data_end = 0;
    reg  [127:0] u_wr_data = 0;
    reg  [15:0]  u_wr_data_mask = 0;
    wire        u_wr_data_rdy;
    wire [127:0] u_rd_data;
    wire        u_rd_data_valid;
    wire        u_rd_data_end;

    // Adapter 256-bit IP side, wired to the arbiter CPU port.
    wire        ip_cmd_en;
    wire [2:0]  ip_cmd;
    wire [28:0] ip_addr;
    wire        ip_cmd_ready;
    wire        ip_wr_data_en;
    wire        ip_wr_data_end;
    wire [255:0] ip_wr_data;
    wire [31:0]  ip_wr_data_mask;
    wire         ip_wr_data_rdy;
    wire [255:0] ip_rd_data;
    wire         ip_rd_data_valid;
    wire         ip_rd_data_end;

    // Scanout producer.
    reg         g_valid = 0;
    reg  [28:0] g_addr = 0;
    wire        g_ready;
    wire [255:0] g_data;
    wire        g_data_valid;

    // Blitter/GPU producer.
    wire        b_valid;
    wire        b_write;
    wire [28:0] b_addr;
    wire [255:0] b_wr_data;
    wire [31:0] b_wr_mask;
    wire        b_ready;
    wire [255:0] b_rd_data;
    wire        b_rd_valid;

    // Ordered native terminal.
    wire        m_en;
    wire [2:0]  m_cmd;
    wire [28:0] m_addr;
    wire        m_ready;
    wire        m_wr_en;
    wire        m_wr_end;
    wire [255:0] m_wr_data;
    wire [31:0]  m_wr_mask;
    wire        m_wr_ready;
    wire [255:0] m_rd_data;
    wire        m_rd_valid;
    wire        m_rd_end;

    // ---------------------------------------------------------------------
    // DUT composition.
    // ---------------------------------------------------------------------
    ddr_ui_adapt u_adapter (
        .clk(clk), .rst_n(rst_n),
        .u_cmd_en(u_cmd_en), .u_cmd(u_cmd), .u_addr(u_addr),
        .u_cmd_ready(u_cmd_ready),
        .u_wr_data_en(u_wr_data_en), .u_wr_data_end(u_wr_data_end),
        .u_wr_data(u_wr_data), .u_wr_data_mask(u_wr_data_mask),
        .u_wr_data_rdy(u_wr_data_rdy),
        .u_rd_data(u_rd_data), .u_rd_data_valid(u_rd_data_valid),
        .u_rd_data_end(u_rd_data_end),
        .ip_cmd_en(ip_cmd_en), .ip_cmd(ip_cmd), .ip_addr(ip_addr),
        .ip_cmd_ready(ip_cmd_ready),
        .ip_wr_data_en(ip_wr_data_en), .ip_wr_data_end(ip_wr_data_end),
        .ip_wr_data(ip_wr_data), .ip_wr_data_mask(ip_wr_data_mask),
        .ip_wr_data_rdy(ip_wr_data_rdy),
        .ip_rd_data(ip_rd_data), .ip_rd_data_valid(ip_rd_data_valid),
        .ip_rd_data_end(ip_rd_data_end)
    );

    ddr_gpu_arb u_arb (
        .clk(clk), .rst_n(rst_n),
        .c_en(ip_cmd_en), .c_cmd(ip_cmd), .c_addr(ip_addr),
        .c_ready(ip_cmd_ready),
        .c_wr_en(ip_wr_data_en), .c_wr_end(ip_wr_data_end),
        .c_wr_data(ip_wr_data), .c_wr_mask(ip_wr_data_mask),
        .c_wr_ready(ip_wr_data_rdy),
        .c_rd_data(ip_rd_data), .c_rd_valid(ip_rd_data_valid),
        .c_rd_end(ip_rd_data_end),
        .g_valid(g_valid), .g_addr(g_addr), .g_ready(g_ready),
        .g_data(g_data), .g_data_valid(g_data_valid),
        .b_valid(b_valid && !suppress_request), .b_write(b_write), .b_addr(b_addr),
        .b_wr_data(b_wr_data), .b_wr_mask(b_wr_mask), .b_ready(b_ready),
        .b_rd_data(b_rd_data), .b_rd_valid(b_rd_valid),
        .m_en(m_en), .m_cmd(m_cmd), .m_addr(m_addr), .m_ready(m_ready),
        .m_wr_en(m_wr_en), .m_wr_end(m_wr_end), .m_wr_data(m_wr_data),
        .m_wr_mask(m_wr_mask), .m_wr_ready(m_wr_ready),
        .m_rd_data(m_rd_data), .m_rd_valid(m_rd_valid), .m_rd_end(m_rd_end)
    );

    native_memory u_native (
        .clk(clk), .resetn(rst_n), .hold_command(hold_command),
        .hold_write(hold_write), .hold_returns(hold_returns), .en(m_en), .cmd(m_cmd), .addr(m_addr),
        .ready(m_ready), .wr_en(m_wr_en), .wr_end(m_wr_end),
        .wr_data(m_wr_data), .wr_mask(m_wr_mask), .wr_ready(m_wr_ready),
        .rd_data(m_rd_data), .rd_valid(m_rd_valid), .rd_end(m_rd_end)
    );

    // Test-only fault controls. They are real top-level connections, never
    // force/deposit internal RTL state. Driver may only change these inputs.
    reg hold_command=0,hold_write=0,hold_returns=0;
    reg cut_feedback=0,suppress_request=0;
    reg start=0;
    reg [255:0] command=0;
    wire gpu_done,gpu_busy,target_valid;
    wire [31:0] rejected;
    integer gpu_done_count=0;
    gpu_v1 gpu(.clk(clk),.rst(!rst_n),.child_resetn({4{rst_n}}),
      .start(start),.command(command),.done(gpu_done),.busy(gpu_busy),
      .observe_packet_word0(),.target_config_valid(target_valid),
      .material_config_valid(),.rejected(rejected),.fragments(),.passed(),
      .texture_hits(),.texture_misses(),.valid(b_valid),.write(b_write),
      .addr(b_addr),.wr_data(b_wr_data),.wr_mask(b_wr_mask),
      .ready(b_ready && !cut_feedback && !suppress_request),
      .rd_valid(b_rd_valid),.rd_data(b_rd_data));
    always @(posedge clk) if(rst_n && gpu_done) gpu_done_count<=gpu_done_count+1;

    integer scenario=0,cycle=0,full_block_ready_cycles=0;
    reg cpu_begin=0;
    integer cpu_count=0,cpu_sent=0,scan_count=0;
    reg [31:0] cpu_words[0:31];
    initial $value$plusargs("case=%d",scenario);
    always @(posedge clk)begin
      cycle<=cycle+1;
      if(rst_n && u_arb.full && b_valid && m_ready && m_wr_ready)
        full_block_ready_cycles<=full_block_ready_cycles+1;
      if(cycle>12000)$fatal(1,"HARNESS bounded watchdog");
      if(rst_n && g_data_valid)scan_count<=scan_count+1;
    end
    // A serial CPU-side proxy: one upstream 128-bit beat per requested
    // 32-bit load, 32 loads over scratch128B. Real AE350/AHB/CDC not modeled.
    // We align to16B and select the corresponding 32-bit lane independently.
    initial begin : cpu_reader
      integer i,n; reg[31:0] word,expected;
      wait(cpu_begin); @(negedge clk);
      for(i=0;i<32;i=i+1)begin
        n=0;
        while(!u_cmd_ready && n<6000)begin @(negedge clk);n=n+1;end
        if(!u_cmd_ready)$fatal(1,"CPU request watchdog");
        u_cmd=1;u_addr=(32'h12000000+(i/4)*16)>>1;u_cmd_en=1;
        @(negedge clk);u_cmd_en=0;cpu_sent=cpu_sent+1;n=0;
        while(!u_rd_data_valid && n<6000)begin @(negedge clk);n=n+1;end
        if(!u_rd_data_valid)$fatal(1,"CPU response watchdog");
        word=u_rd_data[(i%4)*32+:32];
        expected=(32'h12000000+4*i)^32'ha5396c17;
        if(scenario!=5 && scenario!=7 && i>=8 && i<16)expected=32'h6b4d6b4d;
        if(word!==expected)$fatal(1,"CPU_DATA index%0d got%08x expected%08x",i,word,expected);
        cpu_words[i]=word;cpu_count=cpu_count+1;
        @(negedge clk);
      end
    end
    task automatic report(input string label);
      $display("OBS {\"case\":%0d,\"label\":\"%s\",\"cpu\":%0d,\"sent\":%0d,\"gpu_done\":%0d,\"busy\":%0d,\"rejected\":%0d,\"native_reads\":%0d,\"native_writes\":%0d,\"returned\":%0d,\"scan_returns\":%0d,\"full\":%0d,\"tags\":%0d,\"cpu_pending\":%0d,\"take_blitter\":%0d,\"prefer_blitter\":%0d,\"adapter_tags\":%0d,\"gpu_valid\":%0d,\"gpu_ready\":%0d,\"command_ready\":%0d,\"write_ready\":%0d,\"full_ready_cycles\":%0d,\"cycle\":%0d}",
        scenario,label,cpu_count,cpu_sent,gpu_done_count,gpu_busy,rejected,
        u_native.reads,u_native.writes,u_native.returned,scan_count,
        u_arb.full,(u_arb.wp-u_arb.rp)&31,u_arb.cpu_pending,
        u_arb.take_blitter,u_arb.prefer_blitter,(u_adapter.tq_w-u_adapter.tq_r)&31,
        b_valid,b_ready&&!cut_feedback&&!suppress_request,m_ready,m_wr_ready,full_block_ready_cycles,cycle);
    endtask
    // Driver implements reset, TARGET, CLEAR, faults and bounded observation.
    // Fixed test wrapper and above byte oracle remain read-only to the agent.
    `include "scenario.svh"
endmodule
