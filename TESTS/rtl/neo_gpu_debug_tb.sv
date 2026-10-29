`timescale 1ns/1ps
module neo_gpu_debug_tb;
    reg hclk=0,mem_clk=0,run_mem=1,resetn=0;
    real hp=6.25,mp=6.667,phase=0.371;
    initial begin
        if($value$plusargs("hp=%f",hp))begin end
        forever #(hp) hclk=~hclk;
    end
    initial begin
        if($value$plusargs("mp=%f",mp))begin end
        if($value$plusargs("phase=%f",phase))begin end
        #(phase);
        forever begin #(mp); if(run_mem)mem_clk=~mem_clk;end
    end
    reg hsel=0,hwrite=0,host_accept=0;
    reg [1:0] htrans=0;
    reg [31:0] haddr=0,hwdata=0;
    wire [31:0] hrdata;
    wire hready;
    reg [31:0] generation=0;
    wire [255:0] live;
    for(genvar k=0;k<8;k=k+1)begin
        assign live[k*32+:32]=(generation+k*32'h1020304) & (k==1 ? 32'hffffffef:32'hffffffff);
    end
    always @(posedge mem_clk)generation<=generation+1;
    neo_gpu_debug dut(.*);
    task read_reg(input [7:0] addr,output [31:0] data);
        @(negedge hclk);hsel=1;htrans=2;hwrite=0;haddr=addr;
        @(negedge hclk);hsel=0;htrans=0;
        if(hready!==0)$fatal(1,"Read did not insert its wait state");
        // An idle address may change during the data phase. The selected
        // register must remain the one accepted in the address phase.
        haddr=32'hfffffffc;
        @(negedge hclk);
        if(hready!==1)$fatal(1,"Read wait exceeded one cycle");
        data=hrdata;
    endtask
    task snapshot_request;
        @(negedge hclk);hsel=1;htrans=2;hwrite=1;haddr=4;
        @(negedge hclk);hsel=0;htrans=0;hwdata=1;
        @(negedge hclk);hwdata=0;hwrite=0;
    endtask
    task wait_ready;
        reg [31:0] status;
        integer n;
        begin:named_ready
            for(n=0;n<50;n=n+1)begin
                read_reg(4,status);
                if(status[2])disable named_ready;
            end
            $fatal(1,"Debug source never became ready");
        end
    endtask
    task check_snapshot(input integer expected_sequence);
        reg [31:0] status,base,word_value,expected;
        integer n;
        begin
            begin:named_wait
                for(n=0;n<100;n=n+1)begin
                    read_reg(4,status);
                    if(status[1:0]==2)disable named_wait;
                end
                $fatal(1,"Snapshot did not finish");
            end
            read_reg(12,word_value);
            if(word_value!==expected_sequence)$fatal(1,"Wrong sequence");
            read_reg(32,base);
            for(n=0;n<8;n=n+1)begin
                read_reg(32+n*4,word_value);
                expected=base+n*32'h1020304;
                if(n==1)expected=expected & 32'hffffffef;
                if(word_value!==expected)$fatal(1,"Torn/stale snapshot lane %0d",n);
            end
            repeat(10)@(posedge hclk);
            read_reg(32,word_value);
            if(word_value!==base)$fatal(1,"Snapshot changed without request");
        end
    endtask
    reg [31:0] status;
    initial begin
        repeat(8)@(negedge hclk);resetn=1;
        wait_ready();read_reg(0,status);
        if(status!==32'h4e474442)$fatal(1,"Wrong debug ID");
        for(integer a=0;a<256;a=a+1)begin
            if((a%4)!=0 || a==24 || a==28 || a>=64)begin
                read_reg(a,status);
                if(status!==0)$fatal(1,"Invalid address %h returned %h",a,status);
            end
        end
        for(integer n=1;n<=30;n=n+1)begin snapshot_request();check_snapshot(n);end
        @(negedge mem_clk);run_mem=0;
        snapshot_request();repeat(20)@(posedge hclk);read_reg(4,status);
        if(!status[0])$fatal(1,"Stopped source returned a false acknowledgement");
        run_mem=1;check_snapshot(31);
        // Reset with a previous ACK=1 and stopped source must not replay it.
        @(negedge mem_clk);run_mem=0;
        @(negedge hclk);resetn=0;
        repeat(8)@(negedge hclk);resetn=1;
        repeat(8)@(negedge hclk);snapshot_request();read_reg(4,status);
        if(status!==0)$fatal(1,"Stale ACK or ready survived stopped-clock reset");
        run_mem=1;wait_ready();snapshot_request();check_snapshot(1);
        $display("PASS: coherent snapshots, stopped source and reset hp=%f mp=%f",hp,mp);
        $finish;
    end
    initial begin #1000000;$fatal(1,"Timeout");end
endmodule
