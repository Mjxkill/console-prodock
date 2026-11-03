// ORBITAL R3: autonomous first-person adventure on the unchanged R31 GPU.
// Shared by the AE350 firmware and the host reference (tools/render_orbital.py).
//
// The station is a chain of convex rooms along z, joined by doors. Flat surfaces are
// rectangle clears (opcode 28), about twenty times cheaper per pixel than triangles on
// R31: walls are vertical bars, floors and ceilings are rows. The camera only yaws, so a
// screen column of a wall and a screen row of a floor each have one depth. Triangles are
// kept for what needs them: perspective textures, drones, additive lights.
#ifndef ORBITAL_SCENE_H
#define ORBITAL_SCENE_H
#include <stdint.h>
#include <string.h>
#include "gpu_v1.h"
#include "orbital_assets.h"
#define ORBITAL_FRAMES 13200U
// Pages: 0 and 1 colour (double buffer), 2 depth, 4 and 5 indexed HUD drawn by the 2D engine
// (double buffer), 6 and 7 colour and depth of the wall screens rendered every frame.
#define ORB_HUD_PAGE 4U
#define ORB_MONITOR GPU_PAGE_ADDR(6)
#define ORBITAL_STRIDE 800U
// Depth haze: the hardware fog formula of GPU_V1_FOG on the Z16 value, with the same three
// constants for the triangles (gpu_material) and for the rows and bars shaded by the CPU.
#define ORB_FOG_NEAR 56000
#define ORB_FOG_SCALE 2950U
#define ORB_FOG_COLOR 0x228eU
typedef struct { int x,y,z,u,v; } orb_point;
// Camera: x and z in 1/16 unit, yaw in 1/65536 turn, so that it glides instead of stepping
// (one whole angle step would be 1.4 degree: the whole picture would jump); y in units, bob in pixels.
typedef struct { int x,y,z,yaw,bob; } orb_camera;
typedef struct { unsigned frame,chapter,sprites,shots;int aim_x,aim_y; } orb_info;
static const int16_t orb_sines[65]={0,402,804,1205,1606,2006,2404,2801,3196,3590,3981,4370,4756,5139,5520,5897,6270,6639,7005,7366,7723,8076,8423,8765,9102,9434,9760,10080,10394,10702,11003,11297,11585,11866,12140,12406,12665,12916,13160,13395,13623,13842,14053,14256,14449,14635,14811,14978,15137,15286,15426,15557,15679,15791,15893,15986,16069,16143,16207,16261,16305,16340,16364,16379,16384};
static int orb_sin(unsigned p){p&=255;int v=orb_sines[(p&64)?64-(p&63):p&63];return p&128?-v:v;}
static int orb_cos(unsigned p){return orb_sin(p+64);}
// Fine angles, 1/65536 turn, by linear interpolation of the table.
// The camera yaw is asked for thousands of times per frame: the last value of each is kept.
static int orb_sine(int a){unsigned p=(unsigned)a&65535U;int s0=orb_sin(p>>8),s1=orb_sin((p>>8)+1);return s0+(s1-s0)*(int)(p&255)/256;}
static int orb_sinf(int a){static int last=1<<30,value;if(a!=last){last=a;value=orb_sine(a);}return value;}
static int orb_cosf(int a){static int last=1<<30,value;if(a!=last){last=a;value=orb_sine(a+16384);}return value;}
static int orb_clamp(int v,int a,int b){return v<a?a:v>b?b:v;}
static int orb_min(int a,int b){return a<b?a:b;}
static int orb_max(int a,int b){return a>b?a:b;}
static int orb_floor_div(int a,int b){int q=a/b;return (a%b && (a<0)!=(b<0))?q-1:q;}
// Smooth start and stop between two keys.
static int orb_ease(int a,int b,int t,int n){int u=t*1024/n;return a+(b-a)*(int)(((int64_t)u*u*(3072-2*u))>>20)/1024;}
// Bench only (firmware command B): 1 bars, 2 textured, 4 emissive triangles skipped, 16 no Z
// clear, 32 no sky, 64 no combat, 128 no rows, 256 full-screen sky first (coverage proof).
static unsigned orb_skip;
static int orb_depth(int z){return 60000-1600000/z;}
static int orb_depth16(int z){return 60000-25600000/z;}   // z in 1/16 unit

// ---------------------------------------------------------------- journey
enum { ORB_SAS,ORB_BAY,ORB_LIFT,ORB_REACTOR,ORB_ARENA,ORB_ESCAPE,ORB_DECK,ORB_CELLS };
#define ORB_OPENING 150U
static const unsigned orb_chapters[ORB_CELLS]={ORB_OPENING,2700,4300,5500,8100,10100,11800};
static orb_camera orb_view(unsigned t)
{
 // phase, x, y, z, yaw swing
 static const int16_t keys[][5]={{0,0,0,0,3},{400,0,0,150,3},{2400,0,0,1010,3},{2700,0,0,1160,10},{3900,0,0,1650,12},{4300,0,0,1950,4},
  {4400,0,0,1950,2},{5400,0,-900,1950,2},{5500,0,-900,1950,3},{6600,-130,-900,2560,8},{7000,-130,-900,2850,8},{7700,0,-900,3180,6},
  {8100,0,-900,3400,10},{10300,0,-900,3560,10},{10500,0,-900,3800,4},{11700,0,-900,4850,3},{12200,0,-900,5050,10},{13200,0,-900,5150,12}};
 unsigned i=0;while(i+2<sizeof(keys)/sizeof(*keys) && (int)t>=keys[i+1][0])++i;
 int dt=(int)t-keys[i][0],n=keys[i+1][0]-keys[i][0];if(dt>n)dt=n;
 int swing=orb_ease(keys[i][4],keys[i+1][4],dt,n),still=keys[i][3]==keys[i+1][3];
 // The guardian fight strafes slowly across the arena.
 int strafe=t>=8100&&t<10300?orb_sinf((int)(t-8100)*256/5)*1440/16384*orb_min((int)t-8100,200)/200*orb_min(10300-(int)t,200)/200:0;
 return (orb_camera){orb_ease(keys[i][1]*16,keys[i+1][1]*16,dt,n)+orb_sinf((int)t*256/7)*288/16384+strafe,orb_ease(keys[i][2],keys[i+1][2],dt,n),
  orb_ease(keys[i][3]*16,keys[i+1][3]*16,dt,n),orb_sinf((int)t*256/9)*swing/64,still?0:orb_sin(t*2)*2/16384};
}
// World point (units) to camera space, x y z all in 1/16 unit: ratios x/z and y/z are unchanged.
static orb_point orb_transform(orb_point p,orb_camera c)
{int x=p.x*16-c.x,z=p.z*16-c.z,cs=orb_cosf(c.yaw)/4,sn=orb_sinf(c.yaw)/4;return (orb_point){(x*cs-z*sn)/4096,(p.y-c.y)*16,(z*cs+x*sn)/4096,p.u,p.v};}   // 32 bits: |x|,|z| < 2^17

// ---------------------------------------------------------------- light of the frame
// Muzzle flash on near surfaces, coloured glows around explosions and the reactor core,
// red alert and final dawn. Computed by the CPU for rows and bars: no GPU cost.
enum { ORB_ORANGE,ORB_CYAN };
static struct { int muzzle,dawn,alarm,count,power[4],depth[4],kind[4]; } orb_env;
static void orb_lamp(int kind,int power,int depth)
{if(orb_env.count<4&&power>0){orb_env.kind[orb_env.count]=kind;orb_env.power[orb_env.count]=power;orb_env.depth[orb_env.count++]=depth;}}
static unsigned orb_tone(unsigned color,int light,int z)
{
 light+=orb_env.dawn;if(z<400)light+=orb_env.muzzle*(400-z)/400;
 int r=((int)(color>>11)*light+128)>>8,g=((int)((color>>5)&63)*light+128)>>8,b=((int)(color&31)*light+128)>>8;
 for(int i=0;i<orb_env.count;++i){int d=z-orb_env.depth[i];if(d<0)d=-d;if(d>=300)continue;
  int e=orb_env.power[i]*(300-d)/300;if(orb_env.kind[i]==ORB_ORANGE){r+=e>>3;g+=e>>3;}else{g+=e>>3;b+=e>>4;}}
 if(orb_env.alarm){r+=orb_env.alarm>>4;g=g*(512-orb_env.alarm)>>9;b=b*(512-orb_env.alarm)>>9;}
 r=r>31?31:r;g=g>63?63:g;b=b>31?31:b;
 int over=orb_depth(z)-ORB_FOG_NEAR,f=over<=0?0:orb_clamp((int)(((unsigned)over*ORB_FOG_SCALE)>>16),0,256);
 r=(r*(256-f)+(int)(ORB_FOG_COLOR>>11)*f+128)>>8;g=(g*(256-f)+(int)((ORB_FOG_COLOR>>5)&63)*f+128)>>8;b=(b*(256-f)+(int)(ORB_FOG_COLOR&31)*f+128)>>8;
 return (unsigned)(r<<11|g<<5|b);
}
static int orb_shade(int z,int y){return orb_clamp(310-z/6+y/6,95,256);}

// ---------------------------------------------------------------- triangles
static int orb_clip(const orb_point *in,int count,orb_point *out,int plane,int far)
{
 int n=0;for(int i=0;i<count;++i){orb_point a=in[i],b=in[(i+1)%count];int ia=far?a.z<=plane:a.z>=plane,ib=far?b.z<=plane:b.z>=plane;
  if(ia)out[n++]=a;
  if(ia!=ib){int d=b.z-a.z,t=plane-a.z;out[n++]=(orb_point){a.x+(int)((int64_t)(b.x-a.x)*t/d),a.y+(int)((int64_t)(b.y-a.y)*t/d),plane,a.u+(int)((int64_t)(b.u-a.u)*t/d),a.v+(int)((int64_t)(b.v-a.v)*t/d)};}
 }return n;
}
// type 0: lit colour, 1: perspective texture, 2: emissive colour, 3: perspective texture whose
// colour 0 is transparent. UV in texels of the base level; tex selects level and edge modes.
static int orb_quad(gpu_v1_context *c,orb_camera camera,const orb_point points[4],unsigned color,unsigned type,int bias,const gpu_texture_level *tex)
{
 if((orb_skip&2&&(type&1))||(orb_skip&4&&type==2))return 1;
 orb_point a[10],b[10];for(unsigned i=0;i<4;++i)a[i]=orb_transform(points[i],camera);
 int count=orb_clip(a,4,b,1024,0);if(count<3)return 1;count=orb_clip(b,count,a,28800,1);if(count<3)return 1;
 gpu_vertex v[10];for(int i=0;i<count;++i){int light=type==2?256:orb_clamp(orb_shade(a[i].z/16,a[i].y/16)+orb_env.dawn,95,256);
  v[i]=(gpu_vertex){200+a[i].x*180/a[i].z,120-a[i].y*180/a[i].z+camera.bob,a[i].u,a[i].v,orb_depth16(a[i].z)-bias,268435456/a[i].z,light,light,light};}
 int minx=10000,maxx=-10000,miny=10000,maxy=-10000;
 for(int i=0;i<count;++i){minx=orb_min(minx,v[i].x);maxx=orb_max(maxx,v[i].x);miny=orb_min(miny,v[i].y);maxy=orb_max(maxy,v[i].y);}
 if(maxx<0||minx>=400||maxy<24||miny>=221)return 1;
 gpu_material m={GPU_Z_TEST|GPU_Z_WRITE|(type==2?0:GPU_V1_GOURAUD|GPU_V1_FOG)|(type&1?GPU_RASTER_TEXTURE|GPU_PERSPECTIVE:0)|(type==3?GPU_KEY_ZERO:0),256,color,256,256,256,ORB_FOG_NEAR,ORB_FOG_COLOR,ORB_FOG_SCALE};
 if(!gpu_v1_material(c,&m))return 0;
 if((type&1)&&!gpu_v1_texture(c,tex))return 0;
 for(int i=1;i<count-1;++i){gpu_vertex q[3]={v[0],v[i],v[i+1]};int64_t area=(int64_t)(q[1].x-q[0].x)*(q[2].y-q[0].y)-(int64_t)(q[2].x-q[0].x)*(q[1].y-q[0].y);
  if(area>-16 && area<16)continue;
  if(!gpu_v1_triangle(c,q))return 0;
 }return 1;
}
// Decor textures are 128x128; a texture level carries its own size, mipmap level and edge modes.
static gpu_texture_level orb_tex(unsigned long base){return (gpu_texture_level){(uint32_t)base,128,128,256,GPU_RGB565,GPU_TEX_CLAMP,GPU_TEX_CLAMP,0};}
static int orb_floor(gpu_v1_context *c,orb_camera cam,int x0,int x1,int z0,int z1,int y,unsigned col,unsigned type,int bias,gpu_texture_level tex)
{int e=(tex.width<<tex.lod)-1;orb_point v[4]={{x0,y,z0,0,e},{x1,y,z0,e,e},{x1,y,z1,e,0},{x0,y,z1,0,0}};return orb_quad(c,cam,v,col,type,bias,&tex);}
static int orb_wall(gpu_v1_context *c,orb_camera cam,int x,int z0,int z1,int y0,int y1,unsigned col,unsigned type,int bias,gpu_texture_level tex)
{int e=(tex.width<<tex.lod)-1;orb_point v[4]={{x,y1,z0,0,0},{x,y1,z1,e,0},{x,y0,z1,e,e},{x,y0,z0,0,e}};return orb_quad(c,cam,v,col,type,bias,&tex);}
static int orb_front(gpu_v1_context *c,orb_camera cam,int x0,int x1,int z,int y0,int y1,unsigned col,unsigned type,int bias,gpu_texture_level tex)
{int e=(tex.width<<tex.lod)-1;orb_point v[4]={{x0,y1,z,0,0},{x1,y1,z,e,0},{x1,y0,z,e,e},{x0,y0,z,0,e}};return orb_quad(c,cam,v,col,type,bias,&tex);}

// ---------------------------------------------------------------- rows (floors, ceilings)
typedef struct { int x0,x1,z0,z1;unsigned color,emissive; } orb_tile;
// Screen column of a camera-space abscissa at a depth, both in 1/64 unit, pixel centres.
static int orb_column(int xq,int zq){xq=orb_clamp(xq,-zq*3/2,zq*3/2);return orb_floor_div(xq*360+zq*401,zq*2);}
// y is the height of the plane above the eye. box: first column, end column, first row, end row.
// With sky, only the sky is copied where the base tiles leave the box uncovered (background pass).
static int orb_rows(gpu_v1_context *c,orb_camera cam,int y,const orb_tile *tiles,unsigned count,unsigned base,const gpu_target *sky,int sx,const int box[4])
{
 int cs=orb_cosf(cam.yaw),sn=orb_sinf(cam.yaw),cy=120+cam.bob;if(!y)return 1;
 for(int sy=box[2];sy<box[3];++sy){int d=2*(sy-cy)+1;if(y>0)d=-d;if(d<=0)continue;
  int z=360*(y<0?-y:y)/d;if(z<64||z>1800)continue;
  int light=orb_shade(z,y),depth=orb_depth(z),n=z*cs,reach=((z*10/9+1)*(sn<0?-sn:sn)>>14)+2,zc=cam.z/16+n/16384;
  int span[40][3];unsigned spans=0;int covered=0;
  for(unsigned i=0;i<count&&spans<40;++i){const orb_tile *t=&tiles[i];if(t->z1<zc-reach||t->z0>zc+reach)continue;
   int a=orb_column(orb_floor_div(((t->x0*16-cam.x)*1024-z*sn)*64,cs),z*64),b=orb_column(orb_floor_div(((t->x1*16-cam.x)*1024-z*sn)*64,cs),z*64);
   int b0=(t->z0*16-cam.z)*1024,b1=(t->z1*16-cam.z)*1024;
   if(!sn){if(n<b0||n>=b1)continue;}
   else{int p=orb_column(orb_clamp(orb_floor_div((n-b0)*16,sn),-24*z,24*z)*4,z*64),q=orb_column(orb_clamp(orb_floor_div((n-b1)*16,sn),-24*z,24*z)*4,z*64);
    if(sn>0){a=orb_max(a,q);b=orb_min(b,p);}else{a=orb_max(a,p);b=orb_min(b,q);}}
   a=orb_max(a,box[0]);b=orb_min(b,box[1]);if(b<=a)continue;
   span[spans][0]=a;span[spans][1]=b-a;span[spans][2]=(int)(t->emissive?t->color:orb_tone(t->color,light,z));++spans;if(i<base)covered+=b-a;
  }
  if(sky){if(covered<box[1]-box[0]&&!gpu_v1_copy(c,sky,sx+box[0],8+sy,box[0],sy,(unsigned)(box[1]-box[0]),1))return 0;continue;}
  for(unsigned i=0;i<spans;++i)if(!gpu_v1_clear(c,3,(unsigned)span[i][2],(unsigned)depth,span[i][0],sy,(unsigned)span[i][1],1))return 0;
 }
 return 1;
}

// ---------------------------------------------------------------- bars (walls)
// side: x=p, z in a..b; else z=p, x in a..b. y0..y1 in world height. trim bit 0: the foot is
// cut by rows drawn later, bit 1: the head is; such edges overshoot, the others are exact.
// style 1: lift shaft, banded every 45 units with a bright ring every 360; 2: one flat shade.
typedef struct { int side,p,a,b,y0,y1;unsigned color;int trim,style; } orb_slab;
// Camera-space abscissa and depth of a world point, both in 1/64 unit.
static void orb_camera_point(orb_camera cam,int wx,int wz,int *xq,int *zq)
{int dx=wx*16-cam.x,dz=wz*16-cam.z,cs=orb_cosf(cam.yaw),sn=orb_sinf(cam.yaw);*xq=(dx*cs-dz*sn)/4096;*zq=(dz*cs+dx*sn)/4096;}
static int orb_wall_columns(orb_camera cam,int ax,int az,int bx,int bz,int *ca,int *cb)
{
 int xa,za,xb,zb;orb_camera_point(cam,ax,az,&xa,&za);orb_camera_point(cam,bx,bz,&xb,&zb);if(za<4096&&zb<4096)return 0;
 if(za<4096){xa=xb+(int)((int64_t)(xa-xb)*(zb-4096)/(zb-za));za=4096;}
 if(zb<4096){xb=xa+(int)((int64_t)(xb-xa)*(za-4096)/(za-zb));zb=4096;}
 int a=orb_clamp(orb_column(xa,za),0,400),b=orb_clamp(orb_column(xb,zb),0,400);*ca=orb_min(a,b);*cb=orb_max(a,b);return *cb>*ca;
}
// Depth, in 1/16 unit, of the wall on the ray through abscissa r/2 pixels - 200; 0 when it is not in front.
static int orb_wall_depth(orb_camera cam,const orb_slab *s,int r)
{
 int cs=orb_cosf(cam.yaw),sn=orb_sinf(cam.yaw),z;
 if(s->side){int den=(r*cs+360*sn)/360;z=den?(s->p*16-cam.x)*16384/den:0;}   // 32 bits: |p*16-x| < 2^13
 else{int den=cs-r*sn/360;z=den>0?(s->p*16-cam.z)*16384/den:0;}
 return z>=1024&&z<=28800?z:0;
}
// Screen row of a height y (units above the eye) at a depth z in 1/16 unit.
static int orb_edge(int cy,int y,int z){return orb_floor_div(cy*z-y*2880+z/2,z);}
// box: column and row limits of what can be seen of the room. limit: widest bar.
static int orb_bars(gpu_v1_context *c,orb_camera cam,const orb_slab *s,int depth,const int box[4],int limit)
{
 int ca,cb,cy=120+cam.bob,step=s->style!=1&&s->y1-s->y0>240?90:45,tolerance=s->style==2?3:1;if(s->y1<=s->y0||s->b<=s->a)return 1;
 if(!(s->side?orb_wall_columns(cam,s->p,s->a,s->p,s->b,&ca,&cb):orb_wall_columns(cam,s->a,s->p,s->b,s->p,&ca,&cb)))return 1;
 ca=orb_max(ca,box[0]);cb=orb_min(cb,box[1]);
 for(int x=ca,w;x<cb;x+=w){int z0=orb_wall_depth(cam,s,2*x+1-400);w=depth?16:!z0?1:z0<3200?16:z0<6400?8:z0<11200?4:2;w=orb_min(orb_min(w,limit),cb-x);
  int z1=orb_wall_depth(cam,s,2*(x+w)-1-400);
  // An exact edge may not move by more than a pixel across its bar (3 for a block, whose ends
  // lie on a floor and a ceiling already drawn): narrower bars on steep edges.
  for(;w>1&&z0&&z1;w/=2,z1=orb_wall_depth(cam,s,2*(x+w)-1-400)){
   int dh=s->trim&2?0:orb_edge(cy,s->y1-cam.y,z0)-orb_edge(cy,s->y1-cam.y,z1),df=s->trim&1?0:orb_edge(cy,s->y0-cam.y,z0)-orb_edge(cy,s->y0-cam.y,z1);
   if(dh>=-tolerance&&dh<=tolerance&&df>=-tolerance&&df<=tolerance)break;}
  int z=orb_wall_depth(cam,s,2*x+w-400);if(!z||!z0||!z1)continue;
  // Trimmed edges take the extreme of both ends of the bar, plus 2 pixels.
  int head=s->trim&2?orb_min(orb_edge(cy,s->y1-cam.y,z0),orb_edge(cy,s->y1-cam.y,z1))-2:orb_edge(cy,s->y1-cam.y,z);
  int foot=s->trim&1?orb_max(orb_edge(cy,s->y0-cam.y,z0),orb_edge(cy,s->y0-cam.y,z1))+2:orb_edge(cy,s->y0-cam.y,z);
  head=orb_clamp(head,box[2],box[3]);foot=orb_clamp(foot,box[2],box[3]);if(foot<=head)continue;
  if(depth){if(!gpu_v1_clear(c,2,0,(unsigned)orb_depth16(orb_max(z0,z1)),x,head,(unsigned)w,(unsigned)(foot-head)))return 0;continue;}
  // Shading bands on world heights (45 units, 90 on tall plain walls), so that they stay put
  // when the camera rides the lift.
  for(int ya=s->y0,yb;ya<s->y1;ya=yb){int band=orb_floor_div(ya,step);yb=s->style==2?s->y1:orb_min((band+1)*step,s->y1);
   int top=yb==s->y1?head:orb_clamp(orb_edge(cy,yb-cam.y,z),head,foot),bottom=ya==s->y0?foot:orb_clamp(orb_edge(cy,ya-cam.y,z),head,foot);
   if(bottom<=top)continue;
   int light=orb_shade(z/16,(ya+yb)/2-cam.y)+(s->style!=1?0:!(band&7)?70:(band&1)?-40:0);
   unsigned color=orb_tone(s->color,light,z/16);
   if(!gpu_v1_clear(c,1,color,0,x,top,(unsigned)w,(unsigned)(bottom-top)))return 0;}
 }
 return 1;
}
// Free-standing block (pillar, crate): its faces towards the camera, exact narrow bars with
// depth, drawn after the rows of its room and before nearer blocks.
static int orb_block(gpu_v1_context *c,orb_camera cam,int x0,int x1,int z0,int z1,int y0,int y1,unsigned color,const int box[4])
{
 if(orb_skip&1)return 1;
 orb_slab face[2]={{0,z0,x0,x1,y0,y1,color,0,2},{1,cam.x<x0*16?x0:x1,z0,z1,y0,y1,color,0,2}};unsigned faces=cam.x<x0*16||cam.x>x1*16?2:1;
 for(unsigned pass=0;pass<2;++pass)for(unsigned i=0;i<faces;++i)if(!orb_bars(c,cam,&face[i],(int)pass,box,16))return 0;
 return 1;
}

// ---------------------------------------------------------------- rooms
enum { ORB_SKY=1,ORB_GLASS=2,ORB_SHAFT=4 };
// floor..roof: heights. Far wall at z1 with a doorway of half-width gate up to height lintel
// (gate 0: closed end), sliding open from phase open during slide phases.
typedef struct { int16_t z0,z1,w,floor,roof;uint16_t flags,wall,tile0,tile1,ceiling;int16_t gate,lintel,open,slide; } orb_cell;
static const orb_cell orb_cells[ORB_CELLS]={
 {0,1080,200,-90,135,ORB_GLASS,0x6370,0x4aab,0x52eb,0x3189,200,135,1950,350},
 {1080,1800,300,-90,170,ORB_SKY,0x5b0e,0x4aab,0x52eb,0,110,110,3600,350},
 {1800,2100,150,-990,135,ORB_SHAFT,0x4a6b,0x5aca,0x4208,0x18c5,100,-765,5380,220},
 {2100,3300,330,-990,-630,0,0x4a8c,0x3a09,0x424a,0x2146,120,-765,7350,350},
 {3300,3900,330,-990,-630,ORB_GLASS,0x5acc,0x4a8a,0x52ab,0x2146,100,-765,10150,250},
 {3900,4900,200,-990,-765,ORB_GLASS,0x6370,0x4aab,0x52eb,0x3189,200,-765,11200,350},
 {4900,5700,300,-990,-955,ORB_SKY,0x52cd,0x4aab,0x52eb,0,0,-955,0,1}};
static int orb_aperture(const orb_cell *r,unsigned t){return r->gate?orb_clamp(((int)t-r->open)*r->gate/r->slide,0,r->gate):0;}
// The lift platform is the floor of its shaft and rides with the camera.
static int orb_ground(const orb_cell *r,orb_camera cam){return r->flags&ORB_SHAFT?orb_max(cam.y-90,r->floor):r->floor;}
typedef struct { int cell,box[4]; } orb_sight;
// Rooms in sight, nearest first, each with the screen box left by the doorways before it.
static int orb_sights(orb_camera cam,unsigned t,orb_sight v[ORB_CELLS])
{
 int i=0,n=1,cy=120+cam.bob;while(i<ORB_CELLS-1&&orb_cells[i].z1*16<=cam.z+1024)++i;
 v[0]=(orb_sight){i,{0,400,24,221}};
 for(;i<ORB_CELLS-1;++i){const orb_cell *r=&orb_cells[i];int a=orb_aperture(r,t),ca,cb,xq,za,zb;
  int low=orb_max(orb_ground(r,cam),orb_ground(r+1,cam));
  if(!a||r->z1*16-cam.z>28800||r->lintel<=low||!orb_wall_columns(cam,-a,r->z1,a,r->z1,&ca,&cb))break;
  orb_camera_point(cam,-a,r->z1,&xq,&za);orb_camera_point(cam,a,r->z1,&xq,&zb);
  // A jamb nearer than the near plane is out of the picture: the doorway reaches that edge of the box.
  if(za<4096)ca=v[n-1].box[0];
  if(zb<4096)cb=v[n-1].box[1];
  za=orb_max(za,4096)/4;zb=orb_max(zb,4096)/4;
  int top=orb_min(orb_edge(cy,r->lintel-cam.y,za),orb_edge(cy,r->lintel-cam.y,zb))-1,bottom=orb_max(orb_edge(cy,low-cam.y,za),orb_edge(cy,low-cam.y,zb))+1;
  orb_sight s={i+1,{orb_max(ca,v[n-1].box[0]),orb_min(cb,v[n-1].box[1]),orb_max(top,v[n-1].box[2]),orb_min(bottom,v[n-1].box[3])}};
  if(s.box[1]<=s.box[0]||s.box[3]<=s.box[2])break;
  v[n++]=s;}
 return n;
}
static unsigned orb_floor_tiles(const orb_cell *r,orb_camera cam,orb_tile tile[40],unsigned *base)
{
 unsigned n=0;
 if(r->flags&ORB_SHAFT){tile[n++]=(orb_tile){-r->w,r->w,r->z0,r->z1,r->tile0,0};*base=n;
  // Platform of the lift: orange edges and warning stripes, as free row tiles.
  tile[n++]=(orb_tile){-r->w+12,r->w-12,r->z0+12,r->z0+18,0xfd20,1};tile[n++]=(orb_tile){-r->w+12,r->w-12,r->z1-18,r->z1-12,0xfd20,1};
  for(int k=0;k<6;++k){tile[n++]=(orb_tile){-66+k*24,-54+k*24,r->z0+70,r->z1-70,0xe5a4,0};}
  return n;}
 // The first slab starts 24 units before the doorway: seen from the previous room, the floor
 // reaches under its threshold and no seam can open there (the nearer room paints over it).
 for(int z=r->z0,k=0;z<r->z1;z+=180,++k){int end=orb_min(z+180,r->z1),from=k?z:z-24;
  tile[n++]=(orb_tile){-r->w,0,from,end,(k&1)?r->tile0:r->tile1,0};tile[n++]=(orb_tile){0,r->w,from,end,(k&1)?r->tile1:r->tile0,0};}
 *base=n;
 for(int z=r->z0;z<r->z1;z+=180)for(int side=-1;side<=1;side+=2){int x=side*(r->w-24);tile[n++]=(orb_tile){x-2,x+2,z+8,orb_min(z+170,r->z1),cam.y<-400&&r->w>300?0xfbe0U:0x3e7fU,1};}
 return n;
}
// Sky through the glazing of the right wall (55 to 185 above the floor, or above the
// platform of the glass lift), row by row.
static int orb_window(gpu_v1_context *c,orb_camera cam,const orb_cell *r,const gpu_target *sky,int sx,const int box[4])
{
 int cs=orb_cosf(cam.yaw),sn=orb_sinf(cam.yaw),cy=120+cam.bob,xe,ze,ground=orb_ground(r,cam),up=ground+185-cam.y,down=cam.y-ground-55;
 orb_camera_point(cam,r->w,r->z1,&xe,&ze);if(ze<4096||up<=0||down<=0)return 1;
 int end=orb_column(xe,ze);
 for(int sy=box[2];sy<box[3];++sy){int e=2*(cy-sy)-1,z=e>0?up*360/e:down*360/-e,a=end;
  if(z<64)continue;
  if(z*64<ze)a=orb_max(end,orb_column(orb_floor_div(((r->w*16-cam.x)*1024-z*sn)*64,cs),z*64));
  a=orb_max(a,box[0]);if(a<box[1]&&!gpu_v1_copy(c,sky,sx+a,8+sy,a,sy,(unsigned)(box[1]-a),1))return 0;}
 return 1;
}
// Background pass of an open room: sky above the horizon of its floor, then wherever the
// floor does not reach. Copies of the same picture: overlapping rooms cannot disagree.
// For the lift, the sky behind its glazed far wall.
static int orb_backdrop(gpu_v1_context *c,orb_camera cam,const orb_sight *s,const gpu_target *sky,int sx)
{
 const orb_cell *r=&orb_cells[s->cell];
 if(r->flags&ORB_SHAFT){int a,b,xq,z0,z1,solid=orb_max(r->lintel,orb_ground(r,cam)+35)-cam.y,cy=120+cam.bob;
  if(!orb_wall_columns(cam,-r->w,r->z1,r->w,r->z1,&a,&b))return 1;
  orb_camera_point(cam,-r->w,r->z1,&xq,&z0);orb_camera_point(cam,r->w,r->z1,&xq,&z1);z0=orb_max(z0,4096)/4;z1=orb_max(z1,4096)/4;
  int foot=orb_clamp(orb_max(orb_edge(cy,solid,z0),orb_edge(cy,solid,z1))+2,s->box[2],s->box[3]);a=orb_max(a,s->box[0]);b=orb_min(b,s->box[1]);
  return b<=a||foot<=s->box[2]||gpu_v1_copy(c,sky,sx+a,8+s->box[2],a,s->box[2],(unsigned)(b-a),(unsigned)(foot-s->box[2]));}orb_tile tile[40];unsigned base,n=orb_floor_tiles(r,cam,tile,&base);
 int h=cam.y-orb_ground(r,cam),horizon=orb_clamp(120+cam.bob+(360*h/1801+1)/2,s->box[2],s->box[3]);
 // The far wall hides the sky behind it: below its head, only the strips on both sides.
 int ca,cb,xq,za,zb,upper=horizon;
 if(orb_wall_columns(cam,-r->w,r->z1,r->w,r->z1,&ca,&cb)){orb_camera_point(cam,-r->w,r->z1,&xq,&za);orb_camera_point(cam,r->w,r->z1,&xq,&zb);
  if(za>=4096&&zb>=4096)upper=orb_clamp(orb_max(orb_edge(120+cam.bob,r->roof-cam.y,za/4),orb_edge(120+cam.bob,r->roof-cam.y,zb/4))+2,s->box[2],horizon);}
 if(upper>s->box[2]&&!gpu_v1_copy(c,sky,sx+s->box[0],8+s->box[2],s->box[0],s->box[2],(unsigned)(s->box[1]-s->box[0]),(unsigned)(upper-s->box[2])))return 0;
 if(upper<horizon){int left=orb_clamp(ca+2,s->box[0],s->box[1]),right=orb_clamp(cb-2,s->box[0],s->box[1]);
  if(left>s->box[0]&&!gpu_v1_copy(c,sky,sx+s->box[0],8+upper,s->box[0],upper,(unsigned)(left-s->box[0]),(unsigned)(horizon-upper)))return 0;
  if(right<s->box[1]&&!gpu_v1_copy(c,sky,sx+right,8+upper,right,upper,(unsigned)(s->box[1]-right),(unsigned)(horizon-upper)))return 0;}
 (void)n;return orb_rows(c,cam,-h,tile,base,base,sky,sx,s->box);
}
// Props of a room, in triangles with depth test, then free-standing blocks.
static int orb_props(gpu_v1_context *c,orb_camera cam,unsigned t,int cell,const int box[4])
{
 const orb_cell *r=&orb_cells[cell];int ground=orb_ground(r,cam),a=orb_aperture(r,t),cz=cam.z/16;
 for(int z=r->z0;z<r->z1;z+=180){if(z+180<cz+64||z-cz>1500)continue;
  if(cell!=ORB_LIFT&&z+120<=r->z1&&z-cz<900&&!orb_floor(c,cam,-30,30,z+34,z+100,ground+1,0,1,12,orb_tex(ORBITAL_TEX_FLOOR)))return 0;
  if(r->flags&ORB_GLASS){
   // Window mullions, wall screens and light strips of the glazed corridors.
   if(!orb_wall(c,cam,r->w-2,z,z+14,ground+55,ground+185,0x9cf3,0,8,orb_tex(0))||!orb_front(c,cam,r->w-10,r->w,z+14,ground+55,ground+185,0x31c8,0,8,orb_tex(0)))return 0;
   if(!orb_wall(c,cam,-r->w+2,z+50,z+120,ground+65,ground+135,0,1,18,orb_tex(cell==ORB_ARENA?ORBITAL_TEX_PANEL:ORB_MONITOR)))return 0;
   if(!orb_wall(c,cam,-r->w+3,z+3,z+7,ground+15,ground+200,cell==ORB_ESCAPE?0xf9a6:0x2e5f,2,20,orb_tex(0)))return 0;}
  if(r->flags&ORB_SKY)for(int side=-1;side<=1;side+=2)if(!orb_wall(c,cam,side*(r->w-1),z,orb_min(z+180,r->z1),ground+36,ground+41,0x5f7f,2,10,orb_tex(0)))return 0;
 }
 // Station emblem inlaid in the bay floor: a 512x512 texture with three mipmap levels. Seen at
 // a grazing angle in a 400x240 picture it is always reduced: the level follows the distance.
 if(cell==ORB_BAY&&1560>cz+64){int d=1500-cz,lod=d>420?3:d>240?2:1;const unsigned long level[4]={ORBITAL_EMBLEM0,ORBITAL_EMBLEM1,ORBITAL_EMBLEM2,ORBITAL_EMBLEM3};
  gpu_texture_level tex={(uint32_t)level[lod],(uint16_t)(512>>lod),(uint16_t)(512>>lod),(uint16_t)(1024>>lod),GPU_RGB565,GPU_TEX_CLAMP,GPU_TEX_CLAMP,(uint8_t)lod};
  if(d<900&&!orb_floor(c,cam,-50,50,1450,1550,ground+1,0,1,12,tex))return 0;}
 // Perforated girders in front of the glazed wall of the lift: one 128x128 texture repeated
 // along the height (4 texels per unit, anchored to the shaft), colour 0 as transparency key.
 if(cell==ORB_LIFT)for(int side=-1;side<=1;side+=2){int x=side*52,top=orb_max(r->lintel,ground+35),y1=orb_min(r->roof,cam.y+120),y0=orb_max(top,cam.y-110);
  gpu_texture_level tex=orb_tex(ORBITAL_GIRDER);tex.v_mode=GPU_TEX_REPEAT;
  orb_point v[4]={{x-4,y1,r->z1-4,0,-y1*4},{x+4,y1,r->z1-4,127,-y1*4},{x+4,y0,r->z1-4,127,-y0*4},{x-4,y0,r->z1-4,0,-y0*4}};
  if(y1>y0&&!orb_quad(c,cam,v,0,3,10,&tex))return 0;}
 // Glowing edges of the sliding door, lit sill of a closed end.
 if(r->gate&&a<r->gate){int low=orb_max(ground,orb_ground(r+1,cam))+10;
  if(!orb_front(c,cam,-a-3,-a,r->z1-2,low,r->lintel-10,0x67df,2,16,orb_tex(0))||!orb_front(c,cam,a,a+3,r->z1-2,low,r->lintel-10,0x67df,2,16,orb_tex(0)))return 0;
  // Armour plate fixed on each leaf: it slides with the leaf and the wall swallows it, so
  // its visible width shrinks from the outer side with the matching part of the texture.
  if(r->lintel-low>=110)for(int side=-1;side<=1;side+=2){int inner=a+r->gate/2-22,outer=orb_min(inner+44,r->gate),u=127*(outer-inner)/44;gpu_texture_level tex=orb_tex(ORBITAL_TEX_DOOR);
   orb_point v[4]={{side*inner,low+100,r->z1-2,0,0},{side*outer,low+100,r->z1-2,u,0},{side*outer,low+56,r->z1-2,u,127},{side*inner,low+56,r->z1-2,0,127}};
   if(outer>inner&&!orb_quad(c,cam,v,0,1,14,&tex))return 0;}}
 if(!r->gate&&!orb_front(c,cam,-r->w,r->w,r->z1-2,r->roof-1,r->roof+4,0x4f5f,2,14,orb_tex(0)))return 0;
 // Hazard panels on both sides of a doorway narrower than its wall.
 if(r->gate&&r->gate<r->w)for(int side=-1;side<=1;side+=2){int x=side*(r->gate+40),low=orb_max(ground,orb_ground(r+1,cam));
  if(r->lintel-low>=80&&!orb_front(c,cam,x-22,x+22,r->z1-2,low+30,low+74,0,1,14,orb_tex(ORBITAL_TEX_CRATE)))return 0;}
 if(cell==ORB_REACTOR){
  // Six clad pillars, far ones first, and the pedestal of the core.
  for(int k=2;k>=0;--k)for(int side=-1;side<=1;side+=2){int x=side*210,z=2420+k*340;if(z+40<cz+64)continue;
   if(!orb_block(c,cam,x-22,x+22,z,z+44,ground,r->roof,0x5b0d,box)||(z-cz<400&&!orb_front(c,cam,x-18,x+18,z-1,ground+36,ground+96,0,1,14,orb_tex(ORBITAL_TEX_PILLAR))))return 0;}
  if(2650>cz+64&&!orb_block(c,cam,-46,46,2654,2746,ground,ground+52,0x4a6a,box))return 0;}
 if(cell==ORB_ARENA)for(int k=0;k<4;++k){int x=k&1?250:-250,z=k&2?3780:3520;if(z<cz+64)continue;
  if(!orb_block(c,cam,x-34,x+34,z,z+60,ground,ground+56,0x6b6d,box)||!orb_front(c,cam,x-20,x+20,z-1,ground+8,ground+48,0,1,14,orb_tex(ORBITAL_TEX_CRATE)))return 0;}
 return 1;
}
// One room inside its sight box: walls, glazing sky, floor, ceiling, props.
static int orb_room(gpu_v1_context *c,orb_camera cam,unsigned t,const orb_sight *s,const gpu_target *sky,int sx)
{
 const orb_cell *r=&orb_cells[s->cell];int ground=orb_ground(r,cam),a=orb_aperture(r,t),near=orb_max(r->z0,cam.z/16),open=r->flags&ORB_SKY;
 int low=s->cell<ORB_CELLS-1?orb_max(ground,orb_ground(r+1,cam)):ground,style=r->flags&ORB_SHAFT?1:0,head=open?1:3;
 orb_slab wall[10];unsigned n=0;
 if(open){wall[n++]=(orb_slab){1,-r->w,near,r->z1,ground,ground+38,0x528c,1,0};wall[n++]=(orb_slab){1,r->w,near,r->z1,ground,ground+38,0x528c,1,0};}
 else{wall[n++]=(orb_slab){1,-r->w,near,r->z1,ground,r->roof,r->wall,3,style};
  if(r->flags&ORB_GLASS){wall[n++]=(orb_slab){1,r->w,near,r->z1,ground,ground+55,0x52ed,3,0};wall[n++]=(orb_slab){1,r->w,near,r->z1,ground+185,r->roof,r->wall,3,0};}
  else wall[n++]=(orb_slab){1,r->w,near,r->z1,ground,r->roof,r->wall,3,style};}
 // Far wall: solid sides, sliding leaves, lintel above the doorway. The lift faces a glazed
 // wall: solid only up to the lintel of the door below, or to the rail of the platform.
 int shaft=r->flags&ORB_SHAFT,top=shaft?orb_max(r->lintel,ground+35):r->roof;if(shaft)head=1;   // glass above: exact head, foot cut by the platform
 if(!r->gate)wall[n++]=(orb_slab){0,r->z1,-r->w,r->w,ground,top,r->wall,head,style};
 else{
  wall[n++]=(orb_slab){0,r->z1,-r->w,-r->gate,ground,top,r->wall,head,style};wall[n++]=(orb_slab){0,r->z1,r->gate,r->w,ground,top,r->wall,head,style};
  // The leaves overshoot upwards: the ceiling rows or the lintel, drawn after them, cut their head.
  wall[n++]=(orb_slab){0,r->z1,-r->gate,-a,low,r->lintel,0x746f,(low==ground?1:0)|2,0};
  wall[n++]=(orb_slab){0,r->z1,a,r->gate,low,r->lintel,0x746f,(low==ground?1:0)|2,0};
  wall[n++]=(orb_slab){0,r->z1,-r->gate,r->gate,orb_max(r->lintel,ground),top,r->wall,(r->lintel<=ground?1:0)|(open||shaft?0:2),style};
  if(low>ground)wall[n++]=(orb_slab){0,r->z1,-r->gate,r->gate,ground,orb_min(low,top),r->wall,1,style};}
 if(!(orb_skip&1))for(unsigned pass=0;pass<2;++pass)for(unsigned i=0;i<n;++i)if(!orb_bars(c,cam,&wall[i],(int)pass,s->box,16))return 0;
 if((r->flags&ORB_GLASS)&&!(orb_skip&32)&&!orb_window(c,cam,r,sky,sx,s->box))return 0;
 // Frame of the glazed wall: transoms every 90 units of height, which scroll during the ride, and two posts.
 if(shaft&&!(orb_skip&1))for(unsigned pass=0;pass<2;++pass){
  for(int y=orb_floor_div(top,90)*90+90;y<r->roof;y+=90){orb_slab bar={0,r->z1,-r->w,r->w,y,y+7,0x9cf3,0,2};if(y-cam.y>-400&&y-cam.y<400&&!orb_bars(c,cam,&bar,(int)pass,s->box,16))return 0;}
  for(int side=-1;side<=1;side+=2){orb_slab post={0,r->z1,side*52-4,side*52+4,top,r->roof,0x9cf3,2,2};if(!orb_bars(c,cam,&post,(int)pass,s->box,16))return 0;}}
 if(!(orb_skip&128)){orb_tile tile[40];unsigned base,count=orb_floor_tiles(r,cam,tile,&base);
  if(!orb_rows(c,cam,ground-cam.y,tile,count,base,0,0,s->box))return 0;
  if(!open){count=0;
   for(int z=r->z0;z<r->z1;z+=180){tile[count++]=(orb_tile){-r->w,r->w,z==r->z0?z-24:z,orb_min(z+180,r->z1),r->ceiling,0};}
   base=count;
   for(int z=r->z0;z+13<r->z1;z+=180)tile[count++]=(orb_tile){-r->w+30,r->w-30,z+6,z+13,s->cell==ORB_ESCAPE?0xf9a6U:0x6f7fU,1};
   if(!orb_rows(c,cam,r->roof-cam.y,tile,count,base,0,0,s->box))return 0;}}
 return orb_props(c,cam,t,s->cell,s->box);
}

// ---------------------------------------------------------------- enemies and weapon
enum { ORB_DRONE,ORB_ELITE,ORB_GUARDIAN,ORB_SCOUT,ORB_RIDER=4 };  // rider: height relative to the camera (lift)
typedef struct { int16_t spawn,kill,kind,x,y,z,dz; } orb_enemy;
// Kills are at least 150 phases apart except the guardian's escorts: at most two bursts at
// once. render_orbital.py --sweep checks the 64-sprite limit on every phase.
#define ORB_ENEMIES 32
static const orb_enemy orb_enemies[ORB_ENEMIES]={
 {260,700,0,-55,5,520,-60},{420,860,0,40,30,640,-40},{700,1100,3,65,20,780,-60},{900,1300,1,-70,25,900,-80},{1150,1550,0,-35,0,960,-40},
 {1400,1800,0,60,35,1040,-60},{1650,2000,1,0,20,1060,0},
 {2350,2800,0,-90,22,1500,-80},{2500,2950,3,100,35,1560,-60},{2700,3120,1,0,60,1640,-100},{3170,3300,0,-140,40,1600,-40},{3200,3480,3,130,20,1700,-80},
 {3300,3700,1,-40,50,1760,-20},
 {4500,4900,7,-60,30,2060,0},{4800,5250,5,60,20,2070,0},
 {5650,6100,0,80,-880,2680,-60},{5900,6350,0,-100,-860,2820,-60},{6430,6600,1,95,-870,2900,-80},{6450,6850,3,-55,-850,3050,-60},{6700,7100,0,100,-880,3150,-40},
 {6950,7350,1,-95,-860,3230,-30},{7150,7550,3,60,-870,3285,0},
 {8400,8800,0,-180,-860,3700,-60},{8700,9100,0,180,-850,3720,-60},{9000,9400,1,-120,-820,3740,-80},{9420,9700,1,140,-840,3740,-80},{8200,10000,2,0,-860,3830,0},
 {10600,10900,3,-60,-880,4500,-200},{10850,11150,3,70,-860,4850,-200},
 {11900,12300,3,-100,-860,5400,-60},{12050,12450,0,100,-850,5450,-60},{12200,12600,1,0,-830,5500,-60}};
static int orb_kind(const orb_enemy *e){return e->kind&3;}
static int orb_last(const orb_enemy *e){return orb_kind(e)==ORB_GUARDIAN?150:75;}   // phases of the burst
static int orb_aimed(const orb_enemy *e){return e->kill-(orb_kind(e)==ORB_GUARDIAN?280:110);}   // first shot
static int orb_enemy_pos(unsigned t,unsigned i,orb_camera camera,orb_point *out)
{
 const orb_enemy *e=&orb_enemies[i];if((int)t<e->spawn||(int)t>e->kill+orb_last(e))return 0;
 int life=orb_min((int)t,e->kill)-e->spawn,sway=orb_kind(e)==ORB_GUARDIAN?70:orb_kind(e)==ORB_SCOUT?44:24;
 orb_point p={e->x+orb_sin(t/3+i*53)*sway/16384,e->y+(e->kind&ORB_RIDER?camera.y:0)+orb_sin(t+i*31)*12/16384,e->z+e->dz*life/(e->kill-e->spawn),0,0};
 *out=orb_transform(p,camera);return out->z>=1024 && out->z<28800;   // camera space, 1/16 unit
}
// The enemy being engaged and how far the rifle has turned to it, 0..256. The rifle starts
// turning 40 phases before the first shot and comes back in 30 after the kill.
static int orb_engage(unsigned t,int *blend)
{
 *blend=0;for(unsigned i=0;i<ORB_ENEMIES;++i){const orb_enemy *e=&orb_enemies[i];int first=orb_aimed(e),now=(int)t;
  if(now>=first-40&&now<e->kill+30){*blend=now<first?(now-first+40)*256/40:now<e->kill?256:(e->kill+30-now)*256/30;return (int)i;}}
 return -1;
}
static int orb_shoot(unsigned t,int *target)
{int blend;*target=orb_engage(t,&blend);if(*target<0)return 0;const orb_enemy *e=&orb_enemies[*target];return (int)t>=orb_aimed(e)&&(int)t<e->kill&&t%12<3;}
typedef struct { int frame,x,y,aim_x,aim_y,muzzle_x,muzzle_y,target,firing; } orb_rifle;
// Rifle of the native HUD: frame turned to the aim point, layer position, muzzle on the LCD.
static orb_rifle orb_weapon(unsigned t,orb_camera cam)
{
 static const int16_t muzzle[17][2]=ORBITAL_MUZZLES;
 orb_rifle w={8,254,167,400,236,0,0,-1,0};int blend;w.target=orb_engage(t,&blend);w.firing=orb_shoot(t,&w.target);
 orb_point p;if(w.target>=0&&orb_enemy_pos(orb_min(t,(unsigned)orb_enemies[w.target].kill),(unsigned)w.target,cam,&p)){
  w.aim_x=400+(p.x*360/p.z)*blend/256;w.aim_y=236+(4-p.y*360/p.z+cam.bob*2)*blend/256;}
 w.aim_x=orb_clamp(w.aim_x,60,740);w.aim_y=orb_clamp(w.aim_y,70,400);
 // Frame whose barrel points best at the aim point (all barrels have the same length).
 int vx=w.aim_x-(w.x+ORBITAL_PIVOT_X),vy=w.aim_y-(w.y+ORBITAL_PIVOT_Y),best=-(1<<30);
 for(int i=0;i<17;++i){int dot=(muzzle[i][0]-ORBITAL_PIVOT_X)*vx+(muzzle[i][1]-ORBITAL_PIVOT_Y)*vy;if(dot>best){best=dot;w.frame=i;}}
 int recoil=w.firing?7:0;if(w.firing&&w.frame>0)--w.frame;
 // Steep frames are lowered so that the cut wrist stays behind the bottom band.
 w.x+=orb_sin(t*2)*3/16384+recoil;w.y+=orb_sin(t*4)*3/16384+recoil+orb_max(0,8-w.frame)*5;
 if(t>=12750)w.y+=(int)(t-12750)*2;
 w.muzzle_x=w.x+muzzle[w.frame][0];w.muzzle_y=w.y+muzzle[w.frame][1];return w;
}

// ---------------------------------------------------------------- effects
// Additive lights; depth 0 disables the depth test (screen-space effects).
static int orb_glow(gpu_v1_context *c,int x,int y,int r,unsigned color,unsigned alpha,int depth)
{
 gpu_material m={GPU_V1_ADDITIVE|GPU_V1_GOURAUD|(depth?GPU_Z_TEST:0),alpha,color,256,256,256,0,0,0};if(r<1||!gpu_v1_material(c,&m))return r<1;
 for(unsigned i=0;i<12;++i){unsigned a=i*256/12,b=(i+1)*256/12;gpu_vertex v[3]={{x,y,0,0,depth,65536,256,256,256},{x+orb_cos(a)*r/16384,y+orb_sin(a)*r/16384,0,0,depth,65536,0,0,0},{x+orb_cos(b)*r/16384,y+orb_sin(b)*r/16384,0,0,depth,65536,0,0,0}};if(!gpu_v1_triangle(c,v))return 0;}return 1;
}
// Shock wave: a ring of 12 Gouraud quads, bright inside, black outside.
static int orb_ring(gpu_v1_context *c,int x,int y,int r,int w,unsigned color,unsigned alpha,int depth)
{
 gpu_material m={GPU_V1_ADDITIVE|GPU_V1_GOURAUD|(depth?GPU_Z_TEST:0),alpha,color,256,256,256,0,0,0};if(!gpu_v1_material(c,&m))return 0;
 for(unsigned i=0;i<12;++i){unsigned a=i*256/12,b=(i+1)*256/12;gpu_vertex v[4]={{x+orb_cos(a)*r/16384,y+orb_sin(a)*r/16384,0,0,depth,65536,256,256,256},
   {x+orb_cos(a)*(r+w)/16384,y+orb_sin(a)*(r+w)/16384,0,0,depth,65536,0,0,0},{x+orb_cos(b)*(r+w)/16384,y+orb_sin(b)*(r+w)/16384,0,0,depth,65536,0,0,0},
   {x+orb_cos(b)*r/16384,y+orb_sin(b)*r/16384,0,0,depth,65536,256,256,256}};
  if(!gpu_v1_quad(c,v))return 0;}
 return 1;
}
// An enemy is drawn as runs of occupied texture cells: transparent texels cost as much as
// opaque ones on R31, so the empty third of each pose is simply not sent.
// roll: rotation about the centre, in 1/256 turn.
static int orb_sprite(gpu_v1_context *c,unsigned image,int texels,int left,int top,int size,int z,int roll)
{
 static const uint8_t cells[16][8]=ORBITAL_CELLS;int cell=texels/8,cs=orb_cos((unsigned)roll),sn=orb_sin((unsigned)roll),cx=left+size/2,cy=top+size/2;
 // A rolled sprite is one quad: oblique strips mean many short spans, each with a fixed set-up cost.
 if(roll){int h=size/2;gpu_vertex v[4]={{-h,-h,0,0,z,65536,256,256,256},{size-h,-h,texels,0,z,65536,256,256,256},{size-h,size-h,texels,texels,z,65536,256,256,256},{-h,size-h,0,texels,z,65536,256,256,256}};
  for(int k=0;k<4;++k){int dx=v[k].x,dy=v[k].y;v[k].x=cx+(dx*cs-dy*sn)/16384;v[k].y=cy+(dx*sn+dy*cs)/16384;}
  return gpu_v1_quad(c,v);}
 for(int row=0;row<8;++row)for(int a=0,b;a<8;a=b+1){unsigned mask=size<32?255U:cells[image][row];
  for(;a<8&&!(mask>>a&1);++a){}
  for(b=a;b<8&&(mask>>b&1);++b){}
  if(b==a)break;
  int x0=left+size*a/8,x1=left+size*b/8,y0=top+size*row/8,y1=top+size*(row+1)/8;
  gpu_vertex v[4]={{x0,y0,a*cell,row*cell,z,65536,256,256,256},{x1,y0,b*cell,row*cell,z,65536,256,256,256},{x1,y1,b*cell,row*cell+cell,z,65536,256,256,256},{x0,y1,a*cell,row*cell+cell,z,65536,256,256,256}};
  if(x1>x0&&y1>y0&&!gpu_v1_quad(c,v))return 0;}
 return 1;
}
// Scripted blasts of the evacuation and the far bursts of the finale: phase, x, y, z.
static const int16_t orb_blasts[][4]={{10230,-150,-860,3750},{10420,160,-850,3950},{10640,-170,-880,4350},{10800,180,-860,4560},{10960,-160,-850,4700},
 {11120,150,-870,4900},{11300,-170,-860,5000},{11460,160,-880,5060},{12620,-500,-500,6400},{12700,620,-420,6600},{12780,80,-380,6800}};
#define ORB_BLASTS (sizeof(orb_blasts)/sizeof(*orb_blasts))
static void orb_light(unsigned t,orb_camera cam)
{
 int target;orb_env.muzzle=orb_shoot(t,&target)?56:0;orb_env.count=0;orb_env.dawn=orb_clamp(((int)t-12700)*70/300,0,70);
 // Red alert from the fall of the guardian until the outer deck.
 orb_env.alarm=t>=10000&&t<11900?(70+orb_sin(t*5)*60/16384)*orb_min(orb_min((int)t-10000,11900-(int)t),100)/100:0;   // same as orb_alarm
 for(unsigned i=0;i<ORB_ENEMIES;++i){int dt=(int)t-orb_enemies[i].kill;orb_point p;
  if(dt>=0&&dt<40&&orb_enemy_pos(t,i,cam,&p))orb_lamp(ORB_ORANGE,(40-dt)*(orb_kind(&orb_enemies[i])==ORB_GUARDIAN?8:4),p.z/16);}
 for(unsigned i=0;i<ORB_BLASTS;++i){int dt=(int)t-orb_blasts[i][0];orb_point p=orb_transform((orb_point){orb_blasts[i][1],orb_blasts[i][2],orb_blasts[i][3],0,0},cam);
  if(dt>=0&&dt<50&&p.z>=1024)orb_lamp(ORB_ORANGE,(50-dt)*4,p.z/16);}
 // The reactor core breathes; faster once it is critical.
 if(cam.z/16+64<2700&&cam.z/16>1700&&cam.y<-800)orb_lamp(ORB_CYAN,70+orb_sin(t*4)*40/16384,2700-cam.z/16);
}
static int orb_screen(orb_camera cam,orb_point world,int *x,int *y,int *z)
{orb_point p=orb_transform(world,cam);if(p.z<1024||p.z>=28800)return 0;*x=200+p.x*180/p.z;*y=120-p.y*180/p.z+cam.bob;*z=p.z/16;return 1;}
static int orb_combat(gpu_v1_context *c,orb_camera cam,unsigned t)
{
 static const unsigned long texs[4][4]={{ORBITAL_DRONE0,ORBITAL_DRONE1,ORBITAL_DRONE2,ORBITAL_DRONE3},{ORBITAL_ELITE0,ORBITAL_ELITE1,ORBITAL_ELITE2,ORBITAL_ELITE3},
  {ORBITAL_GUARDIAN0,ORBITAL_GUARDIAN1,ORBITAL_GUARDIAN2,ORBITAL_GUARDIAN3},{ORBITAL_SCOUT0,ORBITAL_SCOUT1,ORBITAL_SCOUT2,ORBITAL_SCOUT3}};
 static const int16_t span[4]={125,160,330,120},limit[4]={96,88,116,84};  // world size, largest size on screen
 orb_rifle rifle=orb_weapon(t,cam);int sx,sy,sz;
 // Reactor core: breathing light and two counter-swinging rings above its pedestal.
 if(cam.y<-800&&orb_screen(cam,(orb_point){0,-990+140,2700,0,0},&sx,&sy,&sz)){int r=orb_min(46*180/sz,26),d=orb_depth(sz),pulse=orb_sin(t*4)*r/16384/4;
  if(!orb_glow(c,sx,sy,r*3/2+pulse,0x3e9f,170,d)||!orb_glow(c,sx,sy,r+pulse,0xdfff,255,d)||
     !orb_ring(c,sx,sy,r*2+orb_sin(t*3)*r/16384/2,orb_max(2,r/4),0x5f7f,170,d)||!orb_ring(c,sx,sy,r*3-orb_sin(t*3)*r/16384/2,orb_max(2,r/6),0x2c9f,120,d))return 0;}
 // Enemies, far ones first.
 int order[ORB_ENEMIES],depth[ORB_ENEMIES],n=0;orb_point p;
 for(int i=0;i<ORB_ENEMIES;++i)if(orb_enemy_pos(t,(unsigned)i,cam,&p)){int k=n++;for(;k>0&&depth[k-1]<p.z;--k){order[k]=order[k-1];depth[k]=depth[k-1];}order[k]=i;depth[k]=p.z;}
 for(int k=0;k<n;++k){int i=order[k];const orb_enemy *e=&orb_enemies[i];orb_enemy_pos(t,(unsigned)i,cam,&p);
  int kind=orb_kind(e),last=orb_last(e),dt=(int)t-e->kill,cx=200+p.x*180/p.z,cy=120-p.y*180/p.z+cam.bob,z=orb_depth16(p.z);
  int size=orb_clamp(span[kind]*2880/p.z,10,limit[kind]),hit=rifle.target==i&&(int)t>=orb_aimed(e)&&t%12>=8;
  unsigned pose=dt>=0?3:hit?2:kind==ORB_GUARDIAN&&dt>-350?(t%40<20?2:1):t%160<32?1:0;
  unsigned alpha=dt>=0?(unsigned)(last-dt)*256/(unsigned)last:256;if(dt>=0)size+=dt*size/600;
  // Scouts bank from side to side (rotation of the textured quad, about twice the cost of a straight one).
  int roll=kind==ORB_SCOUT&&dt<0?orb_sin(t*3+(unsigned)i*40)*8/16384:0;
  // Arrival: the enemy fades in behind a shrinking flash.
  int born=(int)t-e->spawn;if(born<32)alpha=(unsigned)born*8;
  gpu_texture_level tex={(uint32_t)texs[kind][pose],kind==ORB_GUARDIAN?256:128,kind==ORB_GUARDIAN?256:128,kind==ORB_GUARDIAN?512:256,GPU_ARGB4444,GPU_TEX_CLAMP,GPU_TEX_CLAMP,0};
  gpu_material m={GPU_RASTER_TEXTURE|GPU_Z_TEST|GPU_Z_WRITE,alpha,0,256,256,256,0,0,0};
  if(!gpu_v1_texture(c,&tex)||!gpu_v1_material(c,&m)||!orb_sprite(c,(unsigned)kind*4+pose,kind==ORB_GUARDIAN?256:128,cx-size/2,cy-size/2,size,z,roll))return 0;
  if(born<32&&!orb_glow(c,cx,cy,4+(32-born)*size/128,0x9e7f,(unsigned)(32-born)*7,0))return 0;
  if(dt>=0&&dt<45&&!orb_ring(c,cx,cy,(8+dt*3)*size/96,3+size/16,0xfd88,(unsigned)(45-dt)*5,0))return 0;
  if(dt>=0&&dt<50&&!orb_glow(c,cx,cy,(8+dt/2)*size/110+4,0xfc44,(unsigned)(50-dt)*4,0))return 0;
  // The guardian falls apart in a chain of secondary blasts.
  if(kind==ORB_GUARDIAN&&dt>=0)for(int b=0;b<4;++b){int bt=dt-20-b*22;if(bt<0||bt>=36)continue;
   int bx=cx+orb_cos((unsigned)(b*77+30))*size/16384/3,by=cy+orb_sin((unsigned)(b*77+30))*size/16384/4;
   if(!orb_glow(c,bx,by,6+bt*2/3,0xfe66,(unsigned)(36-bt)*6,0)||!orb_ring(c,bx,by,4+bt*3/2,3,0xfd88,(unsigned)(36-bt)*5,0))return 0;}
  // Incoming plasma travels towards the camera; the shield answers on the native HUD.
  unsigned shot=(t+(unsigned)i*37)%(kind==ORB_GUARDIAN?70U:160U);
  if(dt<0&&born>=32&&shot<50){int d=50-(int)shot,x=200+(cx-200)*d/50,y=120+(cy-120)*d/50;
   if(!orb_glow(c,x,y,(3+(int)shot/7)*(kind==ORB_GUARDIAN?2:1),kind==ORB_GUARDIAN?0xfb20:0xf05f,200,0))return 0;}
 }
 // Rifle bolts fly from the turned muzzle to the target in eight phases.
 if(rifle.target>=0&&(int)t>=orb_aimed(&orb_enemies[rifle.target])&&(int)t<orb_enemies[rifle.target].kill+8&&orb_enemy_pos(orb_min(t,(unsigned)orb_enemies[rifle.target].kill),(unsigned)rifle.target,cam,&p)){
  int age=(int)(t%12),tx=200+p.x*180/p.z,ty=120-p.y*180/p.z+cam.bob,mx=rifle.muzzle_x/2,my=rifle.muzzle_y/2;
  if(age<8&&(int)t-age>=orb_aimed(&orb_enemies[rifle.target])&&(int)t-age<orb_enemies[rifle.target].kill){
   int x0=mx+(tx-mx)*age/8,y0=my+(ty-my)*age/8,x1=mx+(tx-mx)*(age+1)/8,y1=my+(ty-my)*(age+1)/8;
   gpu_material beam={GPU_V1_ADDITIVE,230,0xffcc,256,256,256,0,0,0};if(!gpu_v1_material(c,&beam))return 0;
   gpu_vertex v[4]={{x0-1,y0,0,0,0,65536,256,256,256},{x0+1,y0+1,0,0,0,65536,256,256,256},{x1+1,y1+1,0,0,0,65536,256,256,256},{x1-1,y1,0,0,0,65536,256,256,256}};
   if(!gpu_v1_quad(c,v)||!orb_glow(c,x1,y1,7-age/2,0xffb0,230,0))return 0;}
  if(age>=8&&age<11&&!orb_glow(c,tx,ty,12-(age-8)*3,0xff85,200,0))return 0;}
 // Scripted blasts: evacuation behind the walls, far bursts over the outer deck.
 for(unsigned i=0;i<ORB_BLASTS;++i){int dt=(int)t-orb_blasts[i][0];
  if(dt<0||dt>=60||!orb_screen(cam,(orb_point){orb_blasts[i][1],orb_blasts[i][2],orb_blasts[i][3],0,0},&sx,&sy,&sz))continue;
  int r=orb_clamp(9000/sz,3,40);
  if(!orb_glow(c,sx,sy,r+dt*r/30,0xfdaa,(unsigned)(60-dt)*4,0)||!orb_ring(c,sx,sy,r/2+dt*r/12,orb_max(2,r/5),0xfd88,(unsigned)(60-dt)*3,0))return 0;}
 if(t>=12600){
  // Finale: reinforcements cross the sky in formation, then the dawn grows behind the title.
  gpu_texture_level tex={ORBITAL_DRONE0,128,128,256,GPU_ARGB4444,GPU_TEX_CLAMP,GPU_TEX_CLAMP,0};gpu_material m={GPU_RASTER_TEXTURE,256,0,170,256,256,0,0,0};
  if(!gpu_v1_texture(c,&tex)||!gpu_v1_material(c,&m))return 0;
  for(int k=0;k<7;++k){int lag=k<4?k:7-k,x=470-(int)(t-12600)*2/3+lag*44-k*8,y=34+lag*10+(k<4?0:lag*12)+cam.bob,size=34-lag*3;
   if(x>-40&&x<420&&!orb_sprite(c,0,128,x,y,size,0,0))return 0;}
  int grow=orb_clamp(((int)t-12700)*86/300,0,86),radius=grow+orb_sin(t*3)*grow/16384/12;
  if(radius>2&&!orb_glow(c,200,96+cam.bob,radius,0xfed2,210,0))return 0;}
 return 1;
}

// ---------------------------------------------------------------- wall screens
static unsigned orb_kills(unsigned t){unsigned n=0;for(unsigned i=0;i<ORB_ENEMIES;++i)if((int)t>=orb_enemies[i].kill)++n;return n;}
// The wall screens show a picture rendered every frame into a 128x128 texture: a radar sweep
// in additive Gouraud triangles and readouts written by the GPU text of the driver.
static int orb_monitor(gpu_v1_context *c,unsigned t)
{
 gpu_target screen={ORB_MONITOR,GPU_PAGE_ADDR(7),128,128,256,256};char line[12]="DRONES 00";unsigned kills=orb_kills(t);
 line[7]=(char)('0'+kills/10);line[8]=(char)('0'+kills%10);
 if(!gpu_v1_target(c,&screen)||!gpu_v1_scissor(c,0,0,128,128)||!gpu_v1_clear(c,1,0x0128,0,0,0,128,128)||!gpu_v1_clear(c,1,0x0a4f,0,0,0,128,18))return 0;
 gpu_material m={GPU_V1_ADDITIVE|GPU_V1_GOURAUD,220,0x07ff,256,256,256,0,0,0};if(!gpu_v1_material(c,&m))return 0;
 unsigned a=t*3;gpu_vertex v[3]={{64,74,0,0,0,65536,256,256,256},{64+orb_cos(a)*44/16384,74+orb_sin(a)*44/16384,0,0,0,65536,160,160,160},{64+orb_cos(a-24)*44/16384,74+orb_sin(a-24)*44/16384,0,0,0,65536,0,0,0}};
 gpu_vertex w[3]={{64,74,0,0,0,65536,256,256,256},{64+orb_cos(a+128)*30/16384,74+orb_sin(a+128)*30/16384,0,0,0,65536,60,60,60},{64+orb_cos(a+104)*30/16384,74+orb_sin(a+104)*30/16384,0,0,0,65536,0,0,0}};
 if(!gpu_v1_triangle(c,v)||!gpu_v1_triangle(c,w))return 0;
 return gpu_v1_text(c,ORBITAL_FONT,4,1,0xffff,256,1,"CAM 07")&&gpu_v1_text(c,ORBITAL_FONT,28,108,t%60<40?0xffe0U:0xfbe0U,256,1,line);
}

// ---------------------------------------------------------------- frame
static int orbital_render(gpu_v1_context *c,unsigned t,unsigned page)
{
 orb_camera cam=orb_view(t);gpu_target dst={GPU_PAGE_ADDR(page),GPU_PAGE_ADDR(2),400,240,800,800};orb_light(t,cam);
 orb_sight sight[ORB_CELLS];int n=orb_sights(cam,t,sight);
 // Night sky over the upper level, dawn over the lower one: never both in sight.
 gpu_target sky={sight[0].cell>=ORB_REACTOR?ORBITAL_SKY2:ORBITAL_SKY,0,512,256,1024,1024};int sx=56+cam.yaw*3/256;
 // Rooms with wall screens: their texture is redrawn first, then the texture cache is told.
 int screens=0;for(int k=0;k<n;++k)screens|=sight[k].cell==ORB_SAS||sight[k].cell==ORB_ESCAPE;   // in sight, even through a doorway
 if(t>=ORB_OPENING&&screens&&!(orb_skip&2)){if(!orb_monitor(c,t))return 0;gpu_v1_invalidate(c);}
 // The HUD hides rows 0..23 and 221..239; they are kept black so that the page is fully defined.
 if(!gpu_v1_target(c,&dst)||!gpu_v1_scissor(c,0,0,400,240)||!gpu_v1_clear(c,1,0,0,0,0,400,24)||!gpu_v1_clear(c,1,0,0,0,221,400,19)||
    (!(orb_skip&16)&&!gpu_v1_clear(c,2,0,65535,0,24,400,197))||!gpu_v1_scissor(c,0,24,400,197))return 0;
 if((orb_skip&256)&&!gpu_v1_copy(c,&sky,sx,8+24,0,24,400,197))return 0;
 // Opening: the illustration fills the 3D window under the title.
 if(t<ORB_OPENING){gpu_target art={ORBITAL_ART,0,400,197,800,800};return gpu_v1_copy(c,&art,0,0,0,24,400,197);}
 // Background: the sky of every open room in sight. Then the rooms, farthest first, each
 // clipped to what its doorways leave: nearer walls and floors simply paint over.
 if(!(orb_skip&32))for(int k=0;k<n;++k)if((orb_cells[sight[k].cell].flags&(ORB_SKY|ORB_SHAFT))&&!orb_backdrop(c,cam,&sight[k],&sky,sx))return 0;
 for(int k=n-1;k>=0;--k){const int *b=sight[k].box;
  if(!gpu_v1_scissor(c,(unsigned)b[0],(unsigned)b[2],(unsigned)(b[1]-b[0]),(unsigned)(b[3]-b[2]))||!orb_room(c,cam,t,&sight[k],&sky,sx))return 0;}
 if(!gpu_v1_scissor(c,0,24,400,197))return 0;
 return (orb_skip&64)||orb_combat(c,cam,t);
}
static gpu_layer orb_layer(unsigned long base,int w,int h,int x,int y)
{return gpu_make_layer(base,w,w,h,x,y,w,h,0,0,GPU_LAYER_ENABLE|GPU_LAYER_KEY_ZERO);}
static void orb_fx(gpu_sprite s[64],unsigned *n,unsigned long base,int x,int y,unsigned priority,unsigned flip)
{if(*n<64&&x>-32&&x<800&&y>-32&&y<480)s[(*n)++]=gpu_make_sprite(base,x,y,32,32,priority,GPU_SPRITE_ENABLE|flip);}
static int orb_alarm(unsigned t){return t>=10000&&t<11900?(70+orb_sin(t*5)*60/16384)*orb_min(orb_min((int)t-10000,11900-(int)t),100)/100:0;}
static int orb_shield(unsigned t){return t%160<60&&t>260&&t<12600?180+(int)(t%160)*2/3:220;}
static unsigned orb_shots(unsigned t)
{unsigned shots=0;for(unsigned i=0;i<ORB_ENEMIES;++i){const orb_enemy *e=&orb_enemies[i];int first=orb_aimed(e),end=orb_min((int)t+1,e->kill);if(end>first)shots+=(unsigned)((end+11)/12-(first+11)/12);}return shots;}

// ---------------------------------------------------------------- HUD drawn by the 2D engine
// Indexed colours of the fixed end of the palette (tools/build_orbital_assets.py).
enum { ORB_INK_WHITE=240,ORB_INK_CYAN,ORB_INK_GOLD,ORB_INK_PINK,ORB_INK_NAVY,ORB_INK_STEEL,ORB_INK_CREAM,ORB_INK_TEAL,ORB_INK_ORANGE,ORB_INK_SKYBLUE,ORB_INK_ICE,ORB_INK_RED,ORB_INK_SAND };
// Regions of the HUD page shown by layers: motion tracker, two counters, clock, shield gauge.
enum { ORB_HUD_COUNT_Y=100,ORB_HUD_TOP_Y=140 };   // counters 130x32 (kills at 0, rounds at 98); top strip 400x16 (shield at 0, clock at 334)
static void orb_draw(void (*emit)(const gpu_command *),unsigned op,unsigned page,int x,int y,int a,int b,unsigned fg,unsigned bg)
{gpu_command cmd=gpu_make_command(op,page,0,x,y,a,b,0,0,fg,bg);emit(&cmd);}
static void orb_print(void (*emit)(const gpu_command *),unsigned page,int x,int y,unsigned fg,unsigned scale,const char *text)
{
 gpu_command cmd=gpu_make_command(GPU_TEXT,page,0,x,y,0,(int)scale,0,0,fg,0);unsigned n=0;
 for(;n<16&&text[n];++n)cmd.words[4+n/4]|=(uint32_t)(uint8_t)text[n]<<(8*(n%4));
 cmd.words[2]|=n<<16;emit(&cmd);
}
// The 2D engine draws the HUD page: disk, circles, lines and a rotating sweep for the motion
// tracker, one disk per enemy, text for the counters and the mission clock, a horizontal
// gradient for the shield. Opcodes 1 to 9 of the indexed path, no CPU pixel.
// previous: phase whose HUD the page still holds (it was drawn two frames ago), or -1 for a
// page that only holds zeroes. The tracker is redrawn every frame; counters, clock and shield
// only when their value differs, which leaves the page exactly as a full redraw would.
static void orbital_hud(unsigned t,int previous,unsigned page,void (*emit)(const gpu_command *))
{
 orb_camera cam=orb_view(t);unsigned old=previous<0?0U:(unsigned)previous;
 orb_draw(emit,GPU_FILL,page,0,0,96,96,0,0);orb_draw(emit,GPU_DISK,page,48,48,47,0,ORB_INK_NAVY,0);
 orb_draw(emit,GPU_CIRCLE,page,48,48,47,0,ORB_INK_CYAN,0);orb_draw(emit,GPU_CIRCLE,page,48,48,24,0,ORB_INK_TEAL,0);
 // Sweep and its trail.
 for(unsigned k=0;k<2;++k){unsigned a=t*3-k*6;orb_draw(emit,GPU_LINE,page,48,48,48+orb_cos(a)*45/16384,48+orb_sin(a)*45/16384,k?ORB_INK_SKYBLUE:ORB_INK_ICE,0);}
 for(unsigned i=0;i<ORB_ENEMIES;++i){const orb_enemy *e=&orb_enemies[i];if((int)t<e->spawn||(int)t>=e->kill)continue;
  int dx=orb_clamp((e->x-cam.x/16)/8,-40,40),dz=orb_clamp((e->z-cam.z/16)/16,-40,40),kind=orb_kind(e);
  orb_draw(emit,GPU_DISK,page,48+dx,48-dz,kind==ORB_GUARDIAN?5:3,0,kind==ORB_GUARDIAN?ORB_INK_GOLD:kind==ORB_ELITE?ORB_INK_ORANGE:kind==ORB_SCOUT?ORB_INK_SAND:ORB_INK_RED,0);}
 // The player: a small triangle of three lines.
 orb_draw(emit,GPU_LINE,page,48,42,53,54,ORB_INK_CREAM,0);orb_draw(emit,GPU_LINE,page,53,54,43,54,ORB_INK_CREAM,0);orb_draw(emit,GPU_LINE,page,43,54,48,42,ORB_INK_CREAM,0);
 // Counters in double-size text: drones destroyed, rounds left.
 unsigned kills=orb_kills(t),ammo=32-orb_shots(t)%32;char two[3]={0,0,0};
 if(previous<0||kills!=orb_kills(old)||ammo!=32-orb_shots(old)%32){
  orb_draw(emit,GPU_FILL,page,0,ORB_HUD_COUNT_Y,130,32,0,0);
  two[0]=(char)('0'+kills/10);two[1]=(char)('0'+kills%10);orb_print(emit,page,0,ORB_HUD_COUNT_Y,ORB_INK_ICE,2,two);
  two[0]=(char)('0'+ammo/10);two[1]=(char)('0'+ammo%10);orb_print(emit,page,98,ORB_HUD_COUNT_Y,ammo<6?ORB_INK_RED:ORB_INK_ICE,2,two);}
 // Mission clock, 55 phases per second.
 unsigned seconds=t*100/5504;
 if(previous<0||seconds!=old*100/5504){char clock[8]="T+00:00";clock[2]=(char)('0'+seconds/600);clock[3]=(char)('0'+seconds/60%10);clock[5]=(char)('0'+seconds%60/10);clock[6]=(char)('0'+seconds%10);
  orb_draw(emit,GPU_FILL,page,334,ORB_HUD_TOP_Y,64,16,0,0);orb_print(emit,page,334,ORB_HUD_TOP_Y,ORB_INK_SKYBLUE,1,clock);}
 // Shield: gradient across the 16-colour ramp 224..239, as wide as the shield is strong.
 if(previous<0||orb_shield(t)!=orb_shield(old)){orb_draw(emit,GPU_FILL,page,0,ORB_HUD_TOP_Y,256,8,0,0);orb_draw(emit,GPU_GRAD_H,page,0,ORB_HUD_TOP_Y,orb_shield(t),8,224,239);}
}
// Colours animated outside the frame transaction: the cyan accents of the HUD turn red with the alert.
static uint32_t orbital_palette(unsigned t,unsigned index,uint32_t color)
{
 int alarm=orb_alarm(t);if(!alarm||(index!=ORB_INK_CYAN&&index!=ORB_INK_ICE&&index!=ORB_INK_SKYBLUE&&index!=ORB_INK_TEAL))return color;
 int f=alarm*2,r=(int)(color>>12&63),g=(int)(color>>6&63),b=(int)(color&63);
 r+=(63-r)*f/256;g-=g*f/384;b-=b*f/320;return (uint32_t)(r<<12|g<<6|b);
}
// Native 800x480 HUD. hud: indexed page just redrawn by orbital_hud for this frame.
static void orbital_layers(unsigned t,unsigned hud,gpu_layer layers[16],gpu_sprite sprites[64],orb_info *info)
{
 memset(layers,0,sizeof(gpu_layer)*16);memset(sprites,0,sizeof(gpu_sprite)*64);unsigned n=0,chapter=0;unsigned long page=GPU_PAGE_ADDR(hud);
 while(chapter+1<ORB_CELLS&&t>=orb_chapters[chapter+1])++chapter;
 orb_camera cam=orb_view(t);orb_rifle w=orb_weapon(t,cam);
 if(t>=ORB_OPENING)layers[4]=orb_layer(ORBITAL_WEAPON+(unsigned long)w.frame*ORBITAL_WEAPON_W*ORBITAL_WEAPON_H,ORBITAL_WEAPON_W,ORBITAL_WEAPON_H,w.x,w.y);
 if(t>=ORB_OPENING&&t<12750)layers[5]=orb_layer(ORBITAL_CROSSHAIR,32,32,w.aim_x-16,w.aim_y-16);
 layers[6]=orb_layer(ORBITAL_TOP,800,48,0,0);layers[7]=orb_layer(ORBITAL_BOTTOM,800,38,0,442);
 // Three regions of the HUD page: top strip (shield and clock), tracker, counters.
 layers[9]=gpu_make_layer(page+ORB_HUD_TOP_Y*800UL,800,400,16,318,29,400,16,0,0,GPU_LAYER_ENABLE|GPU_LAYER_KEY_ZERO);
 if(t>=ORB_OPENING)layers[1]=gpu_make_layer(page,800,96,96,16,338,96,96,0,0,GPU_LAYER_ENABLE|GPU_LAYER_KEY_ZERO);
 layers[10]=gpu_make_layer(page+ORB_HUD_COUNT_Y*800UL,800,130,32,640,445,130,32,0,0,GPU_LAYER_ENABLE|GPU_LAYER_KEY_ZERO);
 const unsigned long caps[ORB_CELLS]={ORBITAL_CAPTION0,ORBITAL_CAPTION1,ORBITAL_CAPTION2,ORBITAL_CAPTION3,ORBITAL_CAPTION4,ORBITAL_CAPTION5,ORBITAL_CAPTION6};
 if(t>=orb_chapters[chapter]&&t-orb_chapters[chapter]<150)layers[8]=orb_layer(caps[chapter],448,64,176,65);
 if(t<ORB_OPENING)layers[15]=orb_layer(ORBITAL_TITLE,512,150,144,282);
 if(t>=12800)layers[15]=orb_layer(ORBITAL_FINISH,512,110,144,166);
 // Guardian gauge: its armour melts under fire.
 if(t>=8230&&t<10000){int life=t<9720?230:230*(10000-(int)t)/280;
  layers[2]=orb_layer(ORBITAL_GAUGE,320,32,240,58);layers[3]=gpu_make_layer(ORBITAL_SHIELD,256,256,8,322,70,orb_max(life,2),8,0,0,GPU_LAYER_ENABLE);}
 // Alert ticker: a tile map layer scrolled by the compositor, three pixels per phase, with
 // horizontally flipped tiles for the arrows pointing back. No drawing command at all.
 if(orb_alarm(t))layers[0]=gpu_make_tile_layer(ORBITAL_TICKER,ORBITAL_TILES,16,6,0,0,52,800,16,(t*3)%1024,0,GPU_LAYER_ENABLE|GPU_LAYER_KEY_ZERO|GPU_LAYER_WRAP_X);
 if(w.firing){orb_fx(sprites,&n,ORBITAL_EFFECTS+(4+t%4)*1024UL,w.muzzle_x-16,w.muzzle_y-16,5,0);orb_fx(sprites,&n,ORBITAL_EFFECTS+2*1024UL,w.aim_x-16,w.aim_y-16,5,0);}
 // Debris of a destroyed enemy, twice as many for the guardian, mirrored one way or the other.
 for(unsigned i=0;i<ORB_ENEMIES;++i){const orb_enemy *e=&orb_enemies[i];int dt=(int)t-e->kill,count=orb_kind(e)==ORB_GUARDIAN?24:12;if(dt<0||dt>75)continue;orb_point p;if(!orb_enemy_pos((unsigned)e->kill,i,cam,&p))continue;
  int x=400+p.x*360/p.z,y=240-p.y*360/p.z;for(int k=0;k<count;++k){unsigned a=(unsigned)(k*256/count);int r=dt*(2+k%3);
   orb_fx(sprites,&n,ORBITAL_EFFECTS+(unsigned)(k%8)*1024UL,x+orb_cos(a)*r/16384-16,y+orb_sin(a)*r/16384+dt*dt/70-16,3,(k&1?GPU_SPRITE_FLIP_X:0U)|(k&2?GPU_SPRITE_FLIP_Y:0U));}}
 *info=(orb_info){t,chapter,n,(unsigned)w.firing,w.aim_x,w.aim_y};
}
#endif
