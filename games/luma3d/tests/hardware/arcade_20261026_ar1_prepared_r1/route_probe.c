#define _POSIX_C_SOURCE 200809L
/* Labelled diagnostic, linked to the unchanged frozen arcade sources. */
#include "luma3d_render.h"
#include "luma3d_progress.h"
#include "luma3d_activities.h"
#include <assert.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static const uint32_t ids[]={0x4c455431,0x4c455432,0x4c455433,0x4c455434};
static const L3ProgressSchema schema={0x56414c31,5,4,ids};
static int host,opened,replay;
static const char *save_path;
static L3Render renderer;
static unsigned simulated_steps,activity_steps,rendered_frames,reloads,zero_dt_steps;
static volatile sig_atomic_t interrupted;
static void on_signal(int n){interrupted=n;}
static unsigned checksum(const void *data,size_t bytes){const unsigned char *p=data;unsigned c=~0u;while(bytes--){c^=*p++;for(unsigned i=0;i<8;i++)c=(c>>1)^(0xedb88320u&-(c&1));}return ~c;}
static double seconds(void){struct timespec t;assert(!clock_gettime(CLOCK_MONOTONIC,&t));return t.tv_sec+t.tv_nsec*1e-9;}
static void cancel(void){if(interrupted){if(opened)l3_render_close(&renderer);exit(128+interrupted);}}
static void draw(const L3Game *g){cancel();if(!opened){assert(l3_render_open(&renderer,host,0));opened=1;}assert(l3_render_frame(&renderer,g));rendered_frames++;}
static void ar_step(L3Game *g,const L3Input *in,float dt){
 cancel();l3_game_step(g,in,dt);simulated_steps++;
 if(replay&&g->story.region&&!g->autopilot){
  /* All timed arcade steps are shown. Walking is sampled at 5 Hz of
   * simulation; this is deliberately not a real-time benchmark. */
  if(g->activities.arcade.active){activity_steps++;draw(g);}
  else if(!(simulated_steps%12))draw(g);
 }
}
static void ar_activity_step(L3Game *g,const L3Input *in,float dt){
 cancel();l3_activity_step(g,in,dt);activity_steps++;if(dt==0)zero_dt_steps++;
 if(replay)draw(g); /* Unlike OP2, every zero-time logical move is shown. */
}
static void ar_capture(const L3Game *g,const char *name){
 if(replay){draw(g);printf("AR_CHECKPOINT name=%s active=%u won=%u region=%u x=%.3f y=%.3f z=%.3f\n",name,g->activities.arcade.active,g->activities.arcade.won,g->story.region,g->player.position.x,g->player.position.y,g->player.position.z);fflush(stdout);}
}
static void ar_reload(L3Game *g){
 assert(replay&&g->activities.arcade.active);
 assert(l3_progress_write(save_path,g,&schema)==L3_PROGRESS_OK);
 L3Game loaded;assert(l3_game_init(&loaded,&g->world,0));assert(l3_progress_read(save_path,&loaded,&schema)==L3_PROGRESS_OK);
 assert(!memcmp(&loaded.player,&g->player,sizeof(g->player))&&!memcmp(&loaded.camera,&g->camera,sizeof(g->camera)));
 L3ArcadeState expected=g->activities.arcade;expected.release_inputs=1;assert(!memcmp(&loaded.activities.arcade,&expected,sizeof(expected)));
 assert(loaded.time==g->time&&loaded.activities.pending_us==g->activities.pending_us);
 /* Continue from the actual file-loaded state. Release before sending the
  * next normal adviser input; no world time or reward is advanced. */
 *g=loaded;l3_activity_step(g,NULL,0);expected.release_inputs=0;assert(!memcmp(&g->activities.arcade,&expected,sizeof(expected)));
 reloads++;draw(g);printf("AR_RELOAD active=%u won=%u exact_pose=1 mid_activity=1\n",g->activities.arcade.active,g->activities.arcade.won);fflush(stdout);
}
static void ar_finish(const L3Game *g){
 assert(g->activities.arcade.won==255&&!g->activities.arcade.active&&reloads==8);
 assert(l3_progress_write(save_path,g,&schema)==L3_PROGRESS_OK);draw(g);
 printf("AR_COMPLETE won=%u active=%u region=%u phase=%u met_nils=%u reloads=%u input_steps=%u activity_steps=%u zero_dt_steps=%u rendered_frames=%u accelerated_replay=1\n",g->activities.arcade.won,g->activities.arcade.active,g->story.region,g->story.amber_phase,g->story.amber_met_nils,reloads,simulated_steps,activity_steps,zero_dt_steps,rendered_frames);fflush(stdout);
}
#include "route_core.inc"

int main(int argc,char **argv){
 signal(SIGTERM,on_signal);signal(SIGINT,on_signal);signal(SIGHUP,on_signal);
 int at=1;if(at<argc&&!strcmp(argv[at],"--host")){host=1;at++;}
 if(argc-at!=2)return 2;double start=seconds();
 if(!strcmp(argv[at],"--replay")){
  replay=1;save_path=argv[at+1];if(strncmp(save_path,"/tmp/",5)||strchr(save_path+5,'/'))return 2;assert(!ar_route_main());
 }else if(!strcmp(argv[at],"--scene")||!strcmp(argv[at],"--capture")){
  int capture=!strcmp(argv[at],"--capture");if(capture&&!host)return 2;
  char path[1100];snprintf(path,sizeof(path),"%s%s",argv[at+1],capture?".save":"");
  L3World w;L3Game g;l3_world_init(&w);assert(l3_game_init(&g,&w,0));assert(l3_progress_read(path,&g,&schema)==1);
  assert(l3_render_open(&renderer,host,0));opened=1;
  if(capture){snprintf(path,sizeof(path),"%s.commands",argv[at+1]);renderer.capture=fopen(path,"wb");assert(renderer.capture);}
  for(unsigned i=0;i<3;i++)draw(&g);
  if(capture){assert(!fclose(renderer.capture));renderer.capture=NULL;assert(l3_render_dump(&renderer,argv[at+1]));}
  printf("AR_SCENE active=%u won=%u region=%u fixed_fixture=1 frames=%u commands=%u batches=%u draws_last=%u triangles_last=%u mini_uploads=%u mini_bytes=%u\n",g.activities.arcade.active,g.activities.arcade.won,g.story.region,renderer.frame,renderer.total_commands,renderer.total_flushes,renderer.draws,renderer.triangles,renderer.mini_uploads,renderer.mini_bytes);
  printf("AR_PRESENT layers=%u sprites=%u palette_crc=%u descriptor_crc=%u cpu_descriptor=1\n",renderer.last_scene.layers_enabled,renderer.last_scene.sprites_enabled,checksum(&renderer.hud_palette,sizeof(renderer.hud_palette)),checksum(&renderer.last_scene,sizeof(renderer.last_scene)));
 }else if(!strcmp(argv[at],"--inspect-save")){
  L3World w;L3Game g;l3_world_init(&w);assert(l3_game_init(&g,&w,1));assert(l3_progress_read(argv[at+1],&g,&schema)==1);
  unsigned char data[L3_PROGRESS_MAX_BYTES];size_t bytes=0;assert(l3_progress_encode(&g,&schema,data,sizeof(data),&bytes)==1);
  printf("AR_SAVE bytes=%zu active=%u won=%u initialized=%u region=%u phase=%u auto=%d canonical_crc=%u\n",bytes,g.activities.arcade.active,g.activities.arcade.won,g.activities.arcade.initialized,g.story.region,g.story.amber_phase,g.autopilot,checksum(data,bytes));
 }else return 2;
 if(opened){printf("AR_RENDER frames=%u elapsed=%.6f commands=%u batches=%u feed_seconds=%.6f present_seconds=%.6f scope=accelerated_or_fixed_fixture\n",renderer.frame,seconds()-start,renderer.total_commands,renderer.total_flushes,renderer.feed_seconds,renderer.present_seconds);assert(l3_render_close(&renderer));}
 puts("AR_PASS");return 0;
}
