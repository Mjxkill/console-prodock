`timescale 1ns/1ps
// Standalone bounded bench for the exact gpu_copy565 RTL.
//
// Stimulus comes only from cases.hex (+case=N selects one 15-word record).
// The DUT is the real module, driven through its public ports, with an
// external native 32-byte memory terminal.  The RESULT line is built from
// measured outputs and a payload comparison against the documented memory
// content formula; it never asserts a precomputed verdict.
module bench;
  reg clk = 0;
  always #5 clk = ~clk;

  // ------------------------------------------------------------------
  // DUT interface
  // ------------------------------------------------------------------
  reg rst = 1;
  reg start = 0;
  reg [255:0] command = 0;
  reg [29:0]  dst_base = 0;
  reg [15:0]  dst_stride = 0;
  reg [15:0]  dst_height = 0;
  reg [15:0]  clip_l = 0;
  reg [15:0]  clip_t = 0;
  reg [15:0]  clip_r = 0;
  reg [15:0]  clip_b = 0;

  wire        done;
  wire        bad;
  wire        valid;
  wire        write;
  wire [28:0] addr;
  wire [255:0] wr_data;
  wire [31:0] wr_mask;

  reg         ready = 1;          // native memory always accepts
  reg         rd_valid = 0;
  reg [255:0] rd_data = 0;

  gpu_copy565 dut (
    .clk(clk), .rst(rst), .start(start), .command(command),
    .dst_base(dst_base), .dst_stride(dst_stride), .dst_height(dst_height),
    .clip_l(clip_l), .clip_t(clip_t), .clip_r(clip_r), .clip_b(clip_b),
    .done(done), .bad(bad), .valid(valid), .write(write),
    .addr(addr), .wr_data(wr_data), .wr_mask(wr_mask),
    .ready(ready), .rd_valid(rd_valid), .rd_data(rd_data)
  );

  // ------------------------------------------------------------------
  // Native memory content
  //
  // The RTL address port carries a 4-byte word address; the documented
  // byte address is therefore addr*4.  A 32-byte response word i is
  // (byte_address + 4*i) ^ 32'ha5396c17.
  // ------------------------------------------------------------------
  function [31:0] mem_word32;
    input [31:0] byte_addr;
    begin
      mem_word32 = byte_addr ^ 32'ha5396c17;
    end
  endfunction

  function [255:0] mem_block32;
    input [28:0] word_addr;
    integer k;
    reg [31:0] base;
    begin
      base = {3'b000, word_addr} << 2;
      for (k = 0; k < 8; k = k + 1)
        mem_block32[k*32 +: 32] = mem_word32(base + k*4);
    end
  endfunction

  // ------------------------------------------------------------------
  // Read response engine: accepts a request only on valid&&ready, then
  // returns one 256-bit response with a one-cycle rd_valid pulse.  The
  // response is held stable during that pulse.
  // ------------------------------------------------------------------
  reg [2:0]  rd_timer;
  reg        rd_pending;
  reg [28:0] rd_addr_q;

  always @(posedge clk) begin
    if (rst) begin
      rd_valid   <= 1'b0;
      rd_pending <= 1'b0;
      rd_timer   <= 3'd0;
      rd_addr_q  <= 29'd0;
      rd_data    <= 256'd0;
    end else begin
      rd_valid <= 1'b0;                 // default: one-cycle pulse
      if (valid && ready && !write) begin
        rd_addr_q  <= addr;
        rd_timer   <= 3'd3;             // response a few cycles later
        rd_pending <= 1'b1;
      end
      if (rd_pending) begin
        if (rd_timer == 3'd0) begin
          rd_valid   <= 1'b1;
          rd_data    <= mem_block32(rd_addr_q);
          rd_pending <= 1'b0;
        end else begin
          rd_timer <= rd_timer - 3'd1;
        end
      end
    end
  end

  // ------------------------------------------------------------------
  // Cases and measured state
  // ------------------------------------------------------------------
  reg [31:0] words [0:14*15-1];
  integer    case_id;
  integer    base;
  integer    read_count;
  integer    write_count;
  reg        read_err;
  reg        write_err;
  reg        late_io;
  reg        late_window;
  reg [255:0] exp_board_data;

  // Transaction monitor samples the handshake with pre-edge signal values.
  // Only the exact board case is allowed to move native traffic; every
  // other fixed case is either rejected or has zero clipped extent.
  always @(posedge clk) begin
    if (!rst) begin
      if (valid && ready) begin
        if (write) begin
          write_count <= write_count + 1;
          if (case_id == 0) begin
            $display("OBS board_write addr=%h mask=%h payload_match=%0d",
                     addr, wr_mask, (wr_data === exp_board_data));
            if (addr !== 29'h04800008)        write_err <= 1'b1;
            if (wr_mask !== 32'h00000000)     write_err <= 1'b1;
            if (wr_data !== exp_board_data)   write_err <= 1'b1;
            if (write_count != 0)             write_err <= 1'b1;
            if (read_count == 0)              write_err <= 1'b1;
          end else begin
            $display("OBS unexpected_write case=%0d addr=%h mask=%h", case_id, addr, wr_mask);
            write_err <= 1'b1;
          end
        end else begin
          read_count <= read_count + 1;
          if (case_id == 0) begin
            $display("OBS board_read addr=%h", addr);
            if (addr !== 29'h04800000)        read_err <= 1'b1;
            if (read_count != 0)              read_err <= 1'b1;
          end else begin
            $display("OBS unexpected_read case=%0d addr=%h", case_id, addr);
            read_err <= 1'b1;
          end
        end
      end
      if (late_window && valid && ready)
        late_io <= 1'b1;
    end
  end

  // Simulation-only read-only peek at the DUT's registered verdict and
  // state.  It does not drive or force any DUT signal.
  always @(posedge clk) begin
    if (!rst && dut.state == 5'd1)
      $display("OBS case=%0d state=CHECK", case_id);
    if (!rst && dut.state == 5'd17)
      $display("OBS case=%0d state=VALIDATE descriptor_bad=%b", case_id, dut.descriptor_bad);
  end

  // ------------------------------------------------------------------
  // Run one selected case.
  // ------------------------------------------------------------------
  initial begin
    integer cyc, dcount, dcycle, dseen, obs_bad, payload_ok;

    $readmemh("cases.hex", words);

    case_id = 0;
    if (!$value$plusargs("case=%d", case_id))
      case_id = 0;
    if (case_id < 0 || case_id > 13)
      case_id = 0;
    base = case_id * 15;

    // 8 command words then dst_base,stride,height,clip_l,t,clip_r,b.
    command    = {words[base+7], words[base+6], words[base+5], words[base+4],
                  words[base+3], words[base+2], words[base+1], words[base+0]};
    dst_base   = words[base+8][29:0];
    dst_stride = words[base+9][15:0];
    dst_height = words[base+10][15:0];
    clip_l     = words[base+11][15:0];
    clip_t     = words[base+12][15:0];
    clip_r     = words[base+13][15:0];
    clip_b     = words[base+14][15:0];

    // Board case source byte address is 04800000*4 and both lanes are 0,
    // so the exact write payload is the source block itself.
    exp_board_data = mem_block32(29'h04800000);

    read_count  = 0;
    write_count = 0;
    read_err    = 1'b0;
    write_err   = 1'b0;
    late_io     = 1'b0;
    late_window = 1'b0;

    // Reset for several edges, then one-cycle start with command stable.
    rst   = 1'b1;
    start = 1'b0;
    repeat (4) @(negedge clk);
    rst = 1'b0;
    @(negedge clk);
    start = 1'b1;
    @(negedge clk);
    start = 1'b0;

    // Deadline: wait for the single done pulse.
    dseen  = 0;
    dcount = 0;
    dcycle = 0;
    obs_bad = 0;
    cyc = 0;
    while (!dseen && cyc < 1000) begin
      @(posedge clk);
      #1;
      cyc = cyc + 1;
      if (done) begin
        dcount = dcount + 1;
        if (!dseen) begin
          dseen     = 1;
          dcycle    = cyc;
          obs_bad   = bad;
          late_window = 1'b1;
        end
      end
    end

    // Post-done window: catch any late native handshake or a second done.
    if (dseen) begin
      repeat (20) begin
        @(posedge clk);
        #1;
        if (done) dcount = dcount + 1;
      end
    end

    @(negedge clk);
    payload_ok = !(read_err || write_err);
    $display("RESULT case=%0d done=%0d bad=%0d reads=%0d writes=%0d payload_ok=%0d late_io=%0d cycles=%0d",
             case_id, dcount, obs_bad, read_count, write_count,
             payload_ok, late_io, (dseen ? dcycle : 1000));
    $finish;
  end
endmodule
