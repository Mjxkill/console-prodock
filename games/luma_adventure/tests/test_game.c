/* SPDX-License-Identifier: MIT */
#define _POSIX_C_SOURCE 200809L
#include "luma.h"
#include "stepper.h"
#include <assert.h>
#include <errno.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
static void step(LumaGame *g,float x,float y,unsigned pressed,unsigned held){luma_step(g,(LumaInput){x,y,pressed,held});}
static int entity(const LumaGame *g,unsigned kind){for(unsigned i=0;i<g->world->entity_count;i++)if(g->world->entities[i].kind==kind)return (int)i;return -1;}
static void approach(LumaGame *g,int i){g->x=g->actors[i].x;g->y=g->actors[i].y;step(g,0,0,0,0);g->nearby=i;}
int main(void){
 LumaGame a,b;luma_init(&a,&luma_world);LumaStepper clock={0};assert(luma_frame_steps(&clock,&a,(LumaInput){0,0,B_MAP,0},.001)==0);assert(!a.map);assert(luma_frame_steps(&clock,&a,(LumaInput){0},.016)==1);assert(a.map);assert(luma_frame_steps(&clock,&a,(LumaInput){0,0,B_MAP,0},.05)==3);assert(!a.map);puts("PASS input edges survive frames without simulation and are consumed once");
luma_init(&a,&luma_world);luma_init(&b,&luma_world);assert(luma_world_count>=6);
 for(int n=0;n<18000;n++){LumaInput in={sinf(n*.013f),cosf(n*.017f),n%51==0?B_ATTACK:0,n%7<3?B_SHOOT:0};luma_step(&a,in);luma_step(&b,in);}assert(!memcmp(&a,&b,sizeof(a)));assert(isfinite(a.x)&&isfinite(a.y));puts("PASS deterministic 18,000 fixed simulation steps");
 luma_init(&a,&luma_world);int npc=entity(&a,E_NPC);assert(npc>=0);approach(&a,npc);step(&a,0,0,B_INTERACT,0);assert(a.flags&1);assert(a.dialogue==npc);float x=a.x,y=a.y;for(int i=0;i<120;i++)step(&a,1,0,0,0);assert(a.x==x&&a.y==y);step(&a,0,0,B_INTERACT,0);assert(a.dialogue==-1);
 int shrine=entity(&a,E_SHRINE);assert(shrine>=0);approach(&a,shrine);unsigned flags=a.flags;step(&a,0,0,B_INTERACT,0);assert(a.flags==flags);a.crystals=20;
 for(unsigned i=0;i<a.world->entity_count;i++)if(a.world->entities[i].kind==E_ENEMY)a.actors[i].alive=0;
 approach(&a,shrine);step(&a,0,0,B_INTERACT,0);assert(a.activated&(UINT64_C(1)<<shrine));assert(a.flags&a.world->entities[shrine].grants);unsigned crystals=a.crystals;step(&a,0,0,B_INTERACT,0);assert(a.crystals==crystals);puts("PASS dialogue pause, shrine preconditions and idempotence");
 int chest=entity(&a,E_CHEST);approach(&a,chest);step(&a,0,0,B_INTERACT,0);crystals=a.crystals;step(&a,0,0,B_INTERACT,0);assert(a.crystals==crystals);assert(a.secrets==1);
 int enemy=entity(&a,E_ENEMY);assert(enemy>=0);a.actors[enemy].alive=1;a.actors[enemy].hp=3;a.actors[enemy].x=a.x+20;a.actors[enemy].y=a.y;a.face_x=1;a.face_y=0;a.attack=0;a.actors[enemy].stun=0;step(&a,0,0,B_ATTACK,0);assert(a.actors[enemy].hp==2);for(int n=0;n<30;n++)step(&a,0,0,0,0);a.actors[enemy].x=a.x+20;a.actors[enemy].y=a.y;step(&a,0,0,B_ATTACK,0);assert(a.actors[enemy].hp==1);for(int n=0;n<30;n++)step(&a,0,0,0,0);a.actors[enemy].x=a.x+20;a.actors[enemy].y=a.y;step(&a,0,0,B_ATTACK,0);assert(!a.actors[enemy].alive);assert(a.defeated&(UINT64_C(1)<<enemy));puts("PASS melee damage, cooldown and persistent defeat");
 uint64_t collected=a.collected,defeated=a.defeated;flags=a.flags;assert(luma_enter(&a,1,0,0)==0);assert(a.flags==0&&!a.collected);a.flags=7;assert(luma_enter(&a,0,0,0)==0);assert(a.flags==flags&&a.collected==collected&&a.defeated==defeated);assert(luma_enter(&a,1,0,0)==0&&a.flags==7);puts("PASS transitions preserve each world's progression");
 char path[256];snprintf(path,sizeof(path),"/tmp/luma-test-%ld.sav",(long)getpid());assert(luma_save(&a,path)==0);luma_init(&b,&luma_world);assert(luma_load(&b,path)==0);assert(a.world_index==b.world_index&&a.flags==b.flags&&a.crystals==b.crystals&&a.progress[0].collected==b.progress[0].collected);assert(fabsf(a.x-b.x)<.004f);
 FILE *f=fopen(path,"r+b");assert(f);fseek(f,35,SEEK_SET);fputc(213,f);fclose(f);LumaGame before=b;assert(luma_load(&b,path)==-1&&errno==EINVAL);assert(!memcmp(&b,&before,sizeof(b)));unlink(path);puts("PASS atomic save/load, per-map state and corruption rejection");
 luma_init(&a,&luma_world);int water=-1;for(int i=0;i<a.world->width*a.world->height;i++)if(a.world->terrain[i]=='~'){water=i;break;}assert(water>=0);x=(water%a.world->width+.5f)*a.world->tile;y=(water/a.world->width+.5f)*a.world->tile;assert(!luma_walkable(&a,x,y,WALK));assert(luma_walkable(&a,x,y,GLIDER));a.unlocked=255;a.x=x;a.y=y;a.vehicle=GLIDER;step(&a,0,0,B_VEHICLE,0);assert(a.vehicle==PARACHUTE||a.vehicle==PLANE||a.vehicle==GLIDER);puts("PASS traversal rules prevent landing in water");
 luma_init(&a,&luma_world);assert(!luma_enter(&a,5,0,0));a.missions=UINT16_MAX;a.flags=0xffffff;int ending=-1,back=-1;for(unsigned i=0;i<a.world->entity_count;i++){const LumaEntity *e=a.world->entities+i;if(e->kind==E_PORTAL){if(e->target_world<0)ending=(int)i;else back=(int)i;}}assert(ending>=0&&back>=0);approach(&a,ending);step(&a,0,0,B_INTERACT,0);assert(a.won&&a.ending_open);unsigned tick=a.tick;x=a.x;y=a.y;step(&a,1,0,0,0);assert(a.tick==tick&&a.x==x&&a.y==y);step(&a,0,0,B_INTERACT,0);assert(a.won&&!a.ending_open&&a.tick==tick);step(&a,0,0,0,0);assert(a.tick==tick+1);approach(&a,back);step(&a,0,0,B_INTERACT,0);assert(a.world_index==4&&a.won&&!a.ending_open);puts("PASS ending can be dismissed and world travel preserves completed story");
 unsigned local_doors=0;for(unsigned wi=0;wi<luma_world_count;wi++){luma_init(&a,&luma_world);luma_enter(&a,wi,0,0);assert(luma_walkable(&a,a.x,a.y,WALK));assert(a.world->entity_count<=64);for(unsigned i=0;i<a.world->entity_count;i++){const LumaEntity *e=a.world->entities+i;if(e->kind!=E_DOOR&&e->kind!=E_CRATE&&e->kind!=E_TARGET&&e->kind!=E_MIRROR)assert(luma_walkable(&a,e->x,e->y,WALK));assert(e->target_world<(int)luma_world_count);if(wi==2&&e->kind==E_DOOR&&e->target_world==(int)wi){a.flags=e->requires;approach(&a,(int)i);a.dirty=0;step(&a,0,0,B_INTERACT,0);assert(a.world_index==wi&&fabsf(a.x-e->target_x)<4&&fabsf(a.y-e->target_y)<4&&a.dirty);local_doors++;}}}assert(local_doors);puts("PASS local doors request autosave after moving the player");
 puts("PASS all worlds' spawn, entity and portal bounds\nLUMA_LOGIC_PASS");return 0;
}
