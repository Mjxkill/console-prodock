`timescale 1ns/1ps
module gpu_layers_tb #(parameter W=64,H=32,HT=1193,VT=48,HSTART=182,VSTART=8,LATENCY=32,SPRITES=0,TILES=0);
    reg hc=0,pc=0,mc=0,rst=0;
    always #6.25 hc=~hc;
    always #14.285 pc=~pc;
    always #6.666 mc=~mc;
    reg sel=0,wr=0;
    reg [31:0] addr=0,data=0;
    reg [1:0] trans=0;
    wire [31:0] result;
    wire ready,fv,fr,fdv,de,hs,vs;
    wire [28:0] fa;
    wire [255:0] fd;
    wire [5:0] r,g,b;
    gpu_scanout #(.WIDTH(W),.HEIGHT(H),.H_TOTAL(HT),.V_TOTAL(VT),.H_START(HSTART),.V_START(VSTART),.H_SYNC(20),.V_SYNC(2)) dut (
        .hclk(hc),.hresetn(rst),.hsel(sel),.hwrite(wr),.haddr(addr),.hwdata(data),.htrans(trans),.hrdata(result),.hready(ready),
        .pixel_clk(pc),.mem_clk(mc),.fetch_valid(fv),.fetch_addr(fa),.fetch_ready(fr),.fetch_data(fd),.fetch_data_valid(fdv),
        .lcd_en(de),.lcd_hs(hs),.lcd_vs(vs),.lcd_r(r),.lcd_g(g),.lcd_b(b));

    // L11 tile layers. Poses 7 and up; fields of one tile layer of a pose.
    localparam MAPS='h3000000,ATLAS='h4000000,POSES=11;
    localparam T_USED=0,T_CODE=1,T_WLOG=2,T_HLOG=3,T_X=4,T_Y=5,T_VW=6,T_VH=7,T_SX=8,T_SY=9,T_FLAGS=10,T_MAP=11,T_ATLAS=12;
    function automatic integer tile_field(input integer pose,input integer layer,input integer field);
        integer v[13];
        for(integer i=0;i<13;i++) v[i]=0;
        v[T_MAP]=MAPS+layer*'h100000;v[T_ATLAS]=ATLAS;v[T_VW]=W;v[T_VH]=H;v[T_FLAGS]=5;
        if(pose==7) case(layer)
            // Opaque 16x16 background, unaligned scroll, map larger than the screen.
            0:begin v[T_USED]=1;v[T_CODE]=1;v[T_WLOG]=6;v[T_HLOG]=5;v[T_SX]=5;v[T_SY]=7;end
            // 8x8, tiny map wrapped many times on both axes, scroll beyond the map.
            4:begin v[T_USED]=1;v[T_CODE]=0;v[T_WLOG]=4;v[T_HLOG]=4;v[T_SX]=1000;v[T_SY]=300;
                    v[T_X]=-3;v[T_Y]=2;v[T_VW]=W+3;v[T_FLAGS]=5+2+8+16;end
            // 32x32, no wrap: only the last map pixels remain, then nothing.
            5:begin v[T_USED]=1;v[T_CODE]=2;v[T_WLOG]=5;v[T_HLOG]=4;v[T_SX]=1024-W/2-3;v[T_SY]=512-H/2-5;
                    v[T_FLAGS]=5+2;end
            // 16x16, wrap X only, window inside the screen, scroll above 32767.
            6:begin v[T_USED]=1;v[T_CODE]=1;v[T_WLOG]=5;v[T_HLOG]=6;v[T_SX]=40001;v[T_SY]=3;
                    v[T_X]=W/4+1;v[T_Y]=H/4;v[T_VW]=W/2;v[T_VH]=H/2;v[T_FLAGS]=5+2+8;end
            // Negative position, window wider than the screen, wrap Y only.
            9:begin v[T_USED]=1;v[T_CODE]=0;v[T_WLOG]=8;v[T_HLOG]=4;v[T_SX]=11;v[T_SY]=65533;
                    v[T_X]=-37;v[T_Y]=-5;v[T_VW]=W+90;v[T_VH]=H+9;v[T_FLAGS]=5+2+16;end
            default:begin end
        endcase
        // Line budget: full-screen tile layers of each size under surfaces.
        if(pose==8 && layer<4) begin
            v[T_USED]=1;v[T_CODE]=layer==3 ? 2 : layer==2 ? 0 : 1;v[T_WLOG]=7;v[T_HLOG]=6;
            v[T_SX]=layer*21+9;v[T_SY]=layer*13+3;v[T_FLAGS]=layer==0 ? 5 : 5+2+8+16;
        end
        // Every rejection: bases, size code, width, pixel extent, end of DDR.
        if(pose==9 && layer<8) begin
            v[T_USED]=1;v[T_CODE]=1;v[T_WLOG]=6;v[T_HLOG]=5;
            case(layer)
                0:v[T_MAP]=MAPS+16;
                1:v[T_ATLAS]=ATLAS+8;
                2:v[T_CODE]=3;
                3:v[T_WLOG]=3;
                4:begin v[T_CODE]=2;v[T_WLOG]=11;end
                5:begin v[T_CODE]=0;v[T_HLOG]=13;end
                6:v[T_MAP]='h3ffff020; // last map byte just beyond the first GiB
                7:v[T_ATLAS]='h3ff00000;
            endcase
        end
        return v[field];
    endfunction
    function automatic [15:0] map_entry(input integer index);
        return 16'(((index*37+(index>>5)*11)%8192) | ((index%3==1) ? 'h4000 : 0) | ((index%5==2) ? 'h8000 : 0));
    endfunction
    function automatic [31:0] descriptor(input integer pose,input integer layer,input integer word);
        integer page,x,y,sx,sy,vw,vh,flags;
        if(pose>=7 && tile_field(pose,layer,T_USED)) case(word)
            0:return tile_field(pose,layer,T_MAP);
            1:return tile_field(pose,layer,T_ATLAS);
            2:return ((tile_field(pose,layer,T_Y)&65535)<<16)|(tile_field(pose,layer,T_X)&65535);
            3:return ((tile_field(pose,layer,T_VH)&65535)<<16)|(tile_field(pose,layer,T_VW)&65535);
            4:return ((tile_field(pose,layer,T_SY)&65535)<<16)|(tile_field(pose,layer,T_SX)&65535);
            5:return tile_field(pose,layer,T_WLOG)|(tile_field(pose,layer,T_HLOG)<<4)|(tile_field(pose,layer,T_CODE)<<8);
            6:return tile_field(pose,layer,T_FLAGS);
            default:return 0;
        endcase
        if(pose==7) return word==6 ? (layer>=1 && layer<=3 ? 3 : 0) : descriptor(0,layer,word);
        if(pose==8) return word==6 ? (layer<4+TILES ? 3 : 0) : descriptor(0,layer,word);
        if(pose==9) return word==6 ? 0 : descriptor(0,layer,word);
        if(pose==10) return descriptor(0,layer,word);
        page=pose==1 ? 15-layer : layer;
        x=pose==1 ? layer*5-37 : 0;y=pose==1 ? layer%5-2 : 0;
        sx=pose==1 ? 31-layer : 0;sy=pose==1 ? layer%4 : 0;
        vw=pose==1 ? W+15-layer*2 : W;vh=pose==1 ? H+4-layer%7 : H;
        flags=(pose==2 || pose==4 || pose==5) ? 0 : layer==0 || (pose==1 && layer%5==0) ? 1 : 3;
        // Both source and destination clipping; all 16 source alignments vary.
        case(word)
            0:return 'h800000+(page<<20)+page*2+1;
            1:return ((H+10)<<16)|(W+20);
            2:return ((y&65535)<<16)|(x&65535);
            3:return ((vh&65535)<<16)|(vw&65535);
            4:return ((sy&65535)<<16)|(sx&65535);
            5:return W+32+page%5;
            6:return flags;
            default:return 0;
        endcase
    endfunction
    function automatic [31:0] sprite_descriptor(input integer pose,input integer slot,input integer word);
        integer x,y,w,h,flags,priority_layer,base;
        w=(pose==4 || pose==6) ? 32 : (slot%3==0 ? 8 : slot%3==1 ? 16 : 32);h=w;
        if(pose==1) case(slot%8)
            0:begin w=1;h=31;end
            1:begin w=17;h=7;end
            2:begin w=31;h=1;end
            3:begin w=9;h=23;end
        endcase
        x=(pose==4 || pose==6) ? (slot%16)*(W/16)-3 : (slot%8)*(W/8)+(slot%2 ? -7 : 5);
        y=(pose==4 || pose==6) ? 16 : (slot/8)*(H/8)-4;
        if(slot==63 && pose!=4 && pose!=6) x=W-4;
        if(pose==1) begin x-=3;y+=2;end
        flags=1|((slot+pose)%4<<1);priority_layer=(slot*7+pose*3)%16;
        base='h2000000+slot*1024+(pose==1 ? 65536 : 0);
        if(pose==2 || pose==3 || (pose==5 && slot>=5)) flags=0;
        if(pose==5) case(slot)
            0:base+=1;
            1:w=33;
            2:h=0;
            3:base='h40000000;
            4:begin base='h3fffffe0;h=2;end
        endcase
        case(word)
            0:return base;
            1:return ((y&65535)<<16)|(x&65535);
            2:return w|(h<<8)|(flags<<16)|(priority_layer<<20);
            default:return 0;
        endcase
    endfunction
    function automatic [7:0] pixel(input integer address);
        integer page,offset,x,y;
        if(address>=MAPS && address<MAPS+'h1000000)
            return 8'(map_entry((address-MAPS)%'h100000/2)>>(address%2 ? 8 : 0));
        if(address>=ATLAS && address<ATLAS+'h800000)
            return ((address>>3)%5==0 || address%13==0) ? 0 : 8'(1+(address*7+(address>>8)*29+(address>>15)*3)%255);
        if(address>='h2000000 && address<'h2020000) return (address%7==0 || address%11==0) ? 0 : 8'(1+(address*13+(address>>10)*19+(address>>16))%255);
        if(address<'h800000) return 8'((address*73)^(address>>7));
        page=(address>>20)-8;offset=(address&'hfffff)-(page*2+1);
        if(page<0 || page>15) $fatal(1,"Read outside surface slots @%h",address);
        x=offset%(W+32+page%5);y=offset/(W+32+page%5);
        if(offset<0 || x>=W+20 || y>=H+10) return 8'h5a;
        return x%16==page ? 8'(((y*17+x+page*31)&254)|1) : 0;
    endfunction
    function automatic [255:0] burst(input integer a);
        reg [255:0] v;
        for(integer i=0;i<32;i++) v[i*8+:8]=pixel(a+i);
        return v;
    endfunction
    reg [7:0] expected_image[0:POSES-1][0:H-1][0:W-1];
    // Independent tile painter: one map lookup and one atlas byte per pixel.
    // No bursts, word assembly, request order or pipeline of the hardware.
    task automatic reference_tiles(input integer pose,input integer l);
        integer t,size,wt,wpx,hpx,flags,mx,my,dx,dy,tx,ty,index;
        reg [15:0] entry;
        reg [7:0] value;
        t=tile_field(pose,l,T_CODE)+3;size=1<<t;flags=tile_field(pose,l,T_FLAGS);
        wt=1<<tile_field(pose,l,T_WLOG);wpx=wt*size;hpx=(1<<tile_field(pose,l,T_HLOG))*size;
        if(pose==9) return; // every descriptor of this pose is invalid
        for(integer y=0;y<H;y++) for(integer x=0;x<W;x++) begin
            dx=x-tile_field(pose,l,T_X);dy=y-tile_field(pose,l,T_Y);
            mx=tile_field(pose,l,T_SX)+dx;my=tile_field(pose,l,T_SY)+dy;
            if(flags&8) mx=(tile_field(pose,l,T_SX)%wpx+dx)%wpx;
            if(flags&16) my=(tile_field(pose,l,T_SY)%hpx+dy)%hpx;
            if(dx>=0 && dy>=0 && dx<tile_field(pose,l,T_VW) && dy<tile_field(pose,l,T_VH) && mx<wpx && my<hpx) begin
                index=(my>>t)*wt+(mx>>t);entry=map_entry(index);
                tx=mx%size;ty=my%size;
                if(entry[14]) tx=size-1-tx;
                if(entry[15]) ty=size-1-ty;
                value=pixel(tile_field(pose,l,T_ATLAS)+(entry&8191)*size*size+ty*size+tx);
                if(!(flags&2) || value!=0) expected_image[pose][y][x]=value;
            end
        end
    endtask
    // Independent software painter: visit each layer, then the bounded sprite
    // rectangles above it. No cache, burst alignment or linked-list machinery.
    task automatic reference_scene(input integer pose);
        integer dx,dy,sx,sy,vw,vh,sw,sh,flags,a,stride,prop,xx,yy,ww,hh,x0,y0;
        reg [7:0] value;
        for(integer y=0;y<H;y++) for(integer x=0;x<W;x++)
            expected_image[pose][y][x]=pose==3 ? pixel('h800000+y*W+x) : 0;
        if(pose==3) return;
        for(integer l=0;l<16;l++) begin
            a=descriptor(pose,l,0);stride=descriptor(pose,l,5);flags=descriptor(pose,l,6);
            x0=int'(shortint'(descriptor(pose,l,2)));y0=int'(shortint'(descriptor(pose,l,2)>>16));
            vw=descriptor(pose,l,3)&65535;vh=descriptor(pose,l,3)>>16;
            sw=descriptor(pose,l,1)&65535;sh=descriptor(pose,l,1)>>16;
            if(pose>=7 && tile_field(pose,l,T_USED)) reference_tiles(pose,l);
            else if(flags&1) for(integer y=0;y<H;y++) for(integer x=0;x<W;x++) begin
                dx=x-x0;dy=y-y0;
                sx=(descriptor(pose,l,4)&65535)+dx;sy=(descriptor(pose,l,4)>>16)+dy;
                if(dx>=0 && dy>=0 && dx<vw && dy<vh && sx>=0 && sy>=0 && sx<sw && sy<sh) begin
                    value=pixel(a+sy*stride+sx);
                    if(!(flags&2) || value!=0) expected_image[pose][y][x]=value;
                end
            end
            if(SPRITES && pose!=5) for(integer sp=0;sp<64;sp++) begin
                prop=sprite_descriptor(pose,sp,2);ww=prop&255;hh=(prop>>8)&255;
                x0=int'(shortint'(sprite_descriptor(pose,sp,1)));y0=int'(shortint'(sprite_descriptor(pose,sp,1)>>16));
                if((prop&65536) && ((prop>>20)&15)==l) for(integer y=0;y<hh;y++) for(integer x=0;x<ww;x++) begin
                    xx=(prop&131072) ? ww-1-x : x;yy=(prop&262144) ? hh-1-y : y;
                    value=pixel(sprite_descriptor(pose,sp,0)+yy*32+xx);
                    if(x+x0>=0 && x+x0<W && y+y0>=0 && y+y0<H && value!=0)
                        expected_image[pose][y+y0][x+x0]=value;
                end
            end
        end
    endtask
    initial for(integer pose=0;pose<(TILES ? POSES : 7);pose++) reference_scene(pose);
    function automatic [17:0] color(input [7:0] p);
        return {p[5:0],p[7:2],p[5:0]^6'h15};
    endfunction
    function automatic [31:0] rot(input [31:0] v,input integer n);
        return (v<<n)|(v>>(32-n));
    endfunction
    function automatic [31:0] frame_hash(input integer pose);
        reg [31:0] hash,word,block_hash;
        hash=0;
        for(integer yy=0;yy<H;yy++) for(integer xx=0;xx<W;xx+=32) begin
            block_hash=0;
            for(integer w=0;w<8;w++) begin
                for(integer lane=0;lane<4;lane++) word[lane*8+:8]=expected_image[pose][yy][xx+w*4+lane];
                block_hash^=rot(word,w*4);
            end
            hash=rot(hash,5)^block_hash;
        end
        return hash;
    endfunction

    wire cr,cv;
    wire [255:0] cd;
    reg cpu_pending=0;
    reg [28:0] cpu_addr=29'h400;
    wire me,mwe,mwend;
    wire [2:0] cmd;
    wire [28:0] ma;
    wire [255:0] wd;
    wire [31:0] wm;
    reg mr=0,rv=0,stalled=0;
    reg [255:0] rd=0;
    ddr_gpu_arb arb (
        .clk(mc),.rst_n(rst),.c_en(cr && !cpu_pending),.c_cmd(3'b001),.c_addr(cpu_addr),.c_ready(cr),
        .c_wr_en(1'b0),.c_wr_end(1'b0),.c_wr_data(256'd0),.c_wr_mask(32'hffffffff),.c_wr_ready(),.c_rd_data(cd),.c_rd_valid(cv),.c_rd_end(),
        .g_valid(fv),.g_addr(fa),.g_ready(fr),.g_data(fd),.g_data_valid(fdv),
        .b_valid(1'b0),.b_write(1'b0),.b_addr(29'd0),.b_wr_data(256'd0),.b_wr_mask(32'hffffffff),.b_ready(),.b_rd_data(),.b_rd_valid(),
        .m_en(me),.m_cmd(cmd),.m_addr(ma),.m_ready(mr),.m_wr_en(mwe),.m_wr_end(mwend),.m_wr_data(wd),.m_wr_mask(wm),
        .m_wr_ready(mr),.m_rd_data(rd),.m_rd_valid(rv),.m_rd_end(rv));
    integer addresses[$],due[$],cycle=0,last_due=0,cpureads=0,read_counts[16];
    always @(negedge mc) begin
        cycle++;mr=rst && !stalled && cycle%7!=0;rv=0;
        if(due.size()>0 && due[0]<=cycle && !stalled) begin
            rd=burst(addresses.pop_front());rv=1;void'(due.pop_front());
        end
    end
    always @(posedge mc) if(rst) begin
        if(me && mr) begin
            if(cmd!=1 || ma[2:0]!=0) $fatal(1,"Invalid read");
            addresses.push_back(int'(ma)*4);
            last_due=cycle+LATENCY+cycle%11>last_due ? cycle+LATENCY+cycle%11 : last_due+1;due.push_back(last_due);
            if(int'(ma)*4>='h800000 && int'(ma)*4<'h1800000) read_counts[((int'(ma)*4)>>20)-8]++;
        end
        if(cr && !cpu_pending) cpu_pending<=1;
        if(cv) begin
            if(!cpu_pending || cd!==burst(int'(cpu_addr)*4)) $fatal(1,"CPU data/tag");
            cpu_pending<=0;cpu_addr<=cpu_addr==29'h3fff8 ? 29'h400 : cpu_addr+8;cpureads++;
        end
    end
    integer ahb_stalls=0;
    task automatic write_reg(input [31:0] a,input [31:0] d);
        @(negedge hc);sel=1;wr=1;trans=2;addr=a;
        do @(posedge hc);while(!ready);
        @(negedge hc);sel=0;trans=0;data=d;
        do begin @(posedge hc);if(!ready) ahb_stalls++;end while(!ready);
        @(negedge hc);wr=0;
    endtask
    task automatic read_reg(input [31:0] a,output [31:0] d);
        @(negedge hc);sel=1;wr=0;trans=2;addr=a;
        @(posedge hc);@(negedge hc);sel=0;trans=0;d=result;
    endtask
    integer expected_pose=0,selected_pose=0,checked_frames=0,col=0,row=0;
    reg prev_vs=1,prev_de=0,check_pixels=0,skip_pixels=0;
    always @(negedge pc) begin
        if(!vs && prev_vs) begin
            if(check_pixels && row!=H) $fatal(1,"Wrong line count");
            row=0;col=0;selected_pose=expected_pose;
            check_pixels=rst && dut.active_enable && !skip_pixels;
            if(check_pixels) checked_frames++;
        end
        if(de && check_pixels) begin
            if({r,g,b}!==color(expected_image[selected_pose][row][col]))
                $fatal(1,"Pose%0d pixel %0d,%0d got=%h expected=%h",selected_pose,col,row,{r,g,b},color(expected_image[selected_pose][row][col]));
            col++;
        end
        if(!de && prev_de) begin
            if(check_pixels && col!=W) $fatal(1,"Wrong pixel count");
            row++;col=0;
        end
        prev_vs=vs;prev_de=de;
    end
    // The max_cycles register keeps its maximum since reset; measure a scene.
    integer scene_max=0;
    // The reader latches its maximum one cycle before it leaves FINISH.
    always @(posedge mc) if(dut.reader_done && dut.u_reader.elapsed-1>scene_max) scene_max=dut.u_reader.elapsed-1;
    task automatic submit_pose(input integer pose);
        for(integer l=0;l<16;l++) for(integer w=0;w<8;w++) write_reg('h800+l*32+w*4,descriptor(pose,l,w));
        if(SPRITES) for(integer sp=0;sp<64;sp++) for(integer w=0;w<4;w++) write_reg('hc00+sp*16+w*4,sprite_descriptor(pose,sp,w));
        write_reg('h40,SPRITES && pose!=2);
        write_reg('h30,1);write_reg(8,1);write_reg(12,1);
        do read_reg(12,value);while(value!=0);
        expected_pose=pose;scene_max=0;
    endtask
    reg [31:0] value;
    integer goal_frames,underflow_before,invalid_before;
    initial begin
        #200;rst=1;
        read_reg('h28,value);if(value!=16) $fatal(1,"Missing 16-layer capability");
        for(integer i=0;i<256;i++) write_reg('h400+i*4,{14'b0,color(8'(i))});
        submit_pose(0);
        wait(checked_frames>=3);@(negedge vs);
        read_reg('h1c,value);if(value!=0) $fatal(1,"16 full surfaces underflowed");
        read_reg('h20,value);if(value!=frame_hash(0)) $fatal(1,"Initial frame hash %h vs %h",value,frame_hash(0));
        read_reg('h2c,value);if(value>=HT*75/35) $fatal(1,"Exceeded line budget: %0d cycles",value);
        $display("16 full surfaces: max line %0d/%0d DDR cycles",value,HT*75/35);
        for(integer l=0;l<16;l++) if(read_counts[l]<H*(W/32)*2) $fatal(1,"Layer %0d not read",l);
        wait(de);submit_pose(1);goal_frames=checked_frames+3;
        wait(checked_frames>=goal_frames);@(negedge vs);
        read_reg('h20,value);if(value!=frame_hash(1)) $fatal(1,"Clipped/shifted frame hash");
        read_reg('h38,value);if(value!=0) $fatal(1,"Unexpected invalid descriptors");
        if(SPRITES) begin
            read_reg('h48,value);if(value!=0) $fatal(1,"Valid sprites rejected");
            read_reg('h4c,value);if(value==0) $fatal(1,"No sprites composed");
            read_reg('h50,value);$display("Sprite cache: max prefetch %0d DDR cycles",value);
            submit_pose(4);goal_frames=checked_frames+3;
            wait(checked_frames>=goal_frames);@(negedge vs);
            read_reg('h20,value);if(value!=frame_hash(4)) $fatal(1,"64 sprites frame hash");
            read_reg('h4c,value);if(value!=64) $fatal(1,"64 sprites on the same line not supported");
            read_reg('h1c,value);if(value!=0) $fatal(1,"Sprites underflowed");
            read_reg('h2c,value);$display("G4 max line %0d/%0d DDR cycles",value,HT*75/35);
            submit_pose(5);goal_frames=checked_frames+3;
            wait(checked_frames>=goal_frames);@(negedge vs);
            read_reg('h20,value);if(value!=0) $fatal(1,"Invalid sprites produced pixels");
            read_reg('h48,value);if(value<5) $fatal(1,"Invalid sprites not reported");
            if(W==800) begin
                // Deliberate overload: 16 full layers AND 64 sprites on one
                // line. Capacity is 64; the finite line deadline still applies.
                skip_pixels=1;read_reg('h1c,underflow_before);submit_pose(6);
                repeat(3) @(negedge vs);
                read_reg('h1c,value);if(value<=underflow_before) $fatal(1,"Missing sprite overload report");
                read_reg('h2c,value);$display("Deliberate 16-layer + 64-sprite overload: %0d/%0d DDR cycles, reported",value,HT*75/35);
            end
            submit_pose(1);repeat(2) @(negedge vs);skip_pixels=0;
            goal_frames=checked_frames+3;wait(checked_frames>=goal_frames);@(negedge vs);
        end
        if(TILES) begin
            read_reg('h5c,value);if(value!='h00000d07) $fatal(1,"Missing tile layer capability");
            // Both counters are cumulative; the overload above was deliberate.
            read_reg('h38,invalid_before);read_reg('h1c,underflow_before);
            submit_pose(7);goal_frames=checked_frames+3;
            wait(checked_frames>=goal_frames);@(negedge vs);
            read_reg('h20,value);if(value!=frame_hash(7)) $fatal(1,"Tile layers frame hash");
            read_reg('h38,value);if(value!=invalid_before) $fatal(1,"Valid tile layers rejected");
            read_reg('h1c,value);if(value!=underflow_before) $fatal(1,"Tile layers underflowed");
            $display("L11 5 tile layers, 3 surfaces, sprites: max line %0d/%0d DDR cycles",scene_max,HT*75/35);
            submit_pose(10);goal_frames=checked_frames+2;
            wait(checked_frames>=goal_frames);@(negedge vs);
            submit_pose(8);goal_frames=checked_frames+3;
            wait(checked_frames>=goal_frames);@(negedge vs);
            read_reg('h20,value);if(value!=frame_hash(8)) $fatal(1,"Tile budget frame hash");
            read_reg('h1c,value);if(value!=underflow_before) $fatal(1,"Tile budget scene underflowed");
            $display("L11 4 full tile layers (16,16,8,32), %0d full surfaces, sprites: max line %0d/%0d DDR cycles",TILES,scene_max,HT*75/35);
            // A write to 0x02c restarts the maxima: the register then holds
            // this scene, not the largest load since reset.
            write_reg('h2c,0);scene_max=0;repeat(2) @(negedge vs);
            read_reg('h2c,value);if(value==0 || value!=scene_max) $fatal(1,"Restarted maximum %0d, scene %0d",value,scene_max);
            submit_pose(9);goal_frames=checked_frames+3;
            wait(checked_frames>=goal_frames);@(negedge vs);
            read_reg('h20,value);if(value!=frame_hash(9)) $fatal(1,"Invalid tile layers produced pixels");
            read_reg('h38,value);if(value<invalid_before+8*H) $fatal(1,"Invalid tile layers not reported");
            submit_pose(1);goal_frames=checked_frames+3;
            wait(checked_frames>=goal_frames);@(negedge vs);
            read_reg('h20,value);if(value!=frame_hash(1)) $fatal(1,"Surfaces after tile layers");
            $display("L11 PASS: tile layers 8/16/32, flips, wrap, clipping, scroll, key zero, sprites and surfaces above, invalid descriptors");
        end
        // Defer a table commit while the old memory request is still blocked.
        skip_pixels=1;@(negedge vs);read_reg('h1c,underflow_before);wait(fv);stalled=1;
        for(integer l=0;l<16;l++) for(integer w=0;w<8;w++) write_reg('h800+l*32+w*4,descriptor(2,l,w));
        write_reg('h40,0);write_reg(12,1);
        repeat(2) @(negedge vs);
        read_reg(12,value);if(value!=1) $fatal(1,"Recycled a descriptor bank while still in use");
        read_reg('h1c,value);if(value<=underflow_before) $fatal(1,"Missing underflow report");
        // An attempted write to the bank being recycled must also wait for
        // the old DDR transaction. Exercise the new sprite table decode.
        fork
            begin write_reg(SPRITES ? 'hc00 : 'h800,'h2000000);end
            begin
                repeat(20) @(posedge hc);
                if(ready) $fatal(1,"Descriptor write was not held during BUSY");
                stalled=0;
            end
        join
        if(ahb_stalls<18) $fatal(1,"Missing AHB table backpressure");
        do read_reg(12,value);while(value!=0);
        expected_pose=2;repeat(2) @(negedge vs);skip_pixels=0;
        goal_frames=checked_frames+3;wait(checked_frames>=goal_frames);@(negedge vs);
        read_reg('h20,value);if(value!=0) $fatal(1,"Disabled layers did not clear the image");
        wait(de);write_reg(4,'h800000);write_reg('h30,0);write_reg(12,1);
        do read_reg(12,value);while(value!=0);
        expected_pose=3;goal_frames=checked_frames+3;
        wait(checked_frames>=goal_frames);@(negedge vs);
        if(cpureads<100) $fatal(1,"CPU starved");
        if(SPRITES) $display("G4 PASS: 64 DDR sprites, sizes 8/16/32, flip X/Y, key zero, clipping, layer/object priorities, image animation, invalid descriptors, cache refresh");
        $display("PASS: 16 layers, clipping, scroll, priority, alpha key, arbitrary byte alignment/stride, atomic commit, DDR stalls/recovery, legacy mode; CPU reads=%0d",cpureads);
        $finish;
    end
    initial begin #(HT*VT*28.57*64);$fatal(1,"Timeout");end
endmodule
