// L13/L14/L15 RGB565 fragment engine. Ordered by the legacy command FIFO.
// Native DDR addresses are 32-bit words, bursts 256 bits. No new clock.
// See ARCHI/GPU_L13_L15_RGB_DEPTH.md for fixed-point and memory contracts.
`default_nettype none
module gpu_raster_reference #(
    parameter WIDTH=800, HEIGHT=480
) (
    input wire clk, rst, start,
    input wire [255:0] command,
    output wire busy,
    output reg done,
    output reg [31:0] rejected, fragments, passed,
    output reg valid, write,
    output reg [28:0] addr,
    output reg [255:0] wr_data,
    output reg [31:0] wr_mask,
    input wire ready,
    input wire [255:0] rd_data,
    input wire rd_valid
);
    localparam IDLE=0, FINISH=1, BAD=2, TEX_ADDR=3, TEX_REQ=4,
        TEX_WAIT=5, TEX_COPY=6, TEX_NEXT=7, TRI_START=8, TRI_BOOT=9,
        TRI_WAIT=10, SPAN0=11, SPAN1=12, SPAN2=13, CHUNK=14,
        COLOR_REQ=15, COLOR_WAIT=16, Z_PREP=17, Z_REQ=18, Z_WAIT=19,
        PIX_PRIME=20, PIX_SAMPLE=21, PIX_TEST=22, PIX_BLEND=23, PIX_STORE=24,
        COLOR_WRITE=25, COLOR_SENT=26, Z_WRITE=27, Z_SENT=28, ADVANCE=29,
        CLEAR_PREP=30, CLEAR_SEND=31, CLEAR_NEXT=32,TEX_OFFSET=33,TEX_BASE=34;
    // One-hot state bits keep DDR READY/VALID off a deep binary decode.
    reg [34:0] state;
    assign busy=!state[IDLE];
    // Copie locale du mot de commande. Le blitter écrit son dernier mot (txt[127:96]) un cycle avant de lever
    // start : la copie prise à chaque cycle est donc égale au mot au moment du départ, sans cycle ajouté.
    // Sans elle, l'opcode du blitter (registre op, module voisin) décodait directement les enables de ce
    // module : chemin inter-modules en défaut de 0,4 ns dans r617.
    reg [255:0] command_r /* synthesis syn_preserve=1 */;
    always @(posedge clk) command_r<=command;
    wire [31:0] w0=command_r[31:0], w1=command_r[63:32], w2=command_r[95:64],
        w3=command_r[127:96], w4=command_r[159:128], w5=command_r[191:160],
        w6=command_r[223:192], w7=command_r[255:224];
    reg configured, texture_valid;
    reg [3:0] plane_valid;
    reg [3:0] color_page, z_page;
    reg [4:0] flags;
    reg [8:0] alpha;
    reg [15:0] solid;
    reg signed [47:0] u0,v0,z0,q0;
    reg signed [31:0] ux,uy,vx,vy,zx,zy,qx,qy;
    // One guard bit beyond the 48-bit origin covers both screen products.
    reg signed [48:0] u,v,z,q;
    reg signed [47:0] xu,yu,xv,yv,xz,yz,xq,yq;
    reg [10:0] px, span_left;
    reg [9:0] py;
    reg [19:0] row_offset;
    reg [28:0] color_addr,z_addr;
    reg [4:0] chunk_count, chunk_left;
    reg [3:0] lane;
    reg [255:0] color_buf,z_buf;
    reg [31:0] pixel_mask;
    reg [15:0] source_pixel,background,depth;
    reg [63:0] background_groups,depth_groups;
    wire [15:0] sampled_background=background_groups[lane[3:2]*16+:16];
    wire [15:0] sampled_depth=depth_groups[lane[3:2]*16+:16];
    reg sample_inside, sample_depth_ok, visible;
    reg [14:0] mix_r,mix_g,mix_b;
    wire [8:0] inverse_alpha=9'd256-alpha;
    wire [15:0] blended={mix_r[12:8],mix_g[13:8],mix_b[12:8]};

    reg [7:0] tw,th;
    reg [1:0] mode_u,mode_v;
    reg [3:0] texture_page;
    reg [9:0] texture_x,texture_y;
    reg [6:0] load_x,load_y;
    reg [7:0] load_left;
    reg [3:0] load_lane;
    reg [24:0] texture_row,texture_offset;
    reg [10:0] texture_scan_y;
    reg [255:0] texture_buffer;
    reg [15:0] texture [0:16383];
    reg [15:0] texel;
    reg [13:0] texture_sample_address;
    wire [15:0] sampled_source=flags[0] ? texel:solid;
    // Two look-ahead samples hide exact division behind fragment processing.
    // A slow, far-out repeated coordinate simply holds PIX_PRIME.
    reg per_select;
    wire [1:0] per_start,per_done,per_valid;
    reg [1:0] per_ready;
    wire signed [48:0] per_u0,per_v0,per_u1,per_v1;
    wire signed [48:0] step_u={{16{ux[31]}},ux,1'b0};
    wire signed [48:0] step_v={{16{vx[31]}},vx,1'b0};
    wire signed [48:0] step_q={{16{qx[31]}},qx,1'b0};
    reg per_next,store_pixel,chunk_init;
    always @(posedge clk)begin
        if(rst)begin per_next<=0;store_pixel<=0;chunk_init<=0;end
        else begin
            per_next<=state[PIX_SAMPLE];
            store_pixel<=state[PIX_BLEND];
            chunk_init<=state[SPAN2] || (state[ADVANCE] && span_left!={6'd0,chunk_count});
        end
    end
    assign per_start[0]=flags[4] && (state[CHUNK] || (per_next && !per_select && chunk_left>2));
    assign per_start[1]=flags[4] && ((state[CHUNK] && span_left>1 && room>1) || (per_next && per_select && chunk_left>2));
    gpu_perspective u_perspective0 (.clk(clk),.rst(rst),.start(per_start[0]),
        .uq(per_next ? u+step_u:u),.vq(per_next ? v+step_v:v),.q(per_next ? q+step_q:q),
        .done(per_done[0]),.valid(per_valid[0]),.tu(per_u0),.tv(per_v0));
    gpu_perspective u_perspective1 (.clk(clk),.rst(rst),.start(per_start[1]),
        .uq(per_next ? u+step_u:u+ux),.vq(per_next ? v+step_v:v+vx),.q(per_next ? q+step_q:q+qx),
        .done(per_done[1]),.valid(per_valid[1]),.tu(per_u1),.tv(per_v1));
    always @(posedge clk) begin
        if(rst)begin per_ready<=0;per_select<=0;end
        else begin
            per_ready<=(per_ready|per_done)&~per_start;
            if(state[CHUNK])per_select<=0;
            else if(state[PIX_STORE])per_select<=~per_select;
        end
    end
    // Decode affine and both rational coordinates independently, then select
    // the compact address. Mode selection must not precede a 49-bit bounds
    // comparison and clamp on the path into the texture BSRAM address port.
    function [7:0] texture_axis;
        input signed [48:0] coordinate;
        input [7:0] size;
        input [1:0] mode;
        reg in_bounds;
        reg [6:0] position;
        begin
            // coordinate < size (taille sur 8 bits) <=> coordonnée positive, bits 48:8 nuls et bits 7:0 < size.
            // Équivalent au comparateur signé de 49 bits, mais la chaîne de retenue n'a plus que 8 étages :
            // l'adresse des 16 mémoires du cache en dépend directement (r604 : 2,8 ns en défaut).
            in_bounds=!coordinate[48] && coordinate[47:8]==40'd0 && coordinate[7:0]<size;
            position=mode==1 ? (coordinate[6:0] & (size[6:0]-7'd1)) :
                coordinate<0 ? 7'd0 : !in_bounds ? size[6:0]-7'd1 : coordinate[6:0];
            texture_axis={in_bounds || mode!=0,position};
        end
    endfunction
    wire [7:0] affine_u=texture_axis(u>>>16,tw,mode_u),affine_v=texture_axis(v>>>16,th,mode_v);
    wire [7:0] rational_u0=texture_axis(per_u0,tw,mode_u),rational_v0=texture_axis(per_v0,th,mode_v);
    wire [7:0] rational_u1=texture_axis(per_u1,tw,mode_u),rational_v1=texture_axis(per_v1,th,mode_v);
    wire [7:0] selected_u=flags[4] ? (per_select ? rational_u1:rational_u0):affine_u;
    wire [7:0] selected_v=flags[4] ? (per_select ? rational_v1:rational_v0):affine_v;
    wire [6:0] tex_u=selected_u[6:0],tex_v=selected_v[6:0];
    wire texture_inside=selected_u[7] && selected_v[7] && (!flags[4] || per_valid[per_select]);
    // Follow the return bus while waiting, then freeze its accepted burst
    // during TEX_COPY. The return-valid/tag path only changes the state;
    // it no longer drives the enable of all 256 buffer bits. Data before
    // a valid response is never consumed. No copy cycle is added.
    always @(posedge clk)begin
        if(rst)texture_buffer<=0;
        else if(!state[TEX_COPY])texture_buffer<=rd_data;
    end
    always @(posedge clk) begin
        if(state[TEX_COPY])texture[{load_y,load_x}]<=texture_buffer[load_lane*16+:16];
        // PRIME enregistre l'adresse ; SAMPLE lit la BSRAM ; TEST utilise
        // le texel. Ces trois états existaient déjà : aucun cycle de pixel
        // ajouté. La comparaison/bouclage des coordonnées ne précède plus
        // directement les seize ports d'adresse du cache (c2 : -1,920 ns).
        texture_sample_address<={tex_v,tex_u};
        texel<=texture[texture_sample_address];
    end

    reg triangle_start;
    wire triangle_busy,triangle_valid;
    wire [10:0] triangle_x,triangle_width;
    wire [9:0] triangle_y;
    gpu_triangle #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) u_triangle (
        .clk(clk),.rst(rst),.start(triangle_start),
        .x0(w1[31:16]),.y0(w1[15:0]),.x1(w2[31:16]),.y1(w2[15:0]),
        .x2(w3[31:16]),.y2(w3[15:0]),.busy(triangle_busy),
        .valid(triangle_valid),.ready(state[TRI_WAIT]),
        .span_x(triangle_x),.span_width(triangle_width),.span_y(triangle_y));
    // Registered products: two settling cycles before loading accumulators.
    always @(posedge clk) begin
        xu<=$signed({1'b0,px})*ux; yu<=$signed({1'b0,py})*uy;
        xv<=$signed({1'b0,px})*vx; yv<=$signed({1'b0,py})*vy;
        xz<=$signed({1'b0,px})*zx; yz<=$signed({1'b0,py})*zy;
        xq<=$signed({1'b0,px})*qx; yq<=$signed({1'b0,py})*qy;
    end
    reg signed [48:0] origin_u,origin_v,origin_z,origin_q;
    always @(posedge clk) begin
        origin_u<=xu+u0;origin_v<=xv+v0;origin_z<=xz+z0;origin_q<=xq+q0;
    end
    reg [1:0] clear_flags;
    reg clearing_depth;
    reg [15:0] clear_color,clear_depth;
    reg [15:0] clear_block;
    wire [4:0] room=5'd16-{1'b0,px[3:0]};
    wire state_words_ok=w0[23:0]==0 && w1[31:8]==0 && w2[31:5]==0 && (!w2[4] || w2[0]) &&
        w3<=256 && w4[31:16]==0 && w5==0 && w6==0 && w7==0 && w1[3:0]!=w1[7:4];
    wire tex_words_ok=w0[23:0]==0 && w1[31:4]==0 && w4[31:4]==0 &&
        w5==0 && w6==0 && w7==0 && w3[31:16]>=1 && w3[31:16]<=128 &&
        w3[15:0]>=1 && w3[15:0]<=128 &&
        ({1'b0,w2[31:16]}+{1'b0,w3[31:16]})<=WIDTH &&
        ({1'b0,w2[15:0]}+{1'b0,w3[15:0]})<=HEIGHT &&
        w4[1:0]!=3 && w4[3:2]!=3 &&
        (w4[1:0]!=1 || (w3[31:16] & (w3[31:16]-16'd1))==0) &&
        (w4[3:2]!=1 || (w3[15:0] & (w3[15:0]-16'd1))==0);
    wire triangle_words_ok=w0[23:0]==0 && w4==0 && w5==0 && w6==0 && w7==0;
    wire plane_words_ok=w0[23:0]==0 && w4[31:17]==0 &&
        (w4[16] || w4[15:0]==0) && w5==0 && w6==0 && w7==0;
    // Internal interface contract: blitter finishes fetching the command at
    // least one full cycle before start, and holds it until done. Predecode
    // during that existing interval; no command or pixel cycle is added.
    reg state_words_ready,tex_words_ready,triangle_words_ready,plane_words_ready,clear_words_ready;
    always @(posedge clk)begin
        state_words_ready<=state_words_ok;
        tex_words_ready<=tex_words_ok;
        triangle_words_ready<=triangle_words_ok;
        plane_words_ready<=plane_words_ok;
        clear_words_ready<=w0[23:0]==0 && w1[31:2]==0 && w2[31:16]==0 &&
            w3[31:16]==0 && w4==0 && w5==0 && w6==0 && w7==0;
    end
    // Extended origin is signed Q32.16; w4=0 retains the initial interface.
    wire signed [47:0] signed_plane_origin=w4[16] ? {w4[15:0],w1}:{{16{w1[31]}},w1};
    wire signed [47:0] depth_plane_origin=w4[16] ? {w4[15:0],w1}:{16'd0,w1};
    // The arbiter's return tag is combinational. Capture it separately from
    // the wide, per-lane buffer enables; PIX_PRIME leaves a settling cycle
    // before either buffer is sampled, so command timing stays unchanged.
    reg color_load,z_load;
    // Copie locale du bus de lecture DDR. Sans syn_preserve, la synthèse fusionne les copies identiques des
    // différents modules en un seul registre, placé chez l'un d'eux : les autres le lisent par de longs fils.
    reg [255:0] returned_data /* synthesis syn_preserve=1 */;
    always @(posedge clk)begin
        returned_data<=rd_data;
        if(rst)begin color_load<=0;z_load<=0;end
        else begin
            color_load<=state[COLOR_WAIT] && rd_valid;
            z_load<=state[Z_WAIT] && rd_valid;
        end
    end
    // Predict unconditional state transitions one cycle ahead, so the wide
    // chunk buffers are not enabled through the shared binary-state decode.
    always @(posedge clk)begin
        if(rst)begin color_buf<=0;z_buf<=0;pixel_mask<=-1;end
        else if(chunk_init)begin color_buf<=0;z_buf<=0;pixel_mask<=-1;end
        else begin
            if(color_load)color_buf<=returned_data;
            else if(store_pixel && visible)color_buf[lane*16+:16]<=blended;
            if(z_load)z_buf<=returned_data;
            else if(store_pixel && visible)z_buf[lane*16+:16]<=depth;
            if(store_pixel && visible)pixel_mask[lane*2+:2]<=0;
        end
    end
    // Split each 16:1 lane selector across SAMPLE and TEST. The alpha
    // products use background in BLEND, so native command cycles stay exact.
    genvar background_group;
    generate for(background_group=0;background_group<4;background_group=background_group+1)begin: g_background
        always @(posedge clk)begin
            if(rst)begin
                background_groups[background_group*16+:16]<=0;
                depth_groups[background_group*16+:16]<=0;
            end else if(state[PIX_SAMPLE])begin
                background_groups[background_group*16+:16]<=color_buf[background_group*64+lane[1:0]*16+:16];
                depth_groups[background_group*16+:16]<=z_buf[background_group*64+lane[1:0]*16+:16];
            end
        end
    end endgenerate
    // Explicit legal-state enables avoid the priority decode of unrelated
    // command states on the 256-bit DDR write-data register.
    always @(posedge clk)begin
        if(rst)wr_data<=0;
        else if(state[CLEAR_PREP])wr_data<={16{clearing_depth ? clear_depth:clear_color}};
        else if(state[COLOR_WRITE] && pixel_mask!=32'hffffffff)wr_data<=color_buf;
        else if(state[Z_WRITE])wr_data<=z_buf;
    end
    // The four interpolators only change at span setup and pixel retirement.
    // Unrelated texture-loading states must not drive their shared enable.
    always @(posedge clk)begin
        if(rst)begin u<=0;v<=0;z<=0;q<=0;end
        else if(state[SPAN2])begin u<=origin_u+yu;v<=origin_v+yv;z<=origin_z+yz;q<=origin_q+yq;end
        else if(state[PIX_STORE])begin u<=u+ux;v<=v+vx;z<=z+zx;q<=q+qx;end
    end
    always @(posedge clk) begin
        if(rst)begin
            state<=35'b1 << (IDLE);done<=0;valid<=0;write<=0;addr<=0;wr_mask<=-1;
            configured<=0;texture_valid<=0;plane_valid<=0;rejected<=0;fragments<=0;passed<=0;
            color_page<=0;z_page<=0;flags<=0;alpha<=256;solid<=0;
            q0<=0;qx<=0;qy<=0;u0<=0;v0<=0;z0<=0;ux<=0;uy<=0;vx<=0;vy<=0;zx<=0;zy<=0;
            px<=0;py<=0;span_left<=0;row_offset<=0;
            color_addr<=0;z_addr<=0;chunk_count<=0;chunk_left<=0;lane<=0;
            source_pixel<=0;background<=0;depth<=0;
            sample_inside<=0;sample_depth_ok<=0;visible<=0;mix_r<=0;mix_g<=0;mix_b<=0;
            tw<=0;th<=0;mode_u<=0;mode_v<=0;texture_page<=0;texture_x<=0;texture_y<=0;
            load_x<=0;load_y<=0;load_left<=0;load_lane<=0;texture_row<=0;
            triangle_start<=0;clear_flags<=0;clearing_depth<=0;clear_color<=0;clear_depth<=0;clear_block<=0;
        end else begin
            done<=0;triangle_start<=0;
            case(1'b1) // synthesis parallel_case
            state[IDLE]:if(start)begin
                case(w0[31:24])
                14:begin
                    configured<=state_words_ready;
                    color_page<=w1[3:0];z_page<=w1[7:4];flags<=w2[4:0];alpha<=w3[8:0];solid<=w4[15:0];
                    state<=35'b1 << (state_words_ready ? FINISH:BAD);
                end
                15:begin
                    texture_valid<=0;tw<=w3[23:16];th<=w3[7:0];mode_u<=w4[1:0];mode_v<=w4[3:2];
                    texture_page<=w1[3:0];texture_x<=w2[25:16];texture_y<=w2[9:0];
                    load_x<=0;load_y<=0;state<=35'b1 << (tex_words_ready ? TEX_ADDR:BAD);
                end
                16:begin u0<=signed_plane_origin;ux<=w2;uy<=w3;plane_valid[0]<=plane_words_ready;state<=35'b1 << (plane_words_ready ? FINISH:BAD);end
                17:begin v0<=signed_plane_origin;vx<=w2;vy<=w3;plane_valid[1]<=plane_words_ready;state<=35'b1 << (plane_words_ready ? FINISH:BAD);end
                18:begin z0<=depth_plane_origin;zx<=w2;zy<=w3;plane_valid[2]<=plane_words_ready;state<=35'b1 << (plane_words_ready ? FINISH:BAD);end
                21:begin q0<=signed_plane_origin;qx<=w2;qy<=w3;plane_valid[3]<=plane_words_ready;state<=35'b1 << (plane_words_ready ? FINISH:BAD);end
                19:begin
                    if(!configured || !triangle_words_ready ||
                       (flags[0] && (!texture_valid || plane_valid[1:0]!=3)) ||
                       ((flags[1] || flags[2]) && !plane_valid[2]) || (flags[4] && !plane_valid[3]))state<=35'b1 << (BAD);
                    else state<=35'b1 << (alpha==0 ? FINISH:TRI_START);
                end
                20:begin
                    clear_flags<=w1[1:0];clear_color<=w2[15:0];clear_depth<=w3[15:0];
                    clear_block<=0;clearing_depth<=!w1[0];
                    state<=35'b1 << (!configured || !clear_words_ready ? BAD:
                        w1[1:0]==0 ? FINISH:CLEAR_PREP);
                end
                default:state<=35'b1 << (BAD);
                endcase
            end
            state[BAD]:begin rejected<=rejected+1'b1;state<=35'b1 << (FINISH);end
            state[FINISH]:begin done<=1;state<=35'b1 << (IDLE);end
            state[TEX_ADDR]:begin
                texture_scan_y<={1'b0,texture_y}+{4'b0,load_y};
                state<=35'b1 << (TEX_OFFSET);
            end
            state[TEX_OFFSET]:begin
                texture_offset<=texture_scan_y*(WIDTH*2);
                state<=35'b1 << (TEX_BASE);
            end
            state[TEX_BASE]:begin
                texture_row<=25'h0800000+{1'b0,texture_page,20'b0}+texture_offset+{14'd0,texture_x,1'b0};
                load_x<=0;load_left<=tw;state<=35'b1 << (TEX_NEXT);
            end
            state[TEX_NEXT]:begin
                addr<={6'b0,texture_row[24:5],3'b0};load_lane<=texture_row[4:1];
                valid<=1;write<=0;state<=35'b1 << (TEX_REQ);
            end
            state[TEX_REQ]:if(ready)begin valid<=0;state<=35'b1 << (TEX_WAIT);end
            state[TEX_WAIT]:if(rd_valid)begin state<=35'b1 << (TEX_COPY);end
            state[TEX_COPY]:begin
                load_x<=load_x+1'b1;load_left<=load_left-1'b1;load_lane<=load_lane+1'b1;
                if(load_left==1)begin
                    if({1'b0,load_y}+8'd1==th)begin texture_valid<=1;state<=35'b1 << (FINISH);end
                    else begin load_y<=load_y+1'b1;state<=35'b1 << (TEX_ADDR);end
                end else if(load_lane==15)begin
                    texture_row<={texture_row[24:5]+20'd1,5'b0};state<=35'b1 << (TEX_NEXT);
                end
            end
            state[TRI_START]:begin triangle_start<=1;state<=35'b1 << (TRI_BOOT);end
            state[TRI_BOOT]:state<=35'b1 << (TRI_WAIT);
            state[TRI_WAIT]:begin
                if(triangle_valid)begin px<=triangle_x;py<=triangle_y;span_left<=triangle_width;state<=35'b1 << (SPAN0);end
                else if(!triangle_busy)state<=35'b1 << (FINISH);
            end
            state[SPAN0]:begin row_offset<=py*(WIDTH*2);state<=35'b1 << (SPAN1);end
            state[SPAN1]:state<=35'b1 << (SPAN2);
            state[SPAN2]:state<=35'b1 << (CHUNK);
            state[CHUNK]:begin
                color_addr<=(29'h0800000+{5'd0,color_page,20'd0}+row_offset+({18'd0,px}<<1))>>2;
                z_addr<=(29'h0800000+{5'd0,z_page,20'd0}+row_offset+({18'd0,px}<<1))>>2;
                lane<=px[3:0];chunk_count<=span_left>{6'd0,room} ? room:span_left[4:0];
                chunk_left<=span_left>{6'd0,room} ? room:span_left[4:0];
                state<=35'b1 << (COLOR_REQ);
            end
            state[COLOR_REQ]:begin
                if(alpha!=256)begin addr<={color_addr[28:3],3'b0};valid<=1;write<=0;state<=35'b1 << (COLOR_WAIT);end
                else state<=35'b1 << (Z_PREP);
            end
            state[COLOR_WAIT]:begin
                if(valid && ready)valid<=0;
                if(rd_valid)begin state<=35'b1 << (Z_PREP);end
            end
            state[Z_PREP]:begin
                if(flags[1])begin addr<={z_addr[28:3],3'b0};valid<=1;write<=0;state<=35'b1 << (Z_WAIT);end
                else state<=35'b1 << (PIX_PRIME);
            end
            state[Z_WAIT]:begin
                if(valid && ready)valid<=0;
                if(rd_valid)begin state<=35'b1 << (PIX_PRIME);end
            end
            state[PIX_PRIME]:if(!flags[4] || per_ready[per_select])state<=35'b1 << (PIX_SAMPLE);
            state[PIX_SAMPLE]:begin
                depth<=z[31:16];sample_depth_ok<=z>=0 && z<48'sh000100000000;
                sample_inside<=!flags[0] || texture_inside;state<=35'b1 << (PIX_TEST);
            end
            state[PIX_TEST]:begin
                source_pixel<=sampled_source;
                background<=sampled_background;
                visible<=sample_inside && !(flags[3] && sampled_source==0) &&
                    (!(flags[1] || flags[2]) || sample_depth_ok) &&
                    (!flags[1] || depth<sampled_depth);
                fragments<=fragments+1'b1;state<=35'b1 << (PIX_BLEND);
            end
            state[PIX_BLEND]:begin
                mix_r<=source_pixel[15:11]*alpha+background[15:11]*inverse_alpha+15'd128;
                mix_g<=source_pixel[10:5]*alpha+background[10:5]*inverse_alpha+15'd128;
                mix_b<=source_pixel[4:0]*alpha+background[4:0]*inverse_alpha+15'd128;
                state<=35'b1 << (PIX_STORE);
            end
            state[PIX_STORE]:begin
                if(visible)begin
                    passed<=passed+1'b1;
                end
                lane<=lane+1'b1;chunk_left<=chunk_left-1'b1;
                state<=35'b1 << (chunk_left==1 ? COLOR_WRITE:PIX_PRIME);
            end
            state[COLOR_WRITE]:begin
                if(pixel_mask==32'hffffffff)state<=35'b1 << (ADVANCE);
                else begin
                    addr<={color_addr[28:3],3'b0};wr_mask<=pixel_mask;
                    valid<=1;write<=1;state<=35'b1 << (COLOR_SENT);
                end
            end
            state[COLOR_SENT]:if(ready)begin valid<=0;state<=35'b1 << (flags[2] ? Z_WRITE:ADVANCE);end
            state[Z_WRITE]:begin
                addr<={z_addr[28:3],3'b0};wr_mask<=pixel_mask;
                valid<=1;write<=1;state<=35'b1 << (Z_SENT);
            end
            state[Z_SENT]:if(ready)begin valid<=0;state<=35'b1 << (ADVANCE);end
            state[ADVANCE]:begin
                px<=px+chunk_count;span_left<=span_left-chunk_count;
                state<=35'b1 << (span_left=={6'd0,chunk_count} ? TRI_WAIT:CHUNK);
            end
            state[CLEAR_PREP]:begin
                addr<=29'h0200000+{7'd0,(clearing_depth ? z_page:color_page),18'd0}+{10'd0,clear_block,3'b0};
                wr_mask<=0;
                valid<=1;write<=1;state<=35'b1 << (CLEAR_SEND);
            end
            state[CLEAR_SEND]:if(ready)begin valid<=0;state<=35'b1 << (CLEAR_NEXT);end
            state[CLEAR_NEXT]:begin
                clear_block<=clear_block+1'b1;
                if(clear_block==WIDTH*HEIGHT/16-1)begin
                    if(!clearing_depth && clear_flags[1])begin clearing_depth<=1;clear_block<=0;state<=35'b1 << (CLEAR_PREP);end
                    else state<=35'b1 << (FINISH);
                end else state<=35'b1 << (CLEAR_PREP);
            end
            default:begin valid<=0;state<=35'b1 << (BAD);end
            endcase
        end
    end
endmodule
`default_nettype wire
