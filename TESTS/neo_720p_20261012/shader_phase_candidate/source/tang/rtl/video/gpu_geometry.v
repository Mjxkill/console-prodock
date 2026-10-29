// Geometry frontend, ABI G3D1. Camera-space Q16.16, indexed DDR meshes.
// Transform/cache -> six-plane clipping -> projection -> lighting -> raster planes.
// The existing GPU V1 remains the pixel engine; no CPU-generated raster planes.
`default_nettype none
module gpu_geometry(
 input wire [5:0] child_resetn,
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
  CL_READ=61,PROJ_READ=62,V_BOUNDS_MUL=63,V_BOUNDS_X=64,V_BOUNDS_Y=65,V_BOUNDS_SAVE=66,DECODE=67,PROJ_NORMALIZE=68,PROJ_LAUNCH=69,
  TRI_READ1=70,TRI_READ2=71,TRI_CAPTURE=72,F_VALIDATE=73,DRAW_VALIDATE=74,LIGHT_VALIDATE=75,MATRIX_VALIDATE=76,CAMERA_VALIDATE=77,PROJ_VALIDATE=78,FACE_CHECK=79,PROJ_OFFSET=80;
 // One bit per state avoids high-fanout binary decode across the DSP/RAM datapath.
 reg [80:0] state;
 reg [4:0] face_bad;
 reg [2:0] draw_bad;
 reg light_bad;
 reg matrix_bad;
 reg [5:0] camera_bad;
 reg [255:0] captured_command;
 reg [32:0] mesh_vertex_end,mesh_face_end;
 wire [31:0] w0=captured_command[31:0],w1=captured_command[63:32],w2=captured_command[95:64],w3=captured_command[127:96],
  w4=captured_command[159:128],w5=captured_command[191:160],w6=captured_command[223:192],w7=captured_command[255:224];
 reg shader_start;reg [255:0] shader_command;
 wire shader_done,shader_valid,shader_write,shader_target_valid,shader_material_valid;wire [28:0] shader_addr;
 wire [255:0] shader_data;wire [31:0] shader_mask,shader_rejected;
 reg fetch_valid;reg [28:0] fetch_addr;
 reg shader_read_phase;
 always @(posedge clk)
  if(rst)shader_read_phase<=0;
  else if(shader_start)shader_read_phase<=1;
  else if(shader_done)shader_read_phase<=0;
 // START already marks the first wait-state cycle, before the retained bit.
 wire shader_read_enable=shader_start || shader_read_phase;
 assign busy=!state[IDLE];
 assign valid=fetch_valid||shader_valid;assign write=shader_valid&&shader_write;
 assign addr=fetch_valid ? fetch_addr:shader_addr;
 assign wr_data=shader_data;assign wr_mask=shader_mask;
 assign rejected=geom_errors+shader_rejected;
 gpu_v1 u_pixels(.child_resetn(child_resetn[5:2]),.clk(clk),.rst(!child_resetn[0]),.start(shader_start),.command(shader_command),.done(shader_done),.busy(),
  .target_config_valid(shader_target_valid),.material_config_valid(shader_material_valid),
  .rejected(shader_rejected),.fragments(fragments),.passed(passed),.texture_hits(texture_hits),.texture_misses(texture_misses),
  .valid(shader_valid),.write(shader_write),.addr(shader_addr),.wr_data(shader_data),.wr_mask(shader_mask),
  .ready(ready&&!fetch_valid),.rd_valid(rd_valid&&shader_read_enable),.rd_data(rd_data));
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
 reg signed [63:0] projection_mul0,projection_mul1,projection_mul2;
 reg signed [48:0] transform_pair0,transform_pair1;
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
 reg [15:0] triangle_z[0:2];reg [23:0] triangle_q[0:2];
 reg signed [15:0] triangle_u[0:2],triangle_v[0:2];
 reg signed [24:0] triangle_scale[0:2];
 reg signed [40:0] triangle_uq[0:2],triangle_vq[0:2];
 genvar attribute_vertex;
 generate for(attribute_vertex=0;attribute_vertex<3;attribute_vertex=attribute_vertex+1)begin: attribute_products
  always @(posedge clk)begin
   triangle_uq[attribute_vertex]<=triangle_u[attribute_vertex]*triangle_scale[attribute_vertex];
   triangle_vq[attribute_vertex]<=triangle_v[attribute_vertex]*triangle_scale[attribute_vertex];
  end
 end endgenerate
 reg [23:0] recip;reg signed [63:0] proj_x,proj_y,depth_mul;
 reg signed [31:0] projection_x,projection_y,normalized_x,normalized_y;
 reg [1:0] normalization_bad;
 reg signed [15:0] projection_u,projection_v;
 // A signed 32-bit integer product plus an unsigned 16-bit center fits
 // signed 33 bits. Separate this offset from clamping and the BRAM write.
 reg signed [32:0] projected_x,projected_y;
 reg [3:0] fan,attr;reg [6:0] plane_mask;
 // A fan needs only three projected vertices at a time. Store the polygon
 // in one synchronous RAM instead of twelve banks of FFs and two wide
 // variable-index read multiplexers (G17 physical CLS utilization: 88%).
 reg [103:0] projected [0:15] /* synthesis syn_ramstyle="block_ram" */;
 reg [103:0] projected_read;
 wire [3:0] projected_read_addr=state[TRI_INIT] ? 4'd0:
     state[TRI_READ1] ? fan:fan+4'd1;
 wire [15:0] projected_store_x=projected_x<0 ? 16'd0:
     projected_x>$signed({1'b0,width}) ? width:projected_x[15:0];
 wire [15:0] projected_store_y=projected_y<0 ? 16'd0:
     projected_y>$signed({1'b0,height}) ? height:projected_y[15:0];
 wire [63:0] projected_depth=((64'sd65536-depth_mul)*65534)>>16;
 wire [15:0] projected_store_z=depth_mul>=65536 ? 16'd0:projected_depth[15:0];
 always @(posedge clk)begin
  if(!rst&&state[PROJ_STORE])projected[project_index[3:0]]<=
      {projection_v,projection_u,recip,projected_store_z,projected_store_y,projected_store_x};
  projected_read<=projected[projected_read_addr];
 end
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
 reg signed [63:0] clip_distance_product0,clip_distance_product1;
 reg signed [22:0] area_product0,area_product1;
 reg signed [48:0] origin_product0,origin_product1;
 reg signed [63:0] origin_term0,origin_term1;
 reg signed [32:0] midpoint;
 // True dual-port polygon memory: port A is read/write, port B is read-only.
 // A registered read stage replaces five large, multiply indexed register
 // arrays. The two 12-vertex banks share a single 160-bit record per vertex.
 reg [159:0] polygon[0:31] /* synthesis syn_ramstyle="block_ram" */;
 reg [159:0] poly_a,poly_b;
 reg projecting;
 // Keep clipping operands in local FFs. The BRAM -> 33-bit subtraction ->
 // DSP input path crossed several routing regions in Neo N11 (-4.949 ns).
 reg [159:0] edge_a,edge_b;
 wire poly_we=!rst&&(state[F_COPY]||state[CL_STORE]||(state[CL_CURRENT]&&!dc[47]&&nout<12));
 wire [4:0] poly_wa=state[F_COPY] ? {3'b0,corner}:dst_base+nout;
 wire [4:0] poly_ra=projecting ? src_base+project_index:src_base+previous;
 wire [4:0] poly_aa=poly_we ? poly_wa:poly_ra;
 wire [4:0] poly_ba=src_base+current;
 wire signed [31:0] ax=poly_a[31:0],ay=poly_a[63:32],az=poly_a[95:64],au=poly_a[127:96],av=poly_a[159:128];
 wire signed [31:0] bx=poly_b[31:0],by=poly_b[63:32],bz=poly_b[95:64],bu=poly_b[127:96],bv=poly_b[159:128];
 wire signed [31:0] eax=edge_a[31:0],eay=edge_a[63:32],eaz=edge_a[95:64],eau=edge_a[127:96],eav=edge_a[159:128];
 wire signed [31:0] ebx=edge_b[31:0],eby=edge_b[63:32],ebz=edge_b[95:64],ebu=edge_b[127:96],ebv=edge_b[159:128];
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
 // A DSP product and its rounding must not feed a second DSP's input FF
 // in one cycle. Both operands settle well before TRI_INIT / MAT_SEND.
 reg [17:0] light_r,light_g,light_b /* synthesis syn_preserve=1 */;
 reg [17:0] material_r,material_g,material_b /* synthesis syn_preserve=1 */;
 always @(posedge clk)begin
  light_r<=face[218:210]*illumination;
  light_g<=face[209:201]*illumination;
  light_b<=face[200:192]*illumination;
  material_r<=material[154:146]*gains[26:18];
  material_g<=material[145:137]*gains[17:9];
  material_b<=material[136:128]*gains[8:0];
 end
 reg div_start;reg signed [63:0] dividend0,dividend1,divisor;
 reg signed [31:0] projection_z;
 wire raw_done0,raw_done1,raw_bad0,raw_bad1;
 wire signed [63:0] raw_quotient0,raw_quotient1;
 reg div_done0,div_done1;reg signed [63:0] quotient0,quotient1;
 reg camera_div_invalid,clip_div_invalid,projection_div_invalid,gradient_div_invalid,gradient_out_of_range;
 // Each datapath owns its result registers. Shared result registers forced
 // distant DSPs through wide muxes (N11: -4.508 ns). The existing states
 // provide the operand/output latency; no extra vertex cycle is needed.
 always @(posedge clk)begin
  mul0<=coefficient[0]*position[0];mul1<=coefficient[1]*position[1];mul2<=coefficient[2]*position[2];
  projection_mul0<=projection_x*$signed(quotient0[31:0]);
  projection_mul1<=projection_y*$signed(quotient0[31:0]);
  projection_mul2<=$signed(near_z)*$signed(quotient0[31:0]);
  clip_distance_product0<=clip_z0*clip_ratio;clip_distance_product1<=clip_z1*clip_ratio;
  area_product0<=ex1*ey2;area_product1<=ex2*ey1;
  origin_product0<=dx*$signed({1'b0,tx[0][15:0]});origin_product1<=dy*$signed({1'b0,ty[0][15:0]});
 end
 gpu_geom_div u_divx(.clk(clk),.rst(!child_resetn[1]),.start(div_start),.numerator(dividend0),.denominator(divisor),.busy(),.done(raw_done0),.invalid(raw_bad0),.quotient(raw_quotient0));
 gpu_geom_div u_divy(.clk(clk),.rst(!child_resetn[1]),.start(div_start),.numerator(dividend1),.denominator(divisor),.busy(),.done(raw_done1),.invalid(raw_bad1),.quotient(raw_quotient1));
 // Register range predicates beside the divider outputs. Their wide
 // reductions no longer feed configuration/data-register enables in the
 // same cycle (G15 quotient -> camera/clipping endpoints: -3.56 ns).
 always @(posedge clk)begin
  if(rst)begin div_done0<=0;div_done1<=0;end
  else begin div_done0<=raw_done0;div_done1<=raw_done1;end
  quotient0<=raw_quotient0;quotient1<=raw_quotient1;
  camera_div_invalid<=raw_bad0||raw_quotient0>524288;
  clip_div_invalid<=raw_bad0||raw_quotient0<0||raw_quotient0>65536;
  projection_div_invalid<=raw_bad0||raw_quotient0<=0||raw_quotient0>24'hffffff;
  gradient_div_invalid<=raw_bad0||raw_bad1;
  gradient_out_of_range<=raw_quotient0>2147483647||raw_quotient0< -64'sd2147483648||
      raw_quotient1>2147483647||raw_quotient1< -64'sd2147483648;
 end
 function [8:0] rounded_gain;
  input [17:0] product;reg [17:0] p;
  begin p=product+18'd128;rounded_gain=p[16:8];end
 endfunction
 function signed [63:0] attribute_value;
  input [3:0] k,v;
  begin case(k)
   0:attribute_value=triangle_uq[v];
   1:attribute_value=triangle_vq[v];
   2:attribute_value=$signed({1'b0,triangle_q[v]});
   default:attribute_value=$signed({1'b0,triangle_z[v],16'b0});
  endcase end
 endfunction
 integer j;
 always @(posedge clk)begin
  shader_start<=0;div_start<=0;done<=0;
  if(rst)begin
   state<=81'b1<<(IDLE);fetch_valid<=0;shader_start<=0;div_start<=0;done<=0;
   matrix_valid<=0;camera_valid<=0;material_valid<=0;draw_active<=0;target_w<=0;target_h<=0;
   projecting<=0;
   geom_errors<=0;vertices<=0;triangles<=0;culled<=0;clipped<=0;slivers<=0;geom_cycles<=0;
   ambient<=256;diffuse<=0;light_x<=0;light_y<=0;light_z<=0;
   // material_valid is the reset boundary. Material payload is private and
   // is overwritten by a validated material before drawing; resetting it
   // also reset distant DSP input FFs through the whole engine reset tree.
   shader_command<=0;fetch_addr<=0;
  end else begin
   if(!state[IDLE]&&!state[PASS])geom_cycles<=geom_cycles+1'b1;
   case(1'b1) // synthesis parallel_case
    state[IDLE]:if(start)begin
     // Separate the distant command FIFO and address sums from validation.
     captured_command<=command;
     mesh_vertex_end<={1'b0,command[63:32]}+{12'b0,command[127:112],5'b0};
     mesh_face_end<={1'b0,command[95:64]}+{12'b0,command[111:96],5'b0};
     state<=81'b1<<(DECODE);
    end
    state[DECODE]:begin
     if(w0[31:24]<31)begin
      shader_command<=captured_command;shader_start<=1;state<=81'b1<<(PASS);
      if(w0[31:24]==22)begin target_w<=w3[31:16];target_h<=w3[15:0];camera_valid<=0;end
      if(w0[31:24]==25)begin material<=captured_command;material_valid<=0;end
     end else case(w0[31:24])
      31:begin
       matrix_bad<=w0[23:0]!=0||w1>2||w6!=0||w7!=0;
       state<=81'b1<<(MATRIX_VALIDATE);
      end
      32:begin
       camera_valid<=0;
       // Invalid CAMERA keeps camera_valid clear. Private payload capture
       // can therefore precede validation, avoiding its wide CE fanout.
       near_z<=w1;far_z<=w2;fx<=w3;fy<=w4;cx<=w5[31:16];cy<=w5[15:0];width<=w6[31:16];height<=w6[15:0];cam_index<=0;
       camera_bad[0]<=w0[23:0]!=0||w7!=0;
       camera_bad[1]<=$signed(w1)<4096||$signed(w2)<=$signed(w1);
       camera_bad[2]<=$signed(w3)<65536||$signed(w4)<65536||w3>32'h10000000||w4>32'h10000000;
       camera_bad[3]<=w5[31:16]>w6[31:16]||w5[15:0]>w6[15:0];
       camera_bad[4]<=!w6[31:16]||w6[31:16]>1024||!w6[15:0]||w6[15:0]>512;
       camera_bad[5]<=w6!={target_w,target_h};
       state<=81'b1<<(CAMERA_VALIDATE);
      end
      33:begin
       light_bad<=w0[23:0]!=0||w2[31:16]!=0||w3[15:0]>256||w3[31:16]>256||w4!=0||w5!=0||w6!=0||w7!=0;
       state<=81'b1<<(LIGHT_VALIDATE);
      end
      34:begin
       // Only a validated DRAW asserts draw_active and starts memory reads.
       vb<=w1;fb<=w2;nv<=w3[31:16];nf<=w3[15:0];vi<=0;fi<=0;cull_enable<=w4[0];
       // Check independent groups before driving state/clock enables. This
       // avoids a long combinational path through the whole DRAW descriptor.
       draw_bad[0]<=w0[23:0]!=0||w4>1||w5!=0||w6!=0||w7!=0;
       draw_bad[1]<=(w1&31)!=0||(w2&31)!=0||mesh_vertex_end>33'h020000000||mesh_face_end>33'h020000000;
       draw_bad[2]<=matrix_valid!=7||!camera_valid||!material_valid||w3[31:16]==0||w3[31:16]>256||w3[15:0]==0;
       state<=81'b1<<(DRAW_VALIDATE);
      end
      default:state<=81'b1<<(FAIL);
     endcase
    end
    state[DRAW_VALIDATE]:begin
     if(|draw_bad)state<=81'b1<<(FAIL);
     else begin draw_active<=1;state<=81'b1<<(V_REQ);end
    end
    state[MATRIX_VALIDATE]:begin
     if(matrix_bad)state<=81'b1<<(FAIL);
     else begin
      case(w1[1:0])
       0:begin matrix[0]<=w2;matrix[1]<=w3;matrix[2]<=w4;matrix[3]<=w5;matrix_valid[0]<=1;end
       1:begin matrix[4]<=w2;matrix[5]<=w3;matrix[6]<=w4;matrix[7]<=w5;matrix_valid[1]<=1;end
       2:begin matrix[8]<=w2;matrix[9]<=w3;matrix[10]<=w4;matrix[11]<=w5;matrix_valid[2]<=1;end
       default: ;
      endcase
      state<=81'b1<<(FINISH);
     end
    end
    state[CAMERA_VALIDATE]:state<=81'b1<<(|camera_bad ? FAIL:CAM_DIV);
    state[LIGHT_VALIDATE]:begin
     if(light_bad)state<=81'b1<<(FAIL);
     else begin light_x<=w1[31:16];light_y<=w1[15:0];light_z<=w2[15:0];ambient<=w3[8:0];diffuse<=w3[24:16];state<=81'b1<<(FINISH);end
    end
    state[PASS]:if(shader_done)begin
     // Use the pixel engine's complete descriptor validation, including
     // headers/reserved bits. Lighting must never sanitize an invalid tint.
     if(w0[31:24]==25)material_valid<=shader_material_valid&&!w1[6];
     if(w0[31:24]==22&&!shader_target_valid)begin target_w<=0;target_h<=0;camera_valid<=0;end
     state<=81'b1<<(FINISH);
    end
    state[FAIL]:begin
     geom_errors<=geom_errors+1'b1;fetch_valid<=0;
     // A preceding face may have changed the pixel engine's tint. Keep the
     // public material contract even when a later mesh face is malformed.
     state<=81'b1<<(draw_active ? RESTORE:FINISH);
    end
    state[FINISH]:begin done<=1;state<=81'b1<<(IDLE);end
    state[CAM_DIV]:begin
     dividend0<=$signed({16'b0,(cam_index==0 ? cx:cam_index==1 ? width-cx:cam_index==2 ? cy:height-cy),32'b0});
     dividend1<=0;divisor<=cam_index<2 ? fx:fy;div_start<=1;state<=81'b1<<(CAM_WAIT);
    end
    state[CAM_WAIT]:if(div_done0)begin
     if(camera_div_invalid)state<=81'b1<<(FAIL);
     else begin ratio[cam_index]<=quotient0[31:0];if(cam_index==3)begin camera_valid<=1;state<=81'b1<<(FINISH);end else begin cam_index<=cam_index+1'b1;state<=81'b1<<(CAM_DIV);end end
    end
    state[V_REQ]:begin fetch_addr<=(vb+{vi,5'b0})>>2;fetch_valid<=1;state<=81'b1<<(V_WAIT);end
    state[V_WAIT]:begin
     if(fetch_valid&&ready)fetch_valid<=0;
     if(rd_valid)begin
      position[0]<=rd_data[31:0];position[1]<=rd_data[63:32];position[2]<=rd_data[95:64];row<=0;
      for(j=0;j<4;j=j+1)coefficient[j]<=matrix[j];
      if(rd_data[255:96]!=0)state<=81'b1<<(FAIL);
      else begin
       state<=81'b1<<(V_MUL);
      end
     end
    end
    state[V_MUL]:state<=81'b1<<(V_PAIR);
    state[V_PAIR]:begin transform_pair0<=$signed(mul0[63:16])+$signed(mul1[63:16]);transform_pair1<=$signed(mul2[63:16])+$signed(coefficient[3]);state<=81'b1<<(V_SUM);end
    state[V_SUM]:begin sum64<=transform_pair0+transform_pair1;state<=81'b1<<(V_STORE);end
    state[V_STORE]:begin
     if(sum64>2147483647||sum64< -64'sd2147483648)state<=81'b1<<(FAIL);
     else begin
      transformed[row]<=sum64[31:0];
      if(row==0)vx[vi[7:0]]<=sum64[31:0];if(row==1)vy[vi[7:0]]<=sum64[31:0];if(row==2)vz[vi[7:0]]<=sum64[31:0];
      if(row==2)begin bounds_y<=0;state<=81'b1<<(V_BOUNDS_MUL);end
      else begin
       // Select the next row while storing this one, before the DSP products.
       for(j=0;j<4;j=j+1)coefficient[j]<=row==0 ? matrix[4+j]:matrix[8+j];
       row<=row+1'b1;state<=81'b1<<(V_MUL);
      end
     end
    end
    state[V_BOUNDS_MUL]:begin
     bounds_product0<=transformed[2]*bounds_ratio0;bounds_product1<=transformed[2]*bounds_ratio1;
     state<=81'b1<<(bounds_y ? V_BOUNDS_Y:V_BOUNDS_X);
    end
    state[V_BOUNDS_X]:begin
     bounds_code[0]<=transformed[2]<near_z;bounds_code[1]<=transformed[2]>far_z;
     bounds_code[2]<=((bounds_product0>>>16)+$signed(transformed[0]))<0;
     bounds_code[3]<=((bounds_product1>>>16)-$signed(transformed[0]))<0;
     bounds_y<=1;state<=81'b1<<(V_BOUNDS_MUL);
    end
    state[V_BOUNDS_Y]:begin
     bounds_code[4]<=((bounds_product0>>>16)+$signed(transformed[1]))<0;
     bounds_code[5]<=((bounds_product1>>>16)-$signed(transformed[1]))<0;
     state<=81'b1<<(V_BOUNDS_SAVE);
    end
    state[V_BOUNDS_SAVE]:begin
     vertex_code[vi[7:0]]<=bounds_code;vertices<=vertices+1'b1;
     if(vi+1==nv)state<=81'b1<<(F_REQ);else begin vi<=vi+1'b1;state<=81'b1<<(V_REQ);end
    end
    state[F_REQ]:begin fetch_addr<=(fb+{fi,5'b0})>>2;fetch_valid<=1;state<=81'b1<<(F_WAIT);end
    state[F_WAIT]:begin
     if(fetch_valid&&ready)fetch_valid<=0;
     if(rd_valid)begin
      face<=rd_data;state<=81'b1<<(F_VALIDATE);
     end
    end
    state[F_VALIDATE]:begin
     // Prepare the first cache read independently of descriptor validation.
     // Invalid faces still go straight to FAIL, without ever reading the cache.
     // This keeps the full validation cone off the cache address/enable path.
     corner<=0;face_code<=0;cache_index<=face[7:0];
     face_bad[0]<=face[7:0]>=nv;
     face_bad[1]<=face[15:8]>=nv;
     face_bad[2]<=face[23:16]>=nv;
     face_bad[3]<=face[31:26]!=0||face[255:224]!=0||face[223:219]!=0||face[191:176]!=0;
     face_bad[4]<=face[200:192]>256||face[209:201]>256||face[218:210]>256;
     state<=81'b1<<(FACE_CHECK);
    end
    state[FACE_CHECK]:begin
     if(|face_bad)state<=81'b1<<(FAIL);
     else state<=81'b1<<(F_CACHE);
    end
    state[F_CACHE]:begin cached_x<=vx[cache_index];cached_y<=vy[cache_index];cached_z<=vz[cache_index];cached_code<=vertex_code[cache_index];state<=81'b1<<(F_COPY);end
    state[F_COPY]:begin
     face_code<=face_code|cached_code;
     if(corner==2)state<=81'b1<<(L_MUL);else begin
      corner<=corner+1'b1;
      // The only remaining triangle corners are 1 and 2. A two-way mux
      // avoids a 32-bit variable-shift expression on the next cache address.
      cache_index<=corner==0 ? face[15:8]:face[23:16];
      state<=81'b1<<(F_CACHE);
     end
    end
    state[L_MUL]:begin light_product[0]<=$signed(face[159:144])*$signed(light_x);light_product[1]<=$signed(face[143:128])*$signed(light_y);light_product[2]<=$signed(face[175:160])*$signed(light_z);state<=81'b1<<(L_ADD);end
    state[L_ADD]:begin light_dot<=light_total>>>15;state<=81'b1<<(L_SUM);end
    state[L_SUM]:begin
     sum64<=light_dot*$signed({1'b0,diffuse});state<=81'b1<<(CL_INIT);
    end
    state[CL_INIT]:begin
     if(face[24])illumination<=256;
     else if(sum64<0)illumination<=ambient;
     else if((sum64>>>15)+ambient>256)illumination<=256;
     else illumination<=(sum64>>>15)+ambient;
     src_base<=0;dst_base<=12;npoly<=3;nout<=0;previous<=2;current<=0;plane<=0;project_index<=0;
     projecting<=face_code==0;
     // Convex frustum: three inside vertices imply an entirely inside triangle.
     // Outside triangles retain the original six-plane path and exact counters.
     state<=81'b1<<(face_code==0 ? PROJ_READ:CL_DIST);
    end
    state[CL_DIST]:state<=81'b1<<(CL_READ);
    state[CL_READ]:begin
     edge_a<=poly_a;edge_b<=poly_b;
     clip_z0<=az;clip_z1<=bz;
     clip_ratio<=plane>=2 ? ratio[plane-2]:0;
     case(plane)
      2:begin clip_side0<=ax;clip_side1<=bx;end
      3:begin clip_side0<=-$signed({ax[31],ax});clip_side1<=-$signed({bx[31],bx});end
      4:begin clip_side0<=ay;clip_side1<=by;end
      default:begin clip_side0<=-$signed({ay[31],ay});clip_side1<=-$signed({by[31],by});end
     endcase
     state<=81'b1<<(CL_PRODUCT);
    end
    state[CL_PRODUCT]:state<=81'b1<<(CL_DISTANCE);
    state[CL_DISTANCE]:begin
     case(plane)
      0:begin dp<=$signed(clip_z0)-$signed(near_z);dc<=$signed(clip_z1)-$signed(near_z);end
      1:begin dp<=$signed(far_z)-$signed(clip_z0);dc<=$signed(far_z)-$signed(clip_z1);end
      default:begin dp<=(clip_distance_product0>>>16)+clip_side0;dc<=(clip_distance_product1>>>16)+clip_side1;end
     endcase
     state<=81'b1<<(CL_EDGE);
    end
    state[CL_EDGE]:begin
     if(dp!=0&&dc!=0&&dp[47]!=dc[47])state<=81'b1<<(CL_DIV);
     else state<=81'b1<<(CL_CURRENT);
    end
    state[CL_DIV]:begin
     // Always interpolate from inside to outside. Opposite windings must
     // produce the same fixed-point intersection on a shared triangle edge.
     dividend0<=$signed(dp[47] ? dc:dp)<<<16;dividend1<=0;
     divisor<=dp[47] ? $signed(dc)-$signed(dp):$signed(dp)-$signed(dc);
     div_start<=1;state<=81'b1<<(CL_WAIT);
    end
    state[CL_WAIT]:if(div_done0)begin
     if(clip_div_invalid||nout>=11)state<=81'b1<<(FAIL);
     else begin fraction<=quotient0[17:0];clipped<=clipped+1'b1;state<=81'b1<<(CL_INTER);end
    end
    state[CL_INTER]:begin
     if(dp[47])begin
      clip_a[0]<=ebx;clip_delta[0]<=$signed({eax[31],eax})-$signed({ebx[31],ebx});
      clip_a[1]<=eby;clip_delta[1]<=$signed({eay[31],eay})-$signed({eby[31],eby});
      clip_a[2]<=ebz;clip_delta[2]<=$signed({eaz[31],eaz})-$signed({ebz[31],ebz});
      clip_a[3]<=ebu;clip_delta[3]<=$signed({eau[31],eau})-$signed({ebu[31],ebu});
      clip_a[4]<=ebv;clip_delta[4]<=$signed({eav[31],eav})-$signed({ebv[31],ebv});
     end else begin
      clip_a[0]<=eax;clip_delta[0]<=$signed({ebx[31],ebx})-$signed({eax[31],eax});
      clip_a[1]<=eay;clip_delta[1]<=$signed({eby[31],eby})-$signed({eay[31],eay});
      clip_a[2]<=eaz;clip_delta[2]<=$signed({ebz[31],ebz})-$signed({eaz[31],eaz});
      clip_a[3]<=eau;clip_delta[3]<=$signed({ebu[31],ebu})-$signed({eau[31],eau});
      clip_a[4]<=eav;clip_delta[4]<=$signed({ebv[31],ebv})-$signed({eav[31],eav});
     end
     state<=81'b1<<(CL_MULT);
    end
    state[CL_MULT]:begin for(j=0;j<5;j=j+1)clip_product[j]<=clip_delta[j]*fraction;state<=81'b1<<(CL_STORE);end
    state[CL_STORE]:begin
     nout<=nout+1'b1;state<=81'b1<<(CL_CURRENT);
    end
    state[CL_CURRENT]:begin
     if(!dc[47])begin
      if(nout>=12)state<=81'b1<<(FAIL);
      else begin nout<=nout+1'b1;state<=81'b1<<(CL_NEXT);end
     end else state<=81'b1<<(CL_NEXT);
    end
    state[CL_NEXT]:begin
     if(current+1==npoly)state<=81'b1<<(CL_PLANE);
     else begin previous<=current;current<=current+1'b1;state<=81'b1<<(CL_DIST);end
    end
    state[CL_PLANE]:begin
     if(nout<3)begin culled<=culled+1'b1;state<=81'b1<<(F_NEXT);end
     else begin
      src_base<=dst_base;dst_base<=src_base;npoly<=nout;
      if(plane==5)begin projecting<=1;project_index<=0;state<=81'b1<<(PROJ_READ);end
      else begin plane<=plane+1'b1;previous<=nout-1'b1;current<=0;nout<=0;state<=81'b1<<(CL_DIST);end
     end
    end
    state[PROJ_READ]:state<=81'b1<<(PROJ_DIV);
    state[PROJ_DIV]:begin
     dividend0<=64'h100000000;dividend1<=0;
     projection_x<=ax;projection_y<=ay;projection_u<=au>>>16;projection_v<=av>>>16;
     projection_z<=az;state<=81'b1<<(PROJ_LAUNCH);
    end
    state[PROJ_LAUNCH]:begin
     // Capture the BRAM output before the near-plane comparison/mux.
     divisor<=projection_z<near_z ? near_z:projection_z;
     div_start<=1;state<=81'b1<<(PROJ_WAIT);
    end
    state[PROJ_WAIT]:if(div_done0)begin
     if(projection_div_invalid)state<=81'b1<<(FAIL);
     else begin recip<=quotient0[23:0];state<=81'b1<<(PROJ_NORMALIZE);end
    end
    state[PROJ_NORMALIZE]:begin
     // A clipped frustum ratio is bounded by 8. Check before narrowing so an
     // invalid internal position cannot silently wrap before projection.
     // Capture payload and range predicates separately. The wide product
     // carry/overflow chain must not also drive the next DSP's input enables.
     normalization_bad[0]<=(projection_mul0>>>16)>2147483647||(projection_mul0>>>16)< -64'sd2147483648;
     normalization_bad[1]<=(projection_mul1>>>16)>2147483647||(projection_mul1>>>16)< -64'sd2147483648;
     normalized_x<=projection_mul0>>>16;normalized_y<=projection_mul1>>>16;
     depth_mul<=projection_mul2>>>16;state<=81'b1<<(PROJ_VALIDATE);
    end
    state[PROJ_VALIDATE]:begin
     if(|normalization_bad)state<=81'b1<<(FAIL);
     else state<=81'b1<<(PROJ_MUL);
    end
    state[PROJ_MUL]:begin proj_x<=normalized_x*fx;proj_y<=normalized_y*fy;state<=81'b1<<(PROJ_OFFSET);end
    state[PROJ_OFFSET]:begin
     projected_x<=$signed({proj_x[63],proj_x[63:32]})+$signed({17'b0,cx});
     projected_y<=$signed({proj_y[63],proj_y[63:32]})+$signed({17'b0,cy});
     state<=81'b1<<(PROJ_STORE);
    end
    state[PROJ_STORE]:begin
     // The synchronous projected-vertex RAM writes the same clamped values.
     if(project_index+1==npoly)begin fan<=1;state<=81'b1<<(TRI_INIT);end
     else begin project_index<=project_index+1'b1;state<=81'b1<<(PROJ_READ);end
    end
    state[TRI_INIT]:begin
     gains<={rounded_gain(light_r),rounded_gain(light_g),rounded_gain(light_b)};
     state<=81'b1<<(TRI_READ1);
    end
    state[TRI_READ1]:begin
     tx[0]<={16'b0,projected_read[15:0]};ty[0]<={16'b0,projected_read[31:16]};
     triangle_z[0]<=projected_read[47:32];triangle_q[0]<=projected_read[71:48];
     triangle_u[0]<=projected_read[87:72];triangle_v[0]<=projected_read[103:88];
     triangle_scale[0]<=material[36] ? $signed({1'b0,projected_read[71:48]}):25'sd65536;
     state<=81'b1<<(TRI_READ2);
    end
    state[TRI_READ2]:begin
     tx[1]<={16'b0,projected_read[15:0]};ty[1]<={16'b0,projected_read[31:16]};
     triangle_z[1]<=projected_read[47:32];triangle_q[1]<=projected_read[71:48];
     triangle_u[1]<=projected_read[87:72];triangle_v[1]<=projected_read[103:88];
     triangle_scale[1]<=material[36] ? $signed({1'b0,projected_read[71:48]}):25'sd65536;
     state<=81'b1<<(TRI_CAPTURE);
    end
    state[TRI_CAPTURE]:begin
     tx[2]<={16'b0,projected_read[15:0]};ty[2]<={16'b0,projected_read[31:16]};
     triangle_z[2]<=projected_read[47:32];triangle_q[2]<=projected_read[71:48];
     triangle_u[2]<=projected_read[87:72];triangle_v[2]<=projected_read[103:88];
     triangle_scale[2]<=material[36] ? $signed({1'b0,projected_read[71:48]}):25'sd65536;
     state<=81'b1<<(TRI_DIFF);
    end
    state[TRI_DIFF]:begin
     ex1<=$signed({1'b0,tx[1][10:0]})-$signed({1'b0,tx[0][10:0]});
     ey1<=$signed({1'b0,ty[1][9:0]})-$signed({1'b0,ty[0][9:0]});
     ex2<=$signed({1'b0,tx[2][10:0]})-$signed({1'b0,tx[0][10:0]});
     ey2<=$signed({1'b0,ty[2][9:0]})-$signed({1'b0,ty[0][9:0]});state<=81'b1<<(TRI_MUL);
    end
    state[TRI_MUL]:state<=81'b1<<(TRI_AREA);
    state[TRI_AREA]:begin area<=area_product0-area_product1;state<=81'b1<<(MAT_SEND);end
    state[MAT_SEND]:begin
     if(area==0||(cull_enable&&!face[25]&&area>=0))begin culled<=culled+1'b1;state<=81'b1<<(TRI_NEXT);end
     else begin
      shader_command<=material;
      shader_command[159:128]<={5'b0,rounded_gain(material_r),rounded_gain(material_g),rounded_gain(material_b)};
      shader_start<=1;attr<=0;
      plane_mask<=(material[32] ? 7'd3:7'd0)|(material[36] ? 7'd4:7'd0)|((material[63:32]&134)!=0 ? 7'd8:7'd0);
      state<=81'b1<<(MAT_WAIT);
     end
    end
    state[MAT_WAIT]:if(shader_done)state<=81'b1<<(PL_INIT);
    state[PL_INIT]:begin
     if(attr==4)state<=81'b1<<(TRI_SEND);
     else if(!plane_mask[attr])attr<=attr+1'b1;
     else begin
      value[0]<=attribute_value(attr,0);value[1]<=attribute_value(attr,1);value[2]<=attribute_value(attr,2);state<=81'b1<<(PL_DIFF);
     end
    end
    state[PL_DIFF]:begin dv1<=value[1]-value[0];dv2<=value[2]-value[0];state<=81'b1<<(PL_MUL);end
    state[PL_MUL]:state<=81'b1<<(PL_NUM);
    state[PL_NUM]:begin
     numx<=gradient_product[0]-gradient_product[1];numy<=gradient_product[2]-gradient_product[3];state<=81'b1<<(PL_DIV);
    end
    state[PL_DIV]:begin dividend0<=numx;dividend1<=numy;divisor<=area;div_start<=1;state<=81'b1<<(PL_WAIT);end
    state[PL_WAIT]:if(div_done0&&div_done1)begin
     if(gradient_div_invalid)state<=81'b1<<(FAIL);
     else if(gradient_out_of_range)begin
      // Explicitly counted constant-attribute approximation for raster slivers.
      dx<=0;dy<=0;slivers<=slivers+1'b1;state<=81'b1<<(SLIVER_DIV);
     end else begin dx<=quotient0[31:0];dy<=quotient1[31:0];state<=81'b1<<(ORIGIN_MUL);end
    end
    state[SLIVER_DIV]:begin dividend0<=value[0]+value[1]+value[2];dividend1<=0;divisor<=3;div_start<=1;state<=81'b1<<(SLIVER_WAIT);end
    state[SLIVER_WAIT]:if(div_done0)begin value[0]<=quotient0;state<=81'b1<<(ORIGIN_MUL);end
    state[ORIGIN_MUL]:begin
     midpoint<=($signed({dx[31],dx})+$signed({dy[31],dy}))/2;state<=81'b1<<(ORIGIN_SUM);
    end
    state[ORIGIN_SUM]:begin origin_term0<=value[0]-origin_product0;origin_term1<=origin_product1-midpoint;state<=81'b1<<(PL_ORIGIN);end
    state[PL_ORIGIN]:begin origin<=origin_term0-origin_term1;state<=81'b1<<(PL_SEND);end
    state[PL_SEND]:begin
     if(origin>64'sh7fffffffffff||origin< -64'sh800000000000)state<=81'b1<<(FAIL);
     else begin shader_command<={96'b0,16'b0,origin[47:32],dy,dx,origin[31:0],24'h1a0000,4'b0,attr};shader_start<=1;state<=81'b1<<(PL_SENT);end
    end
    state[PL_SENT]:if(shader_done)begin attr<=attr+1'b1;state<=81'b1<<(PL_INIT);end
    state[TRI_SEND]:begin shader_command<={128'b0,tx[2][15:0],ty[2][15:0],tx[1][15:0],ty[1][15:0],tx[0][15:0],ty[0][15:0],32'h1b000000};shader_start<=1;state<=81'b1<<(TRI_WAIT);end
    state[TRI_WAIT]:if(shader_done)begin triangles<=triangles+1'b1;state<=81'b1<<(TRI_NEXT);end
    state[TRI_NEXT]:if(fan+2>=npoly)state<=81'b1<<(F_NEXT);else begin fan<=fan+1'b1;state<=81'b1<<(TRI_INIT);end
    state[F_NEXT]:if(fi+1==nf)state<=81'b1<<(RESTORE);else begin fi<=fi+1'b1;state<=81'b1<<(F_REQ);end
    state[RESTORE]:begin shader_command<=material;shader_start<=1;state<=81'b1<<(RESTORED);end
    state[RESTORED]:if(shader_done)begin draw_active<=0;state<=81'b1<<(FINISH);end
    default:state<=81'b1<<(FAIL);
   endcase
  end
 end
endmodule
`default_nettype wire
