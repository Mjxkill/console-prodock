// Dual-profile GEOMETRY COPY transaction bench.
//
// Scope: exact R6/R19 gpu_geometry plus its real gpu_v1/gpu_copy565 children.
// TARGET, SCISSOR and COPY are injected through the public geometry command
// port. The bench only observes internal nets; it never forces hardware or
// RTL state. It does not model a DDR PHY, board wiring, or physical timing.
// Profile selection is external (+define+NEO). In Neo the six child reset bits
// are tied together to !rst; Pro Dock has no child_resetn port.
`timescale 1ns/1ps
`default_nettype none
module tb;
`ifdef NEO
    parameter string PROFILE = "neo";
`else
    parameter string PROFILE = "prodock";
`endif

    // Exact staged capture reused from the previous tested bench.
    // TARGET: colour base 0x12000020, depth 0x12000040, 16x1, strides 32.
    localparam [255:0] P_TARGET =
        {96'b0,32'h00200020,32'h00100001,32'h12000040,32'h12000020,32'h16000000};
    // SCISSOR: left/top 0,0 and right/bottom 16,1 (full 16x1 clip).
    localparam [255:0] P_SCISSOR =
        {160'b0,32'h00100001,32'b0,32'h17000000};
    // COPY: source 0x12000020, 16x1, stride 32, origin 0,0, 16x1 rectangle.
    localparam [255:0] P_COPY =
        {32'b0,32'h00100001,64'b0,32'h00000020,32'h00100001,32'h12000020,32'h1d000000};

    localparam [28:0] READ_ADDR  = 29'h04800008; // (0x12000020[30:5])<<3
    localparam [28:0] WRITE_ADDR = 29'h04800008; // destination 0x12000020, lane 0
    localparam [31:0] WRITE_MASK = 32'h00000000; // sixteen RGB565 halfwords
    // PASS=1 in both exact geometry profiles; COPY WAIT0 is 7 in gpu_copy565.
    localparam integer PASS_STATE_BIT  = 1;
    localparam [4:0]  COPY_WAIT0       = 5'd7;
    localparam integer FIRST_VALID_BOUND = 40;
    localparam integer COMPLETION_BOUND  = 400;
    localparam integer NEGATIVE_WAIT     = 96;

    reg clk=0;
    always #5 clk=~clk;
    reg rst=1,start=0,ready=0,rd_valid=0;
    reg [255:0] command=0,rd_data=0;
    wire done,busy,valid,write;
    wire [31:0] rejected,fragments,passed,texture_hits,texture_misses;
    wire [31:0] geom_errors,vertices,triangles,culled,clipped,slivers,geom_cycles;
    wire [28:0] addr;
    wire [255:0] wr_data;
    wire [31:0] wr_mask;

`ifdef NEO
    wire [63:0] observe_packet_words;
    // Coherent baseline: rst and all six child reset bits deassert together.
    gpu_geometry dut(.child_resetn({6{!rst}}),.clk(clk),.rst(rst),.start(start),
        .command(command),.done(done),.busy(busy),
        .observe_packet_words(observe_packet_words),
        .rejected(rejected),.fragments(fragments),.passed(passed),
        .texture_hits(texture_hits),.texture_misses(texture_misses),
        .geom_errors(geom_errors),.vertices(vertices),.triangles(triangles),
        .culled(culled),.clipped(clipped),.slivers(slivers),.geom_cycles(geom_cycles),
        .valid(valid),.write(write),.addr(addr),.wr_data(wr_data),.wr_mask(wr_mask),
        .ready(ready),.rd_valid(rd_valid),.rd_data(rd_data));
`else
    gpu_geometry dut(.clk(clk),.rst(rst),.start(start),.command(command),
        .done(done),.busy(busy),
        .rejected(rejected),.fragments(fragments),.passed(passed),
        .texture_hits(texture_hits),.texture_misses(texture_misses),
        .geom_errors(geom_errors),.vertices(vertices),.triangles(triangles),
        .culled(culled),.clipped(clipped),.slivers(slivers),.geom_cycles(geom_cycles),
        .valid(valid),.write(write),.addr(addr),.wr_data(wr_data),.wr_mask(wr_mask),
        .ready(ready),.rd_valid(rd_valid),.rd_data(rd_data));
`endif

    integer cyc=0;
    always @(posedge clk) cyc<=cyc+1;

    // Observation only: child state, shader command pulses, and COPY chronology.
    reg [4:0] last_copy_state=0;
    reg [31:0] seen_copy_states=0;
    integer copy_transitions=0;
    integer shader_starts=0,shader_dones=0;
    integer gate_cycles=0;
    reg watch_chrono=0;
    integer chrono_start=-1,chrono_pass=-1,chrono_read=-1;
    integer chrono_copy_done=-1,chrono_geom_done=-1;
    always @(posedge clk) begin
        if(rst) begin
            last_copy_state=0;seen_copy_states=0;copy_transitions=0;
            shader_starts=0;shader_dones=0;
            watch_chrono=0;gate_cycles=0;
            chrono_start=-1;chrono_pass=-1;chrono_read=-1;
            chrono_copy_done=-1;chrono_geom_done=-1;
        end else begin
            if(dut.shader_start) shader_starts=shader_starts+1;
            if(dut.shader_done) shader_dones=shader_dones+1;
            if(dut.u_pixels.u_copy.state!==last_copy_state) begin
                seen_copy_states=seen_copy_states|(32'b1<<dut.u_pixels.u_copy.state);
                copy_transitions=copy_transitions+1;
                last_copy_state=dut.u_pixels.u_copy.state;
            end
            if(watch_chrono) begin
                if(start && chrono_start<0) chrono_start=cyc;
                if(dut.state[PASS_STATE_BIT] && chrono_pass<0) chrono_pass=cyc;
                // A legitimate read response must pass both return gates:
                // geometry gating (PASS or shader read phase) and COPY_WAIT.
                if(rd_valid && dut.u_pixels.u_copy.state==COPY_WAIT0) begin
                    gate_cycles=gate_cycles+1;
                    if(!dut.u_pixels.rd_valid)
                        $fatal(1,"GEOMETRY_GATE_CLOSED profile=%0s",PROFILE);
                    if(!dut.u_pixels.u_copy.rd_valid)
                        $fatal(1,"COPY_GATE_CLOSED profile=%0s",PROFILE);
                    if(chrono_read<0) chrono_read=cyc;
                end
                if(dut.shader_done && shader_starts==3 && chrono_copy_done<0)
                    chrono_copy_done=cyc;
                if(done && chrono_geom_done<0) chrono_geom_done=cyc;
            end
        end
    end

    reg reset_reported=0;
    reg [28:0] observed_read_addr=0,observed_write_addr=0;
    reg [255:0] observed_write_data=0;
    reg [31:0] observed_write_mask=0;
    integer case_start_cycle=0;
    integer t_start,t_pass,t_read_response,t_copy_done,t_geometry_done;

    task launch(input [255:0] packet);
        begin
            @(negedge clk); command=packet; start=1;
            @(negedge clk); start=0;
        end
    endtask

    task wait_geometry(input integer bound,input [8*20-1:0] tag);
        integer n;
        begin
            n=0;
            while(!done && n<bound) begin @(negedge clk); n=n+1; end
            if(!done) $fatal(1,"NO_GEOMETRY_DONE tag=%0s",tag);
            if(rejected!==0) $fatal(1,"GEOMETRY_REJECTED tag=%0s value=%0d",tag,rejected);
            repeat(5) @(negedge clk);
        end
    endtask

    task reset_dut(input [8*20-1:0] tag);
        begin
            @(negedge clk);
            rst=1;start=0;ready=0;rd_valid=0;command=0;rd_data=0;
            repeat(5) @(negedge clk);
            rst=0;
            repeat(8) @(negedge clk);
            if(busy!==0 || done!==0 || valid!==0) $fatal(1,"RESET_NOT_IDLE tag=%0s",tag);
`ifdef NEO
            if(dut.child_resetn!==6'b111111) $fatal(1,"CHILD_RESET_INCOHERENT");
            if(!reset_reported)
                $display("RESET profile=%0s coherent=1 child_resetn=tied_to_rst bits=6 rst=%0d",PROFILE,rst);
`else
            if(!reset_reported)
                $display("RESET profile=%0s coherent=1 child_resetn=absent rst=%0d",PROFILE,rst);
`endif
            reset_reported=1;
        end
    endtask

    // Exact TARGET then SCISSOR, both through the real geometry frontend.
    task stage_setup(input [8*20-1:0] tag);
        begin
            launch(P_TARGET);
            wait_geometry(80,"target");
            if(dut.shader_target_valid!==1) $fatal(1,"TARGET_NOT_ACCEPTED tag=%0s",tag);
            if(dut.u_pixels.width!==16 || dut.u_pixels.height!==1 || dut.u_pixels.right!==16 || dut.u_pixels.bottom!==1)
                $fatal(1,"TARGET_BOUNDS tag=%0s",tag);
            if(shader_starts!==1 || shader_dones!==1)
                $fatal(1,"TARGET_COUNTS tag=%0s starts=%0d dones=%0d",tag,shader_starts,shader_dones);
            launch(P_SCISSOR);
            wait_geometry(80,"scissor");
            if(dut.u_pixels.left!==0 || dut.u_pixels.top!==0 || dut.u_pixels.right!==16 || dut.u_pixels.bottom!==1)
                $fatal(1,"SCISSOR_BOUNDS tag=%0s",tag);
            if(shader_starts!==2 || shader_dones!==2)
                $fatal(1,"SCISSOR_COUNTS tag=%0s starts=%0d dones=%0d",tag,shader_starts,shader_dones);
        end
    endtask

    // Positive COPY through geometry. READY is held low across the read request
    // and across the write request; the read response is delayed as requested.
    task run_case(input [8*20-1:0] id,input [255:0] data_value,
                  input integer read_stall,input integer response_delay,
                  input integer write_stall);
        integer n,w,first_latency,total_cycles;
        begin
            reset_dut(id);
            stage_setup(id);
            case_start_cycle=cyc;
            watch_chrono=1;gate_cycles=0;
            chrono_start=-1;chrono_pass=-1;chrono_read=-1;
            chrono_copy_done=-1;chrono_geom_done=-1;
            launch(P_COPY);

            n=0;
            while(!valid && n<FIRST_VALID_BOUND) begin @(negedge clk); n=n+1; end
            if(!valid) $fatal(1,"NO_READ_REQUEST id=%0s",id);
            if(write) $fatal(1,"FIRST_REQUEST_IS_WRITE id=%0s",id);
            if(addr!==READ_ADDR) $fatal(1,"READ_ADDR id=%0s addr=%h",id,addr);
            if(dut.u_pixels.packet!==P_COPY) $fatal(1,"PIXEL_PACKET id=%0s",id);
            if(shader_starts!==3 || shader_dones!==2)
                $fatal(1,"STALE_ACCUMULATOR_BEFORE_COPY id=%0s starts=%0d dones=%0d",id,shader_starts,shader_dones);
            if(dut.u_pixels.u_copy.bad!==0) $fatal(1,"COPY_BAD_EARLY id=%0s",id);
`ifdef NEO
            // Neo only: both captured command snapshots must be the exact COPY.
            if(observe_packet_words[31:0]!==P_COPY[31:0] ||
               observe_packet_words[63:32]!==P_COPY[31:0])
                $fatal(1,"OBSERVE_PACKET id=%0s words=%h",id,observe_packet_words);
`endif
            first_latency=n;
            observed_read_addr=addr;

            w=0;
            while(w<read_stall) begin
                @(negedge clk);
                if(!valid || write) $fatal(1,"READ_NOT_HELD id=%0s",id);
                if(addr!==READ_ADDR) $fatal(1,"READ_ADDR_HELD id=%0s",id);
                w=w+1;
            end

            @(negedge clk);
            ready=1; rd_data=data_value;
            if(response_delay==0) rd_valid=1;
            @(negedge clk);
            ready=0; rd_valid=0;
            if(response_delay>0) begin
                repeat(response_delay) @(negedge clk);
                rd_data=data_value; rd_valid=1;
                @(negedge clk); rd_valid=0;
            end

            n=0;
            while(!(valid && write) && n<COMPLETION_BOUND) begin
                if(done || dut.u_pixels.u_copy.bad!==0)
                    $fatal(1,"ENDED_BEFORE_WRITE id=%0s",id);
                @(negedge clk); n=n+1;
            end
            if(!(valid && write)) $fatal(1,"NO_WRITE_REQUEST id=%0s",id);
            if(addr!==WRITE_ADDR) $fatal(1,"WRITE_ADDR id=%0s addr=%h",id,addr);
            if(wr_data!==data_value) $fatal(1,"WRITE_DATA id=%0s",id);
            if(wr_mask!==WRITE_MASK) $fatal(1,"WRITE_MASK id=%0s mask=%h",id,wr_mask);
            observed_write_addr=addr;
            observed_write_data=wr_data;
            observed_write_mask=wr_mask;

            w=0;
            while(w<write_stall) begin
                @(negedge clk);
                if(!valid || !write) $fatal(1,"WRITE_NOT_HELD id=%0s",id);
                if(addr!==WRITE_ADDR) $fatal(1,"WRITE_ADDR_HELD id=%0s",id);
                w=w+1;
            end
            @(negedge clk); ready=1;
            @(negedge clk); ready=0;

            n=0;
            while(!done && n<COMPLETION_BOUND) begin @(negedge clk); n=n+1; end
            if(!done) $fatal(1,"NO_COMPLETION id=%0s",id);
            if(rejected!==0) $fatal(1,"GEOMETRY_REJECTED id=%0s value=%0d",id,rejected);
            if(dut.u_pixels.u_copy.bad!==0) $fatal(1,"COPY_BAD id=%0s",id);
            if(shader_starts!==3 || shader_dones!==3)
                $fatal(1,"FINAL_COUNTS id=%0s starts=%0d dones=%0d",id,shader_starts,shader_dones);
            if(gate_cycles!==1) $fatal(1,"GATE_CYCLES id=%0s count=%0d",id,gate_cycles);
            repeat(5) @(negedge clk);
            total_cycles=cyc-case_start_cycle;
            t_start=chrono_start-case_start_cycle;
            t_pass=chrono_pass-case_start_cycle;
            t_read_response=chrono_read<0 ? -1:chrono_read-case_start_cycle;
            t_copy_done=chrono_copy_done<0 ? -1:chrono_copy_done-case_start_cycle;
            t_geometry_done=chrono_geom_done<0 ? -1:chrono_geom_done-case_start_cycle;
            watch_chrono=0;

            $display("CASE profile=%0s id=%0s result=PASS rejects=%0d done=1 bad=0 busy=%0d first_read_latency=%0d total_cycles=%0d read_addr=%h write_addr=%h write_data=%h write_mask=%h read_accept_wait=%0d write_accept_wait=%0d response_delay=%0d shader_starts=%0d shader_dones=%0d gate_cycles=%0d gate_ok=1 geom_errors=%0d geom_cycles=%0d copy_states=%h transitions=%0d t_start=%0d t_pass=%0d t_read_response=%0d t_copy_shader_done=%0d t_geometry_done=%0d",
                PROFILE,id,rejected,busy,first_latency,total_cycles,
                observed_read_addr,observed_write_addr,observed_write_data,
                observed_write_mask,read_stall,write_stall,response_delay,
                shader_starts,shader_dones,gate_cycles,geom_errors,geom_cycles,
                seen_copy_states,copy_transitions,
                t_start,t_pass,t_read_response,t_copy_done,t_geometry_done);
        end
    endtask

    // Expected-negative: the READ request is accepted but no response arrives.
    // The real COPY must remain BUSY in WAIT0 with no BAD and no DONE. This is
    // an absent-response observation, not a physical cause.
    task run_missing_response(input [8*20-1:0] id);
        begin
            reset_dut(id);
            stage_setup(id);
            case_start_cycle=cyc;
            watch_chrono=1;gate_cycles=0;
            chrono_start=-1;chrono_pass=-1;chrono_read=-1;
            chrono_copy_done=-1;chrono_geom_done=-1;
            launch(P_COPY);
            begin : wait_read
                integer n;
                n=0;
                while(!valid && n<FIRST_VALID_BOUND) begin @(negedge clk); n=n+1; end
                if(!valid) $fatal(1,"NO_READ_REQUEST id=%0s",id);
                if(write || addr!==READ_ADDR)
                    $fatal(1,"MISSING_RESPONSE_REQUEST id=%0s",id);
                if(shader_starts!==3 || shader_dones!==2)
                    $fatal(1,"NEGATIVE_COUNTS id=%0s starts=%0d dones=%0d",id,shader_starts,shader_dones);
            end
            repeat(5) @(negedge clk);
            @(negedge clk); ready=1;
            @(negedge clk); ready=0;
            repeat(NEGATIVE_WAIT) @(negedge clk);
            if(done) $fatal(1,"EXPECTED_STALL_GOT_DONE id=%0s",id);
            if(!busy) $fatal(1,"EXPECTED_STALL_NOT_BUSY id=%0s",id);
            if(rejected!==0 || dut.u_pixels.u_copy.bad!==0)
                $fatal(1,"EXPECTED_STALL_BAD id=%0s",id);
            if(dut.u_pixels.u_copy.state!==COPY_WAIT0)
                $fatal(1,"EXPECTED_WAIT0 id=%0s state=%0d",id,dut.u_pixels.u_copy.state);
            if(valid) $fatal(1,"EXPECTED_READ_VALID_CLEARED id=%0s",id);
            if(gate_cycles!==0) $fatal(1,"NEGATIVE_GATE_COUNT id=%0s",id);
            if(chrono_copy_done>=0 || chrono_geom_done>=0)
                $fatal(1,"NEGATIVE_CHRONOLOGY id=%0s",id);
            if(shader_starts!==3 || shader_dones!==2)
                $fatal(1,"NEGATIVE_FINAL_COUNTS id=%0s starts=%0d dones=%0d",id,shader_starts,shader_dones);
            t_start=chrono_start-case_start_cycle;
            t_pass=chrono_pass-case_start_cycle;
            watch_chrono=0;
            $display("CASE profile=%0s id=%0s result=EXPECTED_STALL state=WAIT0 busy=%0d done=0 bad=0 rejects=%0d wait_cycles=%0d valid=%0d shader_starts=%0d shader_dones=%0d gate_cycles=0 gate_ok=1 t_start=%0d t_pass=%0d t_read_response=-1 t_copy_shader_done=-1 t_geometry_done=-1",
                PROFILE,id,busy,rejected,NEGATIVE_WAIT,valid,
                shader_starts,shader_dones,t_start,t_pass);
        end
    endtask

    initial begin
        // Same four transaction latency cases as the prior tested bench.
        run_case("stall_zero",256'b0,32,17,32);
        run_case("stall_one",{256{1'b1}},32,17,32);
        run_case("simul_one",{256{1'b1}},0,0,0);
        run_case("short_delay",
            {32'h01234567,32'h89abcdef,32'h0f1e2d3c,32'h4b5a6978,
             32'hc7d6e5f4,32'h30211203,32'hfedcba98,32'h76543210},5,1,7);
        run_missing_response("no_read_response");
        $display("GEOMETRY_CASE_RUN_PASS profile=%0s",PROFILE);
        $finish;
    end
endmodule
`default_nettype wire
