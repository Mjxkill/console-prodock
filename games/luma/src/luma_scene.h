// Luma: deterministic autonomous choreography, shared by AE350 and host.
#ifndef LUMA_SCENE_H
#define LUMA_SCENE_H
#include <stdint.h>
#include <string.h>
#include "gpu.h"
#include "luma_assets.h"
#define LUMA_FX_START 5120U
#define LUMA_FX_FRAMES 3200U
#define LUMA_FRAMES (LUMA_FX_START+LUMA_FX_FRAMES)

typedef struct { int frame,x,y; } luma_key;
typedef struct { int x,y,frame,kind; } luma_actor;
typedef struct { unsigned frame,chapter,sprites,light; int camera_x,camera_y,hero_x,hero_y; } luma_info;
static int luma_clamp(int v,int lo,int hi){return v<lo?lo:v>hi?hi:v;}
static int luma_abs(int v){return v<0?-v:v;}
static int luma_wave(unsigned t,unsigned period,int amp){int v=(int)(t%period)*4*amp/(int)period;return v<amp?v:v<3*amp?2*amp-v:v-4*amp;}
static const luma_key luma_route[]={
 {0,410,912},{200,410,912},{490,425,805},{700,345,709},{925,350,622},
 {1150,439,585},{1350,540,557},{1470,565,511},{1810,867,505},{2070,998,558},
 {2280,1040,558},{2360,1040,558},{2560,1127,582},{2700,1127,582},
 {2910,1180,515},{3000,1180,515},{3240,1334,550},{3440,1370,449},
 {3660,1318,373},{3830,1291,371},{3910,1250,402},{4030,1290,365},
 {4150,1290,365},{4440,1280,285},{4710,1280,228},{5010,1280,228},
 {5599,1280,228}};
static void luma_position(unsigned t,int *x,int *y,int *direction,int *moving)
{
 unsigned k=0;while(k+1<sizeof(luma_route)/sizeof(*luma_route) && t>(unsigned)luma_route[k+1].frame)++k;
 const luma_key *a=&luma_route[k],*b=k+1<sizeof(luma_route)/sizeof(*luma_route)?a+1:a;
 int n=(int)t-a->frame,d=b->frame-a->frame;
 *x=a->x+(d?(b->x-a->x)*n/d:0);*y=a->y+(d?(b->y-a->y)*n/d:0);
 int dx=b->x-a->x,dy=b->y-a->y;*moving=dx||dy;
 *direction=luma_abs(dx)>luma_abs(dy)?(dx>0?1:3):(dy>0?0:2);
 if(!*moving)*direction=t<220?2:t>4400?2:1;
}
static void luma_fx(gpu_sprite sprites[64],unsigned *count,unsigned effect,int x,int y,unsigned priority)
{
 if(*count<64 && x>-32 && x<800 && y>-32 && y<480)
  sprites[(*count)++]=gpu_make_sprite(LUMA_EFFECTS+effect*1024UL,x,y,32,32,priority,GPU_SPRITE_ENABLE);
}
static void luma_character(gpu_sprite sprites[64],unsigned *count,const luma_actor *a,int cx,int cy)
{
 // Sort by feet; all four quadrants have one priority and keep sheet alignment.
 int x=a->x-cx-32,y=a->y-cy-54;
 unsigned long base=(a->kind?LUMA_ENEMIES:LUMA_HERO)+a->frame*4096UL;
 for(int row=0;row<2;++row)for(int col=0;col<2;++col)
  if(*count<64 && x+col*32>-32 && x+col*32<800 && y+row*32>-32 && y+row*32<480)
   sprites[(*count)++]=gpu_make_sprite(base+(row*2+col)*1024UL,x+col*32,y+row*32,32,32,5,GPU_SPRITE_ENABLE);
}
static gpu_layer luma_panel(unsigned long address,int width,int height,int x,int y)
{return gpu_make_layer(address,width,width,height,x,y,width,height,0,0,GPU_LAYER_ENABLE|GPU_LAYER_KEY_ZERO);}
static void luma_scene(unsigned tick,gpu_layer layers[16],gpu_sprite sprites[64],luma_info *info)
{
 unsigned t=tick%LUMA_FRAMES;int hx,hy,dir,moving;
 memset(layers,0,sizeof(gpu_layer)*16);memset(sprites,0,sizeof(gpu_sprite)*64);
 luma_position(t,&hx,&hy,&dir,&moving);
 int cx=luma_clamp(hx-365,0,736),cy=luma_clamp(hy-290,0,544);
 unsigned count=0,chapter=t<1970?0:t<3280?1:t<4320?2:t<5160?3:4;
 layers[0]=gpu_make_layer(LUMA_WORLD,1536,1536,1024,0,0,800,480,cx,cy,GPU_LAYER_ENABLE);
 luma_actor actors[5];unsigned actor_count=0;
 unsigned attack=0;
 const int hits[4]={2300,2620,2950,4110};
 for(unsigned i=0;i<4;++i)if((int)t>=hits[i]-22&&(int)t<hits[i]+20)attack=1;
 if(attack)dir=t>4000?2:1;
 int hero_frame=dir*4+(attack?3:moving?1+(t/10)%2:0);
 actors[actor_count++]=(luma_actor){hx,hy,hero_frame,0};
 const int ex[3]={1082,1170,1222},ey[3]={558,582,515};
 for(unsigned i=0;i<3;++i){
  int dt=(int)t-hits[i];if(dt>80)continue;
  int x=ex[i]+luma_wave(t+i*31,180,8),y=ey[i]+luma_wave(t+i*41,200,5);
  unsigned pose=(t/12+i)%3;
  if(dt>-70 && dt<0){x-=luma_clamp(70+dt,0,70)/5;pose=3;}
  if(dt>=0){pose=dt<18?6:7;x+=dt/5;}
  actors[actor_count++]=(luma_actor){x,y-(pose==1?3:0),(int)pose,1};
 }
 if(t<4270){int gframe=8+(t/18)%3,gy=320;
  if(t<3640)gframe=8;
  else if(t<3810)gy+=((int)t-3640)/8;
  else gy=341;
  if(t>=3830&&t<3910)gframe=11;
  if(t>=4110)gframe=t<4140?14:15;
  actors[actor_count++]=(luma_actor){1290,gy,gframe,1};
 }
 for(unsigned i=0;i<actor_count;++i)for(unsigned j=i+1;j<actor_count;++j)
  if(actors[j].y<actors[i].y){luma_actor a=actors[i];actors[i]=actors[j];actors[j]=a;}
 for(unsigned i=0;i<actor_count;++i)luma_fx(sprites,&count,0,actors[i].x-cx-16,actors[i].y-cy-17,3);
 for(unsigned i=0;i<actor_count;++i)luma_character(sprites,&count,&actors[i],cx,cy);
 // Screen-independent ambient motion: reflected ripples, floating leaves, fireflies.
 for(unsigned i=0;i<6;++i){int y=125+(int)i*143;int x=778+luma_wave(t/3+i*37,240,34);
  luma_fx(sprites,&count,5+(t/16+i)%4,x-cx-16,y-cy-16,2);}
 for(unsigned i=0;i<8;++i){int x=150+(i*193)%1280+luma_wave(t+i*73,350,16);
  int y=220+(i*117)%660+luma_wave(t+i*53,420,12);
  luma_fx(sprites,&count,1+(t/19+i)%3,x-cx-16,y-cy-16,7);}
 for(unsigned i=0;i<3;++i){int x=(int)((t/2+i*287)%920)-60,y=(int)((t/4+i*191)%580)-50;
  luma_fx(sprites,&count,14,x,y,8);}
 // Four localized impact bursts, then the shards float toward the hero.
 static const int vx[8]={4,3,0,-3,-4,-3,0,3},vy[8]={0,3,4,3,0,-3,-4,-3};
 for(unsigned hit=0;hit<4;++hit){int dt=(int)t-hits[hit];
  if(dt>=0 && dt<65){int x=hit<3?ex[hit]:1290,y=hit<3?ey[hit]:326;
   for(unsigned i=0;i<8;++i)luma_fx(sprites,&count,9+(unsigned)dt/18%4,x-cx-16+vx[i]*dt/5,y-cy-34+vy[i]*dt/5,9);}
  else if(dt>=65&&dt<155){int x=hit<3?ex[hit]:1290,y=hit<3?ey[hit]:326,p=dt-65;
   luma_fx(sprites,&count,13,x+(hx-x)*p/90-cx-16,y+(hy-35-y)*p/90-cy-30,9);}
 }
 if(t>4690){unsigned age=t-4690;
  for(unsigned i=0;i<16;++i){unsigned phase=(age+i*19)%240;unsigned oct=(phase/30)%8,frac=phase%30;
   int radius=t<4900?22+(int)age/5:64+luma_wave(age,170,12);
   int x=(vx[oct]*(int)(30-frac)+vx[(oct+1)%8]*(int)frac)*radius/120;
   int y=(vy[oct]*(int)(30-frac)+vy[(oct+1)%8]*(int)frac)*radius/160;
   luma_fx(sprites,&count,1+(age/9+i)%4,1281+x-cx-16,158+y-cy-16,10);}
 }
 layers[12]=luma_panel(LUMA_HUD,272,48,16,14);
 layers[12].words[6]=GPU_LAYER_ENABLE; // opaque, palette index zero is allowed
 layers[13]=luma_panel(LUMA_BADGE,144,30,640,14);
 const unsigned long captions[]={LUMA_CHAPTER0,LUMA_CHAPTER1,LUMA_CHAPTER2,LUMA_CHAPTER3,LUMA_CHAPTER4};
 layers[14]=luma_panel(captions[chapter],576,56,112,410);
 if(t<180)layers[15]=luma_panel(LUMA_TITLE,440,122,180,172);
 unsigned light=t<60?t*256/60:256;
 *info=(luma_info){t,chapter,count,light,cx,cy,hx,hy};
}
// Palette fade and localized water shimmer; no changes to source pixels.
static uint32_t luma_color(uint32_t original,unsigned index,unsigned frame,unsigned light)
{
 unsigned r=(original>>12)&63,g=(original>>6)&63,b=original&63;
 if(index>=224&&index<240){int wave=luma_wave(frame+index*8,128,2);g=(unsigned)luma_clamp((int)g+wave,0,63);b=(unsigned)luma_clamp((int)b+wave,0,63);}
 r=r*light/256;g=g*light/256;b=b*light/256;return r<<12|g<<6|b;
}
#endif
