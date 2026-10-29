#ifndef LUMA_PLAY_DUNGEON_H
#define LUMA_PLAY_DUNGEON_H
#include "play_input.h"
#include "puzzle_witness.h"
#include <string.h>
static int entity_id(const LumaGame *g,const char *id){for(unsigned i=0;i<g->world->entity_count;i++)if(!strcmp(id,g->world->entities[i].id))return (int)i;return -1;}
static int play_dungeon(LumaGame *g){
 const PuzzleGroup *group=NULL;for(unsigned i=0;i<sizeof(puzzle_groups)/sizeof(*puzzle_groups);i++)if(puzzle_groups[i].first==g->world_index)group=puzzle_groups+i;if(!group)return -1;
 for(unsigned n=group->begin;n<group->end;n++){
  const PuzzleStep *s=puzzle_steps+n;assert(g->world_index==s->world);int target=entity_id(g,s->target);assert(target>=0);const LumaEntity *e=g->world->entities+target;
  printf("  ROOM %u %s %s\n",s->world,s->action,s->target);fflush(stdout);
  if(!strcmp(s->action,"push")){
   assert(!reach_point(g,s->x,s->y,2.5f));
   for(unsigned i=0;i<s->count;i++){
    float x=g->actors[target].x,y=g->actors[target].y;assert(!reach_point(g,x-s->dx*32,y-s->dy*32,2.5f));
    luma_step(g,(LumaInput){s->dx,s->dy,0,0});interact(g);
    if(g->actors[target].x!=x+s->dx*32||g->actors[target].y!=y+s->dy*32){fprintf(stderr,"Push failed at %.1f,%.1f near=%d face=%.1f,%.1f target=%d before=%.1f,%.1f after=%.1f,%.1f destination_walkable=%d\n",g->x,g->y,g->nearby,g->face_x,g->face_y,target,x,y,g->actors[target].x,g->actors[target].y,luma_walkable(g,x+s->dx*32,y+s->dy*32,WALK));return -1;}
   }
  }else if(!strcmp(s->action,"rotate")){
   assert(e->kind==E_MIRROR);assert(!reach_point(g,s->x,s->y,2.5f));
   float dx=e->x-g->x,dy=e->y-g->y,d=hypotf(dx,dy);assert(d>0);luma_step(g,(LumaInput){dx/d,dy/d,0,0});
   for(unsigned i=0;i<s->count;i++){unsigned before=g->mirror_orientation[target];interact(g);assert(g->mirror_orientation[target]==(before^1));}
   assert(!g->light_fault);
  }else if(!strcmp(s->action,"shoot")){
   assert(!reach_point(g,s->x,s->y,2.5f));unsigned before=g->flags;float dx=e->x-g->x,dy=e->y-(g->y-8),d=hypotf(dx,dy);luma_step(g,(LumaInput){dx/d,dy/d,0,0});luma_step(g,(LumaInput){0,0,0,B_SHOOT});for(unsigned i=0;i<110;i++)luma_step(g,(LumaInput){0});assert((g->flags&e->grants)==((before^e->grants)&e->grants));
  }else{
   assert(!reach(g,(unsigned)target));if(strcmp(s->action,"defeat"))interact(g);else assert(!g->actors[target].alive);
  }
 }
 return 0;
}
#endif
