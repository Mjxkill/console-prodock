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
#define AS_CACHE_FRAMES 1705U
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
typedef struct {uint32_t base;int width,height;int32_t u,v,ux,vx,uy,vy;float seconds,roll,travel,shot;} as_camera;
// Camera plates are filtered at boot, then copied by the GPU. Only the
// background is cached; all foreground geometry/effects are rendered live.
static unsigned as_plate(unsigned t){
 unsigned k=as_chapter(t),local=t-as_keys[k];
 if(k==2)return local<1430?770+local%220:990+local-1430;
 if(k==3||k==6)return 1210+local%220;
 if(k>=8)return 1430+local%275;
 return local%770;
}
static unsigned as_plate_time(unsigned i){
 if(i<770)return i;
 if(i<990)return 3850+i-770;
 if(i<1210)return 5280+i-990;
 if(i<1430)return 5500+i-1210;
 return 14300+i-1430;
}
static as_camera as_view(unsigned t){
 unsigned k=as_chapter(t),plate=as_plate(t);float seconds=(float)t/55.f;
 float shot=(float)(t-as_keys[k])/385.f,u=(float)((t-as_keys[k])%385)/385.f,e=af_ease(u),cx=512.f,cy=176.f,zoom=1.f,roll=0;
 unsigned variant=plate/385;uint32_t base=ASTRILLA_COSMOS;int width=1024,height=352;
 if(k==2){base=ASTRILLA_BLACKHOLE;height=512;cy=236.f;
  if(plate<990){float a=(float)(plate-770)*256.f/220.f;cx=605.f+35.f*af_sin(a);zoom=1.08f+.12f*af_cos(a);roll=.08f*af_sin(a);}
  else{float q=(float)(plate-990)/219.f;cx=605.f;zoom=.96f-.88f*af_ease(q);roll=0;}
 }else if(k==3||k==6){base=ASTRILLA_WORMHOLE;height=512;float a=(float)(plate-1210)*256.f/220.f;
  cx=512.f+14.f*af_sin(a);cy=256.f+10.f*af_cos(a);zoom=.84f+.10f*af_sin(a*2);roll=a*.024543693f;
 }else if(k>=8){base=ASTRILLA_VALLEY;width=800;height=400;float a=(float)(plate-1430)*256.f/275.f;
  cx=410.f+60.f*af_sin(a);cy=240.f+20.f*af_cos(a);zoom=.80f+.06f*af_sin(a);roll=.04f*af_sin(a);
 }else{
  float a=(float)(plate%385)/385.f;float q=af_ease(a);cx=variant?740.f-480.f*q:260.f+480.f*q;
  cy=176.f+12.f*af_sin(a*256.f);zoom=.85f+.12f*af_sin(a*128.f);roll=(variant?-1.f:1.f)*.10f*af_sin(a*128.f);
 }
 float sn=af_sin(roll*40.743665f),cs=af_cos(roll*40.743665f),ux=zoom*cs,vx=zoom*sn,uy=-zoom*sn,vy=zoom*cs;
 return (as_camera){base,width,height,af_round((cx-200.f*ux-120.f*uy)*65536.f),af_round((cy-200.f*vx-120.f*vy)*65536.f),
  af_round(ux*65536.f),af_round(vx*65536.f),af_round(uy*65536.f),af_round(vy*65536.f),seconds,roll,e,shot};
}
// Four-bit bilinear weights (1/16 texel). Camera coordinates remain Q16 until
// sampling. The texture never stays still for 20 frames then jumps two LCD pixels.
static inline __attribute__((always_inline)) unsigned as_mix(unsigned a,unsigned b,unsigned f){
 unsigned x=((a<<16)|a)&0x07e0f81fU,y=((b<<16)|b)&0x07e0f81fU;
 unsigned q=(x+(((y-x)*f)>>4))&0x07e0f81fU;return (q|(q>>16))&65535;
}
static __attribute__((optimize("O3"))) void astrilla_background(unsigned t,uint16_t *out,const uint8_t *assets){
 as_camera c=as_view(t);const uint16_t *source=(const uint16_t *)(assets+c.base-ASTRILLA_BASE);
 for(int y=0;y<240;++y){int32_t u=c.u+c.uy*y,v=c.v+c.vy*y;
  for(int x=0;x<400;++x,u+=c.ux,v+=c.vx){int ix=u>>16,iy=v>>16;unsigned fu=((unsigned)u>>12)&15,fv=((unsigned)v>>12)&15;
   if(ix<0){ix=0;fu=0;}if(ix>=c.width-1){ix=c.width-2;fu=15;}
   if(iy<0){iy=0;fv=0;}if(iy>=c.height-1){iy=c.height-2;fv=15;}
   const uint16_t *s=source+iy*c.width+ix;
   out[y*400+x]=(uint16_t)as_mix(as_mix(s[0],s[1],fu),as_mix(s[c.width],s[c.width+1],fu),fv);
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
 float sn=af_sin(angle),cs=af_cos(angle),ax=cs*width/(float)tw,ay=sn*width/(float)tw,bx=-sn*height/(float)th,by=cs*height/(float)th;
 gpu_texture_level tex={base,(uint16_t)tw,(uint16_t)th,(uint16_t)(tw*2),GPU_ARGB4444,GPU_TEX_CLAMP,GPU_TEX_CLAMP,0};
 TRY(gpu_v1_texture(c,&tex));unsigned tr=(tint>>16)&255,tg=(tint>>8)&255,tb=tint&255;
 TRY(as_mat(c,0xffff,alpha,GPU_RASTER_TEXTURE|flags,tr+(tr==255),tg+(tg==255),tb+(tb==255)));
 float dudx=cs*tw/width,dudy=sn*tw/width,dvdx=-sn*th/height,dvdy=cs*th/height;
 gpu_raster_plane pu={(int64_t)((tw*.5f-dudx*(x-.5f)-dudy*(y-.5f))*65536.f),af_round(dudx*65536.f),af_round(dudy*65536.f)};
 gpu_raster_plane pv={(int64_t)((th*.5f-dvdx*(x-.5f)-dvdy*(y-.5f))*65536.f),af_round(dvdx*65536.f),af_round(dvdy*65536.f)};
 TRY(gpu_v1_plane(c,0,&pu));TRY(gpu_v1_plane(c,1,&pv));
 static const uint8_t occupied[2][6]=ASTRILLA_SHIP_CELLS;
 int cw=kind>=0?32:tw,ch=kind>=0?32:th;
 for(int row=0;row<th;row+=ch)for(int col=0;col<tw;col+=cw){
  if(kind>=0&&!(occupied[kind][row/32]&(1U<<(col/32))))continue;
  int vx[4],vy[4];for(int i=0;i<4;++i){float u=(float)(col+((i==1||i==2)?cw:0))-tw*.5f,v=(float)(row+(i>=2?ch:0))-th*.5f;
   vx[i]=af_round(x+u*ax+v*bx);vy[i]=af_round(y+u*ay+v*by);}
  as_rawtri(c,vx[0],vy[0],vx[1],vy[1],vx[2],vy[2]);as_rawtri(c,vx[0],vy[0],vx[2],vy[2],vx[3],vy[3]);
 }return 1;
}
#define AS_WHITE 0xffffffU
static int as_glow(gpu_v1_context *c,float x,float y,float size,unsigned tint,unsigned alpha){return as_image(c,ASTRILLA_GLOW,64,64,x,y,size,size,0,alpha,GPU_V1_ADDITIVE,tint,-1);}
static int as_ship(gpu_v1_context *c,float x,float y,float size,float angle,int enemy,unsigned t){
 TRY(as_image(c,enemy?ASTRILLA_CARRIER:ASTRILLA_CORVETTE,256,192,x,y,size,size*.75f,angle,256,0,AS_WHITE,enemy));
 if(!enemy&&size>40){float cs=af_cos(angle),sn=af_sin(angle),ex=-size*.25f,ey=size*.12f;
  TRY(as_glow(c,x+ex*cs-ey*sn,y+ex*sn+ey*cs,size*.21f,0x50bfff,150+(t%11)*4));}
 return 1;
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
  float z=80.f+phase*1400.f,x=200.f+((float)((int)((h>>8)%1000)-500))*180.f/z,y=120.f+(float)((int)((h>>18)%500)-250)*180.f/z,r=(7.f+(float)(i%4)*4.f)*180.f/z*strength;
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
 float sec=(float)(t-as_keys[4])/55.f;
 // The flagship is drawn by native layer 7, freeing the rasterizer for combat.
 for(unsigned i=0;i<7;++i){float p=sec*.28f+(float)i/7.f;p-=(float)(int)p;float x=-70.f+p*540.f,y=72.f+98.f*af_sin(sec*14.f+(float)i*37.f);
  TRY(as_ship(c,x,y,23.f+25.f*p,(float)i*15.f+af_sin(sec*15.f+i*9.f)*18.f,i&1,t));
  if((t+i*11)%49<27)TRY(as_beam(c,x,y,240.f+af_cos(sec*8.f)*60.f,70.f,1.f,i&1?0xfb87:0x5fff,185));}
 for(int i=0;i<3;++i){float f=sec*1.35f+i*.33f;int serial=(int)f;f-=serial;float x=80.f+(float)(as_hash((unsigned)serial+i*91)%260),y=52.f+(float)(as_hash((unsigned)serial+i*17)%110);
  if(f<.74f){unsigned pose=(unsigned)(f*10.f);float size=18.f+48.f*f;
   TRY(as_image(c,ASTRILLA_FIRE0+pose*32768U,128,128,x,y,size,size,0,200,GPU_V1_ADDITIVE,AS_WHITE,-1));
   if(f<.3f)TRY(as_ringfx(c,x,y,12.f+f*130.f,8.f+f*80.f,0,1.2f,0xffd7,(unsigned)(200.f*(1.f-f/.3f)),0));}}
 TRY(as_ship(c,105.f+af_sin(sec*9.f)*65.f,182.f+af_cos(sec*17.f)*20.f,96.f,-7.f+af_sin(sec*11.f)*13.f,0,t));return 1;
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
static int astrilla_render(gpu_v1_context *c,unsigned t,unsigned page){
 if(t>=ASTRILLA_FRAMES||page>1)return 0;
 unsigned k=as_chapter(t);as_camera cam=as_view(t);float s=(float)t/55.f,local=(float)(t-as_keys[k])/55.f,e=cam.travel;
 gpu_target dst={GPU_PAGE_ADDR(page),GPU_PAGE_ADDR(2),400,240,800,800},bg={AS_CACHE_BASE+as_plate(t)*192000UL,0,400,240,800,800};
 TRY(gpu_v1_target(c,&dst));TRY(gpu_v1_scissor(c,0,0,400,240));TRY(gpu_v1_clear(c,2,0,65535,0,0,400,240));TRY(gpu_v1_copy(c,&bg,0,0,0,0,400,240));
 if(k<8&&k!=2)TRY(as_stars(c,t,k));
 if(k==0||k==5){float px=(unsigned)cam.shot&1?80.f+100.f*e:300.f-200.f*e;
  float py=90.f+30.f*af_sin(local*7.f),radius=48.f+14.f*af_sin(local*5.f);
  if(k==0)TRY(as_ringfx(c,px,py,radius*1.5f,radius*.24f,-8.f,1.8f,0xbccd,160,1));
  TRY(as_planet(c,px,py,radius,k==5?ASTRILLA_PLANET:ASTRILLA_GAS,s*3.f));
  if(k==0)TRY(as_ringfx(c,px,py,radius*1.5f,radius*.24f,-8.f,1.8f,0xffd3,190,2));
  TRY(as_glow(c,325.f-70.f*e,44.f,36.f,0xffcc77,210));
  TRY(as_ship(c,70.f+250.f*e,162.f+25.f*af_sin(local*13.f),95.f+35.f*af_sin(local*9.f),-7.f+12.f*af_sin(local*12.f),0,t));TRY(as_asteroids(c,t,1));
 }else if(k==1){TRY(as_ship(c,350.f-300.f*e,120.f+35.f*af_sin(local*17.f),110.f-60.f*e,-12.f+30.f*e,0,t));TRY(as_asteroids(c,t,1.4f));
 }else if(k==2){if(local<23.f)TRY(as_ship(c,100.f+local*4.f,175.f-local*2.1f,75.f-local*2.f,-10.f-local*.2f,0,t));
 }else if(k==3){for(int i=0;i<9;++i){float p=local*1.2f+(float)i/9.f;p-=(float)(int)p;float a=local*37.f+i*28.f,r=15.f+p*240.f;
  TRY(as_beam(c,200.f+af_cos(a)*r,120.f+af_sin(a)*r*.64f,200.f+af_cos(a)*(r+35),120.f+af_sin(a)*(r+35)*.64f,1,0x8fbf,150));}
 }else if(k==4){TRY(as_battle(c,t));
 }else if(k==6){TRY(as_dimensions(c,t));
 }else if(k==7){float q=local/35.f;TRY(as_planet(c,250.f-q*80.f,120.f+q*75.f,30.f+q*68.f,ASTRILLA_PLANET,s*3.f));
  if(local<28)TRY(as_ship(c,90.f+local*3.4f,160.f-local*.8f,110.f-local*3.f,-8.f+local*.2f,0,t));
 }else if(k>=8){float q=k==8?af_ease(local/25.f):1.f;
  if(k==8)TRY(as_ship(c,170.f+q*40.f,72.f+q*124.f,140.f-q*108.f,-12.f+q*13.f,0,t));
  else TRY(as_ship(c,210,196,32,1,0,t));
  for(int i=0;i<12;++i){float a=s*13.f+(float)i*19.f;TRY(as_glow(c,20.f+(float)i*33.f+8.f*af_sin(a),205.f+10.f*af_sin(a*.7f),8.f+(float)(i%3)*4.f,i&1?0xe66bff:0x55ffaa,85));}
 }return 1;
}
static void astrilla_layers(unsigned t,gpu_layer layers[16],gpu_sprite sprites[64],astrilla_info *info){
 memset(layers,0,sizeof(*layers)*16);memset(sprites,0,sizeof(*sprites)*64);unsigned k=as_chapter(t);int local=(int)(t-as_keys[k]);
 if(k==4){
  float sec=(float)local/55.f;unsigned pose=((unsigned)local*256/880)%256;
  int x=af_round((300.f-90.f*af_sin(sec*5.f))*2.f),y=af_round((67.f+18.f*af_sin(sec*11.f))*2.f);
  layers[7]=gpu_make_layer(ASTRILLA_FLAGSHIP+pose*101376U,352,352,288,x-176,y-144,352,288,0,0,3);
 }
 // Discreet chapter card, only at entry; the rest of the screen stays cinematic.
 if(local<140&&k){unsigned hud=ASTRILLA_HUD0+k*64000U;layers[11]=gpu_make_layer(hud,800,800,80,0,0,800,36,0,0,3);}
 if(t<250||t>=16000)layers[13]=gpu_make_layer(t<250?ASTRILLA_TITLE:ASTRILLA_FINISH,640,640,128,80,t<250?285:70,640,128,0,0,3);
 unsigned count=0;
 if(k==4)for(unsigned i=0;i<20;++i){unsigned h=as_hash(i+478);float sec=(float)local/55.f,p=sec*1.5f+(float)i/20.f;p-=(float)(int)p;
  float a=(float)(h&255),r=20.f+p*65.f;int x=af_round(490.f+af_cos(a)*r),y=af_round(145.f+af_sin(a)*r*.7f);
  if(p<.8f)sprites[count++]=gpu_make_sprite(ASTRILLA_PARTICLES+2*1024,x-16,y-16,32,32,9,GPU_SPRITE_ENABLE);
 }
 if(k>=8)for(unsigned i=0;i<48;++i){unsigned h=as_hash(i+817);float sec=(float)t/55.f;int x=af_round((float)(h%800)+12.f*af_sin(sec*9.f+i*13.f));
  int y=(int)((h/800+t*(1+i%3))%460);sprites[count++]=gpu_make_sprite(ASTRILLA_PARTICLES+(i&1?3:4)*1024,x-16,y-16,32,32,8,GPU_SPRITE_ENABLE);}
 // Six-frame iris at shot changes masks deliberate edits, not animation quantization.
 int within=local%385,remain=385-within,gate=0;if(k<2||k==5){if(within<5)gate=(5-within)*240/5;if(remain<5)gate=(5-remain)*240/5;}
 int end=(int)(as_keys[k+1]-t);if(local<8)gate=(8-local)*240/8;if(end<8)gate=(8-end)*240/8;
 if(gate){layers[14]=gpu_make_layer(ASTRILLA_BLACK,800,800,480,0,0,800,(unsigned)gate,0,0,1);layers[15]=gpu_make_layer(ASTRILLA_BLACK,800,800,480,0,480-gate,800,(unsigned)gate,0,0,1);}
 *info=(astrilla_info){t,k,count,k==4?7U:0U};
}
#undef TRY
#endif
