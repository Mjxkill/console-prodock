`timescale 1ns/1ps
// USB IN may be retried: bytes read speculatively must remain unchanged
// until the packet is acknowledged. Exercise consecutive USB byte requests.
module usb_tx_retry_tb;
    reg clk=0;
    always #5 clk=~clk;
    reg resetn=0,write=0,read=0,active=0,ack=0;
    reg [7:0] data=0;
    wire [7:0] out;
    wire [6:0] count;
    wire full,empty;
    sync_tx_pkt_fifo #(.ASIZE(6)) dut(.CLK(clk),.RSTn(resetn),
        .write(write),.pktfin(ack),.txact(active),.read(read),.iData(data),
        .oData(out),.wrnum(count),.full(full),.empty(empty));
    integer checked=0;
    task packet(input integer first,input integer length,input bit accepted);
        @(negedge clk);active=1;
        repeat(4) @(negedge clk);
        for(integer n=0;n<length;n++) begin
            read=1;
            if(out!==8'(first+n))
                $fatal(1,"TX retry byte=%0d got=%02x expected=%02x rp=%0d next=%0d",n,out,8'(first+n),dut.rp,dut.rp_next);
            checked++;
            @(negedge clk);
        end
        read=0;
        repeat(3) @(negedge clk);
        if(accepted) begin ack=1;@(negedge clk);ack=0;end
        active=0;
        repeat(5) @(negedge clk);
    endtask
    initial begin
        repeat(4) @(negedge clk);resetn=1;
        for(integer n=0;n<48;n++) begin
            write=1;data=8'(n);@(negedge clk);
        end
        write=0;
        repeat(5) @(negedge clk);
        packet(0,8,1);
        packet(8,16,0); // lost ACK: retry the same packet
        packet(8,16,1);
        packet(24,7,0); // interrupted packet: retry from its start
        packet(24,24,1);
        if(!empty || count!=0) $fatal(1,"Not drained count=%0d",count);
        for(integer n=48;n<88;n++) begin
            write=1;data=8'(n);@(negedge clk);
        end
        write=0;
        repeat(5) @(negedge clk);
        packet(48,40,0); // packet crosses the physical RAM boundary
        packet(48,40,0); // two consecutive retries
        packet(48,40,1);
        if(!empty || count!=0) $fatal(1,"Not drained after wrap count=%0d",count);
        $display("PASS: %0d USB bytes checked including retries and an interrupted packet",checked);
        $finish;
    end
    initial begin #100000; $fatal(1,"timeout");end
endmodule
