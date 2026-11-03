// ASTRA: a deterministic 300-second cinematic on the existing C37 GPU.
// Shared by the AE350 and the independent host pixel oracle. No SD access.
#ifndef ASTRA_SCENE_H
#define ASTRA_SCENE_H
#include <stdint.h>
#include <string.h>
#include "gpu_v1.h"
#include "astra_assets.h"
#define ASTRA_HZ 55U
#define ASTRA_FRAMES (300U*ASTRA_HZ)
typedef struct { unsigned frame,chapter,sprites,shots; } astra_info;
static int as_min(int a,int b){return a<b?a:b;}
static int as_max(int a,int b){return a>b?a:b;}
static int as_clamp(int a,int lo,int hi){return as_min(as_max(a,lo),hi);}
// Fine angles in 1/65536 turns. Signed divisions avoid left-shift UB.
static int as_sin(int a){unsigned p=(unsigned)a&65535;int i=p>>8;return as_sines[i]+(as_sines[i+1]-as_sines[i])*(int)(p&255)/256;}
static int as_cos(int a){return as_sin(a+16384);}
static unsigned as_hash(unsigned v){v^=v>>16;v*=0x7feb352d;v^=v>>15;v*=0x846ca68b;return v^(v>>16);}
static int as_ease(int a,int b,int t,int n){int u=as_clamp(t*1024/n,0,1024);return a+(int)((int64_t)(b-a)*u*u*(3072-2*u)/1073741824);}
static const unsigned as_keys[11]={0,1925,3850,5500,7150,8800,10450,12375,14300,15675,16500};
static unsigned as_chapter(unsigned t){unsigned k=0;while(k<9&&t>=as_keys[k+1])++k;return k;}
static unsigned as_color(int r,int g,int b){return (unsigned)(as_clamp(r,0,31)<<11|as_clamp(g,0,63)<<5|as_clamp(b,0,31));}
#define AS_TRY(v) do{if(!(v))return 0;}while(0)
static gpu_vertex as_vertex(int x,int y,int z){return (gpu_vertex){x,y,0,0,as_clamp(z,0,65535),65536,256,256,256};}
static int as_material(gpu_v1_context *c,unsigned col,unsigned alpha,unsigned flags){gpu_material m={flags,alpha,col,256,256,256,0,0,0};return gpu_v1_material(c,&m);}
static int as_tri(gpu_v1_context *c,int x0,int y0,int x1,int y1,int x2,int y2,int z){gpu_vertex v[3]={as_vertex(x0,y0,z),as_vertex(x1,y1,z),as_vertex(x2,y2,z)};return gpu_v1_triangle(c,v);}
static int as_line(gpu_v1_context *c,int x0,int y0,int x1,int y1,int w,int z){
 int dx=x1-x0,dy=y1-y0,px=0,py=0;if(!dx&&!dy)return 1;
 if((dx<0?-dx:dx)>(dy<0?-dy:dy))py=w;else px=w;
 gpu_vertex v[4]={as_vertex(x0-px,y0-py,z),as_vertex(x1-px,y1-py,z),as_vertex(x1+px,y1+py,z),as_vertex(x0+px,y0+py,z)};
 return gpu_v1_quad(c,v);
}
// Thin elliptical ribbons. Colour and intensity run around the ring.
// range 0=complete,1=far half,2=near half for planet occlusion.
static int as_ring(gpu_v1_context *c,int x,int y,int rx,int ry,int tilt,int width,unsigned t,unsigned col,int range,unsigned alpha){
 int sn=as_sin(tilt),cs=as_cos(tilt),begin=range==2?16:0,end=range==1?16:32;
 for(int i=begin;i<end;++i){int a=i*2048,b=(i+1)*2048;
  int ax=as_cos(a)*rx/16384,ay=as_sin(a)*ry/16384,bx=as_cos(b)*rx/16384,by=as_sin(b)*ry/16384;
  int power=as_clamp((int)alpha+(as_sin(a+(int)t*43)*50/16384),16,256);
  AS_TRY(as_material(c,col,(unsigned)power,GPU_V1_ADDITIVE));
  AS_TRY(as_line(c,x+(ax*cs-ay*sn)/16384,y+(ax*sn+ay*cs)/16384,x+(bx*cs-by*sn)/16384,y+(bx*sn+by*cs)/16384,width,50000));
 }return 1;
}
// GPU texture mapping and Gouraud illumination on a tessellated sphere.
// Only the visible hemisphere is emitted; the rear hemisphere cannot add overdraw.
static int as_planet(gpu_v1_context *c,int x,int y,int radius,unsigned texture,int rotation,unsigned tint){
 gpu_texture_level tex={texture,256,128,512,GPU_RGB565,GPU_TEX_REPEAT,GPU_TEX_CLAMP,0};
 AS_TRY(gpu_v1_texture(c,&tex));AS_TRY(as_material(c,tint,256,GPU_RASTER_TEXTURE|GPU_V1_GOURAUD));
 int rows=radius>=80?10:radius>=40?8:radius>=20?6:4,columns=radius>=80?16:radius>=40?12:radius>=20?10:8;
 for(int row=0;row<rows;++row)for(int col=0;col<columns;++col){gpu_vertex v[4];
  for(int i=0;i<4;++i){int r=row+(i>=2),s=col+(i==1||i==2),lat=-16384+r*32768/rows,lon=-16384+s*32768/columns;
   int nx=as_cos(lat)*as_sin(lon)/16384,ny=as_sin(lat),nz=as_cos(lat)*as_cos(lon)/16384;
   int light=as_clamp(54+(-nx*72-ny*80+nz*145)/16384,18,256);
   if(texture==ASTRA_SUN)light=256; // Photosphere emits its own light.
   v[i]=(gpu_vertex){x+nx*radius/16384,y+ny*radius/16384,rotation+s*128/columns,r*127/rows,50000,65536,light,light,light};
  }
  AS_TRY(gpu_v1_quad(c,v));
 }return 1;
}
// Lit low-poly spacecraft with separate wings, engine pods, cockpit and hull.
// Vertex transforms are 3D; Z16 resolves intersecting wings and hulls.
static int as_ship(gpu_v1_context *c,int x,int y,int scale,int yaw,int roll,int depth,int enemy,unsigned t){
 static const int16_t points[][3]={{0,0,-80},{-18,-10,30},{18,-10,30},{0,-20,18},{0,12,24},
  {-65,4,45},{-20,3,-8},{-32,8,60},{65,4,45},{20,3,-8},{32,8,60},
  {-23,-3,48},{-12,-3,48},{-18,-14,30},{12,-3,48},{23,-3,48},{18,-14,30},
  {0,-20,-25},{-9,-12,0},{9,-12,0},{0,-25,27}};
 static const uint8_t faces[][4]={{0,1,3,0},{0,3,2,1},{0,2,4,2},{0,4,1,0},{1,4,2,2},{1,2,3,0},
  {5,6,7,1},{6,1,7,0},{8,10,9,0},{9,10,2,1},{11,12,13,3},{14,15,16,3},
  {0,18,17,4},{0,17,19,4},{18,19,17,4},{3,20,2,1},{1,20,3,2}};
 gpu_vertex v[21];int sn=as_sin(yaw),cs=as_cos(yaw),sr=as_sin(roll),cr=as_cos(roll);
 for(unsigned i=0;i<21;++i){int xx=(points[i][0]*cs+points[i][2]*sn)/16384,zz=(points[i][2]*cs-points[i][0]*sn)/16384,yy=points[i][1];
  int pitched=(yy*14418+zz*7780)/16384,zview=(zz*14418-yy*7780)/16384;
  int rx=(xx*cr-pitched*sr)/16384,ry=(xx*sr+pitched*cr)/16384;
  v[i]=as_vertex(x+rx*scale*320/(100*(320+zview)),y+ry*scale*320/(100*(320+zview)),depth+zview*12);
 }
 static const unsigned friendly[5]={0x7c31,0xbdf7,0x31e9,0x3fff,0x2bd8},hostile[5]={0x922a,0xdc52,0x4824,0xfd43,0xfa83};
 for(unsigned i=0;i<sizeof(faces)/sizeof(*faces);++i){gpu_vertex q[3]={v[faces[i][0]],v[faces[i][1]],v[faces[i][2]]};
  AS_TRY(as_material(c,(enemy?hostile:friendly)[faces[i][3]],256,GPU_Z_TEST|GPU_Z_WRITE));AS_TRY(gpu_v1_triangle(c,q));}
 // Pulsating ion exhaust, three translucent cones behind the engines.
 AS_TRY(as_material(c,enemy?0xfce6:0x3dff,180,GPU_V1_ADDITIVE|GPU_Z_TEST));
 for(unsigned i=0;i<2;++i){gpu_vertex a=v[i?14:11],b=v[i?15:12],tip=a;tip.x=(a.x+b.x)/2+as_sin(yaw)*scale/50000;tip.y+=scale*(23+(int)(t%7))/100;
  gpu_vertex q[3]={a,b,tip};AS_TRY(gpu_v1_triangle(c,q));}
 return 1;
}
static int as_explosion(gpu_v1_context *c,int x,int y,int age,unsigned seed){
 if(age<0||age>=70)return 1;
 int r=3+age*2/3,alpha=(70-age)*256/70;
 AS_TRY(as_ring(c,x,y,r,r*2/3,0,1,seed+age,0xfd4b,0,(unsigned)alpha));
 for(int i=0;i<12;++i){int a=i*65536/12+(int)(seed&65535),dist=age*(5+i%3)/5;
  int px=x+as_cos(a)*dist/16384,py=y+as_sin(a)*dist/16384,s=as_max(1,7-age/12);
  AS_TRY(as_material(c,i&1?0xfbe4:0xff98,(unsigned)alpha,GPU_V1_ADDITIVE));AS_TRY(as_tri(c,px-s,py+s,px,py-s,px+s,py+s,1000));
 }return 1;
}
static int as_solar(gpu_v1_context *c,unsigned t,unsigned k){
 int u=(int)(t-as_keys[k]),n=(int)(as_keys[k+1]-as_keys[k]);
 AS_TRY(as_ring(c,290,104,33,33,0,4,t,0xfce5,0,85));
 AS_TRY(as_planet(c,290,104,29,ASTRA_SUN,(int)t/12,0xffff));
 // Orbiting bodies and a large ringed gas giant pass at different depths.
 int px=as_ease(66,106,u,n),py=135+as_sin((int)t*14)*7/16384;
 AS_TRY(as_ring(c,px,py,92,23,-4200,2,t,0xccd2,1,155));
 AS_TRY(as_planet(c,px,py,55,k==5?ASTRA_PLANET:ASTRA_GAS,(int)t/14,0xffff));
 AS_TRY(as_ring(c,px,py,92,23,-4200,2,t,0xccd2,2,150));
 AS_TRY(as_planet(c,236+as_cos((int)t*27)*34/16384,153+as_sin((int)t*27)*17/16384,15,ASTRA_MOON,(int)t/6,0xffff));
 AS_TRY(as_ship(c,235+as_sin((int)t*19)*18/16384,185,36,28000+(int)t*3,as_sin((int)t*21)/9,19000,0,t));
 return 1;
}
static int as_galaxies(gpu_v1_context *c,unsigned t){
 int u=(int)(t-as_keys[1]);
 // Spiral of bright dust in front of the galaxy panorama: 3 arms rotate
 // differentially, with a central glow and travelling exploration vessel.
 for(int i=0;i<60;++i){int arm=i%3,r=8+i*2,a=arm*21845+i*690+(int)t*13;
  int x=205+as_cos(a)*r/16384,y=114+as_sin(a)*r/42000;
  AS_TRY(as_material(c,i&1?0x869f:0xfe75,110,GPU_V1_ADDITIVE));AS_TRY(as_line(c,x,y,x+2,y+1,1,45000));}
 AS_TRY(as_ship(c,as_ease(340,80,u,1925),184+as_sin((int)t*11)*18/16384,45,as_ease(23000,40000,u,1925),-2300,14000,0,t));
 return 1;
}
static int as_blackhole(gpu_v1_context *c,unsigned t){
 int u=(int)(t-as_keys[2]),r=u<1430?as_ease(22,89,u,1430):as_ease(89,330,u-1430,220),cx=200+as_sin((int)t*11)*12/16384,cy=115;
 // In the final four seconds the camera crosses the horizon. Once inside,
 // only the stretched front accretion arc remains before the wormhole cut.
 // The far accretion disc and Einstein ring pass behind the event horizon.
 for(int j=0;j<3;++j)AS_TRY(as_ring(c,cx,cy,r*2+j*5,r/2+j*2,-3700,2,t+j*40,0xfce9,1,140-j*25));
 AS_TRY(as_ring(c,cx,cy,r+5,r+5,0,3,t,0xfc8b,0,160));
 // Fast opaque spans for the dark core, rather than a full-screen alpha fill.
 for(int y=as_max(-r,18-cy);y<=as_min(r,221-cy);++y){int w=0;while(w*w+y*y<r*r)++w;if(w)AS_TRY(gpu_v1_clear(c,1,0x0001,0,cx-w,cy+y,(unsigned)(2*w),1));}
 // Lensed light above and below the core, animated photon filaments.
 AS_TRY(as_ring(c,cx,cy,r+2,r+2,0,1,t,0xff95,0,210));
 for(int j=0;j<3;++j)AS_TRY(as_ring(c,cx,cy,r*2+j*5,r/2+j*2,-3700,2,t+j*40,j?0xfba4:0xffb3,2,190-j*35));
 for(int i=0;i<12;++i){int a=i*5461+(int)t*70;int x=cx+as_cos(a)*(r+8)/16384,y=cy+as_sin(a)*(r+8)/16384;
  AS_TRY(as_material(c,0xfe96,180,GPU_V1_ADDITIVE));AS_TRY(as_line(c,x,y,x+as_cos(a+12000)*7/16384,y+as_sin(a+12000)*7/16384,1,100));}
 return 1;
}
static int as_wormhole(gpu_v1_context *c,unsigned t,int alternate){
 int cx=200+as_sin((int)t*41)*43/16384,cy=120+as_cos((int)t*31)*24/16384;
 for(int ring=12;ring>=0;--ring){int z=100+ring*90-(int)(t*4%90);
  if(z<40)continue; // Passed the near plane; never divide by zero or invert a ring.
  int radius=16000/z;
  int twist=(int)t*29+ring*2100,x=cx+as_sin(twist)*ring/2/16384,y=cy+as_cos(twist)*ring/2/16384;
  AS_TRY(as_ring(c,x,y,radius,radius*3/5,twist,1,t,alternate?0xfd5f:0x557f,0,(unsigned)(240-ring*12)));
  AS_TRY(as_material(c,alternate?0x6d7f:0x7b5f,100,GPU_V1_ADDITIVE));
  for(int j=0;j<8;++j){int a=j*8192+twist,b=a+1700,outer=16000/as_max(30,z-65);
   AS_TRY(as_tri(c,x+as_cos(a)*radius/16384,y+as_sin(a)*radius/27000,
     x+as_cos(b)*outer/16384,y+as_sin(b)*outer/27000,x+as_cos(a+450)*outer/16384,y+as_sin(a+450)*outer/27000,50000));}
 }return 1;
}
static int as_battle(gpu_v1_context *c,unsigned t){
 unsigned u=t-as_keys[4];
 AS_TRY(as_planet(c,327,78,37,ASTRA_MOON,(int)t/14,0xffff));
 AS_TRY(as_ship(c,67,84,105,20000,4200,35000,1,t));
 AS_TRY(as_ship(c,325,157,92,43000,-2100,33000,0,t));
 for(int i=0;i<7;++i){int a=(int)u*48+i*9362,x=200+as_sin(a)*160/16384,y=112+as_cos(a*2+i*1700)*63/16384;
  AS_TRY(as_ship(c,x,y,19+i%3*7,20000+as_sin(a)*2,as_cos(a)/2,18000-i*1200,i&1,t));
  unsigned phase=(u+(unsigned)i*31)%100;
  if(phase<48){int tx=i&1?320:70,ty=i&1?157:84;int bx=x+(tx-x)*(int)phase/48,by=y+(ty-y)*(int)phase/48;
   AS_TRY(as_material(c,i&1?0xfa86:0x4fff,200,GPU_V1_ADDITIVE));AS_TRY(as_line(c,bx,by,bx+(tx-x)/7,by+(ty-y)/7,1,100));}
  else AS_TRY(as_explosion(c,i&1?310:83,i&1?148:92,(int)phase-48,(unsigned)i*313));
 }
 // Foreground laser volleys sweep past the camera; no random runtime state.
 if(u%90<22){AS_TRY(as_material(c,0x6fff,210,GPU_V1_ADDITIVE));AS_TRY(as_line(c,30,216,172,110,1,50));AS_TRY(as_line(c,372,216,224,110,1,50));}
 return 1;
}
static int as_multiverse(gpu_v1_context *c,unsigned t){
 // A receding lattice bends around the hypercube: a visible space to travel
 // through, with several satellite polyhedra orbiting in different planes.
 AS_TRY(as_material(c,0x3957,90,GPU_V1_ADDITIVE));
 for(int i=-5;i<=5;++i)AS_TRY(as_line(c,200+i*8,157,200+i*69,221,1,60000));
 for(int i=0;i<7;++i){int y=158+(i*i*61+(int)(t%55))/49;AS_TRY(as_line(c,0,y,400,y,1,60000));}
 for(int i=0;i<4;++i){int a=(int)t*17+i*16384,x=200+as_cos(a)*155/16384,y=111+as_sin(a)*77/16384,s=11+i%2*6;
  AS_TRY(as_material(c,i&1?0x4873:0x1bd3,100,GPU_V1_ADDITIVE));AS_TRY(as_tri(c,x-s,y+s/2,x+s,y+s/2,x,y-s,40000));
  AS_TRY(as_material(c,i&1?0xfc7f:0x67ff,150,GPU_V1_ADDITIVE));AS_TRY(as_line(c,x-s,y+s/2,x,y-s,1,100));AS_TRY(as_line(c,x,y-s,x+s,y+s/2,1,100));
  AS_TRY(as_line(c,x+s,y+s/2,x-s,y+s/2,1,100));}
 int xyz[16][3],px[16],py[16];
 // Tesseract rotated in XW and YZ, projected 4D->3D->2D.
 int a=(int)t*35,b=(int)t*23,cs=as_cos(a),sn=as_sin(a),ct=as_cos(b),st=as_sin(b);
 for(int i=0;i<16;++i){int x=i&1?80:-80,y=i&2?80:-80,z=i&4?80:-80,w=i&8?80:-80;
  int xx=(x*cs-w*sn)/16384,ww=(x*sn+w*cs)/16384,yy=(y*ct-z*st)/16384,zz=(y*st+z*ct)/16384;
  int k=280-ww;xyz[i][0]=xx*200/k;xyz[i][1]=yy*200/k;xyz[i][2]=zz*200/k;
  int depth=310+xyz[i][2];px[i]=200+xyz[i][0]*230/depth;py[i]=117+xyz[i][1]*230/depth;
 }
 // A few glass faces, then luminous edges: two depth dimensions remain legible.
 static const uint8_t faces[6][4]={{0,1,3,2},{4,5,7,6},{8,9,11,10},{12,13,15,14},{0,4,12,8},{3,7,15,11}};
 for(int i=0;i<6;++i){gpu_vertex v[4];for(int j=0;j<4;++j){unsigned id=faces[i][j];v[j]=as_vertex(px[id],py[id],50000);}
  AS_TRY(as_material(c,i&1?0x325f:0x69ba,50,GPU_V1_ADDITIVE));AS_TRY(gpu_v1_quad(c,v));}
 for(int i=0;i<16;++i)for(int dim=0;dim<4;++dim)if(!(i&(1<<dim))){int j=i|(1<<dim);AS_TRY(as_material(c,dim==3?0xfc7f:0x4fff,210,GPU_V1_ADDITIVE));AS_TRY(as_line(c,px[i],py[i],px[j],py[j],1,100));}
 for(int i=0;i<3;++i)AS_TRY(as_ring(c,200,117,100+i*24,36+i*6,(int)t*11+i*16000,1,t,0x4dbf,0,100));
 return 1;
}
static int as_approach(gpu_v1_context *c,unsigned t){
 int u=(int)(t-as_keys[7]),r=as_ease(27,112,u,1925),x=as_ease(268,200,u,1925),y=as_ease(116,170,u,1925);
 AS_TRY(as_ring(c,x,y,r+2,r+2,0,2,t,0x3fda,0,120));
 AS_TRY(as_planet(c,x,y,r,ASTRA_PLANET,(int)t/20,0xffff));
 AS_TRY(as_planet(c,73,71,12,ASTRA_MOON,(int)t/10,0xffff));
 if(u<1550)AS_TRY(as_ship(c,as_ease(105,198,u,1550),as_ease(159,184,u,1550),as_ease(62,19,u,1550),32000,as_sin((int)t*11)/7,9000,0,t));
 return 1;
}
static int as_landing(gpu_v1_context *c,unsigned t,unsigned k){
 int u=(int)(t-as_keys[8]),scale=as_ease(68,29,u,1375),y=as_ease(82,190,u,1375);
 // The ship settles over a projected landing ring; spores rise around it.
 if(k==8){AS_TRY(as_ring(c,200,195,35,7,0,1,t,0x4fdb,0,90));AS_TRY(as_ship(c,200+as_sin((int)t*13)*5/16384,y,scale,32768,as_sin((int)t*10)/18,15000,0,t));}
 else{AS_TRY(as_ring(c,200,194,30,5,0,1,t,0x4fda,0,65));AS_TRY(as_ship(c,200,187,29,32768,0,15000,0,t));}
 // Living light-ribbons above the vegetation, individually animated leaves.
 for(int i=0;i<16;++i){int x=15+i*25,y0=210-i%3*8,bend=as_sin((int)t*33+i*2100)*8/16384;
  AS_TRY(as_material(c,i&1?0x4ed6:0xa39e,85,GPU_V1_ADDITIVE));
  AS_TRY(as_tri(c,x,y0,x+bend-7,y0-13-i%4*5,x+bend+3,y0-21-i%4*5,100));}
 return 1;
}
// The distant stars are drawn *before* the opaque geometry. Native overlay
// sprites would incorrectly shine through planets and the event horizon.
static int as_stars(gpu_v1_context *c,unsigned t,unsigned k){
 for(unsigned i=0;i<100;++i){unsigned h=as_hash(i+7123);int speed=k==3?13:k==6?3:1;
  int z=60+(int)((h/17+1200-(t*(unsigned)speed)%1200)%1200),xx=(int)(h%1800)-900,yy=(int)((h>>12)%1000)-500;
  int x=200+xx*130/z,y=120+yy*130/z;if(x<0||x>=400||y<18||y>=222)continue;
  unsigned color=i%3==0?0x6b9d:0x9e59;
  AS_TRY(gpu_v1_clear(c,1,color,0,x,y,z<240?2:1,1));
  if(k==3){AS_TRY(as_material(c,0x6dbf,145,GPU_V1_ADDITIVE));AS_TRY(as_line(c,x,y,x+(x-200)*30/z,y+(y-120)*30/z,1,60000));}
 }return 1;
}
static int astra_render(gpu_v1_context *c,unsigned t,unsigned page){
 if(t>=ASTRA_FRAMES||page>1)return 0;
 unsigned k=as_chapter(t);
 gpu_target dst={GPU_PAGE_ADDR(page),GPU_PAGE_ADDR(2),400,240,800,800};
 AS_TRY(gpu_v1_target(c,&dst));AS_TRY(gpu_v1_scissor(c,0,0,400,240));
 AS_TRY(gpu_v1_clear(c,3,0,65535,0,0,400,240));
 AS_TRY(gpu_v1_scissor(c,0,18,400,204));
 if(k>=8){gpu_target bg={ASTRA_VALLEY,0,800,400,1600,1600};
  int u=as_clamp((int)t-(int)as_keys[8],0,2200),sy=as_ease(0,178,u,2200),sx=as_ease(185,235,u,2200);
  AS_TRY(gpu_v1_copy(c,&bg,sx,sy,0,18,400,204));
 }else if(k==3||k==6){
  for(int y=18;y<222;y+=12)AS_TRY(gpu_v1_clear(c,1,as_color(1,1+(y-18)/38,5+(y-18)/20),0,0,y,400,12));
 }else{gpu_target bg={ASTRA_COSMOS,0,1024,352,2048,2048};
  int sx=as_clamp((int)t*600/(int)as_keys[8]+as_sin((int)t*5)*14/16384,0,624),sy=48+as_cos((int)t*7)*20/16384;
  if(k==1)sx=as_ease(0,205,(int)t-(int)as_keys[1],1925);
  AS_TRY(gpu_v1_copy(c,&bg,sx,sy,0,18,400,204));
 }
 if(k<8)AS_TRY(as_stars(c,t,k));
 switch(k){case 0:case 5:AS_TRY(as_solar(c,t,k));break;case 1:AS_TRY(as_galaxies(c,t));break;
 case 2:AS_TRY(as_blackhole(c,t));break;case 3:AS_TRY(as_wormhole(c,t,0));break;
 case 4:AS_TRY(as_battle(c,t));break;case 6:AS_TRY(as_multiverse(c,t));break;
 case 7:AS_TRY(as_approach(c,t));break;default:AS_TRY(as_landing(c,t,k));break;}
 return 1;
}
static void astra_layers(unsigned t,gpu_layer layers[16],gpu_sprite sprites[64],astra_info *info){
 unsigned k=as_chapter(t);int u=(int)(t-as_keys[k]),left=(int)(as_keys[k+1]-t);
 memset(layers,0,16*sizeof(*layers));memset(sprites,0,64*sizeof(*sprites));
 unsigned hud=ASTRA_HUD0+k*64000U;
 layers[10]=gpu_make_layer(hud,800,800,80,0,0,800,36,0,0,GPU_LAYER_ENABLE|GPU_LAYER_KEY_ZERO);
 layers[11]=gpu_make_layer(hud,800,800,80,0,444,800,36,0,44,GPU_LAYER_ENABLE|GPU_LAYER_KEY_ZERO);
 unsigned progress=1+t*764/ASTRA_FRAMES;
 layers[12]=gpu_make_layer(ASTRA_PROGRESS,800,800,2,18,439,progress,2,0,0,GPU_LAYER_ENABLE);
 if(t<440||t>=15950){unsigned base=t<440?ASTRA_TITLE:ASTRA_FINISH;
  layers[13]=gpu_make_layer(base,640,640,128,80,t<440?91:98,640,128,0,0,GPU_LAYER_ENABLE|GPU_LAYER_KEY_ZERO);}
 unsigned count=0;
 for(unsigned i=0;k>=8&&i<56;++i){unsigned h=as_hash(i+7123);int x,y,kind;
  if(k>=8){x=(int)(h%790)+as_sin((int)t*11+(int)i*777)*17/16384;
   y=52+(int)((h/800+t*(1+i%2)/3)%380);kind=i%2?3:4;}
  else{int speed=k==3?11:k==6?3:1,z=60+(int)((h/17+1200-(t*(unsigned)speed)%1200)%1200);
   int xx=(int)(h%1800)-900,yy=(int)((h>>12)%1000)-500;
   x=400+xx*260/z;y=240+yy*260/z;kind=k==4?2:k==3?3:i%3==0?1:0;}
  if(x<-10||x>=810||y<42||y>=436)continue;
  sprites[count++]=gpu_make_sprite(ASTRA_PARTICLES+(unsigned)kind*1024,x-16,y-16,32,32,8,GPU_SPRITE_ENABLE);
 }
 // Cinematic shutter on each cut (0.36 s either side). The last chapter
 // fades to black at 300 s before the next voyage starts, still clock-driven.
 int gate=0;if(u<20)gate=(20-u)*240/20;if(left<20)gate=(20-left)*240/20;
 if(gate){layers[14]=gpu_make_layer(ASTRA_BLACK,800,800,480,0,0,800,(unsigned)gate,0,0,GPU_LAYER_ENABLE);
  layers[15]=gpu_make_layer(ASTRA_BLACK,800,800,480,0,480-gate,800,(unsigned)gate,0,0,GPU_LAYER_ENABLE);}
 *info=(astra_info){t,k,count,k==4?7U:0U};
}
#undef AS_TRY
#endif
