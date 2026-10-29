/* Hardware functional fixture. Uses real inputs and the unchanged game/render
 * engine, but seeds its starting chapter prerequisites. Never writes a save.
 * Rendering every fourth step (and every interaction) is deliberately NOT a
 * real-time gameplay cadence or a performance benchmark. */
#define _POSIX_C_SOURCE 200809L
#include "video.h"
#include <signal.h>
#include <stdlib.h>
#include <string.h>
static void observed_step(LumaGame *g,LumaInput input);
#define luma_step observed_step
#include "play_dungeon.h"
#undef luma_step
static LumaVideo video;
static unsigned calls,rotations,beam_changes,max_beams,beam_frames;
static volatile sig_atomic_t stopping;
static int opened;
static void stop(int signal_number){(void)signal_number;stopping=1;}
static void close_video(void){if(opened)luma_video_close(&video);}
static void observed_step(LumaGame *g,LumaInput input){
 if(stopping)exit(2);
 unsigned world=g->world_index;uint8_t before[LUMA_MAX_ENTITIES];memcpy(before,g->mirror_orientation,sizeof(before));
 uint32_t old=luma_crc(g->beams,g->beam_count*sizeof(*g->beams));
 luma_step(g,input);calls++;assert(!g->light_fault);
 if(world==g->world_index)for(unsigned i=0;i<g->world->entity_count;i++)if(g->world->entities[i].kind==E_MIRROR&&before[i]!=g->mirror_orientation[i])rotations++;
 if(old!=luma_crc(g->beams,g->beam_count*sizeof(*g->beams)))beam_changes++;
 if(g->beam_count>max_beams)max_beams=g->beam_count;
 if(calls%4==0||input.pressed||world!=g->world_index){luma_render(&video,g);beam_frames+=g->beam_count>0;if(video.failed)exit(1);}
}
int main(int argc,char **argv){
 assert(argc>=3);int final=!strcmp(argv[1],"final");assert(final||!strcmp(argv[1],"first"));
 int host=0;
#ifdef LUMA_HOST
 host=1;
#endif
 atexit(close_video);if(luma_video_open(&video,host,0,argv[2]))return 1;opened=1;
 signal(SIGTERM,stop);signal(SIGINT,stop);signal(SIGHUP,stop);
 LumaGame g;luma_init(&g,&luma_world);unsigned start=final?35:26,finish=final?2:27,gallery=0;
 if(final){g.progress[2].flags=511;for(unsigned i=0;i<luma_worlds[2].mission_count;i++)if(strcmp(luma_worlds[2].missions[i].id,"c17_reflections"))g.progress[2].missions|=1U<<i;}
 printf("LUMA_PROBE_FIXTURE case=%s direct_start=%u outer_prerequisites_seeded=%d saving_disabled=1 render_every_four_steps_and_interactions=1\n",argv[1],start,final);fflush(stdout);
 assert(!luma_enter(&g,start,0,0));assert(!vehicle(&g,WALK));luma_render(&video,&g);assert(!video.failed);
 assert(!play_dungeon(&g));assert(g.world_index==finish);
 if(final){
  assert((g.progress[35].flags&32)&&(g.flags&512));
  const char *ids[]={"post_gallery_west","post_gallery_east"};
  for(unsigned i=0;i<2;i++){int target=entity_id(&g,ids[i]);assert(target>=0);const LumaEntity *e=g.world->entities+target;assert(luma_entity_enabled(&g,e));assert(!reach(&g,(unsigned)target));unsigned crystals=g.crystals;interact(&g);assert(g.world_index==2&&fabsf(g.x-e->target_x)<4&&fabsf(g.y-e->target_y)<4&&g.crystals==crystals);gallery++;}
 }
 luma_render(&video,&g);assert(!video.failed&&rotations&&beam_changes&&beam_frames);
 if(argc>3){assert(!luma_snapshot(&video,argv[3]));}
 printf("LUMA_PROBE_PASS case=%s start_world=%u end_world=%u steps=%u rendered_frames=%u rotations=%u beam_changes=%u max_beams=%u beam_frames=%u gallery=%u loading_scenes=%u status=0\n",argv[1],start,g.world_index,calls,video.frames,rotations,beam_changes,max_beams,beam_frames,gallery,video.loading_scenes);
 return 0;
}
