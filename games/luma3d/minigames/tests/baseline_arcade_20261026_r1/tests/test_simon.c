#include "../l3_simon.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned checks;
#define C(x) do{++checks;if(!(x)){fprintf(stderr,"FAIL line%d: %s\n",__LINE__,#x);exit(1);}}while(0)
static const unsigned keys[4]={1,8,2,4};
static uint32_t rnd(uint32_t *r){*r^=*r<<13;*r^=*r>>17;*r^=*r<<5;return *r;}
static void savecheck(const L3SimonState *s)
{
    uint8_t b[L3_SIMON_SAVE_BYTES];L3SimonState t;
    C(l3_simon_encode(s,b,sizeof(b))==sizeof(b));C(l3_simon_decode(&t,b,sizeof(b)));C(!memcmp(s,&t,sizeof(t)));
}
static void wait_input(L3SimonState *s)
{
    L3SimonView v;unsigned n=0;
    do{C(l3_simon_view(s,&v));if(v.phase==L3_SIMON_INPUT)return;
        C(!(l3_simon_step(s,0,15,v.phase_ms>250?250:v.phase_ms)&L3_MINI_EVENT_INVALID));C(++n<100);
    }while(1);
}
static void rules(void)
{
    L3SimonState s,before,t;L3SimonView v;unsigned color,i;
    C(l3_simon_init(&s,1));before=s;C(!l3_simon_step(&s,15,15,0));C(!memcmp(&s,&before,sizeof(s)));
    wait_input(&s);before=s;C(l3_simon_step(&s,0,15,250)==L3_MINI_EVENT_CHANGED);C(s.words[8]==0 && s.words[1]==L3_MINI_RUNNING);
    color=s.sequence[0];C(l3_simon_step(&s,keys[(color+1)%4],0,0)==(L3_MINI_EVENT_CHANGED|L3_MINI_EVENT_LOST));
    C(l3_simon_validate(&s));savecheck(&s);before=s;C(!l3_simon_step(&s,keys[color],0,250));C(!memcmp(&s,&before,sizeof(s)));
    C(l3_simon_step(&s,L3_MINI_BACK|15,15,250)==L3_MINI_EVENT_EXIT);C(!memcmp(&s,&before,sizeof(s)));
    C(l3_simon_init(&s,1));wait_input(&s);C(!(l3_simon_step(&s,keys[s.sequence[0]],0,0)&L3_MINI_EVENT_INVALID));
    wait_input(&s);C(s.words[7]==2);
    C(!(l3_simon_step(&s,keys[s.sequence[0]],keys[s.sequence[0]],0)&L3_MINI_EVENT_INVALID));
    C(s.words[8]==1);savecheck(&s);
    for(i=0;i<10;++i)C(!(l3_simon_step(&s,0,keys[s.sequence[0]],25)&L3_MINI_EVENT_INVALID));
    C(s.words[8]==1 && s.words[1]==L3_MINI_RUNNING);C(l3_simon_view(&s,&v));C(v.active_color==4);
    /* Two simultaneous color fronts are an ambiguous response and lose. */
    t=s;C(l3_simon_step(&t,3,0,0)&L3_MINI_EVENT_LOST);savecheck(&t);
    /* Explicit wrong order on a two-note round with distinct colors. */
    for(i=0;i<100;++i){C(l3_simon_init(&s,i));if(s.sequence[0]!=s.sequence[1])break;}C(i<100);
    wait_input(&s);C(!(l3_simon_step(&s,keys[s.sequence[0]],0,0)&L3_MINI_EVENT_INVALID));wait_input(&s);
    C(l3_simon_step(&s,keys[s.sequence[1]],0,0)&L3_MINI_EVENT_LOST);
    puts("PASS Simon errors: wrong color/order, simultaneous fronts, held button ignored across demonstration/input, frozen loss/BACK");
}
static void codec(void)
{
    L3SimonState s,t,before;uint8_t b[L3_SIMON_SAVE_BYTES+1],bad[L3_SIMON_SAVE_BYTES];unsigned n,phase_seen=0;
    C(l3_simon_init(&s,33));
    for(n=0;n<2000 && s.words[1]==L3_MINI_RUNNING;++n){uint32_t p,h,dt;
        phase_seen|=1u<<s.words[5];savecheck(&s);C(l3_simon_demo_input(&s,&p,&h,&dt));
        if(dt>1)dt/=2;
        C(!(l3_simon_step(&s,p,h,dt)&L3_MINI_EVENT_INVALID));}
    C(s.words[1]==L3_MINI_WON);C((phase_seen&31u)==31u);savecheck(&s);
    C(l3_simon_init(&s,33));C(!(l3_simon_step(&s,0,0,250)&L3_MINI_EVENT_INVALID));
    C(l3_simon_encode(&s,b,sizeof(b))==L3_SIMON_SAVE_BYTES);memset(&t,0x5a,sizeof(t));before=t;
    for(n=0;n<L3_SIMON_SAVE_BYTES;++n){C(!l3_simon_decode(&t,b,n));C(!memcmp(&t,&before,sizeof(t)));
        memcpy(bad,b,sizeof(bad));bad[n]^=1;C(!l3_simon_decode(&t,bad,sizeof(bad)));C(!memcmp(&t,&before,sizeof(t)));}
    C(!l3_simon_decode(&t,b,sizeof(b)));C(!memcmp(&t,&before,sizeof(t)));
    puts("PASS Simon codec: resume in every phase, truncated/corrupt/incompatible-length saves rejected transactionally");
}
static void wins_timing(const char *trace)
{
    static const unsigned chunks[]={1,5,16,33,100,250};unsigned seed,c;
    for(seed=0;seed<64;++seed){L3SimonState reference;
        for(c=0;c<sizeof(chunks)/sizeof(chunks[0]);++c){L3SimonState s;unsigned n=0,edges=0;FILE *f=NULL;
            C(l3_simon_init(&s,seed));
            if(trace && seed==1 && c==5){f=fopen(trace,"w");C(f!=NULL);fprintf(f,"L3SIMONTRACE 1 1\n");}
            while(s.words[1]==L3_MINI_RUNNING){uint32_t p,h,dt;L3SimonState before=s;C(l3_simon_demo_input(&s,&p,&h,&dt));C(!memcmp(&s,&before,sizeof(s)));
                if(p){C(!(l3_simon_step(&s,p,h,0)&L3_MINI_EVENT_INVALID));++edges;if(f)fprintf(f,"%u 0 0\n",p);}
                while(dt){unsigned step=dt<chunks[c]?dt:chunks[c];C(!(l3_simon_step(&s,0,0,step)&L3_MINI_EVENT_INVALID));dt-=step;if(f)fprintf(f,"0 0 %u\n",step);}
                C(l3_simon_validate(&s));C(++n<400);}
            C(s.words[1]==L3_MINI_WON && edges==36 && s.words[4]==35400);savecheck(&s);
            if(c==0)reference=s;else C(!memcmp(&s,&reference,sizeof(s)));
            if(f)C(!fclose(f));
        }
    }
    puts("PASS Simon 64 seeded victories:36 ordinary color edges,35400ms; identical states across6 call frequencies");
}
static void random_inputs(void)
{
    L3SimonState s;uint32_t r=0x6d686361;unsigned i;C(l3_simon_init(&s,0));
    for(i=0;i<20000;++i){L3SimonState before=s;uint32_t p=rnd(&r)%128u,h=rnd(&r)%128u,dt=rnd(&r)%300u;
        C(!(l3_simon_step(&s,p,h,dt)&L3_MINI_EVENT_INVALID));C(l3_simon_validate(&s));
        if(p&L3_MINI_BACK)C(!memcmp(&s,&before,sizeof(s)));
        if(i%53u==0)savecheck(&s);
        if(s.words[1]!=L3_MINI_RUNNING)C(l3_simon_init(&s,rnd(&r)));
    }
    puts("PASS Simon 20000 bounded randomized input/hold/time frames");
}
int main(int argc,char **argv)
{
    C(sizeof(L3SimonState)<=4096);rules();codec();wins_timing(argc>1?argv[1]:NULL);random_inputs();
    printf("PASS Simon all checks=%u state=%lu save=%u\n",checks,(unsigned long)sizeof(L3SimonState),L3_SIMON_SAVE_BYTES);return 0;
}
