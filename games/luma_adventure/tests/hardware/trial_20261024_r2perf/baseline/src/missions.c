/* SPDX-License-Identifier: MIT */
#include "luma.h"
#include <math.h>
#include <string.h>
LumaProgress luma_progress(const LumaGame *g){LumaProgress p={.flags=g->flags,.collected=g->collected,.activated=g->activated,.defeated=g->defeated,.talked=g->talked,.missions=g->missions};memcpy(p.steps,g->mission_steps,16);for(unsigned i=0;i<g->world->entity_count;i++)if(g->world->entities[i].kind==E_CRATE)p.objects[i]=0x80000000U|((unsigned)g->actors[i].x&65535)|(((unsigned)g->actors[i].y&32767)<<16);return p;}
int luma_missions_complete(const LumaGame *g){for(unsigned i=0;i<g->world->mission_count;i++)if(g->world->missions[i].required&&!(g->missions&(1U<<i)))return 0;return 1;}
static unsigned count(uint64_t bits){unsigned n=0;while(bits){bits&=bits-1;n++;}return n;}
void luma_missions_update(LumaGame *g){
 for(unsigned i=0;i<g->world->mission_count;i++){
  const LumaMission *m=g->world->missions+i;unsigned bit=1U<<i;if((g->missions&bit)||(g->missions&m->requires)!=m->requires)continue;int complete=0;
  switch(m->type){
   case M_DUNGEON:complete=m->target<luma_world_count&&(g->progress[m->target].flags&m->count)==m->count;break;
   case M_TALK:complete=!!((g->talked|g->activated)&(UINT64_C(1)<<m->target));break;
   case M_COLLECT:complete=count(g->collected&m->targets)>=m->count;break;
   case M_DEFEAT:complete=count(g->defeated&m->targets)>=m->count;break;
   case M_CHOICE:complete=g->mission_steps[i]>0;break;
   case M_VISIT:case M_ROUTE:
    if(g->mission_steps[i]<m->point_count&&(m->type!=M_ROUTE||g->vehicle==m->vehicle)){
     const LumaCheckpoint *p=m->points+g->mission_steps[i];if(hypotf(g->x-p->x,g->y-p->y)<=p->radius){g->mission_steps[i]++;g->dirty=1;}}
    complete=g->mission_steps[i]>=m->point_count;break;
  }
  if(complete){g->missions|=bit;g->flags|=m->reward_flags;g->crystals+=m->reward_crystals;if(m->reward_vehicle<VEHICLES)g->unlocked|=1U<<m->reward_vehicle;g->dirty=1;luma_notice(g,m->title);}
 }
}

void luma_restore_objects(LumaGame *g){LumaProgress *p=g->progress+g->world_index;for(unsigned i=0;i<g->world->entity_count;i++)if(g->world->entities[i].kind==E_CRATE&&(p->objects[i]&0x80000000U)){unsigned x=p->objects[i]&65535,y=(p->objects[i]>>16)&32767;if(x<(unsigned)(g->world->width*g->world->tile)&&y<(unsigned)(g->world->height*g->world->tile)){char c=g->world->terrain[(y/g->world->tile)*g->world->width+x/g->world->tile];if(c!='#'&&c!='~'&&c!='t'&&c!='H'){g->actors[i].x=(float)x;g->actors[i].y=(float)y;}}}}
