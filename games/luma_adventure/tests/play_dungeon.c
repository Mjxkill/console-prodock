#include "play_dungeon.h"
int main(void){LumaGame g;luma_init(&g,&luma_world);assert(!luma_enter(&g,6,0,0));assert(!vehicle(&g,WALK));assert(!play_dungeon(&g));assert(g.world_index==0);assert((g.progress[15].flags&33)==33);printf("LUMA_DUNGEON_PASS rooms=10 seconds=%.1f steps=%u kills=%u deaths=%u shots=%u\n",g.time,g.tick,g.kills,g.deaths,g.shots_fired);return 0;}
