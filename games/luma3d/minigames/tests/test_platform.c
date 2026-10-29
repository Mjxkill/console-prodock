#include "../l3_platform.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned checks;
#define C(x) do{++checks;if(!(x)){fprintf(stderr,"FAIL line%d: %s\n",__LINE__,#x);exit(1);}}while(0)
static uint32_t rnd(uint32_t *r){*r^=*r<<13;*r^=*r>>17;*r^=*r<<5;return *r;}
static void put32(uint8_t *p,uint32_t x){unsigned i;for(i=0;i<4;++i)p[i]=(uint8_t)(x>>(8u*i));}
static uint32_t hash(const uint8_t *p){unsigned i;uint32_t h=2166136261u;for(i=0;i<L3_PLATFORM_SAVE_BYTES;++i)if(i<12 || i>=16){h^=p[i];h*=16777619u;}return h;}
static void roundtrip(const L3PlatformState *s)
{
    L3PlatformState t;L3PlatformView v;uint8_t b[L3_PLATFORM_SAVE_BYTES];unsigned i;
    C(l3_platform_validate(s));C(l3_platform_encode(s,b,sizeof(b))==sizeof(b));C(l3_platform_decode(&t,b,sizeof(b)));C(!memcmp(s,&t,sizeof(t)));
    C(l3_platform_view(s,&v));C(v.actor_count<=11 && v.surface_count==7 && v.ladder_count==4 && v.lives<=3 && v.checkpoint_floor<=2);
    for(i=0;i<v.actor_count;++i)C(v.actors[i].x256>=0 && v.actors[i].x256<=160*256 && v.actors[i].y256>=0 && v.actors[i].y256<=160*256 && v.actors[i].z256>=0 && v.actors[i].z256<=64*256 && v.actors[i].color<16);
}
static void barrel(L3PlatformBarrel *b,unsigned id,unsigned floor,unsigned x,unsigned z)
{
    memset(b,0,sizeof(*b));b->words[0]=1;b->words[1]=x;b->words[2]=floor*32u*256u;b->words[3]=z;
    b->words[4]=floor%2u?2368:1728;b->words[5]=2048;b->words[6]=floor;b->words[7]=id;
}
static void floor1(L3PlatformState *s,unsigned x)
{C(l3_platform_init(s,1));s->words[9]=x*256u;s->words[10]=32*256;s->words[13]=1;s->words[17]=1;s->words[6]=100;C(l3_platform_validate(s));}
static void physics(void)
{
    L3PlatformState s;unsigned i,maximum=0;
    C(l3_platform_init(&s,1));C(!(l3_platform_step(&s,L3_MINI_ACT,L3_MINI_ACT,0)&L3_MINI_EVENT_INVALID));C(s.words[15]==1 && s.words[22]==1);roundtrip(&s);
    for(i=0;i<80;++i){C(!(l3_platform_step(&s,0,L3_MINI_ACT,17)&L3_MINI_EVENT_INVALID));if(s.words[10]>maximum)maximum=s.words[10];}
    C(maximum>0 && maximum<24*256 && s.words[10]==0 && s.words[15]==0 && s.words[22]==1);
    floor1(&s,90);C(!(l3_platform_step(&s,0,L3_MINI_LEFT,100)&L3_MINI_EVENT_INVALID));C(s.words[15]==1 && s.words[10]<32*256);
    for(i=0;i<10 && s.words[15];++i)C(!(l3_platform_step(&s,0,0,100)&L3_MINI_EVENT_INVALID));
    C(s.words[13]==0 && s.words[10]==0 && s.words[7]==3);roundtrip(&s);
    floor1(&s,101);C(!(l3_platform_step(&s,L3_MINI_ACT,L3_MINI_LEFT,100)&L3_MINI_EVENT_INVALID));
    for(i=0;i<3;++i)C(!(l3_platform_step(&s,0,L3_MINI_LEFT,100)&L3_MINI_EVENT_INVALID));
    C(s.words[13]==1 && !s.words[15] && s.words[9]<=72*256 && s.words[10]==32*256);roundtrip(&s);
    C(l3_platform_init(&s,1));s.words[9]=128*256;
    C(!(l3_platform_step(&s,0,L3_MINI_UP,250)&L3_MINI_EVENT_INVALID));C(s.words[14]==1 && s.words[10]==15*256);roundtrip(&s);
    C(!(l3_platform_step(&s,0,L3_MINI_DOWN,250)&L3_MINI_EVENT_INVALID));C(!s.words[14] && s.words[10]==0 && s.words[13]==0);roundtrip(&s);
    C(l3_platform_init(&s,1));C(!(l3_platform_step(&s,0,L3_MINI_UP,250)&L3_MINI_EVENT_INVALID));C(s.words[11]<32*256 && s.words[10]==0);
    puts("PASS platform physics: real jump arc/gravity, held jump does not repeat, gap fall, successful gap jump, ladder up/down and depth movement");
}
static void checkpoint_pool(void)
{
    L3PlatformState s;unsigned i,n=0;C(l3_platform_init(&s,1));
    while(s.words[16]!=2){uint32_t p,h,dt;C(l3_platform_demo_input(&s,&p,&h,&dt));C(!(l3_platform_step(&s,p,h,dt)&L3_MINI_EVENT_INVALID));C(++n<500);}
    C(s.words[13]==2 && s.words[6]==450);roundtrip(&s);
    memset(s.barrels,0,sizeof(s.barrels));s.words[8]=0;s.words[18]=90;s.words[19]=1;s.words[20]=1;s.words[21]=0;
    barrel(&s.barrels[0],1,2,s.words[9],s.words[11]);C(l3_platform_validate(&s));
    C(!(l3_platform_step(&s,0,0,17)&L3_MINI_EVENT_INVALID));C(s.words[7]==2 && s.words[16]==2 && s.words[13]==2 && s.words[9]==32*256 && s.words[10]==64*256 && s.words[8]==120);roundtrip(&s);
    C(!(l3_platform_step(&s,0,0,100)&L3_MINI_EVENT_INVALID));C(s.words[7]==2 && s.words[6]==450);
    C(l3_platform_init(&s,1));for(i=0;i<8;++i)barrel(&s.barrels[i],i+1,4,144*256,16*256);
    s.words[19]=8;s.words[20]=8;C(l3_platform_validate(&s));
    C(!(l3_platform_step(&s,0,0,17)&L3_MINI_EVENT_INVALID));C(s.words[20]==8 && s.words[19]==8);roundtrip(&s);
    puts("PASS platform checkpoint respawn/reward once, post-hit protection and saturated8-barrel pool");
}
static void codec(void)
{
    L3PlatformState s,t,before;uint8_t good[L3_PLATFORM_SAVE_BYTES+1],bad[L3_PLATFORM_SAVE_BYTES];unsigned i;
    C(l3_platform_init(&s,55));s.words[9]=128*256;C(!(l3_platform_step(&s,0,L3_MINI_UP,117)&L3_MINI_EVENT_INVALID));roundtrip(&s);
    C(l3_platform_encode(&s,good,sizeof(good))==L3_PLATFORM_SAVE_BYTES);memset(&t,0xa5,sizeof(t));before=t;
    for(i=0;i<L3_PLATFORM_SAVE_BYTES;++i){C(!l3_platform_decode(&t,good,i));C(!memcmp(&t,&before,sizeof(t)));
        memcpy(bad,good,sizeof(bad));bad[i]^=1;C(!l3_platform_decode(&t,bad,sizeof(bad)));C(!memcmp(&t,&before,sizeof(t)));}
    C(!l3_platform_decode(&t,good,sizeof(good)));C(!memcmp(&t,&before,sizeof(t)));C(!l3_platform_validate(NULL));
    {static const unsigned offsets[]={4,8,16,36,52,68,140,148};
        for(i=0;i<sizeof(offsets)/sizeof(offsets[0]);++i){memcpy(bad,good,sizeof(bad));put32(bad+offsets[i],UINT32_MAX);put32(bad+12,hash(bad));C(!l3_platform_decode(&t,bad,sizeof(bad)));C(!memcmp(&t,&before,sizeof(t)));}}
    puts("PASS platform codec: ladder/subtick exact resume and every truncated length/corrupt byte rejected transactionally");
}
static void wins(const char *trace)
{
    unsigned seed;
    for(seed=0;seed<64;++seed){L3PlatformState s;unsigned n=0;FILE *f=NULL;C(l3_platform_init(&s,seed));
        if(trace && seed==1){f=fopen(trace,"w");C(f!=NULL);fprintf(f,"L3PLATFORMTRACE 1 1\n");}
        while(s.words[1]==L3_MINI_RUNNING){uint32_t p,h,dt;L3PlatformState before=s,t;uint8_t save[L3_PLATFORM_SAVE_BYTES];
            C(l3_platform_demo_input(&s,&p,&h,&dt));C(!memcmp(&s,&before,sizeof(s)));if(f)fprintf(f,"%u %u %u\n",p,h,dt);
            C(!(l3_platform_step(&s,p,h,dt)&L3_MINI_EVENT_INVALID));C(l3_platform_validate(&s));C(++n<5000);
            if(n%17u==0){C(l3_platform_encode(&before,save,sizeof(save))==sizeof(save));C(l3_platform_decode(&t,save,sizeof(save)));C(!(l3_platform_step(&t,p,h,dt)&L3_MINI_EVENT_INVALID));C(!memcmp(&t,&s,sizeof(t)));}}
        C(s.words[1]==L3_MINI_WON && s.words[23]==1 && s.words[16]==2 && s.words[22]>=2);roundtrip(&s);
        if(f){C(!fclose(f));printf("PASS platform witness seed1 frames=%u jumps=%u lives=%u score=%u\n",n,s.words[22],s.words[7],s.words[6]);}
        {L3PlatformState before=s;C(!l3_platform_step(&s,L3_MINI_ACT,0,250));C(!memcmp(&s,&before,sizeof(s)));}
    }
    puts("PASS platform64 seeded victories by ordinary controls, jumps, ladders and checkpoint rules");
}
static void timing(void)
{
    static const unsigned chunks[]={1,5,16,33,100,250};unsigned c;
    for(c=0;c<sizeof(chunks)/sizeof(chunks[0]);++c){L3PlatformState a,b;unsigned n=0;C(l3_platform_init(&a,1));b=a;
        while(a.words[1]==L3_MINI_RUNNING){uint32_t p,h,dt,left;C(l3_platform_demo_input(&a,&p,&h,&dt));left=dt;
            C(!(l3_platform_step(&a,p,h,dt)&L3_MINI_EVENT_INVALID));C(!(l3_platform_step(&b,p,h,0)&L3_MINI_EVENT_INVALID));
            while(left){unsigned step=left<chunks[c]?left:chunks[c];C(!(l3_platform_step(&b,0,h,step)&L3_MINI_EVENT_INVALID));left-=step;}
            C(!memcmp(&a,&b,sizeof(a)));C(++n<5000);}
    }
    puts("PASS platform exact states at6 call frequencies with identical jump edges and held timelines");
}
static void loss_random(void)
{
    L3PlatformState s,initial,before;unsigned i;uint32_t r=0x12343412;
    C(l3_platform_init(&s,1));initial=s;
    for(i=0;i<10000 && s.words[1]==L3_MINI_RUNNING;++i)C(!(l3_platform_step(&s,0,0,250)&L3_MINI_EVENT_INVALID));
    C(s.words[1]==L3_MINI_LOST);roundtrip(&s);before=s;C(l3_platform_step(&s,L3_MINI_BACK,0,250)==L3_MINI_EVENT_EXIT);C(!memcmp(&s,&before,sizeof(s)));
    C(l3_platform_init(&s,1));C(!memcmp(&s,&initial,sizeof(s)));
    for(i=0;i<50000;++i){uint32_t p=rnd(&r)%128u,h=rnd(&r)%128u,dt=rnd(&r)%300u;before=s;
        C(!(l3_platform_step(&s,p,h,dt)&L3_MINI_EVENT_INVALID));C(l3_platform_validate(&s));if(p&L3_MINI_BACK)C(!memcmp(&s,&before,sizeof(s)));
        if(i%97u==0)roundtrip(&s);
        if(s.words[1]!=L3_MINI_RUNNING)C(l3_platform_init(&s,rnd(&r)));}
    puts("PASS platform natural loss/BACK/restart and50000 bounded randomized frames");
}
static void replay(const char *path)
{
    L3PlatformState s;FILE *f;char magic[32];unsigned version,seed,p,h,dt;
    if(!path)return;
    f=fopen(path,"r");C(f!=NULL);C(fscanf(f,"%31s %u %u",magic,&version,&seed)==3);C(!strcmp(magic,"L3PLATFORMTRACE") && version==1);C(l3_platform_init(&s,seed));
    while(fscanf(f,"%u %u %u",&p,&h,&dt)==3)C(!(l3_platform_step(&s,p,h,dt)&L3_MINI_EVENT_INVALID));
    C(feof(f));C(!fclose(f));C(s.words[1]==L3_MINI_WON);puts("PASS platform recorded trace replay without adviser");
}
int main(int argc,char **argv)
{
    C(sizeof(L3PlatformState)==384);physics();checkpoint_pool();codec();wins(argc>1?argv[1]:NULL);timing();loss_random();replay(argc>1?argv[1]:NULL);
    printf("PASS platform all checks=%u state=%lu save=%u\n",checks,(unsigned long)sizeof(L3PlatformState),L3_PLATFORM_SAVE_BYTES);return 0;
}
