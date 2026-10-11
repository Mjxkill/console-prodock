// ASTRILLA: floating camera, filtered scenery, GPU textured objects and effects.
#ifndef ASTRILLA_SCENE_H
#define ASTRILLA_SCENE_H
#include <stdint.h>
#include <string.h>
#include "gpu_v1.h"
#include "astrilla_assets.h"
#define ASTRILLA_HZ 55U
#define ASTRILLA_FRAMES 16500U
#define AS_BG GPU_PAGE_ADDR(6)
#define AS_CACHE_BASE 0x0a000000UL
#define AS_CACHE_FRAMES 1870U
#define AS_CACHE_BYTES (AS_CACHE_FRAMES*192000UL)
typedef struct {unsigned frame,chapter,sprites,shots;} astrilla_info;
static const unsigned as_keys[11]={0,1925,3850,5500,7150,8800,10450,12375,14300,15675,16500};
static unsigned as_chapter(unsigned t){unsigned k=0;while(k<9&&t>=as_keys[k+1])++k;return k;}
static int as_min(int a,int b){return a<b?a:b;}
static int as_max(int a,int b){return a>b?a:b;}
static float af_clamp(float a,float lo,float hi){return a<lo?lo:a>hi?hi:a;}
static int af_round(float x){return (int)(x+(x<0?-.5f:.5f));}
static float af_sin(float a){int i=(int)a;if(a<(float)i)--i;float f=a-(float)i;unsigned j=(unsigned)i&255;return ((float)as_sines[j]+(float)(as_sines[j+1]-as_sines[j])*f)/16384.f;}
static float af_cos(float a){return af_sin(a+64.f);}
static float af_ease(float t){t=af_clamp(t,0,1);return t*t*(3.f-2.f*t);}
static unsigned as_hash(unsigned v){v^=v>>16;v*=0x7feb352d;v^=v>>15;v*=0x846ca68b;return v^(v>>16);}
typedef struct {uint32_t base;int width,height;int32_t u,v,ux,vx,uy,vy,lens;float seconds,roll,travel,shot;} as_camera;
// Camera plates are filtered at boot, then copied by the GPU. Only the
// background is cached; all foreground geometry/effects are rendered live.
static unsigned as_plate(unsigned t){
 unsigned k=as_chapter(t),local=t-as_keys[k];
 if(k==2)return local<660?220+local:880+(local-660)%110;
 if(k==3||k==6)return 880+local%110;
 if(k==8)return 990+(local<330?local:329);
 if(k==9)return 1320+(local<550?local:549);
 if(k==4)return 110;
 if(k==7)return 73;
 return local%220;
}
static unsigned as_plate_time(unsigned i){
 if(i<220)return i;
 if(i<880)return 3850+i-220;
 if(i<990)return 4510+i-880;
 if(i<1320)return 14300+i-990;
 return 15675+i-1320;
}
static as_camera as_view(unsigned t){
 unsigned k=as_chapter(t),plate=as_plate(t);float seconds=(float)t/55.f;
 float shot=(float)(t-as_keys[k])/220.f,e=(float)((t-as_keys[k])%220)/219.f,cx=512.f,cy=176.f,zoom=1.f,roll=0;
 uint32_t base=ASTRILLA_COSMOS;int width=1024,height=352,lens=0;
 if(k==2&&plate<880){
  // A single accelerating infall. The camera never banks or backs away.
  float q=(float)(plate-220)/659.f;zoom=.85f;
  lens=af_round((10.f+30.f*q+245.f*q*q*q)*16.f);
 }else if(k==2||k==3||k==6){base=ASTRILLA_WORMHOLE;height=512;cy=256.f;zoom=.78f;lens=-1-(int)(plate-880);
 }else if(k>=8){base=ASTRILLA_VALLEY;width=800;height=400;
  if(k==8){float q=af_ease((float)(plate-990)/329.f);cx=350.f+60.f*q;cy=210.f+40.f*q;zoom=.98f-.13f*q;}
  else{float q=af_ease((float)(plate-1320)/549.f);cx=410.f+30.f*q;cy=250.f+63.8f*q;zoom=.85f-.57f*q;}
 }else{float q=(float)plate/219.f;cx=265.f+475.f*q;cy=171.f+10.f*q;zoom=.85f;roll=.015f;}
 float sn=af_sin(roll*40.743665f),cs=af_cos(roll*40.743665f),ux=zoom*cs,vx=zoom*sn,uy=-zoom*sn,vy=zoom*cs;
 return (as_camera){base,width,height,af_round((cx-200.f*ux-120.f*uy)*65536.f),af_round((cy-200.f*vx-120.f*vy)*65536.f),
  af_round(ux*65536.f),af_round(vx*65536.f),af_round(uy*65536.f),af_round(vy*65536.f),lens,seconds,roll,e,shot};
}
// Objects on the ground use the inverse of the *same quantized camera* as the
// background. No independent screen-space coordinates can slide over terrain.
static void as_ground(const as_camera *c,float wx,float wy,float *x,float *y,float *scale){
 float a=c->ux/65536.f,b=c->uy/65536.f,d=c->vx/65536.f,e=c->vy/65536.f,det=a*e-b*d;
 float u=wx-c->u/65536.f,v=wy-c->v/65536.f;
 *x=(u*e-b*v)/det;*y=(a*v-u*d)/det;*scale=1.f/a;
}
typedef struct {float x,y,dx,dy;} as_motion;
static as_motion as_curve(float u,float x0,float y0,float x1,float y1,float x2,float y2,float x3,float y3){
 float v=1.f-u;return (as_motion){v*v*v*x0+3*v*v*u*x1+3*v*u*u*x2+u*u*u*x3,
 v*v*v*y0+3*v*v*u*y1+3*v*u*u*y2+u*u*u*y3,
 3*v*v*(x1-x0)+6*v*u*(x2-x1)+3*u*u*(x3-x2),3*v*v*(y1-y0)+6*v*u*(y2-y1)+3*u*u*(y3-y2)};
}
static float as_heading(float x,float y){
 float ax=x<0?-x:x,ay=y<0?-y:y;if(ax+ay<.0001f)return 0;
 float r=ax>ay?ay/ax:ax/ay,a=r*(32.f+11.12f*(1.f-r));if(ay>ax)a=64.f-a;
 if(x<0)a=128.f-a;
 return y<0?-a:a;
}
static float as_turn(float angle){while(angle>128.f)angle-=256.f;while(angle<-128.f)angle+=256.f;return angle;}
static as_motion as_flagship(float seconds){return (as_motion){355.f-seconds*7.1f,35.f+seconds*4.8f,-7.1f,4.8f};}
typedef struct {float x,y,size,gx,gy,scale,altitude;} as_landing_pose;
static as_landing_pose as_landing(unsigned t){
 unsigned k=as_chapter(t);float local=(float)(t-as_keys[k])/55.f;
 float q=k==8?af_ease(local/18.f):1.f,alt=90.f*(1.f-q),x,y,scale;
 as_camera cam=as_view(t);as_ground(&cam,270.f+170.f*q,265.f+60.f*q,&x,&y,&scale);
 float size=30.f*(1.f+alt/80.f)*scale;
 return (as_landing_pose){x,y-alt*scale-size*.18f,size,x,y,scale,alt};
}
// Four-bit bilinear weights (1/16 texel). Camera coordinates remain Q16 until
// sampling. The texture never stays still for 20 frames then jumps two LCD pixels.
static inline __attribute__((always_inline)) unsigned as_mix(unsigned a,unsigned b,unsigned f){
 unsigned x=((a<<16)|a)&0x07e0f81fU,y=((b<<16)|b)&0x07e0f81fU;
 unsigned q=(x+(((y-x)*f)>>4))&0x07e0f81fU;return (q|(q>>16))&65535;
}
static inline __attribute__((always_inline)) unsigned as_sample(const uint16_t *source,const as_camera *c,int32_t u,int32_t v){
 int ix=u>>16,iy=v>>16;unsigned fu=((unsigned)u>>12)&15,fv=((unsigned)v>>12)&15;
 if(ix<0){ix=0;fu=0;}if(ix>=c->width-1){ix=c->width-2;fu=15;}
 if(iy<0){iy=0;fv=0;}if(iy>=c->height-1){iy=c->height-2;fv=15;}
 const uint16_t *s=source+iy*c->width+ix;
 return as_mix(as_mix(s[0],s[1],fu),as_mix(s[c->width],s[c->width+1],fu),fv);
}
// Stylized gravitational lens: non-affine sky sampling, dark capture region,
// bright photon ring and an inclined, advecting accretion disk. Integer maths
// keeps the independently implemented reference bit-exact with the AE350.
static __attribute__((optimize("O3"))) void astrilla_background(unsigned t,uint16_t *out,const uint8_t *assets){
 as_camera c=as_view(t);const uint16_t *source=(const uint16_t *)(assets+c.base-ASTRILLA_BASE);
 unsigned radius2=(unsigned)(c.lens*c.lens)>>8;
 for(int y=0;y<240;++y){int32_t u=c.u+c.uy*y,v=c.v+c.vy*y;
  for(int x=0;x<400;++x,u+=c.ux,v+=c.vx){
   if(c.lens<=0){int32_t uu=u,vv=v;
    if(c.lens<0){int phase=(-c.lens-1)*256/110;
     uu+=as_sines[(unsigned)(y*2+phase)&255]*100;
     vv+=as_sines[(unsigned)(x*2-phase)&255]*68;}
    out[y*400+x]=(uint16_t)as_sample(source,&c,uu,vv);continue;}

   int dx=x-200,dy=y-120;unsigned d2=(unsigned)(dx*dx+dy*dy)+1;
   if(d2<radius2*3/4){out[y*400+x]=0;continue;}
   unsigned bend=radius2*4096U/(d2+radius2/4+1),gain=(55706U*(4096U+2*bend))>>12;
   unsigned pixel=as_sample(source,&c,512*65536+dx*(int)gain,176*65536+dy*(int)gain);
   int delta=(int)d2-(int)radius2;if(delta<0)delta=-delta;
   unsigned rel=(unsigned)as_min(1024,delta*256/(int)(radius2+1));
   unsigned ring=255U*256/(256+rel*rel),halo=100U*radius2/(d2+radius2);
   int hx=dx+(dy>>2),hy=dy-(dx>>2),diskdelta=hx*hx+25*hy*hy-(int)radius2*4;
   if(diskdelta<0)diskdelta=-diskdelta;
   unsigned dr=(unsigned)as_min(1024,diskdelta*128/(int)(radius2*4+1));
   unsigned disk=255U*400/(400+dr*dr);
   unsigned ripple=208U+((unsigned)(as_sines[(unsigned)(hx*2+hy*5+(int)t/2)&255]+16384)*47>>15);
   disk=disk*ripple/255;
   unsigned r=as_min(31,(pixel>>11)+(ring*24+disk*31+halo*3)/255);
   unsigned g=as_min(63,((pixel>>5)&63)+(ring*60+disk*40+halo*8)/255);
   unsigned b=as_min(31,(pixel&31)+(ring*27+disk*8+halo*10)/255);
   out[y*400+x]=(uint16_t)((r<<11)|(g<<5)|b);
  }
 }
}
#define TRY(v) do{if(!(v))return 0;}while(0)
static int as_mat(gpu_v1_context *c,unsigned color,unsigned alpha,unsigned flags,unsigned r,unsigned g,unsigned b){gpu_material m={flags,alpha,color,r,g,b,0,0,0};return gpu_v1_material(c,&m);}
static uint32_t as_xy(int x,int y){return ((uint32_t)(uint16_t)x<<16)|(uint16_t)y;}
static void as_rawtri(gpu_v1_context *c,int x0,int y0,int x1,int y1,int x2,int y2){gpu_command q={{27U<<24,as_xy(x0,y0),as_xy(x1,y1),as_xy(x2,y2),0,0,0,0}};c->emit(&q);}
static int as_beam(gpu_v1_context *c,float x,float y,float xx,float yy,float width,unsigned color,unsigned alpha){
 float dx=xx-x,dy=yy-y,n=dx<0?-dx:dx;n+=(dy<0?-dy:dy);if(n<.01f)return 1;float px=-dy*width/n,py=dx*width/n;
 TRY(as_mat(c,color,alpha,GPU_V1_ADDITIVE,256,256,256));
 as_rawtri(c,af_round(x-px),af_round(y-py),af_round(xx-px),af_round(yy-py),af_round(xx+px),af_round(yy+py));
 as_rawtri(c,af_round(x-px),af_round(y-py),af_round(xx+px),af_round(yy+py),af_round(x+px),af_round(y+py));return 1;
}
// Affine UV planes preserve fractional object centres. All occupied cells use
// the same mapping, eliminating redundant per-triangle planes and texture seams.
static int as_image(gpu_v1_context *c,uint32_t base,int tw,int th,float x,float y,float width,float height,float angle,unsigned alpha,unsigned flags,unsigned tint,int kind){
 if(width<1.f||height<1.f)return 1;
 float flip=kind>=0&&(kind&8)?-1.f:1.f;
 float sn=af_sin(angle),cs=af_cos(angle),ax=flip*cs*width/(float)tw,ay=flip*sn*width/(float)tw,bx=-sn*height/(float)th,by=cs*height/(float)th;
 gpu_texture_level tex={base,(uint16_t)tw,(uint16_t)th,(uint16_t)(tw*2),GPU_ARGB4444,GPU_TEX_CLAMP,GPU_TEX_CLAMP,0};
 TRY(gpu_v1_texture(c,&tex));unsigned tr=(tint>>16)&255,tg=(tint>>8)&255,tb=tint&255;
 TRY(as_mat(c,0xffff,alpha,GPU_RASTER_TEXTURE|flags,tr+(tr==255),tg+(tg==255),tb+(tb==255)));
 float dudx=flip*cs*tw/width,dudy=flip*sn*tw/width,dvdx=-sn*th/height,dvdy=cs*th/height;
 gpu_raster_plane pu={(int64_t)((tw*.5f-dudx*(x-.5f)-dudy*(y-.5f))*65536.f),af_round(dudx*65536.f),af_round(dudy*65536.f)};
 gpu_raster_plane pv={(int64_t)((th*.5f-dvdx*(x-.5f)-dvdy*(y-.5f))*65536.f),af_round(dvdx*65536.f),af_round(dvdy*65536.f)};
 TRY(gpu_v1_plane(c,0,&pu));TRY(gpu_v1_plane(c,1,&pv));
 static const uint8_t occupied[5][6]=ASTRILLA_SHIP_CELLS;
 int cw=kind>=0?32:tw,ch=kind>=0?32:th;
 for(int row=0;row<th;row+=ch)for(int col=0;col<tw;col+=cw){
  if(kind>=0&&!(occupied[kind&7][row/32]&(1U<<(col/32))))continue;
  int vx[4],vy[4];for(int i=0;i<4;++i){float u=(float)(col+((i==1||i==2)?cw:0))-tw*.5f,v=(float)(row+(i>=2?ch:0))-th*.5f;
   vx[i]=af_round(x+u*ax+v*bx);vy[i]=af_round(y+u*ay+v*by);}
  as_rawtri(c,vx[0],vy[0],vx[1],vy[1],vx[2],vy[2]);as_rawtri(c,vx[0],vy[0],vx[2],vy[2],vx[3],vy[3]);
 }return 1;
}
#define AS_WHITE 0xffffffU
static int as_glow(gpu_v1_context *c,float x,float y,float size,unsigned tint,unsigned alpha){return as_image(c,ASTRILLA_GLOW,64,64,x,y,size,size,0,alpha,GPU_V1_ADDITIVE,tint,-1);}
// Each view is a separate camera view of the same craft. Mirroring selects
// left/right travel; the small residual rotation follows the path tangent.
static int as_craft(gpu_v1_context *c,float x,float y,float size,float heading,unsigned view,unsigned mirror,unsigned tint,float throttle,unsigned t){
 static const uint32_t textures[5]={ASTRILLA_CORVETTE,ASTRILLA_CARRIER,ASTRILLA_CORVETTE_FRONT,ASTRILLA_CORVETTE_SIDE,ASTRILLA_CORVETTE_LANDED};
 static const float bearing[5]={-24.f,96.f,24.f,0.f,24.f};
 float angle=as_turn(heading-(mirror?128.f-bearing[view]:bearing[view]));
 TRY(as_image(c,textures[view],256,192,x,y,size,size*.75f,angle,256,0,tint,(int)view|(mirror?8:0)));
 if(throttle>.01f&&view!=4&&size>40.f){float ex=x-af_cos(heading)*size*.30f,ey=y-af_sin(heading)*size*.30f;
  TRY(as_glow(c,ex,ey,size*.14f,0x50bfff,(unsigned)(throttle*(150.f+15.f*af_sin((float)t*2.f)))));}
 return 1;
}
static int as_flyby(gpu_v1_context *c,unsigned t,unsigned variant,float u){
 static const float path[4][10]={{-90,215,70,185,210,70,460,10,108,38},{-100,78,80,70,230,120,520,175,54,108},
  {500,205,310,185,200,70,-95,55,92,64},{-110,162,100,142,270,152,510,127,98,98}};
 unsigned v=variant%4;const float *p=path[v];as_motion m=as_curve(u,p[0],p[1],p[2],p[3],p[4],p[5],p[6],p[7]);
 return as_craft(c,m.x,m.y,p[8]+(p[9]-p[8])*u,as_heading(m.dx,m.dy),v==1?2:v==3?3:0,v==2,AS_WHITE,.9f,t);
}
// Q16 UV and light at vertices: retaining the fractional spin avoids the
// former one-texel jump every ~18 frames. The hardware evaluates these planes.
static int as_planet_triangle(gpu_v1_context *c,const gpu_vertex v[3]){
 int64_t area=(int64_t)(v[1].x-v[0].x)*(v[2].y-v[0].y)-(int64_t)(v[1].y-v[0].y)*(v[2].x-v[0].x);
 if(!area)return 1;
 for(unsigned k=0;k<3;++k){int64_t f[3];for(unsigned i=0;i<3;++i)f[i]=k==0?v[i].u:k==1?v[i].v:v[i].r;
  int64_t dx=((f[1]-f[0])*(v[2].y-v[0].y)-(f[2]-f[0])*(v[1].y-v[0].y))/area;
  int64_t dy=((int64_t)(v[1].x-v[0].x)*(f[2]-f[0])-(int64_t)(v[2].x-v[0].x)*(f[1]-f[0]))/area;
  if(dx<INT32_MIN||dx>INT32_MAX||dy<INT32_MIN||dy>INT32_MAX)return 0;
  gpu_raster_plane p={f[0]-dx*v[0].x-dy*v[0].y+(dx+dy)/2,(int32_t)dx,(int32_t)dy};
  if(k<2){TRY(gpu_v1_plane(c,k,&p));}else for(unsigned j=4;j<7;++j)TRY(gpu_v1_plane(c,j,&p));
 }
 as_rawtri(c,v[0].x,v[0].y,v[1].x,v[1].y,v[2].x,v[2].y);return 1;
}
static int as_planet(gpu_v1_context *c,float x,float y,float radius,unsigned texture,float spin){
 gpu_texture_level tex={texture,256,128,512,GPU_RGB565,GPU_TEX_REPEAT,GPU_TEX_CLAMP,0};TRY(gpu_v1_texture(c,&tex));TRY(as_mat(c,0xffff,256,GPU_RASTER_TEXTURE|GPU_V1_GOURAUD,256,256,256));
 int rows=radius>55?8:6,cols=radius>55?12:10;
 for(int j=0;j<rows;++j)for(int i=0;i<cols;++i){gpu_vertex v[4];for(int n=0;n<4;++n){int a=i+(n==1||n==2),b=j+(n>=2);
  float lat=-64.f+(float)b*128.f/rows,lon=-64.f+(float)a*128.f/cols,nx=af_cos(lat)*af_sin(lon),ny=af_sin(lat),nz=af_cos(lat)*af_cos(lon);
  int light=af_round(af_clamp(55.f-95.f*nx-76.f*ny+147.f*nz,12,256)*65536.f);
  v[n]=(gpu_vertex){af_round(x+nx*radius),af_round(y+ny*radius),af_round((spin+(float)a*128.f/cols)*65536.f),af_round((float)b*127.f*65536.f/rows),50000,65536,light,light,light};
 }gpu_vertex second[3]={v[0],v[2],v[3]};TRY(as_planet_triangle(c,v));TRY(as_planet_triangle(c,second));}return 1;
}
static int as_stars(gpu_v1_context *c,unsigned t,unsigned k){
 float sec=(float)t/55.f,speed=k==3?680.f:k==4?230.f:140.f;
 for(unsigned i=0;i<90;++i){unsigned h=as_hash(i+1881);float z=(float)(h%2200)-sec*speed;z-=((float)(int)(z/2200.f)-1.f)*2200.f;if(z>2200)z-=2200;z+=90;
  float xx=(float)((int)((h>>12)%2000)-1000),yy=(float)((int)((h>>21)%1100)-550),x=200.f+xx*180.f/z,y=120.f+yy*180.f/z;
  if(x<0||x>=400||y<0||y>=240)continue;
  float stretch=k==3?af_clamp(90.f/z,.015f,.35f):.005f;
  TRY(as_beam(c,x,y,x+(x-200.f)*stretch+.5f,y+(y-120.f)*stretch+.5f,k==3?.7f:.45f,0xb6df,140));
 }return 1;
}
static int as_asteroids(gpu_v1_context *c,unsigned t,float strength){
 float sec=(float)t/55.f;
 for(unsigned i=0;i<12;++i){unsigned h=as_hash(i+573);float phase=sec*.27f+(float)(h&255)/256.f;phase-=(float)(int)phase;
  float z=1480.f-phase*1400.f,x=200.f+((float)((int)((h>>8)%1000)-500))*180.f/z,y=120.f+(float)((int)((h>>18)%500)-250)*180.f/z,r=(7.f+(float)(i%4)*4.f)*180.f/z*strength;
  if(x+r<0||x-r>400||y+r<0||y-r>240)continue;
  gpu_vertex v[5];for(int j=0;j<5;++j){float a=(float)j*51.2f+sec*17.f+(float)i*11.f;
   v[j]=(gpu_vertex){af_round(x+af_cos(a)*r),af_round(y+af_sin(a)*r),0,0,(int)(12000+z*10),65536,80+j*32,80+j*32,80+j*32};}
  TRY(as_mat(c,0x9c93,256,GPU_Z_TEST|GPU_Z_WRITE|GPU_V1_GOURAUD,256,256,256));
  for(int j=1;j<4;++j){gpu_vertex tri[3]={v[0],v[j],v[j+1]};TRY(gpu_v1_triangle(c,tri));}
 }return 1;
}
static int as_ringfx(gpu_v1_context *c,float x,float y,float rx,float ry,float tilt,float width,unsigned color,unsigned alpha,int half){
 TRY(as_mat(c,color,alpha,GPU_V1_ADDITIVE,256,256,256));
 int begin=half==2?12:0,end=half==1?12:24;
 float sn=af_sin(tilt),cs=af_cos(tilt);
 for(int i=begin;i<end;++i){int px[4],py[4];for(int n=0;n<4;++n){float a=(float)(i+(n==1||n==2))*256.f/24.f,w=n<2?-width:width;
   float xx=af_cos(a)*(rx+w),yy=af_sin(a)*(ry+w);px[n]=af_round(x+xx*cs-yy*sn);py[n]=af_round(y+xx*sn+yy*cs);}
  as_rawtri(c,px[0],py[0],px[1],py[1],px[2],py[2]);as_rawtri(c,px[0],py[0],px[2],py[2],px[3],py[3]);
 }return 1;
}
static int as_battle(gpu_v1_context *c,unsigned t){
 float sec=(float)(t-as_keys[4])/55.f;as_motion capital=as_flagship(sec);
 for(unsigned i=0;i<7;++i){float period=5.7f+(float)(i%3)*.8f,p=sec/period+(float)i/7.f;p-=(float)(int)p;
  unsigned left=i&1,view=i%3==0?0:i%3==1?2:3;float x0=left?490.f:-90.f,x3=left?-90.f:490.f;
  float y0=55.f+(float)(i%4)*33.f,dy=view==0?-48.f:view==2?48.f:6.f;
  as_motion m=as_curve(p,x0,y0,x0+(x3-x0)*.30f,y0+dy*.10f,x0+(x3-x0)*.72f,y0+dy*.85f,x3,y0+dy);
  float heading=as_heading(m.dx,m.dy),size=23.f+22.f*p;
  // A mirrored rear view ascends; a mirrored front view descends too.
  TRY(as_craft(c,m.x,m.y,size,heading,view,left,left?0xffb899:AS_WHITE,.8f,t));
  unsigned fire=(t+i*13)%57;if(fire<21){float x=m.x+af_cos(heading)*(size*.4f+(float)fire*7.f),y=m.y+af_sin(heading)*(size*.4f+(float)fire*7.f);
   TRY(as_beam(c,x,y,x+af_cos(heading)*21.f,y+af_sin(heading)*21.f,.65f,left?0xfb87:0x5fff,210));}
 }
 // The capital and impacts are native layers. Plasma/shockwave geometry still
 // goes through the GPU, while the craft pass in coherent firing directions.
 for(int i=0;i<3;++i){float f=sec*.8f+i*.33f;f-=(float)(int)f;
  if(f<.3f)TRY(as_ringfx(c,capital.x+(i-1)*24.f,capital.y+(i-1)*14.f,8.f+f*90.f,5.f+f*55.f,0,1.f,0xffd7,(unsigned)(150.f*(1.f-f/.3f)),0));}
 float p=sec/7.f;p-=(float)(int)p;as_motion hero=as_curve(p,-100,226,80,220,310,173,510,154);
 TRY(as_craft(c,hero.x,hero.y,96.f-28.f*p,as_heading(hero.dx,hero.dy),3,0,AS_WHITE,1.f,t));return 1;
}
static int as_dimensions(gpu_v1_context *c,unsigned t){
 float sec=(float)t/55.f;float x[16],y[16];
 for(int i=0;i<16;++i){float a=i&1?55.f:-55.f,b=i&2?55.f:-55.f,z=i&4?55.f:-55.f,w=i&8?55.f:-55.f;
  float xx=a*af_cos(sec*16.f)-w*af_sin(sec*16.f),ww=a*af_sin(sec*16.f)+w*af_cos(sec*16.f),yy=b*af_cos(sec*11.f)-z*af_sin(sec*11.f),zz=b*af_sin(sec*11.f)+z*af_cos(sec*11.f);
  float d=(200.f-ww)*(260.f+zz)/220.f;x[i]=200.f+xx*230.f/d;y[i]=120.f+yy*230.f/d;}
 for(int i=0;i<16;++i)for(int d=0;d<4;++d)if(!(i&(1<<d))){int j=i|(1<<d);TRY(as_beam(c,x[i],y[i],x[j],y[j],1.1f,d==3?0xfc9f:0x7fff,180));}
 for(int i=0;i<4;++i){float a=sec*23.f+(float)i*64.f;TRY(as_glow(c,200.f+af_cos(a)*150.f,120.f+af_sin(a)*85.f,22.f, i&1?0xff55cc:0x55ccff,180));}
 // Three lit crystalline octahedra use actual depth-tested geometry and fog.
 static const int8_t points[6][3]={{1,0,0},{-1,0,0},{0,1,0},{0,-1,0},{0,0,1},{0,0,-1}};
 static const uint8_t faces[8][3]={{4,0,2},{4,2,1},{4,1,3},{4,3,0},{5,2,0},{5,1,2},{5,3,1},{5,0,3}};
 for(int n=0;n<3;++n){float a=sec*19.f+n*85.f,cx=200.f+af_cos(a)*132.f,cy=120.f+af_sin(a)*72.f,sz=15.f+4.f*af_sin(a);
  float sn=af_sin(sec*29.f+n*23.f),cs=af_cos(sec*29.f+n*23.f),st=af_sin(sec*17.f),ct=af_cos(sec*17.f);gpu_vertex v[6];
  for(int j=0;j<6;++j){float x=points[j][0]*sz,y=points[j][1]*sz,z=points[j][2]*sz,xx=x*cs-z*sn,zz=x*sn+z*cs,yy=y*ct-zz*st;zz=y*st+zz*ct;
   int light=af_round(af_clamp(190.f+zz*4.f,40,256));v[j]=(gpu_vertex){af_round(cx+xx),af_round(cy+yy),0,0,af_round(24000.f+zz*32.f),65536,light,light,light};}
  gpu_material mat={GPU_Z_TEST|GPU_Z_WRITE|GPU_V1_GOURAUD|GPU_V1_FOG,256,n==0?0x3eff:n==1?0xcaff:0xff2a,256,256,256,18000,0x0005,655};TRY(gpu_v1_material(c,&mat));
  for(int j=0;j<8;++j){gpu_vertex q[3]={v[faces[j][0]],v[faces[j][1]],v[faces[j][2]]};TRY(gpu_v1_triangle(c,q));}
 }

 return 1;
}
// A forward passage through changing polygonal cross-sections. The scenery
// stays level: moving geometry, parallax and light convey the folded space.
static int as_passage(gpu_v1_context *c,unsigned t,unsigned style){
 float sec=(float)t/55.f;unsigned sides=style%3==0?4:style%3==1?6:8;
 for(unsigned i=0;i<7;++i){float p=sec*.32f+(float)i/7.f;p-=(float)(int)p;
  float r=12.f+p*p*p*340.f,turn=(float)i*7.f+sec*(style%3==1?-9.f:7.f);
  unsigned color=i&1?0xfabf:0x67ff,alpha=(unsigned)(50.f+p*140.f);
  for(unsigned j=0;j<sides;++j){float a=(float)j*256.f/sides+turn,b=(float)(j+1)*256.f/sides+turn;
   TRY(as_beam(c,200.f+af_cos(a)*r,120.f+af_sin(a)*r*.64f,
    200.f+af_cos(b)*r,120.f+af_sin(b)*r*.64f,.55f+p*.65f,color,alpha));}
 }
 for(int i=0;i<4;++i){float a=sec*24.f+(float)i*64.f;
  TRY(as_glow(c,200.f+af_cos(a)*128.f,120.f+af_sin(a)*77.f,15.f,i&1?0xff77ee:0x55ddff,150));}
 return 1;
}
static int as_infall(gpu_v1_context *c,unsigned t){
 float local=(float)(t-as_keys[2])/55.f;as_camera cam=as_view(t);float radius=cam.lens/16.f;
 if(local<8.f){float q=local/8.f;q=q*q;
  TRY(as_craft(c,45.f+155.f*q,211.f-91.f*q,85.f*(1.f-q)+3.f,as_heading(155,-91),0,0,AS_WHITE,1.f,t));}
 // Orbiting hot spots belong to the disk, never to the camera transform.
 for(int i=0;i<3;++i){float a=local*31.f+(float)i*85.f;
  float x=200.f+af_cos(a)*radius*1.85f,y=120.f+af_cos(a)*radius*.46f+af_sin(a)*radius*.30f;
  if((x-200.f)*(x-200.f)+(y-120.f)*(y-120.f)<radius*radius*.78f)continue;
  TRY(as_glow(c,x,y,14.f+radius*.06f,i&1?0x77bbff:0xffbd77,180));}
 return 1;
}
static int as_opening(gpu_v1_context *c,unsigned t,unsigned k,const as_camera *cam){
 float e=cam->travel,sec=(float)t/55.f,px=380.f-450.f*e,py=100.f+12.f*e;
 unsigned shot=(unsigned)cam->shot,mode=(shot+(k==5?4:0))%9;
 if(mode==0){float r=43.f+16.f*e;
  TRY(as_ringfx(c,px,py,r*1.5f,r*.24f,-8.f,1.8f,0xbccd,160,1));
  TRY(as_planet(c,px,py,r,ASTRILLA_GAS,sec*3.f));
  TRY(as_ringfx(c,px,py,r*1.5f,r*.24f,-8.f,1.8f,0xffd3,190,2));
 }else if(mode==1){
  TRY(as_planet(c,88.f-35.f*e,48.f,18.f,ASTRILLA_PLANET,sec*2.f));
  TRY(as_planet(c,px+20.f,132.f,64.f,ASTRILLA_MOON,sec*5.f));
 }else if(mode==2){float x=320.f-260.f*e;
  TRY(as_ringfx(c,x,120.f,75.f,31.f,28.f,1.3f,0xfbc7,170,0));
  TRY(as_ringfx(c,x,120.f,68.f,26.f,-28.f,1.3f,0xfea4,140,0));
  TRY(as_planet(c,x,120.f,50.f,ASTRILLA_SUN,sec*7.f));
  TRY(as_glow(c,x+38.f,94.f,32.f,0xffbf66,220));
 }else if(mode==3){
  TRY(as_planet(c,315.f-45.f*e,51.f,26.f,ASTRILLA_MOON,sec*4.f));
  TRY(as_asteroids(c,t,1.9f));
 }else if(mode==4){
  TRY(as_planet(c,px+68.f,55.f,17.f,ASTRILLA_MOON,sec*5.f));
  TRY(as_planet(c,px,129.f,56.f,ASTRILLA_PLANET,sec*4.f));
 }else if(mode==5){
  float u=e+.3f;if(u>1.f)u-=1.f;TRY(as_flyby(c,t,shot+1,u));
  u=e+.6f;if(u>1.f)u-=1.f;TRY(as_flyby(c,t,shot+2,u));
 }else if(mode==6){
  TRY(as_glow(c,205.f,108.f,78.f,0xffdc99,165));
  TRY(as_planet(c,205.f,108.f,32.f,ASTRILLA_SUN,sec*5.f));
  TRY(as_planet(c,145.f+125.f*e,110.f,31.f,ASTRILLA_MOON,sec*2.f));
 }else if(mode==7){float r=44.f;
  TRY(as_ringfx(c,px,py,r*1.9f,r*.4f,18.f,1.3f,0x5eff,155,1));
  TRY(as_planet(c,px,py,r,ASTRILLA_MOON,sec*4.f));
  TRY(as_ringfx(c,px,py,r*1.9f,r*.4f,18.f,1.3f,0xbfff,170,2));
 }else{
  TRY(as_planet(c,90.f+45.f*e,145.f,32.f,ASTRILLA_PLANET,sec*3.f));
  TRY(as_planet(c,310.f-105.f*e,72.f,24.f,ASTRILLA_MOON,sec*6.f));
 }
 TRY(as_flyby(c,t,shot+(k==5?2:0),e));
 if(mode==0||mode==1||mode==4||mode==8)TRY(as_asteroids(c,t,1.f));
 return 1;
}
static int astrilla_render(gpu_v1_context *c,unsigned t,unsigned page){
 if(t>=ASTRILLA_FRAMES||page>1)return 0;
 unsigned k=as_chapter(t);as_camera cam=as_view(t);float s=(float)t/55.f,local=(float)(t-as_keys[k])/55.f,e=cam.travel;
 gpu_target dst={GPU_PAGE_ADDR(page),GPU_PAGE_ADDR(2),400,240,800,800},bg={AS_CACHE_BASE+as_plate(t)*192000UL,0,400,240,800,800};
 TRY(gpu_v1_target(c,&dst));TRY(gpu_v1_scissor(c,0,0,400,240));TRY(gpu_v1_clear(c,2,0,65535,0,0,400,240));TRY(gpu_v1_copy(c,&bg,0,0,0,0,400,240));
 if(k<8&&k!=2)TRY(as_stars(c,t,k));
 if(k==0||k==5){TRY(as_opening(c,t,k,&cam));
 }else if(k==1){TRY(as_flyby(c,t,(unsigned)cam.shot+1,e));TRY(as_asteroids(c,t,1.4f));
  if((unsigned)cam.shot%3==1)TRY(as_planet(c,360.f-480.f*e,190.f,45.f,ASTRILLA_MOON,s*4.f));
 }else if(k==2){if(local<12.f){TRY(as_infall(c,t));}
  else{unsigned style=(unsigned)((local-12.f)/6.f);TRY(as_stars(c,t,3));
   if(style!=1)TRY(as_dimensions(c,t));
   if(style!=0)TRY(as_passage(c,t,style));}
 }else if(k==3){TRY(as_passage(c,t,(unsigned)(local/6.f)));
 }else if(k==4){TRY(as_battle(c,t));
 }else if(k==6){if((unsigned)(local/7.f)%3!=1)TRY(as_dimensions(c,t));
  if((unsigned)(local/7.f)%3!=0)TRY(as_passage(c,t,(unsigned)(local/7.f)));
 }else if(k==7){float q=local/35.f;TRY(as_planet(c,250.f-q*80.f,120.f+q*75.f,30.f+q*68.f,ASTRILLA_PLANET,s*3.f));
  if(local<28)TRY(as_craft(c,-20.f+local*10.f,180.f-local*2.86f,90.f-local*2.57f,as_heading(10,-2.86f),0,0,AS_WHITE,.8f,t));
 }else if(k>=8){as_landing_pose pose=as_landing(t);float alt=pose.altitude,x=pose.gx,y=pose.gy,scale=pose.scale;
  TRY(as_image(c,ASTRILLA_SHADOW,64,32,x,y,37.f*scale,10.f*scale,0,(unsigned)(240.f-alt),0,AS_WHITE,-1));
  TRY(as_craft(c,pose.x,pose.y,pose.size,24.f,alt<.5f?4:2,0,AS_WHITE,af_clamp(alt/25.f,0,1),t));
  if(k==8&&local>=18.f&&local<20.f){float age=(local-18.f)/2.f;TRY(as_ringfx(c,x,y,(12.f+age*32.f)*scale,(3.f+age*8.f)*scale,0,1,0xa4eb,(unsigned)(100.f*(1.f-age)),0));}
  for(int i=0;i<12;++i){float gx,gy,z;as_ground(&cam,280.f+(float)i*26.f,327.f+(float)((i*19)%35),&gx,&gy,&z);
   TRY(as_glow(c,gx,gy,(3.f+(float)(i%3))*z,i&1?0xe66bff:0x55ffaa,85));}
 }return 1;
}
static void astrilla_layers(unsigned t,gpu_layer layers[16],gpu_sprite sprites[64],astrilla_info *info){
 memset(layers,0,sizeof(*layers)*16);memset(sprites,0,sizeof(*sprites)*64);unsigned k=as_chapter(t);int local=(int)(t-as_keys[k]);
 if(k==4){
  float sec=(float)local/55.f;as_motion capital=as_flagship(sec);int x=af_round(capital.x*2.f),y=af_round(capital.y*2.f);
  layers[7]=gpu_make_layer(ASTRILLA_FLAGSHIP,352,352,288,x-176,y-144,352,288,0,0,3);
  for(int i=0;i<3;++i){float f=sec*.8f+i*.33f;f-=(float)(int)f;if(f<.72f){unsigned pose=(unsigned)(f*10.f);
   layers[8+i]=gpu_make_layer(ASTRILLA_FIRE_NATIVE+pose*16384U,128,128,128,x+(i-1)*48-64,y+(i-1)*28-64,128,128,0,0,3);}}
 }
 // Discreet chapter card, only at entry; the rest of the screen stays cinematic.
 if(local<140&&k){unsigned hud=ASTRILLA_HUD0+k*64000U;layers[11]=gpu_make_layer(hud,800,800,80,0,0,800,36,0,0,3);}
 if(t<250||t>=16000)layers[13]=gpu_make_layer(t<250?ASTRILLA_TITLE:ASTRILLA_FINISH,640,640,128,80,t<250?285:70,640,128,0,0,3);
 unsigned count=0;
 if(k==4)for(unsigned i=0;i<20;++i){unsigned h=as_hash(i+478);float sec=(float)local/55.f,p=sec*1.5f+(float)i/20.f;p-=(float)(int)p;
  float a=(float)(h&255),r=20.f+p*65.f;as_motion capital=as_flagship(sec);int x=af_round(capital.x*2.f+af_cos(a)*r),y=af_round(capital.y*2.f+af_sin(a)*r*.7f);
  if(p<.8f)sprites[count++]=gpu_make_sprite(ASTRILLA_PARTICLES+2*1024,x-16,y-16,32,32,12,GPU_SPRITE_ENABLE);
 }
 if(k>=8){as_camera cam=as_view(t);for(unsigned i=0;i<48;++i){unsigned h=as_hash(i+817);float sec=(float)t/55.f,x,y,scale;
  as_ground(&cam,250.f+(float)(h%380)+4.f*af_sin(sec*4.f+i*13.f),280.f+(float)((h/380)%100),&x,&y,&scale);
  sprites[count++]=gpu_make_sprite(ASTRILLA_PARTICLES+(i&1?3:4)*1024,af_round(x*2.f)-16,af_round(y*2.f)-16,32,32,8,GPU_SPRITE_ENABLE);}}
 // Six-frame iris at shot changes masks deliberate edits, not animation quantization.
 int within=local%220,remain=220-within,gate=0;if(k<2||k==5){if(within<5)gate=(5-within)*240/5;if(remain<5)gate=(5-remain)*240/5;}
 if(k==2&&local>=660&&local<668)gate=(668-local)*240/8;
 int end=(int)(as_keys[k+1]-t);if(local<8&&k!=9)gate=(8-local)*240/8;if(end<8&&k!=8)gate=(8-end)*240/8;
 if(gate){layers[14]=gpu_make_layer(ASTRILLA_BLACK,800,800,480,0,0,800,(unsigned)gate,0,0,1);layers[15]=gpu_make_layer(ASTRILLA_BLACK,800,800,480,0,480-gate,800,(unsigned)gate,0,0,1);}
 *info=(astrilla_info){t,k,count,k==4?7U:0U};
}
#undef TRY
#endif
