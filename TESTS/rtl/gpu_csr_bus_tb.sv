`timescale 1ns/1ps
// Standard AHB address/data overlap: a stalled read must neither repeat the
// following write nor return the next address's value. No DDR model is
// needed: this bench exercises CSR/font transactions without draw commands.
module gpu_csr_bus_tb #(parameter STAGED=0);
    reg hc=0,mc=0,rst=0;
    always #6.25 hc=~hc;
    always #6.671 mc=~mc;
    reg sel=0,wr=0;
    reg [1:0] trans=0;
    reg [31:0] address=0,data=0;
    wire hready,ps,pw,pr;
    wire [1:0] pt;
    wire [31:0] result,pa,pd,presult;
    generate if(STAGED)begin
        video_bus_stage stage(.clk(hc),.resetn(rst),.s_hsel(sel),.s_hwrite(wr),.s_htrans(trans),
          .s_haddr(address),.s_hwdata(data),.s_hready(hready),.s_hrdata(result),
          .m_hsel(ps),.m_hwrite(pw),.m_htrans(pt),.m_haddr(pa),.m_hwdata(pd),.m_hready(pr),.m_hrdata(presult));
    end else begin
        assign ps=sel;assign pw=wr;assign pt=trans;assign pa=address;assign pd=data;
        assign result=presult;assign hready=pr;
    end endgenerate
    wire valid,write;
    gpu_accel #(.FONT_FILE("font8x16.hex")) dut(.hclk(hc),.hresetn(rst),.hsel(ps),.hwrite(pw),
      .haddr(pa),.hwdata(pd),.htrans(pt),.hrdata(presult),.hready(pr),.mem_clk(mc),
      .valid(valid),.write(write),.addr(),.wr_data(),.wr_mask(),.ready(1'b1),.rd_data(256'd0),.rd_valid(1'b0));
    reg [31:0] addresses[0:2047],payloads[0:2047],expected[0:2047];
    reg writes[0:2047];
    integer n=0,reads=0,stores=0,stalls=0;
    task automatic add(input bit w,input [31:0] a,input [31:0] d,input [31:0] e);
        writes[n]=w;addresses[n]=a;payloads[n]=d;expected[n]=e;n++;
    endtask
    task automatic stream;
        integer next_request,active,completed;
        next_request=0;active=-1;completed=0;
        while(completed<n)begin
            @(negedge hc);
            sel=next_request<n;trans=sel ? 2:0;
            if(sel)begin wr=writes[next_request];address=addresses[next_request];end
            data=active>=0 ? payloads[active]:0;
            @(posedge hc);
            if(hready)begin
                if(active>=0)begin
                    if(!writes[active])begin
                        if(result!==expected[active])$fatal(1,"CSR %0d addr=%h got=%h expected=%h",active,addresses[active],result,expected[active]);
                        reads++;
                    end else stores++;
                    completed++;
                end
                if(sel)begin active=next_request;next_request++;end
                else active=-1;
            end else stalls++;
        end
        @(negedge hc);sel=0;trans=0;wr=0;
    endtask
    initial begin
        repeat(8)@(negedge hc);rst=1;
        repeat(8)@(negedge hc);
        // Abort a read while its next address is a font write. Reset must
        // discard both the outstanding read and the unaccepted write.
        sel=1;trans=2;address=0;
        @(posedge hc);
        @(negedge hc);address='h14;wr=1;data='hfff;rst=0;
        repeat(4)@(negedge hc);sel=0;trans=0;wr=0;rst=1;
        repeat(8)@(negedge hc);
        add(0,'h14,0,0);
        for(integer i=0;i<128;i++)begin
            add(0,0,0,'h424c5432);
            add(1,'h14,i*31,0);
            add(0,'h14,0,i*31);
            add(1,'h18,i^'h5a,0);
            add(1,'h18,i^'ha5,0);
            add(0,'h14,0,i*31+2);
            add(0,'h48,0,'h47334431);
            add(0,'h20,0,'h1f);
            add(0,'h30,0,'h1ff);
            add(0,'h1c,0,0);
        end
        // All holes and unaligned offsets return zero, not the previous CSR.
        for(integer a=0;a<256;a++)if(a%4!=0 || a>='h68)begin
            add(0,a,0,0);add(0,0,0,'h424c5432);
        end
        stream();
        if(stalls==0 || reads<1000 || stores!=384 || valid || dut.queue_lost!=0 || dut.command_word!=0)
            $fatal(1,"Missing AHB coverage or unsolicited GPU work");
        $display("PASS CSR staged=%0d reads=%0d writes=%0d stalls=%0d reset abort and all holes exact",STAGED,reads,stores,stalls);
        $finish;
    end
    initial begin #2000000;$fatal(1,"CSR bus timeout");end
endmodule
