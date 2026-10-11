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
#define AS_FULL_FRAMES 1045U
#define AS_ATLAS_BANKS 26U
#define AS_ATLAS_W 576U
#define AS_ATLAS_H 320U
#define AS_ATLAS_BYTES (AS_ATLAS_W*AS_ATLAS_H*2UL)
#define AS_CACHE_FRAMES (AS_FULL_FRAMES+AS_ATLAS_BANKS*16U)
#define AS_CACHE_BYTES (AS_FULL_FRAMES*192000UL+AS_ATLAS_BANKS*16U*AS_ATLAS_BYTES)
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
typedef struct {uint32_t base;int width,height;int32_t u,v,ux,vx,uy,vy,lens,portal;float seconds,roll,travel,shot;} as_camera;
// Full nonlinear frames share DDR with reusable subpixel panorama atlases.
// A shot owns its own camera/lens. GPU_COPY crops a quarter-pixel filtered atlas
// so a new trajectory does not require storing every final 400x240 background.
static uint32_t as_cache_addr(unsigned i){return AS_CACHE_BASE+(i<AS_FULL_FRAMES?i*192000UL:AS_FULL_FRAMES*192000UL+(i-AS_FULL_FRAMES)*AS_ATLAS_BYTES);}
static unsigned as_cache_bytes(unsigned i){return i<AS_FULL_FRAMES?192000U:AS_ATLAS_BYTES;}
static unsigned as_cache_clock(unsigned i){return i<660?3850+i:i<770?4510+i-660:i<AS_FULL_FRAMES?15675+i-770:0;}
static as_camera as_camera_make(uint32_t base,int w,int h,float cx,float cy,float zoom,float roll,int lens,int portal,int outw,int outh){
 float sn=af_sin(roll*40.743665f),cs=af_cos(roll*40.743665f),ux=zoom*cs,vx=zoom*sn,uy=-zoom*sn,vy=zoom*cs;
 return (as_camera){base,w,h,af_round((cx-outw*.5f*ux-outh*.5f*uy)*65536.f),af_round((cy-outw*.5f*vx-outh*.5f*vy)*65536.f),
  af_round(ux*65536.f),af_round(vx*65536.f),af_round(uy*65536.f),af_round(vy*65536.f),lens,portal,0,roll,0,0};
}
static as_camera as_cache_view(unsigned i){
 if(i<660){float q=(float)i/659.f,r=10.f+30.f*q+245.f*q*q*q;
  float p=af_clamp(280.f*af_ease((q-.40f)/.60f),0,r*.865f);
  return as_camera_make(ASTRILLA_COSMOS,1024,352,512,176,.85f,0,af_round(r*16),af_round(p*16),400,240);}
 if(i<770)return as_camera_make(ASTRILLA_WORMHOLE,1024,512,512,256,.78f,0,-1-(int)(i-660),0,400,240);
 if(i<AS_FULL_FRAMES){float q=af_ease((float)(i-770)/274.f);
  return as_camera_make(ASTRILLA_CLEARING,800,400,427.f+13.f*q,207.5f+30.5f*q,1.5f-.7f*q,0,0,0,400,240);}
 unsigned bank=(i-AS_FULL_FRAMES)/16,phase=(i-AS_FULL_FRAMES)%16;
 // cx, cy, world-units per pixel, bank angle. Each row is a distinct shot.
 static const float plan[26][4]={
 {350,172,.70f,.015f},{650,173,.86f,-.09f},{480,170,.63f,.045f},
 {540,178,1.02f,-.025f},{740,177,.74f,.07f},{300,172,.91f,-.05f},
 {530,176,.69f,0},{650,174,.94f,.10f},{420,176,.81f,-.07f},
 {270,170,.55f,-.06f},{740,174,.65f,.05f},{490,176,.95f,0},
 {350,173,.70f,.08f},{620,174,.86f,-.05f},{512,176,.85f,.015f},
 {440,190,1.05f,-.035f},{560,240,1.15f,.06f},{485,275,.90f,-.06f},
 {610,250,1.10f,.07f},{420,252,.95f,-.05f},{570,238,1.20f,.025f},
 {620,266,.82f,-.08f},{450,245,1.03f,.055f},{550,273,.87f,-.02f},
 {465,238,1.10f,.025f},{400,200,1.5f,0}};
 static const uint32_t terrain[10]={ASTRILLA_VALLEY,ASTRILLA_CANYON,ASTRILLA_CANYON,ASTRILLA_FOREST,ASTRILLA_FOREST,ASTRILLA_CANYON,ASTRILLA_FOREST,ASTRILLA_CANYON,ASTRILLA_FOREST,ASTRILLA_CLEARING};
 uint32_t base=bank<15?ASTRILLA_COSMOS:bank<25?terrain[bank-15]:ASTRILLA_CLEARING;
 int w=base==ASTRILLA_VALLEY||base==ASTRILLA_CLEARING?800:1024,h=bank<15?352:w==800?400:512;
 const float *v=plan[bank];as_camera c=as_camera_make(base,w,h,v[0],v[1],v[2],v[3],0,0,AS_ATLAS_W,AS_ATLAS_H);
 c.u+=(c.ux*(int)(phase&3)+c.uy*(int)(phase>>2))/4;
 c.v+=(c.vx*(int)(phase&3)+c.vy*(int)(phase>>2))/4;
 if(bank==14)c.portal=-1; // distant station is anchored in this world panorama
 return c;
}
static unsigned as_ground_shot(unsigned t){return t>=13750?9U:(t-8800)/550U;}
static unsigned as_ground_bank(unsigned shot){
 static const uint8_t route[9]={0,1,3,4,6,5,7,3,8};
 return shot>=9?24U:15U+route[shot];
}
static unsigned as_plate(unsigned t,int *sx,int *sy){
 unsigned k=as_chapter(t),local=t-as_keys[k],bank;float q;
 *sx=*sy=0;
 if(k==2)return local<660?local:660+(local-660)%110;
 if(k==3)return 660+local%110;
 if(k==9)return 770+(local<275?local:274);
 if(k==0){static const uint8_t opening[5]={0,5,3,6,8};bank=opening[local/385];q=(float)(local%385)/384.f;}
 else if(k==1){bank=9+local/385;q=(float)(local%385)/384.f;}
 else if(k==4){bank=14;q=(float)local/1649.f;}
 else if(k>=5&&k<=7){unsigned shot=as_ground_shot(t);bank=as_ground_bank(shot);q=shot==9?(float)(t-13750)/549.f:(float)((t-8800)%550)/549.f;}
 else{bank=25;q=af_ease((float)local/330.f);}
 static const uint8_t travel[26][4]={
 {4,42,170,38},{160,75,20,5},{70,72,105,2},{0,5,176,76},{160,5,15,75},{30,65,168,15},{40,10,150,72},{165,40,5,40},{80,5,90,78},
 {10,70,166,10},{165,12,15,70},{30,3,145,75},{165,75,8,5},{0,42,176,30},{35,38,115,44},
 {15,2,150,72},{160,5,10,76},{0,70,172,6},{168,70,10,8},{15,6,160,74},{160,8,10,70},{0,65,176,10},{172,6,8,74},{8,76,168,8},{160,15,15,60},{60,35,106,45}};
 const uint8_t *v=travel[bank];float ease=bank==25?q:af_ease(q);
 float cx=v[0]+((float)v[2]-v[0])*ease,cy=v[1]+((float)v[3]-v[1])*ease;
 if(k>=5&&k<=7&&t<13750)cy+=13.f*af_sin(q*256.f);
 int xx=af_round(af_clamp(cx,0,176)*4),yy=af_round(af_clamp(cy,0,80)*4);
 *sx=xx/4;*sy=yy/4;return AS_FULL_FRAMES+bank*16+(unsigned)(xx&3)+(unsigned)(yy&3)*4;
}
static as_camera as_view(unsigned t){
 int x,y;unsigned i=as_plate(t,&x,&y),k=as_chapter(t),local=t-as_keys[k];as_camera c=as_cache_view(i);
 c.u+=c.ux*x+c.uy*y;c.v+=c.vx*x+c.vy*y;c.seconds=(float)t/55.f;
 unsigned length=k<=1?385:k>=5&&k<=7?550:220,relative=k>=5&&k<=7?t-8800:local;
 c.travel=(float)(relative%length)/(float)(length-1);c.shot=(float)(relative/length);return c;
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
static as_motion as_flagship(float seconds){return (as_motion){375.f-seconds*9.f,45.f+seconds*3.1f+22.f*af_sin(seconds*7.f),-9.f,3.1f+22.f*7.f*.024543693f*af_cos(seconds*7.f)};}
typedef struct {float x,y,size,gx,gy,scale,altitude;} as_landing_pose;
static as_landing_pose as_landing(unsigned t){
 unsigned k=as_chapter(t);float local=(float)(t-as_keys[k])/55.f;
 float q=k==8?af_ease(local/18.f):1.f,alt=90.f*(1.f-q),x,y,scale;
 as_camera cam=as_view(t);as_ground(&cam,270.f+170.f*q,265.f+5.f*q,&x,&y,&scale);
 float size=64.f*(1.f+alt/80.f)*scale;
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
// Precompose the distant station once per subpixel atlas phase. Premultiplied
// bilinear alpha avoids dark edges and preserves quarter-pixel camera motion.
// Its live charging light and beam are drawn by the GPU on top of this hull.
static unsigned as_station(const uint16_t *s,int32_t u,int32_t v,unsigned bg){
 u=(u-376*65536)*2;v=(v-81*65536)*2; // world center (440,145), width 128
 int x=u>>16,y=v>>16;if(x<0||x>=255||y<0||y>=255)return bg;
 unsigned fx=((unsigned)u>>12)&15,fy=((unsigned)v>>12)&15,sa=0,sr=0,sg=0,sb=0;
 for(unsigned i=0;i<4;++i){unsigned w=(i&1?fx:16-fx)*(i&2?fy:16-fy),p=s[(y+(i>>1))*256+x+(i&1)],a=(p>>12)*w;
  sa+=a;sr+=((p>>8)&15)*a;sg+=((p>>4)&15)*a;sb+=(p&15)*a;}
 unsigned r=(sr*31+(bg>>11)*15*(3840-sa))/57600;
 unsigned g=(sg*63+((bg>>5)&63)*15*(3840-sa))/57600;
 unsigned b=(sb*31+(bg&31)*15*(3840-sa))/57600;
 return (r<<11)|(g<<5)|b;
}
// Stylized gravitational lens: non-affine sky sampling, dark capture region,
// bright photon ring and an inclined, advecting accretion disk. Integer maths
// keeps the independently implemented reference bit-exact with the AE350.
static __attribute__((optimize("O3"))) void as_background(as_camera c,unsigned t,uint16_t *out,unsigned width,unsigned height,const uint8_t *assets){
 const uint16_t *source=(const uint16_t *)(assets+c.base-ASTRILLA_BASE);
 unsigned radius2=(unsigned)(c.lens*c.lens)>>8;
 int portal_phase=((int)t-4510+5500)%110;as_camera worldcam=as_cache_view(660+(unsigned)portal_phase);
 for(unsigned y=0;y<height;++y){int32_t u=c.u+c.uy*(int)y,v=c.v+c.vy*(int)y;
  for(unsigned x=0;x<width;++x,u+=c.ux,v+=c.vx){
   if(c.lens<=0){int32_t uu=u,vv=v;
    if(c.lens<0){int phase=(-c.lens-1)*256/110;
     uu+=as_sines[(unsigned)(y*2+phase)&255]*100;
     vv+=as_sines[(unsigned)(x*2-phase)&255]*68;}
    unsigned pixel=as_sample(source,&c,uu,vv);
    if(c.portal==-1)pixel=as_station((const uint16_t *)(assets+ASTRILLA_STATION-ASTRILLA_BASE),u,v,pixel);
    out[y*width+x]=(uint16_t)pixel;continue;}

   int dx=(int)x-200,dy=(int)y-120;unsigned d2=(unsigned)(dx*dx+dy*dy)+1;
   if(d2<radius2*3/4){unsigned p=(unsigned)c.portal,pr=p*p/256;
    if(!p||d2>pr){out[y*width+x]=0;continue;}
    unsigned gain=p>=3840?51118U:196293120U/p;
    int phase=portal_phase*256/110;
    as_camera other={0};other.width=1024;other.height=512;
    const uint16_t *world=(const uint16_t *)(assets+ASTRILLA_WORMHOLE-ASTRILLA_BASE);
    out[y*width+x]=(uint16_t)as_sample(world,&other,worldcam.u+200*worldcam.ux+dx*(int)gain+as_sines[(y*2+phase)&255]*100,
     worldcam.v+120*worldcam.vy+dy*(int)gain+as_sines[(x*2-phase)&255]*68);continue;}
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
   out[y*width+x]=(uint16_t)((r<<11)|(g<<5)|b);
  }
 }
}
static void astrilla_background(unsigned t,uint16_t *out,const uint8_t *assets){as_background(as_view(t),t,out,400,240,assets);}
static void astrilla_cache(unsigned i,uint16_t *out,const uint8_t *assets){as_background(as_cache_view(i),as_cache_clock(i),out,i<AS_FULL_FRAMES?400:AS_ATLAS_W,i<AS_FULL_FRAMES?240:AS_ATLAS_H,assets);}
#ifdef ASTRILLA_HOST
#include <stdio.h>
#define TRY(v) do{if(!(v)){fprintf(stderr,"ASTRILLA rejected %s:%d: %s\n",__FILE__,__LINE__,#v);return 0;}}while(0)
#else
#define TRY(v) do{if(!(v))return 0;}while(0)
#endif
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
 int cells=kind>=0&&!(kind&16),cw=cells?32:tw,ch=cells?32:th;
 for(int row=0;row<th;row+=ch)for(int col=0;col<tw;col+=cw){
  if(cells&&!(occupied[kind&7][row/32]&(1U<<(col/32))))continue;
  int vx[4],vy[4];for(int i=0;i<4;++i){float u=(float)(col+((i==1||i==2)?cw:0))-tw*.5f,v=(float)(row+(i>=2?ch:0))-th*.5f;
   vx[i]=af_round(x+u*ax+v*bx);vy[i]=af_round(y+u*ay+v*by);}
  as_rawtri(c,vx[0],vy[0],vx[1],vy[1],vx[2],vy[2]);as_rawtri(c,vx[0],vy[0],vx[2],vy[2],vx[3],vy[3]);
 }return 1;
}
#define AS_WHITE 0xffffffU
static int as_glow(gpu_v1_context *c,float x,float y,float size,unsigned tint,unsigned alpha){return as_image(c,ASTRILLA_GLOW,64,64,x,y,size,size,0,alpha,GPU_V1_ADDITIVE,tint,-1);}
#include "astrilla_3d.h"
#include "astrilla_flight.h"
static as_flight as_flyby_flight(unsigned t,unsigned variant){return as_space_flight((float)t/55.f,variant,1.16f);}
static int as_flyby(gpu_v1_context *c,unsigned t,unsigned variant){
 // Seven-second shots preserve enough time to see approach, bank and escape.
 return as_flight_draw(c,as_flyby_flight(t,variant),0,.9f,t);
}
// A rigid object instance: the CPU supplies one matrix; G3D1 transforms,
// clips, lights and projects the mesh. Rotations preserve its volume.
static int as_relic(gpu_v1_context *c,const as3_mesh *mesh,as3_vec center,float scale,float turn,float tilt){
 float ca=af_cos(turn),sa=af_sin(turn),cb=af_cos(tilt),sb=af_sin(tilt);
 return as3_draw_at(c,mesh,center,scale,(as3_vec){ca*cb,sa*cb,-sb},
  (as3_vec){-sa,ca,0},(as3_vec){ca*sb,sa*sb,cb},0);
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
 float sec=(float)t/55.f,speed=k==3?1800.f:k==4?1100.f:420.f;
 for(unsigned i=0;i<90;++i){unsigned h=as_hash(i+1881);float z=(float)(h%2200)-sec*speed;z-=((float)(int)(z/2200.f)-1.f)*2200.f;if(z>2200)z-=2200;z+=90;
  float xx=(float)((int)((h>>12)%2000)-1000),yy=(float)((int)((h>>21)%1100)-550),x=200.f+xx*180.f/z,y=120.f+yy*180.f/z;
  if(x<0||x>=400||y<0||y>=240)continue;
  float stretch=k==3?af_clamp(190.f/z,.03f,.55f):k==4?af_clamp(130.f/z,.02f,.22f):.010f;
  TRY(as_beam(c,x,y,x+(x-200.f)*stretch+.5f,y+(y-120.f)*stretch+.5f,k==3?.7f:.45f,0xb6df,140));
 }return 1;
}
static int as_asteroids(gpu_v1_context *c,unsigned t,float strength){
 float sec=(float)t/55.f;
 for(unsigned i=0;i<10;++i){unsigned h=as_hash(i+573);float phase=sec*.19f+(h&255)/256.f;phase-=(float)(int)phase;
  float a=(float)((h>>8)&255),r=5.f+(float)((h>>16)%19);
  as3_vec p={af_cos(a)*r,af_sin(a)*r*.65f,94.f-phase*92.f};
  float scale=(.65f+(i%3)*.30f)*strength;
  if(p.x/p.z< -1.4f||p.x/p.z>1.4f||p.y/p.z< -.95f||p.y/p.z>.95f)continue;
  TRY(as_relic(c,&as3_rock,p,scale,sec*(5.f+i*.8f)+i*39.f,sec*3.f+i*27.f));
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
 as_camera camera=as_view(t);float station_x,station_y,scale;
 as_ground(&camera,421.f,126.f,&station_x,&station_y,&scale);
 // The station unfolds a solid orbital structure while the battle continues.
 float deploy=af_ease(sec/3.f);
 if(deploy>.02f)TRY(as_relic(c,&as3_gate,(as3_vec){(station_x-200.f)*.07f,(station_y-120.f)*.07f,14.f},
  4.6f*scale*deploy,sec*2.5f,20.f+8.f*af_sin(sec*5.f)));
 float charge=sec/6.f;charge-=(float)(int)charge;
 if(charge>.55f)TRY(as_glow(c,station_x,station_y,14.f+(charge-.55f)*40.f,0x88ff99,220));
 if(charge>.88f){TRY(as_beam(c,station_x,station_y,430.f,215.f,2.3f,0x5fea,245));
  TRY(as_beam(c,station_x,station_y,430.f,215.f,.7f,0xffff,230));}
 TRY(as_flight_draw(c,as_flight_pose(capital,136.f-sec*1.8f,-1.8f,0),0,.4f,t));
 for(unsigned i=0;i<7;++i){float p;as_flight flight=as_dogfight_flight(sec,i,&p);as_motion m=flight.m;
  for(unsigned j=0;j<3;++j){float pp;as_motion trail=as_dogfight(sec-.035f*(j+1),i,&pp);
   if(pp>p)break;
   TRY(as_beam(c,m.x,m.y,trail.x,trail.y,.65f,i&1?0xfd68:0x5fff,110-j*30));}
  TRY(as_flight_draw(c,flight,i&1,.95f,t));
  unsigned fire=(t+i*13)%31;if(fire<10)TRY(as_flight_shot(c,flight,(float)fire,i&1?0xfb87:0x5fff));
 }
 float p;TRY(as_flight_draw(c,as_dogfight_flight(sec,8,&p),0,1.f,t));
 return 1;
}
static float as_dimension_scale=1.f;
static int as_dimensions(gpu_v1_context *c,unsigned t){
 if(as_dimension_scale<.01f)return 1;
 float sec=(float)t/55.f,s=as_dimension_scale;
 // An orrery with independently precessing rings; front/back intersections
 // share the same hardware depth buffer as the crystals inside it.
 for(unsigned i=0;i<2;++i)TRY(as_relic(c,&as3_gate,(as3_vec){0,0,7},s*(2.55f+i*.35f),sec*(i?-5.f:4.f),i*60.f+sec*6.f));
 TRY(as_relic(c,&as3_crystal,(as3_vec){0,0,7},s*1.2f,sec*8.f,42.f+sec*4.f));
 for(unsigned i=0;i<3;++i){float a=sec*9.f+i*85.3333f;
  as3_vec p={af_cos(a)*3.3f*s,af_sin(a)*1.7f*s,7.f+af_sin(a)*2.f*s};
  TRY(as_relic(c,&as3_crystal,p,s*.52f,-sec*7.f+i*43.f,sec*5.f));
  TRY(as_glow(c,200.f+200.f*p.x/p.z,120.f+200.f*p.y/p.z,12.f*s,i&1?0xff77ee:0x66ddff,150));
 }
 return 1;
}
// Pass through solid gates. Their near sides leave the screen naturally;
// real perspective and the depth buffer reveal thickness and occlusion.
static int as_passage(gpu_v1_context *c,unsigned t,unsigned style){
 float sec=(float)t/55.f;
 for(unsigned i=0;i<3;++i){float p=sec*.23f+i/3.f;p-=(float)(int)p;
  float z=70.f-p*68.f;
  TRY(as_relic(c,&as3_gate,(as3_vec){af_sin(sec*6.f+z)*2.f,af_cos(sec*4.f+z)*.7f,z},5.f,
   sec*(style&1?-4.f:4.f)+i*11.f,af_sin(sec*7.f+i*35.f)*13.f));
 }
 TRY(as_glow(c,200.f,120.f,24.f,0x88ccff,135));
 return 1;
}
static int as_lightspeed(gpu_v1_context *c,unsigned t){
 float sec=(float)(t-6875)/55.f,ramp=af_ease(sec/.65f),speed=2.f+ramp*5.f;
 for(unsigned i=0;i<84;++i){unsigned h=as_hash(i+1499);float p=sec*speed+(h&1023)/1024.f;p-=(float)(int)p;
  float angle=(float)((h>>10)&255),r=5.f+p*p*p*330.f,length=(12.f+160.f*p*p)*ramp;
  float x=200.f+af_cos(angle)*r,y=120.f+af_sin(angle)*r*.65f;
  TRY(as_beam(c,x,y,x+af_cos(angle)*length,y+af_sin(angle)*length*.65f,.5f+p, i%3?0x9fff:0xffff,100+(unsigned)(p*140.f)));}
 for(unsigned i=0;i<3;++i){float p=sec*2.1f+i/3.f;p-=(float)(int)p;
  TRY(as_ringfx(c,200,120,10+p*p*290,6+p*p*180,0,.8f,0xafff,(unsigned)(100.f*(1.f-p)),0));}
 if(sec<1.f)TRY(as_flight_draw(c,as_flight_pose((as_motion){200,170.f-50.f*sec,0,-50},84.f-80.f*sec,-80,0),0,1.f,t));
 return 1;
}
static int as_infall(gpu_v1_context *c,unsigned t){
 float local=(float)(t-as_keys[2])/55.f;as_camera cam=as_view(t);float radius=cam.lens/16.f;
 if(local<8.f){float q=local/8.f;q=q*q;
  TRY(as_flight_draw(c,as_flight_pose((as_motion){45.f+155.f*q,211.f-91.f*q,155,-91},88.f-85.f*q,-85,0),0,1.f,t));}
 // Orbiting hot spots belong to the disk, never to the camera transform.
 for(int i=0;i<3;++i){float a=local*31.f+(float)i*85.f;
  float x=200.f+af_cos(a)*radius*1.85f,y=120.f+af_cos(a)*radius*.46f+af_sin(a)*radius*.30f;
  if((x-200.f)*(x-200.f)+(y-120.f)*(y-120.f)<radius*radius*.78f)continue;
  TRY(as_glow(c,x,y,14.f+radius*.06f,i&1?0x77bbff:0xffbd77,180));}
 return 1;
}
static int as_opening(gpu_v1_context *c,unsigned t,unsigned k,const as_camera *cam){
 float e=cam->travel,sec=(float)t/55.f,px=380.f-450.f*e,py=100.f+12.f*e;
 static const unsigned themes[5]={0,5,3,6,8};
 unsigned shot=(unsigned)cam->shot,mode=themes[shot%5];
 if(mode==0){float r=43.f+16.f*e;
  TRY(as_ringfx(c,px,py,r*1.5f,r*.24f,-8.f,1.8f,0xbccd,160,1));
  TRY(as_planet(c,px,py,r,ASTRILLA_GAS,sec*3.f));
  TRY(as_ringfx(c,px,py,r*1.5f,r*.24f,-8.f,1.8f,0xffd3,190,2));
 }else if(mode==1){
  TRY(as_planet(c,88.f-35.f*e,48.f,18.f,ASTRILLA_PLANET,sec*2.f));
  TRY(as_planet(c,px+20.f,132.f,55.f,ASTRILLA_MOON,sec*5.f));
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
  TRY(as_relic(c,&as3_gate,(as3_vec){3.f-6.f*e,-.6f,18.f-12.f*e},3.7f,sec*3.f,18.f));
  TRY(as_flyby(c,t,shot+1));
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
 TRY(as_flyby(c,t,shot+(k==5?2:0)));
 if(mode==0||mode==1||mode==4||mode==8)TRY(as_asteroids(c,t,1.f));
 return 1;
}
static int as_galaxies(gpu_v1_context *c,unsigned t,const as_camera *cam){
 unsigned shot=(unsigned)cam->shot;float e=cam->travel;
 TRY(as_flyby(c,t,shot+1));
 if(shot==0){TRY(as_asteroids(c,t,1.7f));}
 else if(shot==1){float x=460.f-540.f*e,y=40.f+130.f*e;
  for(int i=0;i<4;++i)TRY(as_beam(c,x,y,x+90.f+i*9.f,y-25.f+i*5.f,1.1f,0x8fff,90-i*16));
  TRY(as_glow(c,x,y,26.f,0x99eeff,230));}
 else if(shot==2){TRY(as_dimensions(c,t));}
 else if(shot==3){for(unsigned i=0;i<18;++i){float p=e*2.f+(float)i/18.f;p-=(float)(int)p;
  float x=-40.f+p*510.f,y=(float)(as_hash(i+515)%180);TRY(as_beam(c,x,y,x-30.f,y-18.f,.6f,0xfeaf,150));}}
 else{for(int i=0;i<6;++i){float a=(float)i*42.66f+(float)t*.06f;
  TRY(as_beam(c,200,120,200.f+af_cos(a)*(20.f+e*90.f),120.f+af_sin(a)*(12.f+e*45.f),.6f,0x7fff,(unsigned)(40.f+e*110.f)));}}
 return 1;
}
static void as_impact(unsigned t,float *x,float *y){
 as_motion impact=as_pursuit(13475,1);as_camera at=as_view(13475),now=as_view(t);
 float wx=(at.u+at.ux*impact.x+at.uy*impact.y)/65536.f,wy=(at.v+at.vx*impact.x+at.vy*impact.y)/65536.f,scale;
 as_ground(&now,wx,wy,x,y,&scale);
}
static int as_fleeing_birds(gpu_v1_context *c,unsigned t,float e,unsigned shot){
 if(e<.32f||e>.89f)return 1;
 float age=(e-.32f)*3.f;
 for(unsigned i=0;i<9;++i){float x=185.f+(i%3)*9.f+(i&1?-1.f:1.f)*age*(65.f+i*7.f),y=177.f-age*(72.f+i*7.f);
  float flap=af_sin(t*5.f+i*31.f),w=2.f+age*2.5f;TRY(as_mat(c,(i+shot)&1?0x9fff:0xfadf,230,0,256,256,256));
  as_rawtri(c,af_round(x),af_round(y),af_round(x-w*2),af_round(y-flap*w-2),af_round(x-w*.3f),af_round(y+1));
  as_rawtri(c,af_round(x),af_round(y),af_round(x+w*2),af_round(y-flap*w-2),af_round(x+w*.3f),af_round(y+1));}
 return 1;
}
static int as_planet_flight(gpu_v1_context *c,unsigned t){
 unsigned shot=as_ground_shot(t);
 if(shot>=9){TRY(as_flyby(c,t,1));return 1;}
 unsigned bank=as_ground_bank(shot),tree=bank==18||bank==19||bank==21||bank==23;
 // Static objects in the same world as the race, viewed by its moving camera.
 as_follow_camera camera=as_race_camera(t);int segment=(int)((t-8800)*12U/55U)/9;unsigned drawn=0;
 for(int j=-4;j<7&&drawn<3;++j){int id=segment+j;unsigned h=as_hash((unsigned)(id+400));
  float side=h&1?1.f:-1.f;as3_vec world={side*(8.f+(h%7)*.3f),3.1f,(float)id*9.f};
  as3_vec view=as_camera_point(world,camera);
  if(view.z<3.4f||view.z>35.f||view.x/view.z< -1.15f||view.x/view.z>1.15f)continue;
  TRY(as3_obstacle_at(c,tree,view,1.f,(h&255)+camera.yaw));++drawn;
 }
 // Ancient stone arches are fixed in the race world, never tied to the screen.
 // The same view matrix makes the ships pass between their near/far sides.
 if(t>=9900){int cell=(int)((t-8800)*12U/55U)/45;
  for(int j=-1;j<=2;++j){as3_vec p=as_camera_point((as3_vec){0,-3.5f,(float)(cell+j)*45.f},camera);
   if(p.z<3.f||p.z>65.f||p.x/p.z< -1.5f||p.x/p.z>1.5f)continue;
   TRY(as_relic(c,&as3_arch,p,5.f,0,-camera.yaw));
  }
 }
 float action=(float)((t-8800)%165)/164.f;
 for(unsigned i=0;i<18;++i){float p=action*5.f+i/18.f;p-=(float)(int)p;float side=i&1?-1.f:1.f;
  float x=200.f+side*(100.f+p*160.f),y=35.f+(as_hash(i+shot*13)%160);
  TRY(as_beam(c,x,y,x+side*(20.f+p*36.f),y+10.f,.5f,0xafff,65));}
 as_flight hero_flight=as_pursuit_flight(t,0),enemy_flight=as_pursuit_flight(t,1);
 as_motion hero=hero_flight.m,enemy=enemy_flight.m;
 if(t>=9295&&t<13475){TRY(as_flight_draw(c,enemy_flight,1,1.f,t));
  unsigned fire=t%29;if(fire<9){float p=fire/9.f,x=hero.x+(enemy.x-hero.x)*p,y=hero.y+(enemy.y-hero.y)*p;
   TRY(as_beam(c,x,y,x+(enemy.x-hero.x)*.20f,y+(enemy.y-hero.y)*.20f,.8f,0x67ff,230));}}
 if(t>=13464&&t<13480){float x,y;as_impact(t,&x,&y);TRY(as_beam(c,hero.x,hero.y,x,y,1.3f,0xcfff,230));}
 if(t>=13475&&t<13585){float x,y;as_impact(t,&x,&y);float age=(t-13475)/110.f;
  for(unsigned i=0;i<8;++i){float a=(float)(as_hash(i+313)&255),r=age*(28.f+i*6.f);float xx=x+af_cos(a)*r,yy=y+af_sin(a)*r*.6f+age*age*25.f;
   TRY(as_beam(c,xx,yy,xx-af_cos(a)*4.f,yy-af_sin(a)*3.f,.65f,0xfca8,(unsigned)(210.f*(1.f-age))));}
  TRY(as_ringfx(c,x,y,12.f+age*90.f,8.f+age*60.f,0,1.2f,0xffd3,(unsigned)(200.f*(1.f-age)),0));}
 TRY(as_flight_draw(c,hero_flight,0,1.f,t));
 if(tree)TRY(as_fleeing_birds(c,t,action,shot));
 return 1;
}
static int as_wildlife(gpu_v1_context *c,unsigned t,const as_camera *cam){
 float sec=(float)t/55.f;
 for(int i=0;i<2;++i){float x,y,scale;as_ground(cam,i?600.f:280.f,335.f,&x,&y,&scale);
  float sway=af_sin(sec*12.f+i*53.f)*1.8f;
  TRY(as_image(c,ASTRILLA_FERN,128,192,x+af_sin(sway)*45.f*scale,y-af_cos(sway)*45.f*scale,60.f*scale,90.f*scale,sway,256,0,AS_WHITE,-1));}
 for(int i=0;i<6;++i){float p=sec*.041f+i*.163f;p-=(float)(int)p;
  float x=-20.f+p*450.f,y=62.f+i*16.f+af_sin(sec*11.f+i*37.f)*8.f,flap=af_sin(sec*110.f+i*43.f);
  float size=3.f+(float)(i%3);TRY(as_mat(c,i&1?0x7fdf:0xfaff,210,0,256,256,256));
  as_rawtri(c,af_round(x),af_round(y),af_round(x-size*2),af_round(y-2-flap*size),af_round(x-size*.7f),af_round(y+2));
  as_rawtri(c,af_round(x),af_round(y),af_round(x+size*1.8f),af_round(y-2-flap*size),af_round(x+size*.6f),af_round(y+2));
  TRY(as_beam(c,x,y,x-size*.6f,y+size*1.7f,.5f,0x87ff,180));
  TRY(as_beam(c,x+.8f,y,x+size*.7f,y+size*1.6f,.4f,0xfcff,160));}
 return 1;
}
static int as_bloom(gpu_v1_context *c,unsigned t,const as_camera *cam){
 if(t<15290)return 1;
 float open=af_ease((float)(t-15290)/220.f),sec=(float)(t-15290)/55.f;
 if(open<.01f)return 1;
 float x,y,size;as_ground(cam,495.f,287.f,&x,&y,&size);
 float z=10.f/size;as3_vec center={(x-200.f)*z/200.f,(y-120.f)*z/200.f,z};
 for(unsigned i=0;i<6;++i){float a=i*42.6667f+sec*1.5f,r=.25f+1.25f*open;
  as3_vec p={center.x+af_cos(a)*r,center.y+af_sin(a)*r*.34f-open*.35f,center.z+af_sin(a)*r*.8f};
  TRY(as_relic(c,&as3_crystal,p,.72f*open,a,open*57.f));
 }
 TRY(as_relic(c,&as3_crystal,(as3_vec){center.x,center.y-open,center.z},open*.55f,sec*5.f,48.f));
 TRY(as_glow(c,x,y-open*20.f*size,26.f*size*open,0x77ffcc,140));
 return 1;
}
static int astrilla_render(gpu_v1_context *c,unsigned t,unsigned page){
 if(t>=ASTRILLA_FRAMES||page>1)return 0;
 unsigned k=as_chapter(t);as_camera cam=as_view(t);float local=(float)(t-as_keys[k])/55.f;
 int bx,by;unsigned slot=as_plate(t,&bx,&by),wide=slot>=AS_FULL_FRAMES;
 gpu_target dst={GPU_PAGE_ADDR(page),GPU_PAGE_ADDR(2),400,240,800,800},bg={as_cache_addr(slot),0,wide?AS_ATLAS_W:400,wide?AS_ATLAS_H:240,wide?AS_ATLAS_W*2:800,0};
 TRY(gpu_v1_target(c,&dst));TRY(gpu_v1_scissor(c,0,0,400,240));TRY(gpu_v1_clear(c,2,0,65535,0,0,400,240));TRY(gpu_v1_copy(c,&bg,bx,by,0,0,400,240));
 as_dimension_scale=1.f;
 if(k<5&&k!=2&&!(t>=6875&&t<7150))TRY(as_stars(c,t,k));
 if(k==0){TRY(as_opening(c,t,k,&cam));
 }else if(k==1){TRY(as_galaxies(c,t,&cam));
 }else if(k==2){as_dimension_scale=af_ease((local-9.f)/5.f);
  if(local<12.f){TRY(as_infall(c,t));if(local>9.f)TRY(as_dimensions(c,t));}
  else{unsigned style=(unsigned)((local-12.f)/6.f);TRY(as_stars(c,t,3));
   if(style!=1)TRY(as_dimensions(c,t));
   if(style!=0)TRY(as_passage(c,t,style));}
 }else if(k==3){if(t>=6875)TRY(as_lightspeed(c,t));else TRY(as_passage(c,t,(unsigned)(local/6.f)));
 }else if(k==4){TRY(as_battle(c,t));
 }else if(k>=5&&k<=7){TRY(as_planet_flight(c,t));
 }else if(k>=8){as_landing_pose pose=as_landing(t);float alt=pose.altitude,x=pose.gx,y=pose.gy,scale=pose.scale;
  TRY(as_image(c,ASTRILLA_SHADOW,64,32,x,y,70.f*scale,18.f*scale,0,(unsigned)(240.f-alt),0,AS_WHITE,-1));
  // The same level attitude holds through touchdown and the final dolly.
  TRY(as3_ship(c,pose.x,pose.y,pose.size,0,24.f,0,0,af_clamp(alt/25.f,0,1),t));
  if(k==8&&local>=18.f&&local<20.f){float age=(local-18.f)/2.f;TRY(as_ringfx(c,x,y,(12.f+age*32.f)*scale,(3.f+age*8.f)*scale,0,1,0xa4eb,(unsigned)(100.f*(1.f-age)),0));}
  TRY(as_bloom(c,t,&cam));
  TRY(as_wildlife(c,t,&cam));
  for(int i=0;i<12;++i){float gx,gy,z;as_ground(&cam,280.f+(float)i*26.f,327.f+(float)((i*19)%35),&gx,&gy,&z);
   TRY(as_glow(c,gx,gy,(3.f+(float)(i%3))*z,i&1?0xe66bff:0x55ffaa,85));}
 }return 1;
}
static void astrilla_layers(unsigned t,gpu_layer layers[16],gpu_sprite sprites[64],astrilla_info *info){
 memset(layers,0,sizeof(*layers)*16);memset(sprites,0,sizeof(*sprites)*64);unsigned k=as_chapter(t);int local=(int)(t-as_keys[k]);
 if(k==4){
  float sec=(float)local/55.f;as_motion capital=as_flagship(sec);int x=af_round(capital.x*2.f),y=af_round(capital.y*2.f);
  for(int i=0;i<3;++i){float f=sec*.8f+i*.33f;f-=(float)(int)f;if(f<.72f){unsigned pose=(unsigned)(f*10.f);
   layers[8+i]=gpu_make_layer(ASTRILLA_FIRE_NATIVE+pose*16384U,128,128,128,x+(i-1)*48-64,y+(i-1)*28-64,128,128,0,0,3);}}
 }
 if(t>=8800&&t<13750){unsigned shot=as_ground_shot(t),bank=as_ground_bank(shot);
  if(bank==18||bank==19||bank==21||bank==23)for(unsigned i=0;i<2;++i){float p=(float)(t-8800)/(i?57.f:43.f)+i*.47f;p-=(float)(int)p;
   int x=af_round((shot==3?-150.f+p*1000.f:850.f-p*1000.f)),y=335+(int)i*45;
   unsigned pose=(t/9+i*5)%16;layers[5+i]=gpu_make_layer(ASTRILLA_FERN_NATIVE+pose*24576U,128,128,192,x,y,128,192,0,0,3);}
 }
 if(t>=13475&&t<13640){float x,y;as_impact(t,&x,&y);unsigned age=t-13475,pose=age*8/165;
  layers[8]=gpu_make_layer(ASTRILLA_FIRE_LARGE+pose*36864U,192,192,192,af_round(x*2)-96,af_round(y*2)-96,192,192,0,0,3);
 }
 if(t<250||t>=16000)layers[11]=gpu_make_layer(t<250?ASTRILLA_TITLE:ASTRILLA_FINISH,640,640,128,80,t<250?285:70,640,128,0,0,3);
 unsigned count=0;
 if(k==4)for(unsigned i=0;i<20;++i){unsigned h=as_hash(i+478);float sec=(float)local/55.f,p=sec*1.5f+(float)i/20.f;p-=(float)(int)p;
  float a=(float)(h&255),r=20.f+p*65.f;as_motion capital=as_flagship(sec);int x=af_round(capital.x*2.f+af_cos(a)*r),y=af_round(capital.y*2.f+af_sin(a)*r*.7f);
  if(p<.8f)sprites[count++]=gpu_make_sprite(ASTRILLA_PARTICLES+2*1024,x-16,y-16,32,32,10,GPU_SPRITE_ENABLE);
 }
 if(k>=8){as_camera cam=as_view(t);for(unsigned i=0;i<48;++i){unsigned h=as_hash(i+817);float sec=(float)t/55.f,x,y,scale;
  as_ground(&cam,250.f+(float)(h%380)+4.f*af_sin(sec*4.f+i*13.f),265.f+(float)((h/380)%75),&x,&y,&scale);
  sprites[count++]=gpu_make_sprite(ASTRILLA_FIREFLY+((t/6+i*11)&15)*1024,af_round(x*2.f)-16,af_round(y*2.f)-16,32,32,8,GPU_SPRITE_ENABLE);}}
 // Native animated motes complement the hardware meshes. These sprites
 // occupy a foreground particle plane, independently of the 3D framebuffer.
 if(t>=4510&&t<6875){float sec=(float)(t-4510)/55.f;
  for(unsigned i=0;i<16;++i){float p=sec*.22f+i/16.f;p-=(float)(int)p;
   float a=i*97.f+sec*2.f,r=22.f+p*p*430.f;
   sprites[count++]=gpu_make_sprite(ASTRILLA_FIREFLY+((t/5+i*3)&15)*1024,
    af_round(400.f+af_cos(a)*r)-16,af_round(240.f+af_sin(a)*r*.58f)-16,32,32,8,GPU_SPRITE_ENABLE);
  }
 }
 // Six-frame iris at shot changes masks deliberate edits, not animation quantization.
 unsigned shotlength=k<=1?385:k>=5&&k<=7?550:220;
 int within=(k>=5&&k<=7?(int)(t-8800):local)%(int)shotlength,remain=(int)shotlength-within,gate=0;if(k<2){if(within<5)gate=(5-within)*240/5;if(remain<5)gate=(5-remain)*240/5;}
 
 int end=(int)(as_keys[k+1]-t);if(local<8&&k!=9&&!(k>=6&&k<=7))gate=(8-local)*240/8;if(end<8&&k!=8&&k!=5&&k!=6)gate=(8-end)*240/8;
 if(gate){layers[12]=gpu_make_layer(ASTRILLA_BLACK,800,800,480,0,0,800,(unsigned)gate,0,0,1);layers[13]=gpu_make_layer(ASTRILLA_BLACK,800,800,480,0,480-gate,800,(unsigned)gate,0,0,1);}
 *info=(astrilla_info){t,k,count,k==4?7U:t>=9295&&t<13475?1U:0U};
}
#undef TRY
#endif
