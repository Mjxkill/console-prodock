#include "l3_shooter.h"
#include <limits.h>
#include <string.h>

enum {VER,STATUS,SEED,RNG,TICKS,PHASE,SCORE,WAVE,CLOCK,SPAWNED,KILLS,LIVES,
      SHIELD,FIRE,PX,PY,DOUBLE,ESCAPED,SERIAL,TOTAL,BOSSDEAD,PICKED};
enum {EK,EX,EY,EVX,EVY,EHP,EAGE,EID};
#define FX(n) ((n)*256)
static int absolute(int v){return v<0?-v:v;}
static int clamp(int n,int lo,int hi){return n<lo?lo:n>hi?hi:n;}
static uint32_t add(uint32_t a,uint32_t b){return UINT32_MAX-a<b?UINT32_MAX:a+b;}
static uint32_t random32(L3ShooterState *s)
{uint32_t x=s->words[RNG];x^=x<<13;x^=x>>17;x^=x<<5;s->words[RNG]=x;return x;}
static unsigned slots(unsigned pool){return pool==0?L3_SHOOTER_ENEMIES:pool==1?L3_SHOOTER_SHOTS:L3_SHOOTER_BONUSES;}
static L3ShooterEntity *array(L3ShooterState *s,unsigned pool)
{return pool==0?s->enemies:pool==1?s->shots:s->bonuses;}
static const L3ShooterEntity *carray(const L3ShooterState *s,unsigned pool)
{return pool==0?s->enemies:pool==1?s->shots:s->bonuses;}
static unsigned next_id(L3ShooterState *s)
{
    unsigned candidate=s->words[SERIAL],pool,i;int used;
    do{candidate=candidate%65535u+1u;used=0;
        for(pool=0;pool<3;++pool)for(i=0;i<slots(pool);++i)
            if(carray(s,pool)[i].words[EID]==candidate)used=1;
    }while(used);
    s->words[SERIAL]=candidate;return candidate;
}
static L3ShooterEntity *spawn(L3ShooterState *s,unsigned pool,unsigned kind,int x,int y,int vx,int vy,unsigned hp)
{
    unsigned i;L3ShooterEntity *a=array(s,pool);
    for(i=0;i<slots(pool);++i)if(!a[i].words[EK]){
        memset(&a[i],0,sizeof(a[i]));a[i].words[EK]=kind;a[i].words[EX]=(unsigned)x;a[i].words[EY]=(unsigned)y;
        a[i].words[EVX]=(unsigned)(vx+2048);a[i].words[EVY]=(unsigned)(vy+2048);a[i].words[EHP]=hp;a[i].words[EID]=next_id(s);return &a[i];}
    return NULL;
}
static void vanish(L3ShooterEntity *e){memset(e,0,sizeof(*e));}
static void finish(L3ShooterState *s,unsigned status){s->words[STATUS]=status;s->words[PHASE]=0;}
static void fire_player(L3ShooterState *s)
{
    int x=(int)s->words[PX],y=(int)s->words[PY]-FX(7);
    if(s->words[FIRE])return;
    if(s->words[DOUBLE]){
        spawn(s,1,L3_SHOOTER_PLAYER_SHOT,x-FX(3),y,0,-FX(4),1);
        spawn(s,1,L3_SHOOTER_PLAYER_SHOT,x+FX(3),y,0,-FX(4),1);
    }else spawn(s,1,L3_SHOOTER_PLAYER_SHOT,x,y,0,-FX(4),1);
    s->words[FIRE]=8;
}
static void damage(L3ShooterState *s)
{
    unsigned i;
    if(s->words[SHIELD] || s->words[STATUS]!=L3_MINI_RUNNING)return;
    if(--s->words[LIVES]==0){finish(s,L3_MINI_LOST);return;}
    s->words[SHIELD]=120;s->words[PX]=FX(80);s->words[PY]=FX(176);
    for(i=0;i<L3_SHOOTER_SHOTS;++i)if(s->shots[i].words[EK]==L3_SHOOTER_ENEMY_SHOT)vanish(&s->shots[i]);
}
static void kill_enemy(L3ShooterState *s,L3ShooterEntity *e)
{
    unsigned kind=e->words[EK];int x=(int)e->words[EX],y=(int)e->words[EY];
    vanish(e);++s->words[KILLS];s->words[SCORE]+=kind==L3_SHOOTER_BOSS?1000u:kind==L3_SHOOTER_DRIFTER?100u:150u;
    if(kind==L3_SHOOTER_BOSS){s->words[BOSSDEAD]=1;finish(s,L3_MINI_WON);return;}
    if(s->words[KILLS]%2u==0)spawn(s,2,L3_SHOOTER_SHIELD+random32(s)%3u,x,y,0,FX(1),1);
}
static void emit_wave(L3ShooterState *s)
{
    unsigned wave=s->words[WAVE],n=s->words[SPAWNED],limit=wave==1?3u:wave==2?4u:1u,kind;
    int x;
    if(s->words[CLOCK]){--s->words[CLOCK];return;}
    if(n>=limit)return;
    x=FX(wave==1?32u+48u*n:24u+36u*n);
    kind=wave==1?L3_SHOOTER_DRIFTER:(n%2u?L3_SHOOTER_SWEEPER:L3_SHOOTER_ZIGZAG);
    if(wave==3){kind=L3_SHOOTER_BOSS;x=FX(80);}
    if(spawn(s,0,kind,x,FX(wave==3?24:8),kind==L3_SHOOTER_DRIFTER?0:(n%2u?-192:192),wave==3?0:96,wave==3?24:2)){
        ++s->words[SPAWNED];++s->words[TOTAL];s->words[CLOCK]=60;
    }
}
static void enemies_tick(L3ShooterState *s)
{
    unsigned i;
    for(i=0;i<L3_SHOOTER_ENEMIES && s->words[STATUS]==L3_MINI_RUNNING;++i){L3ShooterEntity *e=&s->enemies[i];unsigned kind=e->words[EK];int x,y,vx,vy;
        if(!kind)continue;
        ++e->words[EAGE];vx=(int)e->words[EVX]-2048;vy=(int)e->words[EVY]-2048;
        if(kind==L3_SHOOTER_ZIGZAG && e->words[EAGE]%45u==0)vx=-vx;
        if(kind==L3_SHOOTER_SWEEPER && e->words[EAGE]%75u==0)vx=-vx;
        x=(int)e->words[EX]+vx;y=(int)e->words[EY]+vy;
        if(x<FX(16) || x>FX(144)){vx=-vx;x=clamp(x,FX(16),FX(144));}
        e->words[EVX]=(unsigned)(vx+2048);
        if(y>FX(188)){vanish(e);++s->words[ESCAPED];damage(s);continue;}
        e->words[EX]=(unsigned)x;e->words[EY]=(unsigned)y;
        if(e->words[EAGE]%(kind==L3_SHOOTER_BOSS?45u:90u)==0){
            int aim=clamp(((int)s->words[PX]-x)/64,-512,512);
            int down=(int)s->words[PY]>=y?FX(2):-FX(2);
            spawn(s,1,L3_SHOOTER_ENEMY_SHOT,x,y,aim,down,1);
            if(kind==L3_SHOOTER_BOSS){spawn(s,1,L3_SHOOTER_ENEMY_SHOT,x,y,aim-192,down,1);spawn(s,1,L3_SHOOTER_ENEMY_SHOT,x,y,aim+192,down,1);}
        }
        if(absolute(x-(int)s->words[PX])<FX(kind==L3_SHOOTER_BOSS?18:10) && absolute(y-(int)s->words[PY])<FX(10)){
            if(kind!=L3_SHOOTER_BOSS){vanish(e);++s->words[ESCAPED];}damage(s);
        }
    }
}
static void shots_tick(L3ShooterState *s)
{
    unsigned i,j;
    for(i=0;i<L3_SHOOTER_SHOTS && s->words[STATUS]==L3_MINI_RUNNING;++i){L3ShooterEntity *b=&s->shots[i];int x,y;
        if(!b->words[EK])continue;
        x=(int)b->words[EX]+(int)b->words[EVX]-2048;y=(int)b->words[EY]+(int)b->words[EVY]-2048;
        if(x<0 || y<0 || x>FX(160) || y>FX(192) || b->words[EAGE]>=1000){vanish(b);continue;}
        b->words[EX]=(unsigned)x;b->words[EY]=(unsigned)y;++b->words[EAGE];
        if(b->words[EK]==L3_SHOOTER_ENEMY_SHOT){
            if(absolute(x-(int)s->words[PX])<=FX(4) && absolute(y-(int)s->words[PY])<=FX(6)){vanish(b);damage(s);}
        }else for(j=0;j<L3_SHOOTER_ENEMIES;++j){L3ShooterEntity *e=&s->enemies[j];
            if(!e->words[EK])continue;
            if(absolute(x-(int)e->words[EX])<=FX(e->words[EK]==L3_SHOOTER_BOSS?14:6) && absolute(y-(int)e->words[EY])<=FX(8)){
                vanish(b);if(--e->words[EHP]==0)kill_enemy(s,e);break;
            }
        }
    }
}
static void bonuses_tick(L3ShooterState *s)
{
    unsigned i;
    for(i=0;i<L3_SHOOTER_BONUSES;++i){L3ShooterEntity *e=&s->bonuses[i];unsigned kind=e->words[EK];
        if(!kind)continue;
        e->words[EY]+=256;++e->words[EAGE];
        if(e->words[EY]>FX(192)){vanish(e);continue;}
        if(absolute((int)e->words[EX]-(int)s->words[PX])<=FX(8) && absolute((int)e->words[EY]-(int)s->words[PY])<=FX(8)){
            if(kind==L3_SHOOTER_SHIELD)s->words[SHIELD]=300;
            if(kind==L3_SHOOTER_HEART && s->words[LIVES]<3)++s->words[LIVES];
            if(kind==L3_SHOOTER_DOUBLE)s->words[DOUBLE]=360;
            ++s->words[PICKED];s->words[SCORE]+=50;vanish(e);
        }
    }
}
static void tick(L3ShooterState *s,uint32_t controls)
{
    int x=(int)s->words[PX],y=(int)s->words[PY];unsigned i,active=0,limit;
    s->words[TICKS]=add(s->words[TICKS],1);
    if(s->words[SHIELD])--s->words[SHIELD];
    if(s->words[DOUBLE])--s->words[DOUBLE];
    if(s->words[FIRE])--s->words[FIRE];
    if(controls&L3_MINI_LEFT)x-=512;
    if(controls&L3_MINI_RIGHT)x+=512;
    if(controls&L3_MINI_UP)y-=512;
    if(controls&L3_MINI_DOWN)y+=512;
    s->words[PX]=(unsigned)clamp(x,FX(8),FX(152));s->words[PY]=(unsigned)clamp(y,FX(8),FX(184));
    if(controls&L3_MINI_ACT)fire_player(s);
    emit_wave(s);enemies_tick(s);shots_tick(s);
    if(s->words[STATUS]!=L3_MINI_RUNNING)return;
    bonuses_tick(s);
    for(i=0;i<L3_SHOOTER_ENEMIES;++i)active+=s->enemies[i].words[EK]!=0;
    limit=s->words[WAVE]==1?3u:s->words[WAVE]==2?4u:1u;
    if(!active && s->words[SPAWNED]==limit && s->words[WAVE]<3){++s->words[WAVE];s->words[SPAWNED]=0;s->words[CLOCK]=60;}
}
int l3_shooter_init(L3ShooterState *s,uint32_t seed)
{
    L3ShooterState t;if(!s)return 0;memset(&t,0,sizeof(t));t.words[VER]=1;t.words[SEED]=seed;t.words[RNG]=seed^0x53544152u;
    if(!t.words[RNG])t.words[RNG]=1;
    t.words[WAVE]=1;t.words[LIVES]=3;t.words[SHIELD]=120;t.words[PX]=FX(80);t.words[PY]=FX(176);*s=t;return 1;
}
int l3_shooter_validate(const L3ShooterState *s)
{
    unsigned pool,i,j,other,ids[44],n=0,active=0,boss=0;
    if(!s || s->words[VER]!=1 || s->words[STATUS]>L3_MINI_LOST || !s->words[RNG] || s->words[PHASE]>=1000 || s->words[PHASE]%20u || s->words[WAVE]<1 || s->words[WAVE]>3 || s->words[CLOCK]>60 || s->words[SPAWNED]>(s->words[WAVE]==1?3u:s->words[WAVE]==2?4u:1u) || s->words[LIVES]>3 || s->words[SHIELD]>300 || s->words[DOUBLE]>360 || s->words[FIRE]>8 || s->words[PX]<FX(8) || s->words[PX]>FX(152) || s->words[PY]<FX(8) || s->words[PY]>FX(184) || s->words[SERIAL]>65535 || s->words[TOTAL]>8 || s->words[KILLS]>8 || s->words[ESCAPED]>7 || s->words[BOSSDEAD]>1 || s->words[PICKED]>3 || s->words[SCORE]>2200 || s->words[SCORE]%50u)return 0;
    for(i=22;i<32;++i)if(s->words[i])return 0;
    if((s->words[STATUS]==L3_MINI_WON)!=(s->words[BOSSDEAD]!=0) || (s->words[STATUS]==L3_MINI_LOST)!=(s->words[LIVES]==0) || (s->words[STATUS]!=L3_MINI_RUNNING && s->words[PHASE]))return 0;
    for(pool=0;pool<3;++pool)for(i=0;i<slots(pool);++i){const L3ShooterEntity *e=&carray(s,pool)[i];unsigned k=e->words[EK];
        if(!k){for(j=1;j<8;++j)if(e->words[j])return 0;continue;}
        if((pool==0 && (k<1 || k>4)) || (pool==1 && (k<5 || k>6)) || (pool==2 && (k<7 || k>9)))return 0;
        if(e->words[EX]>FX(160) || e->words[EY]>FX(192) || e->words[EVX]>4096 || e->words[EVY]>4096 || !e->words[EHP] || e->words[EHP]>(k==4?24u:pool==0?2u:1u) || !e->words[EID] || e->words[EID]>65535)return 0;
        if(pool==1 && e->words[EAGE]>1000)return 0;
        for(other=0;other<n;++other)if(ids[other]==e->words[EID])return 0;
        ids[n++]=e->words[EID];if(pool==0)++active;if(k==4)++boss;
    }
    if(active+s->words[KILLS]+s->words[ESCAPED]!=s->words[TOTAL] || boss>1 || (boss && s->words[WAVE]!=3) || (s->words[BOSSDEAD] && boss))return 0;
    if(s->words[TOTAL]!=s->words[SPAWNED]+(s->words[WAVE]==1?0u:s->words[WAVE]==2?3u:7u))return 0;
    return 1;
}
uint32_t l3_shooter_step(L3ShooterState *s,uint32_t pressed,uint32_t held,uint32_t dt)
{
    unsigned n,i,phase;
    if(!l3_shooter_validate(s) || ((pressed|held)&~L3_MINI_INPUT_MASK))return L3_MINI_EVENT_INVALID;
    if(pressed&L3_MINI_BACK)return L3_MINI_EVENT_EXIT;
    if(s->words[STATUS]!=L3_MINI_RUNNING)return 0;
    if(pressed&L3_MINI_ACT)fire_player(s);
    if(dt>250)dt=250;
    phase=s->words[PHASE]+dt*60u;n=phase/1000u;s->words[PHASE]=phase%1000u;
    for(i=0;i<n && s->words[STATUS]==L3_MINI_RUNNING;++i)tick(s,held);
    if(s->words[STATUS]!=L3_MINI_RUNNING)return L3_MINI_EVENT_CHANGED|(s->words[STATUS]==L3_MINI_WON?L3_MINI_EVENT_WON:L3_MINI_EVENT_LOST);
    return pressed || held || dt?L3_MINI_EVENT_CHANGED:0;
}
static void actor(L3ShooterActor *a,unsigned k,unsigned id,int x,int y,int vx,int vy,unsigned hp)
{
    a->kind=(uint8_t)k;a->id=(uint16_t)id;a->x256=x;a->y256=y;a->vx256=(int16_t)vx;a->vy256=(int16_t)vy;a->hp=(uint16_t)hp;
    a->half_width=(uint8_t)(k==4?13:k==5 || k==6?1:k==10?4:5);a->half_height=(uint8_t)(k==4?7:k==5 || k==6?2:5);
    a->color=(uint8_t)(k==10?11:k==5?10:k==6?12:k==4?13:k>=7?14:8+k);
}
int l3_shooter_view(const L3ShooterState *s,L3ShooterView *out)
{
    L3ShooterView v;unsigned pool,i;uint64_t elapsed;
    if(!out || !l3_shooter_validate(s))return 0;
    memset(&v,0,sizeof(v));actor(&v.actors[0],L3_SHOOTER_PLAYER,0,(int)s->words[PX],(int)s->words[PY],0,0,s->words[LIVES]);
    v.actors[0].flags=(uint8_t)((s->words[SHIELD]?1u:0u)|(s->words[DOUBLE]?2u:0u));v.actor_count=1;
    for(pool=0;pool<3;++pool)for(i=0;i<slots(pool);++i){const L3ShooterEntity *e=&carray(s,pool)[i];if(!e->words[EK])continue;
        actor(&v.actors[v.actor_count++],e->words[EK],e->words[EID],(int)e->words[EX],(int)e->words[EY],(int)e->words[EVX]-2048,(int)e->words[EVY]-2048,e->words[EHP]);
        if(e->words[EK]==L3_SHOOTER_BOSS)v.boss_hp=(uint16_t)e->words[EHP];}
    v.status=s->words[STATUS];v.score=s->words[SCORE];v.lives=(uint8_t)s->words[LIVES];v.wave=(uint8_t)s->words[WAVE];v.kills=(uint8_t)s->words[KILLS];v.escaped=(uint8_t)s->words[ESCAPED];
    v.shield_ticks=(uint16_t)s->words[SHIELD];v.double_ticks=(uint16_t)s->words[DOUBLE];elapsed=((uint64_t)s->words[TICKS]*1000u+s->words[PHASE])/60u;v.elapsed_ms=elapsed>UINT32_MAX?UINT32_MAX:(uint32_t)elapsed;
    v.title="Patrouille des cometes";v.help="Fleches: piloter. Action maintenue: tirer. Retour: sortir.";v.objective="Traverser deux vagues et vaincre le gardien des cometes avec 3 vies.";*out=v;return 1;
}
static void put32(uint8_t *p,uint32_t v){unsigned i;for(i=0;i<4;++i)p[i]=(uint8_t)(v>>(8u*i));}
static uint32_t get32(const uint8_t *p){return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static uint32_t checksum(const uint8_t *p){uint32_t h=2166136261u;unsigned i;for(i=0;i<L3_SHOOTER_SAVE_BYTES;++i)if(i<12 || i>=16){h^=p[i];h*=16777619u;}return h;}
size_t l3_shooter_encode(const L3ShooterState *s,void *out,size_t cap)
{
    uint8_t b[L3_SHOOTER_SAVE_BYTES];unsigned i,pool,j,pos=144;
    if(!l3_shooter_validate(s))return 0;
    if(!out)return sizeof(b);
    if(cap<sizeof(b))return 0;
    memcpy(b,"L3SH",4);put32(b+4,1);put32(b+8,1536);put32(b+12,0);
    for(i=0;i<32;++i)put32(b+16u+4u*i,s->words[i]);
    for(pool=0;pool<3;++pool)for(i=0;i<slots(pool);++i)for(j=0;j<8;++j){put32(b+pos,carray(s,pool)[i].words[j]);pos+=4;}
    put32(b+12,checksum(b));memcpy(out,b,sizeof(b));return sizeof(b);
}
int l3_shooter_decode(L3ShooterState *s,const void *in,size_t size)
{
    const uint8_t *b=(const uint8_t *)in;L3ShooterState t;unsigned i,pool,j,pos=144;
    if(!s || !b || size!=L3_SHOOTER_SAVE_BYTES || memcmp(b,"L3SH",4) || get32(b+4)!=1 || get32(b+8)!=1536 || get32(b+12)!=checksum(b))return 0;
    memset(&t,0,sizeof(t));for(i=0;i<32;++i)t.words[i]=get32(b+16u+4u*i);
    for(pool=0;pool<3;++pool)for(i=0;i<slots(pool);++i)for(j=0;j<8;++j){array(&t,pool)[i].words[j]=get32(b+pos);pos+=4;}
    if(!l3_shooter_validate(&t))return 0;
    *s=t;return 1;
}
int l3_shooter_demo_input(const L3ShooterState *s,uint32_t *pressed,uint32_t *held,uint32_t *dt)
{
    unsigned i;int target,best=-1,danger=0;
    if(!pressed || !held || !dt || !l3_shooter_validate(s) || s->words[STATUS]!=L3_MINI_RUNNING)return 0;
    target=(int)s->words[PX];
    for(i=0;i<L3_SHOOTER_ENEMIES;++i){const L3ShooterEntity *e=&s->enemies[i];if(!e->words[EK])continue;
        if((int)e->words[EY]>best){int frames=((int)s->words[PY]-(int)e->words[EY])/1024;best=(int)e->words[EY];target=(int)e->words[EX]+((int)e->words[EVX]-2048)*frames;}}
    target=clamp(target,FX(10),FX(150));
    if(!s->words[SHIELD])for(i=0;i<L3_SHOOTER_SHOTS;++i){const L3ShooterEntity *b=&s->shots[i];int x,y;
        if(b->words[EK]!=L3_SHOOTER_ENEMY_SHOT)continue;
        x=(int)b->words[EX];y=(int)b->words[EY];
        if(y<(int)s->words[PY]+FX(6) && y>(int)s->words[PY]-FX(32) && absolute(x-(int)s->words[PX])<FX(13)){
            target=(int)s->words[PX]+((int)s->words[PX]>FX(80)?-FX(24):FX(24));danger=1;break;}}
    *pressed=0;*held=L3_MINI_ACT;*dt=100;
    if(target>(int)s->words[PX]+256)*held|=L3_MINI_RIGHT;
    if(target<(int)s->words[PX]-256)*held|=L3_MINI_LEFT;
    if(!danger && best<0){for(i=0;i<L3_SHOOTER_BONUSES;++i)if(s->bonuses[i].words[EK]){
        target=(int)s->bonuses[i].words[EX];*held=L3_MINI_ACT;if(target>(int)s->words[PX]+256)*held|=L3_MINI_RIGHT;if(target<(int)s->words[PX]-256)*held|=L3_MINI_LEFT;break;}}
    return 1;
}
