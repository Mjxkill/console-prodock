/* Candidate indexed backend: actual GPU descriptors, dirty rows and page reuse. */
#include "video.h"
#include "assets.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#ifndef LUMA_INDEXED_BACKGROUND
#error Test requires the indexed resource layout
#endif
static void fresh_equal(LumaVideo *cached,const LumaGame *g,int wide){
 LumaVideo fresh;assert(!luma_video_open(&fresh,1,wide,"build/indexed/luma.pak"));luma_render(&fresh,g);
 assert(!fresh.failed&&!cached->failed);assert(!memcmp(fresh.pixels,cached->pixels,cached->width*cached->height*8));luma_video_close(&fresh);
}
int main(void){
 for(int wide=0;wide<2;wide++){
  LumaVideo v;LumaGame g;luma_init(&g,&luma_world);assert(!luma_video_open(&v,1,wide,"build/indexed/luma.pak"));
  for(unsigned i=0;i<sizeof(luma_effect_rgb565)/sizeof(*luma_effect_rgb565);i++)assert(v.palette[LUMA_EFFECT_FIRST+i]==luma_effect_rgb565[i]);
  for(unsigned frame=0;frame<8;frame++){
   /* Alternate sparse particles, overlapping arrows and empty effects across both pages. */
   memset(g.particles,0,sizeof(g.particles));memset(g.shots,0,sizeof(g.shots));g.time=frame*.41f;g.attack=frame==3?.1f:0;
   if(frame<4){for(unsigned i=0;i<9;i++)g.particles[i]=(LumaParticle){g.x-205+(float)i*49,g.y-115+(float)i*28,0,0,0,luma_effect_rgb565[i],1};for(unsigned i=0;i<8;i++)g.shots[i]=(LumaShot){.x=g.x-80+i*18,.y=g.y-30+i*8,.live=1,.hostile=i&1};}
   g.camera_x=g.x+frame*3;g.camera_y=g.y+frame*2;luma_render(&v,&g);assert(!v.failed);fresh_equal(&v,&g,wide);assert(v.commands==0);if(frame==3){char path[100];snprintf(path,sizeof(path),"build/indexed/effects_%u",wide?720:480);assert(!luma_capture(&v,path));}
  }
  /* Dense scenes keep all four hero quadrants within the 64-sprite budget. */
  LumaGame saved=g;LumaWorld crowded=*g.world;LumaEntity npcs[32];memset(npcs,0,sizeof(npcs));crowded.entities=npcs;crowded.entity_count=32;g.world=&crowded;g.face_x=0;g.face_y=1;g.vx=g.vy=0;g.invincible=0;
  for(unsigned i=0;i<32;i++){npcs[i].kind=E_NPC;npcs[i].art=1;g.actors[i].x=g.x+(int)(i%8)*3-12;g.actors[i].y=g.y+(int)(i/8)*3-6;g.actors[i].alive=1;}
  luma_render(&v,&g);assert(!v.failed&&v.sprites==64&&v.sprites_culled>=17);unsigned hero=0;
  for(unsigned i=0;i<v.sprites;i++){unsigned address=v.scene.sprites[i][0];if(address>=PRODOCK_GPU_BASE+LUMA_ASSET_BASE+luma_art_offsets[0]&&address<PRODOCK_GPU_BASE+LUMA_ASSET_BASE+luma_art_offsets[0]+4096)hero++;}
  assert(hero==4);g=saved;
  assert(!luma_enter(&g,9,0,0));luma_render(&v,&g);assert(v.loading_scenes==1);assert(!v.scene.layers[12][6]);fresh_equal(&v,&g,wide);for(unsigned wi=0;wi<luma_world_count;wi++){assert(!luma_enter(&g,wi,0,0));luma_render(&v,&g);assert(!v.failed);}
  if(luma_world_count>26){
   assert(!luma_enter(&g,26,0,0));unsigned mirror=0;while(mirror<g.world->entity_count&&g.world->entities[mirror].kind!=E_MIRROR)mirror++;assert(mirror<g.world->entity_count);
   /* Rendering fixtures alternate both real optical states across both pages. */
   g.camera_x=g.actors[mirror].x;g.camera_y=g.actors[mirror].y;
   for(unsigned frame=0;frame<6;frame++){g.mirror_orientation[mirror]=(frame/2)&1;g.light_dirty=1;luma_light_update(&g);assert(g.beam_count&&!g.light_fault);luma_render(&v,&g);fresh_equal(&v,&g,wide);if(frame==2){char path[100];snprintf(path,sizeof(path),"build/indexed/light_%u",wide?720:480);assert(!luma_capture(&v,path));}}
  }
  luma_video_close(&v);
 }
 printf("LUMA_INDEXED_PASS worlds=%u effects exact, both pages, clipping, camera scroll, world change, 800/720\n",luma_world_count);return 0;
}
