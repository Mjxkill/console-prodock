`timescale 1ns/1ps
module gpu_scanout_tb #(
    parameter W=64, H=4, HT=128, VT=12,
    parameter HSTART=16, VSTART=2, HSYNC=4, VSYNC=1, RGB=0
);
    reg hc=0, pc=0, mc=0, rst=0;
    always #6.25 hc=~hc;
    always #14.285 pc=~pc;
    always #6.666 mc=~mc;
    reg sel=0, wr=0;
    reg [31:0] addr=0, data=0;
    reg [1:0] trans=0;
    wire [31:0] result;
    wire ready, fv, fr, fdv, de, hs, vs;
    wire [28:0] fa;
    wire [255:0] fd;
    wire [5:0] r,g,b;
    gpu_scanout #(.WIDTH(W),.HEIGHT(H),.H_TOTAL(HT),.V_TOTAL(VT),
        .H_START(HSTART),.V_START(VSTART),.H_SYNC(HSYNC),.V_SYNC(VSYNC)) dut (
        .hclk(hc),.hresetn(rst),.hsel(sel),.hwrite(wr),.haddr(addr),.hwdata(data),.htrans(trans),
        .hrdata(result),.hready(ready),.pixel_clk(pc),.mem_clk(mc),
        .fetch_valid(fv),.fetch_addr(fa),.fetch_ready(fr),.fetch_data(fd),.fetch_data_valid(fdv),
        .lcd_en(de),.lcd_hs(hs),.lcd_vs(vs),.lcd_r(r),.lcd_g(g),.lcd_b(b));

    // A concurrent CPU client and variable-latency DDR model exercise read tags.
    wire cr, cwr, cv, ce;
    wire [255:0] cd;
    reg cpu_pending=0;
    reg [28:0] cpu_addr=29'h400;
    wire cmd_en, wr_en, wr_end;
    wire [2:0] cmd;
    wire [28:0] mem_addr;
    wire [255:0] wd;
    wire [31:0] wm;
    reg mem_ready=0, rd_valid=0;
    reg [255:0] rd_data=0;
    ddr_gpu_arb arb (
        .clk(mc),.rst_n(rst),.c_en(cr && !cpu_pending),.c_cmd(3'b001),.c_addr(cpu_addr),.c_ready(cr),
        .c_wr_en(1'b0),.c_wr_end(1'b0),.c_wr_data(256'b0),.c_wr_mask(32'b0),.c_wr_ready(cwr),
        .c_rd_data(cd),.c_rd_valid(cv),.c_rd_end(ce),.g_valid(fv),.g_addr(fa),.g_ready(fr),.g_data(fd),.g_data_valid(fdv),
        .b_valid(1'b0),.b_write(1'b0),.b_addr(29'd0),.b_wr_data(256'd0),.b_wr_mask(32'hffffffff),
        .b_ready(),.b_rd_data(),.b_rd_valid(),
        .m_en(cmd_en),.m_cmd(cmd),.m_addr(mem_addr),.m_ready(mem_ready),
        .m_wr_en(wr_en),.m_wr_end(wr_end),.m_wr_data(wd),.m_wr_mask(wm),.m_wr_ready(mem_ready),
        .m_rd_data(rd_data),.m_rd_valid(rd_valid),.m_rd_end(rd_valid));

    function automatic [7:0] pixel(input integer a);
        return 8'((a*73) ^ (a>>7) ^ (a>>12));
    endfunction
    function automatic [255:0] burst(input integer a);
        reg [255:0] value;
        for (integer i=0;i<32;i++) value[i*8+:8]=pixel(a+i);
        return value;
    endfunction
    integer addresses[$], due[$];
    integer cycle=0, last_due=0, cpureads=0;
    reg stalled=0;
    always @(negedge mc) begin
        cycle=cycle+1;
        mem_ready=rst && !stalled && (cycle%7 != 0);
        rd_valid=0;
        if (due.size()>0 && due[0]<=cycle && !stalled) begin
            rd_data=burst(addresses.pop_front());
            rd_valid=1;
            void'(due.pop_front());
        end
    end
    always @(posedge mc) begin
        if (rst) begin
            if (cmd_en && mem_ready) begin
                if (cmd!=1 || mem_addr[2:0]!=0) $fatal(1,"Invalid read command");
                addresses.push_back(int'(mem_addr)*4);
                last_due = ((cycle+3+cycle%5)>last_due) ? cycle+3+cycle%5 : last_due+1;
                due.push_back(last_due);
            end
            if (cr && !cpu_pending) cpu_pending<=1;
            if (cv) begin
                if (!cpu_pending || cd!==burst(int'(cpu_addr)*4) || !ce) $fatal(1,"CPU read tag/data");
                cpu_pending<=0; cpu_addr<=cpu_addr+8; cpureads<=cpureads+1;
            end
        end
    end

    task automatic write_reg(input [31:0] a, input [31:0] d);
        @(negedge hc); sel=1; wr=1; trans=2; addr=a;
        do @(posedge hc); while (!ready);
        @(negedge hc); sel=0; trans=0; data=d;
        do @(posedge hc); while (!ready);
        @(negedge hc); wr=0;
    endtask
    task automatic read_reg(input [31:0] a, output [31:0] d);
        @(negedge hc); sel=1; wr=0; trans=2; addr=a;
        @(posedge hc);
        @(negedge hc); sel=0; trans=0; d=result;
    endtask

    // Check every pixel, including first/last pixels and alternating line banks.
    // Frame selection is sampled at VS, independently from the scanout's X/Y.
    reg prev_vs=1, prev_de=0, check_pixels=0, skip_pixels=0;
    integer col=0,row=0,checked_frames=0,selected_base=0,expected_base=0;
    reg expected_rgb=RGB!=0,selected_rgb=0;
    function automatic [17:0] expected_color(input integer at,input bit direct);
        reg [15:0] p;
        p={pixel(at+1),pixel(at)};
        return direct ? {p[15:11],p[15],p[10:5],p[4:0],p[4]}:{10'b0,pixel(at)};
    endfunction
    always @(negedge pc) begin
        if (!vs && prev_vs) begin
            if (check_pixels && row!=H) $fatal(1,"Wrong active line count %0d",row);
            row=0; col=0;
            selected_base=expected_base;
            selected_rgb=expected_rgb;
            check_pixels=rst && dut.active_enable && !stalled && !skip_pixels;
            if (check_pixels) checked_frames=checked_frames+1;
        end
        if (de && check_pixels) begin
            if ({r,g,b} !== expected_color(selected_base+(row*W+col)*(selected_rgb ? 2:1),selected_rgb))
                $fatal(1,"Pixel frame%0d xy=%0d,%0d got=%h expected=%h base=%h",checked_frames,col,row,{r,g,b},pixel(selected_base+row*W+col),selected_base);
            col=col+1;
        end
        if (!de && prev_de) begin
            if (check_pixels && col!=W) $fatal(1,"Wrong active pixel count %0d",col);
            col=0; row=row+1;
        end
        prev_vs=vs; prev_de=de;
    end
    reg [31:0] value, sum;
    initial begin
        #200; rst=1;
        read_reg(0,value);
        if(value!=32'h47505531) $fatal(1,"GPU ID");
        for(integer i=0;i<256;i++) write_reg('h400+i*4,i);
        write_reg(4,'h2000); write_reg(8,RGB ? 3:1); write_reg(12,1);
        expected_base='h2000;
        wait(checked_frames>=3); @(negedge vs);
        read_reg('h1c,value); if(value!=0) $fatal(1,"Unexpected underflows %0d",value);
        sum=0;
        for(integer a='h2000;a<'h2000+W*H*(RGB ? 2:1);a+=4)
            sum=sum+{pixel(a+3),pixel(a+2),pixel(a+1),pixel(a)};
        read_reg('h20,value); if(value!=sum) $fatal(1,"Framebuffer checksum %h expected %h",value,sum);
        // Submit a flip during active pixels: it must wait for blanking.
        wait(de); write_reg(4,'h3000); write_reg(12,1);
        repeat(20) @(posedge pc);
        if(dut.active_base!='h2000) $fatal(1,"Page changed during display");
        wait(dut.active_base=='h3000); expected_base='h3000;
        wait(checked_frames>=6); @(negedge vs);
        if(cpureads<100) $fatal(1,"CPU starved");
        // Stall DDR across entire frames, then recover without shifting pixels.
        skip_pixels=1;
        @(negedge vs); stalled=1;
        repeat(3) @(negedge vs);
        read_reg('h1c,value); if(value==0) $fatal(1,"Underflow not reported");
        stalled=0;
        repeat(3) @(negedge vs);
        skip_pixels=0;
        wait(checked_frames>=9); @(negedge vs);
        // Switch between direct RGB and indexed palette at vertical blank.
        wait(de);write_reg(8,RGB ? 1:3);write_reg(12,1);
        repeat(20)@(posedge pc);
        if(dut.active_rgb565!=(RGB!=0))$fatal(1,"Format changed inside active frame");
        wait(dut.active_rgb565!=(RGB!=0));expected_rgb=RGB==0;
        wait(checked_frames>=12);@(negedge vs);
        $display("PASS: palette, pixel order, exact dimensions, checksum, vblank flip, underflow recovery, CPU reads=%0d",cpureads);
        $finish;
    end
    initial begin #(HT*VT*28.57*40); $fatal(1,"Timeout"); end
endmodule
