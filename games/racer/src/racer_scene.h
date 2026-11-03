#ifndef CONSOLE_RACER_SCENE_H
#define CONSOLE_RACER_SCENE_H
// Portable, deterministic game model + command generation. No MMIO or clocks.
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include "gpu.h"
enum { R_LEFT=1,R_RIGHT=2,R_ACCEL=4,R_BRAKE=8,R_START=16 };
enum { RC_BLACK=1,RC_WHITE,RC_ROAD,RC_ROAD2,RC_GRASS,RC_GRASS2,RC_RED,
       RC_DARKRED,RC_BLUE,RC_GLASS,RC_CHROME,RC_TIRE,RC_TREE,RC_LEAF,
       RC_TRUNK,RC_YELLOW,RC_MOUNTAIN,RC_MOUNTAIN2,RC_SHADOW,RC_ORANGE };
#define RACE_ATLAS 8
#define RACE_FINISH 60000
#define RACE_OBJECTS 5
#define RACE_COMMANDS 512
// Distance in decimetres, velocity in dm/s, lateral coordinate in cm/10.
// Model advances exactly 20 ms per step, independent of display frame rate.
typedef struct {
    int distance,speed,x,steer,phase,previous_keys,crash_ticks,hits;
    int time_ticks,travel_remainder,traffic_remainder,steer_remainder,curve_remainder;
    int traffic[RACE_OBJECTS];
} racer_state;
static int race_abs(int x){return x<0?-x:x;}
static int race_clamp(int v,int a,int b){return v<a?a:v>b?b:v;}
static void racer_reset(racer_state *s)
{
    memset(s,0,sizeof(*s));s->x=45;
    for(int i=0;i<RACE_OBJECTS;++i)s->traffic[i]=450+i*510;
}
// Smooth periodic road displacement; bounded integer parabolas, no floats.
static int race_wave(int z)
{
    int t=z%12000;if(t<0)t+=12000;
    int sign=t<6000?1:-1;t%=6000;
    return sign*(t*(6000-t)/18000);
}
static int race_center(int position,int z)
{
    int slope= race_wave(position+100)-race_wave(position);
    return race_wave(position+z)-race_wave(position)-slope*z/100;
}
static void racer_step(racer_state *s,unsigned keys)
{
    int start=(keys&R_START) && !(s->previous_keys&R_START);
    s->previous_keys=keys;
    if(start){racer_reset(s);s->previous_keys=keys;s->phase=1;}
    if(s->phase!=1)return;
    ++s->time_ticks;
    if(s->crash_ticks)--s->crash_ticks;
    int accel=(keys&R_ACCEL)?2:-1;
    if(keys&R_BRAKE)accel=-7;
    if(race_abs(s->x)>91)accel-=5;
    if(s->crash_ticks)accel=-4;
    s->speed=race_clamp(s->speed+accel,0,500); // 180 km/h
    int direction=!!(keys&R_RIGHT)-!!(keys&R_LEFT);
    s->steer=direction;
    s->steer_remainder+=direction*(25+s->speed/3);
    s->x+=s->steer_remainder/50;s->steer_remainder%=50;
    // Tangential inertia in bends: the driver must follow the road.
    int bend=race_wave(s->distance+200)-2*race_wave(s->distance)+race_wave(s->distance-200);
    s->curve_remainder-=bend*s->speed*s->speed/120000;
    s->x+=s->curve_remainder/50;s->curve_remainder%=50;
    s->x=race_clamp(s->x,-160,160);
    s->travel_remainder+=s->speed;
    int travel=s->travel_remainder/50;s->travel_remainder%=50;
    s->distance+=travel;
    s->traffic_remainder+=220;
    int advance=travel+s->traffic_remainder/50;s->traffic_remainder%=50;
    for(int i=0;i<RACE_OBJECTS;++i) {
        int old=s->traffic[i];s->traffic[i]-=advance;
        // Swept longitudinal collision: cannot skip a car between steps.
        if(!s->crash_ticks && old>65 && s->traffic[i]<=105 && race_abs(s->x+45)<32) {
            ++s->hits;s->crash_ticks=65;s->speed/=4;
        }
        if(s->traffic[i]<-80)s->traffic[i]+=2700;
    }
    if(s->distance>=RACE_FINISH){s->phase=2;s->speed=0;}
}
static unsigned racer_palette(unsigned i)
{
    static const uint32_t colors[]={0x000000,0x102039,0xfff4d7,0x555d69,0x505865,
        0x568839,0x609440,0xf24738,0x972933,0x288fe0,0x96d9e9,0xc8dce0,
        0x18232b,0x285a40,0x3d8350,0x755337,0xffdb69,0x69939a,0x88b1b5,
        0x344d38,0xf89340};
    unsigned rgb=i<sizeof(colors)/sizeof(colors[0])?colors[i]:0;
    if(i>=64 && i<128){unsigned t=i-64;rgb=((40+t*80/63)<<16)|((125+t*73/63)<<8)|(187+t*42/63);}
    return (((rgb>>16)*63/255)<<12)|((((rgb>>8)&255)*63/255)<<6)|((rgb&255)*63/255);
}
// Original procedural pixel art, stored in DDR rather than the 64 KiB ITCM.
// Tiles: player rear, two opposing fronts, pine tree, roadside bollard.
static unsigned racer_asset(int tile,int x,int y)
{
    int dx=race_abs(x-32);
    if(tile==3) {
        if(y>=102 && y<125 && dx<4)return RC_TRUNK;
        if(y>8 && y<112 && dx < ((y-8)%32)/2+9+(y/32)*3)
            return x<30?RC_TREE:RC_LEAF;
        return 0;
    }
    if(tile==4) {
        if(y>28 && y<64 && dx<5)return y<40?RC_RED:RC_WHITE;
        return 0;
    }
    if(y>=57 && y<62 && dx<31)return RC_SHADOW;
    if(y>=28 && y<58 && dx>=24 && dx<30)return RC_TIRE;
    if(y<8 || y>=58 || dx>(y<28?17+(y-8)/2:27))return 0;
    unsigned body=tile==0?RC_RED:tile==1?RC_BLUE:RC_YELLOW;
    if(y<12)return RC_CHROME;
    if(y<28 && dx<17) return y<15 || x<19 ? RC_GLASS:RC_BLACK;
    if(dx>23)return tile==0?RC_DARKRED:RC_CHROME;
    if(y>39 && y<47 && dx>15)return tile==0?RC_YELLOW:RC_WHITE;
    if(y>48 && y<53)return RC_BLACK;
    if(y>=54)return RC_CHROME;
    if(tile==0 && dx<2 && y>28)return RC_WHITE;
    if(x<12 || (y==31 && dx<23))return RC_WHITE;
    return body;
}
static void racer_make_atlas(uint8_t *atlas)
{
    memset(atlas,0,800*480);
    for(int t=0;t<5;++t)for(int y=0;y<(t==3?128:64);++y)
        for(int x=0;x<64;++x)atlas[y*800+t*128+x]=racer_asset(t,x,y);
}
static gpu_command race_commands[RACE_COMMANDS];
static unsigned race_count,race_overflow,race_page;
// Default to the original, more expensive renderer to exercise GPU throughput.
static unsigned race_original=1;
static void race_emit(gpu_command c)
{
    if(race_count<RACE_COMMANDS)race_commands[race_count++]=c;else race_overflow=1;
}
static void race_rect(int x,int y,int w,int h,unsigned color)
{race_emit(gpu_make_command(GPU_FILL,race_page,0,x,y,w,h,0,0,color,0));}
static void race_tri(int ax,int ay,int bx,int by,int cx,int cy,unsigned c)
{race_emit(gpu_make_command(GPU_TRIANGLE,race_page,0,ax,ay,bx,by,cx,cy,c,0));}
static void race_quad(int cx0,int y0,int half0,int cx1,int y1,int half1,unsigned c)
{
    race_tri(cx0-half0,y0,cx0+half0,y0,cx1+half1,y1,c);
    race_tri(cx0-half0,y0,cx1+half1,y1,cx1-half1,y1,c);
}
static void race_text(int x,int y,unsigned color,unsigned scale,const char *text)
{
    while(*text){
        gpu_command c=gpu_make_command(GPU_TEXT,race_page,0,x,y,0,scale,0,0,color,0);
        unsigned n=0;while(n<16 && *text){c.words[4+n/4]|=(uint32_t)(uint8_t)*text++<<(8*(n%4));++n;}
        c.words[2]|=n<<16;race_emit(c);x+=(int)n*8*(int)scale;
    }
}
static void race_zoom(int tile,int x,int bottom,int w,int h)
{
    if(w<1 || h<1 || w>1500 || h>1500)return;
    race_emit(gpu_make_zoom(race_page,RACE_ATLAS,x-w/2,bottom-h,w,h,tile*128,0,64,tile==3?128:64));
}
typedef struct{int z,x,tile;} racer_object;
static void racer_background(unsigned page)
{
    race_count=race_overflow=0;race_page=page;
    race_emit(gpu_make_command(GPU_GRAD_V,page,0,0,0,800,165,0,0,64,127));
    // Periodic panorama: the two COPY commands wrap it without a seam.
    for(int i=-1;i<6;++i) {
        int x=i*200;
        race_tri(x-120,165,x+65,75+(i&1)*25,x+220,165,RC_MOUNTAIN2);
        race_tri(x-60,165,x+110,111+(i&1)*16,x+250,165,RC_MOUNTAIN);
    }
}
static void race_strip(int left0,int right0,int y0,int left1,int right1,int y1,unsigned c)
{
    race_tri(left0,y0,right0,y0,right1,y1,c);
    race_tri(left0,y0,right1,y1,left1,y1,c);
}
static void racer_build(const racer_state *s,unsigned page)
{
    race_count=race_overflow=0;race_page=page;
    if(race_original) {
        race_emit(gpu_make_command(GPU_GRAD_V,page,0,0,0,800,165,0,0,64,127));
        int pan=(race_wave(s->distance+100)-race_wave(s->distance))*3;
        for(int i=-1;i<6;++i) {
            int x=i*190-pan;
            race_tri(x-120,165,x+65,75+(i&1)*25,x+220,165,RC_MOUNTAIN2);
            race_tri(x-60,165,x+110,111+(i&1)*16,x+250,165,RC_MOUNTAIN);
        }
    } else {
    int pan=((race_wave(s->distance+100)-race_wave(s->distance))*3+800)%800;
    race_emit(gpu_make_command(GPU_COPY,page,9,0,0,800-pan,165,pan,0,0,0));
    if(pan)race_emit(gpu_make_command(GPU_COPY,page,9,800-pan,0,pan,165,0,0,0,0));
    }
    race_rect(0,160,800,10,RC_GRASS);
    // 32 trapezoids cover every scanline; geometry is projected in integer
    // arithmetic. Segment boundaries use the triangle top-left ownership rule.
    int far_y=165,far_z=4800;
    int far_c=400+(race_center(s->distance,far_z)-s->x)*240/far_z;
    int far_half=90*240/far_z;
    for(int i=1;i<=32;++i) {
        int near_y=165+(315*i*i)/(32*32);
        if(near_y<=far_y)continue;
        int z=24000/(near_y-160);
        int center=400+(race_center(s->distance,z)-s->x)*240/z;
        int half=90*240/z;
        unsigned stripe=((s->distance+z)/180)&1;
        race_rect(0,far_y,800,near_y-far_y,stripe?RC_GRASS:RC_GRASS2);
        if(race_original) {
            race_quad(far_c,far_y,far_half+far_half/12+1,center,near_y,half+half/12+1,stripe?RC_WHITE:RC_RED);
        } else {
        int outer0=far_half+far_half/12+1,outer1=half+half/12+1;
        unsigned shoulder=stripe?RC_WHITE:RC_RED;
        race_strip(far_c-outer0,far_c-far_half,far_y,center-outer1,center-half,near_y,shoulder);
        race_strip(far_c+far_half,far_c+outer0,far_y,center+half,center+outer1,near_y,shoulder);
        }
        race_quad(far_c,far_y,far_half,center,near_y,half,stripe?RC_ROAD:RC_ROAD2);
        if(((s->distance+z)/100)%3!=0)
            race_quad(far_c,far_y,far_half/55+1,center,near_y,half/55+1,RC_WHITE);
        far_y=near_y;far_z=z;far_c=center;far_half=half;
    }
    racer_object objects[40];int count=0;
    for(int i=0;i<16;++i) {
        int z=110+i*185-(s->distance%185);
        if(z<70)continue;
        objects[count++]=(racer_object){z,-145,3};
        objects[count++]=(racer_object){z+60,145,(i%3)?3:4};
    }
    for(int i=0;i<RACE_OBJECTS;++i)if(s->traffic[i]>65 && s->traffic[i]<3000)
        objects[count++]=(racer_object){s->traffic[i],-45,1+(i&1)};
    // Painter order across both traffic and scenery, no per-pixel Z-buffer.
    for(int i=1;i<count;++i){racer_object v=objects[i];int j=i;while(j>0 && objects[j-1].z<v.z){objects[j]=objects[j-1];--j;}objects[j]=v;}
    for(int i=0;i<count;++i){racer_object o=objects[i];
        int x=400+(race_center(s->distance,o.z)+o.x-s->x)*240/o.z;
        int y=160+24000/o.z;
        int w=(o.tile==3?70:o.tile==4?22:40)*240/o.z;
        int h=(o.tile==3?125:o.tile==4?45:36)*240/o.z;
        race_zoom(o.tile,x,y,w,h);
    }
    if(!s->crash_ticks || (s->crash_ticks&4))race_zoom(0,400+s->steer*6,473,146,122);
    race_rect(12,12,222,59,RC_BLACK);
    race_text(24,20,RC_WHITE,1,"MEGA COAST / 6 KM");
    char label[40];snprintf(label,sizeof(label),"%03d KM/H",s->speed*36/100);
    race_text(24,40,RC_YELLOW,2,label);
    race_rect(557,12,231,59,RC_BLACK);
    snprintf(label,sizeof(label),"%02d:%02d   CHOCS %d",s->time_ticks/3000,(s->time_ticks/50)%60,s->hits%100);
    race_text(569,22,RC_WHITE,1,label);
    snprintf(label,sizeof(label),"%04d / 6000 M",s->distance/10);
    race_text(569,44,RC_WHITE,1,label);
    race_rect(15,78,217,4,RC_BLACK);race_rect(15,78,race_clamp(s->distance*217/RACE_FINISH,0,217),4,RC_YELLOW);
    if(s->phase!=1){
        race_rect(112,206,576,115,RC_BLACK);
        race_text(160,222,RC_YELLOW,2,s->phase==2?"ARRIVEE !":"MEGA COAST RACER");
        race_text(160,266,RC_WHITE,1,"ENTREE : DEPART / RECOMMENCER");
        race_text(160,290,RC_WHITE,1,"FLECHES : CONDUIRE   ESPACE : FREINER");
    }
}
#endif
