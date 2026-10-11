// Geometry frontend, ABI G3D1. Camera-space Q16.16, indexed DDR meshes.
// Transform/cache -> six-plane clipping -> projection -> lighting -> raster planes.
// The existing GPU V1 remains the pixel engine; no CPU-generated raster planes.
`default_nettype none
module gpu_geometry_reference(
 input wire clk,rst,start,input wire [255:0] command,
 output reg done,output wire busy,
 output wire [31:0] rejected,fragments,passed,texture_hits,texture_misses,
 output reg [31:0] geom_errors,vertices,triangles,culled,clipped,slivers,geom_cycles,
 output wire valid,write,output wire [28:0] addr,output wire [255:0] wr_data,output wire [31:0] wr_mask,
 input wire ready,rd_valid,input wire [255:0] rd_data
);
 localparam IDLE=0,PASS=1,FINISH=2,FAIL=3,CAM_DIV=4,CAM_WAIT=5,
  V_REQ=6,V_WAIT=7,V_MUL=8,V_SUM=9,V_STORE=10,F_REQ=11,F_WAIT=12,
  F_CACHE=13,F_COPY=14,L_MUL=15,L_SUM=16,CL_INIT=17,CL_DIST=18,CL_EDGE=19,
  CL_DIV=20,CL_WAIT=21,CL_INTER=22,CL_CURRENT=23,CL_NEXT=24,CL_PLANE=25,
  PROJ_DIV=26,PROJ_WAIT=27,PROJ_MUL=28,PROJ_STORE=29,
  TRI_INIT=30,TRI_AREA=31,MAT_SEND=32,MAT_WAIT=33,PL_INIT=34,PL_NUM=35,
  PL_DIV=36,PL_WAIT=37,PL_ORIGIN=38,PL_SEND=39,PL_SENT=40,TRI_SEND=41,TRI_WAIT=42,
  TRI_NEXT=43,F_NEXT=44,RESTORE=45,RESTORED=46,SLIVER_DIV=47,SLIVER_WAIT=48,
  TRI_DIFF=49,TRI_MUL=50,PL_DIFF=51,PL_MUL=52,ORIGIN_MUL=53,ORIGIN_SUM=54,
  CL_PRODUCT=55,CL_DISTANCE=56,CL_MULT=57,CL_STORE=58,L_ADD=59,V_PAIR=60,
  CL_READ=61,PROJ_READ=62,V_BOUNDS_MUL=63,V_BOUNDS_X=64,V_BOUNDS_Y=65,V_BOUNDS_SAVE=66,DECODE=67,PROJ_NORMALIZE=68,PROJ_LAUNCH=69;
 // One bit per state avoids high-fanout binary decode across the DSP/RAM datapath.
 reg [69:0] state;
 reg [255:0] captured_command;
 reg [32:0] mesh_vertex_end,mesh_face_end;
 wire [31:0] w0=captured_command[31:0],w1=captured_command[63:32],w2=captured_command[95:64],w3=captured_command[127:96],
  w4=captured_command[159:128],w5=captured_command[191:160],w6=captured_command[223:192],w7=captured_command[255:224];
 reg shader_start;reg [255:0] shader_command;
 wire shader_done,shader_valid,shader_write,shader_target_valid,shader_material_valid;wire [28:0] shader_addr;
 wire [255:0] shader_data;wire [31:0] shader_mask,shader_rejected;
 reg fetch_valid;reg [28:0] fetch_addr;
 assign busy=!state[IDLE];
 assign valid=fetch_valid||shader_valid;assign write=shader_valid&&shader_write;
 assign addr=fetch_valid ? fetch_addr:shader_addr;
 assign wr_data=shader_data;assign wr_mask=shader_mask;
 assign rejected=geom_errors+shader_rejected;
 gpu_v1_reference u_pixels(.clk(clk),.rst(rst),.start(shader_start),.command(shader_command),.done(shader_done),.busy(),
  .target_config_valid(shader_target_valid),.material_config_valid(shader_material_valid),
  .rejected(shader_rejected),.fragments(fragments),.passed(passed),.texture_hits(texture_hits),.texture_misses(texture_misses),
  .valid(shader_valid),.write(shader_write),.addr(shader_addr),.wr_data(shader_data),.wr_mask(shader_mask),
  .ready(ready&&!fetch_valid),.rd_valid(rd_valid&&(state[PASS]||state[MAT_WAIT]||state[PL_SENT]||state[TRI_WAIT]||state[RESTORED])),.rd_data(rd_data));
 reg signed [31:0] matrix[0:11],coefficient[0:3];reg [2:0] matrix_valid;
 reg camera_valid,material_valid,draw_active;reg [15:0] target_w,target_h,width,height,cx,cy;
 reg signed [31:0] near_z,far_z,fx,fy,ratio[0:3];
 reg signed [15:0] light_x,light_y,light_z;reg [8:0] ambient,diffuse;
 reg [255:0] material,face;
 reg [31:0] vb,fb;reg [15:0] nv,nf,vi,fi;reg cull_enable;
 reg signed [31:0] vx[0:255],vy[0:255],vz[0:255];
 reg [5:0] vertex_code[0:255] /* synthesis syn_ramstyle="block_ram" */;
 reg [5:0] cached_code,face_code,bounds_code;
 reg bounds_y;
 reg signed [63:0] bounds_product0,bounds_product1;
 wire signed [31:0] bounds_ratio0=bounds_y ? ratio[2]:ratio[0];
 wire signed [31:0] bounds_ratio1=bounds_y ? ratio[3]:ratio[1];
 reg signed [31:0] position[0:2],transformed[0:2],cached_x,cached_y,cached_z;
 reg [1:0] row,corner;reg [2:0] cam_index;
 reg signed [63:0] mul0,mul1,mul2,sum64;
 reg signed [31:0] light_product[0:2];
 wire signed [33:0] light_total=$signed(light_product[0])+$signed(light_product[1])+$signed(light_product[2]);
 reg signed [17:0] light_dot;
 reg [7:0] cache_index;
 // At most nine vertices after clipping a triangle against six planes.
 // Two banks keep every edge's input stable while its outputs are appended.
 reg [4:0] src_base,dst_base,previous,current,npoly,nout,project_index;
 reg [2:0] plane;
 reg signed [47:0] dp,dc;
 // CL_WAIT admits only 0..65536. Preserve that exact range in the DSP operand.
 reg signed [17:0] fraction;
 reg signed [31:0] clip_z0,clip_z1,clip_ratio,clip_a[0:4];
 reg signed [32:0] clip_side0,clip_side1,clip_delta[0:4];
 reg signed [63:0] clip_product[0:4];
 reg [15:0] screen_x[0:11],screen_y[0:11],screen_z[0:11];
 reg [23:0] screen_q[0:11];reg signed [15:0] screen_u[0:11],screen_v[0:11];
 reg [15:0] triangle_z[0:2];reg [23:0] triangle_q[0:2];
 reg signed [15:0] triangle_u[0:2],triangle_v[0:2];
 reg [23:0] recip;reg signed [63:0] proj_x,proj_y,depth_mul;
 reg signed [31:0] projection_x,projection_y,normalized_x,normalized_y;
 reg signed [15:0] projection_u,projection_v;
 wire signed [63:0] projected_x=(proj_x>>>32)+$signed({1'b0,cx});
 wire signed [63:0] projected_y=(proj_y>>>32)+$signed({1'b0,cy});
 reg [3:0] fan,attr;reg [6:0] plane_mask;
 reg signed [31:0] tx[0:2],ty[0:2];reg signed [63:0] value[0:2];
 reg signed [31:0] area,dx,dy;reg signed [63:0] numx,numy,origin;
 // Clipped viewport is at most 1024x512: differences fit signed 12/11 bits.
 reg signed [11:0] ex1,ex2;
 reg signed [10:0] ey1,ey2;
 // Screen coordinates are unsigned 16-bit after viewport clipping. UV*q is
 // signed 16*unsigned 24; its difference fits 41 bits without losing precision.
 reg signed [40:0] dv1,dv2;
 reg signed [52:0] gradient_product[0:3];
 // Dedicated registered products avoid a DSP -> carry chain -> shared
 // product-register mux in one cycle (G13: -2.546 ns). PL_DIFF updates the
 // operands, PL_MUL lets these registers settle, PL_NUM consumes them.
 always @(posedge clk)begin
  gradient_product[0]<=dv1*ey2;gradient_product[1]<=dv2*ey1;
  gradient_product[2]<=ex1*dv2;gradient_product[3]<=ex2*dv1;
 end
 reg signed [63:0] product[0:3];reg signed [32:0] midpoint;
 // True dual-port polygon memory: port A is read/write, port B is read-only.
 // A registered read stage replaces five large, multiply indexed register
 // arrays. The two 12-vertex banks share a single 160-bit record per vertex.
 reg [159:0] polygon[0:31] /* synthesis syn_ramstyle="block_ram" */;
 reg [159:0] poly_a,poly_b;
 wire projecting=state[PROJ_READ]||state[PROJ_DIV]||state[PROJ_LAUNCH]||state[PROJ_WAIT]||state[PROJ_NORMALIZE]||state[PROJ_MUL]||state[PROJ_STORE];
 wire poly_we=!rst&&(state[F_COPY]||state[CL_STORE]||(state[CL_CURRENT]&&!dc[47]&&nout<12));
 wire [4:0] poly_wa=state[F_COPY] ? {3'b0,corner}:dst_base+nout;
 wire [4:0] poly_ra=projecting ? src_base+project_index:src_base+previous;
 wire [4:0] poly_aa=poly_we ? poly_wa:poly_ra;
 wire [4:0] poly_ba=src_base+current;
 wire signed [31:0] ax=poly_a[31:0],ay=poly_a[63:32],az=poly_a[95:64],au=poly_a[127:96],av=poly_a[159:128];
 wire signed [31:0] bx=poly_b[31:0],by=poly_b[63:32],bz=poly_b[95:64],bu=poly_b[127:96],bv=poly_b[159:128];
 wire signed [31:0] ix=clip_a[0]+(clip_product[0]>>>16),iy=clip_a[1]+(clip_product[1]>>>16),iz=clip_a[2]+(clip_product[2]>>>16),
  iu=clip_a[3]+(clip_product[3]>>>16),iv=clip_a[4]+(clip_product[4]>>>16);
 wire [159:0] poly_wdata=state[F_COPY] ? {face[32+corner*32+:16],16'b0,face[48+corner*32+:16],16'b0,cached_z,cached_y,cached_x}:
  state[CL_STORE] ? {iv,iu,iz,iy,ix}:poly_b;
 always @(posedge clk)begin
  // GW5AST DPX9B supports write-through/normal mode, not read-before-write.
  // Port A's output is unused after a write (F_COPY, CL_STORE, CL_CURRENT).
  if(poly_we)begin polygon[poly_aa]<=poly_wdata;poly_a<=poly_wdata;end
  else poly_a<=polygon[poly_aa];
 end
 always @(posedge clk)poly_b<=polygon[poly_ba];
 reg [26:0] gains;reg [8:0] illumination;
 reg div_start;reg signed [63:0] dividend0,dividend1,divisor;
 wire div_done0,div_done1,div_bad0,div_bad1;wire signed [63:0] quotient0,quotient1;
 gpu_geom_div_reference u_divx(.clk(clk),.rst(rst),.start(div_start),.numerator(dividend0),.denominator(divisor),.busy(),.done(div_done0),.invalid(div_bad0),.quotient(quotient0));
 gpu_geom_div_reference u_divy(.clk(clk),.rst(rst),.start(div_start),.numerator(dividend1),.denominator(divisor),.busy(),.done(div_done1),.invalid(div_bad1),.quotient(quotient1));
 function [8:0] gain;
  input [8:0] c,l;reg [17:0] p;
  begin p=c*l+18'd128;gain=p[17:8];end
 endfunction
 function signed [63:0] attribute_value;
  input [3:0] k,v;
  begin case(k)
   0:attribute_value=$signed(triangle_u[v])*(material[36] ? $signed({1'b0,triangle_q[v]}):32'sd65536);
   1:attribute_value=$signed(triangle_v[v])*(material[36] ? $signed({1'b0,triangle_q[v]}):32'sd65536);
   2:attribute_value=$signed({1'b0,triangle_q[v]});
   default:attribute_value=$signed({1'b0,triangle_z[v],16'b0});
  endcase end
 endfunction
 integer j;
 always @(posedge clk)begin
  shader_start<=0;div_start<=0;done<=0;
  if(rst)begin
   state<=70'b1<<(IDLE);fetch_valid<=0;shader_start<=0;div_start<=0;done<=0;
   matrix_valid<=0;camera_valid<=0;material_valid<=0;draw_active<=0;target_w<=0;target_h<=0;
   geom_errors<=0;vertices<=0;triangles<=0;culled<=0;clipped<=0;slivers<=0;geom_cycles<=0;
   ambient<=256;diffuse<=0;light_x<=0;light_y<=0;light_z<=0;
   shader_command<=0;material<=0;fetch_addr<=0;
  end else begin
   if(!state[IDLE]&&!state[PASS])geom_cycles<=geom_cycles+1'b1;
   case(1'b1) // synthesis parallel_case
    state[IDLE]:if(start)begin
     // Separate the distant command FIFO and address sums from validation.
     captured_command<=command;
     mesh_vertex_end<={1'b0,command[63:32]}+{12'b0,command[127:112],5'b0};
     mesh_face_end<={1'b0,command[95:64]}+{12'b0,command[111:96],5'b0};
     state<=70'b1<<(DECODE);
    end
    state[DECODE]:begin
     if(w0[31:24]<31)begin
      shader_command<=captured_command;shader_start<=1;state<=70'b1<<(PASS);
      if(w0[31:24]==22)begin target_w<=w3[31:16];target_h<=w3[15:0];camera_valid<=0;end
      if(w0[31:24]==25)begin material<=captured_command;material_valid<=0;end
     end else case(w0[31:24])
      31:begin
       if(w0[23:0]!=0||w1>2||w6!=0||w7!=0)state<=70'b1<<(FAIL);
       else begin matrix[w1*4]<=w2;matrix[w1*4+1]<=w3;matrix[w1*4+2]<=w4;matrix[w1*4+3]<=w5;matrix_valid[w1]<=1;state<=70'b1<<(FINISH);end
      end
      32:begin
       camera_valid<=0;
       if(w0[23:0]!=0||$signed(w1)<4096||$signed(w2)<=$signed(w1)||$signed(w3)<65536||$signed(w4)<65536||
        w3>32'h10000000||w4>32'h10000000||w5[31:16]>w6[31:16]||w5[15:0]>w6[15:0]||
        !w6[31:16]||w6[31:16]>1024||!w6[15:0]||w6[15:0]>512||w6!={target_w,target_h}||w7!=0)state<=70'b1<<(FAIL);
       else begin near_z<=w1;far_z<=w2;fx<=w3;fy<=w4;cx<=w5[31:16];cy<=w5[15:0];width<=w6[31:16];height<=w6[15:0];cam_index<=0;state<=70'b1<<(CAM_DIV);end
      end
      33:begin
       if(w0[23:0]!=0||w2[31:16]!=0||w3[15:0]>256||w3[31:16]>256||w4!=0||w5!=0||w6!=0||w7!=0)state<=70'b1<<(FAIL);
       else begin light_x<=w1[31:16];light_y<=w1[15:0];light_z<=w2[15:0];ambient<=w3[8:0];diffuse<=w3[24:16];state<=70'b1<<(FINISH);end
      end
      34:begin
       if(w0[23:0]!=0||matrix_valid!=7||!camera_valid||!material_valid||(w1&31)||(w2&31)||
        w3[31:16]==0||w3[31:16]>256||w3[15:0]==0||
        mesh_vertex_end>33'h020000000||mesh_face_end>33'h020000000||
        w4>1||w5!=0||w6!=0||w7!=0)state<=70'b1<<(FAIL);
       else begin vb<=w1;fb<=w2;nv<=w3[31:16];nf<=w3[15:0];vi<=0;fi<=0;cull_enable<=w4[0];draw_active<=1;state<=70'b1<<(V_REQ);end
      end
      default:state<=70'b1<<(FAIL);
     endcase
    end
    state[PASS]:if(shader_done)begin
     // Use the pixel engine's complete descriptor validation, including
     // headers/reserved bits. Lighting must never sanitize an invalid tint.
     if(w0[31:24]==25)material_valid<=shader_material_valid&&!w1[6];
     if(w0[31:24]==22&&!shader_target_valid)begin target_w<=0;target_h<=0;camera_valid<=0;end
     state<=70'b1<<(FINISH);
    end
    state[FAIL]:begin
     geom_errors<=geom_errors+1'b1;fetch_valid<=0;
     // A preceding face may have changed the pixel engine's tint. Keep the
     // public material contract even when a later mesh face is malformed.
     state<=70'b1<<(draw_active ? RESTORE:FINISH);
    end
    state[FINISH]:begin done<=1;state<=70'b1<<(IDLE);end
    state[CAM_DIV]:begin
     dividend0<=$signed({16'b0,(cam_index==0 ? cx:cam_index==1 ? width-cx:cam_index==2 ? cy:height-cy),32'b0});
     dividend1<=0;divisor<=cam_index<2 ? fx:fy;div_start<=1;state<=70'b1<<(CAM_WAIT);
    end
    state[CAM_WAIT]:if(div_done0)begin
     if(div_bad0||quotient0>524288)state<=70'b1<<(FAIL);
     else begin ratio[cam_index]<=quotient0[31:0];if(cam_index==3)begin camera_valid<=1;state<=70'b1<<(FINISH);end else begin cam_index<=cam_index+1'b1;state<=70'b1<<(CAM_DIV);end end
    end
    state[V_REQ]:begin fetch_addr<=(vb+{vi,5'b0})>>2;fetch_valid<=1;state<=70'b1<<(V_WAIT);end
    state[V_WAIT]:begin
     if(fetch_valid&&ready)fetch_valid<=0;
     if(rd_valid)begin
      if(rd_data[255:96]!=0)state<=70'b1<<(FAIL);
      else begin
       position[0]<=rd_data[31:0];position[1]<=rd_data[63:32];position[2]<=rd_data[95:64];row<=0;
       for(j=0;j<4;j=j+1)coefficient[j]<=matrix[j];
       state<=70'b1<<(V_MUL);
      end
     end
    end
    state[V_MUL]:begin mul0<=coefficient[0]*position[0];mul1<=coefficient[1]*position[1];mul2<=coefficient[2]*position[2];state<=70'b1<<(V_PAIR);end
    state[V_PAIR]:begin product[0]<=(mul0>>>16)+(mul1>>>16);product[1]<=(mul2>>>16)+$signed(coefficient[3]);state<=70'b1<<(V_SUM);end
    state[V_SUM]:begin sum64<=product[0]+product[1];state<=70'b1<<(V_STORE);end
    state[V_STORE]:begin
     if(sum64>2147483647||sum64< -64'sd2147483648)state<=70'b1<<(FAIL);
     else begin
      transformed[row]<=sum64[31:0];
      if(row==0)vx[vi[7:0]]<=sum64[31:0];if(row==1)vy[vi[7:0]]<=sum64[31:0];if(row==2)vz[vi[7:0]]<=sum64[31:0];
      if(row==2)begin bounds_y<=0;state<=70'b1<<(V_BOUNDS_MUL);end
      else begin
       // Select the next row while storing this one, before the DSP products.
       for(j=0;j<4;j=j+1)coefficient[j]<=row==0 ? matrix[4+j]:matrix[8+j];
       row<=row+1'b1;state<=70'b1<<(V_MUL);
      end
     end
    end
    state[V_BOUNDS_MUL]:begin
     bounds_product0<=transformed[2]*bounds_ratio0;bounds_product1<=transformed[2]*bounds_ratio1;
     state<=70'b1<<(bounds_y ? V_BOUNDS_Y:V_BOUNDS_X);
    end
    state[V_BOUNDS_X]:begin
     bounds_code[0]<=transformed[2]<near_z;bounds_code[1]<=transformed[2]>far_z;
     bounds_code[2]<=((bounds_product0>>>16)+$signed(transformed[0]))<0;
     bounds_code[3]<=((bounds_product1>>>16)-$signed(transformed[0]))<0;
     bounds_y<=1;state<=70'b1<<(V_BOUNDS_MUL);
    end
    state[V_BOUNDS_Y]:begin
     bounds_code[4]<=((bounds_product0>>>16)+$signed(transformed[1]))<0;
     bounds_code[5]<=((bounds_product1>>>16)-$signed(transformed[1]))<0;
     state<=70'b1<<(V_BOUNDS_SAVE);
    end
    state[V_BOUNDS_SAVE]:begin
     vertex_code[vi[7:0]]<=bounds_code;vertices<=vertices+1'b1;
     if(vi+1==nv)state<=70'b1<<(F_REQ);else begin vi<=vi+1'b1;state<=70'b1<<(V_REQ);end
    end
    state[F_REQ]:begin fetch_addr<=(fb+{fi,5'b0})>>2;fetch_valid<=1;state<=70'b1<<(F_WAIT);end
    state[F_WAIT]:begin
     if(fetch_valid&&ready)fetch_valid<=0;
     if(rd_valid)begin
      face<=rd_data;
      if(rd_data[7:0]>=nv||rd_data[15:8]>=nv||rd_data[23:16]>=nv||rd_data[31:26]!=0||rd_data[255:224]!=0||rd_data[223:219]!=0||rd_data[191:176]!=0||
       rd_data[200:192]>256||rd_data[209:201]>256||rd_data[218:210]>256)state<=70'b1<<(FAIL);
      else begin corner<=0;face_code<=0;cache_index<=rd_data[7:0];state<=70'b1<<(F_CACHE);end
     end
    end
    state[F_CACHE]:begin cached_x<=vx[cache_index];cached_y<=vy[cache_index];cached_z<=vz[cache_index];cached_code<=vertex_code[cache_index];state<=70'b1<<(F_COPY);end
    state[F_COPY]:begin
     face_code<=face_code|cached_code;
     if(corner==2)state<=70'b1<<(L_MUL);else begin corner<=corner+1'b1;cache_index<=face[(corner+1)*8+:8];state<=70'b1<<(F_CACHE);end
    end
    state[L_MUL]:begin light_product[0]<=$signed(face[159:144])*$signed(light_x);light_product[1]<=$signed(face[143:128])*$signed(light_y);light_product[2]<=$signed(face[175:160])*$signed(light_z);state<=70'b1<<(L_ADD);end
    state[L_ADD]:begin light_dot<=light_total>>>15;state<=70'b1<<(L_SUM);end
    state[L_SUM]:begin
     sum64<=light_dot*$signed({1'b0,diffuse});state<=70'b1<<(CL_INIT);
    end
    state[CL_INIT]:begin
     if(face[24])illumination<=256;
     else if(sum64<0)illumination<=ambient;
     else if((sum64>>>15)+ambient>256)illumination<=256;
     else illumination<=(sum64>>>15)+ambient;
     src_base<=0;dst_base<=12;npoly<=3;nout<=0;previous<=2;current<=0;plane<=0;project_index<=0;
     // Convex frustum: three inside vertices imply an entirely inside triangle.
     // Outside triangles retain the original six-plane path and exact counters.
     state<=70'b1<<(face_code==0 ? PROJ_READ:CL_DIST);
    end
    state[CL_DIST]:state<=70'b1<<(CL_READ);
    state[CL_READ]:begin
     clip_z0<=az;clip_z1<=bz;
     clip_ratio<=plane>=2 ? ratio[plane-2]:0;
     case(plane)
      2:begin clip_side0<=ax;clip_side1<=bx;end
      3:begin clip_side0<=-$signed({ax[31],ax});clip_side1<=-$signed({bx[31],bx});end
      4:begin clip_side0<=ay;clip_side1<=by;end
      default:begin clip_side0<=-$signed({ay[31],ay});clip_side1<=-$signed({by[31],by});end
     endcase
     state<=70'b1<<(CL_PRODUCT);
    end
    state[CL_PRODUCT]:begin product[0]<=clip_z0*clip_ratio;product[1]<=clip_z1*clip_ratio;state<=70'b1<<(CL_DISTANCE);end
    state[CL_DISTANCE]:begin
     case(plane)
      0:begin dp<=$signed(clip_z0)-$signed(near_z);dc<=$signed(clip_z1)-$signed(near_z);end
      1:begin dp<=$signed(far_z)-$signed(clip_z0);dc<=$signed(far_z)-$signed(clip_z1);end
      default:begin dp<=(product[0]>>>16)+clip_side0;dc<=(product[1]>>>16)+clip_side1;end
     endcase
     state<=70'b1<<(CL_EDGE);
    end
    state[CL_EDGE]:begin
     if(dp!=0&&dc!=0&&dp[47]!=dc[47])state<=70'b1<<(CL_DIV);
     else state<=70'b1<<(CL_CURRENT);
    end
    state[CL_DIV]:begin
     // Always interpolate from inside to outside. Opposite windings must
     // produce the same fixed-point intersection on a shared triangle edge.
     dividend0<=$signed(dp[47] ? dc:dp)<<<16;dividend1<=0;
     divisor<=dp[47] ? $signed(dc)-$signed(dp):$signed(dp)-$signed(dc);
     div_start<=1;state<=70'b1<<(CL_WAIT);
    end
    state[CL_WAIT]:if(div_done0)begin
     if(div_bad0||quotient0<0||quotient0>65536||nout>=11)state<=70'b1<<(FAIL);
     else begin fraction<=quotient0[17:0];clipped<=clipped+1'b1;state<=70'b1<<(CL_INTER);end
    end
    state[CL_INTER]:begin
     if(dp[47])begin
      clip_a[0]<=bx;clip_delta[0]<=$signed({ax[31],ax})-$signed({bx[31],bx});
      clip_a[1]<=by;clip_delta[1]<=$signed({ay[31],ay})-$signed({by[31],by});
      clip_a[2]<=bz;clip_delta[2]<=$signed({az[31],az})-$signed({bz[31],bz});
      clip_a[3]<=bu;clip_delta[3]<=$signed({au[31],au})-$signed({bu[31],bu});
      clip_a[4]<=bv;clip_delta[4]<=$signed({av[31],av})-$signed({bv[31],bv});
     end else begin
      clip_a[0]<=ax;clip_delta[0]<=$signed({bx[31],bx})-$signed({ax[31],ax});
      clip_a[1]<=ay;clip_delta[1]<=$signed({by[31],by})-$signed({ay[31],ay});
      clip_a[2]<=az;clip_delta[2]<=$signed({bz[31],bz})-$signed({az[31],az});
      clip_a[3]<=au;clip_delta[3]<=$signed({bu[31],bu})-$signed({au[31],au});
      clip_a[4]<=av;clip_delta[4]<=$signed({bv[31],bv})-$signed({av[31],av});
     end
     state<=70'b1<<(CL_MULT);
    end
    state[CL_MULT]:begin for(j=0;j<5;j=j+1)clip_product[j]<=clip_delta[j]*fraction;state<=70'b1<<(CL_STORE);end
    state[CL_STORE]:begin
     nout<=nout+1'b1;state<=70'b1<<(CL_CURRENT);
    end
    state[CL_CURRENT]:begin
     if(!dc[47])begin
      if(nout>=12)state<=70'b1<<(FAIL);
      else begin nout<=nout+1'b1;state<=70'b1<<(CL_NEXT);end
     end else state<=70'b1<<(CL_NEXT);
    end
    state[CL_NEXT]:begin
     if(current+1==npoly)state<=70'b1<<(CL_PLANE);
     else begin previous<=current;current<=current+1'b1;state<=70'b1<<(CL_DIST);end
    end
    state[CL_PLANE]:begin
     if(nout<3)begin culled<=culled+1'b1;state<=70'b1<<(F_NEXT);end
     else begin
      src_base<=dst_base;dst_base<=src_base;npoly<=nout;
      if(plane==5)begin project_index<=0;state<=70'b1<<(PROJ_READ);end
      else begin plane<=plane+1'b1;previous<=nout-1'b1;current<=0;nout<=0;state<=70'b1<<(CL_DIST);end
     end
    end
    state[PROJ_READ]:state<=70'b1<<(PROJ_DIV);
    state[PROJ_DIV]:begin
     dividend0<=64'h100000000;dividend1<=0;
     projection_x<=ax;projection_y<=ay;projection_u<=au>>>16;projection_v<=av>>>16;
     divisor<=az;state<=70'b1<<(PROJ_LAUNCH);
    end
    state[PROJ_LAUNCH]:begin
     // Capture the BRAM output before the near-plane comparison/mux.
     if(divisor<near_z)divisor<=near_z;
     div_start<=1;state<=70'b1<<(PROJ_WAIT);
    end
    state[PROJ_WAIT]:if(div_done0)begin
     if(div_bad0||quotient0<=0||quotient0>24'hffffff)state<=70'b1<<(FAIL);
     else begin recip<=quotient0[23:0];mul0<=projection_x*$signed(quotient0[31:0]);mul1<=projection_y*$signed(quotient0[31:0]);mul2<=$signed(near_z)*$signed(quotient0[31:0]);state<=70'b1<<(PROJ_NORMALIZE);end
    end
    state[PROJ_NORMALIZE]:begin
     // A clipped frustum ratio is bounded by 8. Check before narrowing so an
     // invalid internal position cannot silently wrap before projection.
     if((mul0>>>16)>2147483647||(mul0>>>16)< -64'sd2147483648||(mul1>>>16)>2147483647||(mul1>>>16)< -64'sd2147483648)state<=70'b1<<(FAIL);
     else begin normalized_x<=mul0>>>16;normalized_y<=mul1>>>16;depth_mul<=mul2>>>16;state<=70'b1<<(PROJ_MUL);end
    end
    state[PROJ_MUL]:begin proj_x<=normalized_x*fx;proj_y<=normalized_y*fy;state<=70'b1<<(PROJ_STORE);end
    state[PROJ_STORE]:begin
     // Final integer quantization is clamped to the viewport after clipping.
     if(projected_x<0)screen_x[project_index]<=0;
     else if(projected_x>$signed({1'b0,width}))screen_x[project_index]<=width;
     else screen_x[project_index]<=projected_x[15:0];
     if(projected_y<0)screen_y[project_index]<=0;
     else if(projected_y>$signed({1'b0,height}))screen_y[project_index]<=height;
     else screen_y[project_index]<=projected_y[15:0];
     screen_z[project_index]<=depth_mul>=65536 ? 0:((64'sd65536-depth_mul)*65534)>>16;
     screen_q[project_index]<=recip;
     screen_u[project_index]<=projection_u;screen_v[project_index]<=projection_v;
     if(project_index+1==npoly)begin fan<=1;state<=70'b1<<(TRI_INIT);end
     else begin project_index<=project_index+1'b1;state<=70'b1<<(PROJ_READ);end
    end
    state[TRI_INIT]:begin
     // Capture the three fan vertices before multiplying their attributes.
     // A dynamic 12-way vertex selection followed by UV*Q in one cycle
     // exceeded 18 ns on G3; these registers separate the two operations.
     triangle_u[0]<=screen_u[0];triangle_v[0]<=screen_v[0];triangle_q[0]<=screen_q[0];triangle_z[0]<=screen_z[0];
     triangle_u[1]<=screen_u[fan];triangle_v[1]<=screen_v[fan];triangle_q[1]<=screen_q[fan];triangle_z[1]<=screen_z[fan];
     triangle_u[2]<=screen_u[fan+1];triangle_v[2]<=screen_v[fan+1];triangle_q[2]<=screen_q[fan+1];triangle_z[2]<=screen_z[fan+1];
     tx[0]<=$signed({1'b0,screen_x[0]});ty[0]<=$signed({1'b0,screen_y[0]});
     tx[1]<=$signed({1'b0,screen_x[fan]});ty[1]<=$signed({1'b0,screen_y[fan]});
     tx[2]<=$signed({1'b0,screen_x[fan+1]});ty[2]<=$signed({1'b0,screen_y[fan+1]});
     gains<={gain(face[218:210],illumination),gain(face[209:201],illumination),gain(face[200:192],illumination)};
     state<=70'b1<<(TRI_DIFF);
    end
    state[TRI_DIFF]:begin
     ex1<=$signed({1'b0,tx[1][10:0]})-$signed({1'b0,tx[0][10:0]});
     ey1<=$signed({1'b0,ty[1][9:0]})-$signed({1'b0,ty[0][9:0]});
     ex2<=$signed({1'b0,tx[2][10:0]})-$signed({1'b0,tx[0][10:0]});
     ey2<=$signed({1'b0,ty[2][9:0]})-$signed({1'b0,ty[0][9:0]});state<=70'b1<<(TRI_MUL);
    end
    state[TRI_MUL]:begin product[0]<=ex1*ey2;product[1]<=ex2*ey1;state<=70'b1<<(TRI_AREA);end
    state[TRI_AREA]:begin area<=product[0]-product[1];state<=70'b1<<(MAT_SEND);end
    state[MAT_SEND]:begin
     if(area==0||(cull_enable&&!face[25]&&area>=0))begin culled<=culled+1'b1;state<=70'b1<<(TRI_NEXT);end
     else begin
      shader_command<=material;
      shader_command[159:128]<={5'b0,gain(material[154:146],gains[26:18]),gain(material[145:137],gains[17:9]),gain(material[136:128],gains[8:0])};
      shader_start<=1;attr<=0;
      plane_mask<=(material[32] ? 7'd3:7'd0)|(material[36] ? 7'd4:7'd0)|((material[63:32]&134)!=0 ? 7'd8:7'd0);
      state<=70'b1<<(MAT_WAIT);
     end
    end
    state[MAT_WAIT]:if(shader_done)state<=70'b1<<(PL_INIT);
    state[PL_INIT]:begin
     if(attr==4)state<=70'b1<<(TRI_SEND);
     else if(!plane_mask[attr])attr<=attr+1'b1;
     else begin
      value[0]<=attribute_value(attr,0);value[1]<=attribute_value(attr,1);value[2]<=attribute_value(attr,2);state<=70'b1<<(PL_DIFF);
     end
    end
    state[PL_DIFF]:begin dv1<=value[1]-value[0];dv2<=value[2]-value[0];state<=70'b1<<(PL_MUL);end
    state[PL_MUL]:state<=70'b1<<(PL_NUM);
    state[PL_NUM]:begin
     numx<=gradient_product[0]-gradient_product[1];numy<=gradient_product[2]-gradient_product[3];state<=70'b1<<(PL_DIV);
    end
    state[PL_DIV]:begin dividend0<=numx;dividend1<=numy;divisor<=area;div_start<=1;state<=70'b1<<(PL_WAIT);end
    state[PL_WAIT]:if(div_done0&&div_done1)begin
     if(div_bad0||div_bad1)state<=70'b1<<(FAIL);
     else if(quotient0>2147483647||quotient0< -64'sd2147483648||quotient1>2147483647||quotient1< -64'sd2147483648)begin
      // Explicitly counted constant-attribute approximation for raster slivers.
      dx<=0;dy<=0;slivers<=slivers+1'b1;state<=70'b1<<(SLIVER_DIV);
     end else begin dx<=quotient0[31:0];dy<=quotient1[31:0];state<=70'b1<<(ORIGIN_MUL);end
    end
    state[SLIVER_DIV]:begin dividend0<=value[0]+value[1]+value[2];dividend1<=0;divisor<=3;div_start<=1;state<=70'b1<<(SLIVER_WAIT);end
    state[SLIVER_WAIT]:if(div_done0)begin value[0]<=quotient0;state<=70'b1<<(ORIGIN_MUL);end
    state[ORIGIN_MUL]:begin
     product[0]<=dx*$signed({1'b0,tx[0][15:0]});product[1]<=dy*$signed({1'b0,ty[0][15:0]});
     midpoint<=($signed({dx[31],dx})+$signed({dy[31],dy}))/2;state<=70'b1<<(ORIGIN_SUM);
    end
    state[ORIGIN_SUM]:begin product[2]<=value[0]-product[0];product[3]<=product[1]-midpoint;state<=70'b1<<(PL_ORIGIN);end
    state[PL_ORIGIN]:begin origin<=product[2]-product[3];state<=70'b1<<(PL_SEND);end
    state[PL_SEND]:begin
     if(origin>64'sh7fffffffffff||origin< -64'sh800000000000)state<=70'b1<<(FAIL);
     else begin shader_command<={96'b0,16'b0,origin[47:32],dy,dx,origin[31:0],24'h1a0000,4'b0,attr};shader_start<=1;state<=70'b1<<(PL_SENT);end
    end
    state[PL_SENT]:if(shader_done)begin attr<=attr+1'b1;state<=70'b1<<(PL_INIT);end
    state[TRI_SEND]:begin shader_command<={128'b0,tx[2][15:0],ty[2][15:0],tx[1][15:0],ty[1][15:0],tx[0][15:0],ty[0][15:0],32'h1b000000};shader_start<=1;state<=70'b1<<(TRI_WAIT);end
    state[TRI_WAIT]:if(shader_done)begin triangles<=triangles+1'b1;state<=70'b1<<(TRI_NEXT);end
    state[TRI_NEXT]:if(fan+2>=npoly)state<=70'b1<<(F_NEXT);else begin fan<=fan+1'b1;state<=70'b1<<(TRI_INIT);end
    state[F_NEXT]:if(fi+1==nf)state<=70'b1<<(RESTORE);else begin fi<=fi+1'b1;state<=70'b1<<(F_REQ);end
    state[RESTORE]:begin shader_command<=material;shader_start<=1;state<=70'b1<<(RESTORED);end
    state[RESTORED]:if(shader_done)begin draw_active<=0;state<=70'b1<<(FINISH);end
    default:state<=70'b1<<(FAIL);
   endcase
  end
 end
endmodule
`default_nettype wire
