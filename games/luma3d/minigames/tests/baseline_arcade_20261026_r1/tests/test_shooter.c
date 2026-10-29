#include "../l3_shooter.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned checks;
#define C(x) do{++checks;if(!(x)){fprintf(stderr,"FAIL line%d: %s\n",__LINE__,#x);exit(1);}}while(0)
static uint32_t rnd(uint32_t *r){*r^=*r<<13;*r^=*r>>17;*r^=*r<<5;return *r;}
static void roundtrip(const L3ShooterState *s)
{
    L3ShooterState t;uint8_t b[L3_SHOOTER_SAVE_BYTES];L3ShooterView v;unsigned i;
    C(l3_shooter_validate(s));C(l3_shooter_encode(s,b,sizeof(b))==sizeof(b));C(l3_shooter_decode(&t,b,sizeof(b)));C(!memcmp(s,&t,sizeof(t)));
    C(l3_shooter_view(s,&v));C(v.actor_count<=L3_SHOOTER_ACTORS && v.lives<=3 && v.wave>=1 && v.wave<=3);
    for(i=0;i<v.actor_count;++i){C(v.actors[i].color<16 && v.actors[i].kind>=1 && v.actors[i].kind<=L3_SHOOTER_PLAYER);C(v.actors[i].x256>=0 && v.actors[i].x256<=160*256 && v.actors[i].y256>=0 && v.actors[i].y256<=192*256);}
}
static void entity(L3ShooterEntity *e,unsigned kind,unsigned id,unsigned x,unsigned y,int vx,int vy,unsigned hp)
{
    memset(e,0,sizeof(*e));e->words[0]=kind;e->words[1]=x*256u;e->words[2]=y*256u;e->words[3]=(unsigned)(vx+2048);e->words[4]=(unsigned)(vy+2048);e->words[5]=hp;e->words[7]=id;
}
static void rules(void)
{
    L3ShooterState s,before;unsigned i;
    C(l3_shooter_init(&s,1));
    for(i=0;i<L3_SHOOTER_SHOTS;++i)entity(&s.shots[i],L3_SHOOTER_PLAYER_SHOT,i+1,80,20,0,-1024,1);
    s.words[18]=32;C(l3_shooter_validate(&s));before=s;
    C(!(l3_shooter_step(&s,L3_MINI_ACT,L3_MINI_ACT,0)&L3_MINI_EVENT_INVALID));C(!memcmp(s.shots,before.shots,sizeof(s.shots)));C(s.words[13]==8);roundtrip(&s);
    C(!(l3_shooter_step(&s,0,L3_MINI_ACT,250)&L3_MINI_EVENT_INVALID));roundtrip(&s);
    C(l3_shooter_init(&s,1));s.words[8]=60;s.words[9]=1;s.words[19]=1;s.words[18]=3;
    entity(&s.enemies[0],L3_SHOOTER_DRIFTER,1,80,100,0,0,1);
    entity(&s.shots[0],L3_SHOOTER_PLAYER_SHOT,2,80,104,0,-1024,1);
    entity(&s.shots[1],L3_SHOOTER_PLAYER_SHOT,3,80,104,0,-1024,1);
    C(l3_shooter_validate(&s));C(!(l3_shooter_step(&s,0,0,17)&L3_MINI_EVENT_INVALID));C(s.words[10]==1 && s.words[6]==100);roundtrip(&s);
    C(!(l3_shooter_step(&s,0,0,17)&L3_MINI_EVENT_INVALID));C(s.words[10]==1 && s.words[6]==100);
    C(l3_shooter_init(&s,1));s.words[12]=0;s.words[18]=1;
    entity(&s.shots[0],L3_SHOOTER_ENEMY_SHOT,1,80,174,0,512,1);
    C(!(l3_shooter_step(&s,0,0,17)&L3_MINI_EVENT_INVALID));C(s.words[11]==2 && s.words[12]==120);
    C(!(l3_shooter_step(&s,0,0,250)&L3_MINI_EVENT_INVALID));C(s.words[11]==2);roundtrip(&s);
    C(l3_shooter_init(&s,1));s.words[11]=2;s.words[18]=1;
    entity(&s.bonuses[0],L3_SHOOTER_HEART,1,80,175,0,256,1);
    C(!(l3_shooter_step(&s,0,0,17)&L3_MINI_EVENT_INVALID));C(s.words[11]==3 && s.words[6]==50 && s.words[21]==1);
    C(!(l3_shooter_step(&s,0,0,17)&L3_MINI_EVENT_INVALID));C(s.words[11]==3 && s.words[6]==50 && s.words[21]==1);roundtrip(&s);
    puts("PASS shooter pools/collisions: saturated32-shot pool, single kill reward with2 impacts, single life loss/grace, single heart pickup");
}
static void codec(void)
{
    L3ShooterState s,t,before;uint8_t good[L3_SHOOTER_SAVE_BYTES+1],bad[L3_SHOOTER_SAVE_BYTES];unsigned i;
    C(l3_shooter_init(&s,55));C(!(l3_shooter_step(&s,0,L3_MINI_ACT|L3_MINI_LEFT,117)&L3_MINI_EVENT_INVALID));roundtrip(&s);
    C(l3_shooter_encode(&s,good,sizeof(good))==L3_SHOOTER_SAVE_BYTES);memset(&t,0xa5,sizeof(t));before=t;
    for(i=0;i<L3_SHOOTER_SAVE_BYTES;++i){C(!l3_shooter_decode(&t,good,i));C(!memcmp(&t,&before,sizeof(t)));
        memcpy(bad,good,sizeof(bad));bad[i]^=1;C(!l3_shooter_decode(&t,bad,sizeof(bad)));C(!memcmp(&t,&before,sizeof(t)));}
    C(!l3_shooter_decode(&t,good,sizeof(good)));C(!memcmp(&t,&before,sizeof(t)));
    C(!l3_shooter_validate(NULL));C(!l3_shooter_demo_input(NULL,NULL,NULL,NULL));
    puts("PASS shooter codec: exact fractional-time resume, every truncated length and corrupt byte rejected transactionally");
}
static void wins(const char *trace)
{
    unsigned seed;
    for(seed=0;seed<64;++seed){L3ShooterState s;unsigned n=0;FILE *f=NULL;C(l3_shooter_init(&s,seed));
        if(trace && seed==1){f=fopen(trace,"w");C(f!=NULL);fprintf(f,"L3SHOOTERTRACE 1 1\n");}
        while(s.words[1]==L3_MINI_RUNNING){uint32_t p,h,dt;L3ShooterState before=s,t;uint8_t save[L3_SHOOTER_SAVE_BYTES];
            C(l3_shooter_demo_input(&s,&p,&h,&dt));C(!memcmp(&s,&before,sizeof(s)));if(f)fprintf(f,"%u %u %u\n",p,h,dt);
            C(!(l3_shooter_step(&s,p,h,dt)&L3_MINI_EVENT_INVALID));C(l3_shooter_validate(&s));C(++n<5000);
            if(n%17u==0){C(l3_shooter_encode(&before,save,sizeof(save))==sizeof(save));C(l3_shooter_decode(&t,save,sizeof(save)));C(!(l3_shooter_step(&t,p,h,dt)&L3_MINI_EVENT_INVALID));C(!memcmp(&t,&s,sizeof(t)));}}
        C(s.words[1]==L3_MINI_WON && s.words[20]==1);roundtrip(&s);
        if(f){C(!fclose(f));printf("PASS shooter command witness seed1 frames=%u kills=%u lives=%u score=%u\n",n,s.words[10],s.words[11],s.words[6]);}
        {L3ShooterState before=s;C(!l3_shooter_step(&s,L3_MINI_ACT,0,250));C(!memcmp(&s,&before,sizeof(s)));}
    }
    puts("PASS shooter64 seeded victories through ordinary movement/fire, waves and boss rules");
}
static void timing(void)
{
    static const unsigned chunks[]={1,5,16,33,100,250};unsigned c;
    for(c=0;c<sizeof(chunks)/sizeof(chunks[0]);++c){L3ShooterState a,b;unsigned n=0;C(l3_shooter_init(&a,1));b=a;
        while(a.words[1]==L3_MINI_RUNNING){uint32_t p,h,dt,left;C(l3_shooter_demo_input(&a,&p,&h,&dt));left=dt;
            C(!(l3_shooter_step(&a,p,h,dt)&L3_MINI_EVENT_INVALID));
            C(!(l3_shooter_step(&b,p,h,0)&L3_MINI_EVENT_INVALID));
            while(left){unsigned step=left<chunks[c]?left:chunks[c];C(!(l3_shooter_step(&b,0,h,step)&L3_MINI_EVENT_INVALID));left-=step;}
            C(!memcmp(&a,&b,sizeof(a)));C(++n<5000);}
    }
    puts("PASS shooter exact states at6 call frequencies with identical held-control timelines");
}
static void loss_random(void)
{
    L3ShooterState s,initial,before;unsigned i;uint32_t r=0x12343412;
    C(l3_shooter_init(&s,1));initial=s;
    for(i=0;i<1000 && s.words[1]==L3_MINI_RUNNING;++i)C(!(l3_shooter_step(&s,0,0,250)&L3_MINI_EVENT_INVALID));
    C(s.words[1]==L3_MINI_LOST);roundtrip(&s);before=s;C(l3_shooter_step(&s,L3_MINI_BACK,0,250)==L3_MINI_EVENT_EXIT);C(!memcmp(&s,&before,sizeof(s)));
    C(l3_shooter_init(&s,1));C(!memcmp(&s,&initial,sizeof(s)));
    for(i=0;i<50000;++i){uint32_t p=rnd(&r)%128u,h=rnd(&r)%128u,dt=rnd(&r)%300u;before=s;
        C(!(l3_shooter_step(&s,p,h,dt)&L3_MINI_EVENT_INVALID));C(l3_shooter_validate(&s));if(p&L3_MINI_BACK)C(!memcmp(&s,&before,sizeof(s)));
        if(i%97u==0)roundtrip(&s);
        if(s.words[1]!=L3_MINI_RUNNING)C(l3_shooter_init(&s,rnd(&r)));}
    puts("PASS shooter loss/BACK/restart and50000 bounded randomized frames");
}
int main(int argc,char **argv)
{
    C(sizeof(L3ShooterState)==1536);rules();codec();wins(argc>1?argv[1]:NULL);timing();loss_random();
    printf("PASS shooter all checks=%u state=%lu save=%u\n",checks,(unsigned long)sizeof(L3ShooterState),L3_SHOOTER_SAVE_BYTES);return 0;
}
