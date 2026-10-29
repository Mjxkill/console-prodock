#include "l3_platform.h"
#include <limits.h>
#include <string.h>

enum {VER,STATUS,SEED,RNG,TICKS,PHASE,SCORE,LIVES,GRACE,PX,PY,PZ,VY,FLOOR,
      CLIMB,AIR,CHECKPOINT,HIGHEST,CLOCK,SERIAL,SPAWNED,ESCAPED,JUMPS,PRIZE};
enum {BA,BX,BY,BZ,BVX,BVY,BFLOOR,BID};
#define FX(n) ((n)*256)
static const unsigned ladder_x[4]={128,32,128,32};
static int absolute(int v){return v<0?-v:v;}
static int clamp(int v,int a,int b){return v<a?a:v>b?b:v;}
static uint32_t plus(uint32_t a,uint32_t b){return UINT32_MAX-a<b?UINT32_MAX:a+b;}
static uint32_t random32(L3PlatformState *s){uint32_t r=s->words[RNG];r^=r<<13;r^=r>>17;r^=r<<5;s->words[RNG]=r;return r;}
static int surface(unsigned floor,int x)
{return floor%2u==0 || x<=FX(72) || x>=FX(88);}
static int ladder_near(const L3PlatformState *s,unsigned lower)
{return absolute((int)s->words[PX]-FX((int)ladder_x[lower]))<=FX(4) && absolute((int)s->words[PZ]-FX(32))<=FX(5);}
static void score(L3PlatformState *s)
{s->words[SCORE]=s->words[HIGHEST]*100u+(s->words[CHECKPOINT]?250u:0u)+s->words[PRIZE]*1000u;}
static void finish(L3PlatformState *s,unsigned status)
{s->words[STATUS]=status;s->words[PHASE]=0;}
static void respawn(L3PlatformState *s)
{
    s->words[FLOOR]=s->words[CHECKPOINT];s->words[PX]=s->words[CHECKPOINT]?FX(32):FX(16);
    s->words[PY]=s->words[FLOOR]*FX(32);s->words[PZ]=FX(32);s->words[VY]=2048;
    s->words[CLIMB]=0;s->words[AIR]=0;s->words[GRACE]=120;
}
static void damage(L3PlatformState *s)
{
    if(s->words[GRACE] || s->words[STATUS]!=L3_MINI_RUNNING)return;
    if(--s->words[LIVES]==0)finish(s,L3_MINI_LOST);else respawn(s);
}
static void jump(L3PlatformState *s)
{
    if(s->words[AIR] || s->words[CLIMB])return;
    s->words[AIR]=1;s->words[VY]=2048+896;s->words[JUMPS]=plus(s->words[JUMPS],1);
}
static void player_tick(L3PlatformState *s,uint32_t held)
{
    unsigned f=s->words[FLOOR];int x=(int)s->words[PX],y=(int)s->words[PY],z=(int)s->words[PZ];
    if(!s->words[AIR] && !s->words[CLIMB]){
        if((held&L3_MINI_UP) && f<4 && ladder_near(s,f))s->words[CLIMB]=1;
        else if((held&L3_MINI_DOWN) && f>0 && ladder_near(s,f-1u)){--f;s->words[FLOOR]=f;s->words[CLIMB]=1;}
        if(s->words[CLIMB]){x=FX((int)ladder_x[f]);z=FX(32);s->words[VY]=2048;}
    }
    if(s->words[CLIMB]){
        if(held&L3_MINI_UP)y+=256;
        if(held&L3_MINI_DOWN)y-=256;
        if(y<=(int)(f*FX(32))){y=(int)(f*FX(32));s->words[CLIMB]=0;}
        if(y>=(int)((f+1u)*FX(32))){y=(int)((f+1u)*FX(32));s->words[FLOOR]=f+1u;s->words[CLIMB]=0;}
    }else{
        int old_y=y,velocity;int landing=-1,level;
        if(held&L3_MINI_LEFT)x-=384;
        if(held&L3_MINI_RIGHT)x+=384;
        if(held&L3_MINI_UP)z-=384;
        if(held&L3_MINI_DOWN)z+=384;
        x=clamp(x,FX(8),FX(152));z=clamp(z,FX(8),FX(56));
        if(!s->words[AIR] && !surface(f,x)){s->words[AIR]=1;s->words[VY]=2048;}
        if(s->words[AIR]){
            velocity=clamp((int)s->words[VY]-2048-80,-1024,896);y+=velocity;s->words[VY]=(unsigned)(velocity+2048);
            if(velocity<=0)for(level=4;level>=0;--level){int height=level*FX(32);
                if(height<=old_y && height>=y && surface((unsigned)level,x)){landing=level;break;}}
            if(landing>=0){s->words[FLOOR]=(unsigned)landing;y=landing*FX(32);s->words[AIR]=0;s->words[VY]=2048;}
            if(y<0){damage(s);return;}
        }
    }
    s->words[PX]=(unsigned)x;s->words[PY]=(unsigned)y;s->words[PZ]=(unsigned)z;
    if(!s->words[AIR] && !s->words[CLIMB]){
        if(s->words[FLOOR]>s->words[HIGHEST])s->words[HIGHEST]=s->words[FLOOR];
        if(s->words[FLOOR]>=2)s->words[CHECKPOINT]=2;
        score(s);
    }
}
static unsigned next_id(L3PlatformState *s)
{
    unsigned id=s->words[SERIAL],i;int used;
    do{id=id%65533u+1u;used=0;for(i=0;i<8;++i)if(s->barrels[i].words[BID]==id)used=1;}while(used);
    s->words[SERIAL]=id;return id;
}
static void barrel_spawn(L3PlatformState *s)
{
    unsigned i;
    if(s->words[CLOCK]){--s->words[CLOCK];return;}
    s->words[CLOCK]=90;
    for(i=0;i<8;++i)if(!s->barrels[i].words[BA]){L3PlatformBarrel *b=&s->barrels[i];
        memset(b,0,sizeof(*b));b->words[BA]=1;b->words[BX]=FX(144);b->words[BY]=FX(128);
        b->words[BZ]=FX(16u+16u*(random32(s)%3u));b->words[BVX]=2048-320;b->words[BVY]=2048;b->words[BFLOOR]=4;b->words[BID]=next_id(s);
        ++s->words[SPAWNED];break;}
}
static void barrels_tick(L3PlatformState *s)
{
    unsigned i;
    for(i=0;i<8 && s->words[STATUS]==L3_MINI_RUNNING;++i){L3PlatformBarrel *b=&s->barrels[i];unsigned f=b->words[BFLOOR];int x,y,base;
        if(!b->words[BA])continue;
        x=(int)b->words[BX];y=(int)b->words[BY];base=(int)(f*FX(32));
        if(y>base){y-=512;b->words[BVX]=2048;b->words[BVY]=2048-512;
            if(y<=base){y=base;b->words[BVX]=(unsigned)(2048+(f%2u?320:-320));b->words[BVY]=2048;}
        }else{
            x+=(int)b->words[BVX]-2048;
            if(x<FX(12) || x>FX(148) || !surface(f,x)){
                x=clamp(x,FX(12),FX(148));
                if(f==0){memset(b,0,sizeof(*b));++s->words[ESCAPED];continue;}
                --f;b->words[BFLOOR]=f;b->words[BVX]=2048;b->words[BVY]=2048-512;
            }
        }
        b->words[BX]=(unsigned)x;b->words[BY]=(unsigned)y;
        if(absolute(x-(int)s->words[PX])<FX(6) && absolute((int)b->words[BZ]-(int)s->words[PZ])<FX(6) && absolute(y+FX(3)-(int)s->words[PY]-FX(6))<FX(8))damage(s);
    }
}
static void tick(L3PlatformState *s,uint32_t held)
{
    s->words[TICKS]=plus(s->words[TICKS],1);if(s->words[GRACE])--s->words[GRACE];
    player_tick(s,held);barrel_spawn(s);barrels_tick(s);
    if(s->words[STATUS]==L3_MINI_RUNNING && !s->words[AIR] && !s->words[CLIMB] && s->words[FLOOR]==4 && s->words[PX]>=FX(140) && absolute((int)s->words[PZ]-FX(32))<=FX(6)){
        s->words[PRIZE]=1;score(s);finish(s,L3_MINI_WON);
    }
}
int l3_platform_init(L3PlatformState *s,uint32_t seed)
{
    L3PlatformState t;if(!s)return 0;memset(&t,0,sizeof(t));t.words[VER]=1;t.words[SEED]=seed;t.words[RNG]=seed^0x544f5745u;
    if(!t.words[RNG])t.words[RNG]=1;
    t.words[LIVES]=3;respawn(&t);*s=t;return 1;
}
int l3_platform_validate(const L3PlatformState *s)
{
    unsigned i,j,active=0;int base;
    if(!s || s->words[VER]!=1 || s->words[STATUS]>L3_MINI_LOST || !s->words[RNG] || s->words[PHASE]>=1000 || s->words[PHASE]%20u || s->words[LIVES]>3 || s->words[GRACE]>120 || s->words[PX]<FX(8) || s->words[PX]>FX(152) || s->words[PZ]<FX(8) || s->words[PZ]>FX(56) || s->words[PY]>FX(152) || s->words[VY]<1024 || s->words[VY]>2944 || s->words[FLOOR]>4 || s->words[CLIMB]>1 || s->words[AIR]>1 || (s->words[CHECKPOINT]!=0 && s->words[CHECKPOINT]!=2) || s->words[HIGHEST]>4 || s->words[CLOCK]>90 || s->words[SERIAL]>65533 || s->words[PRIZE]>1)return 0;
    for(i=24;i<32;++i)if(s->words[i])return 0;
    if((s->words[STATUS]==L3_MINI_WON)!=(s->words[PRIZE]!=0) || (s->words[STATUS]==L3_MINI_LOST)!=(s->words[LIVES]==0) || (s->words[STATUS]!=L3_MINI_RUNNING && s->words[PHASE]))return 0;
    if(s->words[SCORE]!=s->words[HIGHEST]*100u+(s->words[CHECKPOINT]?250u:0u)+s->words[PRIZE]*1000u || (s->words[HIGHEST]>=2)!=(s->words[CHECKPOINT]==2))return 0;
    if(s->words[HIGHEST]<s->words[FLOOR])return 0;
    base=(int)(s->words[FLOOR]*FX(32));
    if(s->words[CLIMB]){
        if(s->words[FLOOR]>=4 || s->words[AIR] || s->words[VY]!=2048 || (int)s->words[PY]<=base || (int)s->words[PY]>=base+FX(32) || s->words[PX]!=FX(ladder_x[s->words[FLOOR]]) || s->words[PZ]!=FX(32))return 0;
    }else if(!s->words[AIR]){if((int)s->words[PY]!=base || s->words[VY]!=2048 || !surface(s->words[FLOOR],(int)s->words[PX]))return 0;}
    else if((int)s->words[PY]>base+FX(24))return 0;
    if(s->words[PRIZE] && (s->words[FLOOR]!=4 || s->words[AIR] || s->words[CLIMB] || s->words[PX]<FX(140) || absolute((int)s->words[PZ]-FX(32))>FX(6)))return 0;
    for(i=0;i<8;++i){const L3PlatformBarrel *b=&s->barrels[i];unsigned f=b->words[BFLOOR];
        if(!b->words[BA]){for(j=1;j<8;++j)if(b->words[j])return 0;continue;}
        ++active;
        if(b->words[BA]!=1 || f>4 || b->words[BX]<FX(12) || b->words[BX]>FX(148) || b->words[BY]<f*FX(32) || b->words[BY]>(f+1u)*FX(32) || (b->words[BZ]!=FX(16) && b->words[BZ]!=FX(32) && b->words[BZ]!=FX(48)) || (b->words[BVX]!=1728 && b->words[BVX]!=2048 && b->words[BVX]!=2368) || (b->words[BVY]!=1536 && b->words[BVY]!=2048) || !b->words[BID] || b->words[BID]>65533)return 0;
        for(j=0;j<i;++j)if(s->barrels[j].words[BID]==b->words[BID])return 0;
    }
    if((uint64_t)active+s->words[ESCAPED]!=s->words[SPAWNED])return 0;
    return 1;
}
uint32_t l3_platform_step(L3PlatformState *s,uint32_t pressed,uint32_t held,uint32_t dt)
{
    unsigned n,i,phase;
    if(!l3_platform_validate(s) || ((pressed|held)&~L3_MINI_INPUT_MASK))return L3_MINI_EVENT_INVALID;
    if(pressed&L3_MINI_BACK)return L3_MINI_EVENT_EXIT;
    if(s->words[STATUS]!=L3_MINI_RUNNING)return 0;
    if(pressed&L3_MINI_ACT)jump(s);
    if(dt>250)dt=250;
    phase=s->words[PHASE]+dt*60u;n=phase/1000u;s->words[PHASE]=phase%1000u;
    for(i=0;i<n && s->words[STATUS]==L3_MINI_RUNNING;++i)tick(s,held);
    if(s->words[STATUS]!=L3_MINI_RUNNING)return L3_MINI_EVENT_CHANGED|(s->words[STATUS]==L3_MINI_WON?L3_MINI_EVENT_WON:L3_MINI_EVENT_LOST);
    return pressed || held || dt?L3_MINI_EVENT_CHANGED:0;
}
static void actor(L3PlatformActor *a,unsigned kind,unsigned id,unsigned x,unsigned y,unsigned z)
{a->kind=(uint8_t)kind;a->id=(uint16_t)id;a->x256=(int)x;a->y256=(int)y;a->z256=(int)z;a->color=(uint8_t)(kind==1?10:kind==2?6:kind==3?14:11);}
int l3_platform_view(const L3PlatformState *s,L3PlatformView *out)
{
    L3PlatformView v;unsigned i;uint64_t elapsed;
    if(!out || !l3_platform_validate(s))return 0;
    memset(&v,0,sizeof(v));actor(&v.actors[0],1,0,s->words[PX],s->words[PY],s->words[PZ]);
    v.actors[0].vy256=(int16_t)((int)s->words[VY]-2048);v.actors[0].flags=(uint8_t)(s->words[AIR]|(s->words[CLIMB]<<1)|(s->words[GRACE]?4u:0u));
    actor(&v.actors[1],3,65534,FX(144),FX(128),FX(32));v.actors[1].flags=(uint8_t)s->words[PRIZE];
    actor(&v.actors[2],4,65535,FX(32),FX(64),FX(32));v.actors[2].flags=s->words[CHECKPOINT]!=0;v.actor_count=3;
    for(i=0;i<8;++i)if(s->barrels[i].words[BA]){const L3PlatformBarrel *b=&s->barrels[i];L3PlatformActor *a=&v.actors[v.actor_count++];
        actor(a,2,b->words[BID],b->words[BX],b->words[BY],b->words[BZ]);a->vx256=(int16_t)((int)b->words[BVX]-2048);a->vy256=(int16_t)((int)b->words[BVY]-2048);a->flags=b->words[BY]>b->words[BFLOOR]*FX(32);}
    for(i=0;i<5;++i){L3PlatformSurface *p=&v.surfaces[v.surface_count++];p->x0=FX(8);p->z0=FX(8);p->x1=i%2u?FX(72):FX(152);p->z1=FX(56);p->y256=(int)i*FX(32);
        if(i%2u){p=&v.surfaces[v.surface_count++];p->x0=FX(88);p->z0=FX(8);p->x1=FX(152);p->z1=FX(56);p->y256=(int)i*FX(32);}}
    for(i=0;i<4;++i){v.ladders[i].x256=FX((int)ladder_x[i]);v.ladders[i].z256=FX(32);v.ladders[i].y0=(int)i*FX(32);v.ladders[i].y1=(int)(i+1u)*FX(32);}v.ladder_count=4;
    v.status=s->words[STATUS];v.score=s->words[SCORE];v.jumps=s->words[JUMPS];v.lives=(uint8_t)s->words[LIVES];v.floor=(uint8_t)s->words[FLOOR];v.highest_floor=(uint8_t)s->words[HIGHEST];v.checkpoint_floor=(uint8_t)s->words[CHECKPOINT];v.protection_ticks=(uint16_t)s->words[GRACE];
    elapsed=((uint64_t)s->words[TICKS]*1000u+s->words[PHASE])/60u;v.elapsed_ms=elapsed>UINT32_MAX?UINT32_MAX:(uint32_t)elapsed;
    v.title="La tour des rouages";v.help="Fleches: bouger ou grimper. Action: sauter les trous et tonneaux. Retour: sortir.";v.objective="Atteindre le fanal au sommet. Relais au troisieme etage; 3 vies.";*out=v;return 1;
}
static void put32(uint8_t *p,uint32_t v){unsigned i;for(i=0;i<4;++i)p[i]=(uint8_t)(v>>(8u*i));}
static uint32_t get32(const uint8_t *p){return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static uint32_t checksum(const uint8_t *b){unsigned i;uint32_t h=2166136261u;for(i=0;i<L3_PLATFORM_SAVE_BYTES;++i)if(i<12 || i>=16){h^=b[i];h*=16777619u;}return h;}
size_t l3_platform_encode(const L3PlatformState *s,void *out,size_t cap)
{
    uint8_t b[L3_PLATFORM_SAVE_BYTES];unsigned i,j,pos=144;
    if(!l3_platform_validate(s))return 0;
    if(!out)return sizeof(b);
    if(cap<sizeof(b))return 0;
    memcpy(b,"L3PF",4);put32(b+4,1);put32(b+8,384);put32(b+12,0);
    for(i=0;i<32;++i)put32(b+16u+4u*i,s->words[i]);
    for(i=0;i<8;++i)for(j=0;j<8;++j){put32(b+pos,s->barrels[i].words[j]);pos+=4;}
    put32(b+12,checksum(b));memcpy(out,b,sizeof(b));return sizeof(b);
}
int l3_platform_decode(L3PlatformState *s,const void *in,size_t size)
{
    const uint8_t *b=(const uint8_t *)in;L3PlatformState t;unsigned i,j,pos=144;
    if(!s || !b || size!=L3_PLATFORM_SAVE_BYTES || memcmp(b,"L3PF",4) || get32(b+4)!=1 || get32(b+8)!=384 || get32(b+12)!=checksum(b))return 0;
    memset(&t,0,sizeof(t));for(i=0;i<32;++i)t.words[i]=get32(b+16u+4u*i);
    for(i=0;i<8;++i)for(j=0;j<8;++j){t.barrels[i].words[j]=get32(b+pos);pos+=4;}
    if(!l3_platform_validate(&t))return 0;
    *s=t;return 1;
}
static int safe_command(const L3PlatformState *s,uint32_t pressed,uint32_t held,uint32_t dt)
{
    L3PlatformState t=*s;
    if(l3_platform_step(&t,pressed,held,dt)&L3_MINI_EVENT_INVALID)return 0;
    if(l3_platform_step(&t,0,held,150)&L3_MINI_EVENT_INVALID)return 0;
    return t.words[LIVES]==s->words[LIVES] && t.words[STATUS]!=L3_MINI_LOST;
}
int l3_platform_demo_input(const L3PlatformState *s,uint32_t *pressed,uint32_t *held,uint32_t *dt)
{
    unsigned f,i;int target,x,z;
    if(!pressed || !held || !dt || !l3_platform_validate(s) || s->words[STATUS]!=L3_MINI_RUNNING)return 0;
    *pressed=0;*held=0;*dt=100;f=s->words[FLOOR];x=(int)s->words[PX];z=(int)s->words[PZ];target=f<4?FX((int)ladder_x[f]):FX(144);
    if(s->words[CLIMB]){unsigned ticks=((f+1u)*FX(32)-s->words[PY])/256u;
        unsigned ms=(ticks*1000u-s->words[PHASE]+59u)/60u;
        *held=L3_MINI_UP;if(ms<*dt)*dt=ms;goto advise;}
    if((z<FX(30) || z>FX(34)) && f>0 && absolute(x-FX((int)ladder_x[f-1u]))<FX(8))
        *held=x<target?L3_MINI_RIGHT:L3_MINI_LEFT;
    else if(z<FX(30)){*held=L3_MINI_DOWN;*dt=17;}
    else if(z>FX(34)){*held=L3_MINI_UP;*dt=17;}
    else if(absolute(x-target)>FX(3)){*held=x<target?L3_MINI_RIGHT:L3_MINI_LEFT;if(absolute(x-target)<FX(12))*dt=33;}
    else if(f<4 && !s->words[AIR])*held=L3_MINI_UP;
    if(!s->words[AIR] && ((f%2u && x>=FX(90) && x<=FX(106) && target<x) || (f%2u && x>=FX(54) && x<=FX(70) && target>x)))*pressed=L3_MINI_ACT;
    if(!s->words[AIR] && !s->words[GRACE])for(i=0;i<8;++i){const L3PlatformBarrel *b=&s->barrels[i];
        if(b->words[BA] && absolute((int)b->words[BX]-x)<FX(25) && absolute((int)b->words[BZ]-z)<FX(6) && absolute((int)b->words[BY]-(int)s->words[PY])<FX(8))*pressed=L3_MINI_ACT;}
advise:
    if(!safe_command(s,*pressed,*held,*dt)){
        uint32_t options[7]={0,*held,*held|L3_MINI_UP,*held|L3_MINI_DOWN,L3_MINI_UP,L3_MINI_DOWN,L3_MINI_LEFT|L3_MINI_DOWN};
        for(i=0;i<7;++i){uint32_t p=i==1?L3_MINI_ACT:0;
            if(safe_command(s,p,options[i],*dt)){*pressed=p;*held=options[i];break;}}
    }
    return 1;
}
