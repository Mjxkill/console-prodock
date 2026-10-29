/* SPDX-License-Identifier: MIT */
#define _POSIX_C_SOURCE 200809L
#include "luma.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
static char terrain[16*16];
static LumaEntity entities[8];
const LumaWorld luma_worlds[]={
 {.id="light_test",.name="Light test",.title="Light test",.width=16,.height=16,.tile=32,.terrain=terrain,.spawn_x=80,.spawn_y=80,.entity_count=8,.entities=entities,.indoors=1},
 {.id="return_test",.name="Return",.title="Return",.width=16,.height=16,.tile=32,.terrain=terrain,.spawn_x=80,.spawn_y=80}
};
const unsigned luma_world_count=2;
static const int dx[]={1,0,-1,0},dy[]={0,1,0,-1};
static void setup(void){
 memset(terrain,'.',sizeof(terrain));
 for(unsigned i=0;i<16;i++)terrain[i]=terrain[240+i]=terrain[i*16]=terrain[i*16+15]='#';
 static const char *ids[]={"a","b","c","d","e","f","g","h"};
 for(unsigned i=0;i<8;i++)entities[i]=(LumaEntity){.id=ids[i],.name=ids[i],.text="",.after="",.kind=E_LAMP,.x=400,.y=400,.vehicle=255};
}
static void use(LumaGame *g,unsigned target,int vx,int vy){
 g->x=g->actors[target].x-vx*24;g->y=g->actors[target].y-vy*24;
 g->vx=g->vy=0;g->face_x=vx;g->face_y=vy;luma_step(g,(LumaInput){0});
 assert(g->nearby==(int)target);luma_step(g,(LumaInput){0,0,B_INTERACT,0});
}
int main(void){
 LumaGame g;
 for(unsigned incoming=0;incoming<4;incoming++)for(unsigned orientation=0;orientation<2;orientation++){
  setup();unsigned outgoing=incoming^(orientation?1:3),other=incoming^(orientation?3:1);
  entities[0].kind=E_EMITTER;entities[0].x=240-dx[incoming]*32;entities[0].y=240-dy[incoming]*32;entities[0].behavior=incoming;
  entities[1].kind=E_MIRROR;entities[1].x=entities[1].y=240;entities[1].cost=orientation;
  entities[2].kind=E_RECEIVER;entities[2].x=240+dx[outgoing]*64;entities[2].y=240+dy[outgoing]*64;entities[2].grants=1;
  entities[3].kind=E_RECEIVER;entities[3].x=240+dx[other]*64;entities[3].y=240+dy[other]*64;entities[3].grants=2;
  luma_init(&g,&luma_world);assert(g.flags==1&&!g.light_fault);assert(!luma_walkable(&g,240,240,WALK));
  use(&g,1,1,0);assert(g.mirror_orientation[1]==(orientation^1));assert(g.flags==2&&!g.light_fault);
 }
 puts("PASS all eight reflections, receiver deactivation, real mirror interaction and collision");
 setup();entities[0].kind=E_EMITTER;entities[0].x=80;entities[0].y=176;
 entities[1].kind=E_RECEIVER;entities[1].x=272;entities[1].y=176;entities[1].grants=1;
 entities[2].kind=E_DOOR;entities[2].x=208;entities[2].y=176;entities[2].requires=32;
 terrain[5*16+4]='~';luma_init(&g,&luma_world);assert(g.flags==1);assert(!luma_walkable(&g,208,176,WALK));
 entities[3].kind=E_CRATE;entities[3].x=144;entities[3].y=176;terrain[5*16+4]='.';luma_init(&g,&luma_world);assert(!g.flags);
 use(&g,3,0,1);assert(g.actors[3].y==208&&(g.flags&1));
 entities[4].kind=E_MIRROR;entities[4].x=144;entities[4].y=304;luma_init(&g,&luma_world);
 use(&g,4,1,0);use(&g,3,0,1);g.crystals=17;g.flags|=32;g.collected=UINT64_C(1)<<6;
 assert(!luma_enter(&g,1,0,0));assert(!g.beam_count);assert(!luma_enter(&g,0,0,0));assert(g.mirror_orientation[4]==1&&g.actors[3].y==208&&(g.flags&1));
 char dir[]="/tmp/luma-light-XXXXXX",path[128];assert(mkdtemp(dir));snprintf(path,sizeof(path),"%s/save",dir);assert(!luma_save(&g,path));LumaGame restored;luma_init(&restored,&luma_world);assert(!luma_load(&restored,path));assert(restored.mirror_orientation[4]==1&&restored.actors[3].y==208&&(restored.flags&1));
 luma_step(&restored,(LumaInput){0,0,B_RESET,0});assert(!restored.mirror_orientation[4]&&restored.actors[3].y==176&&!(restored.flags&1));assert((restored.flags&32)&&restored.crystals==17&&restored.collected==(UINT64_C(1)<<6));
 unsigned char saved[131072];FILE *file=fopen(path,"rb");assert(file&&fread(saved,1,sizeof(saved),file)==sizeof(saved));fclose(file);
 unsigned at=128+704+4*4;saved[at]=2; /* CRC-valid, but impossible mirror orientation. */
 uint32_t crc=luma_crc(saved,sizeof(saved)-4);for(unsigned i=0;i<4;i++)saved[sizeof(saved)-4+i]=crc>>(8*i);
 file=fopen(path,"wb");assert(file&&fwrite(saved,1,sizeof(saved),file)==sizeof(saved));assert(!fclose(file));
 LumaGame before=restored;assert(luma_load(&restored,path)!=0);assert(!memcmp(&before,&restored,sizeof(before)));
 unlink(path);rmdir(dir);puts("PASS water/door transmission, crate occlusion, cross-world/save restoration and reward-safe reset");
 setup();entities[0].kind=E_EMITTER;entities[0].x=80;entities[0].y=176;entities[0].requires=128;
 entities[1].kind=E_RECEIVER;entities[1].x=272;entities[1].y=176;entities[1].grants=1;
 entities[2].kind=E_SWITCH;entities[2].x=80;entities[2].y=272;entities[2].grants=128;
 luma_init(&g,&luma_world);assert(!g.flags&&!g.beam_count);use(&g,2,1,0);assert(g.flags==129&&g.beam_count);use(&g,2,1,0);assert(!g.flags&&!g.beam_count);
 entities[3].kind=E_CRATE;entities[3].x=80;entities[3].y=176;luma_init(&g,&luma_world);g.flags=128;luma_light_update(&g);assert(g.flags==128&&!g.beam_count);use(&g,3,0,1);assert(g.flags==129);
 entities[0].kind=E_LAMP;luma_init(&g,&luma_world);g.flags=1;luma_light_update(&g);assert(!g.flags&&!g.beam_count);puts("PASS switched sources, source occlusion and receivers without a source");
 setup();entities[0].kind=E_EMITTER;entities[0].x=80;entities[0].y=176;entities[0].requires=128;
 entities[1].kind=E_RECEIVER;entities[1].x=272;entities[1].y=176;entities[1].grants=1;
 entities[2].kind=E_PLATE;entities[2].x=80;entities[2].y=272;entities[2].grants=128;
 entities[3].kind=E_DOOR;entities[3].x=304;entities[3].y=304;entities[3].requires=1;entities[3].target_world=1;
 luma_init(&g,&luma_world);g.x=80;g.y=272;luma_step(&g,(LumaInput){0});assert(g.flags==129);
 assert(!luma_enter(&g,1,0,0));assert(!luma_enter(&g,0,0,0));assert(!g.flags&&!g.beam_count);
 g.x=304;g.y=280;g.flags=129;g.nearby=3;luma_step(&g,(LumaInput){0,0,B_INTERACT,0});assert(g.world_index==0&&!g.flags);
 char plate_dir[]="/tmp/luma-light-plate-XXXXXX";assert(mkdtemp(plate_dir));snprintf(path,sizeof(path),"%s/save",plate_dir);
 g.x=80;g.y=272;luma_step(&g,(LumaInput){0});assert(g.flags==129);assert(!luma_save(&g,path));assert(!luma_load(&restored,path));assert(restored.flags==129&&restored.beam_count);
 g.x=g.y=16;assert(!luma_save(&g,path));assert(!luma_load(&restored,path));assert(restored.x==80&&restored.y==80&&!restored.flags&&!restored.beam_count);unlink(path);rmdir(plate_dir);
 puts("PASS plate-driven light recomputed before entry, interaction and recovered save position");
 setup();entities[0].kind=E_EMITTER;entities[0].x=240;entities[0].y=176;
 int xs[]={176,304,304,176},ys[]={176,176,304,304};
 for(unsigned i=0;i<4;i++){entities[i+1].kind=E_MIRROR;entities[i+1].x=xs[i];entities[i+1].y=ys[i];entities[i+1].cost=i&1;}
 entities[5].kind=E_RECEIVER;entities[5].x=240;entities[5].y=304;entities[5].grants=4;
 luma_init(&g,&luma_world);assert((g.flags&4)&&g.beam_count==5&&!g.light_fault);
 puts("PASS finite tracing of a closed mirror loop\nLUMA_LIGHT_PASS");return 0;
}
