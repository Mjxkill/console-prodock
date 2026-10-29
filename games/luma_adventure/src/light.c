/* SPDX-License-Identifier: MIT */
#include "luma.h"
#include <string.h>

/* Optics are combinational. Doors and the player transmit light; only walls,
 * crates and mirrors affect its path. Receiver flags cannot enable sources,
 * which prevents feedback/oscillation when a door reads those flags. */
#define LIGHT_SIDE 128
static const int dx[4]={1,0,-1,0},dy[4]={0,1,0,-1};

static void beam(LumaGame *g,int x1,int y1,int x2,int y2){
 if(x1==x2&&y1==y2)return;
 if(g->beam_count==LUMA_BEAMS){g->light_fault=1;return;}
 g->beams[g->beam_count++]=(LumaBeam){x1,y1,x2,y2};
}

void luma_light_init(LumaGame *g){
 g->light_network=0;g->beam_count=0;g->receivers_lit=0;g->light_fault=0;
 memset(g->mirror_orientation,0,sizeof(g->mirror_orientation));
 for(unsigned i=0;i<g->world->entity_count;i++){
  const LumaEntity *e=g->world->entities+i;
  if(e->kind==E_EMITTER||e->kind==E_RECEIVER)g->light_network=1;
  if(e->kind==E_MIRROR)g->mirror_orientation[i]=e->cost&1;
 }
 g->light_dirty=1;
}

void luma_light_update(LumaGame *g){
 if(!g->light_network){g->light_dirty=0;g->light_flags=g->flags;return;}
 if(!g->light_dirty&&g->light_flags==g->flags)return;
 const LumaWorld *w=g->world;
 g->beam_count=0;g->receivers_lit=0;g->light_fault=0;g->light_dirty=0;
 if(w->width<1||w->height<1||w->width>LIGHT_SIDE||w->height>LIGHT_SIDE||w->tile<1||w->tile>256){g->light_fault=1;return;}
 uint8_t cells[LIGHT_SIDE*LIGHT_SIDE]={0};
 uint8_t seen[LIGHT_SIDE*LIGHT_SIDE/2];
 unsigned receiver_mask=0;
 for(unsigned i=0;i<w->entity_count;i++){
  const LumaEntity *e=w->entities+i;
  int x=(int)(g->actors[i].x/w->tile),y=(int)(g->actors[i].y/w->tile);
  if(x<0||y<0||x>=w->width||y>=w->height)continue;
  unsigned at=(unsigned)(y*w->width+x);
  if(e->kind==E_CRATE)cells[at]|=128;
  else if(e->kind==E_MIRROR||e->kind==E_RECEIVER||e->kind==E_EMITTER)cells[at]=(cells[at]&128)|(i+1);
  if(e->kind==E_RECEIVER)receiver_mask|=e->grants;
 }
 for(unsigned source=0;source<w->entity_count;source++){
  const LumaEntity *e=w->entities+source;
  if(e->kind!=E_EMITTER||!luma_entity_enabled(g,e))continue;
  memset(seen,0,(unsigned)(w->width*w->height*4+7)/8);
  int x=(int)(e->x/w->tile),y=(int)(e->y/w->tile);unsigned direction=e->behavior&3;
  if(x<0||y<0||x>=w->width||y>=w->height||(cells[y*w->width+x]&128))continue;
  int origin_x=x*w->tile+w->tile/2,origin_y=y*w->tile+w->tile/2;
  for(;;){
   x+=dx[direction];y+=dy[direction];
   int px=x*w->tile+w->tile/2,py=y*w->tile+w->tile/2;
   int inside=x>=0&&y>=0&&x<w->width&&y<w->height;
   char terrain=inside?w->terrain[y*w->width+x]:'#';
   unsigned cell=inside?cells[y*w->width+x]:0;
   if(!inside||terrain=='#'||terrain=='t'||terrain=='H'||(cell&128)){
    beam(g,origin_x,origin_y,px-dx[direction]*(w->tile/2),py-dy[direction]*(w->tile/2));break;
   }
   unsigned state=(unsigned)(y*w->width+x)*4+direction;
   if(seen[state/8]&(1U<<(state&7))){beam(g,origin_x,origin_y,px,py);break;}
   seen[state/8]|=1U<<(state&7);
   if(!(cell&127))continue;
   unsigned actor=(cell&127)-1;const LumaEntity *hit=w->entities+actor;
   if(hit->kind==E_RECEIVER)g->receivers_lit|=UINT64_C(1)<<actor;
   else if(hit->kind==E_MIRROR){
    beam(g,origin_x,origin_y,px,py);origin_x=px;origin_y=py;
    direction^=g->mirror_orientation[actor]?1:3;
   }
  }
 }
 unsigned lit=0;
 for(unsigned i=0;i<w->entity_count;i++)if(g->receivers_lit&(UINT64_C(1)<<i))lit|=w->entities[i].grants;
 unsigned flags=(g->flags&~receiver_mask)|lit;
 if(flags!=g->flags)g->dirty=1;
 g->flags=flags;g->light_flags=flags;
}
