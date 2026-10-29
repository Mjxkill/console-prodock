#include "../l3_minigames.h"
#include <stdio.h>
#include <stdlib.h>

int main(int argc,char **argv)
{
    unsigned k,seed=argc>1?(unsigned)strtoul(argv[1],NULL,0):1u;
    for(k=0;k<L3_MINI_KIND_COUNT;++k) {
        L3MiniState s;L3MiniView v;unsigned n;
        if(!l3_mini_init(&s,(L3MiniKind)k,seed))return 1;
        for(n=0;n<5000;++n){uint32_t p,h,dt,ev;
            if(!l3_mini_validate(&s)){fprintf(stderr,"invalid k=%u n=%u\n",k,n);return 2;}
            if(!l3_mini_demo_input(&s,&p,&h,&dt))break;
            ev=l3_mini_step(&s,p,h,dt);
            if(ev&L3_MINI_EVENT_INVALID){fprintf(stderr,"invalid step k=%u n=%u\n",k,n);return 3;}
        }
        if(!l3_mini_view(&s,&v)){fprintf(stderr,"invalid final k=%u\n",k);return 4;}
        printf("seed=%u kind=%u commands=%u status=%u score=%u progress=%u/%u lives=%u\n",seed,k,n,v.status,v.score,v.progress,v.target,v.lives);
        fflush(stdout);
        if(v.status!=L3_MINI_WON)return 5;
    }
    return 0;
}
