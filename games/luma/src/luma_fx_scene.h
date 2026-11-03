// R2 cinematic: real V1 RGB565/additive/Gouraud/perspective/Z commands.
// The same command stream is replayed by the independent integer host model.
#ifndef LUMA_FX_SCENE_H
#define LUMA_FX_SCENE_H
#include "luma_scene.h"
#include "gpu_v1.h"
#define LUMA_FX_STRIDE 800U
#define LUMA_FX_X 544
#define LUMA_FX_Y 190
static const int16_t luma_sines[65]={0,402,804,1205,1606,2006,2404,2801,3196,3590,3981,4370,4756,5139,5520,5897,6270,6639,7005,7366,7723,8076,8423,8765,9102,9434,9760,10080,10394,10702,11003,11297,11585,11866,12140,12406,12665,12916,13160,13395,13623,13842,14053,14256,14449,14635,14811,14978,15137,15286,15426,15557,15679,15791,15893,15986,16069,16143,16207,16261,16305,16340,16364,16379,16384};
static int luma_sin(unsigned p){p&=255;int v=luma_sines[(p&64)?64-(p&63):p&63];return p&128?-v:v;}
static int luma_cos(unsigned p){return luma_sin(p+64);}
static gpu_vertex luma_v(int x,int y,int r,int g,int b){return (gpu_vertex){x,y,0,0,10000,65536,r,g,b};}
static gpu_target luma_target(unsigned page){return (gpu_target){GPU_PAGE_ADDR(page),GPU_PAGE_ADDR(2),400,240,LUMA_FX_STRIDE,LUMA_FX_STRIDE};}
// Geometry is authored in LCD coordinates; the RGB raster runs at half size.
// Native indexed layers/sprites are composed after the hardware x2 expansion.
static int luma_triangle(gpu_v1_context *c,const gpu_vertex v[3])
{
 gpu_vertex q[3];for(unsigned i=0;i<3;++i){q[i]=v[i];q[i].x/=2;q[i].y/=2;}
 int a=(q[1].x-q[0].x)*(q[2].y-q[0].y)-(q[2].x-q[0].x)*(q[1].y-q[0].y);
 if((c->flags&GPU_Z_TEST) && a>-16 && a<16)return 1;
 return gpu_v1_triangle(c,q);
}
static int luma_quad(gpu_v1_context *c,const gpu_vertex v[4])
{gpu_vertex t[3]={v[0],v[2],v[3]};return luma_triangle(c,v)&&luma_triangle(c,t);}
static int luma_material(gpu_v1_context *c,unsigned flags,unsigned color,unsigned alpha)
{gpu_material m={flags,alpha,color,256,256,256,0,0,0};return gpu_v1_material(c,&m);}
// A soft light as an additive Gouraud fan: no rectangular alpha-zero overdraw.
static int luma_glow(gpu_v1_context *c,int x,int y,int radius,unsigned color,unsigned alpha)
{
 if(!luma_material(c,GPU_V1_ADDITIVE|GPU_V1_GOURAUD,color,alpha))return 0;
 for(unsigned i=0;i<16;++i){gpu_vertex v[3]={luma_v(x,y,256,256,256),
  luma_v(x+luma_cos(i*16)*radius/16384,y+luma_sin(i*16)*radius/16384,0,0,0),
  luma_v(x+luma_cos((i+1)*16)*radius/16384,y+luma_sin((i+1)*16)*radius/16384,0,0,0)};
  if(!luma_triangle(c,v))return 0;}
 return 1;
}
static int luma_ring(gpu_v1_context *c,int x,int y,int radius,int flat,unsigned angle,unsigned age,unsigned color,unsigned alpha)
{
 if(!luma_material(c,GPU_V1_ADDITIVE|GPU_V1_GOURAUD,color,alpha))return 0;
 int ca=luma_cos(angle),sa=luma_sin(angle);
 for(unsigned k=0;k<32;++k){gpu_vertex v[4];
  for(unsigned j=0;j<4;++j){unsigned p=(k+(j==1||j==2))*8;int r=radius+(j<2?2:-2);
   int xx=luma_cos(p)*r/16384,yy=(int)((int64_t)luma_sin(p)*r*flat/(16384*256));
   int gain=100+(luma_sin(p+age/2)+16384)*156/32768;
   v[j]=luma_v(x+(xx*ca-yy*sa)/16384,y+(xx*sa+yy*ca)/16384,gain,gain,gain);}
  if(!luma_quad(c,v))return 0;
 }
 return 1;
}
static int luma_portal(gpu_v1_context *c,unsigned age,int radius)
{
 gpu_texture_level tex={LUMA_FX_PORTAL,256,256,512,GPU_RGB565,GPU_TEX_REPEAT,GPU_TEX_REPEAT,0};
 gpu_material mat={GPU_RASTER_TEXTURE|GPU_V1_GOURAUD,
  (unsigned)luma_clamp((int)age-340,0,256),0,256,256,256,0,0,0};
 if(!gpu_v1_texture(c,&tex)||!gpu_v1_material(c,&mat))return 0;
 // A moving center and warped boundary UVs distort a 24-triangle affine mesh.
 // Perspective division is reserved for the actual 3D objects below.
 for(unsigned i=0;i<24;++i){gpu_vertex v[3];
  v[0]=(gpu_vertex){LUMA_FX_X+ luma_sin(age/2)*9/16384,LUMA_FX_Y+luma_cos(age/3)*6/16384,
     128+luma_sin(age)*24/16384,128+luma_cos(age)*24/16384,18000,65536,125,210,256};
  for(unsigned j=0;j<2;++j){unsigned p=(i+j)*256/24;int r=radius+luma_sin(p*3+age)*4/16384;
   v[j+1]=(gpu_vertex){LUMA_FX_X+luma_cos(p)*r/16384,LUMA_FX_Y+luma_sin(p)*r/16384,
    128+luma_cos(p+age/3)*116/16384,128+luma_sin(p+age/3)*116/16384,18000,65536,130,240,256};}
  if(!luma_triangle(c,v))return 0;
 }
 return 1;
}
typedef struct { int x,y,z; } luma_xyz;
static int luma_crystal(gpu_v1_context *c,unsigned age,int cx,int cy,int scale,unsigned variant,int distance)
{
 static const luma_xyz points[6]={{0,-94,0},{-46,0,-46},{46,0,-46},{46,0,46},{-46,0,46},{0,94,0}};
 static const uint8_t faces[8][3]={{0,1,2},{0,2,3},{0,3,4},{0,4,1},{5,2,1},{5,3,2},{5,4,3},{5,1,4}};
 gpu_vertex projected[6];
 unsigned tilt=(unsigned)(12+luma_sin(age/3)*10/16384);
 int sa=luma_sin(age),ca=luma_cos(age),sb=luma_sin(tilt),cb=luma_cos(tilt);
 for(unsigned i=0;i<6;++i){int x=(points[i].x*ca+points[i].z*sa)/16384,z=(points[i].z*ca-points[i].x*sa)/16384;
  int y=(points[i].y*cb-z*sb)/16384;z=distance+(points[i].y*sb+z*cb)/16384;
  int light=140+luma_clamp((ca+sa)/256,-90,90);
  projected[i]=(gpu_vertex){cx+x*scale/z,cy+y*scale/z,0,0,z*80,16777216/z,
    variant?240:light,variant?light:240,256};
 }
 gpu_texture_level tex={LUMA_FX_GEM,64,64,128,GPU_RGB565,GPU_TEX_CLAMP,GPU_TEX_CLAMP,0};
 if(!gpu_v1_texture(c,&tex)||!luma_material(c,GPU_RASTER_TEXTURE|GPU_Z_TEST|GPU_Z_WRITE|GPU_PERSPECTIVE|GPU_V1_GOURAUD,0,256))return 0;
 for(unsigned face=0;face<8;++face){gpu_vertex v[3];
  for(unsigned j=0;j<3;++j){v[j]=projected[faces[face][j]];v[j].u=j==0?32:j==1?0:63;v[j].v=j==0?0:63;
   // Face lighting remains attached to the object as it rotates.
   int g=185+luma_sin(age+(face%4)*64)*60/16384;
   v[j].r=v[j].r*g/256;v[j].g=v[j].g*g/256;}
  // Integer projection can collapse an edge-on facet to fewer than eight
  // pixels while leaving an unrepresentable Z gradient. Cull only these
  // subpixel edge facets, never clamp a depth plane or drop a broad face.
  int area=(v[1].x-v[0].x)*(v[2].y-v[0].y)-(v[2].x-v[0].x)*(v[1].y-v[0].y);
  if(area>=-16)continue; // outward winding: positive area faces away
  if(!luma_triangle(c,v))return 0;
 }
 return 1;
}
static int luma_fx_prepare(gpu_v1_context *c)
{
 gpu_target bg=luma_target(3),source={LUMA_FX_BG,0,400,240,800,800};
 if(!gpu_v1_target(c,&bg)||!gpu_v1_scissor(c,0,0,400,240)||!gpu_v1_copy(c,&source,0,0,0,0,400,240))return 0;
 // Static ambient light is baked once by the actual GPU into the scratch
 // backdrop; moving lights below are redrawn each frame.
 if(!luma_glow(c,LUMA_FX_X,LUMA_FX_Y,150,0x063f,50))return 0;
 for(unsigned p=0;p<2;++p){gpu_target dst=luma_target(p);if(!gpu_v1_target(c,&dst)||!gpu_v1_copy(c,&bg,0,0,0,0,400,240))return 0;}
 return 1;
}
// The final bloom expands from the sanctuary to cover every LCD corner.
// Opaque Gouraud interpolation avoids a full-screen alpha read/modify/write.
// An inscribed rectangle is overwritten by the opaque bloom. Restore only
// the four outside bands. In half-size coordinates its half extent r/3-3
// is strictly inside the 24-gon (r/2*cos(pi/24)), including integer rounding.
static int luma_bloom_restore(gpu_v1_context *c,const gpu_target *bg,unsigned age)
{
 int t=(int)age-1960,r=84+(t*t/240)*570/240,n=r/3-3;
 int cx=(LUMA_FX_X-144*t/240)/2,cy=(LUMA_FX_Y+50*t/240)/2;
 int x0=luma_clamp(cx-n,0,400),x1=luma_clamp(cx+n,0,400);
 int y0=luma_clamp(cy-n,0,240),y1=luma_clamp(cy+n,0,240);
 if(y0 && !gpu_v1_copy(c,bg,0,0,0,0,400,y0))return 0;
 if(y1<240 && !gpu_v1_copy(c,bg,0,y1,0,y1,400,240-y1))return 0;
 if(x0 && !gpu_v1_copy(c,bg,0,y0,0,y0,x0,y1-y0))return 0;
 if(x1<400 && !gpu_v1_copy(c,bg,x1,y0,x1,y0,400-x1,y1-y0))return 0;
 return 1;
}
static int luma_final_render(gpu_v1_context *c,unsigned age)
{
 if(age<2200){
  int t=(int)age-1960,progress=t*t/240;
  int cx=LUMA_FX_X-144*t/240,cy=LUMA_FX_Y+50*t/240,r=84+progress*570/240;
  if(!luma_material(c,GPU_V1_GOURAUD,0xffff,256))return 0;
  for(unsigned i=0;i<24;++i){unsigned p=i*256/24,q=(i+1)*256/24;
   gpu_vertex v[3]={luma_v(cx,cy,256,256,256),
    luma_v(cx+luma_cos(p)*r/16384,cy+luma_sin(p)*r/16384,35,180,230),
    luma_v(cx+luma_cos(q)*r/16384,cy+luma_sin(q)*r/16384,35,180,230)};
   if(!luma_triangle(c,v))return 0;
  }
  return luma_ring(c,cx,cy,r+10,256,0,age,0xafff,200);
 }
 // Readable title-card composition: moving orbital ribbons behind the hero.
 if(!luma_ring(c,558,228,182,256,age/4,age,0x4fff,180)||
    !luma_ring(c,558,228,214,105,age/5,age,0xff6a,180)||
    !luma_ring(c,558,228,205,95,256-age/6,age,0x9dff,150))return 0;
 for(unsigned i=0;i<3;++i){unsigned p=age/2+i*85;
  if(!luma_glow(c,558+luma_cos(p)*180/16384,228+luma_sin(p)*170/16384,30,0x5fff,150))return 0;
 }
 return 1;
}
static int luma_fx_render(gpu_v1_context *c,unsigned age,unsigned page)
{
 gpu_target dst=luma_target(page),bg=luma_target(3);
 unsigned act=age<360?0:age<980?1:age<1580?2:3;
 // Full background restore also makes arbitrary diagnostic seeks deterministic.
 // The half-size copy is only 192000 bytes, including during the grand finale.
 if(age>=2200)bg=(gpu_target){LUMA_FX_SKY,0,400,240,800,800};
 if(!gpu_v1_target(c,&dst)||!gpu_v1_scissor(c,0,0,400,240))return 0;
 if(age>=1960 && age<2200){if(!luma_bloom_restore(c,&bg,age))return 0;}
 else if(!gpu_v1_copy(c,&bg,0,0,0,0,400,240))return 0;
 if(age>=1960)return luma_final_render(c,age);
 // Only the opaque 3D objects test/write Z; their support is smaller still.
 if(act>=2 && !gpu_v1_clear(c,2,0,65535,208,36,128,120))return 0;
 int radius=age<360?24+(int)age/6:84+luma_sin(age)*5/16384;
 if(age>=360 && !luma_portal(c,age,radius))return 0;
 for(unsigned i=0;i<3;++i){unsigned p=age/2+i*85;
  int x=LUMA_FX_X+luma_cos(p)*110/16384,y=LUMA_FX_Y+luma_sin(p)*75/16384;
  if(!luma_glow(c,x,y,20,i==0?0xff45:i==1?0x07ff:0xb5ff,150))return 0;
 }
 if(!luma_ring(c,LUMA_FX_X,LUMA_FX_Y,radius+13,256,0,age,0x4fff,190))return 0;
 if(!luma_ring(c,LUMA_FX_X,LUMA_FX_Y,128,110,age/3,age,0xff8b,150))return 0;
 if(act>=2){
  if(!luma_ring(c,LUMA_FX_X,LUMA_FX_Y,135,100,256-age/4,age,0xb5ff,160))return 0;
  int scale=luma_clamp(((int)age-980)*230/100,10,230);
  if(!luma_crystal(c,age/2,LUMA_FX_X,LUMA_FX_Y,scale,0,360))return 0;
  // Shards cross the central crystal; changing their depth demonstrates Z16
  // occlusion in front of and behind it, independent of submission order.
  for(unsigned i=0;i<3;++i){unsigned p=age/2+i*85;int x=LUMA_FX_X+luma_cos(p)*94/16384,y=LUMA_FX_Y+luma_sin(p)*35/16384;
   if(!luma_crystal(c,age+i*21,x,y,luma_clamp(scale*62/230,4,62),1,360+luma_sin(p)*90/16384))return 0;}
 }
 if(act==3){int r=30+(age%100);if(!luma_ring(c,LUMA_FX_X,LUMA_FX_Y,r,200,age,age,0x9fff,(130-r)*2))return 0;}
 return 1;
}
static void luma_fx_layers(unsigned age,gpu_layer layers[16],gpu_sprite sprites[64],luma_info *info)
{
 memset(layers,0,sizeof(gpu_layer)*16);memset(sprites,0,sizeof(gpu_sprite)*64);
 unsigned n=0,act=age<360?0:age<980?1:age<1580?2:3;
 if(age>=2200){
  unsigned t=age-2200;
  // Screen-space particles use all sixty available slots, with varied speeds.
  for(unsigned i=0;i<60;++i){int x=(int)((i*137+age*(1+i%3))%864)-32;
   int y=(int)((i*83+age*(1+i%2))%528)-24;
   luma_fx(sprites,&n,(i%4)?1+(age/11+i)%4:9+(age/7+i)%4,x,y,i%3?4:12);}
  int y=480-luma_clamp((int)t,0,160)*440/160;
  layers[5]=luma_panel(LUMA_FX_PORTRAIT,352,440,20,y);
  if(t>=70){unsigned k=(unsigned)luma_clamp(((int)t-70)/5,0,15);
   const unsigned long logos[]={LUMA_FX_LOGO0,LUMA_FX_LOGO1,LUMA_FX_LOGO2,LUMA_FX_LOGO3,
    LUMA_FX_LOGO4,LUMA_FX_LOGO5,LUMA_FX_LOGO6,LUMA_FX_LOGO7,LUMA_FX_LOGO8,LUMA_FX_LOGO9,
    LUMA_FX_LOGO10,LUMA_FX_LOGO11,LUMA_FX_LOGO12,LUMA_FX_LOGO13,LUMA_FX_LOGO14,LUMA_FX_LOGO15};
   int w=176+16*(int)k,h=60+4*(int)k;
   layers[10]=luma_panel(logos[k],w,h,576-w/2,208-h/2);
  }
  if(t>160)layers[11]=luma_panel(LUMA_FX_CREDIT,416,80,368,294);
  *info=(luma_info){LUMA_FX_START+age,8,n,256,736,0,544,338};
  return;
 }
 int foot=228+luma_clamp((int)age,0,110);
 luma_actor hero={544,foot,age<110?1+(int)(age/10)%2:8,0};
 luma_fx(sprites,&n,0,528,foot-17,3);luma_character(sprites,&n,&hero,0,0);
 // Indexed particles remain native-resolution above the RGB565 scene.
 for(unsigned i=0;i<36;++i){unsigned p=age+i*71;int r=38+(int)((age+i*11)%118);
  int x=LUMA_FX_X+luma_cos(p)*r/16384,y=LUMA_FX_Y+luma_sin(p)*r/16384;
  luma_fx(sprites,&n,1+(age/9+i)%4,x-16,y-16,8);}
 if(act==3)for(unsigned i=0;i<15;++i){int x=(int)((i*71+age*2)%800),y=(int)((i*117+age*3)%400);
  luma_fx(sprites,&n,9+(age/8+i)%4,x-16,y-16,9);}
 if(age>=1960){*info=(luma_info){LUMA_FX_START+age,8,n,256,736,0,544,foot};return;}
 layers[12]=luma_panel(LUMA_HUD,272,48,16,14);
 layers[13]=luma_panel(LUMA_BADGE,144,30,640,14);
 const unsigned long caps[]={LUMA_FX_CAPTION0,LUMA_FX_CAPTION1,LUMA_FX_CAPTION2,LUMA_FX_CAPTION3};
 layers[14]=luma_panel(caps[act],576,56,112,410);
 *info=(luma_info){LUMA_FX_START+age,4+act,n,256,736,0,544,foot};
}
#endif
