#include "../l3_platform.h"
#include <stdio.h>
#include <stdlib.h>
int main(int argc,char **argv)
{
    L3PlatformState s;L3PlatformView v;unsigned i,seed=argc>1?(unsigned)strtoul(argv[1],NULL,0):1;
    l3_platform_init(&s,seed);
    for(i=0;i<5000;++i){uint32_t p,h,dt;
        if(!l3_platform_validate(&s)){printf("invalid n=%u floor=%u y=%u air=%u climb=%u highest=%u\n",i,s.words[13],s.words[10],s.words[15],s.words[14],s.words[17]);return 2;}
        if(!l3_platform_demo_input(&s,&p,&h,&dt))break;
        if(l3_platform_step(&s,p,h,dt)&L3_MINI_EVENT_INVALID)return 3;
    }
    if(!l3_platform_view(&s,&v))return 4;
    printf("seed=%u frames=%u status=%u floor=%u x=%d y=%d z=%d lives=%u jumps=%u score=%u time=%u\n",seed,i,v.status,v.floor,v.actors[0].x256,v.actors[0].y256,v.actors[0].z256,v.lives,v.jumps,v.score,v.elapsed_ms);
    return v.status==L3_MINI_WON?0:1;
}
