#include "play_dungeon.h"
#include <stdlib.h>
int main(int argc,char **argv){assert(argc==4);unsigned first=(unsigned)atoi(argv[1]),last=(unsigned)atoi(argv[2]),exit_world=(unsigned)atoi(argv[3]);LumaGame g;luma_init(&g,&luma_world);assert(!luma_enter(&g,first,0,0));assert(!vehicle(&g,WALK));assert(!play_dungeon(&g));assert(g.world_index==exit_world);assert(g.progress[last].flags&32);printf("LUMA_CANDIDATE_PASS rooms=%u seconds=%.1f steps=%u kills=%u deaths=%u shots=%u\n",last-first+1,g.time,g.tick,g.kills,g.deaths,g.shots_fired);return 0;}
