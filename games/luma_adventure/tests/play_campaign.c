#include "play_input.h"
#include "play_dungeon.h"
int main(void){
 LumaGame g;luma_init(&g,&luma_world);unsigned completed=0;
 for(unsigned world=0;world<6;world++){
  assert(g.world_index==world);printf("PLAY world %u: %s\n",world+1,g.world->name);fflush(stdout);
  unsigned processed=0;for(unsigned pass=0;pass<g.world->mission_count;pass++){
   unsigned mi=0;for(;mi<g.world->mission_count;mi++){const LumaMission *candidate=g.world->missions+mi;if(!(processed&(1U<<mi))&&((g.missions&(1U<<mi))||(g.missions&candidate->requires)==candidate->requires))break;}assert(mi<g.world->mission_count);processed|=1U<<mi;
   const LumaMission *m=g.world->missions+mi;assert((g.missions&m->requires)==m->requires);if(g.missions&(1U<<mi)){completed++;continue;}
   printf("  %s %s\n",m->id,m->title);fflush(stdout);assert(vehicle(&g,m->type==M_ROUTE?m->vehicle:WALK)==0);
   switch(m->type){
    case M_DUNGEON:{const PuzzleGroup *group=NULL;for(unsigned gi=0;gi<sizeof(puzzle_groups)/sizeof(*puzzle_groups);gi++)if(puzzle_groups[gi].last==m->target)group=puzzle_groups+gi;assert(group);int entrance=-1;for(unsigned ei=0;ei<g.world->entity_count;ei++){const LumaEntity *e=g.world->entities+ei;if((e->kind==E_PORTAL||e->kind==E_DOOR)&&e->target_world==(int)group->first)entrance=ei;}assert(entrance>=0);assert(!reach(&g,(unsigned)entrance));interact(&g);assert(g.world_index==group->first);assert(!play_dungeon(&g));luma_step(&g,(LumaInput){0});break;}
    case M_TALK:assert(reach(&g,m->target)==0);interact(&g);break;
    case M_CHOICE:assert(reach(&g,m->target)==0);interact(&g);assert(g.puzzle==(int)mi);luma_step(&g,(LumaInput){0,0,B_CHOICE1<<m->answer,0});break;
    case M_VISIT:case M_ROUTE:
     for(unsigned attempt=0;g.mission_steps[mi]<m->point_count&&attempt<40;attempt++){if(m->type==M_ROUTE&&(g.vehicle!=m->vehicle||g.stamina<20)){assert(vehicle(&g,WALK)==0);for(int rest=0;rest<600;rest++)luma_step(&g,(LumaInput){0});assert(vehicle(&g,m->vehicle)==0);}const LumaCheckpoint *p=m->points+g.mission_steps[mi];assert(reach_point(&g,p->x,p->y,fmaxf(5,p->radius*.8f))==0);luma_step(&g,(LumaInput){0});}break;
    case M_COLLECT:case M_DEFEAT:
     for(unsigned i=0;i<g.world->entity_count&&!(g.missions&(1U<<mi));i++)if(m->targets&(UINT64_C(1)<<i)){assert(reach(&g,i)==0);if(m->type==M_COLLECT&&g.world->entities[i].kind==E_CHEST)interact(&g);}break;
   }
   if(!(g.missions&(1U<<mi))){fprintf(stderr,"Mission blocked %s flags=%u missions=%x vehicle=%u pos=%.1f,%.1f steps=%u deaths=%u\n",m->id,g.flags,g.missions,g.vehicle,g.x,g.y,g.mission_steps[mi],g.deaths);return 1;}completed++;
   if(!strcmp(m->id,"c17_reflections")){
    unsigned crystals=g.crystals;assert(g.flags&512);
    const char *doors[]={"post_gallery_west","post_gallery_east"};
    for(unsigned n=0;n<2;n++){
     unsigned door=0;while(door<g.world->entity_count&&strcmp(g.world->entities[door].id,doors[n]))door++;assert(door<g.world->entity_count);
     const LumaEntity *e=g.world->entities+door;assert(luma_entity_enabled(&g,e));assert(!reach(&g,door));interact(&g);
     assert(g.world_index==world&&fabsf(g.x-e->target_x)<4&&fabsf(g.y-e->target_y)<4);
    }
    assert(g.crystals==crystals);puts("PLAY_CONSEQUENCE gallery traversed in both directions; reward remains unique");
   }
  }
  assert(luma_missions_complete(&g));assert(vehicle(&g,WALK)==0);
  for(unsigned i=0;i<g.world->entity_count;i++){const LumaEntity *e=g.world->entities+i;if(e->kind!=E_PORTAL||e->target_world!=(world+1<6?(int)world+1:-1))continue;assert(reach(&g,i)==0);interact(&g);break;}
  if(world+1<6)assert(g.world_index==world+1);else assert(g.won);
 }
 printf("LUMA_CAMPAIGN_PASS worlds=%u missions=%u seconds=%.1f steps=%u kills=%u deaths=%u shots=%u crystals=%u\n",6U,completed,g.time,g.tick,g.kills,g.deaths,g.shots_fired,g.crystals);return 0;
}
