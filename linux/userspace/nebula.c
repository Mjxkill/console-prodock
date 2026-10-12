// SPDX-License-Identifier: GPL-2.0-or-later
/* NEBULA / Rift Raiders: a native Linux game for the Pro Dock GPU.
 * CPU: input, physics, AI, collisions, descriptor/map preparation.
 * FPGA: RGB565 copies, additive raster effects, cached sprites, layers,
 * tile HUD, clipping, x2 scanout and atomic vblank presentation.
 */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <math.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>
#include "prodock-uapi.h"
#include "nebula-assets.h"

#define MAP_BYTES (14U*1024*1024)
#define BASE 0x00800000U
#define ENEMIES 12
#define SHOTS 16
#define HOSTILE 22
#define EFFECTS 20
#define PI 3.14159265358979323846f
typedef struct { uint32_t offset,bytes,w,h,pitch,kind; } Resource;
typedef struct { float x,y,vx,vy,age,fire,home;int live,hp,kind; } Enemy;
typedef struct { float x,y,vx,vy,age;int live; } Shot;
typedef struct { float x,y,vx,vy,age,life;int live,kind; } Effect;
typedef struct {
    float time,stage_time,spawn,fire,invincible,nova,shake,combo_time,end_time;
    float x,y,vx,vy,tx,ty,bx,by,bfire,bentry;
    int health,bombs,weapon,score,kills,combo,sector,boss_hp,boss_max;
    int phase,paused,finished,won,demo,escape;
    uint32_t rng;
    unsigned spawned,defeated,shots_fired,damage_taken,novas;
    Enemy enemies[ENEMIES];Shot shots[SHOTS],hostile[HOSTILE];Effect fx[EFFECTS];
} Game;
typedef struct {
    int fd,display,failed,scale,host;
    uint8_t *mem;uint32_t used,assets,stars[2][2],atlas[2],maps[2][3];
    Resource art[NEBULA_RESOURCE_COUNT];
    struct prodock_batch batch;
    struct prodock_scene scene;
    uint32_t capture_commands[512][8];unsigned capture_count;
    unsigned sprites,max_sprites,max_layers,fx_dropped,frames,commands;
    struct prodock_display_info initial,last;
} Video;
static volatile sig_atomic_t stopping;
static void stop(int sig) { (void)sig;stopping=1; }
static double now(void) { struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9; }
static float clampf(float x,float lo,float hi) { return x<lo?lo:x>hi?hi:x; }
static uint32_t xy(int x,int y) { return ((uint32_t)(uint16_t)x<<16)|(uint16_t)y; }
static uint32_t yx(int x,int y) { return ((uint32_t)(uint16_t)y<<16)|(uint16_t)x; }
static unsigned random_u(Game *g) { uint32_t x=g->rng;x^=x<<13;x^=x>>17;x^=x<<5;return g->rng=x; }
static float random_f(Game *g) { return (random_u(g)&65535)/65535.f; }
static int checked(Video *v,unsigned long op,void *p)
{
    if(v->host)return 0;
    if(ioctl(op==PRODOCK_DISPLAY_INFO || op==PRODOCK_LAYOUT?v->display:v->fd,op,p)) {
        perror("NEBULA GPU");v->failed=1;return -1;
    }
    return 0;
}
static uint32_t allocate(Video *v,unsigned bytes)
{
    unsigned offset=(v->used+31)&~31U;
    if(offset>MAP_BYTES || bytes>MAP_BYTES-offset) { fprintf(stderr,"NEBULA memory budget\n");v->failed=1;return BASE; }
    v->used=offset+bytes;return BASE+offset;
}
static void *memory(Video *v,uint32_t addr) { return v->mem+(addr-BASE); }
static void flush(Video *v)
{
    if(!v->batch.count || v->failed)return;
    checked(v,PRODOCK_SUBMIT,&v->batch);v->commands+=v->batch.count;
    v->batch=(struct prodock_batch){0};
}
static void emit(Video *v,uint32_t a,uint32_t b,uint32_t c,uint32_t d,uint32_t e,uint32_t f,uint32_t g,uint32_t h)
{
    uint32_t words[8]={a,b,c,d,e,f,g,h};
    if(v->batch.count==PRODOCK_BATCH_MAX)flush(v);
    if(v->failed)return;
    memcpy(v->batch.commands[v->batch.count++],words,sizeof(words));
    if(v->host) {
        if(v->capture_count>=512) { v->failed=1;return; }
        memcpy(v->capture_commands[v->capture_count++],words,sizeof(words));
    }
}
static uint32_t crc32(const uint8_t *p,size_t n)
{
    uint32_t c=~0U;
    while(n--) { c^=*p++;for(unsigned k=0;k<8;++k)c=(c>>1)^(0xedb88320U&-(c&1U)); }
    return ~c;
}
static int assets(Video *v,const char *path)
{
    FILE *f=fopen(path,"rb");if(!f) { perror(path);return -1; }
    uint8_t *data=malloc(NEBULA_ASSET_BYTES);
    if(!data) { fclose(f);return -1; }
    size_t n=fread(data,1,NEBULA_ASSET_BYTES,f);int extra=fgetc(f);fclose(f);
    uint32_t header[6]={0};if(n>=sizeof(header))memcpy(header,data,sizeof(header));
    if(n!=NEBULA_ASSET_BYTES || extra!=EOF || header[0]!=0x3142454e || header[1]!=1 ||
       header[2]!=n || header[3]!=NEBULA_ASSET_CRC || header[4]!=NEBULA_RESOURCE_COUNT || header[5] ||
       crc32(data+64,n-64)!=NEBULA_ASSET_CRC) { fprintf(stderr,"NEBULA asset CRC/header\n");free(data);return -1; }
    v->assets=allocate(v,(unsigned)n);if(v->failed) { free(data);return -1; }
    for(unsigned i=0;i<NEBULA_RESOURCE_COUNT;++i) {
        memcpy(&v->art[i],data+1088+i*24,24);Resource *r=&v->art[i];
        if(r->offset<4096 || (r->offset&31) || r->offset>n || r->bytes>n-r->offset) { free(data);return -1; }
    }
    memcpy(memory(v,v->assets),data,n);
    struct prodock_palette pal;memcpy(pal.rgb,data+64,sizeof(pal.rgb));free(data);
    if(checked(v,PRODOCK_PALETTE,&pal))return -1;
    const uint8_t *font=memory(v,v->assets+v->art[NA_FONT].offset);
    static const uint8_t inks[8]={227,225,228,229,231,233,235,224};
    for(unsigned s=0;s<2;++s) {
        unsigned scale=s+1,tile=8*scale;
        v->atlas[s]=allocate(v,8192*tile*tile);
        if(v->failed)return -1;
        uint8_t *atlas=memory(v,v->atlas[s]);memset(atlas,0,8192*tile*tile);
        for(unsigned ink=0;ink<8;++ink)for(unsigned ch=0;ch<128;++ch)
            for(unsigned y=0;y<tile;++y)for(unsigned x=0;x<tile;++x)
                atlas[(ink*128+ch)*tile*tile+y*tile+x]=
                    font[ch*8+y/scale]&(128U>>(x/scale))?inks[ink]:221;
        for(unsigned field=0;field<2;++field) {
            unsigned pitch=(400*scale+31)&~31U,height=512*scale;
            v->stars[field][s]=allocate(v,pitch*height*2);
            if(v->failed)return -1;
            uint8_t *pixels=memory(v,v->stars[field][s]);memset(pixels,0,pitch*height*2);
            Game seed={.rng=0xc0ffeeU+field*23467};
            for(unsigned i=0;i<75+field*35;++i) {
                unsigned x=random_u(&seed)%398,y=random_u(&seed)%508;
                unsigned length=field?2+random_u(&seed)%3:1;
                for(unsigned yy=0;yy<length*scale;++yy)for(unsigned xx=0;xx<scale;++xx)
                    pixels[(y*scale+yy)*pitch+x*scale+xx]=field?235:239;
            }
            memcpy(pixels+pitch*height,pixels,pitch*height);
        }
    }
    for(unsigned b=0;b<2;++b)for(unsigned part=0;part<3;++part) {
        v->maps[b][part]=allocate(v,64*4*2);if(v->failed)return -1;
        memset(memory(v,v->maps[b][part]),0,64*4*2);
    }
    return 0;
}
static void image_layer(Video *v,unsigned layer,unsigned art,int x,int y)
{
    Resource r=v->art[art];uint32_t *p=v->scene.layers[layer];
    p[0]=v->assets+r.offset;p[1]=yx(r.w,r.h);p[2]=yx(x,y);p[3]=yx(r.w,r.h);p[5]=r.pitch;p[6]=3;
}
static void sprite(Video *v,unsigned art,float x,float y,unsigned priority)
{
    Resource r=v->art[art];int xx=(int)lroundf(x*v->scale)-r.w/2,yy=(int)lroundf(y*v->scale)-r.h/2;
    if(xx>400*v->scale || yy>240*v->scale || xx+(int)r.w<=0 || yy+(int)r.h<=0)return;
    if(v->sprites>=64) { ++v->fx_dropped;return; }
    uint32_t *p=v->scene.sprites[v->sprites++];
    p[0]=v->assets+r.offset;p[1]=yx(xx,yy);p[2]=r.w|(r.h<<8)|(1U<<16)|(priority<<20);
}
static void label(uint16_t *map,int x,int y,unsigned ink,const char *text)
{
    for(;*text;++text,++x)if(x>=0 && x<50 && y>=0 && y<4)map[y*64+x]=(ink&7)*128+((unsigned char)*text&127);
}
static void tile_layer(Video *v,unsigned layer,uint32_t map,int y,unsigned rows)
{
    uint32_t *p=v->scene.layers[layer];p[0]=map;p[1]=v->atlas[v->scale-1];
    p[2]=yx(0,y*v->scale);p[3]=yx(400*v->scale,rows*8*v->scale);
    p[5]=6|(2<<4)|((v->scale-1)<<8);p[6]=7;
}
static void solid(Video *v,unsigned colour,int x,int y,unsigned w,unsigned h)
{ emit(v,28U<<24,1,colour,0,xy(x,y),xy(w,h),0,0); }
static void glow(Video *v,float x,float y,int radius,unsigned colour,unsigned alpha)
{
    if(radius<1)return;
    int left=(int)lroundf(x)-radius,top=(int)lroundf(y)-radius,size=radius*2;
    int32_t step=32*65536/size;
    int64_t u=-(int64_t)left*step+step/2,vv=-(int64_t)top*step+step/2;
    unsigned red=((colour>>11)&31)*256/31,green=((colour>>5)&63)*256/63,blue=(colour&31)*256/31;
    emit(v,25U<<24,33,alpha,0,red|(green<<9)|(blue<<18),0,0,0);
    emit(v,26U<<24,(uint32_t)u,(uint32_t)step,0,(uint32_t)((uint64_t)u>>32)&65535,0,0,0);
    emit(v,(26U<<24)|1,(uint32_t)vv,0,(uint32_t)step,(uint32_t)((uint64_t)vv>>32)&65535,0,0,0);
    emit(v,27U<<24,xy(left,top),xy(left+size,top),xy(left+size,top+size),0,0,0,0);
    emit(v,27U<<24,xy(left,top),xy(left+size,top+size),xy(left,top+size),0,0,0,0);
}
static void ring(Video *v,float x,float y,float radius,unsigned alpha)
{
    emit(v,25U<<24,32,alpha,0x6fff,256|(256<<9)|(256<<18),0,0,0);
    for(unsigned i=0;i<20;++i) {
        float a=i*PI*.1f,b=(i+1)*PI*.1f;
        uint32_t p=xy((int)lroundf(x+cosf(a)*radius),(int)lroundf(y+sinf(a)*radius));
        uint32_t q=xy((int)lroundf(x+cosf(b)*radius),(int)lroundf(y+sinf(b)*radius));
        uint32_t r=xy((int)lroundf(x+cosf(b)*(radius+2)),(int)lroundf(y+sinf(b)*(radius+2)));
        uint32_t s=xy((int)lroundf(x+cosf(a)*(radius+2)),(int)lroundf(y+sinf(a)*(radius+2)));
        emit(v,27U<<24,p,q,r,0,0,0,0);emit(v,27U<<24,p,r,s,0,0,0,0);
    }
}
static void reset_game(Game *g,int demo,int sector,int boss)
{
    *g=(Game){.x=200,.y=197,.tx=200,.ty=197,.health=5,.bombs=3,.weapon=1,.combo=1,
              .rng=0x31415926,.demo=demo,.sector=sector,.invincible=2,.bx=200,.by=-60};
    if(boss) { g->phase=1;g->boss_hp=g->boss_max=100+sector*30;g->stage_time=40; }
}
static void effect(Game *g,float x,float y,int kind)
{
    if(kind==2) {
        unsigned pickups=0;for(unsigned i=0;i<EFFECTS;++i)pickups+=g->fx[i].live && g->fx[i].kind==2;
        if(pickups>=4)return;
    }
    for(unsigned i=0;i<EFFECTS;++i)if(!g->fx[i].live) {
        float angle=random_f(g)*PI*2;
        g->fx[i]=(Effect){.live=1,.x=x,.y=y,.vx=cosf(angle)*22,.vy=sinf(angle)*22,
                         .life=kind==0?.65f:kind==1?.45f:6,.kind=kind};return;
    }
}
static void burst(Game *g,float x,float y)
{
    effect(g,x,y,0);
    for(unsigned n=0;n<3;++n) {
        /* Argument evaluation order differs between x86 and RISC-V GCC.
         * Sequence random draws so diagnostics replay the same scene. */
        float dy=(random_f(g)-.5f)*12;
        float dx=(random_f(g)-.5f)*12;
        effect(g,x+dx,y+dy,1);
    }
    g->shake=.18f;
}
static void shoot(Game *g,Shot *shots,unsigned count,float x,float y,float vx,float vy,int player)
{
    for(unsigned i=0;i<count;++i)if(!shots[i].live) {
        shots[i]=(Shot){.live=1,.x=x,.y=y,.vx=vx,.vy=vy};if(player)++g->shots_fired;return;
    }
}
static void defeat(Game *g,Enemy *e)
{
    e->live=0;++g->kills;++g->defeated;g->combo=g->combo_time>0?g->combo+1:1;
    if(g->combo>8)g->combo=8;
    g->combo_time=2.5f;g->score+=100*g->combo;burst(g,e->x,e->y);
    if(g->kills%5==0)effect(g,e->x,e->y,2);
    if(g->kills%12==0 && g->bombs<3)++g->bombs;
    if(g->kills>=8)g->weapon=2;
}
static void damage(Game *g)
{
    if(g->invincible>0 || g->finished)return;
    --g->health;++g->damage_taken;g->invincible=1.5f;g->shake=.35f;g->combo=1;
    burst(g,g->x,g->y);
    if(g->health<=0) { g->finished=1;g->end_time=0; }
}
static void nova(Game *g)
{
    if(!g->bombs || g->nova>0 || g->finished)return;
    --g->bombs;++g->novas;g->nova=.8f;g->invincible=1;g->shake=.3f;
    memset(g->hostile,0,sizeof(g->hostile));
    for(unsigned i=0;i<ENEMIES;++i)if(g->enemies[i].live)defeat(g,&g->enemies[i]);
    if(g->phase==1)g->boss_hp-=25;
}
static void key(Game *g,unsigned char ch)
{
    if(g->escape==1) { g->escape=(ch=='['||ch=='O')?2:0;return; }
    if(g->escape==2) {
        if(ch=='A')g->ty-=18;
        if(ch=='B')g->ty+=18;
        if(ch=='C')g->tx+=24;
        if(ch=='D')g->tx-=24;
        g->escape=0;return;
    }
    if(ch==27) { g->escape=1;return; }
    if(ch=='a'||ch=='A')g->tx-=24;
    if(ch=='d'||ch=='D')g->tx+=24;
    if(ch=='w'||ch=='W'||ch=='z'||ch=='Z')g->ty-=18;
    if(ch=='s'||ch=='S')g->ty+=18;
    if(ch=='q'||ch=='Q')stopping=1;
    if(ch=='p'||ch=='P')g->paused=!g->paused;
    if(ch==' ')nova(g);
    if((ch=='r'||ch=='R'||ch=='\n'||ch=='\r') && g->finished)reset_game(g,g->demo,0,0);
}
static void update(Game *g,float dt)
{
    if(g->paused)return;
    g->time+=dt;g->stage_time+=dt;
    g->invincible=fmaxf(0,g->invincible-dt);g->nova=fmaxf(0,g->nova-dt);g->shake=fmaxf(0,g->shake-dt);
    g->combo_time=fmaxf(0,g->combo_time-dt);
    if(g->combo_time<=0)g->combo=1;
    for(unsigned i=0;i<EFFECTS;++i)if(g->fx[i].live) {
        Effect *e=&g->fx[i];e->age+=dt;e->x+=e->vx*dt;e->y+=(e->kind==2?32:e->vy)*dt;
        if(e->age>=e->life || e->y>250)e->live=0;
        if(e->kind==2 && hypotf(e->x-g->x,e->y-g->y)<18) {
            e->live=0;if(g->health<5)++g->health;g->score+=250;g->invincible=.4f;
        }
    }
    if(g->finished) { g->end_time+=dt;if(g->demo && g->end_time>5)reset_game(g,1,0,0);return; }
    if(g->demo) {
        float target=200+130*sinf(g->time*.73f);
        if(g->phase==1)target=g->bx;
        else for(unsigned i=0;i<ENEMIES;++i)if(g->enemies[i].live && g->enemies[i].y>25) { target=g->enemies[i].x;break; }
        for(unsigned i=0;i<EFFECTS;++i)if(g->fx[i].live && g->fx[i].kind==2 &&
            g->fx[i].y>100 && g->health<5)target=g->fx[i].x;
        float best=1e30f,chosen=target;unsigned threats=0;
        /* Predict where hostile shots cross our altitude. Pick a reachable
         * safe lane instead of rapidly flipping direction for each bullet. */
        for(unsigned candidate=0;candidate<23;++candidate) {
            float x=24+candidate*16,cost=(x-target)*(x-target)*.0015f+(x-g->x)*(x-g->x)*.003f;
            for(unsigned i=0;i<HOSTILE;++i)if(g->hostile[i].live) {
                Shot *b=&g->hostile[i];float t=b->vy>1?(g->y-b->y)/b->vy:-1;
                if(t>-.08f && t<1.5f) {
                    float dx=(x-(b->x+b->vx*t))/18;
                    cost+=260*(1-fmaxf(0,t)/1.6f)/(1+dx*dx);
                    if(!candidate && t<.5f && fabsf(g->x-b->x-b->vx*t)<25)++threats;
                }
            }
            if(cost<best){best=cost;chosen=x;}
        }
        g->tx=clampf(chosen,24,376);g->ty=195+10*sinf(g->time*.42f);
        if(g->time>2.8f && g->health<=3 && g->bombs && threats && g->invincible<=0)nova(g);
    }
    g->tx=clampf(g->tx,18,382);g->ty=clampf(g->ty,90,212);
    g->vx+=(clampf((g->tx-g->x)*8,-190,190)-g->vx)*fminf(1,dt*9);
    g->vy+=(clampf((g->ty-g->y)*8,-140,140)-g->vy)*fminf(1,dt*9);
    g->x=clampf(g->x+g->vx*dt,16,384);g->y=clampf(g->y+g->vy*dt,35,218);
    if(g->time<2.8f)return;
    g->fire-=dt;
    if(g->fire<=0) {
        g->fire=.14f;shoot(g,g->shots,SHOTS,g->x-6,g->y-14,0,-245,1);
        shoot(g,g->shots,SHOTS,g->x+6,g->y-14,0,-245,1);
    }
    if(g->phase==0 && g->stage_time>38) {
        g->phase=1;g->boss_hp=g->boss_max=100+g->sector*30;g->by=-60;g->bentry=0;
        memset(g->enemies,0,sizeof(g->enemies));memset(g->hostile,0,sizeof(g->hostile));
    }
    if(g->phase==0) {
        g->spawn-=dt;
        if(g->spawn<=0) {
            g->spawn=fmaxf(.32f,.72f-g->sector*.12f);
            for(unsigned i=0;i<ENEMIES;++i)if(!g->enemies[i].live) {
                int kind=g->spawned%3;float x=35+random_f(g)*330;
                g->enemies[i]=(Enemy){.live=1,.x=x,.home=x,.y=-14,.vy=38+g->sector*9,
                                      .hp=kind==1?4:2,.kind=kind,.fire=1+random_f(g)};
                ++g->spawned;break;
            }
        }
        for(unsigned i=0;i<ENEMIES;++i)if(g->enemies[i].live) {
            Enemy *e=&g->enemies[i];e->age+=dt;e->fire-=dt;
            float wanted=e->kind==0?sinf(e->age*2.2f+i)*100:e->kind==1?sinf(e->age*1.6f+i)*65:cosf(e->age*2.8f+i)*130;
            if(e->kind==2 && e->age>2.6f)wanted=clampf((g->x-e->x)*2,-130,130);
            e->vx+=(wanted-e->vx)*fminf(1,dt*3);e->x+=e->vx*dt;
            e->y+=dt*(e->vy+(e->age>3?28:0));
            if(e->x<14){e->x=14;e->vx=fabsf(e->vx);}if(e->x>386){e->x=386;e->vx=-fabsf(e->vx);}
            if(e->fire<=0 && e->y>15 && e->y<180) {
                float dx=g->x-e->x,dy=g->y-e->y,len=fmaxf(1,hypotf(dx,dy));
                float speed=68+g->sector*13;
                shoot(g,g->hostile,HOSTILE,e->x,e->y,dx/len*speed,dy/len*speed,0);
                e->fire=e->kind==1?.7f:1.6f;
            }
            if(e->y>255)e->live=0;
            if(hypotf(e->x-g->x,e->y-g->y)<14){damage(g);defeat(g,e);}
        }
    } else if(g->phase==1) {
        g->bentry+=dt;g->bx=200+95*sinf(g->bentry*.65f);g->by=fminf(66,g->by+dt*42);
        if(g->bentry>2 && fabsf(g->x-g->bx)<45 && fabsf(g->y-g->by)<39)damage(g);
        g->bfire-=dt;
        if(g->bentry>2 && g->bfire<=0) {
            g->bfire=1.05f-g->sector*.1f;
            float aim=atan2f(g->y-g->by,g->x-g->bx);
            for(int j=-3;j<=3;++j) {
                float angle=aim+j*.19f+.1f*sinf(g->time*1.7f),speed=66+g->sector*12;
                shoot(g,g->hostile,HOSTILE,g->bx+j*8,g->by+34,cosf(angle)*speed,sinf(angle)*speed,0);
            }
        }
        if(g->boss_hp<=0) {
            g->phase=2;g->stage_time=0;g->score+=4000*(g->sector+1);g->health=5;g->bombs=3;
            memset(g->hostile,0,sizeof(g->hostile));
            for(unsigned i=0;i<8;++i) {
                float dy=(random_f(g)-.5f)*60;
                float dx=(random_f(g)-.5f)*85;
                burst(g,g->bx+dx,g->by+dy);
            }
        }
    } else if(g->stage_time>4) {
        if(++g->sector==3) { g->finished=1;g->won=1;g->end_time=0; }
        else { g->phase=0;g->stage_time=0;g->spawn=0; }
    }
    for(unsigned group=0;group<2;++group) {
        Shot *shots=group?g->hostile:g->shots;unsigned count=group?HOSTILE:SHOTS;
        for(unsigned i=0;i<count;++i)if(shots[i].live) {
            Shot *b=&shots[i];b->age+=dt;b->x+=b->vx*dt;b->y+=b->vy*dt;
            if(b->x<-12||b->x>412||b->y<-18||b->y>252||b->age>6){b->live=0;continue;}
            if(group) { if(hypotf(b->x-g->x,b->y-g->y)<7) { b->live=0;damage(g); } }
            else {
                if(g->phase==1 && fabsf(b->x-g->bx)<43 && fabsf(b->y-g->by)<33) {
                    b->live=0;g->boss_hp-=g->weapon;effect(g,b->x,b->y,1);g->score+=5;continue;
                }
                for(unsigned j=0;j<ENEMIES;++j)if(g->enemies[j].live) {
                    Enemy *e=&g->enemies[j];
                    if(fabsf(b->x-e->x)<10 && fabsf(b->y-e->y)<10) {
                        b->live=0;e->hp-=g->weapon;effect(g,b->x,b->y,1);if(e->hp<=0)defeat(g,e);break;
                    }
                }
            }
        }
    }
}
static void render(Video *v,const Game *g)
{
    unsigned page=v->frames&1,s=v->scale,offset=s==2?NA_PLAYER_2_0-NA_PLAYER_1_0:0;
    float shake=g->shake>0?sinf(g->time*130)*g->shake*6:0;
    v->sprites=0;v->capture_count=0;
    v->scene=(struct prodock_scene){.base=BASE+page*0x100000,.stride=1600,.format=7,.layers_enabled=1,.sprites_enabled=1};
    emit(v,22U<<24,v->scene.base,BASE+0x200000,xy(400,240),xy(1600,1600),0,0,0);
    Resource bg=v->art[NA_BACKGROUND];
    int sy=(int)(40+34*sinf(g->time*.045f)+shake);
    emit(v,29U<<24,v->assets+bg.offset,xy(bg.w,bg.h),bg.pitch,xy(0,sy),0,xy(400,240),0);
    Resource tex=v->art[NA_GLOW];
    if(!v->frames)emit(v,30U<<24,0,0,0,0,0,0,0);
    emit(v,24U<<24,v->assets+tex.offset,xy(tex.w,tex.h),tex.pitch|(1U<<16),0,0,0,0);
    if(!g->finished) {
        glow(v,g->x,g->y+17,12,0x47ff,220);
        if(g->nova>0) {
            glow(v,g->x,g->y,24,0x57ff,(unsigned)(g->nova*230));
            ring(v,g->x,g->y,15+(1-g->nova/.8f)*160,(unsigned)(g->nova*250));
        }
    }
    unsigned lights=0;
    for(unsigned i=0;i<EFFECTS && lights<4;++i)if(g->fx[i].live && g->fx[i].kind==0) {
        glow(v,g->fx[i].x,g->fx[i].y,10+(int)(g->fx[i].age*12),0xfd46,(unsigned)(220*(1-g->fx[i].age/g->fx[i].life)));++lights;
    }
    /* Small opaque HUD backplates use fast hardware CLEAR, not shaded quads. */
    solid(v,0x0843,0,0,400,24);solid(v,0x0843,0,226,400,14);
    solid(v,0x2a6b,0,23,400,1);solid(v,0x2a6b,0,226,400,1);
    for(int i=0;i<5;++i)solid(v,i<g->health?0x4ef7:0x1946,9+i*11,18,8,2);
    if(g->phase==1) {
        solid(v,0x3807,115,20,175,2);
        solid(v,0xfa69,115,20,(unsigned)(175*clampf((float)g->boss_hp/g->boss_max,0,1)),2);
    }
    flush(v);
    for(unsigned field=0;field<2;++field) {
        unsigned pitch=(400*s+31)&~31U,height=512*s;
        unsigned scroll=(height-(unsigned)(g->time*(field?34:9)*s)%height)%height;
        uint32_t *l=v->scene.layers[field];
        l[0]=v->stars[field][s-1]+scroll*pitch;l[1]=yx(400*s,240*s);
        l[3]=yx(400*s,240*s);l[5]=pitch;l[6]=3;
    }
    if(g->phase==1)image_layer(v,2,NA_BOSS_1+offset,(int)lroundf((g->bx-52)*s),(int)lroundf((g->by-46)*s));
    if(!g->finished || g->won) {
        int bank=(int)lroundf(clampf(g->vx/75,-2,2))+2;
        if(g->invincible<=0 || ((int)(g->time*12)&1))
            image_layer(v,4,NA_PLAYER_1_0+offset+bank,(int)lroundf((g->x-14)*s),(int)lroundf((g->y-16)*s));
        if(g->invincible>0 || g->nova>0)
            image_layer(v,5,NA_SHIELD_1_0+offset+((unsigned)(g->time*12)&3),(int)lroundf((g->x-20)*s),(int)lroundf((g->y-20)*s));
    }
    for(unsigned i=0;i<ENEMIES;++i)if(g->enemies[i].live)
        sprite(v,NA_ENEMY_1_0+offset+g->enemies[i].kind,g->enemies[i].x,g->enemies[i].y,3);
    for(unsigned i=0;i<SHOTS;++i)if(g->shots[i].live)sprite(v,NA_SHOT_1+offset,g->shots[i].x,g->shots[i].y,6);
    for(unsigned i=0;i<HOSTILE;++i)if(g->hostile[i].live)sprite(v,NA_ENEMYSHOT_1+offset,g->hostile[i].x,g->hostile[i].y,6);
    /* Gameplay objects always fit: 12 enemies + 16 shots + 22 hostile
     * shots + at most 4 pickups. Only decorative effects may be culled. */
    for(unsigned i=0;i<EFFECTS;++i)if(g->fx[i].live && g->fx[i].kind==2)
        sprite(v,NA_PICKUP_1+offset,g->fx[i].x,g->fx[i].y,7);
    for(unsigned i=0;i<EFFECTS;++i)if(g->fx[i].live && g->fx[i].kind!=2) {
        const Effect *e=&g->fx[i];unsigned art=e->kind==0?NA_EXPLOSION_1_0+(unsigned)clampf(e->age/e->life*8,0,7):e->kind==1?NA_SPARK_1:NA_PICKUP_1;
        sprite(v,art+offset,e->x,e->y,7);
    }
    uint16_t *top=memory(v,v->maps[page][0]),*bottom=memory(v,v->maps[page][1]),*banner=memory(v,v->maps[page][2]);
    memset(top,0,512);memset(bottom,0,512);memset(banner,0,512);
    char line[80];
    snprintf(line,sizeof(line),"NEBULA  /  RIFT RAIDERS          %08d",g->score);label(top,1,0,0,line);
    snprintf(line,sizeof(line),"HULL     NOVA%d  MK%d  SECTOR%02d  CHAIN x%d",g->bombs,g->weapon,g->sector+1,g->combo);label(top,1,1,1,line);
    label(bottom,1,0,6,g->demo?"AUTOPILOT   /   REAL-TIME LINUX + FPGA GPU":"WASD/ARROWS SPACE:NOVA P:PAUSE F:VIEW Q:EXIT");
    tile_layer(v,9,v->maps[page][0],0,2);tile_layer(v,10,v->maps[page][1],229,1);
    if(g->time<2.8f) {
        image_layer(v,8,s==2?NA_LOGO_2:NA_LOGO_1,122*s,81*s);
        label(banner,13,0,1,"R I F T   R A I D E R S");
        label(banner,11,2,0,g->demo?"AUTOPILOT / GPU SHOWCASE":"DEFEND THE RIFT / AUTO FIRE");
        tile_layer(v,11,v->maps[page][2],122,3);
    } else if(g->finished || g->paused || g->phase==2 || (g->phase==1 && g->bentry<2)) {
        const char *title=g->paused?"FLIGHT PAUSED":g->finished?(g->won?"RIFT SECURED / VICTORY":"SIGNAL LOST"):g->phase==2?"SECTOR CLEARED":"WARNING / DREADNOUGHT";
        label(banner,(50-(int)strlen(title))/2,0,g->won||g->phase==2?5:2,title);
        if(g->finished)label(banner,12,2,0,g->demo?"NEXT FLIGHT IN A MOMENT":"R TO RETRY  /  Q TO EXIT");
        else if(g->paused)label(banner,17,2,0,"P TO RESUME");
        tile_layer(v,11,v->maps[page][2],101,3);
    }
    if(v->sprites>v->max_sprites)v->max_sprites=v->sprites;
    unsigned layers=0;for(unsigned i=0;i<12;++i)layers+=!!(v->scene.layers[i][6]&1);
    if(layers>v->max_layers)v->max_layers=layers;
    checked(v,PRODOCK_PRESENT,&v->scene);++v->frames;
}
static int dump(Video *v,const Game *g,const char *base)
{
    char path[512];FILE *f;
#define SAVE(suffix,data,size) do { snprintf(path,sizeof(path),"%s.%s",base,suffix);f=fopen(path,"wb"); \
    if(!f){return -1;}size_t bytes=(size);if(fwrite(data,1,bytes,f)!=bytes){fclose(f);return -1;}if(fclose(f)){return -1;} } while(0)
    SAVE("memory",v->mem,v->used);SAVE("scene",&v->scene,sizeof(v->scene));
    SAVE("commands",v->capture_commands,v->capture_count*32);
#undef SAVE
    snprintf(path,sizeof(path),"%s.json",base);f=fopen(path,"w");if(!f)return -1;
    fprintf(f,"{\"frames\":%u,\"commands\":%u,\"sprites\":%u,\"max_sprites\":%u,\"max_layers\":%u,\"score\":%d,\"sector\":%d,\"phase\":%d,\"health\":%d,\"boss_hp\":%d,\"won\":%d,\"time\":%.3f,\"memory_bytes\":%u,\"assets\":%u,\"scale\":%d}\n",
            v->frames,v->commands,v->sprites,v->max_sprites,v->max_layers,g->score,g->sector,g->phase,g->health,g->boss_hp,g->won,g->time,v->used,v->assets,v->scale);
    return fclose(f);
}
int main(int argc,char **argv)
{
    int demo=0,split=0,boss=0,sector=0,rc=1,changed=0;
    unsigned limit=0,pose=0;const char *capture=NULL,*snapshot=NULL,*path="/usr/share/nebula/nebula.bin";
    for(int i=1;i<argc;++i) {
        if(!strcmp(argv[i],"--demo"))demo=1;
        else if(!strcmp(argv[i],"--split"))split=1;
        else if(!strcmp(argv[i],"--boss"))boss=1;
        else if(!strcmp(argv[i],"--assets") && i+1<argc)path=argv[++i];
        else if(!strcmp(argv[i],"--capture") && i+1<argc)capture=argv[++i];
        else if(!strcmp(argv[i],"--snapshot") && i+1<argc)snapshot=argv[++i];
        else if(!strcmp(argv[i],"--pose") && i+1<argc) {
            char *end;unsigned long n=strtoul(argv[++i],&end,10);if(*end||!n||n>100000)return 2;pose=(unsigned)n;
        }
        else if(!strcmp(argv[i],"--frames") && i+1<argc) {
            char *end;unsigned long n=strtoul(argv[++i],&end,10);if(*end||!n||n>1000000)return 2;limit=(unsigned)n;
        } else { fprintf(stderr,"usage: nebula [--demo] [--split] [--boss] [--frames N] [--assets FILE]\n");return 2; }
    }
    if(snapshot && !pose) { fprintf(stderr,"--snapshot requires a fixed --pose\n");return 2; }
    Video video={.fd=-1,.display=-1,.used=3*1024*1024,.scale=split?1:2};Video *v=&video;
#ifdef NEBULA_HOST
    v->host=1;demo=1;if(!limit)limit=600;
#else
    if(capture) { fprintf(stderr,"Capture is a host preview option\n");return 2; }
#endif
    struct termios saved={0},raw;
    if(v->host)v->mem=calloc(1,MAP_BYTES);
    else {
        v->fd=open("/dev/prodock-gpu",O_RDWR|O_CLOEXEC);v->display=open("/dev/prodock-display",O_RDWR|O_CLOEXEC);
        if(v->fd<0 || v->display<0) { perror("NEBULA open (stop another game first)");goto cleanup; }
        struct prodock_info info;
        if(checked(v,PRODOCK_INFO,&info) || (info.caps&0x1ff)!=0x1ff || info.faulted || info.errors)goto cleanup;
        if(checked(v,PRODOCK_DISPLAY_INFO,&v->initial))goto cleanup;
        v->mem=mmap(NULL,MAP_BYTES,PROT_READ|PROT_WRITE,MAP_SHARED,v->fd,0);
        if(v->mem==MAP_FAILED) { v->mem=NULL;perror("NEBULA mmap");goto cleanup; }
        if(!demo) {
            if(tcgetattr(STDIN_FILENO,&saved)) { perror("NEBULA input");goto cleanup; }
            raw=saved;raw.c_lflag&=~(ICANON|ECHO);raw.c_cc[VMIN]=0;raw.c_cc[VTIME]=0;
            if(tcsetattr(STDIN_FILENO,TCSANOW,&raw))goto cleanup;
            changed=1;
        }
    }
    if(!v->mem)goto cleanup;
    signal(SIGTERM,stop);signal(SIGINT,stop);signal(SIGHUP,stop);
    printf("NEBULA loading native GPU assets...\n");fflush(stdout);
    if(assets(v,path))goto cleanup;
    struct prodock_layout layout={.mode=split?PRODOCK_SPLIT:PRODOCK_GAME};
    if(checked(v,PRODOCK_LAYOUT,&layout))goto cleanup;
    Game game;reset_game(&game,demo,sector,boss);
    if(pose) {
        game.demo=1;for(unsigned i=0;i<pose;++i)update(&game,1.f/55);
        if(!limit)limit=3;
    }
    double start=now(),last=start,next_status=start;
    printf("NEBULA_START mode=%s assets=%u memory=%u - WASD/arrows SPACE nova P pause Q exit\n",demo?"demo":"play",NEBULA_ASSET_BYTES,v->used);fflush(stdout);
    while(!stopping && !v->failed && (!limit || v->frames<limit)) {
        double current=now();float dt=v->host?1.f/55:(float)(current-last);last=current;
        dt=clampf(dt,.001f,.05f);
        if(!demo) {
            struct pollfd p={STDIN_FILENO,POLLIN,0};
            if(poll(&p,1,0)>0) {
                if(p.revents&(POLLHUP|POLLERR|POLLNVAL))break;
                if(p.revents&POLLIN) {
                    unsigned char keys[64];ssize_t n=read(STDIN_FILENO,keys,sizeof(keys));
                    if(n<0 && errno!=EINTR) { perror("NEBULA input");v->failed=1;break; }
                    for(ssize_t i=0;i<n;++i) {
                        if(keys[i]=='f'||keys[i]=='F') {
                            layout.mode=v->scale==2?PRODOCK_SPLIT:PRODOCK_GAME;
                            checked(v,PRODOCK_LAYOUT,&layout);v->scale=layout.mode==PRODOCK_GAME?2:1;
                        } else key(&game,keys[i]);
                    }
                }
            }
        }
        if(!v->host && current>=next_status) {
            if(checked(v,PRODOCK_DISPLAY_INFO,&v->last))break;
            if(v->last.errors || v->last.faulted || v->last.underflows!=v->initial.underflows ||
               v->last.invalid_layers!=v->initial.invalid_layers || v->last.invalid_sprites!=v->initial.invalid_sprites) {
                fprintf(stderr,"NEBULA display error: errors=%u uf=%u layers=%u sprites=%u fault=%u\n",
                        v->last.errors,v->last.underflows,v->last.invalid_layers,v->last.invalid_sprites,v->last.faulted);
                v->failed=1;break;
            }
            v->scale=v->last.mode==PRODOCK_GAME?2:1;next_status=current+.2;
        }
        if(!pose)update(&game,dt);
        render(v,&game);
    }
    if(capture && dump(v,&game,capture)) { perror("NEBULA capture");v->failed=1; }
    if(snapshot && !v->failed && v->frames) {
        FILE *f=fopen(snapshot,"wb");
        if(!f) { perror("NEBULA snapshot");v->failed=1; }
        else {
            size_t n=fwrite(&v->scene,1,sizeof(v->scene),f);int closed=fclose(f);
            if(n!=sizeof(v->scene) || closed) { perror("NEBULA snapshot write");v->failed=1; }
            else printf("NEBULA_SCENE_CRC32 crc=%08x bytes=%u\n",crc32((uint8_t *)&v->scene,sizeof(v->scene)),(unsigned)sizeof(v->scene));
        }
    }
    double seconds=now()-start;
    if(v->host)printf("NEBULA_MODEL frames=%u simulated_seconds=%.3f commands=%u max_sprites=%u max_layers=%u cosmetic_dropped=%u\n",
            v->frames,game.time,v->commands,v->max_sprites,v->max_layers,v->fx_dropped);
    else printf("NEBULA_RATE frames=%u seconds=%.3f fps=%.2f commands=%u max_sprites=%u max_layers=%u cosmetic_dropped=%u\n",
            v->frames,seconds,v->frames/fmax(seconds,.001),v->commands,v->max_sprites,v->max_layers,v->fx_dropped);
    if(pose && !v->host && !v->failed && v->frames) {
        uint8_t *pixels=malloc(400*240*2);
        if(!pixels)v->failed=1;
        else {
            const uint8_t *frame=memory(v,v->scene.base);
            for(unsigned y=0;y<240;++y)memcpy(pixels+y*800,frame+y*1600,800);
            printf("NEBULA_FRAME_CRC32 pose=%u crc=%08x pixels=96000\n",pose,crc32(pixels,400*240*2));free(pixels);
        }
    }
    printf("NEBULA_RESULT score=%d kills=%d sector=%d boss_hp=%d health=%d victory=%d spawned=%u shots=%u damage=%u novas=%u status=%d\n",
            game.score,game.kills,game.sector+1,game.boss_hp,game.health,game.won,game.spawned,game.shots_fired,game.damage_taken,game.novas,v->failed);
    rc=v->failed?1:0;
cleanup:
    if(changed)tcsetattr(STDIN_FILENO,TCSANOW,&saved);
    if(v->mem) { if(v->host)free(v->mem);else munmap(v->mem,MAP_BYTES); }
    if(v->fd>=0)close(v->fd);
    if(v->display>=0)close(v->display);
    return rc;
}
