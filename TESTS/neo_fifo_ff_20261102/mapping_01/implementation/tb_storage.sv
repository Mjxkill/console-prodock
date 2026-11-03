// Compare the candidate against the unmodified vendor SDPB and an independent
// indexed scoreboard. Same-address concurrent read/write is outside UG300.
`timescale 1ns/1ps
module tb;
    reg ca=0,cb=0,run_a=1,run_b=1;
    real half_a=6.25,half_b=6.667,phase=2.0;
    integer sync_mode=0,cmem_binding=0,ignored,i,j,checks=0,writes=0,reads=0;
    integer collision_outputs_excluded=0;
    reg cea=0,ceb=0,reset=0,oce=0;
    reg [13:0] ada=14'h000f,adb=0;
    reg [31:0] di=0;
    wire clkb=sync_mode ? ca:cb;
    wire read_ce=cmem_binding ? 1'b1:ceb;
    wire output_reset=cmem_binding ? 1'b0:reset;
    wire [31:0] reference,candidate;
    reg [31:0] memory[0:127];
    reg [31:0] expected=0;
    GSR GSR(.GSRI(1'b1));
    SDPB original(.DO(reference),.DI(di),.BLKSELA(3'b0),.BLKSELB(3'b0),
        .ADA(ada),.ADB(adb),.CLKA(ca),.CLKB(clkb),.CEA(cea),.CEB(read_ce),
        .OCE(oce),.RESET(output_reset));
    defparam original.BIT_WIDTH_0=32,original.BIT_WIDTH_1=32;
    defparam original.READ_MODE=0,original.RESET_MODE="SYNC";
    neo_command_ff128 candidate_mem(.DO(candidate),.DI(di),.BLKSELA(3'b0),
        .BLKSELB(3'b0),.ADA(ada),.ADB(adb),.CLKA(ca),.CLKB(clkb),
        .CEA(cea),.CEB(read_ce),.OCE(oce),.RESET(output_reset));
    initial begin
        ignored=$value$plusargs("AHALF=%f",half_a);
        ignored=$value$plusargs("BHALF=%f",half_b);
        ignored=$value$plusargs("PHASE=%f",phase);
        ignored=$value$plusargs("SYNC=%d",sync_mode);
        ignored=$value$plusargs("CMEM=%d",cmem_binding);
        forever begin #(half_a);if(run_a)ca=~ca;end
    end
    initial begin #0;#(phase);forever begin #(half_b);if(run_b)cb=~cb;end end
    always @(posedge ca)if(cea)begin
        memory[ada[11:5]]<=di;writes=writes+1;
    end
    always @(posedge clkb)begin: compare_read
        reg excluded;
        excluded=sync_mode && cea && read_ce && ada[11:5]==adb[11:5];
        if(output_reset)expected<=0;
        else if(read_ce)begin expected<=memory[adb[11:5]];reads=reads+1;end
        #0.5;
        if(excluded)collision_outputs_excluded=collision_outputs_excluded+1;
        else if(candidate!==reference || candidate!==expected)begin
            $display("MISMATCH time=%0t addr=%0d CE=%b reset=%b candidate=%h vendor=%h expected=%h",
                $time,adb[11:5],ceb,reset,candidate,reference,expected);
            $fatal(1,"storage behavior mismatch");
        end
        if(!excluded)checks=checks+1;
    end
    task write_word(input integer index,input [31:0] value);
        begin @(negedge ca);ada={2'b0,index[6:0],5'b01111};di=value;cea=1;
            @(negedge ca);cea=0;end
    endtask
    task read_word(input integer index);
        begin @(negedge clkb);adb={2'b0,index[6:0],5'b0};ceb=1;
            @(negedge clkb);ceb=0;end
    endtask
    initial begin
        $display("STORAGE_PROGRESS begin t=%0t",$time);
        for(i=0;i<128;i=i+1)memory[i]=0;
        #30;
        $display("STORAGE_PROGRESS clocks_started t=%0t",$time);
        // Initial contents/output match the exact SDPB INIT defaults, not reset RAM.
        for(i=0;i<128;i=i+1)read_word(i);
        $display("STORAGE_PROGRESS initialized_read t=%0t",$time);
        for(i=0;i<128;i=i+1)write_word(i,32'h75a00000^(32'h01020408*i));
        $display("STORAGE_PROGRESS initial_write t=%0t",$time);
        for(i=127;i>=0;i=i-1)read_word(i);
        // RESET priority when CEB=0, and held output when CEB=0 afterwards.
        @(negedge clkb);reset=1;ceb=0;
        repeat(3)@(negedge clkb);
        reset=0;
        repeat(3)@(negedge clkb);
        for(i=0;i<128;i=i+1)read_word(i);
        // RESET never suppresses port-A writes, nor clears any stored word.
        @(negedge clkb);reset=1;
        write_word(64,32'hdecafbad);
        @(negedge clkb);reset=0;
        read_word(64);read_word(63);
        // Concurrent clocks, independent addresses: no undefined RAM collision.
        fork
            begin for(i=0;i<900;i=i+1)write_word(64+(i%64),32'h9f317b65^(i*32'h10203));end
            begin for(j=0;j<900;j=j+1)begin
                read_word(j%64);
                @(negedge clkb);oce=~oce; // ignored in bypass, must not change latency
            end end
        join
        $display("STORAGE_PROGRESS concurrent_complete t=%0t",$time);
        // Both stopped and one-domain-stopped episodes are digital tests only.
        @(negedge ca);run_a=0;cea=0;
        if(!sync_mode)repeat(12)@(negedge clkb);else #200;
        run_a=1;
        @(negedge cb);run_b=0;
        if(!sync_mode)begin write_word(126,32'hc001d00d);write_word(127,32'h10000001);end
        #200;run_b=1;
        for(i=0;i<128;i=i+1)read_word(i);
        // Repeated local reset/output-enable combinations after populated memory.
        for(i=0;i<24;i=i+1)begin
            @(negedge clkb);reset=i%3==0;ceb=i%4!=0;adb={(2'b0),i[6:0],5'b0};
        end
        @(negedge clkb);reset=0;ceb=0;
        read_word(127);
        $display("STORAGE_EQUIVALENCE_PASS checks=%0d writes=%0d reads=%0d sync=%0d cmem=%0d collision_outputs_excluded=%0d",
            checks,writes,reads,sync_mode,cmem_binding,collision_outputs_excluded);
        $finish;
    end
    initial begin #1000000;$fatal(1,"test timeout");end
endmodule
