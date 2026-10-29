#include "../l3_shooter.h"
#include <stdio.h>
#include <stdlib.h>
int main(int argc,char **argv)
{
    L3ShooterState s;L3ShooterView v;unsigned n,seed=argc>1?(unsigned)strtoul(argv[1],NULL,0):1;
    l3_shooter_init(&s,seed);
    for(n=0;n<5000;++n){uint32_t p,h,dt;
        if(!l3_shooter_validate(&s)){printf("invalid n=%u\n",n);return 2;}
        if(!l3_shooter_demo_input(&s,&p,&h,&dt))break;
        if(l3_shooter_step(&s,p,h,dt)&L3_MINI_EVENT_INVALID)return 3;
    }
    if(!l3_shooter_view(&s,&v))return 4;
    printf("seed=%u frames=%u status=%u score=%u lives=%u wave=%u kills=%u escaped=%u boss=%u time=%u\n",seed,n,v.status,v.score,v.lives,v.wave,v.kills,v.escaped,v.boss_hp,v.elapsed_ms);
    return v.status==L3_MINI_WON?0:1;
}
