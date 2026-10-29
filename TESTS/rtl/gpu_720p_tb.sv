`timescale 1ns/1ps
// Full-frame independent reference: bit 10 of X, bit 9 of Y, misaligned
// 41-burst surface, tiles, cached sprites and RGB x2; asynchronous clocks.
module gpu_720p_tb #(parameter REQUEST_QUEUE=0);
    reg hc=0,pc=0,mc=0,rst=0;
    always #6.25 hc=~hc;
    always #6.722689 pc=~pc;
    always #6.666667 mc=~mc;
    reg sel=0,wr=0;
    reg [31:0] addr=0,data=0;
    reg [1:0] trans=0;
    wire [31:0] result;
    wire ready,fv,de,hs,vs;
    wire [28:0] fa;
    reg fr=0,fdv=0;
    reg [255:0] fd=0;
    wire [5:0] r,g,b;
    wire sfv,sfr;
    wire [28:0] sfa;
    generate if (REQUEST_QUEUE) begin:g_queue
        neo_scan_queue q(.clk(mc),.resetn(rst),.in_valid(sfv),.in_addr(sfa),.in_ready(sfr),
                         .out_valid(fv),.out_addr(fa),.out_ready(fr));
    end else begin:g_direct
        assign fv=sfv;assign fa=sfa;assign sfr=fr;
    end endgenerate
    gpu_scanout #(.WIDTH(1280),.HEIGHT(720),.H_TOTAL(1650),.V_TOTAL(750),
        .H_START(260),.V_START(25),.H_SYNC(40),.V_SYNC(5)) dut(
        .hclk(hc),.hresetn(rst),.hsel(sel),.hwrite(wr),.haddr(addr),.hwdata(data),
        .htrans(trans),.hrdata(result),.hready(ready),.pixel_clk(pc),.mem_clk(mc),
        .fetch_valid(sfv),.fetch_addr(sfa),.fetch_ready(sfr),.fetch_data(fd),.fetch_data_valid(fdv),
        .lcd_en(de),.lcd_hs(hs),.lcd_vs(vs),.lcd_r(r),.lcd_g(g),.lcd_b(b));
    byte unsigned memory[0:4*1024*1024-1];
    integer mode=0,addresses[$],due[$],cycle=0,last_due=0;
    function automatic [7:0] index_pixel(input integer x,y);
        return 8'((x*3+y*7+(x>>10)*19+(y>>9)*53)%239+1);
    endfunction
    function automatic [17:0] colour(input integer i);
        return {6'(i),6'(i*3),6'(i*7)};
    endfunction
    function automatic [15:0] pixel565(input integer x,y);
        return {5'(x+y),6'(x/3+y/5),5'(x/7+y/3)};
    endfunction
    function automatic [17:0] reference(input integer x,y);
        reg [15:0] p;
        reg [7:0] i;
        if(mode==0) reference=colour(index_pixel(x,y));
        else if(mode==5)reference=colour(((x^y)&1) ? ((x/8+y)%238+1):239);
        else if(mode==1 || mode==2 || mode==4)begin
            p=pixel565(mode==2 ? x/2:x,mode==2 ? y/2:y);
            reference={p[15:11],p[15],p[10:5],p[4:0],p[4]};
        end else begin
            // Entire unaligned surface, then a 1280-pixel 8x8 tile band,
            // finally a sprite at the bottom-right corner above row 511.
            i=index_pixel(x+34,y);
            if(y>=640 && y<664)i=8'((x/8+y-640)%238+1);
            if(x>=1255 && y>=695)i=8'(200+(x-1255)%20);
            reference=colour(i);
        end
    endfunction
    always @(negedge mc) begin
        cycle++;fr=rst && cycle%7!=0;fdv=0;
        if(due.size()>0 && due[0]<=cycle)begin
            automatic integer at=addresses.pop_front();
            void'(due.pop_front());
            if(at<'h800000 || at+32>'h800000+4*1024*1024)$fatal(1,"DDR read out of range %h",at);
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
    task automatic layer(input integer n,input [31:0] a,b,c,d,e,f,g);
        write_reg('h800+n*32,a);write_reg('h804+n*32,b);write_reg('h808+n*32,c);
        write_reg('h80c+n*32,d);write_reg('h810+n*32,e);write_reg('h814+n*32,f);
        write_reg('h818+n*32,g);write_reg('h81c+n*32,0);
    endtask
    integer frames=0,pixels=0,bad=0;
    reg previous_vs=1;
    always @(negedge pc)begin
        if(!vs && previous_vs)begin
            if(frames==4)begin
                $display("GPU_720P mode=%0d pixels=%0d mismatches=%0d uf=%0d line_cycles=%0d",mode,pixels,bad,dut.r_underflows,dut.r_total_cycles);
                if(pixels!=1280*720 || bad || dut.r_underflows || dut.r_invalid_layers || dut.r_invalid_sprites)$fatal(1,"Scanout mismatch");
                $finish;
            end
            frames++;pixels=0;bad=0;
        end
        if(de && frames==4)begin
            if(pixels>=1280*720)$fatal(1,"Too many pixels");
            if({r,g,b}!==reference(pixels%1280,pixels/1280))begin
                if(bad<8)$display("MISMATCH %0d,%0d actual=%h expected=%h",pixels%1280,pixels/1280,{r,g,b},reference(pixels%1280,pixels/1280));
                bad++;
            end
            pixels++;
        end
        previous_vs=vs;
    end
    initial begin
        void'($value$plusargs("mode=%d",mode));
        for(integer y=0;y<720;y++)for(integer x=0;x<1280;x++)begin
            automatic reg[15:0] pix=pixel565(x,y);
            if(mode==0)memory[y*1280+x]=index_pixel(x,y);
            else begin memory[y*2560+x*2]=pix[7:0];memory[y*2560+x*2+1]=pix[15:8];end
        end
        if(mode==3)begin
            for(integer y=0;y<720;y++)for(integer x=0;x<1344;x++)memory[y*1344+x]=index_pixel(x,y);
            for(integer y=0;y<4;y++)for(integer x=0;x<256;x++)begin
                automatic integer tile=(x+y*8)%238;
                memory['h200000+(y*256+x)*2]=8'(tile);memory['h200000+(y*256+x)*2+1]=0;
            end
            for(integer t=0;t<238;t++)for(integer y=0;y<8;y++)for(integer x=0;x<8;x++)
                memory['h220000+t*64+y*8+x]=8'((t+y)%238+1);
            for(integer y=0;y<32;y++)for(integer x=0;x<32;x++)memory['h300000+y*32+x]=8'(200+x%20);
        end
        if(mode==5)begin
            for(integer y=0;y<128;y++)for(integer x=0;x<256;x++)begin
                memory['h200000+(y*256+x)*2]=0;memory['h200000+(y*256+x)*2+1]=0;
                memory['h220000+(y*256+x)*2]=8'((x+y*8)%238);memory['h220000+(y*256+x)*2+1]=0;
            end
            for(integer i=0;i<64;i++)memory['h210000+i]=239;
            for(integer t=0;t<238;t++)for(integer y=0;y<8;y++)for(integer x=0;x<8;x++)
                memory['h230000+t*64+y*8+x]=((x^y)&1) ? 8'((t+y)%238+1):0;
        end
        #200;rst=1;
        for(integer i=0;i<256;i++)write_reg('h400+i*4,{14'd0,colour(i)});
        for(integer i=0;i<128;i++)write_reg('h800+i*4,0);
        for(integer i=0;i<256;i++)write_reg('hc00+i*4,0);
        if(mode==3)begin
            layer(0,'h800000,(720<<16)|1344,16'hfffd,(720<<16)|1283,31,1344,1);
            layer(1,'ha00000,'ha20000,640<<16,(24<<16)|1280,0,'h28,5);
            write_reg('hc00,'hb00000);write_reg('hc04,(695<<16)|1255);
            write_reg('hc08,(1<<20)|(1<<16)|(32<<8)|32);
        end
        if(mode==5)begin
            layer(12,'ha00000,'ha10000,0,(720<<16)|1280,0,'h78,5);
            layer(13,'ha20000,'ha30000,0,(720<<16)|1280,0,'h78,7);
        end
        write_reg('h40,mode==3);write_reg(4,'h800000);write_reg('h30,mode!=0 && mode!=4);
        write_reg('h6c,mode==0 ? 1280:2560);write_reg(8,(mode==1 || mode==4 || mode==5) ? 3:mode==2 ? 7:1);write_reg(12,1);
    end
    initial begin #100000000;$fatal(1,"Timeout");end
endmodule
