`timescale 1ns/1ps
// Replay actual NEBULA resources and descriptors through the real scanout.
// The Python reference writes post-raster memory and independent RGB666 pixels.
module nebula_scanout_tb #(parameter WIDTH=800,HEIGHT=480,H_TOTAL=1193,V_TOTAL=533,H_START=182,V_START=8,H_SYNC=210,V_SYNC=45,parameter realtime HALF_PIXEL=14.285);
    reg hc=0,pc=0,mc=0,rst=0;
    always #6.25 hc=~hc;
    always #(HALF_PIXEL) pc=~pc;
    always #6.666 mc=~mc;
    reg sel=0,wr=0;
    reg [31:0] addr=0,data=0;
    reg [1:0] trans=0;
    wire [31:0] result;
    wire ready,fv,de,hs,vs;
    wire [28:0] fa;
    reg fr=0,fdv=0;
    reg [255:0] fd=0;
    wire [5:0] r,g,b;
    gpu_scanout #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.H_TOTAL(H_TOTAL),.V_TOTAL(V_TOTAL),.H_START(H_START),.V_START(V_START),.H_SYNC(H_SYNC),.V_SYNC(V_SYNC)) dut(.hclk(hc),.hresetn(rst),.hsel(sel),.hwrite(wr),.haddr(addr),
        .hwdata(data),.htrans(trans),.hrdata(result),.hready(ready),.pixel_clk(pc),
        .mem_clk(mc),.fetch_valid(fv),.fetch_addr(fa),.fetch_ready(fr),
        .fetch_data(fd),.fetch_data_valid(fdv),.lcd_en(de),.lcd_hs(hs),.lcd_vs(vs),
        .lcd_r(r),.lcd_g(g),.lcd_b(b));
    byte unsigned memory[0:14*1024*1024-1];
    reg [31:0] scene[0:391],palette[0:255];
    reg [17:0] expected[0:WIDTH*HEIGHT-1];
    string directory;
    integer f,n,addresses[$],due[$],cycle=0,last_due=0;
    always @(negedge mc) begin
        cycle++;fr=rst && cycle%7!=0;fdv=0;
        if(due.size()>0 && due[0]<=cycle)begin
            automatic integer at=addresses.pop_front();
            void'(due.pop_front());
            if(at<'h800000 || at+32>'h800000+14*1024*1024)$fatal(1,"Invalid DDR read %h",at);
            for(integer i=0;i<32;i++)fd[i*8+:8]=memory[at-'h800000+i];
            fdv=1;
        end
    end
    always @(posedge mc)if(rst && fv && fr)begin
        addresses.push_back(int'(fa)*4);
        last_due=cycle+32>last_due ? cycle+32:last_due+1;due.push_back(last_due);
    end
    task automatic write_reg(input [31:0] a,input [31:0] d);
        @(negedge hc);sel=1;wr=1;trans=2;addr=a;
        do @(posedge hc);while(!ready);
        @(negedge hc);sel=0;trans=0;data=d;
        do @(posedge hc);while(!ready);
        @(negedge hc);wr=0;
    endtask
    integer frames=0,pixels=0,bad=0;
    reg previous_vs=1;
    reg [31:0] checksum=0;
    always @(negedge pc)begin
        if(!vs && previous_vs)begin
            if(frames==4)begin
                if(pixels!=WIDTH*HEIGHT)$fatal(1,"Pixel count %0d",pixels);
                $display("NEBULA_SCANOUT pixels=%0d mismatches=%0d sum=%h underflows=%0d",pixels,bad,checksum,dut.r_underflows);
                if(bad || dut.r_underflows)$fatal(1,"Scanout reference mismatch");
                $finish;
            end
            frames++;pixels=0;checksum=0;bad=0;
        end
        if(de && frames==4)begin
            if(pixels>=WIDTH*HEIGHT)$fatal(1,"Too many pixels");
            if({r,g,b}!==expected[pixels])begin
                if(bad<20)$display("MISMATCH x=%0d y=%0d actual=%h expected=%h",pixels%WIDTH,pixels/WIDTH,{r,g,b},expected[pixels]);
                bad++;
            end
            checksum+={14'd0,r,g,b};pixels++;
        end
        previous_vs=vs;
    end
    initial begin
        if(!$value$plusargs("inputs=%s",directory))$fatal(1,"Missing +inputs");
        f=$fopen({directory,"/memory.bin"},"rb");if(!f)$fatal(1,"Missing memory");
        n=$fread(memory,f);$fclose(f);if(n<3*1024*1024)$fatal(1,"Short memory");
        $readmemh({directory,"/scene.hex"},scene);
        $readmemh({directory,"/palette.hex"},palette);
        $readmemh({directory,"/expected.hex"},expected);
        #200;rst=1;
        for(integer i=0;i<256;i++)write_reg('h400+i*4,palette[i]);
        for(integer i=0;i<128;i++)write_reg('h800+i*4,scene[8+i]);
        for(integer i=0;i<256;i++)write_reg('hc00+i*4,scene[136+i]);
        write_reg('h40,scene[4]);write_reg(4,scene[0]);write_reg('h30,scene[3]);
        write_reg('h6c,scene[1]);write_reg(8,scene[2]);write_reg(12,1);
    end
    initial begin #150000000;$fatal(1,"Timeout");end
endmodule
