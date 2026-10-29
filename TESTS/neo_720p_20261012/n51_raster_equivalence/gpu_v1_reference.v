// GPU V1 extended RGB565 pipeline. New opcodes 22..30; legacy 1..21 unchanged.
// Targets and textures use byte addresses; native DDR uses aligned word addresses.
`default_nettype none
module gpu_v1_reference(
    input wire [3:0] child_resetn,
    input wire clk,rst,start,
    input wire [255:0] command,
    output reg done,
    output wire busy,
    output wire target_config_valid,material_config_valid,
    output reg [31:0] rejected,fragments,passed,
    output wire [31:0] texture_hits,texture_misses,
    output wire valid,write,
    output wire [28:0] addr,
    output wire [255:0] wr_data,
    output wire [31:0] wr_mask,
    input wire ready,rd_valid,
    input wire [255:0] rd_data
);
    localparam IDLE=0,BAD=1,FINISH=2,TARGET_CHECK=3,TEX_CHECK=4,
      TRI_START=5,TRI_BOOT=6,TRI_WAIT=7,SPAN_CLIP=8,ROW_ADDR=9,
      PLANE_MUL=10,PLANE_SUM=11,PLANE_LOAD=12,CHUNK=13,COLOR_REQ=14,
      COLOR_WAIT=15,Z_REQ=16,Z_WAIT=17,PIX_BEGIN=18,PIX_ADDR=19,
      PIX_TEX=20,PIX_UNPACK=21,PIX_MOD=22,PIX_FOG=23,PIX_FOG_MIX=24,
      PIX_BLEND=25,PIX_STORE=26,PIX_NEXT=27,COLOR_WRITE=28,
      COLOR_SENT=29,Z_WRITE=30,Z_SENT=31,ADVANCE=32,RECT_SETUP=33,
      RECT_ROW=34,RECT_CHUNK=35,RECT_COLOR=36,RECT_CSENT=37,
      RECT_Z=38,RECT_ZSENT=39,RECT_NEXT=40,COPY_START=41,COPY_WAIT=42,RECT_BOUNDS=43,RECT_CLIP=44,DECODE=45,TARGET_WAIT=46,TEX_WAIT=47,
      DECODE_WAIT=48,TARGET_VALIDATE=49,TEX_VALIDATE=50,SPAN_BOUNDS=51,
      PIX_LOD=52,PIX_OFFSET=53,PIX_FETCH=54,PIX_OPAQUE=55,DECODE_PIPE=56,TARGET_PIPE=57;
    reg [57:0] state;
    assign busy=!state[IDLE];
    // Gowin 1.9.12 can absorb consecutive, independently enabled command
    // registers into a DSP C pipeline with the enables reversed. This affects
    // COPY's source base and TARGET's depth range, so preserve the packet
    // boundary in fabric (SUG550 section 4.3/5.12).
    // See TESTS/test_gpu_copy_dsp.py for the primitive-level reproduction.
    reg [255:0] packet /* synthesis syn_preserve=1 */;
    wire [31:0] w0=packet[31:0],w1=packet[63:32],w2=packet[95:64],w3=packet[127:96],
        w4=packet[159:128],w5=packet[191:160],w6=packet[223:192],w7=packet[255:224];
    reg target_valid,material_valid,texture_valid,fast_shade,opaque_shade;
    assign target_config_valid=target_valid;
    assign material_config_valid=material_valid;
    reg [29:0] color_base,z_base,texture_base;
    reg [15:0] width,height,color_stride,z_stride,tex_width,tex_height,tex_stride;
    reg [15:0] left,top,right,bottom;
    reg [7:0] flags;
    reg [8:0] alpha,tint_r,tint_g,tint_b;
    reg [15:0] solid,fog_color,fog_near;
    reg [24:0] fog_scale;
    reg tex_argb;
    reg [1:0] mode_u,mode_v;
    reg [3:0] mip_level;
    reg [6:0] plane_valid;
    reg signed [47:0] origins[0:6];
    reg signed [31:0] dx[0:6],dy[0:6];
    reg signed [48:0] value[0:6];
    reg [2:0] plane_index;
    reg signed [48:0] product_x,product_y,plane_sum;
    reg [10:0] px,span_left;
    reg [9:0] py;
    reg [4:0] chunk_count,chunk_left;
    reg [3:0] lane;
    reg [31:0] color_row,z_row;
    reg [28:0] color_addr,z_addr;
    reg [255:0] color_buf,z_buf;
    reg [31:0] pixel_mask;
    // Track whether this chunk contains a stored pixel. Do not reduce the
    // 32-bit byte mask in the wide native-request enable path.
    reg chunk_dirty;
    reg native_valid,native_write;
    reg [28:0] native_addr;
    reg [255:0] native_data;
    reg [31:0] native_mask;
    reg cache_start,cache_invalidate;
    reg [29:0] cache_address;
    wire cache_busy,cache_done,cache_valid;
    wire [28:0] cache_addr;
    wire [15:0] cached_texel;
    // Only the pixel texture state owns this client, after color/Z replies drain.
    wire copy_done,copy_bad,copy_valid,copy_write;
    wire [28:0] copy_addr;
    wire [255:0] copy_data;
    wire [31:0] copy_mask;
    gpu_copy565_reference u_copy(.clk(clk),.rst(!child_resetn[0]),.start(state[COPY_START]),.command(packet),
        .dst_base(color_base),.dst_stride(color_stride),.dst_height(height),
        .clip_l(left),.clip_t(top),.clip_r(right),.clip_b(bottom),
        .done(copy_done),.bad(copy_bad),.valid(copy_valid),.write(copy_write),
        .addr(copy_addr),.wr_data(copy_data),.wr_mask(copy_mask),
        .ready(ready && state[COPY_WAIT]),.rd_valid(rd_valid && state[COPY_WAIT]),.rd_data(rd_data));
    assign valid=native_valid || cache_valid || copy_valid;
    // Les multiplexeurs de sortie (adresse, 256 bits de données, masque : plus de 300 entrées) sont
    // commandés par copy_sel, quatre copies d'un bit de phase (COPY_START/COPY_WAIT) qui couvre tous
    // les cycles où copy_valid peut valoir 1, plutôt que par copy_valid lui-même : ce registre du
    // moteur de copie, à 305 destinations, faisait un fil de 5,7 ns (r621). Hors de ces cycles, valid
    // vaut 0 et la valeur des bus est sans effet ; les transactions DDR sont identiques.
    reg [3:0] copy_sel /* synthesis syn_preserve=1 */;
    always @(posedge clk) copy_sel<={4{state[COPY_START] || state[COPY_WAIT]}};
    assign write=copy_sel[0] ? copy_write:native_valid && native_write;
    assign addr=copy_sel[0] ? copy_addr:cache_valid ? cache_addr:native_addr;
    assign wr_data={copy_sel[2] ? copy_data[255:128]:native_data[255:128],copy_sel[1] ? copy_data[127:0]:native_data[127:0]};
    assign wr_mask=copy_sel[3] ? copy_mask:native_mask;
    gpu_texture_cache_reference u_cache(.clk(clk),.rst(!child_resetn[1]),.invalidate(cache_invalidate),.start(cache_start),
        .byte_address(cache_address),.busy(cache_busy),.done(cache_done),.texel(cached_texel),
        .hits(texture_hits),.misses(texture_misses),.valid(cache_valid),.addr(cache_addr),
        .ready(ready && !native_valid),.rd_data(rd_data),.rd_valid(rd_valid && state[PIX_TEX]));
    reg [32:0] color_end,z_end,texture_end;
    always @(posedge clk)begin
        color_end<={3'b0,color_base}+color_stride*height;
        z_end<={3'b0,z_base}+z_stride*height;
        texture_end<={3'b0,texture_base}+tex_stride*tex_height;
    end
    wire texture_alias=(texture_base<color_end && color_base<texture_end) ||
                       ((flags[1] || flags[2]) && texture_base<z_end && z_base<texture_end);
    wire need_background=alpha!=256 || flags[5] || (flags[0] && tex_argb);
    // Explicit set/hold removes the wide FSM clock-enable priority cone.
    // All native requests hold VALID until their registered DDR acceptance.
    // These issue/wait states are mutually exclusive in the one-hot machine.
    wire native_issue=(state[COLOR_REQ] && need_background) ||
        (state[Z_REQ] && flags[1]) ||
        (state[COLOR_WRITE] && chunk_dirty) || state[Z_WRITE] ||
        (state[RECT_COLOR] && clear_flags[0]) || (state[RECT_Z] && clear_flags[1]);
    wire native_wait=state[COLOR_WAIT] || state[Z_WAIT] || state[COLOR_SENT] ||
        state[Z_SENT] || state[RECT_CSENT] || state[RECT_ZSENT];
    always @(posedge clk)begin
        if(rst)native_valid<=0;
        else native_valid<=native_issue || (native_valid && native_wait && !ready);
    end
    wire [4:0] room=5'd16-{1'b0,px[3:0]};
    reg triangle_start;
    wire triangle_busy,triangle_valid;
    wire [10:0] triangle_x,triangle_width;
    wire [9:0] triangle_y;
    gpu_triangle_reference #(.WIDTH(1024),.HEIGHT(512)) u_triangle(.clk(clk),.rst(!child_resetn[2]),.start(triangle_start),
        .x0(w1[31:16]),.y0(w1[15:0]),.x1(w2[31:16]),.y1(w2[15:0]),
        .x2(w3[31:16]),.y2(w3[15:0]),.busy(triangle_busy),.valid(triangle_valid),
        .ready(state[TRI_WAIT]),.span_x(triangle_x),.span_width(triangle_width),.span_y(triangle_y));
    reg [10:0] unclipped_end;
    reg [10:0] clipped_left,clipped_right;
    always @(posedge clk)begin
        clipped_left<=px<left ? left[10:0]:px;
        clipped_right<=unclipped_end>right ? right[10:0]:unclipped_end;
    end
    // Two rational samples overlap division with texture/shading work.
    reg per_select;
    reg [1:0] per_ready;
    wire [1:0] per_start,per_done,per_valid;
    wire signed [48:0] per_u[0:1],per_v[0:1];
    wire signed [48:0] twice_u={{16{dx[0][31]}},dx[0],1'b0};
    wire signed [48:0] twice_v={{16{dx[1][31]}},dx[1],1'b0};
    wire signed [48:0] twice_q={{16{dx[2][31]}},dx[2],1'b0};
    assign per_start[0]=flags[4] && (state[CHUNK] || (state[PIX_ADDR] && !per_select && chunk_left>2));
    assign per_start[1]=flags[4] && ((state[CHUNK] && span_left>1 && room>1) || (state[PIX_ADDR] && per_select && chunk_left>2));
    gpu_perspective_reference u_per0(.clk(clk),.rst(!child_resetn[3]),.start(per_start[0]),
        .uq(state[CHUNK] ? value[0]:value[0]+twice_u),.vq(state[CHUNK] ? value[1]:value[1]+twice_v),
        .q(state[CHUNK] ? value[2]:value[2]+twice_q),.done(per_done[0]),.valid(per_valid[0]),.tu(per_u[0]),.tv(per_v[0]));
    gpu_perspective_reference u_per1(.clk(clk),.rst(!child_resetn[3]),.start(per_start[1]),
        .uq(state[CHUNK] ? value[0]+dx[0]:value[0]+twice_u),.vq(state[CHUNK] ? value[1]+dx[1]:value[1]+twice_v),
        .q(state[CHUNK] ? value[2]+dx[2]:value[2]+twice_q),.done(per_done[1]),.valid(per_valid[1]),.tu(per_u[1]),.tv(per_v[1]));
    reg [6:0] plane_write;
    wire pixel_advance=state[PIX_NEXT] || state[PIX_STORE] || state[PIX_OPAQUE];
    genvar plane_number;
    generate for(plane_number=0;plane_number<7;plane_number=plane_number+1)begin: plane_registers
        always @(posedge clk)begin
            if(rst)begin origins[plane_number]<=0;dx[plane_number]<=0;dy[plane_number]<=0;end
            else if(plane_write[plane_number])begin
                origins[plane_number]<={w4[15:0],w1};dx[plane_number]<=w2;dy[plane_number]<=w3;
            end
        end
    end endgenerate
    always @(posedge clk)begin
        if(rst)begin per_ready<=0;per_select<=0;end
        else begin
            for(integer n=0;n<2;n=n+1)begin
                if(per_start[n])per_ready[n]<=0;
                else if(per_done[n])per_ready[n]<=1;
            end
            if(state[CHUNK])per_select<=0;
            else if(pixel_advance)per_select<=~per_select;
        end
    end
    reg signed [48:0] raw_u,raw_v,coord_u,coord_v;
    reg rational_valid;
    reg [8:0] tex_u,tex_v /* synthesis syn_preserve=1 */;
    reg [24:0] texture_offset;
    reg [29:0] texture_column;
    function [16:0] coordinate;
        input signed [48:0] v;
        input [15:0] size;
        input [1:0] mode;
        reg [15:0] p;
        begin
            if(mode==1)begin p=v[15:0]&(size-16'd1);coordinate={1'b1,p};end
            else if(mode==2)coordinate={1'b1,(v<0 ? 16'd0:v>=$signed({1'b0,size}) ? size-16'd1:v[15:0])};
            else coordinate={v>=0 && v<$signed({1'b0,size}),v[15:0]};
        end
    endfunction
    wire [16:0] addressed_u=coordinate(coord_u,tex_width,mode_u);
    wire [16:0] addressed_v=coordinate(coord_v,tex_height,mode_v);
    // Private prefetch, consumed at PIX_OFFSET only.
    always @(posedge clk)begin
        tex_u<=addressed_u[8:0];tex_v<=addressed_v[8:0];
    end
    reg [15:0] pixel,background,depth;
    reg [8:0] effective_alpha;
    reg [8:0] gain_r,gain_g,gain_b,fog_factor;
    reg [14:0] mod_r,mod_g,mod_b;
    reg [17:0] alpha_product;
    wire [8:0] rounded_alpha=alpha_product[16:8]+{8'b0,alpha_product[7]};
    reg [41:0] fog_product;
    reg signed [16:0] fog_delta;
    reg [14:0] fog_r,fog_g,fog_b;
    reg [15:0] mix_r,mix_g,mix_b;
    reg pixel_visible;
    // z_sample et depth_in_range sont pris à PIX_BEGIN, en même temps que depth : lane et value[3] ne
    // changent pas entre PIX_BEGIN et PIX_LOD, où sample_visible est lu, et z_buf n'y change que par la
    // réponse DDR anticipée ci-dessous. Avant, le choix de la voie
    // (16 x 16 bits) et la comparaison sur 49 bits se faisaient dans le cycle de PIX_LOD (r621 : 0,75 ns).
    reg [15:0] z_sample;
    reg depth_in_range;
    wire sample_visible=rational_valid && (!(flags[1] || flags[2] || flags[7]) || depth_in_range) &&
        (!flags[1] || depth<z_sample);
    reg sample_allowed;
    wire [4:0] unpack_r=flags[0] && tex_argb ? {pixel[11:8],pixel[11]}:pixel[15:11];
    wire [5:0] unpack_g=flags[0] && tex_argb ? {pixel[7:4],pixel[7:6]}:pixel[10:5];
    wire [4:0] unpack_b=flags[0] && tex_argb ? {pixel[3:0],pixel[3]}:pixel[4:0];
    function [8:0] gain;
        input signed [48:0] v;
        begin gain=v<0 ? 9'd0:v>49'sd16777216 ? 9'd256:v[24:16];end
    endfunction
    wire [8:0] texture_alpha=!flags[0] || !tex_argb ? 9'd256:
        pixel[15:12]==15 ? 9'd256:{1'b0,pixel[15:12],pixel[15:12]};
    wire [8:0] inverse_alpha=9'd256-effective_alpha;
    wire [8:0] inverse_fog=9'd256-fog_factor;
    reg [1:0] clear_flags;
    reg [15:0] clear_color,clear_depth,rect_bottom,rect_left,rect_right;
    wire signed [16:0] rect_x=$signed(w4[31:16]),rect_y=$signed(w4[15:0]);
    wire signed [17:0] rect_end_x=rect_x+$signed({1'b0,w5[31:16]});
    wire signed [17:0] rect_end_y=rect_y+$signed({1'b0,w5[15:0]});
    reg signed [17:0] rect_request_l,rect_request_t,rect_request_r,rect_request_b;
    reg signed [17:0] rect_l,rect_t,rect_r,rect_b;
    reg [31:0] rect_mask;
    // Validate in parallel, then apply through registered predicates. Packet
    // comparators must not drive hundreds of descriptor FF clock enables.
    reg bad_header,bad_scissor,bad_material,bad_plane,bad_triangle,bad_clear,
        bad_invalidate,bad_target,bad_texture;
    reg [2:0] scissor_bad,material_bad;
    reg [5:0] target_bad;
    reg [7:1] word_nonzero;
    always @(posedge clk)begin
        // DECODE_WAIT/DECODE_PIPE cover both reduction stages. These reserved
        // words otherwise feed several wide zero tests directly from packet.
        for(integer w=1;w<8;w=w+1)word_nonzero[w]<=|packet[w*32+:32];
        bad_header<=w0[23:0]!=0 && !(w0[31:24]==26 && w0[23:3]==0 && w0[2:0]<7);
        scissor_bad[0]<=w1[31:16]>w2[31:16] || w2[31:16]>width;
        scissor_bad[1]<=w1[15:0]>w2[15:0] || w2[15:0]>height;
        scissor_bad[2]<=!target_valid || w3!=0 || w4!=0 || w5!=0 || w6!=0 || w7!=0;
        bad_scissor<=|scissor_bad;
        material_bad[0]<=w1>255 || (w1[4] && !w1[0]) || w2>256 || w3>65535;
        material_bad[1]<=w4[31:27]!=0 || w4[8:0]>256 || w4[17:9]>256 || w4[26:18]>256;
        material_bad[2]<=w6>32'h01000000 || w7!=0;
        bad_material<=|material_bad;
        bad_plane<=w0[2:0]>=7 || w4[31:16]!=0 || (|word_nonzero[7:5]);
        bad_triangle<=!target_valid || !material_valid || (|word_nonzero[7:4]) ||
            (flags[0] && (!texture_valid || plane_valid[1:0]!=3 || texture_alias)) ||
            (flags[4] && !plane_valid[2]) || ((flags[1] || flags[2] || flags[7]) && !plane_valid[3]) ||
            (flags[6] && plane_valid[6:4]!=7);
        bad_clear<=!target_valid || w1>3 || w2>65535 || w3>65535 || (|word_nonzero[7:6]);
        bad_invalidate<=|word_nonzero;
        target_bad[0]<=w1[31:30]!=0 || w2[31:30]!=0 || color_base[4:0]!=0 || z_base[4:0]!=0;
        target_bad[1]<=width==0 || width>1024 || height==0 || height>512;
        target_bad[2]<=color_stride[4:0]!=0 || z_stride[4:0]!=0 || color_stride<width*2 || z_stride<width*2;
        target_bad[3]<=color_end>33'h040000000 || z_end>33'h040000000;
        target_bad[4]<=color_base<z_end && z_base<color_end;
        target_bad[5]<=w5!=0 || w6!=0 || w7!=0;
        bad_target<=|target_bad;
        bad_texture<=w1[31:30]!=0 || texture_base[4:0]!=0 || tex_width==0 || tex_width>512 || tex_height==0 || tex_height>512 ||
            tex_stride[4:0]!=0 || tex_stride<tex_width*2 || texture_end>33'h040000000 ||
            w3[31:17]!=0 || w4[31:8]!=0 || mip_level>9 || mode_u==3 || mode_v==3 ||
            (mode_u==1 && (tex_width&(tex_width-1))!=0) || (mode_v==1 && (tex_height&(tex_height-1))!=0) ||
            w5!=0 || w6!=0 || w7!=0;
    end
    always @*begin
        rect_mask=32'hffffffff;
        for(integer b=0;b<16;b=b+1)if(b>=px[3:0] && b<({1'b0,px[3:0]}+chunk_count))rect_mask[b*2+:2]=0;
    end
    // Wide reply data is captured independently of the arbiter return tag.
    reg [255:0] returned_data;
    reg color_load,z_load;
    always @(posedge clk)begin
        returned_data<=rd_data;
        if(rst)begin color_load<=0;z_load<=0;end
        else begin color_load<=state[COLOR_WAIT] && rd_valid;z_load<=state[Z_WAIT] && rd_valid;end
    end
    always @(posedge clk)begin
        // The mask/validity owns reset; unwritten payload is private.
        if(rst || state[CHUNK])begin pixel_mask<=-1;chunk_dirty<=0;end
        else begin
            if((state[PIX_STORE] || state[PIX_OPAQUE]) && pixel_visible)begin
                pixel_mask[lane*2+:2]<=0;
                chunk_dirty<=1;
            end
        end
    end
    always @(posedge clk)begin
            if(color_load)color_buf<=returned_data;
            // PIX_MOD sends zero effective alpha directly to PIX_NEXT.
            // Every path to PIX_STORE has already passed that guard; do not
            // repeat its nine-bit reduction on the wide buffer enables.
            else if(state[PIX_STORE] && pixel_visible)begin
                color_buf[lane*16+:16]<={mix_r>=16'd8192 ? 5'd31:mix_r[12:8],
                    mix_g>=16'd16384 ? 6'd63:mix_g[13:8],mix_b>=16'd8192 ? 5'd31:mix_b[12:8]};
            end
            else if(state[PIX_OPAQUE] && pixel_visible)begin
                // No fog or blending: their identity operations leave the
                // rounded modulation unchanged, for RGB565 and solid colors.
                color_buf[lane*16+:16]<={mod_r[12:8],mod_g[13:8],mod_b[12:8]};
            end
            if(z_load)z_buf<=returned_data;
            else if(state[PIX_STORE] && pixel_visible)z_buf[lane*16+:16]<=depth;
            else if(state[PIX_OPAQUE] && pixel_visible)z_buf[lane*16+:16]<=depth;
    end
    // Plane arithmetic shares a multiplier pair across attributes at each span.
    // px_mul/py_mul : copie de px/py prise un cycle plus tôt, entrée des multiplicateurs. Sans elle,
    // la synthèse absorbe px dans le registre d'entrée du DSP, et toute la logique de mise à jour
    // de px (comparaison clipped_left/clipped_right, multiplexeur) doit atteindre la colonne DSP en
    // un cycle : c'était le seul chemin en défaut de la compilation r325 (0,49 ns). px et py sont
    // écrits au moins deux cycles avant PLANE_MUL (SPAN_CLIP, ROW_ADDR), donc les produits sont
    // identiques au cycle près.
    reg [10:0] px_mul,py_mul;
    always @(posedge clk)begin
        px_mul<=px;py_mul<=py;
        product_x<=$signed({1'b0,px_mul})*dx[plane_index];
        product_y<=$signed({1'b0,py_mul})*dy[plane_index];
        plane_sum<=product_x+origins[plane_index];
        if(state[PLANE_LOAD])value[plane_index]<=plane_sum+product_y;
        else if(pixel_advance)for(integer p=0;p<7;p=p+1)value[p]<=value[p]+dx[p];
    end
    always @(posedge clk)begin
        if(rst)begin
            packet<=0;plane_write<=0;state<=58'b1<<IDLE;done<=0;native_write<=0;native_addr<=0;native_data<=0;native_mask<=-1;
            target_valid<=0;texture_valid<=0;material_valid<=0;plane_valid<=0;fast_shade<=1;opaque_shade<=0;
            rejected<=0;fragments<=0;passed<=0;cache_start<=0;cache_invalidate<=0;cache_address<=0;
            color_base<=0;z_base<=0;texture_base<=0;width<=0;height<=0;color_stride<=0;z_stride<=0;
            left<=0;top<=0;right<=0;bottom<=0;tex_width<=0;tex_height<=0;tex_stride<=0;
            flags<=0;alpha<=256;solid<=0;tint_r<=256;tint_g<=256;tint_b<=256;
            fog_color<=0;fog_near<=0;fog_scale<=0;tex_argb<=0;mode_u<=0;mode_v<=0;mip_level<=0;
            px<=0;py<=0;span_left<=0;chunk_count<=0;chunk_left<=0;lane<=0;plane_index<=0;
            color_row<=0;z_row<=0;color_addr<=0;z_addr<=0;triangle_start<=0;unclipped_end<=0;
            raw_u<=0;raw_v<=0;coord_u<=0;coord_v<=0;rational_valid<=0;
            texture_offset<=0;texture_column<=0;
            pixel<=0;background<=0;depth<=0;effective_alpha<=0;pixel_visible<=0;sample_allowed<=0;
            gain_r<=0;gain_g<=0;gain_b<=0;fog_factor<=0;
            mod_r<=0;mod_g<=0;mod_b<=0;alpha_product<=0;fog_product<=0;fog_delta<=0;
            fog_r<=0;fog_g<=0;fog_b<=0;mix_r<=0;mix_g<=0;mix_b<=0;
            rect_request_l<=0;rect_request_t<=0;rect_request_r<=0;rect_request_b<=0;rect_l<=0;rect_t<=0;rect_r<=0;rect_b<=0;
            clear_flags<=0;clear_color<=0;clear_depth<=0;rect_bottom<=0;rect_left<=0;rect_right<=0;
        end else begin
            done<=0;plane_write<=0;cache_start<=0;cache_invalidate<=0;triangle_start<=0;
            case(1'b1) // synthesis parallel_case
            state[IDLE]:if(start)begin packet<=command;state<=58'b1<<DECODE_WAIT;end
            state[DECODE_WAIT]:state<=58'b1<<DECODE_PIPE;
            state[DECODE_PIPE]:state<=58'b1<<DECODE;
            state[TARGET_WAIT]:state<=58'b1<<TARGET_CHECK;
            state[TEX_WAIT]:state<=58'b1<<TEX_CHECK;
            state[TARGET_CHECK]:state<=58'b1<<TARGET_PIPE;
            state[TARGET_PIPE]:state<=58'b1<<TARGET_VALIDATE;
            state[TEX_CHECK]:state<=58'b1<<TEX_VALIDATE;
            state[DECODE]:begin
                if(bad_header)begin
                    // A malformed descriptor must not leave the previous one usable.
                    case(w0[31:24])
                    22:target_valid<=0;
                    24:texture_valid<=0;
                    25:material_valid<=0;
                    26:if(w0[2:0]<7)plane_valid[w0[2:0]]<=0;
                    endcase
                    state<=58'b1<<BAD;
                end
                else case(w0[31:24])
                22:begin
                    target_valid<=0;color_base<=w1[29:0];z_base<=w2[29:0];width<=w3[31:16];height<=w3[15:0];
                    color_stride<=w4[31:16];z_stride<=w4[15:0];
                    state<=58'b1<<TARGET_WAIT;
                end
                23:begin
                    if(bad_scissor)state<=58'b1<<BAD;
                    else begin left<=w1[31:16];top<=w1[15:0];right<=w2[31:16];bottom<=w2[15:0];state<=58'b1<<FINISH;end
                end
                24:begin
                    texture_valid<=0;texture_base<=w1[29:0];tex_width<=w2[31:16];tex_height<=w2[15:0];
                    tex_stride<=w3[15:0];tex_argb<=w3[16];mode_u<=w4[1:0];mode_v<=w4[3:2];mip_level<=w4[7:4];
                    state<=58'b1<<TEX_WAIT;
                end
                25:begin
                    material_valid<=0;
                    if(bad_material)state<=58'b1<<BAD;
                    else begin
                        fast_shade<=w1[7:6]==0 && w4==32'h04020100;
                        opaque_shade<=w2==256 && !w1[5] && !w1[7];
                        flags<=w1[7:0];alpha<=w2[8:0];solid<=w3[15:0];
                        tint_r<=w4[8:0];tint_g<=w4[17:9];tint_b<=w4[26:18];
                        fog_near<=w5[31:16];fog_color<=w5[15:0];fog_scale<=w6[24:0];
                        material_valid<=1;state<=58'b1<<FINISH;
                    end
                end
                26:begin
                    if(bad_plane)begin
                        if(w0[2:0]<7)plane_valid[w0[2:0]]<=0;state<=58'b1<<BAD;
                    end else begin
                        plane_write<=7'b1<<w0[2:0];
                        plane_valid[w0[2:0]]<=1;state<=58'b1<<FINISH;
                    end
                end
                27:begin
                    if(bad_triangle)state<=58'b1<<BAD;
                    else state<=58'b1<<(alpha==0 || left==right || top==bottom ? FINISH:TRI_START);
                end
                28:begin
                    if(bad_clear)state<=58'b1<<BAD;
                    else begin clear_flags<=w1[1:0];clear_color<=w2[15:0];clear_depth<=w3[15:0];state<=58'b1<<RECT_BOUNDS;end
                end
                29:state<=58'b1<<(target_valid ? COPY_START:BAD);
                30:begin
                    if(bad_invalidate)state<=58'b1<<BAD;
                    else begin cache_invalidate<=1;state<=58'b1<<FINISH;end
                end
                default:state<=58'b1<<BAD;
                endcase
            end
            state[COPY_START]:state<=58'b1<<COPY_WAIT;
            state[COPY_WAIT]:if(copy_done)begin cache_invalidate<=1;state<=58'b1<<(copy_bad ? BAD:FINISH);end
            state[BAD]:begin rejected<=rejected+1'b1;state<=58'b1<<FINISH;end
            state[FINISH]:begin done<=1;state<=58'b1<<IDLE;end
            state[TARGET_VALIDATE]:begin
                if(bad_target)state<=58'b1<<BAD;
                else begin target_valid<=1;left<=0;top<=0;right<=width;bottom<=height;state<=58'b1<<FINISH;end
            end
            state[TEX_VALIDATE]:begin
                if(bad_texture)state<=58'b1<<BAD;
                else begin texture_valid<=1;state<=58'b1<<FINISH;end
            end
            state[TRI_START]:begin triangle_start<=1;state<=58'b1<<TRI_BOOT;end
            state[TRI_BOOT]:state<=58'b1<<TRI_WAIT;
            state[TRI_WAIT]:begin
                if(triangle_valid)begin px<=triangle_x;py<=triangle_y;unclipped_end<=triangle_x+triangle_width;state<=58'b1<<SPAN_BOUNDS;end
                else if(!triangle_busy)state<=58'b1<<FINISH;
            end
            state[SPAN_BOUNDS]:state<=58'b1<<SPAN_CLIP;
            state[SPAN_CLIP]:begin
                if(py<top || py>=bottom || clipped_left>=clipped_right)state<=58'b1<<TRI_WAIT;
                else begin px<=clipped_left;span_left<=clipped_right-clipped_left;state<=58'b1<<ROW_ADDR;end
            end
            state[ROW_ADDR]:begin
                color_row<=color_base+py*color_stride;z_row<=z_base+py*z_stride;plane_index<=0;state<=58'b1<<PLANE_MUL;
            end
            state[PLANE_MUL]:state<=58'b1<<PLANE_SUM;
            state[PLANE_SUM]:state<=58'b1<<PLANE_LOAD;
            state[PLANE_LOAD]:begin
                if(plane_index==6)state<=58'b1<<CHUNK;
                else begin plane_index<=plane_index+1'b1;state<=58'b1<<PLANE_MUL;end
            end
            state[CHUNK]:begin
                color_addr<=(color_row+({21'd0,px}<<1))>>2;z_addr<=(z_row+({21'd0,px}<<1))>>2;
                lane<=px[3:0];chunk_count<=span_left>room ? room:span_left[4:0];chunk_left<=span_left>room ? room:span_left[4:0];
                state<=58'b1<<COLOR_REQ;
            end
            state[COLOR_REQ]:begin
                if(need_background)begin native_addr<={color_addr[28:3],3'b0};native_write<=0;state<=58'b1<<COLOR_WAIT;end
                else state<=58'b1<<Z_REQ;
            end
            state[COLOR_WAIT]:begin
                if(rd_valid)state<=58'b1<<Z_REQ;
            end
            state[Z_REQ]:begin
                if(flags[1])begin native_addr<={z_addr[28:3],3'b0};native_write<=0;state<=58'b1<<Z_WAIT;end
                else state<=58'b1<<PIX_BEGIN;
            end
            state[Z_WAIT]:begin
                if(rd_valid)state<=58'b1<<PIX_BEGIN;
            end
            state[PIX_BEGIN]:if(!flags[4] || per_ready[per_select])begin
                raw_u<=flags[4] ? per_u[per_select]:value[0]>>>16;
                raw_v<=flags[4] ? per_v[per_select]:value[1]>>>16;
                rational_valid<=!flags[4] || per_valid[per_select];
                depth<=value[3][31:16];background<=color_buf[lane*16+:16];
                // z_buf reçoit la réponse DDR (z_load) au premier cycle de PIX_BEGIN : anticiper cette valeur.
                z_sample<=z_load ? returned_data[lane*16+:16]:z_buf[lane*16+:16];
                depth_in_range<=value[3]>=0 && value[3]<49'sh100000000;
                gain_r<=flags[6] ? gain(value[4]):tint_r;gain_g<=flags[6] ? gain(value[5]):tint_g;gain_b<=flags[6] ? gain(value[6]):tint_b;
                state<=58'b1<<PIX_LOD;
            end
            state[PIX_LOD]:begin
                coord_u<=raw_u>>>mip_level;coord_v<=raw_v>>>mip_level;
                sample_allowed<=sample_visible;
                state<=58'b1<<PIX_ADDR;
            end
            state[PIX_ADDR]:begin
                fragments<=fragments+1'b1;
                pixel_visible<=sample_allowed;
                if(!sample_allowed || (flags[0] && (!addressed_u[16] || !addressed_v[16])))state<=58'b1<<PIX_NEXT;
                else if(flags[0])begin
                    state<=58'b1<<PIX_OFFSET;
                end else begin
                    pixel<=solid;
                    if(flags[0])pixel_visible<=0;
                    state<=58'b1<<PIX_UNPACK;
                end
            end
            state[PIX_OFFSET]:begin
                texture_offset<=tex_v*tex_stride;
                texture_column<=texture_base+{tex_u,1'b0};state<=58'b1<<PIX_FETCH;
            end
            state[PIX_FETCH]:begin
                cache_address<=texture_column+texture_offset;
                cache_start<=1;state<=58'b1<<PIX_TEX;
            end
            state[PIX_TEX]:if(cache_done)begin pixel<=cached_texel;state<=58'b1<<PIX_UNPACK;end
            state[PIX_UNPACK]:begin
                if(flags[3] && pixel==0)pixel_visible<=0;
                mod_r<=unpack_r*gain_r+15'd128;mod_g<=unpack_g*gain_g+15'd128;mod_b<=unpack_b*gain_b+15'd128;
                if(fast_shade)begin
                    fog_r<={2'b0,unpack_r,8'd128};fog_g<={1'b0,unpack_g,8'd128};fog_b<={2'b0,unpack_b,8'd128};
                end
                alpha_product<=alpha*texture_alpha;
                fog_delta<=$signed({1'b0,depth})-$signed({1'b0,fog_near});
                state<=58'b1<<((flags[3] && pixel==0) || texture_alpha==0 ? PIX_NEXT:
                    opaque_shade && !(flags[0] && tex_argb) ? PIX_OPAQUE:PIX_MOD);
            end
            state[PIX_MOD]:begin
                effective_alpha<=rounded_alpha;
                fog_product<=fog_delta<0 ? 42'd0:fog_delta*fog_scale;
                if(!flags[7])fog_factor<=0;
                state<=58'b1<<(rounded_alpha==0 ? PIX_NEXT:fast_shade ? PIX_BLEND:flags[7] ? PIX_FOG:PIX_FOG_MIX);
            end
            state[PIX_FOG]:begin
                fog_factor<=!flags[7] ? 9'd0:fog_product>=42'd16777216 ? 9'd256:fog_product[24:16];
                state<=58'b1<<PIX_FOG_MIX;
            end
            state[PIX_FOG_MIX]:begin
                fog_r<=mod_r[12:8]*inverse_fog+fog_color[15:11]*fog_factor+15'd128;
                fog_g<=mod_g[13:8]*inverse_fog+fog_color[10:5]*fog_factor+15'd128;
                fog_b<=mod_b[12:8]*inverse_fog+fog_color[4:0]*fog_factor+15'd128;
                state<=58'b1<<PIX_BLEND;
            end
            state[PIX_BLEND]:begin
                mix_r<=fog_r[12:8]*effective_alpha+background[15:11]*(flags[5] ? 9'd256:inverse_alpha)+16'd128;
                mix_g<=fog_g[13:8]*effective_alpha+background[10:5]*(flags[5] ? 9'd256:inverse_alpha)+16'd128;
                mix_b<=fog_b[12:8]*effective_alpha+background[4:0]*(flags[5] ? 9'd256:inverse_alpha)+16'd128;
                state<=58'b1<<PIX_STORE;
            end
            state[PIX_STORE]:begin
                if(pixel_visible)passed<=passed+1'b1;
                lane<=lane+1'b1;chunk_left<=chunk_left-1'b1;state<=58'b1<<(chunk_left==1 ? COLOR_WRITE:PIX_BEGIN);
            end
            state[PIX_OPAQUE]:begin
                if(pixel_visible)passed<=passed+1'b1;
                lane<=lane+1'b1;chunk_left<=chunk_left-1'b1;state<=58'b1<<(chunk_left==1 ? COLOR_WRITE:PIX_BEGIN);
            end
            state[PIX_NEXT]:begin
                lane<=lane+1'b1;chunk_left<=chunk_left-1'b1;state<=58'b1<<(chunk_left==1 ? COLOR_WRITE:PIX_BEGIN);
            end
            state[COLOR_WRITE]:begin
                if(!chunk_dirty)state<=58'b1<<ADVANCE;
                else begin native_addr<={color_addr[28:3],3'b0};native_data<=color_buf;native_mask<=pixel_mask;
                    native_write<=1;state<=58'b1<<COLOR_SENT;end
            end
            state[COLOR_SENT]:if(ready)begin state<=58'b1<<(flags[2] ? Z_WRITE:ADVANCE);end
            state[Z_WRITE]:begin native_addr<={z_addr[28:3],3'b0};native_data<=z_buf;native_mask<=pixel_mask;
                native_write<=1;state<=58'b1<<Z_SENT;end
            state[Z_SENT]:if(ready)begin state<=58'b1<<ADVANCE;end
            state[ADVANCE]:begin px<=px+chunk_count;span_left<=span_left-chunk_count;state<=58'b1<<(span_left==chunk_count ? TRI_WAIT:CHUNK);end
            state[RECT_BOUNDS]:begin
                rect_request_l<=rect_x;rect_request_t<=rect_y;rect_request_r<=rect_end_x;rect_request_b<=rect_end_y;
                state<=58'b1<<RECT_CLIP;
            end
            state[RECT_CLIP]:begin
                rect_l<=rect_request_l<$signed({1'b0,left}) ? $signed({1'b0,left}):rect_request_l;
                rect_t<=rect_request_t<$signed({1'b0,top}) ? $signed({1'b0,top}):rect_request_t;
                rect_r<=rect_request_r>$signed({1'b0,right}) ? $signed({1'b0,right}):rect_request_r;
                rect_b<=rect_request_b>$signed({1'b0,bottom}) ? $signed({1'b0,bottom}):rect_request_b;
                state<=58'b1<<RECT_SETUP;
            end
            state[RECT_SETUP]:begin
                // Empty rectangles may update these private temporaries, but
                // never issue DDR traffic. Keep the wide emptiness comparison
                // out of py's data/enable path (also absorbed into DSP inputs).
                rect_left<=rect_l[15:0];rect_right<=rect_r[15:0];rect_bottom<=rect_b[15:0];py<=rect_t[9:0];
                if(clear_flags==0 || rect_l>=rect_r || rect_t>=rect_b)state<=58'b1<<FINISH;
                else state<=58'b1<<RECT_ROW;
            end
            state[RECT_ROW]:begin
                px<=rect_left[10:0];span_left<=rect_right-rect_left;
                color_row<=color_base+py*color_stride;z_row<=z_base+py*z_stride;state<=58'b1<<RECT_CHUNK;
            end
            state[RECT_CHUNK]:begin
                color_addr<=(color_row+({21'd0,px}<<1))>>2;z_addr<=(z_row+({21'd0,px}<<1))>>2;
                chunk_count<=span_left>room ? room:span_left[4:0];state<=58'b1<<RECT_COLOR;
            end
            state[RECT_COLOR]:begin
                if(clear_flags[0])begin native_addr<={color_addr[28:3],3'b0};native_data<={16{clear_color}};native_mask<=rect_mask;
                    native_write<=1;state<=58'b1<<RECT_CSENT;end
                else state<=58'b1<<RECT_Z;
            end
            state[RECT_CSENT]:if(ready)begin state<=58'b1<<RECT_Z;end
            state[RECT_Z]:begin
                if(clear_flags[1])begin native_addr<={z_addr[28:3],3'b0};native_data<={16{clear_depth}};native_mask<=rect_mask;
                    native_write<=1;state<=58'b1<<RECT_ZSENT;end
                else state<=58'b1<<RECT_NEXT;
            end
            state[RECT_ZSENT]:if(ready)begin state<=58'b1<<RECT_NEXT;end
            state[RECT_NEXT]:begin
                if(span_left>chunk_count)begin px<=px+chunk_count;span_left<=span_left-chunk_count;state<=58'b1<<RECT_CHUNK;end
                else begin
                    py<=py+1'b1;
                    state<=58'b1<<(py+1>=rect_bottom ? FINISH:RECT_ROW);
                end
            end
            default:begin state<=58'b1<<BAD;end
            endcase
        end
    end
endmodule
`default_nettype wire
