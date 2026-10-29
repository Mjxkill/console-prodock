#include "l3_simon.h"
#include <limits.h>
#include <string.h>

enum { SV,SS,SEED,SRNG,ELAPSED,PHASE,REMAIN,LENGTH,INPUT,SHOW,FEEDBACK,ACTIVE,ROUNDS };
static const uint32_t buttons[4]={L3_MINI_UP,L3_MINI_RIGHT,L3_MINI_DOWN,L3_MINI_LEFT};
static const uint8_t palette[4]={12,10,9,14};
static uint32_t rng(uint32_t *r)
{ *r^=*r<<13;*r^=*r>>17;*r^=*r<<5;return *r; }
static uint32_t plus(uint32_t a,uint32_t b)
{ return UINT32_MAX-a<b?UINT32_MAX:a+b; }
static void phase(L3SimonState *s,unsigned p,unsigned time,unsigned active)
{s->words[PHASE]=p;s->words[REMAIN]=time;s->words[ACTIVE]=active;s->words[FEEDBACK]=0;}
int l3_simon_init(L3SimonState *s,uint32_t seed)
{
    L3SimonState t;unsigned i;
    if(!s)return 0;
    memset(&t,0,sizeof(t));t.words[SV]=L3_SIMON_VERSION;t.words[SEED]=seed;
    t.words[SRNG]=seed^0x6c756d61u;if(!t.words[SRNG])t.words[SRNG]=0x53494d4fu;
    for(i=0;i<L3_SIMON_GOAL;++i)t.sequence[i]=(uint8_t)(rng(&t.words[SRNG])%4u);
    t.words[LENGTH]=1;phase(&t,L3_SIMON_INTRO,600,4);*s=t;return 1;
}
int l3_simon_validate(const L3SimonState *s)
{
    L3SimonState initial;unsigned p,status,i,len,idx,rounds;
    if(!s || s->words[SV]!=L3_SIMON_VERSION || s->words[SS]>L3_MINI_LOST)return 0;
    p=s->words[PHASE];status=s->words[SS];len=s->words[LENGTH];idx=s->words[INPUT];rounds=s->words[ROUNDS];
    if(p>L3_SIMON_COMPLETE || len<1 || len>L3_SIMON_GOAL || idx>len || rounds>L3_SIMON_GOAL || s->words[SHOW]>=len || s->words[ACTIVE]>4 || s->words[FEEDBACK]>240)return 0;
    for(i=13;i<24;++i)if(s->words[i])return 0;
    l3_simon_init(&initial,s->words[SEED]);
    if(s->words[SRNG]!=initial.words[SRNG] || memcmp(s->sequence,initial.sequence,sizeof(s->sequence)))return 0;
    if((status==L3_MINI_WON)!=(p==L3_SIMON_COMPLETE) || (status==L3_MINI_LOST)!=(p==L3_SIMON_ERROR))return 0;
    if(p==L3_SIMON_COMPLETE)return len==8 && rounds==8 && idx==8 && s->words[REMAIN]==0 && s->words[ACTIVE]==4 && s->words[FEEDBACK]==0;
    if(p==L3_SIMON_ROUND_OK)return rounds==len && len<8 && idx==len && s->words[REMAIN]>0 && s->words[REMAIN]<=600 && s->words[ACTIVE]==4 && s->words[FEEDBACK]==0;
    if(rounds!=len-1u || idx>=len)return 0;
    if(p==L3_SIMON_INTRO)return len==1 && idx==0 && s->words[SHOW]==0 && s->words[REMAIN]>0 && s->words[REMAIN]<=600 && s->words[ACTIVE]==4 && !s->words[FEEDBACK];
    if(p==L3_SIMON_SHOW)return idx==0 && s->words[REMAIN]>0 && s->words[REMAIN]<=600 && s->words[ACTIVE]==s->sequence[s->words[SHOW]] && !s->words[FEEDBACK];
    if(p==L3_SIMON_GAP)return idx==0 && s->words[REMAIN]>0 && s->words[REMAIN]<=250 && s->words[ACTIVE]==4 && !s->words[FEEDBACK];
    if(p==L3_SIMON_ERROR)return !s->words[REMAIN] && !s->words[FEEDBACK] && s->words[ACTIVE]<4;
    if(s->words[REMAIN] || s->words[SHOW]!=len-1u)return 0;
    if(s->words[FEEDBACK])return idx>0 && s->words[ACTIVE]==s->sequence[idx-1u];
    return s->words[ACTIVE]==4;
}
static void next_phase(L3SimonState *s)
{
    switch(s->words[PHASE]) {
    case L3_SIMON_INTRO:phase(s,L3_SIMON_SHOW,600,s->sequence[0]);break;
    case L3_SIMON_SHOW:phase(s,L3_SIMON_GAP,250,4);break;
    case L3_SIMON_GAP:
        if(s->words[SHOW]+1u<s->words[LENGTH]){++s->words[SHOW];phase(s,L3_SIMON_SHOW,600,s->sequence[s->words[SHOW]]);}
        else phase(s,L3_SIMON_INPUT,0,4);
        break;
    case L3_SIMON_ROUND_OK:
        ++s->words[LENGTH];s->words[INPUT]=0;s->words[SHOW]=0;phase(s,L3_SIMON_SHOW,600,s->sequence[0]);break;
    default:break;
    }
}
uint32_t l3_simon_step(L3SimonState *s,uint32_t pressed,uint32_t held,uint32_t dt)
{
    L3SimonState before;unsigned color,count=0,chosen=0;
    if(!l3_simon_validate(s) || ((pressed|held)&~L3_MINI_INPUT_MASK))return L3_MINI_EVENT_INVALID;
    if(pressed&L3_MINI_BACK)return L3_MINI_EVENT_EXIT;
    if(s->words[SS]!=L3_MINI_RUNNING)return 0;
    before=*s;
    if(s->words[PHASE]==L3_SIMON_INPUT) {
        for(color=0;color<4;++color)if(pressed&buttons[color]){chosen=color;++count;}
        if(count) {
            if(count!=1 || chosen!=s->sequence[s->words[INPUT]]) {
                s->words[SS]=L3_MINI_LOST;phase(s,L3_SIMON_ERROR,0,chosen);
                return L3_MINI_EVENT_CHANGED|L3_MINI_EVENT_LOST;
            }
            ++s->words[INPUT];s->words[ACTIVE]=chosen;s->words[FEEDBACK]=240;
            if(s->words[INPUT]==s->words[LENGTH]) {
                ++s->words[ROUNDS];
                if(s->words[ROUNDS]==L3_SIMON_GOAL){s->words[SS]=L3_MINI_WON;phase(s,L3_SIMON_COMPLETE,0,4);return L3_MINI_EVENT_CHANGED|L3_MINI_EVENT_WON;}
                phase(s,L3_SIMON_ROUND_OK,600,4);
            }
        }
    }
    if(dt>L3_MINI_MAX_DT_MS)dt=L3_MINI_MAX_DT_MS;
    s->words[ELAPSED]=plus(s->words[ELAPSED],dt);
    while(dt) {
        unsigned step=dt;
        if(s->words[PHASE]==L3_SIMON_INPUT) {
            if(s->words[FEEDBACK]>dt)s->words[FEEDBACK]-=dt;
            else {s->words[FEEDBACK]=0;s->words[ACTIVE]=4;}
            break;
        }
        if(step>s->words[REMAIN])step=s->words[REMAIN];
        s->words[REMAIN]-=step;dt-=step;
        if(!s->words[REMAIN])next_phase(s);
    }
    return memcmp(&before,s,sizeof(before))?L3_MINI_EVENT_CHANGED:0;
}
int l3_simon_view(const L3SimonState *s,L3SimonView *out)
{
    L3SimonView v;unsigned i;
    if(!out || !l3_simon_validate(s))return 0;
    memset(&v,0,sizeof(v));v.grid.kind=5;v.grid.status=s->words[SS];v.grid.width=2;v.grid.height=2;
    v.grid.score=s->words[ROUNDS]*100u;v.grid.target=L3_SIMON_GOAL;v.grid.progress=(uint16_t)s->words[ROUNDS];
    v.grid.elapsed_ms=s->words[ELAPSED];v.grid.cursor_x=-1;v.grid.cursor_y=-1;
    v.grid.title="Carillon des quatre couleurs";
    v.grid.help="Haut rouge, droite vert, bas bleu, gauche jaune. Repeter apres le signal.";
    v.grid.objective="Memoriser puis repeter les couleurs dans l'ordre, jusqu'a 8 notes.";
    v.phase=(uint8_t)s->words[PHASE];v.active_color=(uint8_t)s->words[ACTIVE];
    v.sequence_length=(uint8_t)s->words[LENGTH];v.input_index=(uint8_t)s->words[INPUT];
    v.phase_ms=(uint16_t)s->words[REMAIN];v.feedback_ms=(uint16_t)s->words[FEEDBACK];
    for(i=0;i<4;++i){L3MiniCell *c=&v.grid.cells[(i/2u)*20u+i%2u];
        c->kind=L3_MINI_CELL_BLOCK;c->color=palette[i];c->value=(uint16_t)i;
        c->glyph=(uint8_t)(i==0?'^':i==1?'>':i==2?'v':'<');
        if(i==s->words[ACTIVE])c->flags=L3_MINI_FLAG_ACTIVE;
    }
    *out=v;return 1;
}
static void write32(uint8_t *p,uint32_t v)
{unsigned i;for(i=0;i<4;++i)p[i]=(uint8_t)(v>>(8u*i));}
static uint32_t read32(const uint8_t *p)
{return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static uint32_t checksum(const uint8_t *p)
{unsigned i;uint32_t h=2166136261u;for(i=0;i<L3_SIMON_SAVE_BYTES;++i)if(i<12 || i>=16){h^=p[i];h*=16777619u;}return h;}
size_t l3_simon_encode(const L3SimonState *s,void *out,size_t cap)
{
    uint8_t bytes[L3_SIMON_SAVE_BYTES];unsigned i;
    if(!l3_simon_validate(s))return 0;
    if(!out)return sizeof(bytes);
    if(cap<sizeof(bytes))return 0;
    memcpy(bytes,"L3SM",4);write32(bytes+4,L3_SIMON_VERSION);write32(bytes+8,112);write32(bytes+12,0);
    for(i=0;i<24;++i)write32(bytes+16u+4u*i,s->words[i]);
    memcpy(bytes+112,s->sequence,16);write32(bytes+12,checksum(bytes));memcpy(out,bytes,sizeof(bytes));return sizeof(bytes);
}
int l3_simon_decode(L3SimonState *s,const void *in,size_t size)
{
    const uint8_t *p=(const uint8_t *)in;L3SimonState t;unsigned i;
    if(!s || !p || size!=L3_SIMON_SAVE_BYTES || memcmp(p,"L3SM",4) || read32(p+4)!=L3_SIMON_VERSION || read32(p+8)!=112 || read32(p+12)!=checksum(p))return 0;
    memset(&t,0,sizeof(t));for(i=0;i<24;++i)t.words[i]=read32(p+16u+4u*i);memcpy(t.sequence,p+112,16);
    if(!l3_simon_validate(&t))return 0;
    *s=t;return 1;
}
int l3_simon_demo_input(const L3SimonState *s,uint32_t *pressed,uint32_t *held,uint32_t *dt)
{
    if(!pressed || !held || !dt || !l3_simon_validate(s) || s->words[SS]!=L3_MINI_RUNNING)return 0;
    *pressed=0;*held=0;*dt=0;
    if(s->words[PHASE]==L3_SIMON_INPUT)*pressed=buttons[s->sequence[s->words[INPUT]]];
    else *dt=s->words[REMAIN]>L3_MINI_MAX_DT_MS?L3_MINI_MAX_DT_MS:s->words[REMAIN];
    return 1;
}
