#include "../l3_minigames.h"
#include "../l3_mini_actors.h"

#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Private layout is used only for adversarial codec cases and rule fixtures. */
enum { V,K,ST,SEED,RNG,TICKS,MOVES,SCORE,GOAL,W,H,PHASE };
static unsigned checks;
#define CHECK(c) do { ++checks; if (!(c)) { \
    fprintf(stderr,"FAIL %s:%d: %s\n",__FILE__,__LINE__,#c); exit(1); } } while(0)

static uint32_t rnd(uint32_t *r)
{ *r^=*r<<13;*r^=*r>>17;*r^=*r<<5;return *r; }
static uint32_t hash(const uint8_t *p)
{
    unsigned i;uint32_t h=2166136261u;
    for(i=0;i<L3_MINI_SAVE_BYTES;++i)if(i<12 || i>=16){h^=p[i];h*=16777619u;}
    return h;
}
static void put32(uint8_t *p,uint32_t v)
{ unsigned i;for(i=0;i<4;++i)p[i]=(uint8_t)(v>>(8u*i)); }
static void roundtrip(const L3MiniState *s)
{
    uint8_t a[L3_MINI_SAVE_BYTES],b[L3_MINI_SAVE_BYTES];L3MiniState t;
    memset(&t,0xa5,sizeof(t));
    CHECK(l3_mini_validate(s));CHECK(l3_mini_encode(s,NULL,0)==sizeof(a));
    CHECK(l3_mini_encode(s,a,sizeof(a))==sizeof(a));
    CHECK(l3_mini_decode(&t,a,sizeof(a)));CHECK(memcmp(s,&t,sizeof(t))==0);
    CHECK(l3_mini_encode(&t,b,sizeof(b))==sizeof(b));CHECK(memcmp(a,b,sizeof(a))==0);
}
static void check_view(const L3MiniState *s)
{
    unsigned x,y;L3MiniView v;
    CHECK(l3_mini_view(s,&v));CHECK(v.width>0 && v.width<=20 && v.height>0 && v.height<=20);
    CHECK(v.title && v.help && v.objective);CHECK(v.status<=L3_MINI_LOST);
    for(y=0;y<20;++y)for(x=0;x<20;++x){const L3MiniCell *c=&v.cells[y*20u+x];
        CHECK(c->color<16 && c->kind<=L3_MINI_CELL_FINISH && c->flags<16);
        if(x>=v.width || y>=v.height)CHECK(c->kind==0 && c->value==0 && c->flags==0);
    }
    if(v.kind==L3_MINI_MAZE){L3MiniActors a;L3MiniState before=*s;unsigned i;
        CHECK(l3_mini_actors(s,&a));CHECK(a.count==3 && a.progress==v.progress && a.target==v.target);
        CHECK(a.player_tick<6 && a.enemy_tick<14 && a.next_direction<=4);
        for(i=0;i<3;++i){CHECK(a.actors[i].x256/256u<v.width && a.actors[i].y256/256u<v.height);
            CHECK(a.actors[i].x256%256u==128 && a.actors[i].y256%256u==128 && a.actors[i].direction<=4);}
        CHECK(a.actors[0].x256/256u==s->data[0] && a.actors[0].y256/256u==s->data[1]);
        CHECK(memcmp(&before,s,sizeof(before))==0);
    }else{L3MiniActors a,before;memset(&a,0x3c,sizeof(a));before=a;
        CHECK(!l3_mini_actors(s,&a));CHECK(memcmp(&a,&before,sizeof(a))==0);}
}
static void codec(void)
{
    unsigned k,i;uint8_t bytes[L3_MINI_SAVE_BYTES+1],bad[L3_MINI_SAVE_BYTES+1];
    for(k=0;k<5;++k){L3MiniState s,t,before;
        CHECK(l3_mini_init(&s,(L3MiniKind)k,12345));roundtrip(&s);
        CHECK(l3_mini_encode(&s,bytes,sizeof(bytes))==L3_MINI_SAVE_BYTES);
        CHECK(bytes[0]=='L' && bytes[1]=='3' && bytes[2]=='M' && bytes[3]=='G');
        CHECK(bytes[4]==1 && bytes[5]==0 && bytes[8]==0xe0 && bytes[9]==3);
        memset(&t,0x7c,sizeof(t));before=t;
        for(i=0;i<L3_MINI_SAVE_BYTES;++i){CHECK(!l3_mini_decode(&t,bytes,i));CHECK(memcmp(&t,&before,sizeof(t))==0);}
        CHECK(!l3_mini_decode(&t,bytes,sizeof(bytes)));CHECK(memcmp(&t,&before,sizeof(t))==0);
        for(i=0;i<L3_MINI_SAVE_BYTES;++i){memcpy(bad,bytes,L3_MINI_SAVE_BYTES);bad[i]^=1u;
            CHECK(!l3_mini_decode(&t,bad,L3_MINI_SAVE_BYTES));CHECK(memcmp(&t,&before,sizeof(t))==0);}
        /* Malformed data WITH a repaired checksum must also be refused. */
        {static const unsigned offsets[]={4,8,16,20,24,32,52,56,60,64,204,607,1007};
            for(i=0;i<sizeof(offsets)/sizeof(offsets[0]);++i){memcpy(bad,bytes,L3_MINI_SAVE_BYTES);
                bad[offsets[i]]=0xff;if(offsets[i]==32)put32(bad+32,0);put32(bad+12,hash(bad));
                CHECK(!l3_mini_decode(&t,bad,L3_MINI_SAVE_BYTES));CHECK(memcmp(&t,&before,sizeof(t))==0);}}
        memcpy(bad,bytes,L3_MINI_SAVE_BYTES);put32(bad+4,L3_MINI_VERSION+1);put32(bad+12,hash(bad));
        CHECK(!l3_mini_decode(&t,bad,L3_MINI_SAVE_BYTES));
        memset(bad,0xcd,sizeof(bad));CHECK(!l3_mini_encode(&s,bad,L3_MINI_SAVE_BYTES-1));
        for(i=0;i<sizeof(bad);++i)CHECK(bad[i]==0xcd);
        CHECK(!l3_mini_decode(&t,NULL,0));CHECK(!l3_mini_decode(NULL,bytes,L3_MINI_SAVE_BYTES));
        CHECK(!l3_mini_init(&s,(L3MiniKind)99,1));
    }
    CHECK(!l3_mini_validate(NULL));CHECK(!l3_mini_view(NULL,NULL));
    puts("PASS codec: truncation at every byte, corruption at every byte, incompatible schema, repaired-checksum invalid states, transactional destination");
}

static unsigned solve(L3MiniState *s,FILE *trace)
{
    unsigned n;
    for(n=0;n<5000;++n){uint32_t p,h,dt;L3MiniState before,resumed;uint8_t save[L3_MINI_SAVE_BYTES];
        CHECK(l3_mini_validate(s));
        if(s->meta[ST]!=L3_MINI_RUNNING)break;
        before=*s;CHECK(l3_mini_demo_input(s,&p,&h,&dt));CHECK(memcmp(s,&before,sizeof(before))==0);
        if(trace)fprintf(trace,"%u %u %u\n",p,h,dt);
        CHECK(!(l3_mini_step(s,p,h,dt)&L3_MINI_EVENT_INVALID));
        /* Serialize every17th command, replay the same edge once on a copy. */
        if(n%17u==0){CHECK(l3_mini_encode(&before,save,sizeof(save))==sizeof(save));
            CHECK(l3_mini_decode(&resumed,save,sizeof(save)));
            CHECK(!(l3_mini_step(&resumed,p,h,dt)&L3_MINI_EVENT_INVALID));
            CHECK(memcmp(s,&resumed,sizeof(resumed))==0);}
    }
    CHECK(s->meta[ST]==L3_MINI_WON);CHECK(n<5000);roundtrip(s);check_view(s);
    return n;
}
static void wins(const char *trace_dir)
{
    unsigned k,seed;
    for(k=0;k<5;++k){L3MiniState s;unsigned n;FILE *f=NULL;char path[1024];
        CHECK(l3_mini_init(&s,(L3MiniKind)k,1));
        if(trace_dir){CHECK(snprintf(path,sizeof(path),"%s/win_%u.trace",trace_dir,k)>0);f=fopen(path,"w");CHECK(f!=NULL);fprintf(f,"L3MINITRACE 1 %u 1\n",k);}
        n=solve(&s,f);if(f)CHECK(fclose(f)==0);
        printf("PASS victory kind=%u seed=1 commands=%u score=%u\n",k,n,s.meta[SCORE]);
        {L3MiniState before=s;CHECK(l3_mini_step(&s,L3_MINI_ACT,L3_MINI_DOWN,250)==0);CHECK(memcmp(&s,&before,sizeof(s))==0);}
    }
    for(seed=0;seed<64;++seed)for(k=0;k<3;++k){L3MiniState s;CHECK(l3_mini_init(&s,(L3MiniKind)k,seed));solve(&s,NULL);}
    for(seed=0;seed<8;++seed){L3MiniState s;CHECK(l3_mini_init(&s,L3_MINI_MERGE1024,seed));solve(&s,NULL);}
    puts("PASS generated solvability: 64 seeds circuit/blocks/shapes; 8 seeds1024; maze original layout");
}
static void replay(const char *trace_dir)
{
    unsigned k;
    for(k=0;k<5;++k){char path[1024],magic[32];unsigned ver,kind,seed,n=0,p,h,dt;FILE *f;L3MiniState s;
        CHECK(snprintf(path,sizeof(path),"%s/win_%u.trace",trace_dir,k)>0);f=fopen(path,"r");CHECK(f!=NULL);
        CHECK(fscanf(f,"%31s %u %u %u",magic,&ver,&kind,&seed)==4);
        CHECK(strcmp(magic,"L3MINITRACE")==0 && ver==1 && kind==k);
        CHECK(l3_mini_init(&s,(L3MiniKind)kind,seed));
        while(fscanf(f,"%u %u %u",&p,&h,&dt)==3){CHECK(s.meta[ST]==L3_MINI_RUNNING);CHECK(!(l3_mini_step(&s,p,h,dt)&L3_MINI_EVENT_INVALID));++n;}
        CHECK(feof(f));CHECK(fclose(f)==0);CHECK(s.meta[ST]==L3_MINI_WON);CHECK(n>0);
    }
    puts("PASS public command traces replay without adviser or state mutation");
}
static void losses(void)
{
    unsigned k;
    for(k=0;k<5;++k){L3MiniState s,initial,before,resumed;unsigned n;uint32_t r=0x12345678u;
        CHECK(l3_mini_init(&s,(L3MiniKind)k,1));initial=s;
        if(k==L3_MINI_CIRCUIT)for(n=0;n<5;++n)CHECK(!(l3_mini_step(&s,L3_MINI_RIGHT,0,0)&L3_MINI_EVENT_INVALID));
        if(k==L3_MINI_BLOCKS){unsigned key=s.data[9]==0?L3_MINI_RIGHT:L3_MINI_LEFT;
            for(n=0;n<7;++n)CHECK(!(l3_mini_step(&s,key,0,0)&L3_MINI_EVENT_INVALID));}
        for(n=0;n<10000 && s.meta[ST]==L3_MINI_RUNNING;++n){uint32_t p=L3_MINI_ACT,dt=0;
            if(k==L3_MINI_MERGE1024)p=1u<<(rnd(&r)%4u);
            if(k==L3_MINI_MAZE){p=0;dt=250;}
            CHECK(!(l3_mini_step(&s,p,0,dt)&L3_MINI_EVENT_INVALID));CHECK(l3_mini_validate(&s));
        }
        CHECK(s.meta[ST]==L3_MINI_LOST);roundtrip(&s);check_view(&s);before=s;
        CHECK(l3_mini_step(&s,L3_MINI_BACK|L3_MINI_ACT,L3_MINI_DOWN,250)==L3_MINI_EVENT_EXIT);
        CHECK(memcmp(&s,&before,sizeof(s))==0);
        CHECK(l3_mini_step(&s,L3_MINI_ACT,0,250)==0);CHECK(memcmp(&s,&before,sizeof(s))==0);
        CHECK(l3_mini_init(&resumed,(L3MiniKind)k,1));CHECK(memcmp(&resumed,&initial,sizeof(initial))==0);
        printf("PASS loss/save/freeze/restart kind=%u commands=%u\n",k,n);
    }
}
static void rules(void)
{
    L3MiniState s,before;unsigned i;
    CHECK(l3_mini_init(&s,L3_MINI_MERGE1024,1));memset(s.board,0,sizeof(s.board));
    for(i=0;i<4;++i)s.board[i]=1;
    s.data[0]=4;s.data[1]=0;s.meta[MOVES]=2;s.meta[SCORE]=0;CHECK(l3_mini_validate(&s));
    CHECK(!(l3_mini_step(&s,L3_MINI_LEFT,0,0)&L3_MINI_EVENT_INVALID));
    CHECK(s.board[0]==2 && s.board[1]==2);CHECK(s.meta[SCORE]==8);CHECK(s.meta[MOVES]==3 && s.data[0]==5);
    CHECK(l3_mini_init(&s,L3_MINI_MERGE1024,1));memset(s.board,0,sizeof(s.board));
    s.board[0]=1;s.board[20]=1;s.data[0]=2;s.data[1]=0;CHECK(l3_mini_validate(&s));before=s;
    CHECK(!(l3_mini_step(&s,L3_MINI_LEFT,0,0)&L3_MINI_EVENT_INVALID));CHECK(memcmp(&s,&before,sizeof(s))==0);
    /* [4,4,4] => [8,4], never [16], plus exactly one new2/4. */
    memset(s.board,0,sizeof(s.board));s.board[0]=2;s.board[1]=2;s.board[2]=2;
    s.data[0]=6;s.data[1]=0;s.meta[MOVES]=4;CHECK(l3_mini_validate(&s));
    CHECK(!(l3_mini_step(&s,L3_MINI_LEFT,0,0)&L3_MINI_EVENT_INVALID));CHECK(s.board[0]==3 && s.board[1]==2 && s.meta[SCORE]==8);
    CHECK(l3_mini_init(&s,L3_MINI_BLOCKS,1));before=s;
    CHECK(!(l3_mini_step(&s,L3_MINI_ROTATE,0,0)&L3_MINI_EVENT_INVALID));CHECK(s.data[2]==1);
    /* Holding rotation never repeats it. */
    CHECK(!(l3_mini_step(&s,0,L3_MINI_ROTATE,250)&L3_MINI_EVENT_INVALID));CHECK(s.data[2]==1);
    for(i=0;i<12;++i)CHECK(!(l3_mini_step(&s,L3_MINI_LEFT,0,0)&L3_MINI_EVENT_INVALID));
    CHECK(s.data[0]==0);CHECK(s.meta[ST]==L3_MINI_RUNNING);
    s=before;CHECK(l3_mini_step(&s,0,0,UINT32_MAX)==L3_MINI_EVENT_CHANGED);
    CHECK(s.meta[TICKS]==15 && s.meta[PHASE]==0); /* documented cap */
    puts("PASS rules: merge once, null move keeps RNG/board, collisions, rotation fronts, bounded dt");
}
static void temporal(void)
{
    static const unsigned chunks[]={1,5,10,16,33,50,100,250};unsigned k,c,segment;
    for(k=0;k<5;++k){L3MiniState reference;
        for(c=0;c<sizeof(chunks)/sizeof(chunks[0]);++c){L3MiniState s;CHECK(l3_mini_init(&s,(L3MiniKind)k,17));
            for(segment=0;segment<80;++segment){unsigned left=300,dt;uint32_t p=1u<<(segment%4u),held=k==L3_MINI_BLOCKS?L3_MINI_DOWN:0;
                CHECK(!(l3_mini_step(&s,p,held,0)&L3_MINI_EVENT_INVALID));
                while(left){dt=left<chunks[c]?left:chunks[c];CHECK(!(l3_mini_step(&s,0,held,dt)&L3_MINI_EVENT_INVALID));left-=dt;}
            }
            if(c==0)reference=s;else CHECK(memcmp(&s,&reference,sizeof(s))==0);
            roundtrip(&s);
        }
    }
    puts("PASS timing: identical states at 1/5/10/16/33/50/100/250ms call spacing, equal input timelines");
}
static void random_invariants(void)
{
    unsigned k,seed,n;uint32_t r=0x31415926u;
    for(k=0;k<5;++k)for(seed=0;seed<32;++seed){L3MiniState s;CHECK(l3_mini_init(&s,(L3MiniKind)k,seed));
        for(n=0;n<1000;++n){uint32_t p=rnd(&r)%128u,h=rnd(&r)%128u,dt=rnd(&r)%300u;L3MiniState before=s;
            CHECK(!(l3_mini_step(&s,p,h,dt)&L3_MINI_EVENT_INVALID));CHECK(l3_mini_validate(&s));
            if(p&L3_MINI_BACK)CHECK(memcmp(&s,&before,sizeof(s))==0);
            if(n%97u==0){roundtrip(&s);check_view(&s);}
            if(s.meta[ST]!=L3_MINI_RUNNING)CHECK(l3_mini_init(&s,(L3MiniKind)k,rnd(&r)));
        }
    }
    puts("PASS bounded randomized invariants: 160000 input frames including combined edges, holds, BACK and dt cap");
}
static void decoded_mutations(void)
{
    unsigned k,n,accepted=0;uint32_t r=0x27182818u;
    for(k=0;k<5;++k){L3MiniState s;uint8_t good[L3_MINI_SAVE_BYTES],bad[L3_MINI_SAVE_BYTES];
        CHECK(l3_mini_init(&s,(L3MiniKind)k,1));CHECK(l3_mini_encode(&s,good,sizeof(good))==sizeof(good));
        for(n=0;n<2000;++n){L3MiniState out,before;unsigned pos=16u+rnd(&r)%(L3_MINI_SAVE_BYTES-16u);
            memset(&out,0xa5,sizeof(out));before=out;memcpy(bad,good,sizeof(bad));
            bad[pos]^=(uint8_t)(1u<<(rnd(&r)%8u));put32(bad+12,hash(bad));
            if(l3_mini_decode(&out,bad,sizeof(bad))){++accepted;CHECK(l3_mini_validate(&out));check_view(&out);
                CHECK(!(l3_mini_step(&out,rnd(&r)%64u,rnd(&r)%64u,250)&L3_MINI_EVENT_INVALID));CHECK(l3_mini_validate(&out));}
            else CHECK(memcmp(&out,&before,sizeof(out))==0);
        }
    }
    printf("PASS adversarial decode: 10000 repaired-checksum mutations, %u semantically valid cases safely stepped\n",accepted);
}
int main(int argc,char **argv)
{
    const char *traces=argc>1?argv[1]:NULL;
    CHECK(sizeof(L3MiniState)<=4096);codec();rules();wins(traces);losses();temporal();random_invariants();decoded_mutations();
    if(traces)replay(traces);
    printf("PASS all checks=%u state_bytes=%lu save_bytes=%u\n",checks,(unsigned long)sizeof(L3MiniState),L3_MINI_SAVE_BYTES);
    return 0;
}
