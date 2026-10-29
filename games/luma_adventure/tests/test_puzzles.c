/* SPDX-License-Identifier: MIT */
#include "luma.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static void use(LumaGame *g,unsigned i){g->x=g->actors[i].x-24;g->y=g->actors[i].y;g->face_x=1;g->face_y=0;g->nearby=(int)i;luma_step(g,(LumaInput){0,0,B_INTERACT,0});}
int main(void){
 char terrain[16*16];memset(terrain,'.',sizeof(terrain));for(int i=0;i<16;i++){terrain[i]=terrain[240+i]=terrain[i*16]=terrain[i*16+15]='#';}for(int x=3;x<=5;x++)terrain[9*16+x]='~';
 LumaEntity entities[]={
  {.id="crate",.kind=E_CRATE,.x=176,.y=176},
  {.id="plate",.kind=E_PLATE,.x=208,.y=176,.grants=1},
  {.id="door",.kind=E_DOOR,.x=272,.y=176,.requires=1,.target_world=-1},
  {.id="target",.kind=E_TARGET,.x=176,.y=304,.grants=2},
  {.id="switch",.kind=E_SWITCH,.x=80,.y=80,.grants=4,.after="switch"},
  {.id="one",.kind=E_SEQUENCE,.x=80,.y=400,.cost=1,.grants=8,.after="one"},
  {.id="two",.kind=E_SEQUENCE,.x=144,.y=400,.cost=2,.grants=16,.after="two"},
  {.id="key",.kind=E_CHEST,.x=304,.y=80,.grants=32,.after="key"},
  {.id="lamp",.kind=E_LAMP,.x=400,.y=304,.grants=64},
  {.id="coupled",.kind=E_SWITCH,.x=400,.y=80,.grants=192,.after="coupled"},
  {.id="turret",.kind=E_ENEMY,.x=336,.y=400,.hp=7,.behavior=1,.shot_period=.3f},
  {.id="logic_gate",.kind=E_DOOR,.x=400,.y=176,.requires=64,.forbids=128,.target_world=-1},
  {.id="opposite",.kind=E_SWITCH,.x=400,.y=240,.grants=128,.after="opposite"}
 };
 LumaWorld world={.id="puzzle_test",.name="test",.title="test",.width=16,.height=16,.tile=32,.terrain=terrain,.spawn_x=80,.spawn_y=176,.entity_count=13,.entities=entities,.indoors=1};LumaGame g;luma_init(&g,&world);g.world_index=6;
 assert(!luma_walkable(&g,272,176,WALK));use(&g,0);assert(g.actors[0].x==208);assert(g.flags&1);assert(luma_walkable(&g,272,176,WALK));
 LumaProgress p=luma_progress(&g);g.progress[6]=p;g.actors[0].x=176;luma_restore_objects(&g);assert(g.actors[0].x==208);puts("PASS crate push, pressure plate, door and object restoration");
 g.x=80;g.y=312;g.face_x=1;g.face_y=0;luma_step(&g,(LumaInput){0,0,0,B_SHOOT});for(int i=0;i<70;i++)luma_step(&g,(LumaInput){0});assert(g.flags&2);puts("PASS arrows cross water and activate distant target");
 use(&g,4);assert(g.flags&4);use(&g,4);assert(!(g.flags&4));use(&g,6);assert(!(g.flags&24));use(&g,5);assert(g.flags&8);use(&g,6);assert((g.flags&24)==24);use(&g,5);assert(!(g.flags&24));puts("PASS toggle switch and resettable ordered sequence");
 use(&g,7);assert(g.flags&32);unsigned crystals=g.crystals;uint64_t collected=g.collected;luma_step(&g,(LumaInput){0,0,B_RESET,0});assert(g.actors[0].x==176);assert(!(g.flags&31));assert(g.flags&32);assert(g.crystals==crystals&&g.collected==collected);puts("PASS room reset recovers crate mistakes without losing key or treasure");
 use(&g,9);assert((g.flags&192)==192&&!luma_walkable(&g,400,176,WALK));use(&g,12);assert((g.flags&192)==64&&luma_walkable(&g,400,176,WALK));puts("PASS coupled switches and required-on/required-off door masks");
 assert(g.actors[10].hp==7);g.x=80;g.y=400;for(unsigned i=0;i<50;i++)luma_step(&g,(LumaInput){0});assert(g.actors[10].x==336&&g.actors[10].y==400);unsigned hostile=0;for(unsigned i=0;i<LUMA_SHOTS;i++)hostile+=g.shots[i].live&&g.shots[i].hostile;assert(hostile);puts("PASS stationary turret, authored health and firing cadence");
 entities[8].kind=E_CRATE;g.actors[8].x=432;g.actors[8].y=368;g.actors[0].x=400;g.actors[0].y=400;g.x=432.2f;g.y=400;g.vx=g.vy=0;luma_step(&g,(LumaInput){-1,0,0,0});assert(g.nearby==0);luma_step(&g,(LumaInput){0,0,B_INTERACT,0});assert(g.actors[0].x==368&&g.actors[8].x==432);puts("PASS adjacent crate selection follows player facing\nLUMA_PUZZLE_PASS");return 0;
}
